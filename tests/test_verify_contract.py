"""The examples in docs/verification-contract.md §7, against the comparison core.

These need no network and no CLI: each builds a charter and the observed
GitHub evidence directly, then checks the status verify assigns (#79).
"""

import yaml

from agenraci.adapters.github import (
    GitHubProtection,
    TeamFacts,
    compile,
    parse_protection,
    protection_from_github,
    verify_github,
)
from agenraci.schema import Charter


def _charter(*, approver="owner", accountable="owner", github="{paths: ['*']}",
             extra_actions="", members=None):
    members = members or (
        "  - { name: alice, type: human, role: owner }\n"
        "  - { name: carol, type: human, role: other }\n"
        "  - { name: bob, type: human, role: dev }\n"
        "  - { name: botty, type: agent, role: bots }\n"
    )
    body = (
        "project: t\n"
        "roles: [owner, dev, other, bots]\n"
        "members:\n" + members +
        "actions:\n"
        "  merge_to_main:\n"
        "    responsible: dev\n"
        f"    accountable: {accountable}\n"
        f"    gate: {{ approver: {approver}, on_timeout: block, "
        "break_glass: { who: owner, condition: sev1 } }\n"
        f"    github: {github}\n" + extra_actions
    )
    return Charter.model_validate(yaml.safe_load(body))


def _prot(codeowners="* @alice\n", **kw):
    """The contract's default: everything required, readable, and no bypass."""
    base = dict(
        branch="main", required_reviews=1, require_code_owner_review=True,
        dismiss_stale_reviews=True, codeowners=codeowners,
        codeowners_found=codeowners is not None,
        codeowners_path=".github/CODEOWNERS", codeowners_errors=[],
        owner_permissions={"alice": True, "bob": True, "carol": True},
        teams={}, enforce_admins=True, bypass_actors=[],
    )
    base.update(kw)
    return GitHubProtection(**base)


def _action(report, name="merge_to_main"):
    return next(a for a in report.actions if a.action == name)


def _codes(report, name="merge_to_main"):
    return {r.code for r in _action(report, name).reasons}


def test_example_1_single_eligible_owner_is_verified():
    report = verify_github(_charter(), _prot("* @alice\n"))
    assert report.status == "verified"
    assert _action(report).status == "verified"
    assert _action(report).eligible_approvers == ["alice"]
    assert report.ok is True and report.findings == []


def test_example_2_later_rule_wins():
    report = verify_github(_charter(), _prot("* @alice\n* @bob\n"))
    assert report.status == "drift"
    assert "ineligible-owner" in _codes(report)
    assert any("@bob" in f.message for f in report.findings)


def test_example_3_co_listed_ineligible_owner_is_drift():
    """Any one listed owner can approve, so more owners is never stronger."""
    report = verify_github(_charter(), _prot("* @alice @bob\n"))
    assert report.status == "drift"
    assert "ineligible-owner" in _codes(report)


def test_example_4_ownerless_override_is_drift():
    report = verify_github(_charter(), _prot("* @alice\n/docs/\n"))
    assert report.status == "drift"
    assert "no-owner" in _codes(report)
    assert any("docs/" in f.message for f in report.findings)


def test_example_5_designated_approver_not_accountable_owner():
    report = verify_github(_charter(accountable="other"), _prot("* @alice\n"))
    assert report.status == "verified"


def test_example_6_accountable_owner_is_not_an_eligible_approver():
    report = verify_github(_charter(accountable="other"), _prot("* @carol\n"))
    assert report.status == "drift"
    assert any("@carol" in f.message for f in report.findings)


def test_example_7_unreadable_team_is_incomplete():
    report = verify_github(_charter(), _prot("* @alice @org/release\n"))
    assert report.status == "incomplete"
    assert "unresolved-owner" in _codes(report)


def test_team_with_only_eligible_members_is_verified():
    prot = _prot("* @alice @org/release\n",
                 teams={"org/release": TeamFacts(members=["alice"], write=True)})
    assert verify_github(_charter(), prot).status == "verified"


def test_team_with_an_ineligible_member_is_drift():
    prot = _prot("* @alice @org/release\n",
                 teams={"org/release": TeamFacts(members=["alice", "bob"], write=True)})
    report = verify_github(_charter(), prot)
    assert report.status == "drift"
    assert any("@bob" in f.message for f in report.findings)


