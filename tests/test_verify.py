"""Tests for `agenraci verify --target github`: CLI, live reader and org sweep.

The approval semantics themselves (which status each setup gets) are covered
example by example in tests/test_verify_contract.py.
"""

import base64
import json

import pytest
from typer.testing import CliRunner

from agenraci.adapters.github import (
    ActionResult,
    CouldNotCheck,
    GitHubProtection,
    OrgSweepReport,
    Reason,
    RepoResult,
    VerifyFinding,
    VerifyReport,
    fetch_live_protection,
    parse_codeowners,
    parse_protection,
    protection_from_github,
    sweep_org,
    verify_github,
)
from agenraci.cli import app
from agenraci.loader import load_charter

runner = CliRunner()

# One gated action, approved by a human, judged over every path.
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
    "    github: { paths: ['*'] }\n"
)

# Same shape, but the approver role holds only an agent (can't be a code owner).
_AGENT_GATED = _HUMAN_GATED.replace(
    "  - { name: alice, type: human, role: owner }\n",
    "  - { name: botty, type: agent, role: owner }\n")

# A charter with no gated action at all.
_NO_GATE = (
    "project: t\n"
    "roles: [owner]\n"
    "members:\n"
    "  - { name: alice, type: human, role: owner }\n"
    "actions:\n"
    "  doc: { responsible: owner, accountable: owner }\n"
)

# Everything verify needs, stated, for _HUMAN_GATED to verify.
_FULL = {
    "branch": "main", "required_reviews": 1, "require_code_owner_review": True,
    "dismiss_stale_reviews": True, "codeowners": "* @alice\n",
    "codeowners_path": ".github/CODEOWNERS", "codeowners_errors": [],
    "owner_permissions": {"alice": "write"}, "enforce_admins": True,
    "bypass_actors": [], "allow_auto_merge": False,
}


def _charter(tmp_path, body):
    p = tmp_path / "charter.yaml"
    p.write_text(body, encoding="utf-8")
    return p


def _settings(tmp_path, **kw):
    p = tmp_path / "protection.json"
    p.write_text(json.dumps(kw), encoding="utf-8")
    return p


def _full(tmp_path, **overrides):
    return _settings(tmp_path, **{**_FULL, **overrides})


def _invoke(*args):
    return runner.invoke(app, ["verify", *map(str, args)])


# ---- offline CLI: exit codes and output ------------------------------------

def test_cli_verified_json_exit_zero(tmp_path):
    result = _invoke(_charter(tmp_path, _HUMAN_GATED), "--settings", _full(tmp_path),
                     "--format", "json")
    assert result.exit_code == 0, result.stdout
    payload = json.loads(result.stdout)
    assert payload["status"] == "verified"
    assert payload["evidence"] == "snapshot"
    assert payload["ok"] is True and payload["findings"] == []
    assert payload["target"] == "github"
    [action] = payload["actions"]
    assert action == {"action": "merge", "status": "verified", "paths": ["*"],
                      "eligible_approvers": ["alice"], "reasons": []}


def test_cli_drift_exit_one(tmp_path):
    result = _invoke(_charter(tmp_path, _HUMAN_GATED), "--settings",
                     _full(tmp_path, codeowners="* @alice @bob\n",
                           owner_permissions={"alice": "write", "bob": "write"}),
                     "--format", "json")
    assert result.exit_code == 1
    payload = json.loads(result.stdout)
    assert payload["status"] == "drift" and payload["ok"] is False
    assert any("@bob" in f["message"] for f in payload["findings"])
    assert payload["actions"][0]["reasons"][0]["kind"] == "drift"


def test_cli_incomplete_exit_two_and_allow_incomplete(tmp_path):
    charter = _charter(tmp_path, _HUMAN_GATED)
    settings = _full(tmp_path)
    data = json.loads(settings.read_text())
    del data["bypass_actors"]
    settings.write_text(json.dumps(data))
    result = _invoke(charter, "--settings", settings)
    assert result.exit_code == 2
    assert "INCOMPLETE" in result.stdout and "not a pass" in result.stdout
    allowed = _invoke(charter, "--settings", settings, "--allow-incomplete")
    assert allowed.exit_code == 0
    assert "warning: --allow-incomplete" in allowed.stdout


