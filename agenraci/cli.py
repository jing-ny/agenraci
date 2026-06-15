"""The ``agenraci`` command-line interface.

* ``agenraci init [path]`` — write a starter charter to edit.
* ``agenraci validate <charter.yaml>`` — parse + lint, with a per-rule report.
* ``agenraci schema`` — print the charter JSON Schema.
* ``agenraci compile --target {claude,github,humanlayer,langgraph}`` — compile a
  validated charter into config for a target tool (claude/github are real;
  humanlayer/langgraph are stubs).
* ``agenraci verify --target github`` — check that a branch's protection enforces
  what the charter declares (read-only; offline ``--settings`` export for now,
  live ``gh api`` reads land in a later v0.2 increment).
"""

from __future__ import annotations

import json
from importlib.metadata import PackageNotFoundError, version as _pkg_version
from importlib.resources import files
from pathlib import Path

import typer
from pydantic import ValidationError

from .adapters import STUB_TARGETS, TARGETS
from .adapters.github import parse_protection, verify_github
from .linter import EXPLANATIONS, RULES, lint
from .loader import load_charter

app = typer.Typer(
    add_completion=False,
    help="AgenRACI — validate and compile a team's operating constitution.",
)

# Reuse typer's underlying console colours without a hard dependency on rich.
_GREEN = "\033[32m"
_RED = "\033[31m"
_DIM = "\033[2m"
_BOLD = "\033[1m"
_RESET = "\033[0m"


def _echo(msg: str = "") -> None:
    typer.echo(msg)


def _agenraci_version() -> str:
    try:
        return _pkg_version("agenraci")
    except PackageNotFoundError:  # running from a source tree, not installed
        return "0.0.0+unknown"


def _version_callback(value: bool) -> None:
    if value:
        _echo(f"agenraci {_agenraci_version()}")
        raise typer.Exit()


@app.callback()
def _root(
    version: bool = typer.Option(
        False, "--version", "-V",
        help="Show the AgenRACI version and exit.",
        is_eager=True, callback=_version_callback,
    ),
) -> None:
    """AgenRACI — validate and compile a team's operating constitution."""


def _template_text() -> str:
    return (files("agenraci") / "templates" / "charter.template.yaml").read_text(
        encoding="utf-8"
    )


@app.command()
def init(
    charter_path: Path = typer.Argument(
        Path("charter.yaml"),
        help="Where to write the starter charter.",
    ),
    force: bool = typer.Option(
        False, "--force", "-f",
        help="Overwrite the file if it already exists.",
    ),
) -> None:
    """Write a commented starter charter you can edit, then validate."""
    if charter_path.exists() and not force:
        _echo(f"{_RED}✗ {charter_path} already exists.{_RESET} "
              f"Pass {_BOLD}--force{_RESET} to overwrite, or choose another path.")
        raise typer.Exit(code=1)

    charter_path.parent.mkdir(parents=True, exist_ok=True)
    charter_path.write_text(_template_text(), encoding="utf-8")
    _echo(f"{_GREEN}✓{_RESET} wrote starter charter to {_BOLD}{charter_path}{_RESET}")
    _echo(f"  Edit it, then run: {_BOLD}agenraci validate {charter_path}{_RESET}")


def _gh_error(path: Path, title: str, message: str) -> None:
    """Emit a GitHub Actions ``::error`` workflow command (a file-level annotation).

    GitHub renders these in the PR "Files changed" tab, so a failing charter
    shows up where reviewers look instead of only in the run log. Newlines would
    break the command, so collapse them.
    """
    one_line = " ".join(message.split())
    _echo(f"::error file={path},title=AgenRACI {title}::{one_line}")