def test_email_owner_is_incomplete():
    report = verify_github(_charter(), _prot("* @alice alice@example.com\n"))
    assert report.status == "incomplete"
    assert "unresolved-owner" in _codes(report)


def test_example_8_agent_only_approver_is_incomplete():
    report = verify_github(_charter(approver="bots"), _prot("* @alice\n"))
    assert report.status == "incomplete"
    assert "no-human-approver" in _codes(report)
    assert [f.target for f in report.unenforceable] == ["merge_to_main"]
    assert report.ok is True  # not drift: GitHub can't express the gate


def test_example_9_auto_merge_is_not_drift():
    assert verify_github(_charter(), _prot(allow_auto_merge=True)).status == "verified"


def test_example_10_no_required_review_is_drift_with_auto_merge():
    report = verify_github(_charter(), _prot(required_reviews=0, allow_auto_merge=True))
    assert report.status == "drift"
    assert "no-required-review" in _codes(report)


def test_code_owner_review_off_is_drift():
    report = verify_github(_charter(), _prot(require_code_owner_review=False))
    assert "no-code-owner-review" in _codes(report)


def test_example_14_missing_bypass_evidence_is_incomplete():
    report = verify_github(_charter(), _prot(enforce_admins=None, bypass_actors=None))
    assert report.status == "incomplete"
    assert "bypass-unchecked" in _codes(report)


def test_bypass_actors_are_not_judged_yet():
    report = verify_github(_charter(), _prot(bypass_actors=[{"actor_type": "Team"}]))
    assert report.status == "incomplete"
    assert "bypass-not-judged" in _codes(report)


def test_example_15_unmapped_action_is_incomplete():
    report = verify_github(_charter(github="null"), _prot())
    assert report.status == "incomplete"
    assert _codes(report) == {"no-github-mapping"}


def test_example_16_github_none_is_not_applicable():
    deploy = ("  deploy_prod:\n"
              "    responsible: dev\n"
              "    accountable: owner\n"
              "    gate: { approver: owner, on_timeout: block, "
              "break_glass: { who: owner, condition: sev1 } }\n"
              "    github: none\n")
    report = verify_github(_charter(extra_actions=deploy), _prot())
    assert _action(report, "deploy_prod").status == "not-applicable"
    assert report.status == "verified"  # not-applicable never changes the result


def test_every_action_not_applicable_is_nothing_to_verify():
    report = verify_github(_charter(github="none"), _prot())
    assert report.status == "nothing-to-verify"
    assert report.note


def test_example_17_owner_without_write_access_is_drift():
    report = verify_github(_charter(), _prot(owner_permissions={"alice": False}))
    assert report.status == "drift"
    assert "no-effective-owner" in _codes(report)


def test_ineligible_owner_without_write_access_is_ignored_like_github():
    prot = _prot("* @alice @bob\n", owner_permissions={"alice": True, "bob": False})
    assert verify_github(_charter(), prot).status == "verified"


def test_unread_owner_permission_is_incomplete():
    report = verify_github(_charter(), _prot(owner_permissions=None))
    assert report.status == "incomplete"
    assert "unresolved-owner" in _codes(report)


def test_example_18_stale_review_dismissal_off_is_drift():
    report = verify_github(_charter(), _prot(dismiss_stale_reviews=False))
    assert "no-stale-dismissal" in _codes(report)


def test_no_codeowners_file_is_drift():
    report = verify_github(_charter(), _prot(None, codeowners_found=False))
    assert "no-codeowners-file" in _codes(report)


def test_codeowners_file_owned_by_ineligible_owner_is_drift():
    """Whoever owns CODEOWNERS can approve a change to who owns everything."""
    charter = _charter(github="{paths: ['src/**']}")
    prot = _prot("* @bob\n/src/ @alice\n")
    report = verify_github(charter, prot)
    assert report.status == "drift"
    assert any("CODEOWNERS file" in f.message for f in report.findings)
    fixed = _prot("* @bob\n/src/ @alice\n/.github/CODEOWNERS @alice\n")
    assert verify_github(charter, fixed).status == "verified"


