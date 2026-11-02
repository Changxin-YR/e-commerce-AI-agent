"""Import the audited UCI ZIP/XLSX into an explicitly migrated local database."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backend.app.config import Settings
from backend.app.errors import AppError
from backend.app.imports.service import ImportService


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("file", type=Path)
    parser.add_argument("--database", type=Path, help="Existing migrated SQLite database")
    parser.add_argument("--output", type=Path, help="Save the same sanitized JSON returned on stdout")
    args = parser.parse_args()
    overrides = {"database_url": f"sqlite:///{args.database.resolve().as_posix()}"} if args.database else {}
    service = ImportService(Settings(**overrides))
    try:
        service.start()
        result = service.submit(args.file, background=False)
        code = 0 if result["status"] == "READY" else 1
    except AppError as exc:
        result, code = {"status": "FAILED", "error": {"code": exc.code, "message": exc.message}}, 1
    except Exception:
        result, code = {"status": "FAILED", "error": {"code": "IMPORT_FAILED", "message": "Import failed; inspect local configuration and source constraints."}}, 1
    finally:
        service.close()
    payload = json.dumps(result, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(payload, encoding="utf-8")
    print(payload, end="")
    return code


if __name__ == "__main__":
    raise SystemExit(main())
