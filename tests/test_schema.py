"""Tests for the published JSON Schema and the `agenraci schema` command."""

import json
from pathlib import Path

from typer.testing import CliRunner

from agenraci.cli import app
from agenraci.schema import Charter

runner = CliRunner()

_SCHEMA_FILE = Path(__file__).resolve().parent.parent / "charter.schema.json"


def test_schema_command_emits_valid_json_schema():
    result = runner.invoke(app, ["schema"])
    assert result.exit_code == 0
    parsed = json.loads(result.stdout)
    # A JSON Schema for an object model has properties (e.g. `project`).
    assert "properties" in parsed
    assert "project" in parsed["properties"]


def test_committed_schema_is_up_to_date():
    """The checked-in charter.schema.json must match the live model.

    Editors fetch this file by URL for autocomplete, so it can't drift from what
    `agenraci validate` actually accepts. If this fails, regenerate it:
        agenraci schema > charter.schema.json

    Note: this exact-equality check is coupled to pydantic's schema emission, so
    a pydantic upgrade that reorders/renames `$defs` can red the build until the
    file is regenerated. That's intended — a deliberate regen beats silent drift.
    """
    committed = json.loads(_SCHEMA_FILE.read_text(encoding="utf-8"))
    assert committed == Charter.model_json_schema(), (
        "charter.schema.json is stale — run `agenraci schema > charter.schema.json`"
    )