def test_cli_allow_incomplete_never_hides_drift(tmp_path):
    result = _invoke(_charter(tmp_path, _HUMAN_GATED), "--settings",
                     _full(tmp_path, required_reviews=0), "--allow-incomplete")
    assert result.exit_code == 1


def test_cli_legacy_export_is_incomplete_not_clean(tmp_path):
    """An old export (owner names only) can no longer pass silently."""
    settings = _settings(tmp_path, branch="main", required_reviews=1,
                         require_code_owner_review=True, code_owners=["alice"])
    result = _invoke(_charter(tmp_path, _HUMAN_GATED), "--settings", settings)
    assert result.exit_code == 2
    assert "raw `codeowners`" in result.stdout


def test_cli_human_format_lists_each_action(tmp_path):
    clean = _invoke(_charter(tmp_path, _HUMAN_GATED), "--settings", _full(tmp_path))
    assert clean.exit_code == 0
    assert "verified" in clean.stdout and "merge" in clean.stdout
    assert "VERIFIED" in clean.stdout
    assert "snapshot" in clean.stdout
    assert "GitHub logins by convention" in clean.stdout

    drift = _invoke(_charter(tmp_path, _HUMAN_GATED), "--settings",
                    _full(tmp_path, dismiss_stale_reviews=False))
    assert drift.exit_code == 1
    assert "DRIFT" in drift.stdout and "stale approvals" in drift.stdout


def test_cli_auto_merge_on_still_verifies(tmp_path):
    """#81 end to end: auto-merge is not a bypass."""
    result = _invoke(_charter(tmp_path, _HUMAN_GATED), "--settings",
                     _full(tmp_path, allow_auto_merge=True))
    assert result.exit_code == 0, result.stdout
    assert "auto-merge" not in result.stdout


def test_cli_no_gated_actions_is_nothing_to_verify(tmp_path):
    result = _invoke(_charter(tmp_path, _NO_GATE), "--settings", _full(tmp_path),
                     "--format", "json")
    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["status"] == "nothing-to-verify" and payload["note"]


def test_cli_agent_only_approver_is_incomplete_and_unenforceable(tmp_path):
    result = _invoke(_charter(tmp_path, _AGENT_GATED), "--settings", _full(tmp_path),
                     "--format", "json")
    assert result.exit_code == 2
    payload = json.loads(result.stdout)
    assert payload["status"] == "incomplete"
    assert [u["target"] for u in payload["unenforceable"]] == ["merge"]
    assert payload["actions"][0]["reasons"][-1]["code"] == "no-human-approver"


def test_cli_bad_settings_is_could_not_check_exit_two(tmp_path):
    bad = tmp_path / "protection.json"
    bad.write_text("{ not json", encoding="utf-8")
    assert _invoke(_charter(tmp_path, _HUMAN_GATED), "--settings", bad).exit_code == 2
    bad.write_text("[]", encoding="utf-8")
    assert _invoke(_charter(tmp_path, _HUMAN_GATED), "--settings", bad).exit_code == 2


@pytest.mark.parametrize("override", [
    {"require_code_owner_review": "false"},    # a string is not a yes
    {"dismiss_stale_reviews": 1},
    {"required_reviews": "1"},
    {"required_reviews": True},
    {"owner_permissions": {"alice": 1}},
    {"owner_permissions": ["alice"]},
    {"codeowners": ["* @alice"]},
    {"bypass_actors": "none"},
    {"codeowners_errors": "none"},
    {"enforce_admins": "yes"},
])
def test_cli_settings_with_wrong_types_are_could_not_check(tmp_path, override):
    result = _invoke(_charter(tmp_path, _HUMAN_GATED), "--settings",
                     _full(tmp_path, **override))
    assert result.exit_code == 2
    assert "could not read settings" in result.output.lower()


def test_cli_null_owner_permission_is_unknown_not_a_pass(tmp_path):
    result = _invoke(_charter(tmp_path, _HUMAN_GATED), "--settings",
                     _full(tmp_path, owner_permissions={"alice": None}),
                     "--format", "json")
    assert result.exit_code == 2
    assert json.loads(result.stdout)["status"] == "incomplete"


def test_cli_warns_on_branch_mismatch(tmp_path):
    result = _invoke(_charter(tmp_path, _HUMAN_GATED), "--settings",
                     _full(tmp_path, branch="develop"))
    assert "settings export is for branch 'develop'" in result.stdout