def _lint_result(charter_path: Path, *, explain: bool = False) -> dict:
    """Compute the canonical machine-readable result for one charter (no output).

    Shared by the ``json`` and ``sarif`` formats so the two never drift. Shape:
    ``{charter, project, ok, error, rules}`` on a charter that loads, where each
    rule carries ``passed`` and any ``findings``; on a charter that fails to load
    it is ``{charter, project: null, ok: false, error, rules: [], findings}``.
    """
    try:
        charter = load_charter(charter_path)
    except ValidationError as exc:
        return {
            "charter": str(charter_path),
            "project": None,
            "ok": False,
            "error": "schema error",
            "rules": [],
            "findings": [
                {"loc": ".".join(str(p) for p in err["loc"]) or "<root>",
                 "message": err["msg"]}
                for err in exc.errors()
            ],
        }
    except Exception as exc:  # malformed YAML, etc.
        return {
            "charter": str(charter_path),
            "project": None,
            "ok": False,
            "error": "could not load",
            "rules": [],
            "findings": [{"loc": None, "message": str(exc)}],
        }

    errors = lint(charter)
    by_rule: dict[str, list] = {}
    for e in errors:
        by_rule.setdefault(e.rule, []).append(e)
    return {
        "charter": str(charter_path),
        "project": charter.project,
        "ok": not errors,
        "error": None,
        "rules": [
            {
                "id": rule_id,
                "title": title,
                # Reserved for future stub rules; always false while R1-R6 are
                # all active (no RULES title carries a " (stub)" marker today).
                "stub": " (stub)" in title,
                "passed": not by_rule.get(rule_id),
                "findings": [
                    {
                        "target": e.target,
                        "message": e.message,
                        **(
                            {"explanation": EXPLANATIONS[rule_id]}
                            if explain and rule_id in EXPLANATIONS
                            else {}
                        ),
                    }
                    for e in by_rule.get(rule_id, [])
                ],
            }
            for rule_id, title, _fn in RULES
        ],
    }


def _sarif_result(rule_id: str, text: str, uri: str) -> dict:
    """One SARIF result object pinned to a charter file (file-level, no line)."""
    return {
        "ruleId": rule_id,
        "level": "error",
        "message": {"text": text},
        "locations": [
            {"physicalLocation": {"artifactLocation": {"uri": uri}}}
        ],
    }


def _sarif_document(results: list[dict]) -> dict:
    """Build a single SARIF 2.1.0 run from per-charter results.

    Findings are file-level: AgenRACI's checker references a *target* (an action
    or role name), not a source line, so each result points at the charter file
    rather than a line within it. GitHub code-scanning ingests this directly.
    """
    rule_descriptors = [
        {
            "id": rule_id,
            "name": title,
            "shortDescription": {"text": title},
            **({"fullDescription": {"text": EXPLANATIONS[rule_id]}}
               if rule_id in EXPLANATIONS else {}),
        }
        for rule_id, title, _fn in RULES
    ] + [
        {"id": "schema-error", "name": "charter schema error",
         "shortDescription": {"text": "The charter does not match the AgenRACI schema."}},
        {"id": "load-error", "name": "charter load error",
         "shortDescription": {"text": "The charter file could not be parsed."}},
    ]

    sarif_results: list[dict] = []
    for r in results:
        uri = r["charter"]
        if r["error"] == "schema error":
            for f in r["findings"]:
                sarif_results.append(
                    _sarif_result("schema-error", f"{f['loc']}: {f['message']}", uri))
        elif r["error"] == "could not load":
            for f in r["findings"]:
                sarif_results.append(_sarif_result("load-error", f["message"], uri))
        else:
            for rule in r["rules"]:
                for f in rule["findings"]:
                    sarif_results.append(
                        _sarif_result(rule["id"], f"{f['target']}: {f['message']}", uri))

    return {
        "$schema": "https://json.schemastore.org/sarif-2.1.0.json",
        "version": "2.1.0",
        "runs": [
            {
                "tool": {
                    "driver": {
                        "name": "AgenRACI",
                        "informationUri": "https://github.com/jing-ny/agenraci",
                        "version": _agenraci_version(),
                        "rules": rule_descriptors,
                    }
                },
                "results": sarif_results,
            }
        ],
    }


