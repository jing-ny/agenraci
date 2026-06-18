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
    """--out-dir only makes sense for multi-file targets (stubs emit one doc)."""
    result = runner.invoke(app, [
        "compile", "--target", "humanlayer", GOVERNANCE, "--out-dir", str(tmp_path),
    ])
    assert result.exit_code == 2
    assert "single document" in result.stdout


def test_compile_github_emits_three_applyable_files(tmp_path):
    """The github target is multi-file: a real CODEOWNERS, a ruleset, setup notes."""
    import json

    result = runner.invoke(app, [
        "compile", "--target", "github", GOVERNANCE, "--out-dir", str(tmp_path),
    ])
    assert result.exit_code == 0
    codeowners = tmp_path / "CODEOWNERS"
    ruleset = tmp_path / "github-ruleset.json"
    setup = tmp_path / "github-setup.md"
    assert codeowners.exists() and ruleset.exists() and setup.exists()

    # CODEOWNERS is applyable: an uncommented owner line, not just guidance.
    owner_lines = [ln for ln in codeowners.read_text().splitlines()
                   if ln.strip() and not ln.startswith("#")]
    assert owner_lines and owner_lines[0].startswith("*")
    assert "@maintainer" in owner_lines[0]

    # The ruleset is valid JSON GitHub would accept, requiring review + code owners.
    payload = json.loads(ruleset.read_text())
    assert payload["target"] == "branch"
    pr_rule = next(r for r in payload["rules"] if r["type"] == "pull_request")
    assert pr_rule["parameters"]["required_approving_review_count"] >= 1
    assert pr_rule["parameters"]["require_code_owner_review"] is True

    # setup.md carries the apply command and the honest "never POSTs" framing.
    setup_text = setup.read_text()
    assert "gh api --method POST" in setup_text
    assert "never applies them for you" in setup_text


def test_compile_github_ruleset_empty_when_no_gates(tmp_path, monkeypatch):
    """A charter with no gates yields an empty ruleset rule list, not a bogus one."""
    import json

    monkeypatch.chdir(tmp_path)
    (tmp_path / "nogate.yaml").write_text(
        "project: nogate\n"
        "roles: [a]\n"
        "actions:\n"
        "  x: { responsible: a, accountable: a }\n",
        encoding="utf-8",
    )
    out = tmp_path / "out"
    result = runner.invoke(app, [
        "compile", "--target", "github", "nogate.yaml", "--out-dir", str(out),
    ])
    assert result.exit_code == 0
    payload = json.loads((out / "github-ruleset.json").read_text())
    assert payload["rules"] == []


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


def test_compile_claude_frontmatter_is_parseable_yaml(tmp_path):
    """Every generated agent file's frontmatter must yaml.safe_load cleanly.

    The description embeds "Responsible for: …" — unquoted, that ": " breaks
    YAML and Claude Code would reject the file. Regression guard for that.
    """
    import yaml

    runner.invoke(app, [
        "compile", "--target", "claude", GOVERNANCE, "--out-dir", str(tmp_path),
    ])
    agent_files = sorted((tmp_path / ".claude" / "agents").glob("*.md"))
    assert agent_files, "no agent files were written"
    for f in agent_files:
        text = f.read_text(encoding="utf-8")
        assert text.startswith("---\n"), f
        fm_text = text.split("---", 2)[1]
        fm = yaml.safe_load(fm_text)
        assert isinstance(fm, dict), f"{f}: frontmatter did not parse to a dict"
        assert fm.get("name") == f.stem
        assert isinstance(fm.get("description"), str) and fm["description"]
        if "model" in fm:
            assert fm["model"] in ("opus", "sonnet", "haiku")


def test_compile_github_setup_md_renders_escalate_and_break_glass(tmp_path, monkeypatch):
    """The per-action notes cover the escalate_to and break_glass gate branches."""
    monkeypatch.chdir(tmp_path)
    (tmp_path / "esc.yaml").write_text(
        "project: esc\n"
        "roles: [owner, lead, dev]\n"
        "members:\n"
        "  - { name: alice, type: human, role: owner }\n"
        "  - { name: bob, type: human, role: lead }\n"
        "actions:\n"
        "  deploy:\n"
        "    responsible: dev\n"
        "    accountable: owner\n"
        "    gate:\n"
        "      approver: owner\n"
        "      on_timeout: escalate_to:lead\n"
        "      break_glass: { who: lead, condition: SEV-1, requires_after_review: true }\n",
        encoding="utf-8",
    )
    out = tmp_path / "out"
    result = runner.invoke(app, ["compile", "--target", "github", "esc.yaml",
                                 "--out-dir", str(out)])
    assert result.exit_code == 0
    setup = (out / "github-setup.md").read_text()
    assert "route the decision to role 'lead'" in setup
    assert "Break-glass: 'lead' may override when SEV-1" in setup
    assert "after-the-fact review required" in setup


def test_compile_github_codeowners_no_human_owner_fallback(tmp_path, monkeypatch):
    """An agent-only-accountable gate yields a commented CODEOWNERS, not a bogus owner."""
    monkeypatch.chdir(tmp_path)
    (tmp_path / "bot.yaml").write_text(
        "project: bot\n"
        "roles: [bot, dev]\n"
        "members:\n"
        "  - { name: botty, type: agent, role: bot }\n"
        "actions:\n"
        "  merge:\n"
        "    responsible: dev\n"
        "    accountable: bot\n"
        "    gate:\n"
        "      approver: bot\n"
        "      on_timeout: block\n"
        "      break_glass: { who: dev, condition: emergency, requires_after_review: true }\n",
        encoding="utf-8",
    )
    out = tmp_path / "out"
    result = runner.invoke(app, ["compile", "--target", "github", "bot.yaml",
                                 "--out-dir", str(out)])
    assert result.exit_code == 0, result.stdout
    codeowners = (out / "CODEOWNERS").read_text()
    # No uncommented owner line (a bot can't be a code owner).
    assert not [ln for ln in codeowners.splitlines()
                if ln.strip() and not ln.startswith("#")]
    assert "no human is accountable" in codeowners
