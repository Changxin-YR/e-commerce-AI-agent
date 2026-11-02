"""Validate containers and preserve original bytes; never extract arbitrary paths."""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
from pathlib import Path, PurePosixPath
import shutil
import stat
import time
from uuid import uuid4
from zipfile import BadZipFile, ZipFile

from defusedxml import ElementTree as ET
from defusedxml.common import DefusedXmlException

from backend.app.errors import AppError
from backend.app.imports.locks import WriterLease

OFFICIAL_SHA = "43465a06f2ccf7c8b5bd2892bc7defb52f97487934fe93b16ae4c3936424676d"
SOURCE_URL = "https://archive.ics.uci.edu/dataset/352/online+retail"
MAX_UPLOAD = 50 * 1024 * 1024
MAX_XML = 256 * 1024 * 1024
NS = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
HEADERS = ("InvoiceNo", "StockCode", "Description", "Quantity", "InvoiceDate", "UnitPrice", "CustomerID", "Country")


def fail(code: str, status: int = 422):
    raise AppError(code, "Source rejected; see the documented import constraints.", status)


def sha256(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def check_time(deadline: float) -> None:
    if time.monotonic() > deadline:
        fail("IMPORT_TIMEOUT")


def safe_name(name: str) -> None:
    if not name or "\\" in name or ":" in name or "\x00" in name:
        fail("UNSAFE_ARCHIVE_PATH")
    p = PurePosixPath(name)
    if p.is_absolute() or any(part in {"..", "."} for part in name.split("/")):
        fail("UNSAFE_ARCHIVE_PATH")


def inspect_zip(archive: ZipFile, *, workbook: bool) -> None:
    entries = archive.infolist()
    if not entries or len(entries) > (256 if workbook else 1):
        fail("ARCHIVE_MEMBER_LIMIT")
    names: set[str] = set()
    total = 0
    for entry in entries:
        safe_name(entry.filename)
        kind = stat.S_IFMT(entry.external_attr >> 16)
        if entry.is_dir() or kind not in (0, stat.S_IFREG):
            fail("UNSAFE_ARCHIVE_MEMBER")
        if entry.filename.casefold() in names or entry.flag_bits & 1:
            fail("UNSAFE_ARCHIVE_MEMBER")
        names.add(entry.filename.casefold())
        total += entry.file_size
        if entry.file_size > MAX_XML or total > (MAX_XML if workbook else MAX_UPLOAD):
            fail("ARCHIVE_SIZE_LIMIT", 413)
        if entry.file_size > max(entry.compress_size, 1) * 200:
            fail("ARCHIVE_RATIO_LIMIT", 413)
        if entry.compress_type not in {0, 8}:
            fail("UNSUPPORTED_COMPRESSION")
        if workbook and any(x in entry.filename.lower() for x in ("vbaproject", "externallinks", "embeddings")):
            fail("ACTIVE_WORKBOOK_CONTENT")
    if workbook:
        required = {"[content_types].xml", "xl/workbook.xml", "xl/_rels/workbook.xml.rels", "xl/worksheets/sheet1.xml"}
        if not required.issubset(names):
            fail("INVALID_WORKBOOK_STRUCTURE")
        # Validate relationships and reject remote targets even in unused parts.
        for entry in entries:
            if entry.filename.endswith(".rels"):
                if entry.file_size > 1024 * 1024:
                    fail("ARCHIVE_SIZE_LIMIT", 413)
                root = ET.fromstring(archive.read(entry))
                for rel in root:
                    target = rel.get("Target", "")
                    if rel.get("TargetMode") == "External" or ":" in target or "\\" in target:
                        fail("EXTERNAL_RELATIONSHIP")
                    safe_name(target.lstrip("/"))
    elif PurePosixPath(entries[0].filename).suffix.lower() != ".xlsx":
        fail("EXPECTED_SINGLE_XLSX")


@dataclass(frozen=True)
class Source:
    workbook_path: Path
    workbook_sha256: str
    submitted_file_sha256: str
    submitted_bytes: int
    container_kind: str


def prepare_source(path: Path, raw_dir: Path, cache_dir: Path, deadline: float,
                   allowed_hashes: frozenset[str] = frozenset({OFFICIAL_SHA})) -> Source:
    """The allowlist is injectable only by tests, never through HTTP or CLI input."""
    if not path.is_file():
        fail("SOURCE_NOT_FOUND", 400)
    suffix = path.suffix.lower()
    if suffix not in {".zip", ".xlsx"}:
        fail("UNSUPPORTED_FILE_TYPE", 400)
    if path.stat().st_size > MAX_UPLOAD:
        fail("UPLOAD_TOO_LARGE", 413)
    cache_dir.mkdir(parents=True, exist_ok=True)
    temporary = cache_dir / (uuid4().hex + ".xlsx")
    submitted = sha256(path)
    try:
        if suffix == ".zip":
            with ZipFile(path) as archive:
                inspect_zip(archive, workbook=False)
                with archive.open(archive.infolist()[0]) as src, temporary.open("xb") as dst:
                    copied = 0
                    while chunk := src.read(1024 * 1024):
                        copied += len(chunk)
                        check_time(deadline)
                        if copied > MAX_UPLOAD:
                            fail("ARCHIVE_SIZE_LIMIT", 413)
                        dst.write(chunk)
        else:
            shutil.copyfile(path, temporary)
        with ZipFile(temporary) as workbook:
            inspect_zip(workbook, workbook=True)
        workbook_hash = sha256(temporary)
        if workbook_hash not in allowed_hashes:
            fail("WORKBOOK_VERSION_REQUIRES_AUDIT")
        check_time(deadline)
        raw_dir.mkdir(parents=True, exist_ok=True)
        archival_lock = WriterLease(raw_dir / ".archive.lock")
        while not archival_lock.acquire():
            check_time(deadline)
            time.sleep(0.05)
        try:
            # All archive destinations are generated, never derived from uploaded names.
            for source, digest, extension in ((temporary, workbook_hash, ".xlsx"), (path, submitted, suffix)):
                destination = raw_dir / (digest + extension)
                if destination.is_symlink():
                    fail("UNSAFE_ARCHIVE_PATH")
                if destination.exists():
                    if sha256(destination) != digest:
                        fail("ARCHIVED_SOURCE_CORRUPT")
                else:
                    try:
                        with destination.open("xb") as dst, source.open("rb") as src:
                            shutil.copyfileobj(src, dst, 1024 * 1024)
                    except FileExistsError:
                        if sha256(destination) != digest:
                            fail("ARCHIVED_SOURCE_CORRUPT")
        finally:
            archival_lock.close()
        return Source(raw_dir / (workbook_hash + ".xlsx"), workbook_hash, submitted, path.stat().st_size, suffix[1:])
    except AppError:
        raise
    except (BadZipFile, OSError, ValueError, ET.ParseError, DefusedXmlException):
        fail("CORRUPT_SOURCE")
    finally:
        temporary.unlink(missing_ok=True)
