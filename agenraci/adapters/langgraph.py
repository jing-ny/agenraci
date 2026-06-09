"""LangGraph adapter — STUB for v0.1.

Planned (v0.3): emit LangGraph interrupt/checkpoint nodes from each gated action
so approvals become durable pause/resume points in the graph. For now this
returns a placeholder so ``agenraci compile --target langgraph`` is wired end to
end.
"""

from __future__ import annotations

import json

from ..schema import Charter


def compile(charter: Charter) -> str:  # noqa: A001 - mirror CLI "compile" verb
    """Return a placeholder compilation result for the LangGraph target."""
    interrupts = [name for name, a in charter.actions.items() if a.gate is not None]
    payload = {
        "_agenraci_adapter": "langgraph",
        "_status": "STUB — real config emission lands in v0.3",
        "project": charter.project,
        "interrupt_nodes": interrupts,
    }
    return json.dumps(payload, indent=2)
