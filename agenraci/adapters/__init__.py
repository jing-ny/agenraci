"""Adapters compile a validated charter into runtime config for existing tools.

v0.1 ships **stubs only** — the real emit logic lands in later versions
(HumanLayer in v0.2, LangGraph in v0.3). AgenRACI sits *above* these tools and
emits config *for* them; it never runs agents or does orchestration itself.
"""

from . import humanlayer, langgraph

TARGETS = {
    "humanlayer": humanlayer.compile,
    "langgraph": langgraph.compile,
}

__all__ = ["TARGETS", "humanlayer", "langgraph"]
