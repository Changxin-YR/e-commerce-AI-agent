"""D2 contract fixtures: synthetic, never presented as real UCI acceptance evidence."""
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from datetime import datetime
from decimal import Decimal
import io
import json
from pathlib import Path
import sqlite3
import stat
import subprocess
import sys
import time
from unittest.mock import patch
from zipfile import ZipFile, ZipInfo, ZIP_DEFLATED

from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from openpyxl import Workbook
import pytest

from backend.app.config import PROJECT_ROOT, Settings
from backend.app.errors import AppError
from backend.app.imports.rows import INT64_MAX, price_milli, transform_row
from backend.app.imports.service import ImportService
from backend.app.imports.source import HEADERS, MAX_UPLOAD, inspect_zip, prepare_source, sha256
from backend.app.main import create_app

MIME = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
ORIGIN = {"Origin": "http://127.0.0.1:5173"}


@pytest.fixture
def config(tmp_path):
    settings = Settings(_env_file=None, database_url=f"sqlite:///{(tmp_path/'app.db').as_posix()}",
                        app_env="test", import_cache_dir=tmp_path / "cache", raw_data_dir=tmp_path / "raw")
    cfg = Config(str(PROJECT_ROOT / "backend/alembic.ini"))
    cfg.attributes["settings"] = settings
    command.upgrade(cfg, "head")
    return settings


def workbook(path, rows=None):
    book = Workbook()
    sheet = book.active
    sheet.title = "Online Retail"
    sheet.append(HEADERS)
    for row in rows or [["100001", "test_fixture", "=not executed", 3, datetime(2011, 9, 1), 0.001, None, "United Kingdom"]]:
        sheet.append(row)
        # Source descriptions may begin '=' as literal text; actual formulas are tested separately.
        sheet.cell(sheet.max_row, 3).data_type = "s"
    book.save(path)
    return path


@pytest.fixture
def source(tmp_path):
    return workbook(tmp_path / "test_fixture.xlsx")


@contextmanager
def importer(config, source):
    service = ImportService(config, test_hashes=frozenset({sha256(source)}))
    service.start()
    try:
        yield service
    finally:
        service.close()


def cells(invoice="1", quantity="1", price="1E-3", stock="test_fixture", customer=None):
    values = [invoice, stock, "test_fixture", quantity, "40787", price, customer, "United Kingdom"]
    return [{"type": "n" if i in {3, 4, 5, 6} else "str", "raw": v, "value": v} for i, v in enumerate(values)]


@pytest.mark.parametrize("raw,milli,adjusted", [("1E-3", 1, False), ("2.5499999999999998", 2550, True),
    ("1.000000001", 1000, True), ("-11062.06", -11062060, False)])
def test_price_grid(raw, milli, adjusted):
    assert price_milli(raw) == (milli, adjusted)


@pytest.mark.parametrize("raw", ["0.0011", "1.0000000011", "NaN", "Infinity", "1E99", None, "9" * 65])
def test_price_rejects_loss_or_overflow(raw):
    with pytest.raises((ValueError, ArithmeticError)):
        price_milli(raw)


def test_frozen_contract_vectors():
    vectors = json.loads((PROJECT_ROOT / "docs/plan/fixtures/ecommerce_contract_cases.json").read_text(encoding="utf-8"))
    for vector in vectors["row_class_vectors"]:
        raw = str(Decimal(vector["unit_price_milli_gbp"]) / 1000)
        row = transform_row("fixture", 2, cells(vector["invoice_no"], str(vector["quantity"]), raw))
        assert row["primary_class"] == vector["expected_class"], vector["name"]
        assert row["line_amount_milli_gbp"] == vector["expected_signed_amount_milli_gbp"]
        assert row["unit_price_raw"] == raw
        assert "MISSING_CUSTOMER_ID" in row["quality_flags"]
    assert transform_row("x", 2, cells("c1", "0"))["primary_class"] == "EXCLUDED_OTHER"