def test_cli_charter_with_unsupported_github_path_is_rejected(tmp_path):
    body = _HUMAN_GATED.replace("paths: ['*']", "paths: ['[ab]']")
    result = _invoke(_charter(tmp_path, body), "--settings", _full(tmp_path))
    assert result.exit_code == 2
    assert "could not load" in result.stdout


# ---- argument validation ---------------------------------------------------

def test_cli_neither_mode_exit_two(tmp_path):
    result = _invoke(_charter(tmp_path, _HUMAN_GATED))
    assert result.exit_code == 2 and "exactly one" in result.stdout


def test_cli_three_modes_are_mutually_exclusive(tmp_path):
    charter = _charter(tmp_path, _HUMAN_GATED)
    settings = _full(tmp_path)
    for extra in (["--settings", settings, "--repo", "o/r"],
                  ["--repo", "o/r", "--org", "o"],
                  ["--settings", settings, "--org", "o"]):
        result = _invoke(charter, *extra)
        assert result.exit_code == 2 and "exactly one" in result.stdout


def test_cli_limit_without_org_exit_two(tmp_path):
    result = _invoke(_charter(tmp_path, _HUMAN_GATED), "--settings", _full(tmp_path),
                     "--limit", "5")
    assert result.exit_code == 2
    assert "--limit only applies to --org" in result.stdout


def test_cli_unknown_target_exit_two(tmp_path):
    result = _invoke(_charter(tmp_path, _HUMAN_GATED), "--settings", _full(tmp_path),
                     "--target", "gitlab")
    assert result.exit_code == 2


def test_cli_bad_format_rejected(tmp_path):
    result = _invoke(_charter(tmp_path, _HUMAN_GATED), "--settings", _full(tmp_path),
                     "--format", "xml")
    assert result.exit_code == 2


def test_cli_repo_without_slash_exit_two(tmp_path):
    result = _invoke(_charter(tmp_path, _HUMAN_GATED), "--repo", "noslug")
    assert result.exit_code == 2 and "OWNER/REPO" in result.stdout


# ---- SARIF -----------------------------------------------------------------

def _sarif(result):
    doc = json.loads(result.stdout)
    assert doc["version"] == "2.1.0"
    return doc["runs"][0]


def test_cli_sarif_drift_is_error(tmp_path):
    charter = _charter(tmp_path, _HUMAN_GATED)
    result = _invoke(charter, "--settings", _full(tmp_path, required_reviews=0),
                     "--format", "sarif")
    assert result.exit_code == 1
    run = _sarif(result)
    assert run["tool"]["driver"]["name"] == "AgenRACI"
    assert {r["id"] for r in run["tool"]["driver"]["rules"]} == {
        "drift", "incomplete", "unenforceable"}
    assert [r["ruleId"] for r in run["results"]] == ["drift"]
    assert run["results"][0]["level"] == "error"
    uri = run["results"][0]["locations"][0]["physicalLocation"]["artifactLocation"]["uri"]
    assert uri == str(charter)


def test_cli_sarif_verified_has_no_results(tmp_path):
    result = _invoke(_charter(tmp_path, _HUMAN_GATED), "--settings", _full(tmp_path),
                     "--format", "sarif")
    assert result.exit_code == 0
    assert _sarif(result)["results"] == []


def test_cli_sarif_incomplete_and_unenforceable_are_warnings(tmp_path):
    result = _invoke(_charter(tmp_path, _AGENT_GATED), "--settings",
                     _full(tmp_path, dismiss_stale_reviews=None), "--format", "sarif")
    assert result.exit_code == 2
    res = _sarif(result)["results"]
    assert {r["ruleId"] for r in res} == {"incomplete", "unenforceable"}
    assert all(r["level"] == "warning" for r in res)


# ---- live reader (injected runner, no network) -----------------------------

_NOT_PROTECTED = (1, '{"message": "Branch not protected"}',
                  "gh: Branch not protected (HTTP 404)")