def test_a_location_github_reads_first_must_be_owned_too():
    """With CODEOWNERS at the root, adding .github/CODEOWNERS would replace it."""
    charter = _charter(github="{paths: ['src/**']}")
    prot = _prot("* @bob\n/src/ @alice\n/CODEOWNERS @alice\n",
                 codeowners_path="CODEOWNERS")
    report = verify_github(charter, prot)
    assert report.status == "drift"
    assert any(".github/CODEOWNERS" in f.message and "instead of" in f.message
               for f in report.findings)
    fixed = _prot("* @bob\n/src/ @alice\n/CODEOWNERS @alice\n/.github/ @alice\n",
                  codeowners_path="CODEOWNERS")
    assert verify_github(charter, fixed).status == "verified"


def test_codeowners_error_on_the_rule_owning_the_file_is_incomplete():
    charter = _charter(github="{paths: ['src/**']}")
    prot = _prot("/src/ @alice\n/.github/CODEOWNERS @alice\n",
                 codeowners_errors=[{"line": 2, "message": "Unknown owner"}])
    report = verify_github(charter, prot)
    assert report.status == "incomplete"
    assert "codeowners-errors" in _codes(report)


def test_scope_limits_which_rules_matter():
    charter = _charter(github="{paths: ['src/**']}")
    prot = _prot("* @alice\n/docs/ @bob\n")
    assert verify_github(charter, prot).status == "verified"


def test_new_files_are_judged_too():
    """A rule that would take a NEW src/*.md file away from the approvers is drift."""
    charter = _charter(github="{paths: ['src/**']}")
    report = verify_github(charter, _prot("* @alice\n*.md @bob\n"))
    assert report.status == "drift"
    assert any("src/" in f.message and ".md" in f.message for f in report.findings)


def test_path_no_rule_covers_is_drift():
    charter = _charter(github="{paths: ['src/**']}")
    report = verify_github(charter, _prot("/docs/ @alice\n/.github/CODEOWNERS @alice\n"))
    assert "no-owner" in _codes(report)


def test_codeowners_error_on_a_relevant_line_is_incomplete():
    prot = _prot(codeowners_errors=[{"line": 1, "message": "Unknown owner"}])
    report = verify_github(_charter(), prot)
    assert report.status == "incomplete"
    assert "codeowners-errors" in _codes(report)


def test_unsupported_codeowners_pattern_is_incomplete():
    report = verify_github(_charter(), _prot("* @alice\n[ab].md @bob\n"))
    assert report.status == "incomplete"
    assert "unsupported-pattern" in _codes(report)


def test_member_github_handle_is_used_as_the_login():
    members = ("  - { name: Alice Smith, type: human, role: owner, github: asmith }\n"
               "  - { name: bob, type: human, role: dev }\n")
    charter = _charter(members=members)
    prot = _prot("* @asmith\n", owner_permissions={"asmith": True})
    report = verify_github(charter, prot)
    assert report.status == "verified"
    assert _action(report).eligible_approvers == ["asmith"]


def test_logins_compare_case_insensitively():
    prot = _prot("* @Alice\n", owner_permissions={"alice": True})
    assert verify_github(_charter(), prot).status == "verified"


def test_drift_beats_incomplete():
    prot = _prot("* @alice @bob\n", dismiss_stale_reviews=None)
    report = verify_github(_charter(), prot)
    assert report.status == "drift"
    assert {"ineligible-owner", "evidence-missing"} <= _codes(report)


# ---- offline export --------------------------------------------------------

_FULL_EXPORT = {
    "branch": "main", "required_reviews": 1, "require_code_owner_review": True,
    "dismiss_stale_reviews": True, "codeowners": "* @alice\n",
    "codeowners_path": ".github/CODEOWNERS", "codeowners_errors": [],
    "owner_permissions": {"alice": "write"}, "enforce_admins": True,
    "bypass_actors": [], "allow_auto_merge": True,
}


def test_full_offline_export_can_verify():
    prot = parse_protection(dict(_FULL_EXPORT))
    assert prot.evidence == "snapshot"
    assert verify_github(_charter(), prot).status == "verified"


