"""Adapters compile a validated charter into config for existing tools.

The ``github`` target (CODEOWNERS + branch-protection guidance) and the
``claude`` target (``.claude/agents/`` definitions + a CLAUDE.md governance
snippet) are **real**. The ``humanlayer`` and ``langgraph`` targets are still
**stubs**; their real emit logic lands in later versions (HumanLayer in v0.2,
LangGraph in v0.3). AgenRACI sits *above* these tools and emits config *for*
them; it never runs agents or does orchestration itself — even the real
targets generate static config a human reviews and applies, not runtime
enforcement.
"""

from . import claude_code, github, humanlayer, langgraph

TARGETS = {
    "claude": claude_code.compile,
    "github": github.compile,
    "humanlayer": humanlayer.compile,
    "langgraph": langgraph.compile,
}

# Targets whose emit is still a placeholder (the CLI labels these "(STUB)").
STUB_TARGETS = {"humanlayer", "langgraph"}

__all__ = ["TARGETS", "STUB_TARGETS", "claude_code", "github", "humanlayer", "langgraph"]