def _runner(*, repo=(0, '{"allow_auto_merge": false}', ""),
            protection=_NOT_PROTECTED,
            rules=(0, "[]", ""),
            codeowners=None,
            errors=(0, '{"errors": []}', ""),
            permission=(0, '{"permission": "write", "role_name": "write"}', ""),
            team_repo=(0, '{"permissions": {"push": true}}', ""),
            team_members=(0, '[{"login": "alice"}]', ""),
            team=(0, '{"slug": "rel"}', ""),
            calls=None):
    """A fake `gh api` runner keyed on path fragments."""
    def run(argv):
        path = argv[-1]
        if calls is not None:
            calls.append(argv)
        if "/codeowners/errors" in path:
            return errors
        if "/collaborators/" in path:
            return permission
        if path.startswith("orgs/") and "/repos/" in path:
            return team_repo
        if path.startswith("orgs/") and "/members" in path:
            return team_members
        if path.startswith("orgs/"):
            return team
        if "/protection" in path:
            return protection
        if "/rules/branches/" in path:
            return rules
        if "/contents/" in path:
            if codeowners is None or ".github/CODEOWNERS" not in path:
                return (1, "", "404 Not Found")
            enc = base64.b64encode(codeowners.encode()).decode()
            return (0, json.dumps({"encoding": "base64", "content": enc}), "")
        return repo  # repos/{repo}
    return run


_CLASSIC = json.dumps({"required_pull_request_reviews": {
    "required_approving_review_count": 1, "require_code_owner_reviews": True,
    "dismiss_stale_reviews": True}})


def test_fetch_live_reads_the_evidence_verify_needs():
    prot = fetch_live_protection(
        "o/r", "main",
        runner=_runner(protection=(0, _CLASSIC, ""), codeowners="* @alice @o/rel\n"))
    assert prot.evidence == "live"
    assert prot.required_reviews == 1
    assert prot.require_code_owner_review is True
    assert prot.dismiss_stale_reviews is True
    assert prot.codeowners_found is True
    assert prot.codeowners_path == ".github/CODEOWNERS"
    assert prot.codeowners_errors == []
    assert prot.owner_permissions == {"alice": True}
    assert prot.teams["o/rel"].write is True
    assert prot.teams["o/rel"].members == ["alice"]
    # Bypass evidence is not read yet (#80), so it stays unknown.
    assert prot.enforce_admins is None and prot.bypass_actors is None


def test_fetch_live_team_access_uses_the_repository_media_type():
    calls = []
    fetch_live_protection("o/r", "main",
                          runner=_runner(codeowners="* @o/rel\n", calls=calls))
    team_call = next(c for c in calls if c[-1].startswith("orgs/o/teams/rel/repos/"))
    assert "Accept: application/vnd.github.v3.repository+json" in team_call


def test_fetch_live_without_codeowners_is_evidence_of_no_file():
    prot = fetch_live_protection("o/r", "main", runner=_runner())
    assert prot.codeowners_found is False


def test_fetch_live_unreadable_permission_stays_unknown():
    prot = fetch_live_protection(
        "o/r", "main",
        runner=_runner(codeowners="* @alice\n",
                       permission=(1, "", "gh: Forbidden (HTTP 403)")))
    assert prot.owner_permissions == {}  # alice unknown -> incomplete, not a pass


def test_fetch_live_non_collaborator_has_no_write():
    prot = fetch_live_protection(
        "o/r", "main",
        runner=_runner(codeowners="* @alice\n",
                       permission=(0, '{"permission": "none", "role_name": ""}', "")))
    assert prot.owner_permissions == {"alice": False}


def test_fetch_live_collaborator_404_stays_unknown():
    # GitHub also answers 404 for a user the token isn't allowed to see.
    prot = fetch_live_protection(
        "o/r", "main",
        runner=_runner(codeowners="* @alice\n", permission=(1, "", "404 Not Found")))
    assert prot.owner_permissions == {}


def test_fetch_live_team_404_counts_only_when_the_team_is_visible():
    no_access = fetch_live_protection(
        "o/r", "main",
        runner=_runner(codeowners="* @o/rel\n", team_repo=(1, "", "404 Not Found")))
    assert no_access.teams["o/rel"].write is False
    hidden = fetch_live_protection(
        "o/r", "main",
        runner=_runner(codeowners="* @o/rel\n", team_repo=(1, "", "404 Not Found"),
                       team=(1, "", "404 Not Found")))
    assert hidden.teams["o/rel"].write is None


def _contents_runner(files, **kw):
    """Like _runner, but serves each CODEOWNERS location from ``files``."""
    base = _runner(**kw)

    def run(argv):
        path = argv[-1]
        if "/contents/" in path:
            for loc, answer in files.items():
                if f"/contents/{loc}?" in path:
                    return answer
            return (1, "", "404 Not Found")
        return base(argv)
    return run


