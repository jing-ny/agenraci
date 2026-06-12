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


# --- claude target (real: .claude/agents/ + CLAUDE.md snippet) ---------------


def test_compile_claude_emits_one_file_per_agent_member():
    """One agent file per `type: agent` member; humans get no file; not a stub."""
    result = runner.invoke(app, ["compile", "--target", "claude", GOVERNANCE])
    assert result.exit_code == 0
    out = result.stdout
    for agent in ("writer", "coder", "reviewer", "qa"):
        assert f"--- FILE: .claude/agents/{agent}.md ---" in out
    # maintainer is human — escalation contact, not an agent file.
    assert "--- FILE: .claude/agents/maintainer.md ---" not in out
    assert "**maintainer** (human" in out
    assert "--- FILE: CLAUDE.governance.md ---" in out
    assert "STUB" not in out


def test_compile_claude_surfaces_denials_and_gates():
    """Deny rules become explicit never-do guidance; gates keep author != approver."""
    result = runner.invoke(app, ["compile", "--target", "claude", GOVERNANCE])
    out = result.stdout
    # reviewer's denials are the point of the role.
    assert "**Never** exercise `edit_code`" in out
    # The merge gate: reviewer approves, coder must not self-approve.
    assert "required approver: **reviewer**" in out
    assert "Don't approve your own work" in out
    # Suggestion routes survive: qa can't fix, so defects route to coder.
    assert "**defect_report**" in out


def test_compile_claude_maps_member_models_to_frontmatter_tokens():
    """Member model ids map onto Claude Code's model tokens when unambiguous."""
    result = runner.invoke(app, ["compile", "--target", "claude", GOVERNANCE])
    assert "model: opus" in result.stdout     # coder / reviewer
    assert "model: sonnet" in result.stdout   # writer / qa


def test_compile_claude_out_dir_writes_files(tmp_path):
    """--out-dir splits the FILE markers and writes real files."""
    result = runner.invoke(app, [
        "compile", "--target", "claude", GOVERNANCE, "--out-dir", str(tmp_path),
    ])
    assert result.exit_code == 0
    for agent in ("writer", "coder", "reviewer", "qa"):
        f = tmp_path / ".claude" / "agents" / f"{agent}.md"
        assert f.exists(), f
        assert f.read_text(encoding="utf-8").startswith("---\n")  # frontmatter
    assert (tmp_path / "CLAUDE.governance.md").exists()


def test_compile_out_dir_rejects_single_document_target(tmp_path):
    """--out-dir only makes sense for multi-file targets."""
    result = runner.invoke(app, [
        "compile", "--target", "github", GOVERNANCE, "--out-dir", str(tmp_path),
    ])
    assert result.exit_code == 2
    assert "single document" in result.stdout


def test_compile_claude_all_human_charter_says_so(tmp_path, monkeypatch):
    """No agent members -> a clear note, not an error or empty output."""
    monkeypatch.chdir(tmp_path)
    (tmp_path / "humans.yaml").write_text(
        "project: humans-only\n"
        "roles: [lead]\n"
        "members:\n"
        "  - { name: pat, type: human, role: lead }\n"
        "actions:\n"
        "  decide: { responsible: lead, accountable: lead }\n",
        encoding="utf-8",
    )
    result = runner.invoke(app, ["compile", "--target", "claude", "humans.yaml"])
    assert result.exit_code == 0
    assert "No agent members" in result.stdout
