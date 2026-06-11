"""Tests for `agenraci compile` — the real github target and the stubs."""

from pathlib import Path

from typer.testing import CliRunner

from agenraci.cli import app

runner = CliRunner()

GOVERNANCE = "governance/charter.yaml"


def test_compile_github_emits_codeowners_and_branch_protection():
    """The github target is real: CODEOWNERS + a checklist per gated action."""
    result = runner.invoke(app, ["compile", "--target", "github", GOVERNANCE])
    assert result.exit_code == 0
    out = result.stdout
    assert "CODEOWNERS" in out
    assert "Branch protection" in out
    # The governance charter gates A5_merge_to_main and A7_publish_release.
    assert "A5_merge_to_main" in out
    assert "A7_publish_release" in out
    # on_timeout=block must translate to "do not auto-merge".
    assert "Do NOT enable auto-merge" in out
    # github is real, so it must NOT be labelled a stub.
    assert "STUB" not in out


def test_compile_github_flags_non_human_approver():
    """A gate whose approver role has no human member is surfaced, not hidden."""
    result = runner.invoke(app, ["compile", "--target", "github", GOVERNANCE])
    # reviewer (the A5 approver) is an agent in the governance charter.
    assert "no human members" in result.stdout


def test_compile_stub_targets_are_labelled():
    for target in ("humanlayer", "langgraph"):
        result = runner.invoke(app, ["compile", "--target", target, GOVERNANCE])
        assert result.exit_code == 0
        assert "(STUB)" in result.stdout


def test_compile_unknown_target_exits_2(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    runner.invoke(app, ["init", "c.yaml"])
    result = runner.invoke(app, ["compile", "--target", "gitlab", "c.yaml"])
    assert result.exit_code == 2


def test_compile_refuses_invalid_charter(tmp_path, monkeypatch):
    """Never emit config from a charter that fails the checker."""
    monkeypatch.chdir(tmp_path)
    (tmp_path / "bad.yaml").write_text(
        "project: broken\n"
        "roles: [a, b]\n"
        "actions:\n"
        "  x: { responsible: a, accountable: [a, b] }\n",  # R1 fails
        encoding="utf-8",
    )
    result = runner.invoke(app, ["compile", "--target", "github", "bad.yaml"])
    assert result.exit_code == 1
    assert "refusing to compile" in result.stdout


def test_compile_github_no_gates_says_so(tmp_path, monkeypatch):
    """A charter with no gates produces a clear note, not an empty checklist."""
    monkeypatch.chdir(tmp_path)
    (tmp_path / "nogate.yaml").write_text(
        "project: nogate\n"
        "roles: [a]\n"
        "actions:\n"
        "  x: { responsible: a, accountable: a }\n",
        encoding="utf-8",
    )
    result = runner.invoke(app, ["compile", "--target", "github", "nogate.yaml"])
    assert result.exit_code == 0
    assert "No action declares a `gate:`" in result.stdout