def test_absent_export_fields_are_missing_evidence_not_defaults():
    for key in ("required_reviews", "require_code_owner_review",
                "dismiss_stale_reviews", "codeowners", "codeowners_path",
                "codeowners_errors", "owner_permissions", "enforce_admins",
                "bypass_actors"):
        data = {k: v for k, v in _FULL_EXPORT.items() if k != key}
        report = verify_github(_charter(), parse_protection(data))
        assert report.status == "incomplete", key


def test_legacy_export_with_owner_names_only_is_incomplete():
    data = {"branch": "main", "required_reviews": 1, "require_code_owner_review": True,
            "code_owners": ["alice"], "allow_auto_merge": False}
    report = verify_github(_charter(), parse_protection(data))
    assert report.status == "incomplete"
    assert any("raw `codeowners`" in r.message for r in _action(report).reasons)


def test_export_null_codeowners_means_no_file():
    data = dict(_FULL_EXPORT, codeowners=None)
    report = verify_github(_charter(), parse_protection(data))
    assert "no-codeowners-file" in _codes(report)


def test_export_null_enforce_admins_means_no_classic_protection():
    data = dict(_FULL_EXPORT, enforce_admins=None)
    assert verify_github(_charter(), parse_protection(data)).status == "verified"


# ---- live evidence shape ---------------------------------------------------

def test_live_protection_never_claims_bypass_evidence_yet():
    classic = {"required_pull_request_reviews": {
        "required_approving_review_count": 1, "require_code_owner_reviews": True,
        "dismiss_stale_reviews": True}}
    prot = protection_from_github(
        branch="main", protection=classic, codeowners="* @alice\n",
        codeowners_path=".github/CODEOWNERS", codeowners_errors=[],
        owner_permissions={"alice": True}, teams={})
    assert prot.evidence == "live"
    report = verify_github(_charter(), prot)
    assert report.status == "incomplete"
    assert _codes(report) == {"bypass-unchecked"}


# ---- compile stays consistent with verify -----------------------------------

def test_compile_scaffold_round_trips_through_verify():
    """compile's CODEOWNERS + protection, read back, leave only bypass unchecked."""
    import json

    charter = _charter(github="{paths: ['src/**', 'docs/']}")
    out = compile(charter)
    body = json.loads("\n".join(
        ln for ln in out.split("# --- BEGIN protection.json ---")[1]
        .split("# --- END protection.json ---")[0].splitlines()
        if not ln.startswith("#")))
    co_section = out.split("# ── CODEOWNERS")[1].split("# ── Branch protection")[0]
    codeowners = "\n".join(ln for ln in co_section.splitlines()
                           if ln and not ln.startswith("#"))
    assert "src/**    @alice" in codeowners
    assert "/.github/CODEOWNERS    @alice" in codeowners
    prot = protection_from_github(
        branch="main", protection=body, codeowners=codeowners,
        codeowners_path=".github/CODEOWNERS", codeowners_errors=[],
        owner_permissions={"alice": True}, teams={})
    report = verify_github(charter, prot)
    assert _codes(report) == {"bypass-unchecked"}


def test_compile_does_not_scaffold_rules_for_agent_only_approvers():
    out = compile(_charter(approver="bots"))
    assert "GitHub cannot enforce this gate" in out
    assert "*    @" not in out


def test_compile_asks_for_a_mapping_when_none_is_declared():
    out = compile(_charter(github="null"))
    assert "no `github` key" in out


def test_compile_warns_when_actions_with_different_approvers_overlap():
    other = ("  release:\n"
             "    responsible: dev\n"
             "    accountable: other\n"
             "    gate: { approver: other, on_timeout: block, "
             "break_glass: { who: owner, condition: sev1 } }\n"
             "    github: { paths: ['docs/'] }\n")
    out = compile(_charter(extra_actions=other))
    assert "overlap" in out


def test_compile_skips_github_none_actions_in_both_sections():
    out = compile(_charter(github="none"))
    assert "`github: none`, not a repo change" in out
    assert "Require a pull request" not in out
    assert "nothing to own" in out


def test_export_codeowners_errors_may_be_bare_line_numbers():
    prot = parse_protection({"codeowners_errors": [3]})
    assert prot.codeowners_errors == [{"line": 3}]
