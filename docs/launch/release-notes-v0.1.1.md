# AgenRACI v0.1.1

A fast follow-up to the first release. Same honest scope — AgenRACI **writes and
checks** a charter; it still does not intercept tool calls or enforce approvals at
runtime — but the tooling around writing and checking one got noticeably better,
and the first GitHub adapter is now real.

## New

**Editor autocomplete for charters.** `agenraci schema` prints a JSON Schema
generated from the same models the checker uses, and a freshly `agenraci init`'d
charter carries a `# yaml-language-server: $schema=` line — so VS Code (with the
YAML extension) gives you autocomplete and inline validation as you type.

**PR annotations in CI.** `agenraci validate --format github` emits `::error`
annotations, and the GitHub Action now uses it — a failing charter shows up as a
file-level annotation in the PR's "Files changed" tab, not just buried in the log.

**`compile --target github` is real** (no longer a stub). It turns a charter's
gates and accountability into a **CODEOWNERS** starting point and a
**branch-protection checklist** — required approver per gated action, whether a
timeout may auto-proceed, and the break-glass path. It even flags a gate whose
approver role has no human member (you can't make an agent a GitHub required
reviewer). It emits config a human reviews and applies — still not runtime
enforcement. The `humanlayer` and `langgraph` targets remain stubs (labelled).

**Shareable playground links.** The browser playground now has a **Share** button
that encodes the charter into the URL fragment; opening the link restores it. The
charter rides in the `#fragment`, which is never sent to a server, so it still
honors "your charter is never uploaded."

**A cookbook for the "I already run agents" reader.**
[From a running agent team to a charter](https://github.com/jing-ny/agenraci/blob/main/docs/cookbook/from-agents-to-a-charter.md)
maps a LangGraph / CrewAI / Claude-subagent setup to a charter step by step, using
this repo's own `.claude/agents/` ↔ `governance/charter.yaml` as the worked example.

## Hardening

- Reject duplicate YAML keys instead of silently keeping the last value — a
  vanishing rule in a source-of-truth charter is a correctness hazard (anchors and
  merge keys still work).
- Close a shell-injection path in the composite GitHub Action (the `charter` input
  is passed through the environment, not interpolated into the script).
- Pin the playground's in-browser dependencies so a future major release can't
  break it overnight; least-privilege `permissions:` on the CI workflow; correct
  the LICENSE copyright holder.

## Install / upgrade

```bash
pip install --upgrade agenraci
```

Full diff since 0.1.0: <https://github.com/jing-ny/agenraci/compare/v0.1.0...v0.1.1>.
MIT-licensed.