def _file(text):
    enc = base64.b64encode(text.encode()).decode()
    return (0, json.dumps({"type": "file", "encoding": "base64", "content": enc,
                           "size": len(text)}), "")


def test_fetch_live_empty_codeowners_still_takes_precedence():
    prot = fetch_live_protection("o/r", "main", runner=_contents_runner({
        ".github/CODEOWNERS": (0, json.dumps({"type": "file", "encoding": "base64",
                                               "content": "", "size": 0}), ""),
        "CODEOWNERS": _file("* @alice\n"),
    }))
    assert prot.codeowners_found is True
    assert prot.codeowners_path == ".github/CODEOWNERS"
    assert prot.codeowners == ""


def test_fetch_live_directory_at_a_location_is_skipped():
    prot = fetch_live_protection("o/r", "main", runner=_contents_runner({
        ".github/CODEOWNERS": (0, json.dumps([{"name": "x"}]), ""),
        "CODEOWNERS": _file("* @alice\n"),
    }))
    assert prot.codeowners_path == "CODEOWNERS"


def test_fetch_live_codeowners_too_large_to_read_is_unknown():
    big = (0, json.dumps({"type": "file", "encoding": "none", "content": "",
                          "size": 2_000_000}), "")
    prot = fetch_live_protection("o/r", "main",
                                 runner=_contents_runner({".github/CODEOWNERS": big}))
    assert prot.codeowners_found is None


def test_fetch_live_a_full_page_of_rules_is_unknown():
    rules = json.dumps([{"type": "deletion"}] * 100)
    prot = fetch_live_protection("o/r", "main", runner=_runner(rules=(0, rules, "")))
    assert prot.required_reviews is None
    assert prot.require_code_owner_review is None


@pytest.mark.parametrize("kw", [
    {"repo": (0, "[]", "")},                                   # not an object
    {"protection": (0, '{"required_pull_request_reviews": 5}', "")},
])
def test_fetch_live_unexpected_shapes_are_could_not_check(kw):
    # A shape GitHub never sends ends in "couldn't check" (exit 2), not a crash.
    with pytest.raises(CouldNotCheck):
        fetch_live_protection("o/r", "main", runner=_runner(**kw))


@pytest.mark.parametrize("kw", [
    {"protection": (0, "[1]", "")},
    {"rules": (0, "{}", "")},
])
def test_fetch_live_unexpected_protection_body_is_unknown(kw):
    prot = fetch_live_protection("o/r", "main", runner=_runner(**kw))
    assert prot.required_reviews is None


def test_fetch_live_unreadable_codeowners_errors_stay_unknown():
    prot = fetch_live_protection(
        "o/r", "main",
        runner=_runner(codeowners="* @alice\n", errors=(1, "", "HTTP 403: Forbidden")))
    assert prot.codeowners_errors is None


def test_fetch_live_branch_not_protected_is_evidence_of_no_classic_rule():
    prot = fetch_live_protection("o/r", "main", runner=_runner())
    assert prot.required_reviews == 0
    assert prot.require_code_owner_review is False


@pytest.mark.parametrize("protection", [
    (1, "", "gh: Forbidden (HTTP 403)"),
    (1, "", "gh: Not Found (HTTP 404)"),  # GitHub may mean "not allowed"
])
def test_fetch_live_unreadable_classic_protection_is_unknown_not_fatal(protection):
    prot = fetch_live_protection("o/r", "main", runner=_runner(protection=protection))
    assert prot.required_reviews is None
    assert prot.require_code_owner_review is None
    assert prot.dismiss_stale_reviews is None


def test_fetch_live_ruleset_can_establish_what_classic_could_not_show():
    rules = json.dumps([{"type": "pull_request", "parameters": {
        "required_approving_review_count": 1, "require_code_owner_review": True,
        "dismiss_stale_reviews_on_push": True}}])
    prot = fetch_live_protection(
        "o/r", "main",
        runner=_runner(protection=(1, "", "gh: Forbidden (HTTP 403)"),
                       rules=(0, rules, "")))
    assert prot.required_reviews == 1
    assert prot.require_code_owner_review is True
    assert prot.dismiss_stale_reviews is True