@pytest.mark.parametrize("index,value", [(0, None), (1, None), (3, "1.1"), (4, "bad"), (5, "0.0005")])
def test_invalid_rows_preserve_raw(index, value):
    raw = cells()
    raw[index]["raw"] = raw[index]["value"] = value
    row = transform_row("fixture", 2, raw)
    assert row["primary_class"] == "INVALID"
    assert row["raw_fields"] == raw


def test_integer_line_overflow():
    row = transform_row("fixture", 2, cells(quantity=str(INT64_MAX), price="2"))
    assert row["primary_class"] == "INVALID"
    assert "MONEY_OVERFLOW" in row["quality_flags"]


def test_sql_strings_duplicates_and_missing_customer_are_retained(config, tmp_path):
    values = ["100001", "'); DROP TABLE transaction_rows; --", "test_fixture", 3, datetime(2011, 9, 1), 0.001, None, "United Kingdom"]
    source = workbook(tmp_path / "fixture.xlsx", [values, values])
    with importer(config, source) as service:
        result = service.submit(source, background=False)
        assert result["status"] == "READY"
        quality = service.profile(result["dataset_id"], quality=True)
        assert quality["raw_row_count"] == 2
        assert quality["primary_class_counts"]["POSITIVE"] == 2
        assert quality["quality_flags"]["MISSING_CUSTOMER_ID"] == 2
        assert quality["duplicate_candidates_after_first"] == 1
        assert quality["duplicate_group_rows"] == 2
        with sqlite3.connect(config.database_path) as db:
            assert db.execute("SELECT COUNT(*), SUM(line_amount_milli_gbp) FROM transaction_rows").fetchone() == (2, 6)
            assert db.execute("SELECT stock_code FROM transaction_rows LIMIT 1").fetchone()[0] == values[1]


def test_failed_partial_retry_and_history(config, tmp_path, monkeypatch):
    item = ["1", "x", "test_fixture", 1, datetime(2011, 9, 1), 1, None, "UK"]
    source = workbook(tmp_path / "test_fixture.xlsx", [item, item, item])
    import backend.app.imports.service as module
    monkeypatch.setattr(module, "BATCH_SIZE", 1)
    with importer(config, source) as service:
        original = service._write_chunk
        calls = 0
        def fail_after_one(*args):
            nonlocal calls
            calls += 1
            if calls == 2:
                raise RuntimeError("private test_fixture_secret")
            return original(*args)
        monkeypatch.setattr(service, "_write_chunk", fail_after_one)
        first = service.submit(source, background=False)
        assert first["status"] == "FAILED" and first["processed_rows"] == 1
        assert first["error_code"] == "IMPORT_FAILED"
        with pytest.raises(AppError, match="DATASET_NOT_READY"):
            service.profile(first["dataset_id"], quality=True)
        assert service.profile(first["dataset_id"])["row_count"] is None
        monkeypatch.setattr(service, "_write_chunk", original)
        second = service.submit(source, background=False)
        assert second["status"] == "READY" and second["processed_rows"] == 3
        assert second["batch_id"] == first["batch_id"] and second["attempt"] == 2
        assert len(second["failures"]) == 1
        assert "private" not in json.dumps(second)


def test_invalid_precision_keeps_row_but_blocks_ready(config, tmp_path):
    source = workbook(tmp_path / "test_fixture.xlsx", [["1", "x", "test_fixture", 1, datetime(2011, 9, 1), 0.0011, None, "UK"]])
    with importer(config, source) as service:
        result = service.submit(source, background=False)
        assert result["status"] == "FAILED" and result["error_code"] == "INVALID_ROWS_PRESENT"
    with sqlite3.connect(config.database_path) as db:
        assert db.execute("SELECT primary_class,unit_price_raw FROM transaction_rows").fetchone() == ("INVALID", "0.0011")


