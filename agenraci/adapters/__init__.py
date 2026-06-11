"""Adapters compile a validated charter into config for existing tools.

The ``github`` target is **real** — it emits CODEOWNERS + branch-protection
guidance from the charter. The ``humanlayer`` and ``langgraph`` targets are
still **stubs**; their real emit logic lands in later versions (HumanLayer in
v0.2, LangGraph in v0.3). AgenRACI sits *above* these tools and emits config
*for* them; it never runs agents or does orchestration itself, and even the
GitHub output is static config a human applies — not runtime enforcement.
"""

from . import github, humanlayer, langgraph

TARGETS = {
    "github": github.compile,
    "humanlayer": humanlayer.compile,
    "langgraph": langgraph.compile,
}

# Targets whose emit is still a placeholder (the CLI labels these "(STUB)").
STUB_TARGETS = {"humanlayer", "langgraph"}

__all__ = ["TARGETS", "STUB_TARGETS", "github", "humanlayer", "langgraph"]