def _validate_one(charter_path: Path, *, explain: bool = False, github: bool = False) -> bool:
    """Validate a single charter, print its per-rule report, return True if clean."""
    try:
        charter = load_charter(charter_path)
    except ValidationError as exc:
        _echo(f"{_RED}{_BOLD}✗ schema error{_RESET} in {charter_path}")
        for err in exc.errors():
            loc = ".".join(str(p) for p in err["loc"]) or "<root>"
            _echo(f"  {_RED}-{_RESET} {loc}: {err['msg']}")
            if github:
                _gh_error(charter_path, "schema error", f"{loc}: {err['msg']}")
        return False
    except Exception as exc:  # malformed YAML, etc.
        _echo(f"{_RED}{_BOLD}✗ could not load{_RESET} {charter_path}: {exc}")
        if github:
            _gh_error(charter_path, "could not load", str(exc))
        return False

    errors = lint(charter)
    by_rule: dict[str, list] = {}
    for e in errors:
        by_rule.setdefault(e.rule, []).append(e)

    _echo(f"{_BOLD}AgenRACI charter:{_RESET} {charter.project}  "
          f"{_DIM}({charter_path}){_RESET}")
    _echo(f"{_DIM}{len(charter.roles)} roles · {len(charter.members)} members · "
          f"{len(charter.actions)} action types{_RESET}")
    _echo()

    for rule_id, title, _fn in RULES:
        rule_errors = by_rule.get(rule_id, [])
        stub = " (stub)" in title
        if rule_errors:
            _echo(f"{_RED}✗ {rule_id}{_RESET} {title}")
            for e in rule_errors:
                _echo(f"    {_RED}-{_RESET} {e.target}: {e.message}")
                if github:
                    _gh_error(charter_path, rule_id, f"{e.target}: {e.message}")
            if explain and rule_id in EXPLANATIONS:
                _echo(f"    {_DIM}↳ {EXPLANATIONS[rule_id]}{_RESET}")
        else:
            mark = f"{_DIM}-{_RESET}" if stub else f"{_GREEN}✓{_RESET}"
            _echo(f"{mark} {rule_id} {title}")

    _echo()
    if errors:
        _echo(f"{_RED}{_BOLD}FAIL{_RESET} — {len(errors)} issue(s) found.")
        return False
    _echo(f"{_GREEN}{_BOLD}PASS{_RESET} — charter is a valid operating constitution.")
    return True


@app.command()
def validate(
    charter_paths: list[Path] = typer.Argument(..., exists=True, readable=True,
                                               help="Path(s) to charter.yaml"),
    explain: bool = typer.Option(
        False, "--explain", "-e",
        help="After each failing rule, print a plain-language fix in one line.",
    ),
    output_format: str = typer.Option(
        "human", "--format",
        help="Output format: 'human' (default), 'github' (also emit ::error "
             "annotations for GitHub Actions), 'json' (one machine-readable "
             "object per charter), or 'sarif' (a single SARIF 2.1.0 document "
             "for GitHub code-scanning).",
    ),
) -> None:
    """Validate one or more charters against the schema and linter rules R1-R6.

    Accepting several paths lets a CI job or a pre-commit hook check every
    charter in a repo in one call; the command exits non-zero if any fail.
    Add --explain to turn each rule code into a plain-language fix,
    --format github to surface failures as PR annotations in GitHub Actions,
    --format json for machine-readable per-rule results, or --format sarif to
    upload findings to GitHub code-scanning.
    """
    if output_format not in ("human", "github", "json", "sarif"):
        _echo(f"{_RED}unknown --format {output_format!r}.{_RESET} "
              f"choose one of: human, github, json, sarif")
        raise typer.Exit(code=2)

    # SARIF aggregates every charter into ONE document (code-scanning uploads a
    # single file), so it is handled apart from the per-charter loop below.
    if output_format == "sarif":
        results = [_lint_result(p) for p in charter_paths]
        _echo(json.dumps(_sarif_document(results), indent=2))
        if not all(r["ok"] for r in results):
            raise typer.Exit(code=1)
        return

    github = output_format == "github"
    json_out = output_format == "json"

    ok = True
    for i, charter_path in enumerate(charter_paths):
        if json_out:
            result = _lint_result(charter_path, explain=explain)
            _echo(json.dumps(result))  # one object per line -> JSON Lines
            ok = result["ok"] and ok
            continue
        if i:
            _echo(f"{_DIM}{'─' * 60}{_RESET}")
        ok = _validate_one(charter_path, explain=explain, github=github) and ok

    if not ok:
        raise typer.Exit(code=1)