def test_restart_recovery_and_active_writer_protection(config, source):
    with importer(config, source) as first:
        result = first.submit(source, background=False)
        with sqlite3.connect(config.database_path) as db:
            db.execute("UPDATE import_batches SET status='IMPORTING'")
            db.execute("UPDATE dataset_snapshots SET status='IMPORTING'")
        with importer(config, source) as concurrent:
            assert concurrent.batch(result["batch_id"])["status"] == "IMPORTING"
    with importer(config, source) as recovered:
        assert recovered.batch(result["batch_id"])["error_code"] == "IMPORT_INTERRUPTED"
        assert recovered.submit(source, background=False)["status"] == "READY"


def test_parallel_duplicate_requests_single_identity(config, source):
    with importer(config, source) as service:
        with ThreadPoolExecutor(max_workers=4) as pool:
            results = list(pool.map(lambda _: service.submit(source), range(4)))
        service.executor.shutdown(wait=True)
        assert len({r["batch_id"] for r in results}) == 1
        assert service.batch(results[0]["batch_id"])["status"] == "READY"
    with sqlite3.connect(config.database_path) as db:
        assert db.execute("SELECT COUNT(*) FROM transaction_rows").fetchone()[0] == 1


def test_api_zip_xlsx_idempotence_and_read_only_history(config, source, tmp_path):
    outer = tmp_path / "test_fixture.zip"
    with ZipFile(outer, "w") as z:
        z.write(source, "Online Retail.xlsx")
    application = create_app(config, test_hashes=frozenset({sha256(source)}))
    with TestClient(application, base_url="http://127.0.0.1") as client:
        response = client.post("/api/v1/datasets/imports", files={"file": (outer.name, outer.read_bytes(), "application/zip")}, headers=ORIGIN)
        assert response.status_code == 202
        batch_id, dataset_id = response.json()["batch_id"], response.json()["dataset_id"]
        application.state.import_service.executor.shutdown(wait=True)
        assert client.get(f"/api/v1/datasets/imports/{batch_id}").json()["status"] == "READY"
        repeat = client.post("/api/v1/datasets/imports", files={"file": (source.name, source.read_bytes(), MIME)}, headers=ORIGIN)
        assert repeat.status_code == 200 and repeat.json()["batch_id"] == batch_id
        assert len(repeat.json()["containers"]) == 2
        before = sha256(config.database_path)
        for path in [f"/{dataset_id}", f"/{dataset_id}/quality", f"/imports/{batch_id}"]:
            response = client.get("/api/v1/datasets" + path)
            assert response.status_code == 200
            assert str(config.raw_data_dir) not in response.text
        assert sha256(config.database_path) == before
        assert client.get("/api/v1/datasets/missing").status_code == 404
    assert not list(config.import_cache_dir.glob("*.xlsx"))


@pytest.mark.parametrize("name,mime,body,code", [
    ("../../secret.xlsx", MIME, b"bad", "UNSAFE_UPLOAD_NAME"),
    ("x.txt", "text/plain", b"bad", "UNSUPPORTED_FILE_TYPE"),
    ("x.xlsx", "text/html", b"bad", "UNSUPPORTED_MIME_TYPE"),
    ("x.xlsx", MIME, b"bad", "CORRUPT_SOURCE"),
])
def test_rejected_uploads_are_sanitized(config, name, mime, body, code):
    with TestClient(create_app(config), base_url="http://127.0.0.1") as client:
        response = client.post("/api/v1/datasets/imports", files={"file": (name, body, mime)}, headers=ORIGIN)
        assert response.status_code in {400, 415, 422}
        assert response.json()["error"]["code"] == code
        assert "Traceback" not in response.text and str(config.database_path) not in response.text
        no_origin = client.post("/api/v1/datasets/imports", files={"file": ("x.xlsx", body, MIME)})
        assert no_origin.status_code == 403


