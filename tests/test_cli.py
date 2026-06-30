"""CLI-level tests for the agenraci command."""

import json
from importlib.metadata import version as pkg_version
from pathlib import Path

from typer.testing import CliRunner

from agenraci.cli import app

runner = CliRunner()


def test_version_flag_prints_version_and_exits_zero():
    result = runner.invoke(app, ["--version"])
    assert result.exit_code == 0
    assert result.stdout.strip() == f"agenraci {pkg_version('agenraci')}"


def test_short_version_flag():
    result = runner.invoke(app, ["-V"])
    assert result.exit_code == 0
    assert result.stdout.startswith("agenraci ")


def test_init_writes_a_charter_that_validates(tmp_path, monkeypatch):
    """`init` writes a starter charter, and that charter passes `validate`."""
    monkeypatch.chdir(tmp_path)

    init = runner.invoke(app, ["init"])
    assert init.exit_code == 0
    assert (tmp_path / "charter.yaml").exists()

    check = runner.invoke(app, ["validate", "charter.yaml"])
    assert check.exit_code == 0
    assert "PASS" in check.stdout


def test_init_stdout_prints_template_without_writing_file(tmp_path, monkeypatch):
    """`init --stdout` prints the starter charter and skips filesystem writes."""
    monkeypatch.chdir(tmp_path)

    result = runner.invoke(app, ["init", "--stdout"])
    assert result.exit_code == 0
    assert "project:" in result.stdout
    assert not (tmp_path / "charter.yaml").exists()


def test_validate_accepts_multiple_charters(tmp_path, monkeypatch):
    """`validate` checks every path given and exits non-zero if any fails."""
    monkeypatch.chdir(tmp_path)
    runner.invoke(app, ["init", "good.yaml"])
    (tmp_path / "bad.yaml").write_text(
        "project: broken\n"
        "roles: [a, b]\n"
        "actions:\n"
        "  x: { responsible: a, accountable: [a, b] }\n",  # 2 accountable -> R1 fails
        encoding="utf-8",
    )

    result = runner.invoke(app, ["validate", "good.yaml", "bad.yaml"])
    assert result.exit_code == 1
    # Both charters appear in the combined report.
    assert "good.yaml" in result.stdout
    assert "bad.yaml" in result.stdout


def test_validate_explain_prints_plain_language_fix(tmp_path, monkeypatch):
    """`validate --explain` adds a plain-language fix line under a failing rule."""
    monkeypatch.chdir(tmp_path)
    (tmp_path / "bad.yaml").write_text(
        "project: broken\n"
        "roles: [a, b]\n"
        "actions:\n"
        "  x: { responsible: a, accountable: [a, b] }\n",  # R1 fails
        encoding="utf-8",
    )

    plain = runner.invoke(app, ["validate", "bad.yaml"])
    explained = runner.invoke(app, ["validate", "--explain", "bad.yaml"])

    assert plain.exit_code == 1 and explained.exit_code == 1
    # The explanation appears only with --explain.
    assert "exactly one accountable role" in explained.stdout
    assert "exactly one accountable role" not in plain.stdout


def test_validate_github_format_emits_annotations(tmp_path, monkeypatch):
    """`--format github` emits ::error annotations on failure; human mode does not."""
    monkeypatch.chdir(tmp_path)
    (tmp_path / "bad.yaml").write_text(
        "project: broken\n"
        "roles: [a, b]\n"
        "actions:\n"
        "  x: { responsible: a, accountable: [a, b] }\n",  # R1 fails
        encoding="utf-8",
    )

    gh = runner.invoke(app, ["validate", "--format", "github", "bad.yaml"])
    assert gh.exit_code == 1
    assert "::error file=bad.yaml" in gh.stdout
    assert "AgenRACI R1" in gh.stdout

    human = runner.invoke(app, ["validate", "bad.yaml"])
    assert "::error" not in human.stdout  # annotations are opt-in

    bad_fmt = runner.invoke(app, ["validate", "--format", "xml", "bad.yaml"])
    assert bad_fmt.exit_code == 2


