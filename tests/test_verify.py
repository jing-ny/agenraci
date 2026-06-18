"""Tests for `agenraci verify --target github` (offline comparison core)."""

import base64
import json

from typer.testing import CliRunner

from agenraci.adapters.github import (
    CouldNotCheck,
    GitHubProtection,
    fetch_live_protection,
    parse_codeowners,
    parse_protection,
    protection_from_github,
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


def test_cli_verify_neither_mode_exit_two(tmp_path):
    charter = _charter(tmp_path, _HUMAN_GATED)
    result = runner.invoke(app, ["verify", str(charter)])
    assert result.exit_code == 2
    assert "exactly one" in result.stdout


def test_cli_verify_both_modes_exit_two(tmp_path):
    charter = _charter(tmp_path, _HUMAN_GATED)
    settings = _settings(tmp_path, code_owners=["alice"], required_reviews=1)
    result = runner.invoke(app, ["verify", str(charter), "--settings", str(settings),
                                 "--repo", "o/r"])
    assert result.exit_code == 2
    assert "exactly one" in result.stdout


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


# ---- increment 2: real GitHub-shape parsers --------------------------------

def test_parse_codeowners_unions_owners_ignoring_paths_and_comments():
    text = (
        "# comment line\n"
        "*            @alice @bob\n"
        "/docs/       @carol   # docs owner\n"
        "/api/        @org/platform\n"
    )
    assert parse_codeowners(text) == ["alice", "bob", "carol", "org/platform"]


def test_protection_from_github_classic_shape():
    classic = {"required_pull_request_reviews": {
        "required_approving_review_count": 2, "require_code_owner_reviews": True}}
    prot = protection_from_github(branch="main", protection=classic,
                                  repo={"allow_auto_merge": True},
                                  codeowners="* @alice")
    assert prot.required_reviews == 2
    assert prot.require_code_owner_review is True
    assert prot.code_owners == ["alice"]
    assert prot.allow_auto_merge is True


def test_protection_from_github_unions_classic_and_rulesets():
    """Union: required reviews = max, code-owner review = either."""
    classic = {"required_pull_request_reviews": {
        "required_approving_review_count": 1, "require_code_owner_reviews": False}}
    rules = [{"type": "pull_request", "parameters": {
        "required_approving_review_count": 3, "require_code_owner_review": True}}]
    prot = protection_from_github(branch="main", protection=classic, rules=rules)
    assert prot.required_reviews == 3        # max(1, 3)
    assert prot.require_code_owner_review is True  # False OR True


def test_protection_from_github_ruleset_only():
    """A repo protected only via a ruleset (no classic protection) is seen."""
    rules = [{"type": "pull_request", "parameters": {
        "required_approving_review_count": 1, "require_code_owner_review": True}}]
    prot = protection_from_github(branch="main", protection=None, rules=rules,
                                  codeowners="* @alice")
    assert prot.required_reviews == 1
    assert prot.require_code_owner_review is True


# ---- increment 2: live reader (injected runner, no network) ----------------

def _runner(*, repo=(0, '{"allow_auto_merge": false}', ""),
            protection=(1, "", "404 Not Found"),
            rules=(0, "[]", ""),
            codeowners=None):
    """Build a fake `gh api` runner keyed on path fragments."""
    def run(argv):
        path = argv[-1]
        if "/protection" in path:
            return protection
        if "/rules/branches/" in path:
            return rules
        if "/contents/" in path:
            if codeowners is None:
                return (1, "", "404 Not Found")
            enc = base64.b64encode(codeowners.encode()).decode()
            return (0, json.dumps({"encoding": "base64", "content": enc}), "")
        return repo  # repos/{repo}
    return run


def test_fetch_live_success():
    classic = json.dumps({"required_pull_request_reviews": {
        "required_approving_review_count": 1, "require_code_owner_reviews": True}})
    prot = fetch_live_protection(
        "o/r", "main",
        runner=_runner(protection=(0, classic, ""), codeowners="* @alice"))
    assert prot.required_reviews == 1
    assert prot.require_code_owner_review is True
    assert prot.code_owners == ["alice"]


def test_fetch_live_classic_404_is_not_an_error():
    """A 404 on the protection endpoint means 'no classic protection', not error."""
    prot = fetch_live_protection(
        "o/r", "main", runner=_runner(protection=(1, "", "404 Not Found")))
    assert prot.required_reviews == 0  # nothing enforced, but no exception


def test_fetch_live_repo_404_is_could_not_check():
    with __import__("pytest").raises(CouldNotCheck):
        fetch_live_protection(
            "o/missing", "main", runner=_runner(repo=(1, "", "404 Not Found")))


def test_fetch_live_auth_error_is_could_not_check():
    with __import__("pytest").raises(CouldNotCheck):
        fetch_live_protection(
            "o/r", "main", runner=_runner(repo=(1, "", "HTTP 401: Bad credentials")))


def test_fetch_live_propagates_runner_could_not_check():
    def boom(argv):
        raise CouldNotCheck("the `gh` CLI is not installed or not on PATH.")
    with __import__("pytest").raises(CouldNotCheck):
        fetch_live_protection("o/r", "main", runner=boom)


# ---- increment 2: CLI live mode --------------------------------------------

def test_cli_verify_live_success(tmp_path, monkeypatch):
    monkeypatch.setattr(
        "agenraci.cli.fetch_live_protection",
        lambda repo, branch: GitHubProtection(
            branch=branch, required_reviews=1, require_code_owner_review=True,
            code_owners=["alice"]),
    )
    charter = _charter(tmp_path, _HUMAN_GATED)
    result = runner.invoke(app, ["verify", str(charter), "--repo", "o/r",
                                 "--format", "json"])
    assert result.exit_code == 0
    assert json.loads(result.stdout)["ok"] is True


def test_cli_verify_live_could_not_check_exit_two(tmp_path, monkeypatch):
    def boom(repo, branch):
        raise CouldNotCheck("the `gh` CLI is not installed or not on PATH.")
    monkeypatch.setattr("agenraci.cli.fetch_live_protection", boom)
    charter = _charter(tmp_path, _HUMAN_GATED)
    result = runner.invoke(app, ["verify", str(charter), "--repo", "o/r"])
    assert result.exit_code == 2
    assert "could not check" in result.stdout.lower()


# ---- increment 2: error-taxonomy + default-runner edge cases ---------------

def test_fetch_live_protection_403_is_could_not_check():
    """A 403 on the protection endpoint is auth, NOT 'no classic protection'."""
    with __import__("pytest").raises(CouldNotCheck):
        fetch_live_protection(
            "o/r", "main",
            runner=_runner(protection=(1, "", "gh: Forbidden (HTTP 403)")))


def test_fetch_live_repo_500_is_could_not_check():
    """A non-404/non-auth failure on the repo endpoint still can't-check."""
    with __import__("pytest").raises(CouldNotCheck):
        fetch_live_protection(
            "o/r", "main", runner=_runner(repo=(1, "", "gh: Server Error (HTTP 500)")))


def test_fetch_live_unions_classic_and_ruleset_through_reader():
    """The classic∪ruleset union flows end-to-end through fetch_live_protection."""
    classic = json.dumps({"required_pull_request_reviews": {
        "required_approving_review_count": 1, "require_code_owner_reviews": False}})
    rules = json.dumps([{"type": "pull_request", "parameters": {
        "required_approving_review_count": 3, "require_code_owner_review": True}}])
    prot = fetch_live_protection(
        "o/r", "main",
        runner=_runner(protection=(0, classic, ""), rules=(0, rules, ""),
                       codeowners="* @alice"))
    assert prot.required_reviews == 3            # max(1, 3) from the ruleset
    assert prot.require_code_owner_review is True  # False(classic) OR True(ruleset)


def test_default_runner_missing_binary_is_could_not_check():
    """_default_runner maps a missing executable to CouldNotCheck."""
    from agenraci.adapters.github import _default_runner
    with __import__("pytest").raises(CouldNotCheck):
        _default_runner(["this-binary-does-not-exist-xyz", "api", "x"])


def test_cli_verify_repo_without_slash_exit_two(tmp_path):
    charter = _charter(tmp_path, _HUMAN_GATED)
    result = runner.invoke(app, ["verify", str(charter), "--repo", "noslug"])
    assert result.exit_code == 2
    assert "OWNER/REPO" in result.stdout


# ---- v0.2.1: org-wide sweep -------------------------------------------------

from agenraci.adapters.github import (  # noqa: E402
    OrgSweepReport,
    RepoResult,
    VerifyFinding,
    VerifyReport,
    sweep_org,
)


def _sweep_runner(repo_specs):
    """Fake runner handling both `gh repo list` and per-repo `gh api` calls.

    repo_specs maps "owner/name" -> "clean" | "drift" | "error".
    """
    names = list(repo_specs)

    def run(argv):
        if argv[:3] == ["gh", "repo", "list"]:
            return (0, json.dumps([{"nameWithOwner": n} for n in names]), "")
        path = argv[-1]
        repo = next((n for n in names if f"repos/{n}" in path), None)
        if repo is None:
            return (1, "", "404 Not Found")
        spec = repo_specs[repo]
        if spec == "error":
            return (1, "", "HTTP 403: Forbidden")  # repo-level -> CouldNotCheck
        if "/protection" in path:
            if spec == "clean":
                return (0, json.dumps({"required_pull_request_reviews": {
                    "required_approving_review_count": 1,
                    "require_code_owner_reviews": True}}), "")
            return (1, "", "404 Not Found")  # drift: no classic protection
        if "/rules/branches/" in path:
            return (0, "[]", "")
        if "/contents/" in path:
            if spec == "clean":
                enc = base64.b64encode(b"* @alice").decode()
                return (0, json.dumps({"encoding": "base64", "content": enc}), "")
            return (1, "", "404 Not Found")  # drift: no CODEOWNERS
        return (0, '{"allow_auto_merge": false}', "")  # repos/{repo}

    return run


def test_sweep_org_aggregates_clean_drift_and_unreadable(tmp_path):
    charter = load_charter(_charter(tmp_path, _HUMAN_GATED))
    runner_fn = _sweep_runner(
        {"o/clean": "clean", "o/drifty": "drift", "o/locked": "error"})
    report = sweep_org(charter, "o", runner=runner_fn)
    assert report.ok is False  # o/drifty drifts
    assert {r.repo: r.status for r in report.results} == {
        "o/clean": "clean", "o/drifty": "drift", "o/locked": "could-not-check"}
    # An unreadable repo is isolated, not fatal — the sweep still ran the others.
    locked = next(r for r in report.results if r.repo == "o/locked")
    assert locked.report is None and "403" in locked.error


def test_sweep_org_all_clean_is_ok(tmp_path):
    charter = load_charter(_charter(tmp_path, _HUMAN_GATED))
    report = sweep_org(charter, "o",
                       runner=_sweep_runner({"o/a": "clean", "o/b": "clean"}))
    assert report.ok is True
    assert all(r.status == "clean" for r in report.results)


def test_sweep_org_listing_failure_is_could_not_check(tmp_path):
    charter = load_charter(_charter(tmp_path, _HUMAN_GATED))

    def boom(argv):
        if argv[:3] == ["gh", "repo", "list"]:
            return (1, "", "HTTP 404: Not Found")
        return (0, "", "")
    with __import__("pytest").raises(CouldNotCheck):
        sweep_org(charter, "ghost-org", runner=boom)


def test_cli_verify_org_json(tmp_path, monkeypatch):
    charter = _charter(tmp_path, _HUMAN_GATED)
    fake = OrgSweepReport(org="o", branch="main", ok=False, results=[
        RepoResult("o/a", "clean", report=VerifyReport(
            project="t", branch="main", ok=True, findings=[], unenforceable=[])),
        RepoResult("o/b", "could-not-check", error="HTTP 403: Forbidden"),
    ])
    monkeypatch.setattr("agenraci.cli.sweep_org", lambda c, o, branch="main": fake)
    result = runner.invoke(app, ["verify", str(charter), "--org", "o",
                                 "--format", "json"])
    assert result.exit_code == 1  # not ok
    payload = json.loads(result.stdout)
    assert payload["org"] == "o"
    assert {r["repo"]: r["status"] for r in payload["repos"]} == {
        "o/a": "clean", "o/b": "could-not-check"}


def test_cli_verify_three_modes_are_mutually_exclusive(tmp_path):
    charter = _charter(tmp_path, _HUMAN_GATED)
    settings = _settings(tmp_path, code_owners=["alice"], required_reviews=1)
    # repo + org together -> exit 2
    r1 = runner.invoke(app, ["verify", str(charter), "--repo", "o/r", "--org", "o"])
    assert r1.exit_code == 2 and "exactly one" in r1.stdout
    # settings + org together -> exit 2
    r2 = runner.invoke(app, ["verify", str(charter), "--settings", str(settings),
                             "--org", "o"])
    assert r2.exit_code == 2


def test_cli_verify_org_human_format(tmp_path, monkeypatch):
    charter = _charter(tmp_path, _HUMAN_GATED)
    fake = OrgSweepReport(org="o", branch="main", ok=False, results=[
        RepoResult("o/a", "clean", report=VerifyReport(
            project="t", branch="main", ok=True, findings=[], unenforceable=[])),
        RepoResult("o/b", "drift", report=VerifyReport(
            project="t", branch="main", ok=False,
            findings=[VerifyFinding("main", "drift", "no review required")],
            unenforceable=[])),
    ])
    monkeypatch.setattr("agenraci.cli.sweep_org", lambda c, o, branch="main": fake)
    result = runner.invoke(app, ["verify", str(charter), "--org", "o"])
    assert result.exit_code == 1
    assert "o/a" in result.stdout and "o/b" in result.stdout
    assert "DRIFT" in result.stdout and "1 of 2" in result.stdout


def test_sweep_org_flags_truncation_when_org_exceeds_limit(tmp_path):
    """A clean verdict must never be mistaken for a complete audit (truncation)."""
    charter = load_charter(_charter(tmp_path, _HUMAN_GATED))
    runner_fn = _sweep_runner({"o/a": "clean", "o/b": "clean"})
    # limit == number of repos returned -> there may be more -> truncated.
    assert sweep_org(charter, "o", runner=runner_fn, limit=2).truncated is True
    # limit comfortably above the count -> not truncated.
    assert sweep_org(charter, "o", runner=runner_fn, limit=10).truncated is False


def test_sweep_org_empty_org_is_ok_with_no_results(tmp_path):
    charter = load_charter(_charter(tmp_path, _HUMAN_GATED))
    report = sweep_org(charter, "empty", runner=_sweep_runner({}))
    assert report.results == [] and report.ok is True and report.truncated is False


def test_cli_verify_org_empty_says_nothing_to_verify(tmp_path, monkeypatch):
    charter = _charter(tmp_path, _HUMAN_GATED)
    monkeypatch.setattr(
        "agenraci.cli.sweep_org",
        lambda c, o, branch="main": OrgSweepReport(
            org="empty", branch="main", ok=True, results=[]),
    )
    result = runner.invoke(app, ["verify", str(charter), "--org", "empty"])
    assert result.exit_code == 0
    assert "0 repos found" in result.stdout