def test_multipart_limits_and_truncation(config, source):
    with TestClient(create_app(config), base_url="http://127.0.0.1") as client:
        large = client.post("/api/v1/datasets/imports", content=b"x", headers={**ORIGIN, "Content-Type": "multipart/form-data; boundary=x", "Content-Length": str(MAX_UPLOAD + 65537)})
        assert large.status_code == 413
        broken = client.post("/api/v1/datasets/imports", content=b"--x\r\nContent-Disposition: form-data; name=\"file\"; filename=\"x.xlsx\"\r\nContent-Type: " + MIME.encode() + b"\r\n\r\ntruncated", headers={**ORIGIN, "Content-Type": "multipart/form-data; boundary=x"})
        assert broken.status_code == 400
        two = client.post("/api/v1/datasets/imports", files=[("file", ("a.xlsx", source.read_bytes(), MIME)), ("file", ("b.xlsx", source.read_bytes(), MIME))], headers=ORIGIN)
        assert two.status_code == 400
    assert not list(config.import_cache_dir.glob("*.xlsx"))


@pytest.mark.parametrize("name,mode", [("../evil.xlsx", 0), ("/absolute.xlsx", 0), ("C:\\evil.xlsx", 0), ("evil.xlsx", stat.S_IFLNK)])
def test_zip_traversal_and_symlink(config, tmp_path, name, mode):
    path = tmp_path / "bad.zip"
    with ZipFile(path, "w") as z:
        info = ZipInfo(name)
        if mode:
            info.external_attr = (mode | 0o777) << 16
        z.writestr(info, b"test_fixture")
    with pytest.raises(AppError, match="UNSAFE_ARCHIVE"):
        prepare_source(path, config.raw_data_dir, config.import_cache_dir, time.monotonic() + 30)


def test_zip_bomb_and_multiple_members(config, tmp_path):
    path = tmp_path / "bomb.zip"
    with ZipFile(path, "w", compression=ZIP_DEFLATED) as z:
        z.writestr("one.xlsx", b"x" * 200000)
    with pytest.raises(AppError, match="ARCHIVE_RATIO_LIMIT"):
        prepare_source(path, config.raw_data_dir, config.import_cache_dir, time.monotonic() + 30)
    with ZipFile(path, "a") as z:
        z.writestr("two.xlsx", b"test_fixture")
    with pytest.raises(AppError, match="ARCHIVE_MEMBER_LIMIT"):
        prepare_source(path, config.raw_data_dir, config.import_cache_dir, time.monotonic() + 30)


def test_missing_and_unaudited_file(config, source, tmp_path):
    for path, code in [(tmp_path / "missing.xlsx", "SOURCE_NOT_FOUND"), (source, "WORKBOOK_VERSION_REQUIRES_AUDIT")]:
        with pytest.raises(AppError, match=code):
            prepare_source(path, config.raw_data_dir, config.import_cache_dir, time.monotonic() + 30)


def test_archive_change_and_timeout_are_failures(config, source, monkeypatch):
    with importer(config, source) as service:
        original = service.executor.submit
        pending = []
        monkeypatch.setattr(service.executor, "submit", lambda *args: pending.append(args))
        response = service.submit(source)
        path = config.raw_data_dir / (sha256(source) + ".xlsx")
        path.write_bytes(b"corrupt test_fixture")
        service._run(response["batch_id"])
        assert service.batch(response["batch_id"])["error_code"] == "ARCHIVED_SOURCE_CORRUPT"
    with pytest.raises(AppError, match="IMPORT_TIMEOUT"):
        prepare_source(source, config.raw_data_dir, config.import_cache_dir, time.monotonic() - 1, frozenset({sha256(source)}))


def test_missing_database_import_does_not_create_file(tmp_path, source):
    settings = Settings(_env_file=None, database_url=f"sqlite:///{(tmp_path/'missing.db').as_posix()}", app_env="test")
    with TestClient(create_app(settings), base_url="http://127.0.0.1") as client:
        response = client.post("/api/v1/datasets/imports", files={"file": (source.name, source.read_bytes(), MIME)}, headers=ORIGIN)
        assert response.status_code == 503
    assert not settings.database_path.exists()


