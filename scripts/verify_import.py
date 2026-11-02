"""D2 real HTTP/CLI acceptance and independent read-only SQL reconciliation.

Uses the official local source and saved D1 references; never production constants.
Creates/migrates only the explicitly supplied development database. No model calls.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import socket
import sqlite3
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from alembic import command
from alembic.config import Config
import httpx

from backend.app.config import Settings
from backend.app.imports.source import sha256


def sql_snapshot(database: Path, dataset_id: str) -> dict:
    """Verification SQL is independent of ingestion counters and business functions."""
    with sqlite3.connect(database.as_uri() + "?mode=ro", uri=True) as db:
        params = {"d": dataset_id}
        row = db.execute("SELECT COUNT(*),MIN(source_row_num),MAX(source_row_num),SUM(ABS(line_amount_milli_gbp)),MIN(invoice_date_source),MAX(invoice_date_source) FROM transaction_rows WHERE dataset_id=:d", params).fetchone()
        result = {"row_count": row[0], "row_min": row[1], "row_max": row[2], "absolute_amount_milli_gbp": row[3], "date_min": row[4], "date_max": row[5]}
        result["classes"] = {k: 0 for k in ("INVALID", "POSITIVE", "CANCELLATION", "EXCLUDED_OTHER")}
        result["classes"].update(dict(db.execute("SELECT primary_class,COUNT(*) FROM transaction_rows WHERE dataset_id=:d GROUP BY primary_class", params)))
        result["quality"] = dict(db.execute("SELECT issue_code,COUNT(*) FROM quality_issues WHERE dataset_id=:d GROUP BY issue_code", params))
        result["per_month_rows"] = dict(db.execute("SELECT substr(invoice_date_source,1,7),COUNT(*) FROM transaction_rows WHERE dataset_id=:d GROUP BY 1", params))
        result["milli_rows"] = [list(r) for r in db.execute("SELECT source_row_num,unit_price_raw,unit_price_milli_gbp FROM transaction_rows WHERE dataset_id=:d AND unit_price_milli_gbp=1 ORDER BY source_row_num", params)]
        result["monthly"] = {}
        for month, following in (("2011-09", "2011-10"), ("2011-10", "2011-11")):
            values = db.execute("""SELECT SUM(CASE WHEN primary_class='POSITIVE' THEN line_amount_milli_gbp ELSE 0 END),
              SUM(CASE WHEN primary_class='CANCELLATION' THEN -line_amount_milli_gbp ELSE 0 END),
              COUNT(DISTINCT CASE WHEN primary_class='POSITIVE' THEN invoice_no END),
              SUM(primary_class='POSITIVE'),SUM(primary_class='CANCELLATION')
              FROM transaction_rows WHERE dataset_id=:d AND invoice_date_source>=:start AND invoice_date_source<:end""",
              {**params, "start": month + "-01 00:00:00", "end": following + "-01 00:00:00"}).fetchone()
            result["monthly"][month] = dict(zip(("positive_milligbp", "cancellation_milligbp", "positive_invoice_count", "positive_rows", "cancellation_rows"), values))
            result["monthly"][month]["net_milligbp"] = values[0] - values[1]
        result["snapshots"] = db.execute("SELECT COUNT(*) FROM dataset_snapshots").fetchone()[0]
        result["batches"] = db.execute("SELECT COUNT(*) FROM import_batches").fetchone()[0]
        result["fk_check"] = db.execute("PRAGMA foreign_key_check").fetchall()
        result["integrity"] = db.execute("PRAGMA quick_check").fetchall()
        # Row-level independent checks, including source representations and overlap.
        result["class_rule_violations"] = db.execute("""SELECT COUNT(*) FROM transaction_rows WHERE dataset_id=:d AND
            primary_class != CASE WHEN invoice_no NOT LIKE 'c%' AND quantity>0 AND unit_price_milli_gbp>0 THEN 'POSITIVE'
            WHEN invoice_no LIKE 'c%' AND quantity<0 AND unit_price_milli_gbp>0 THEN 'CANCELLATION' ELSE 'EXCLUDED_OTHER' END""", params).fetchone()[0]
        result["money_rule_violations"] = db.execute("SELECT COUNT(*) FROM transaction_rows WHERE dataset_id=:d AND line_amount_milli_gbp != quantity*unit_price_milli_gbp", params).fetchone()[0]
        result["negative_price_examples"] = [list(r) for r in db.execute("SELECT source_row_num,invoice_no,unit_price_raw,primary_class FROM transaction_rows WHERE dataset_id=:d AND unit_price_milli_gbp<0", params)]
        result["non_c_negative_example"] = list(db.execute("SELECT source_row_num,primary_class,quality_flags FROM transaction_rows WHERE dataset_id=:d AND invoice_no NOT LIKE 'c%' AND quantity<0 LIMIT 1", params).fetchone())
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    args.database, args.output = args.database.resolve(), args.output.resolve()
    args.output.mkdir(parents=True, exist_ok=True)
    report = {"started_at": datetime.now(timezone.utc).isoformat(), "scope": "D2_development_acceptance_not_academic_experiment", "checks": [], "observations": []}
    process, log = None, None

    def check(name, actual, expected):
        ok = actual == expected
        report["checks"].append({"name": name, "actual": actual, "expected": expected, "pass": ok})
        if not ok:
            raise AssertionError(name)

    try:
        manifest = json.loads((ROOT / "data/manifest.json").read_text(encoding="utf-8"))
        audit = json.loads((ROOT / "docs/evidence/d1/audit.json").read_text(encoding="utf-8"))
        reference = json.loads((ROOT / "docs/evidence/d1/audit_normalization_and_reference.json").read_text(encoding="utf-8"))
        paths = {key: ROOT / manifest["files"][key]["path"] for key in ("zip", "xlsx")}
        for kind, path in paths.items():
            check(kind + "_hash", sha256(path), manifest["files"][kind]["sha256"])
        settings = Settings(database_url=f"sqlite:///{args.database.as_posix()}", import_cache_dir=args.output / "uploads")
        cfg = Config(str(ROOT / "backend/alembic.ini"))
        cfg.attributes["settings"] = settings
        command.upgrade(cfg, "head")
        with socket.socket() as sock:
            sock.bind(("127.0.0.1", 0))
            port = sock.getsockname()[1]
        env = os.environ.copy()
        env.update(DATABASE_URL=settings.database_url, IMPORT_CACHE_DIR=str(settings.import_cache_dir), APP_PORT=str(port), PYTHONUTF8="1", PYTHONDONTWRITEBYTECODE="1")
        base = f"http://127.0.0.1:{port}"
        client = httpx.Client(base_url=base, timeout=60, trust_env=False)

        def start(label):
            nonlocal process, log
            log = (args.output / (label + ".log")).open("wb")
            argv = [sys.executable, "-m", "uvicorn", "backend.app.main:app", "--host", "127.0.0.1", "--port", str(port)]
            process = subprocess.Popen(argv, cwd=ROOT, env=env, stdout=log, stderr=log,
                                       creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0)
            report.setdefault("servers", []).append({"argv": argv, "pid": process.pid, "log": str(args.output / (label + ".log"))})
            deadline = time.monotonic() + 20
            while time.monotonic() < deadline:
                try:
                    if client.get("/healthz").status_code == 200:
                        return
                except httpx.HTTPError:
                    pass
                if process.poll() is not None:
                    break
                time.sleep(0.15)
            raise RuntimeError("Server not healthy")

        def stop():
            nonlocal process, log
            if process:
                process.terminate()
                process.wait(timeout=15)
                report["servers"][-1]["stop_exit_code"] = process.returncode
                process = None
            if log:
                log.close()
                log = None

        def upload(kind):
            with paths[kind].open("rb") as stream:
                response = client.post("/api/v1/datasets/imports", headers={"Origin": base}, files={"file": (paths[kind].name, stream, "application/zip" if kind == "zip" else "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")})
            report.setdefault("uploads", []).append({"kind": kind, "http_status": response.status_code, "body": response.json()})
            return response

        start("server-import")
        first = upload("zip")
        if first.status_code not in {200, 202}:
            raise AssertionError("initial_upload")
        batch_id, dataset_id = first.json()["batch_id"], first.json()["dataset_id"]
        report.update(batch_id=batch_id, dataset_id=dataset_id, database=str(args.database))
        deadline = time.monotonic() + 360
        while time.monotonic() < deadline:
            response = client.get(f"/api/v1/datasets/imports/{batch_id}")
            response.raise_for_status()
            payload = response.json()
            report["observations"].append({"status": payload["status"], "processed_rows": payload["processed_rows"]})
            if payload["status"] in {"READY", "FAILED"}:
                break
            quality_response = client.get(f"/api/v1/datasets/{dataset_id}/quality")
            # It may complete between the two GETs; both legal responses are recorded.
            if quality_response.status_code not in {200, 409}:
                raise AssertionError("partial_quality_guard")
            report["observations"][-1]["quality_http_status"] = quality_response.status_code
            time.sleep(0.75)
        check("terminal_status", payload["status"], "READY")
        quality = client.get(f"/api/v1/datasets/{dataset_id}/quality").json()
        report["quality"] = quality
        before = sql_snapshot(args.database, dataset_id)
        report["sql"] = before
        check("row_count", before["row_count"], audit["rows"])
        check("source_row_range", [before["row_min"], before["row_max"]], manifest["workbook"]["data_excel_row_range"])
        check("class_counts", before["classes"], audit["primary_class_counts"])
        check("quality_flags", before["quality"], audit["quality_flags"])
        check("quality_api_matches_sql", quality["quality_flags"], before["quality"])
        check("date_min", before["date_min"], audit["date_min"] + ".000")
        check("date_max", before["date_max"], audit["date_max"] + ".000")
        check("per_month_rows", before["per_month_rows"], audit["per_month_rows"])
        check("duplicates_retained", quality["duplicate_group_rows"], audit["rows_in_duplicate_groups"])
        check("duplicate_candidates", quality["duplicate_candidates_after_first"], audit["duplicate_candidate_rows_after_first"])
        check("absolute_amount", before["absolute_amount_milli_gbp"], audit["int64_check"]["sum_absolute_line_amount_milli_gbp"])
        expected_milli = [[r["excel_row"], "1E-3", 1] for r in reference["normalization"]["normalized_prices_requiring_more_than_2_decimal_places"]]
        check("four_raw_thousandths", before["milli_rows"], expected_milli)
        for month, values in before["monthly"].items():
            for field, value in values.items():
                check(month + "_" + field, value, reference["monthly_reference"][month][field])
        for name in ("class_rule_violations", "money_rule_violations"):
            check(name, before[name], 0)
        check("foreign_keys", before["fk_check"], [])
        check("sqlite_integrity", before["integrity"], [("ok",)])
        for kind in ("zip", "xlsx"):
            response = upload(kind)
            check(kind + "_repeat_http", response.status_code, 200)
            check(kind + "_same_batch", response.json()["batch_id"], batch_id)
        check("repeat_rows_and_amounts", sql_snapshot(args.database, dataset_id), before)
        argv = [sys.executable, "scripts/manage.py", "import-data", str(paths["xlsx"]), "--database", str(args.database), "--output", str(args.output / "cli-repeat.json")]
        cli = subprocess.run(argv, cwd=ROOT, env=env, capture_output=True)
        (args.output / "cli-repeat.stdout.txt").write_bytes(cli.stdout)
        (args.output / "cli-repeat.stderr.txt").write_bytes(cli.stderr)
        report["cli"] = {"argv": argv, "exit_code": cli.returncode}
        check("cli_repeat_exit", cli.returncode, 0)
        check("cli_same_batch", json.loads((args.output / "cli-repeat.json").read_text(encoding="utf-8"))["batch_id"], batch_id)
        stop()
        db_hash = sha256(args.database)
        start("server-restart")
        check("restart_quality", client.get(f"/api/v1/datasets/{dataset_id}/quality").json(), quality)
        check("restart_batch_ready", client.get(f"/api/v1/datasets/imports/{batch_id}").json()["status"], "READY")
        check("restart_and_get_no_writes", sha256(args.database), db_hash)
        stop()
        report["database_sha256"] = sha256(args.database)
        report["database_bytes"] = args.database.stat().st_size
        report["status"] = "PASS"
    except Exception as exc:
        report["status"], report["failure"] = "FAIL", {"type": type(exc).__name__, "message": str(exc)}
    finally:
        if process:
            process.terminate()
            process.wait(timeout=15)
        if log:
            log.close()
        report["finished_at"] = datetime.now(timezone.utc).isoformat()
        (args.output / "verification.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"status": report["status"], "checks": len(report["checks"]), "evidence": str(args.output / "verification.json"), "failure": report.get("failure")}, ensure_ascii=True))
    return 0 if report["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