def test_fetch_live_unreadable_codeowners_location_is_unknown():
    prot = fetch_live_protection(
        "o/r", "main",
        runner=_runner(codeowners="* @alice\n"))
    assert prot.codeowners_found is True
    def run(argv):
        if "/contents/" in argv[-1]:
            return (1, "", "gh: Forbidden (HTTP 403)")
        return _runner()(argv)
    assert fetch_live_protection("o/r", "main", runner=run).codeowners_found is None


def test_fetch_live_unions_classic_and_ruleset():
    classic = json.dumps({"required_pull_request_reviews": {
        "required_approving_review_count": 1, "require_code_owner_reviews": False}})
    rules = json.dumps([{"type": "pull_request", "parameters": {
        "required_approving_review_count": 3, "require_code_owner_review": True,
        "dismiss_stale_reviews_on_push": True}}])
    prot = fetch_live_protection(
        "o/r", "main",
        runner=_runner(protection=(0, classic, ""), rules=(0, rules, ""),
                       codeowners="* @alice"))
    assert prot.required_reviews == 3
    assert prot.require_code_owner_review is True
    assert prot.dismiss_stale_reviews is True


@pytest.mark.parametrize("kw", [
    {"repo": (1, "", "404 Not Found")},
    {"repo": (1, "", "HTTP 401: Bad credentials")},
    {"repo": (1, "", "gh: Server Error (HTTP 500)")},
])
def test_fetch_live_unreadable_repo_is_could_not_check(kw):
    with pytest.raises(CouldNotCheck):
        fetch_live_protection("o/r", "main", runner=_runner(**kw))


def test_fetch_live_propagates_runner_could_not_check():
    def boom(argv):
        raise CouldNotCheck("the `gh` CLI is not installed or not on PATH.")
    with pytest.raises(CouldNotCheck):
        fetch_live_protection("o/r", "main", runner=boom)


def test_default_runner_missing_binary_is_could_not_check():
    from agenraci.adapters.github import _default_runner
    with pytest.raises(CouldNotCheck):
        _default_runner(["this-binary-does-not-exist-xyz", "api", "x"])


def test_protection_from_github_keeps_legacy_owner_list_and_auto_merge():
    prot = protection_from_github(branch="main", repo={"allow_auto_merge": True},
                                  codeowners="* @alice")
    assert prot.code_owners == ["alice"]
    assert prot.allow_auto_merge is True


def test_parse_codeowners_legacy_union_still_works():
    text = "# c\n* @alice\n/docs/ @bob @org/platform  # trailing\n*.md @carol\n"
    assert parse_codeowners(text) == ["alice", "bob", "carol", "org/platform"]


def test_parse_protection_strips_at_signs():
    prot = parse_protection({"code_owners": ["@alice"], "owner_permissions": {"@Alice": True}})
    assert prot.code_owners == ["alice"]
    assert prot.owner_permissions == {"alice": True}


def test_parse_protection_reads_permission_strings_and_bare_error_lines():
    prot = parse_protection({"owner_permissions": {"a": "maintain", "b": "read", "c": None},
                             "codeowners_errors": [3]})
    assert prot.owner_permissions == {"a": True, "b": False}   # c stays unknown
    assert prot.codeowners_errors == [{"line": 3}]


def test_cli_live_mode_uses_the_live_reader(tmp_path, monkeypatch):
    def fake(repo, branch):
        return protection_from_github(
            branch=branch, protection=json.loads(_CLASSIC), codeowners="* @alice\n",
            codeowners_path=".github/CODEOWNERS", codeowners_errors=[],
            owner_permissions={"alice": True}, teams={})
    monkeypatch.setattr("agenraci.cli.fetch_live_protection", fake)
    result = _invoke(_charter(tmp_path, _HUMAN_GATED), "--repo", "o/r", "--format", "json")
    payload = json.loads(result.stdout)
    assert payload["evidence"] == "live"
    # Everything but bypass was read, so this is incomplete (exit 2), never clean.
    assert result.exit_code == 2
    assert {r["code"] for r in payload["actions"][0]["reasons"]} == {"bypass-unchecked"}


def test_cli_live_could_not_check_exit_two(tmp_path, monkeypatch):
    def boom(repo, branch):
        raise CouldNotCheck("the `gh` CLI is not installed or not on PATH.")
    monkeypatch.setattr("agenraci.cli.fetch_live_protection", boom)
    result = _invoke(_charter(tmp_path, _HUMAN_GATED), "--repo", "o/r")
    assert result.exit_code == 2
    assert "could not check" in result.stdout.lower()