def test_cli_missing_source_returns_failure(config, tmp_path):
    result = subprocess.run([sys.executable, str(PROJECT_ROOT / "scripts/import_data.py"), str(tmp_path / "absent.xlsx"), "--database", str(config.database_path)], cwd=PROJECT_ROOT, capture_output=True, text=True)
    assert result.returncode == 1
    assert json.loads(result.stdout)["error"]["code"] == "SOURCE_NOT_FOUND"


@pytest.mark.parametrize("change,expected", [("header", "HEADER_MISMATCH"), ("sheet", "WORKSHEET_MISMATCH"), ("epoch", "UNSUPPORTED_DATE_EPOCH"), ("formula", "INVALID_ROWS_PRESENT")])
def test_workbook_schema_and_formula_fail_closed(config, tmp_path, change, expected):
    from openpyxl import load_workbook
    from openpyxl.utils.datetime import MAC_EPOCH
    source = workbook(tmp_path / "test_fixture.xlsx")
    book = load_workbook(source)
    if change == "header":
        book.active["A1"] = "WrongHeader"
    elif change == "sheet":
        book.active.title = "Other Sheet"
    elif change == "epoch":
        book.epoch = MAC_EPOCH
    else:
        book.active["C2"] = "=1+1"
    book.save(source)
    with importer(config, source) as service:
        result = service.submit(source, background=False)
        assert result["status"] == "FAILED" and result["error_code"] == expected


@pytest.mark.parametrize("kind", ["external", "entity", "macro"])
def test_active_ooxml_content_rejected_before_storage(config, source, tmp_path, kind):
    target = tmp_path / "unsafe.xlsx"
    with ZipFile(source) as incoming, ZipFile(target, "w") as outgoing:
        for entry in incoming.infolist():
            data = incoming.read(entry)
            if entry.filename == "xl/_rels/workbook.xml.rels":
                if kind == "external":
                    data = b'<Relationships><Relationship Id="r1" Target="https://example.invalid/" TargetMode="External"/></Relationships>'
                if kind == "entity":
                    data = b'<!DOCTYPE r [<!ENTITY x SYSTEM "file:///private">]><r>&x;</r>'
            outgoing.writestr(entry.filename, data)
        if kind == "macro":
            outgoing.writestr("xl/vbaProject.bin", b"test_fixture")
    with pytest.raises(AppError) as error:
        prepare_source(target, config.raw_data_dir, config.import_cache_dir, time.monotonic() + 30)
    assert error.value.code == {"external": "EXTERNAL_RELATIONSHIP", "entity": "CORRUPT_SOURCE", "macro": "ACTIVE_WORKBOOK_CONTENT"}[kind]
    assert not config.raw_data_dir.exists()


def test_chunked_upload_limit_without_content_length(config, monkeypatch):
    import backend.app.imports.routes as routes
    monkeypatch.setattr(routes, "MAX_UPLOAD", 1024)
    prefix = b'--x\r\nContent-Disposition: form-data; name="file"; filename="x.xlsx"\r\nContent-Type: ' + MIME.encode() + b'\r\n\r\n'
    def stream():
        yield prefix
        yield b"x" * 2048
        yield b"\r\n--x--\r\n"
    with TestClient(create_app(config), base_url="http://127.0.0.1") as client:
        response = client.post("/api/v1/datasets/imports", content=stream(), headers={**ORIGIN, "Content-Type": "multipart/form-data; boundary=x"})
        assert response.status_code == 413
    assert not list(config.import_cache_dir.glob("*.xlsx"))


def test_invalid_project_marker_blocks_import(config, source):
    with sqlite3.connect(config.database_path) as db:
        db.execute("UPDATE app_metadata SET value='another-project'")
    with importer(config, source) as service:
        with pytest.raises(AppError, match="DATABASE_MIGRATION_REQUIRED"):
            service.submit(source, background=False)
