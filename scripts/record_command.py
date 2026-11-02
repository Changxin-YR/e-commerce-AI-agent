"""Run a local command and preserve its actual output and exit code as evidence.

Do not pass secrets on the command line. This utility does not read .env files.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import subprocess
import sys
import time


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--label", required=True)
    parser.add_argument("--cwd", type=Path, default=Path.cwd())
    parser.add_argument("command", nargs=argparse.REMAINDER)
    args = parser.parse_args()
    command = args.command[1:] if args.command[:1] == ["--"] else args.command
    if not command:
        parser.error("a command is required after --")
    args.output.mkdir(parents=True, exist_ok=True)
    started = datetime.now(timezone.utc)
    stem = started.strftime("%Y%m%dT%H%M%S%fZ") + "_" + args.label
    if Path(stem).name != stem or any(c in args.label for c in '/\\:'):
        parser.error("label must be a filename component")
    env = os.environ.copy()
    env["PYTHONUTF8"] = "1"
    env["PYTHONIOENCODING"] = "utf-8"
    before = time.monotonic()
    try:
        result = subprocess.run(command, cwd=args.cwd, env=env, capture_output=True)
        code, stdout, stderr = result.returncode, result.stdout, result.stderr
    except OSError as exc:
        code, stdout, stderr = 127, b"", str(exc).encode("utf-8")
    record = {
        "label": args.label,
        "started_at": started.isoformat(),
        "finished_at": datetime.now(timezone.utc).isoformat(),
        "duration_seconds": round(time.monotonic() - before, 3),
        "cwd": str(args.cwd.resolve()),
        "argv": command,
        "exit_code": code,
        "stdout_file": stem + ".stdout.txt",
        "stderr_file": stem + ".stderr.txt",
    }
    (args.output / record["stdout_file"]).write_bytes(stdout)
    (args.output / record["stderr_file"]).write_bytes(stderr)
    (args.output / (stem + ".json")).write_text(
        json.dumps(record, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    sys.stdout.buffer.write(stdout)
    sys.stderr.buffer.write(stderr)
    print(f"\nEVIDENCE={args.output / (stem + '.json')} EXIT_CODE={code}", flush=True)
    return code


if __name__ == "__main__":
    raise SystemExit(main())