# ---- org sweep -------------------------------------------------------------

def _sweep_runner(repo_specs):
    """`gh repo list` plus per-repo `gh api`. spec: "drift" | "error" | "partial"."""
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
            return (0, _CLASSIC, "") if spec == "partial" else _NOT_PROTECTED
        if "/rules/branches/" in path:
            return (0, "[]", "")
        if "/codeowners/errors" in path:
            return (0, '{"errors": []}', "")
        if "/collaborators/" in path:
            return (0, '{"permission": "write"}', "")
        if "/contents/" in path:
            if spec == "partial" and ".github/CODEOWNERS" in path:
                enc = base64.b64encode(b"* @alice\n").decode()
                return (0, json.dumps({"encoding": "base64", "content": enc}), "")
            return (1, "", "404 Not Found")
        return (0, '{"allow_auto_merge": false}', "")  # repos/{repo}

    return run


def test_sweep_org_reports_each_repo_status(tmp_path):
    charter = load_charter(_charter(tmp_path, _HUMAN_GATED))
    report = sweep_org(charter, "o", runner=_sweep_runner(
        {"o/partial": "partial", "o/drifty": "drift", "o/locked": "error"}))
    assert {r.repo: r.status for r in report.results} == {
        "o/partial": "incomplete", "o/drifty": "drift", "o/locked": "could-not-check"}
    assert report.status == "drift" and report.ok is False
    locked = next(r for r in report.results if r.repo == "o/locked")
    assert locked.report is None and "403" in locked.error


def test_sweep_org_incomplete_without_drift(tmp_path):
    charter = load_charter(_charter(tmp_path, _HUMAN_GATED))
    report = sweep_org(charter, "o", runner=_sweep_runner({"o/a": "partial"}))
    assert report.status == "incomplete" and report.ok is True


def test_sweep_org_truncation_is_at_least_incomplete(tmp_path):
    charter = load_charter(_charter(tmp_path, _NO_GATE))
    runner_fn = _sweep_runner({"o/a": "partial", "o/b": "partial"})
    truncated = sweep_org(charter, "o", runner=runner_fn, limit=2)
    assert truncated.truncated is True and truncated.status == "incomplete"
    full = sweep_org(charter, "o", runner=runner_fn, limit=10)
    assert full.truncated is False and full.status == "nothing-to-verify"


def test_sweep_org_listing_failure_is_could_not_check(tmp_path):
    charter = load_charter(_charter(tmp_path, _HUMAN_GATED))

    def boom(argv):
        return (1, "", "HTTP 404: Not Found")
    with pytest.raises(CouldNotCheck):
        sweep_org(charter, "ghost-org", runner=boom)


def test_sweep_org_empty_org(tmp_path):
    charter = load_charter(_charter(tmp_path, _HUMAN_GATED))
    report = sweep_org(charter, "empty", runner=_sweep_runner({}))
    assert report.results == [] and report.status == "nothing-to-verify"


def _report(status, *reasons):
    action = ActionResult("merge", status, ["*"], ["alice"], list(reasons))
    findings = [VerifyFinding("merge", "drift", r.message)
                for r in reasons if r.kind == "drift"]
    return VerifyReport(project="t", branch="main", ok=not findings,
                        findings=findings, unenforceable=[], status=status,
                        evidence="live", actions=[action])


def _fake_sweep(monkeypatch, results, *, status, truncated=False):
    fake = OrgSweepReport(org="o", branch="main", results=results,
                          ok=status != "drift", truncated=truncated, status=status)
    monkeypatch.setattr("agenraci.cli.sweep_org",
                        lambda c, o, branch="main", limit=1000: fake)


def test_cli_org_json(tmp_path, monkeypatch):
    _fake_sweep(monkeypatch, [
        RepoResult("o/a", "verified", report=_report("verified")),
        RepoResult("o/b", "could-not-check", error="HTTP 403: Forbidden"),
    ], status="incomplete")
    result = _invoke(_charter(tmp_path, _HUMAN_GATED), "--org", "o", "--format", "json")
    assert result.exit_code == 2
    payload = json.loads(result.stdout)
    assert payload["status"] == "incomplete"
    assert {r["repo"]: r["status"] for r in payload["repos"]} == {
        "o/a": "verified", "o/b": "could-not-check"}
    assert payload["repos"][0]["actions"][0]["status"] == "verified"