def _split_compiled_files(text: str) -> list[tuple[str, str]]:
    """Split a multi-file compile output on ``--- FILE: <path> ---`` markers."""
    files: list[tuple[str, list[str]]] = []
    for line in text.splitlines():
        if line.startswith("--- FILE: ") and line.endswith(" ---"):
            files.append((line[len("--- FILE: "):-len(" ---")].strip(), []))
        elif files:
            files[-1][1].append(line)
    return [(path, "\n".join(body).strip() + "\n") for path, body in files]


@app.command()
def compile(  # noqa: A001 - this is the user-facing verb
    charter_path: Path = typer.Argument(..., exists=True, readable=True,
                                        help="Path to charter.yaml"),
    target: str = typer.Option(..., "--target", "-t",
                               help="claude | github | humanlayer | langgraph"),
    out_dir: Path = typer.Option(
        None, "--out-dir", "-o",
        help="For multi-file targets (claude): write the emitted files under "
             "this directory instead of printing them.",
    ),
) -> None:
    """Compile a validated charter into config for a target tool.

    `claude` is real — it emits .claude/agents/ definitions (+ a CLAUDE.md
    governance snippet) so Claude Code agents carry the charter's role
    boundaries. `github` is real — CODEOWNERS + branch-protection guidance from
    the charter's gates. `humanlayer` and `langgraph` are stubs. Either way
    AgenRACI emits config a human reviews and applies; it never enforces at
    runtime.
    """
    if target not in TARGETS:
        _echo(f"{_RED}unknown target {target!r}.{_RESET} "
              f"choose one of: {', '.join(sorted(TARGETS))}")
        raise typer.Exit(code=2)

    try:
        charter = load_charter(charter_path)
    except Exception as exc:  # noqa: BLE001 - schema error, malformed YAML, etc.
        _echo(f"{_RED}✗ could not load {charter_path}:{_RESET} {exc}")
        raise typer.Exit(code=1)

    # Validate before compiling: never emit config from a broken constitution.
    errors = lint(charter)
    if errors:
        _echo(f"{_RED}✗ refusing to compile:{_RESET} charter fails "
              f"{len(errors)} linter rule(s). Run `agenraci validate` first.")
        raise typer.Exit(code=1)

    if target in STUB_TARGETS:
        _echo(f"{_DIM}# agenraci compile --target {target} (STUB){_RESET}")
    output = TARGETS[target](charter)

    if out_dir is None:
        _echo(output)
        return

    files = _split_compiled_files(output)
    if not files:
        _echo(f"{_RED}✗ target {target!r} emits a single document{_RESET} — "
              f"drop --out-dir and redirect stdout instead.")
        raise typer.Exit(code=2)
    for rel, content in files:
        rel_path = Path(rel)
        # Refuse path escapes: everything must land under --out-dir.
        if rel_path.is_absolute() or ".." in rel_path.parts:
            _echo(f"{_RED}✗ refusing to write outside --out-dir:{_RESET} {rel}")
            raise typer.Exit(code=1)
        dest = out_dir / rel_path
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(content, encoding="utf-8")
        _echo(f"{_GREEN}✓{_RESET} wrote {dest}")