def test_validate_json_format_clean_charter(tmp_path, monkeypatch):
    """`--format json` emits one parseable object with every rule passing."""
    monkeypatch.chdir(tmp_path)
    runner.invoke(app, ["init", "good.yaml"])

    result = runner.invoke(app, ["validate", "--format", "json", "good.yaml"])
    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["charter"] == "good.yaml"
    assert payload["ok"] is True
    assert payload["error"] is None
    # All six rules R1-R6 are reported, each passing with no findings.
    assert [r["id"] for r in payload["rules"]] == ["R1", "R2", "R3", "R4", "R5", "R6"]
    assert all(r["passed"] and r["findings"] == [] for r in payload["rules"])
    # The human report is suppressed under json.
    assert "PASS" not in result.stdout


def test_validate_json_format_reports_failing_rule(tmp_path, monkeypatch):
    """A failing rule surfaces as passed=false with structured findings."""
    monkeypatch.chdir(tmp_path)
    (tmp_path / "bad.yaml").write_text(
        "project: broken\n"
        "roles: [a, b]\n"
        "actions:\n"
        "  x: { responsible: a, accountable: [a, b] }\n",  # 2 accountable -> R1 fails
        encoding="utf-8",
    )

    result = runner.invoke(app, ["validate", "--format", "json", "bad.yaml"])
    assert result.exit_code == 1
    payload = json.loads(result.stdout)
    assert payload["ok"] is False
    r1 = next(r for r in payload["rules"] if r["id"] == "R1")
    assert r1["passed"] is False
    assert r1["findings"][0]["target"] == "x"
    assert "accountable" in r1["findings"][0]["message"]


def test_validate_json_format_explain_adds_explanation_to_findings(tmp_path, monkeypatch):
    """`--explain --format json` carries the same plain-language fix per finding."""
    monkeypatch.chdir(tmp_path)
    (tmp_path / "bad.yaml").write_text(
        "project: broken\n"
        "roles: [a, b]\n"
        "actions:\n"
        "  x: { responsible: a, accountable: [a, b] }\n",
        encoding="utf-8",
    )

    result = runner.invoke(app, ["validate", "--explain", "--format", "json", "bad.yaml"])
    assert result.exit_code == 1
    payload = json.loads(result.stdout)
    r1 = next(r for r in payload["rules"] if r["id"] == "R1")
    finding = r1["findings"][0]
    assert "explanation" in finding
    assert "exactly one accountable role" in finding["explanation"]


def test_validate_json_format_is_json_lines_for_multiple(tmp_path, monkeypatch):
    """Several charters yield one JSON object per line (JSON Lines), no separators."""
    monkeypatch.chdir(tmp_path)
    runner.invoke(app, ["init", "good.yaml"])
    (tmp_path / "bad.yaml").write_text(
        "project: broken\n"
        "roles: [a, b]\n"
        "actions:\n"
        "  x: { responsible: a, accountable: [a, b] }\n",
        encoding="utf-8",
    )

    result = runner.invoke(
        app, ["validate", "--format", "json", "good.yaml", "bad.yaml"]
    )
    assert result.exit_code == 1
    lines = [ln for ln in result.stdout.splitlines() if ln.strip()]
    objs = [json.loads(ln) for ln in lines]  # every line parses on its own
    assert len(objs) == 2
    assert objs[0]["ok"] is True and objs[1]["ok"] is False
    assert "─" not in result.stdout  # no human separator leaks into json


def test_validate_json_format_reports_schema_error(tmp_path, monkeypatch):
    """A charter that doesn't load is still a parseable json object with `error` set."""
    monkeypatch.chdir(tmp_path)
    # `actions` must be a mapping; a scalar is a schema (type) error, not a lint miss.
    (tmp_path / "nope.yaml").write_text(
        "project: x\nroles: [a]\nactions: oops\n", encoding="utf-8"
    )

    result = runner.invoke(app, ["validate", "--format", "json", "nope.yaml"])
    assert result.exit_code == 1
    payload = json.loads(result.stdout)
    assert payload["ok"] is False
    assert payload["error"]  # non-null marker distinguishes load failure from rule failure
    assert payload["rules"] == []
    assert payload["findings"]


