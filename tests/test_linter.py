"""Linter tests, driven by file-based charters under tests/fixtures/.

`good_minimal.yaml` passes every active rule (R1-R6); each `bad_*.yaml` is that
same charter with the smallest change that trips a single rule and nothing else.
R2 and R4 each have two independent arms, so each gets two fixtures:
R2 = undeclared-capability + dead-permission, R4 = missing break_glass + missing
suggestion_route. R6 gets a self-escalation and a two-role escalation cycle, plus
`good_escalation.yaml` (a legal escalation chain) to guard against false positives.
The Sprout example is also asserted clean.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from agenraci.linter import lint
from agenraci.loader import load_charter
from agenraci.schema import Charter

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = Path(__file__).resolve().parent / "fixtures"
SPROUT = ROOT / "examples" / "sprout" / "charter.yaml"


def _rules_tripped(fixture: str) -> set[str]:
    """The set of rule IDs the named fixture charter trips."""
    charter = load_charter(FIXTURES / fixture)
    return {e.rule for e in lint(charter)}


# --------------------------------------------------------------------------- #
# Known-good charters pass everything.
# --------------------------------------------------------------------------- #
def test_good_minimal_passes_all_active_rules():
    assert _rules_tripped("good_minimal.yaml") == set()


def test_good_escalation_chain_passes():
    # Uses escalate_to, but the edges form a terminating chain, not a loop, so
    # R6 must not false-positive on it.
    assert _rules_tripped("good_escalation.yaml") == set()


def test_sprout_passes_all_active_rules():
    errors = lint(load_charter(SPROUT))
    assert errors == [], "\n".join(str(e) for e in errors)


_EXAMPLE_CHARTERS = sorted((ROOT / "examples").glob("*/charter.yaml"))


@pytest.mark.parametrize("charter_path", _EXAMPLE_CHARTERS, ids=lambda p: p.parent.name)
def test_every_shipped_example_validates_clean(charter_path):
    errors = lint(load_charter(charter_path))
    assert errors == [], "\n".join(str(e) for e in errors)


# --------------------------------------------------------------------------- #
# Each known-bad charter trips exactly one rule.
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize(
    "fixture, rule",
    [
        ("bad_r1.yaml", "R1"),       # two accountable roles
        ("bad_r2.yaml", "R2"),       # action touches an undeclared capability
        ("bad_r2_dead.yaml", "R2"),  # a declared capability no action touches
        ("bad_r3.yaml", "R3"),       # a role grants and denies the same capability
        ("bad_r4.yaml", "R4"),       # a gate has no break_glass path
        ("bad_r4_route.yaml", "R4"), # consulted-but-denied role has no route
        ("bad_r5.yaml", "R5"),       # proceed_if_low_risk on a non-low_risk action
        ("bad_r6_self.yaml", "R6"),  # a gate escalates to its own approver
        ("bad_r6_cycle.yaml", "R6"), # two gates escalate into a loop
    ],
)
def test_bad_fixture_trips_exactly_its_rule(fixture: str, rule: str):
    assert _rules_tripped(fixture) == {rule}


# --------------------------------------------------------------------------- #
# schema-level referential integrity (distinct from linter rules)
# --------------------------------------------------------------------------- #
def test_undeclared_role_reference_is_a_schema_error():
    data = yaml.safe_load((FIXTURES / "good_minimal.yaml").read_text())
    data["actions"]["do_work"]["accountable"] = "ghost"  # not a declared role
    with pytest.raises(Exception):
        Charter.model_validate(data)
