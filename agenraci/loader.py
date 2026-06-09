"""Load a ``charter.yaml`` into a :class:`~agenraci.schema.Charter`."""

from __future__ import annotations

from pathlib import Path

import yaml

from .schema import Charter


def load_charter_str(text: str) -> Charter:
    """Parse a charter from a YAML string."""
    data = yaml.safe_load(text) or {}
    return Charter.model_validate(data)


def load_charter(path: str | Path) -> Charter:
    """Parse a charter from a YAML file path."""
    return load_charter_str(Path(path).read_text())
