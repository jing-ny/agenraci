"""Tests for `agenraci verify --target github` (offline comparison core)."""

import json

from typer.testing import CliRunner

from agenraci.adapters.github import (
    GitHubProtection,
    parse_protection,
    verify_github,
)
from agenraci.cli import app
from agenraci.loader import load_charter

runner = CliRunner()

# A charter with one gated action whose accountable role has a human member.
_HUMAN_GATED = (
    "project: t\n"
    "roles: [owner, dev]\n"
    "members:\n"
    "  - { name: alice, type: human, role: owner }\n"
    "actions:\n"
    "  merge:\n"
    "    responsible: dev\n"
    "    accountable: owner\n"
    "    gate: { approver: owner, on_timeout: block }\n"
)

# Same shape, but the accountable role holds only an agent (can't be a code owner).
_AGENT_GATED = (
    "project: t\n"
    "roles: [bot, dev]\n"
    "members:\n"
    "  - { name: botty, type: agent, role: bot }\n"
    "actions:\n"
    "  merge:\n"
    "    responsible: dev\n"
    "    accountable: bot\n"
    "    gate: { approver: bot, on_timeout: block }\n"
)

# A charter with no gated action at all.
_NO_GATE = (
    "project: t\n"
    "roles: [owner]\n"
    "members:\n"
    "  - { name: alice, type: human, role: owner }\n"
    "actions:\n"
    "  doc: { responsible: owner, accountable: owner }\n"
)

# Two gated actions owned by different humans — the expected owner set is the
# union of both (the strictest-wins reduction across actions on one branch).
_TWO_GATED = (
    "project: t\n"
    "roles: [owner, lead, dev]\n"
    "members:\n"
    "  - { name: alice, type: human, role: owner }\n"
    "  - { name: bob, type: human, role: lead }\n"
    "actions:\n"
    "  merge:\n"
    "    responsible: dev\n"
    "    accountable: owner\n"
    "    gate: { approver: owner, on_timeout: block }\n"
    "  deploy:\n"
    "    responsible: dev\n"
    "    accountable: lead\n"
    "    gate: { approver: lead, on_timeout: block }\n"
)


def _charter(tmp_path, body):
    p = tmp_path / "charter.yaml"
    p.write_text(body, encoding="utf-8")
    return p


def _settings(tmp_path, **kw):
    p = tmp_path / "protection.json"
    p.write_text(json.dumps(kw), encoding="utf-8")
    return p


# ---- comparison core (pure function) ---------------------------------------

def test_verify_clean(tmp_path):
    charter = load_charter(_charter(tmp_path, _HUMAN_GATED))
    prot = GitHubProtection(
        branch="main", required_reviews=1, require_code_owner_review=True,
        code_owners=["alice"], allow_auto_merge=False,
    )
    report = verify_github(charter, prot)
    assert report.ok is True
    assert report.findings == []
    assert report.unenforceable == []


def test_verify_drift_missing_owner(tmp_path):
    charter = load_charter(_charter(tmp_path, _HUMAN_GATED))
    prot = GitHubProtection(
        branch="main", required_reviews=1, require_code_owner_review=True,
        code_owners=["bob"],  # alice (accountable) is missing
    )
    report = verify_github(charter, prot)
    assert report.ok is False
    assert any("missing accountable owner" in f.message and "@alice" in f.message
               for f in report.findings)


def test_verify_drift_no_required_review(tmp_path):
    charter = load_charter(_charter(tmp_path, _HUMAN_GATED))
    prot = GitHubProtection(
        branch="main", required_reviews=0, require_code_owner_review=True,
        code_owners=["alice"],
    )
    report = verify_github(charter, prot)
    assert report.ok is False
    assert any("no approving review" in f.message for f in report.findings)


def test_verify_drift_no_code_owner_review(tmp_path):
    charter = load_charter(_charter(tmp_path, _HUMAN_GATED))
    prot = GitHubProtection(
        branch="main", required_reviews=1, require_code_owner_review=False,
        code_owners=["alice"],
    )
    report = verify_github(charter, prot)
    assert report.ok is False
    assert any("require review from code owners" in f.message
               for f in report.findings)


def test_verify_drift_auto_merge_with_block(tmp_path):
    charter = load_charter(_charter(tmp_path, _HUMAN_GATED))  # on_timeout=block
    prot = GitHubProtection(
        branch="main", required_reviews=1, require_code_owner_review=True,
        code_owners=["alice"], allow_auto_merge=True,
    )
    report = verify_github(charter, prot)
    assert report.ok is False
    assert any("auto-merge is enabled" in f.message for f in report.findings)


def test_verify_agent_only_is_unenforceable_not_drift(tmp_path):
    """An agent-only-accountable action is surfaced, never silently green."""
    charter = load_charter(_charter(tmp_path, _AGENT_GATED))
    prot = GitHubProtection(
        branch="main", required_reviews=1, require_code_owner_review=True,
        code_owners=[],  # nothing expected, since the only owner would be an agent
    )
    report = verify_github(charter, prot)
    assert report.ok is True  # unenforceable does not flip ok
    assert report.findings == []
    assert len(report.unenforceable) == 1
    assert report.unenforceable[0].target == "merge"


