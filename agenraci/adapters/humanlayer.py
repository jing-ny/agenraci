"""HumanLayer adapter — STUB for v0.1.

Planned (v0.2): emit HumanLayer-style approval-routing config from each action's
gate (approver, on_timeout, break_glass). For now this returns a placeholder so
``agenraci compile --target humanlayer`` is wired end to end.
"""

from __future__ import annotations

import json

from ..schema import Charter


def compile(charter: Charter) -> str:  # noqa: A001 - mirror CLI "compile" verb
    """Return a placeholder compilation result for the HumanLayer target."""
    gated = [name for name, a in charter.actions.items() if a.gate is not None]
    payload = {
        "_agenraci_adapter": "humanlayer",
        "_status": "STUB — real config emission lands in v0.2",
        "project": charter.project,
        "gated_actions": gated,
    }
    return json.dumps(payload, indent=2)
