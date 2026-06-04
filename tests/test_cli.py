"""CLI-level tests for the nextraci command."""

from importlib.metadata import version as pkg_version

from typer.testing import CliRunner

from nextraci.cli import app

runner = CliRunner()


def test_version_flag_prints_version_and_exits_zero():
    result = runner.invoke(app, ["--version"])
    assert result.exit_code == 0
    assert result.stdout.strip() == f"nextraci {pkg_version('nextraci')}"


def test_short_version_flag():
    result = runner.invoke(app, ["-V"])
    assert result.exit_code == 0
    assert result.stdout.startswith("nextraci ")
