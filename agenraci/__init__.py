"""AgenRACI — an operating constitution for humans and AI agents.

AgenRACI is a framework-agnostic specification + linter + adapters for declaring
the operating constitution of a mixed human + AI-agent team. See SPEC.md.
"""

from .schema import (
    Action,
    BreakGlass,
    CapabilitySet,
    Charter,
    Gate,
    Member,
    Role,
    SuggestionRoute,
)
from .linter import LintError, RULES, lint

__version__ = "0.1.0"

__all__ = [
    "Action",
    "BreakGlass",
    "CapabilitySet",
    "Charter",
    "Gate",
    "Member",
    "Role",
    "SuggestionRoute",
    "LintError",
    "RULES",
    "lint",
    "__version__",
]