def test_verify_directionality_stricter_repo_passes(tmp_path):
    """The charter is a floor: a repo with MORE owners and reviews still passes."""
    charter = load_charter(_charter(tmp_path, _HUMAN_GATED))
    prot = GitHubProtection(
        branch="main", required_reviews=3, require_code_owner_review=True,
        code_owners=["alice", "bob", "carol"],  # superset of {alice}
    )
    report = verify_github(charter, prot)
    assert report.ok is True


def test_verify_no_gated_actions_passes_with_note(tmp_path):
    charter = load_charter(_charter(tmp_path, _NO_GATE))
    prot = GitHubProtection(branch="main")
    report = verify_github(charter, prot)
    assert report.ok is True
    assert report.note and "no action declares a gate" in report.note.lower()


def test_verify_reduction_unions_owners_across_gated_actions(tmp_path):
    """Expected owners = union of accountable humans across all gated actions."""
    charter = load_charter(_charter(tmp_path, _TWO_GATED))
    # Only one of the two required owners is present → drift names the missing one.
    partial = GitHubProtection(
        branch="main", required_reviews=1, require_code_owner_review=True,
        code_owners=["alice"],  # bob (accountable for deploy) is missing
    )
    report = verify_github(charter, partial)
    assert report.ok is False
    assert any("@bob" in f.message for f in report.findings)

    # Both owners present → clean.
    full = GitHubProtection(
        branch="main", required_reviews=1, require_code_owner_review=True,
        code_owners=["alice", "bob"],
    )
    assert verify_github(charter, full).ok is True


def test_parse_protection_strips_at_signs():
    prot = parse_protection({"code_owners": ["@alice", "bob"], "required_reviews": 2})
    assert prot.code_owners == ["alice", "bob"]
    assert prot.required_reviews == 2


# ---- CLI integration --------------------------------------------------------

def test_cli_verify_clean_json_exit_zero(tmp_path):
    charter = _charter(tmp_path, _HUMAN_GATED)
    settings = _settings(tmp_path, branch="main", required_reviews=1,
                         require_code_owner_review=True, code_owners=["alice"])
    result = runner.invoke(app, ["verify", str(charter), "--settings", str(settings),
                                 "--format", "json"])
    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["ok"] is True
    assert payload["target"] == "github"
    assert payload["findings"] == []


def test_cli_verify_drift_exit_one(tmp_path):
    charter = _charter(tmp_path, _HUMAN_GATED)
    settings = _settings(tmp_path, branch="main", required_reviews=0,
                         require_code_owner_review=False, code_owners=[])
    result = runner.invoke(app, ["verify", str(charter), "--settings", str(settings),
                                 "--format", "json"])
    assert result.exit_code == 1
    payload = json.loads(result.stdout)
    assert payload["ok"] is False
    assert len(payload["findings"]) >= 1


def test_cli_verify_bad_settings_is_could_not_check_exit_two(tmp_path):
    charter = _charter(tmp_path, _HUMAN_GATED)
    bad = tmp_path / "protection.json"
    bad.write_text("{ not json", encoding="utf-8")
    result = runner.invoke(app, ["verify", str(charter), "--settings", str(bad)])
    assert result.exit_code == 2  # could-not-check, distinct from drift


def test_cli_verify_missing_settings_exit_two(tmp_path):
    charter = _charter(tmp_path, _HUMAN_GATED)
    result = runner.invoke(app, ["verify", str(charter)])
    assert result.exit_code == 2
    assert "--settings is required" in result.stdout


def test_cli_verify_human_format_clean_and_drift(tmp_path):
    """The default human output renders OK / DRIFT verdicts with correct exits."""
    charter = _charter(tmp_path, _HUMAN_GATED)
    ok_settings = _settings(tmp_path, branch="main", required_reviews=1,
                            require_code_owner_review=True, code_owners=["alice"])
    clean = runner.invoke(app, ["verify", str(charter), "--settings", str(ok_settings)])
    assert clean.exit_code == 0
    assert "OK" in clean.stdout

    bad = tmp_path / "bad.json"
    bad.write_text(json.dumps({"branch": "main", "required_reviews": 0,
                               "code_owners": []}), encoding="utf-8")
    drift = runner.invoke(app, ["verify", str(charter), "--settings", str(bad)])
    assert drift.exit_code == 1
    assert "DRIFT" in drift.stdout


def test_cli_verify_warns_on_branch_mismatch(tmp_path):
    """An export for a different branch than --branch warns but does not fail."""
    charter = _charter(tmp_path, _HUMAN_GATED)
    settings = _settings(tmp_path, branch="release", required_reviews=1,
                         require_code_owner_review=True, code_owners=["alice"])
    result = runner.invoke(app, ["verify", str(charter), "--settings", str(settings),
                                 "--branch", "main"])
    assert result.exit_code == 0  # warning, not failure
    assert "release" in result.stdout and "main" in result.stdout


def test_cli_verify_unknown_target_exit_two(tmp_path):
    charter = _charter(tmp_path, _HUMAN_GATED)
    settings = _settings(tmp_path, code_owners=["alice"], required_reviews=1)
    result = runner.invoke(app, ["verify", str(charter), "--settings", str(settings),
                                 "--target", "gitlab"])
    assert result.exit_code == 2
    assert "unknown --target" in result.stdout
