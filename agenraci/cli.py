"""The ``agenraci`` command-line interface.

* ``agenraci init [path]`` — write a starter charter to edit.
* ``agenraci validate <charter.yaml>`` — parse + lint, with a per-rule report.
* ``agenraci compile --target {humanlayer,langgraph} <charter.yaml>`` — STUB.
"""

from __future__ import annotations

from importlib.metadata import PackageNotFoundError, version as _pkg_version
from importlib.resources import files
from pathlib import Path

import typer
from pydantic import ValidationError

from .adapters import STUB_TARGETS, TARGETS
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


def _version_callback(value: bool) -> None:
    if value:
        try:
            ver = _pkg_version("agenraci")
        except PackageNotFoundError:  # running from a source tree, not installed
            ver = "0.0.0+unknown"
        _echo(f"agenraci {ver}")
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
        help="Output format: 'human' (default) or 'github' "
             "(also emit ::error annotations for GitHub Actions).",
    ),
) -> None:
    """Validate one or more charters against the schema and linter rules R1-R6.

    Accepting several paths lets a CI job or a pre-commit hook check every
    charter in a repo in one call; the command exits non-zero if any fail.
    Add --explain to turn each rule code into a plain-language fix, or
    --format github to surface failures as PR annotations in GitHub Actions.
    """
    if output_format not in ("human", "github"):
        _echo(f"{_RED}unknown --format {output_format!r}.{_RESET} "
              f"choose one of: human, github")
        raise typer.Exit(code=2)
    github = output_format == "github"

    ok = True
    for i, charter_path in enumerate(charter_paths):
        if i:
            _echo(f"{_DIM}{'─' * 60}{_RESET}")
        ok = _validate_one(charter_path, explain=explain, github=github) and ok

    if not ok:
        raise typer.Exit(code=1)


@app.command()
def compile(  # noqa: A001 - this is the user-facing verb
    charter_path: Path = typer.Argument(..., exists=True, readable=True,
                                        help="Path to charter.yaml"),
    target: str = typer.Option(..., "--target", "-t",
                               help="github | humanlayer | langgraph"),
) -> None:
    """Compile a validated charter into config for a target tool.

    `github` is real — it emits CODEOWNERS + branch-protection guidance from the
    charter's gates and accountability. `humanlayer` and `langgraph` are stubs in
    v0.1. Either way AgenRACI emits config a human applies; it never enforces at
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
    _echo(TARGETS[target](charter))


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
