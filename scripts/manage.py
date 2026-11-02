"""Windows-first D0 commands. All subprocess failures keep their real exit code."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
from importlib import metadata
import json
import os
from pathlib import Path
import platform
import shutil
import socket
import sqlite3
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
VENV_PYTHON = ROOT / ".venv" / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
PACKAGES = ("fastapi", "pydantic", "pydantic-settings", "SQLAlchemy", "alembic", "uvicorn", "httpx", "pytest", "langgraph", "langgraph-checkpoint", "langgraph-checkpoint-sqlite")
FUTURE_COMMANDS = ("download-data", "verify-data", "tools", "agent", "evaluate")


def run(command: list[str], cwd: Path = ROOT) -> int:
    print("RUN " + subprocess.list2cmdline(command), flush=True)
    try:
        return subprocess.run(command, cwd=cwd, env=os.environ.copy()).returncode
    except OSError as exc:
        print(f"COMMAND_UNAVAILABLE: {type(exc).__name__}", file=sys.stderr)
        return 127


def npm(*args: str) -> list[str]:
    return [shutil.which("npm.cmd" if os.name == "nt" else "npm") or "npm", *args]


def version(command: list[str]) -> dict:
    try:
        result = subprocess.run(command, cwd=ROOT, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=15)
        return {"exit_code": result.returncode, "version": result.stdout.strip() if result.returncode == 0 else None}
    except (OSError, subprocess.TimeoutExpired) as exc:
        return {"exit_code": 127, "error": type(exc).__name__}


def doctor() -> int:
    from backend.app.config import Settings

    settings = Settings()
    packages = {}
    for package in PACKAGES:
        try:
            packages[package] = metadata.version(package)
        except metadata.PackageNotFoundError:
            packages[package] = None
    ports = {}
    for port in (settings.app_port, settings.frontend_port):
        with socket.socket() as sock:
            sock.settimeout(0.3)
            ports[str(port)] = "IN_USE" if sock.connect_ex(("127.0.0.1", port)) == 0 else "AVAILABLE"
    node, npm_version, git = version(["node", "--version"]), version(npm("--version")), version(["git", "--version"])
    git_head = version(["git", "rev-parse", "HEAD"])
    node_text = node.get("version") or "v0.0.0"
    try:
        node_parts = tuple(int(part) for part in node_text.lstrip("v").split(".")[:3])
        node_supported = node_parts >= (22, 12, 0)
    except ValueError:
        node_supported = False
    ready = sys.version_info >= (3, 11) and node_supported and all(packages.values()) and all(item["exit_code"] == 0 for item in (node, npm_version, git))
    print(json.dumps({
        "checked_at": datetime.now(timezone.utc).isoformat(),
        "status": "PASS" if ready else "FAIL",
        "scope": "environment_only_not_business_acceptance",
        "os": platform.platform(), "python": platform.python_version(),
        "python_executable": sys.executable, "sqlite": sqlite3.sqlite_version,
        "node": node, "npm": npm_version, "git": git,
        "git_sha": git_head["version"] if git_head["exit_code"] == 0 else None,
        "git_head_status": "COMMITTED" if git_head["exit_code"] == 0 else "UNBORN_OR_UNAVAILABLE",
        "dependencies": packages, "ports": ports,
        "database_exists": settings.database_path.is_file(),
        "paid_model_calls": "DISABLED" if not settings.allow_paid_model_calls else "CONFIGURATION_REQUIRES_AUTHORIZED_SMOKE",
        "checkpoint_journal": checkpoint_journal(settings),
    }, ensure_ascii=False, indent=2))
    return 0 if ready else 1


def checkpoint_journal(settings):
    if not settings.checkpoint_path.is_file():
        return "NOT_CREATED"
    with sqlite3.connect(settings.checkpoint_path.as_uri()+"?mode=ro",uri=True) as connection:
        return connection.execute("PRAGMA journal_mode").fetchone()[0]


def main() -> int:
    # Let documented `python scripts/manage.py ...` use the project's locked environment.
    os.environ.setdefault("PYTHONDONTWRITEBYTECODE", "1")
    os.environ.setdefault("PYTHONUTF8", "1")
    if VENV_PYTHON.is_file() and Path(sys.executable).resolve() != VENV_PYTHON.resolve():
        return subprocess.run([str(VENV_PYTHON), "-X", "utf8", str(Path(__file__).resolve()), *sys.argv[1:]], cwd=ROOT).returncode
    sys.path.insert(0, str(ROOT))
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("doctor", help="Inspect actual versions and local ports without printing secrets")
    backend = sub.add_parser("backend", help="Start local FastAPI; use Ctrl+C to stop")
    backend.add_argument("--reload", action="store_true")
    sub.add_parser("frontend", help="Start local Vue/Vite; use Ctrl+C to stop")
    sub.add_parser("migrate", help="Explicitly upgrade the local SQLite database to head")
    sub.add_parser("build", help="Type-check and build the frontend")
    importer = sub.add_parser("import-data", help="Import an audited source; migrate the database first")
    importer.add_argument("file", type=Path)
    importer.add_argument("--database", type=Path)
    importer.add_argument("--output", type=Path)
    metrics = sub.add_parser("verify-metrics", help="Real D3 HTTP/SQL acceptance; requires an existing imported database")
    metrics.add_argument("--database", type=Path, required=True)
    metrics.add_argument("--output", type=Path, required=True)
    metrics.add_argument("--reference", type=Path)
    metrics.add_argument("--browser", action="store_true")
    test = sub.add_parser("test", help="Run tests and propagate the first failing exit code")
    test.add_argument("--scope", choices=("smoke", "backend", "frontend", "e2e", "all"), default="smoke")
    for name in FUTURE_COMMANDS:
        future = sub.add_parser(name, help="NOT_IMPLEMENTED: reserved for a later stage")
        future.add_argument("arguments", nargs=argparse.REMAINDER)
    args = parser.parse_args()
    if args.command in FUTURE_COMMANDS:
        print(f"NOT_IMPLEMENTED: {args.command} is outside D0", file=sys.stderr)
        return 2
    try:
        # Only local process configuration; never print .env or provider values.
        from dotenv import dotenv_values
        values = dotenv_values(ROOT / ".env")
        for key in ("D0_CACHE_DIR", "APP_PORT", "FRONTEND_PORT"):
            if values.get(key) is not None:
                os.environ.setdefault(key, str(values[key]))
        cache = Path(os.environ["D0_CACHE_DIR"]).resolve() if os.environ.get("D0_CACHE_DIR") else None
        if args.command == "doctor":
            return doctor()
        if args.command == "verify-metrics":
            command = [sys.executable, str(ROOT / "scripts/verify_metrics.py"), "--database", str(args.database), "--output", str(args.output)]
            if args.reference:
                command.extend(["--reference", str(args.reference)])
            if args.browser:
                command.append("--browser")
            return run(command)
        if args.command == "import-data":
            command = [sys.executable, str(ROOT / "scripts/import_data.py"), str(args.file)]
            for name in ("database", "output"):
                if getattr(args, name):
                    command.extend(["--" + name, str(getattr(args, name))])
            return run(command)
        if args.command == "backend":
            from backend.app.config import Settings
            settings = Settings()
            command = [sys.executable, "-m", "uvicorn", "backend.app.main:app", "--host", settings.app_host, "--port", str(settings.app_port)]
            if args.reload:
                command.append("--reload")
            return run(command)
        if args.command == "migrate":
            return run([sys.executable, "-m", "alembic", "-c", str(ROOT / "backend/alembic.ini"), "upgrade", "head"])
        if args.command == "frontend":
            return run(npm("run", "dev"), ROOT / "frontend")
        if args.command == "build":
            return run(npm("run", "build"), ROOT / "frontend")
        if args.command == "test":
            commands = []
            if args.scope in {"smoke", "backend", "all"}:
                command = [sys.executable, "-m", "pytest", "tests", "-q", "-p", "no:cacheprovider"]
                if cache:
                    # Unique directory preserves previous failures and avoids deleting unrelated files.
                    (cache / "pytest").mkdir(parents=True, exist_ok=True)
                    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%f")
                    command.extend(["--basetemp", str(cache / "pytest" / stamp)])
                commands.append((command, ROOT))
            if args.scope in {"smoke", "frontend", "all"}:
                commands.append((npm("run", "test"), ROOT / "frontend"))
            if args.scope in {"smoke", "all"}:
                commands.append((npm("run", "build"), ROOT / "frontend"))
            if args.scope in {"e2e", "all"}:
                from backend.app.config import Settings
                os.environ.setdefault("E2E_SOURCE_DATABASE", str(Settings().database_path))
                commands.append((npm("run", "test:e2e"), ROOT / "frontend"))
            for command, cwd in commands:
                code = run(command, cwd)
                if code:
                    return code
            return 0
    except ImportError:
        print("DEPENDENCIES_MISSING: install requirements.lock into .venv first", file=sys.stderr)
        return 1
    return 2


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        print("Stopped by user.")
        raise SystemExit(130)