@app.command()
def verify(
    charter_path: Path = typer.Argument(..., exists=True, readable=True,
                                        help="Path to charter.yaml"),
    target: str = typer.Option("github", "--target", "-t",
                               help="Enforcement target to verify against (github)."),
    settings: Path = typer.Option(
        None, "--settings", "-s", exists=True, readable=True,
        help="Path to a branch-protection export (JSON) to verify against "
             "offline. Live `gh api` reads land in a later increment.",
    ),
    branch: str = typer.Option("main", "--branch",
                               help="The protected branch the charter governs."),
    output_format: str = typer.Option(
        "human", "--format",
        help="Output format: 'human' (default) or 'json'.",
    ),
) -> None:
    """Check that a live repo actually enforces what the charter declares.

    Read-only: AgenRACI compares the charter against a branch's protection
    settings and reports drift. It never changes the repo. The charter is a
    *floor* — a repo whose settings are stricter passes. Exit codes: 0 clean,
    1 drift, 2 could-not-check (bad input or unreadable charter).
    """
    if target != "github":
        _echo(f"{_RED}unknown --target {target!r}.{_RESET} "
              f"verify currently supports: github")
        raise typer.Exit(code=2)
    if output_format not in ("human", "json"):
        _echo(f"{_RED}unknown --format {output_format!r}.{_RESET} "
              f"choose one of: human, json")
        raise typer.Exit(code=2)
    if settings is None:
        _echo(f"{_RED}✗ --settings is required{_RESET} — pass a branch-protection "
              f"export to verify against (live `gh api` reads land later).")
        raise typer.Exit(code=2)

    try:
        charter = load_charter(charter_path)
    except Exception as exc:  # noqa: BLE001 - schema error, malformed YAML, etc.
        _echo(f"{_RED}✗ could not load {charter_path}:{_RESET} {exc}")
        raise typer.Exit(code=2)  # could-not-check, distinct from drift

    try:
        data = json.loads(settings.read_text(encoding="utf-8"))
    except Exception as exc:  # noqa: BLE001 - malformed JSON, etc.
        _echo(f"{_RED}✗ could not read settings {settings}:{_RESET} {exc}")
        raise typer.Exit(code=2)

    # Surface a silent mismatch: the export may declare a different branch than
    # the one we're verifying. Warn, don't fail — the user picked --branch.
    exported = data.get("branch")
    if exported is not None and str(exported) != branch:
        _echo(f"{_DIM}note: settings export is for branch {exported!r}, "
              f"but verifying against {branch!r}.{_RESET}")

    protection = parse_protection(data, branch=branch)
    report = verify_github(charter, protection, branch=branch)

    if output_format == "json":
        _echo(json.dumps({
            "charter": str(charter_path),
            "project": report.project,
            "target": "github",
            "branch": report.branch,
            "ok": report.ok,
            "note": report.note,
            "findings": [
                {"target": f.target, "kind": f.kind, "message": f.message}
                for f in report.findings
            ],
            "unenforceable": [
                {"target": f.target, "kind": f.kind, "message": f.message}
                for f in report.unenforceable
            ],
        }))
        if not report.ok:
            raise typer.Exit(code=1)
        return

    # human
    _echo(f"{_BOLD}AgenRACI verify (github):{_RESET} {report.project}  "
          f"{_DIM}(branch {report.branch}, settings {settings}){_RESET}")
    if report.note:
        _echo(f"{_DIM}{report.note}{_RESET}")
    for f in report.findings:
        _echo(f"  {_RED}✗ drift{_RESET} {f.target}: {f.message}")
    for f in report.unenforceable:
        _echo(f"  {_DIM}- unenforceable{_RESET} {f.target}: {f.message}")
    _echo()
    if report.findings:
        _echo(f"{_RED}{_BOLD}DRIFT{_RESET} — {len(report.findings)} mismatch(es) "
              f"between the charter and the live branch protection.")
        raise typer.Exit(code=1)
    _echo(f"{_GREEN}{_BOLD}OK{_RESET} — the branch enforces what the charter declares"
          + (f" ({len(report.unenforceable)} action(s) unenforceable, see above)"
             if report.unenforceable else "") + ".")


@app.command()
def schema() -> None:
    """Print the charter JSON Schema (for editor autocomplete / external tools).

    The schema is generated from the same pydantic models the checker uses, so
    it never drifts from what `agenraci validate` accepts. Editors with the YAML
    language server pick it up automatically from the `# yaml-language-server:
    $schema=` line that `agenraci init` writes at the top of a new charter.
    """
    import json

    from .schema import Charter

    _echo(json.dumps(Charter.model_json_schema(), indent=2))


def main() -> None:  # console-script entry point
    app()


if __name__ == "__main__":  # pragma: no cover
    main()