def test_validate_sarif_clean_charter(tmp_path, monkeypatch):
    """`--format sarif` emits a valid SARIF 2.1.0 run with no results when clean."""
    monkeypatch.chdir(tmp_path)
    runner.invoke(app, ["init", "good.yaml"])

    result = runner.invoke(app, ["validate", "--format", "sarif", "good.yaml"])
    assert result.exit_code == 0
    doc = json.loads(result.stdout)
    assert doc["version"] == "2.1.0"
    assert len(doc["runs"]) == 1
    driver = doc["runs"][0]["tool"]["driver"]
    assert driver["name"] == "AgenRACI"
    # R1-R6 are all described as rules; no findings means no results.
    assert {r["id"] for r in driver["rules"]} >= {"R1", "R2", "R3", "R4", "R5", "R6"}
    assert doc["runs"][0]["results"] == []


def test_validate_sarif_reports_finding(tmp_path, monkeypatch):
    """A failing rule becomes a SARIF result pinned to the charter file; exit 1."""
    monkeypatch.chdir(tmp_path)
    (tmp_path / "bad.yaml").write_text(
        "project: broken\n"
        "roles: [a, b]\n"
        "actions:\n"
        "  x: { responsible: a, accountable: [a, b] }\n",  # R1 fails
        encoding="utf-8",
    )

    result = runner.invoke(app, ["validate", "--format", "sarif", "bad.yaml"])
    assert result.exit_code == 1
    res = json.loads(result.stdout)["runs"][0]["results"]
    assert len(res) == 1
    assert res[0]["ruleId"] == "R1"
    assert res[0]["level"] == "error"
    uri = res[0]["locations"][0]["physicalLocation"]["artifactLocation"]["uri"]
    assert uri == "bad.yaml"


def test_validate_sarif_aggregates_multiple_into_one_document(tmp_path, monkeypatch):
    """Several charters fold into ONE SARIF run (code-scanning uploads one file)."""
    monkeypatch.chdir(tmp_path)
    runner.invoke(app, ["init", "good.yaml"])
    (tmp_path / "bad.yaml").write_text(
        "project: broken\n"
        "roles: [a, b]\n"
        "actions:\n"
        "  x: { responsible: a, accountable: [a, b] }\n",
        encoding="utf-8",
    )

    result = runner.invoke(
        app, ["validate", "--format", "sarif", "good.yaml", "bad.yaml"]
    )
    assert result.exit_code == 1
    doc = json.loads(result.stdout)  # the whole output is a single JSON document
    assert len(doc["runs"]) == 1
    results = doc["runs"][0]["results"]
    # Only the broken charter contributes a result, attributed to its own file.
    assert {r["locations"][0]["physicalLocation"]["artifactLocation"]["uri"]
            for r in results} == {"bad.yaml"}


def test_validate_rejects_duplicate_keys(tmp_path, monkeypatch):
    """A duplicated key must fail loudly, not silently keep the last value.

    Plain ``yaml.safe_load`` would drop the first ``actions:`` block; for a file
    that is a team's source of truth, a vanishing rule is a trust bug.
    """
    monkeypatch.chdir(tmp_path)
    (tmp_path / "dup.yaml").write_text(
        "project: dup\n"
        "roles: [a]\n"
        "actions:\n"
        "  x: { responsible: a, accountable: a }\n"
        "actions:\n"  # second 'actions' key — would silently win under safe_load
        "  y: { responsible: a, accountable: a }\n",
        encoding="utf-8",
    )

    result = runner.invoke(app, ["validate", "dup.yaml"])
    assert result.exit_code == 1
    assert "duplicate key" in result.stdout
    assert "actions" in result.stdout