def test_cli_org_human_format_and_exit(tmp_path, monkeypatch):
    drift = Reason("drift", "no-required-review", "the branch requires no approving review.")
    _fake_sweep(monkeypatch, [
        RepoResult("o/a", "verified", report=_report("verified")),
        RepoResult("o/b", "drift", report=_report("drift", drift)),
    ], status="drift")
    result = _invoke(_charter(tmp_path, _HUMAN_GATED), "--org", "o")
    assert result.exit_code == 1
    assert "o/a" in result.stdout and "o/b" in result.stdout
    assert "DRIFT" in result.stdout and "1 drift" in result.stdout


def test_cli_org_allow_incomplete(tmp_path, monkeypatch):
    _fake_sweep(monkeypatch, [RepoResult("o/a", "could-not-check", error="403")],
                status="incomplete")
    charter = _charter(tmp_path, _HUMAN_GATED)
    assert _invoke(charter, "--org", "o").exit_code == 2
    assert _invoke(charter, "--org", "o", "--allow-incomplete").exit_code == 0


def test_cli_org_allow_incomplete_never_hides_could_not_check(tmp_path, monkeypatch):
    # Not one repo could be read: nothing was verified, so this is never a pass.
    _fake_sweep(monkeypatch, [RepoResult("o/a", "could-not-check", error="403")],
                status="could-not-check")
    result = _invoke(_charter(tmp_path, _HUMAN_GATED), "--org", "o",
                     "--allow-incomplete")
    assert result.exit_code == 2
    assert "COULD NOT CHECK" in result.stdout


def test_sweep_org_every_repo_unreadable_is_could_not_check(tmp_path):
    charter = load_charter(_charter(tmp_path, _HUMAN_GATED))
    report = sweep_org(charter, "o", runner=_sweep_runner({"o/a": "error"}))
    assert report.status == "could-not-check"


def test_cli_org_sarif_names_repos(tmp_path, monkeypatch):
    drift = Reason("drift", "no-required-review", "no approving review")
    unenf = Reason("incomplete", "no-human-approver", "agent-only gate")
    _fake_sweep(monkeypatch, [
        RepoResult("o/a", "drift", report=_report("drift", drift)),
        RepoResult("o/b", "incomplete", report=_report("incomplete", unenf)),
        RepoResult("o/c", "could-not-check", error="403"),
    ], status="drift")
    result = _invoke(_charter(tmp_path, _HUMAN_GATED), "--org", "o", "--format", "sarif")
    assert result.exit_code == 1
    res = _sarif(result)["results"]
    assert [(r["ruleId"], r["message"]["text"].split(":")[0]) for r in res] == [
        ("drift", "o/a"), ("unenforceable", "o/b")]


def test_cli_org_threads_limit_into_sweep(tmp_path, monkeypatch):
    captured = {}

    def fake(charter_arg, org, *, branch="main", limit=1000):
        captured.update(org=org, branch=branch, limit=limit)
        return OrgSweepReport(org=org, branch=branch, results=[], ok=True)

    monkeypatch.setattr("agenraci.cli.sweep_org", fake)
    charter = _charter(tmp_path, _HUMAN_GATED)
    assert _invoke(charter, "--org", "acme", "--limit", "42").exit_code == 0
    assert captured == {"org": "acme", "branch": "main", "limit": 42}
    assert _invoke(charter, "--org", "acme").exit_code == 0
    assert captured["limit"] == 1000


def test_cli_org_empty_says_nothing_to_verify(tmp_path, monkeypatch):
    _fake_sweep(monkeypatch, [], status="nothing-to-verify")
    result = _invoke(_charter(tmp_path, _HUMAN_GATED), "--org", "empty")
    assert result.exit_code == 0
    assert "0 repos found" in result.stdout


def test_verify_github_direct_call_with_defaults_is_incomplete(tmp_path):
    """A bare GitHubProtection states nothing, so nothing can pass."""
    charter = load_charter(_charter(tmp_path, _HUMAN_GATED))
    report = verify_github(charter, GitHubProtection(branch="main"))
    assert report.status == "incomplete"
