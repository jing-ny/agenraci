"""Tests for `agenraci compile` — the real github target and the stubs."""

import json
from pathlib import Path

from typer.testing import CliRunner

from agenraci.adapters import github as gh
from agenraci.cli import app
from agenraci.loader import load_charter

runner = CliRunner()

GOVERNANCE = "governance/charter.yaml"


def _protection_json_from(out: str) -> dict:
    """Extract and parse the JSON between the protection BEGIN/END markers."""
    begin = out.index("# --- BEGIN protection.json ---")
    end = out.index("# --- END protection.json ---")
    body = out[begin:end].split("\n", 1)[1]
    return json.loads(body)


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


def test_compile_github_emits_applyable_protection_json():
    """The new block is real GitHub PUT JSON that round-trips with verify.

    The checklist/CODEOWNERS still emits (kept), and the emitted JSON satisfies
    exactly what verify_github reads: >=1 required review, and code-owner review
    required because the governance charter has human-accountable gated actions.
    """
    result = runner.invoke(app, ["compile", "--target", "github", GOVERNANCE])
    assert result.exit_code == 0
    out = result.stdout
    # The existing human guidance is untouched.
    assert "CODEOWNERS" in out
    assert "Branch protection" in out
    # The new applyable section + the ready-to-run command.
    assert "gh api repos/OWNER/REPO/branches/BRANCH/protection" in out
    # The verify round-trip command must include the REQUIRED positional charter
    # path, or it exits 2 ("Missing argument 'CHARTER_PATH'") when pasted.
    verify_line = next(ln for ln in out.splitlines() if "agenraci verify" in ln)
    assert "CHARTER.yaml" in verify_line
    assert "--repo OWNER/REPO" in verify_line

    body = _protection_json_from(out)
    rpr = body["required_pull_request_reviews"]
    assert rpr["required_approving_review_count"] >= 1
    # governance charter: maintainer (human) is accountable for gated actions.
    assert rpr["require_code_owner_reviews"] is True
    # Real PUT shape: these keys must be present (nullable) for GitHub to accept it.
    assert set(body) >= {
        "required_status_checks", "enforce_admins",
        "required_pull_request_reviews", "restrictions",
    }

    # Fact-level round trip: the emitted body, read by the live verifier's own
    # normaliser, must satisfy verify_github against the same charter.
    charter = load_charter(GOVERNANCE)
    protection = gh.protection_from_github(branch="main", protection=body)
    # The CODEOWNERS owner-set drift is independent of this JSON; check the two
    # facts this block is responsible for are clean.
    report = gh.verify_github(charter, gh.GitHubProtection(
        branch="main",
        required_reviews=protection.required_reviews,
        require_code_owner_review=protection.require_code_owner_review,
        code_owners=sorted({
            h for a in charter.actions.values() if a.gate is not None
            for r in a.accountable
            for m in charter.members
            if m.role == r and m.type == "human" and (h := m.name)
        }),
        allow_auto_merge=False,
    ))
    assert report.ok, [f.message for f in report.findings]


def test_compile_github_no_human_accountable_omits_code_owner_review():
    """Agent-only gated action: reviews required, but code-owner review stays OFF.

    The relay example is all-agent (no human members), so no human is accountable
    for its gated actions. Mirrors verify_github treating code-owner enforcement
    as impossible without a human owner — we must not emit JSON that pretends
    otherwise.
    """
    result = runner.invoke(
        app, ["compile", "--target", "github", "examples/relay/charter.yaml"])
    assert result.exit_code == 0
    body = _protection_json_from(result.stdout)
    rpr = body["required_pull_request_reviews"]
    assert rpr["required_approving_review_count"] >= 1
    assert rpr["require_code_owner_reviews"] is False
    # on_timeout=block -> the repo-level auto-merge-off hint must appear.
    assert "allow_auto_merge=false" in result.stdout


def test_compile_github_no_gates_emits_no_protection_json(tmp_path, monkeypatch):
    """No gated action -> early return; no protection JSON block at all."""
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
    assert "BEGIN protection.json" not in result.stdout


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
