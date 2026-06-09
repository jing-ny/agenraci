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

from .adapters import TARGETS
from .linter import RULES, lint
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


@app.command()
def validate(
    charter_path: Path = typer.Argument(..., exists=True, readable=True,
                                        help="Path to charter.yaml"),
) -> None:
    """Validate a charter against the schema and linter rules R1-R5 (R6 stub)."""
    try:
        charter = load_charter(charter_path)
    except ValidationError as exc:
        _echo(f"{_RED}{_BOLD}✗ schema error{_RESET} in {charter_path}")
        for err in exc.errors():
            loc = ".".join(str(p) for p in err["loc"]) or "<root>"
            _echo(f"  {_RED}-{_RESET} {loc}: {err['msg']}")
        raise typer.Exit(code=1)
    except Exception as exc:  # malformed YAML, etc.
        _echo(f"{_RED}{_BOLD}✗ could not load{_RESET} {charter_path}: {exc}")
        raise typer.Exit(code=1)

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
        else:
            mark = f"{_DIM}-{_RESET}" if stub else f"{_GREEN}✓{_RESET}"
            _echo(f"{mark} {rule_id} {title}")

    _echo()
    if errors:
        _echo(f"{_RED}{_BOLD}FAIL{_RESET} — {len(errors)} issue(s) found.")
        raise typer.Exit(code=1)
    _echo(f"{_GREEN}{_BOLD}PASS{_RESET} — charter is a valid operating constitution.")


@app.command()
def compile(  # noqa: A001 - this is the user-facing verb
    charter_path: Path = typer.Argument(..., exists=True, readable=True,
                                        help="Path to charter.yaml"),
    target: str = typer.Option(..., "--target", "-t",
                               help="humanlayer | langgraph"),
) -> None:
    """Compile a charter into runtime config for a target tool (STUB in v0.1)."""
    if target not in TARGETS:
        _echo(f"{_RED}unknown target {target!r}.{_RESET} "
              f"choose one of: {', '.join(sorted(TARGETS))}")
        raise typer.Exit(code=2)

    try:
        charter = load_charter(charter_path)
    except (ValidationError, Exception) as exc:  # noqa: BLE001
        _echo(f"{_RED}✗ could not load {charter_path}:{_RESET} {exc}")
        raise typer.Exit(code=1)

    # Validate before compiling: never emit config from a broken constitution.
    errors = lint(charter)
    if errors:
        _echo(f"{_RED}✗ refusing to compile:{_RESET} charter fails "
              f"{len(errors)} linter rule(s). Run `agenraci validate` first.")
        raise typer.Exit(code=1)

    _echo(f"{_DIM}# agenraci compile --target {target} (STUB){_RESET}")
    _echo(TARGETS[target](charter))


def main() -> None:  # console-script entry point
    app()


if __name__ == "__main__":  # pragma: no cover
    main()
