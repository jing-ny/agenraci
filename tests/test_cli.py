"""CLI-level tests for the agenraci command."""

from importlib.metadata import version as pkg_version
from pathlib import Path

from typer.testing import CliRunner

from agenraci.cli import app

runner = CliRunner()


def test_version_flag_prints_version_and_exits_zero():
    result = runner.invoke(app, ["--version"])
    assert result.exit_code == 0
    assert result.stdout.strip() == f"agenraci {pkg_version('agenraci')}"


def test_short_version_flag():
    result = runner.invoke(app, ["-V"])
    assert result.exit_code == 0
    assert result.stdout.startswith("agenraci ")


def test_init_writes_a_charter_that_validates(tmp_path, monkeypatch):
    """`init` writes a starter charter, and that charter passes `validate`."""
    monkeypatch.chdir(tmp_path)

    init = runner.invoke(app, ["init"])
    assert init.exit_code == 0
    assert (tmp_path / "charter.yaml").exists()

    check = runner.invoke(app, ["validate", "charter.yaml"])
    assert check.exit_code == 0
    assert "PASS" in check.stdout


def test_init_custom_path_creates_parent_dirs(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    result = runner.invoke(app, ["init", "team/constitution.yaml"])
    assert result.exit_code == 0
    assert (tmp_path / "team" / "constitution.yaml").exists()


def test_init_refuses_to_overwrite_without_force(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    target = tmp_path / "charter.yaml"
    target.write_text("project: keep-me\n", encoding="utf-8")

    result = runner.invoke(app, ["init"])
    assert result.exit_code == 1
    assert target.read_text(encoding="utf-8") == "project: keep-me\n"

    forced = runner.invoke(app, ["init", "--force"])
    assert forced.exit_code == 0
    assert "project: keep-me" not in target.read_text(encoding="utf-8")