def test_validate_allows_yaml_merge_keys(tmp_path, monkeypatch):
    """The strict loader must not break legitimate YAML merge keys (`<<: *anchor`).

    Rejecting duplicate keys is right; rejecting a charter that DRYs repeated
    RACI blocks with an anchor is not.
    """
    monkeypatch.chdir(tmp_path)
    (tmp_path / "merge.yaml").write_text(
        "project: merge\n"
        "roles: [owner]\n"
        "actions:\n"
        "  x: &base { responsible: owner, accountable: owner }\n"
        "  y:\n"
        "    <<: *base\n",
        encoding="utf-8",
    )

    result = runner.invoke(app, ["validate", "merge.yaml"])
    assert result.exit_code == 0, result.stdout
    assert "PASS" in result.stdout


def test_init_custom_path_creates_parent_dirs(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    result = runner.invoke(app, ["init", "team/constitution.yaml"])
    assert result.exit_code == 0
    assert (tmp_path / "team" / "constitution.yaml").exists()


def test_init_refuses_to_overwrite_without_force(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    target = tmp_path / "charter.yaml"
    target.write_text("project: keep-me\n", encoding="utf-8")

    result = runner.invoke(app, ["init"])
    assert result.exit_code == 1
    assert target.read_text(encoding="utf-8") == "project: keep-me\n"

    forced = runner.invoke(app, ["init", "--force"])
    assert forced.exit_code == 0
    assert "project: keep-me" not in target.read_text(encoding="utf-8")


def test_rules_command_lists_all_rules():
    """`agenraci rules` prints every rule id R1-R6 plus its gloss, exit 0."""
    result = runner.invoke(app, ["rules"])
    assert result.exit_code == 0
    for rid in ("R1", "R2", "R3", "R4", "R5", "R6"):
        assert rid in result.stdout
    # The plain-language gloss comes through, not just the ids/titles.
    assert "exactly one accountable role" in result.stdout


def test_validate_sarif_uses_oasis_canonical_schema(tmp_path, monkeypatch):
    """The SARIF document points $schema at the OASIS canonical URL (#55)."""
    monkeypatch.chdir(tmp_path)
    runner.invoke(app, ["init", "good.yaml"])

    result = runner.invoke(app, ["validate", "--format", "sarif", "good.yaml"])
    assert result.exit_code == 0
    doc = json.loads(result.stdout)
    assert doc["$schema"] == (
        "https://raw.githubusercontent.com/oasis-tcs/sarif-spec/master/"
        "Schemata/sarif-schema-2.1.0.json"
    )


def test_color_enabled_decision(monkeypatch):
    """Colour is on only for a TTY with NO_COLOR unset and --no-color not passed."""
    import agenraci.cli as cli

    class _TTY:
        def isatty(self):
            return True

    class _Pipe:
        def isatty(self):
            return False

    monkeypatch.delenv("NO_COLOR", raising=False)
    monkeypatch.setattr(cli.sys, "stdout", _TTY())
    assert cli._color_enabled() is True
    assert cli._color_enabled(no_color=True) is False  # explicit flag wins

    monkeypatch.setenv("NO_COLOR", "")  # NO_COLOR set to ANY value disables
    assert cli._color_enabled() is False

    monkeypatch.delenv("NO_COLOR", raising=False)
    monkeypatch.setattr(cli.sys, "stdout", _Pipe())
    assert cli._color_enabled() is False  # non-TTY (piped) stays plain


def test_no_color_env_suppresses_escape_codes(tmp_path, monkeypatch):
    """With NO_COLOR set, validate output carries no ANSI escape sequences."""
    monkeypatch.chdir(tmp_path)
    runner.invoke(app, ["init", "good.yaml"])

    result = runner.invoke(app, ["validate", "good.yaml"], env={"NO_COLOR": "1"})
    assert result.exit_code == 0
    assert "\033[" not in result.stdout
