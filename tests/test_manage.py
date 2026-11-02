"""Management command contracts; all subprocesses and sockets are test fixtures."""

import json
from pathlib import Path
import subprocess
import sys
import pytest

from scripts import manage


@pytest.fixture
def cli(monkeypatch):
    # Execute in-process without relaunching a different Python or reading .env.
    monkeypatch.setattr(manage, "VENV_PYTHON", Path(sys.executable).resolve())
    monkeypatch.setattr("dotenv.dotenv_values", lambda _path: {})
    monkeypatch.delenv("D0_CACHE_DIR", raising=False)

    def invoke(*arguments: str) -> int:
        monkeypatch.setattr(sys, "argv", ["scripts/manage.py", *arguments])
        return manage.main()

    return invoke


@pytest.mark.parametrize("name", manage.FUTURE_COMMANDS)
def test_future_commands_fail_explicitly_without_running_processes(name, cli, monkeypatch, capsys):
    def forbidden(*_args, **_kwargs):
        pytest.fail("A future command must not launch a process")

    monkeypatch.setattr(manage.subprocess, "run", forbidden)
    assert cli(name) == 2
    output = capsys.readouterr()
    assert f"NOT_IMPLEMENTED: {name}" in output.err
    assert "PASS" not in output.out


@pytest.mark.parametrize("exit_code", [0, 7, -9])
def test_run_preserves_child_exit_code(exit_code, monkeypatch):
    called = []

    def child(command, **kwargs):
        called.append((command, kwargs))
        return subprocess.CompletedProcess(command, exit_code)

    monkeypatch.setattr(manage.subprocess, "run", child)
    assert manage.run(["test_fixture_command"]) == exit_code
    assert called[0][0] == ["test_fixture_command"]
    assert called[0][1]["cwd"] == manage.ROOT


def test_missing_child_command_reports_127_without_exception_contents(monkeypatch, capsys):
    def missing(*_args, **_kwargs):
        raise FileNotFoundError("test_fixture_secret C:/private/path")

    monkeypatch.setattr(manage.subprocess, "run", missing)
    assert manage.run(["test_fixture_command"]) == 127
    output = capsys.readouterr()
    assert "COMMAND_UNAVAILABLE: FileNotFoundError" in output.err
    assert "test_fixture_secret" not in output.err
    assert "C:/private/path" not in output.err


@pytest.mark.parametrize("fail_index,exit_code", [(0, 5), (1, 17), (2, 23)])
def test_smoke_stops_at_first_failure(cli, monkeypatch, fail_index, exit_code):
    calls = []

    def child(command, cwd):
        index = len(calls)
        calls.append((command, cwd))
        return exit_code if index == fail_index else 0

    monkeypatch.setattr(manage, "run", child)
    monkeypatch.setattr(manage, "npm", lambda *args: ["test_fixture_npm", *args])
    assert cli("test", "--scope", "smoke") == exit_code
    assert len(calls) == fail_index + 1
    assert "pytest" in calls[0][0]
    if fail_index >= 1:
        assert calls[1][0] == ["test_fixture_npm", "run", "test"]
    if fail_index >= 2:
        assert calls[2][0] == ["test_fixture_npm", "run", "build"]


def test_successful_smoke_runs_python_frontend_tests_and_build(cli, monkeypatch):
    calls = []

    def child(command, cwd):
        calls.append((command, cwd))
        return 0

    monkeypatch.setattr(manage, "run", child)
    monkeypatch.setattr(manage, "npm", lambda *args: ["test_fixture_npm", *args])
    assert cli("test", "--scope", "smoke") == 0
    assert len(calls) == 3
    assert "pytest" in calls[0][0]
    assert calls[1][0][-2:] == ["run", "test"]
    assert calls[2][0][-2:] == ["run", "build"]


@pytest.mark.parametrize("missing_dependency", [False, True])
def test_doctor_checks_dependencies_without_printing_model_secrets(
    monkeypatch, capsys, tmp_path, missing_dependency
):
    secret = "test_fixture_only_not_a_real_model_key"
    monkeypatch.setenv("MODEL_API_KEY", secret)
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{(tmp_path / 'missing.sqlite3').as_posix()}")
    monkeypatch.setenv("APP_PORT", "18000")
    monkeypatch.setenv("FRONTEND_PORT", "15173")

    class FixtureSocket:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def settimeout(self, _seconds):
            pass

        def connect_ex(self, address):
            assert address in {("127.0.0.1", 18000), ("127.0.0.1", 15173)}
            return 1

    def fixture_version(command):
        if command[0] == "node":
            return {"exit_code": 0, "version": "v24.22.0"}
        if command[-2:] == ["rev-parse", "HEAD"]:
            return {"exit_code": 128, "version": None}
        return {"exit_code": 0, "version": "test_fixture_version"}

    def fixture_package_version(name):
        if missing_dependency and name == "fastapi":
            raise manage.metadata.PackageNotFoundError(name)
        return "0.0.test_fixture"

    monkeypatch.setattr(manage.socket, "socket", FixtureSocket)
    monkeypatch.setattr(manage, "version", fixture_version)
    monkeypatch.setattr(manage.metadata, "version", fixture_package_version)
    assert manage.doctor() == (1 if missing_dependency else 0)
    output = capsys.readouterr()
    assert secret not in output.out + output.err
    assert "MODEL_API_KEY" not in output.out + output.err
    payload = json.loads(output.out)
    assert payload["status"] == ("FAIL" if missing_dependency else "PASS")
    assert payload["git_sha"] is None
    assert payload["database_exists"] is False
    assert payload["paid_model_calls"] == "NOT_IMPLEMENTED_IN_D0"
    assert payload["ports"] == {"18000": "AVAILABLE", "15173": "AVAILABLE"}
