<p align="center">
  <img src="../assets/logo.png" alt="Veridion" width="360">
</p>

# Veridion Prototype

**Status:** Unratified prototype under VDP-0000-REQ-009 ("Prototypes and experiments MAY
precede specifications, but they MUST NOT become normative without the VDP process").

This directory is deliberately out-of-band from the constitutional apparatus in
`../constitution/`, `../GOVERNANCE.md`, `../VISION.md`, and `../ROADMAP.md`. It does not
modify, supersede, or depend on any of that. It is not a proposal and should not be treated as
one — it's just the actual, working tool.

## What this is

A deterministic scanner (tree-sitter + git log, no LLM, fully unit-tested) reads a repository
and writes `.veridion/evidence.json`: languages, module dependency graph, modularity-based
clusters, git ownership and commit cadence, secrets, dependency vulnerabilities, layer-
convention violations. Every other feature below is built on top of that same evidence and
never states anything it can't cite back to a specific field in it.

## Setup

```bash
cd prototype
pip install -e ".[dev]"
pytest
```

Requires Python 3.11+.

## Commands

### `veridion scan [path]`

Runs only the deterministic scan phase. Writes `.veridion/evidence.json` and a rolling history
snapshot under `.veridion/history/`. No LLM call — safe to run repeatedly, in CI, or from a
script.

```bash
veridion scan .
veridion scan . --no-check-vulnerabilities   # skip the OSV.dev dependency check
veridion scan . --no-scan-git-history        # skip walking git history for secrets
```

### `veridion audit [path]`

Runs a scan, then shells out to an installed coding-agent CLI (Claude Code today, via
`--agent` to force a specific one) to write a full grounded report to
`.veridion/audit-report.md`, following the per-section instructions in `manual/` (repository
intelligence, git intelligence, architecture, security, AI-usage detection, audience
perspectives, roadmap synthesis) and citing exact evidence fields throughout.

This is a genuinely different kind of operation from everything else in this list: it spawns
a full second agent CLI process (up to a 10-minute timeout) to produce prose, rather than
answering a fast, deterministic query. It's meant to be run by hand, when you actually want a
written document — it is not wired into CI or the MCP server, and shouldn't be: a CI gate
needs to be fast and pass/fail on concrete facts, and an agent already driving an MCP session
can reason over the evidence itself without spawning a nested agent process.

```bash
veridion audit .
veridion audit . --agent claude
```

### `veridion query <kind> [target]`

Answers one targeted question from an existing `evidence.json`, without re-scanning or an LLM
call.

```bash
veridion query imports app/routes.py --path .
veridion query imported-by app/routes.py --path .
veridion query symbols app/routes.py --path .
veridion query branch main --path .
veridion query ownership --path .
veridion query secrets app/routes.py --path .        # findings within just that file
veridion query vulnerabilities --path .
veridion query cluster app/routes.py --path .
veridion query layer-violations --path .
veridion query changes --path .              # diff against the previous history snapshot
```

### `veridion diff <old.json> <new.json>`

Compares two `evidence.json` files directly — new/resolved secrets, layer violations,
dependency vulnerabilities, architecture deltas. Powers the GitHub Action below.

```bash
veridion diff old/evidence.json new/evidence.json
veridion diff old/evidence.json new/evidence.json --fail-on-new-secrets
```

### `veridion mcp [path]`

Starts a stdio MCP server scoped to one repository, so a coding agent can query its structure
directly instead of shelling out via Bash or re-reading files on every lookup. Exposes 13
tools:

- The 9 query kinds above as tools (`veridion_imports`, `veridion_imported_by`,
  `veridion_symbols`, `veridion_branch`, `veridion_ownership`, `veridion_secrets`,
  `veridion_vulnerabilities`, `veridion_cluster`, `veridion_layer_violations`), plus
  `veridion_changes`.
- `veridion_neighborhood(target)` — a module's imports, dependents, and cluster in one call,
  instead of three round-trips.
- `veridion_search(pattern, regex=False, path_glob=None)` — literal or regex full-text search
  over tracked source files, capped at 200 matches.
- `veridion_scan()` — triggers a fresh deterministic scan and returns a compact summary (not
  the full evidence dump). Does **not** run the agent-driven `audit` report — see the note
  under `veridion audit` above for why that's a deliberate boundary, not a gap.

```bash
veridion mcp .
```

### `veridion dashboard [path]`

A live local web UI (Starlette + SSE, opens in your browser): repo overview, git activity,
trend charts for module/secrets/vulnerability counts across scan history, an interactive
dependency graph, a separate community-aware "clusters" graph with zoom/pan, and the list of
MCP tools available for the repo.

```bash
veridion dashboard . --port 8420
```

## GitHub Action

`../action.yml` is a composite Action that scans a PR's base and head refs and posts a diff —
new secrets, layer violations, dependency vulnerabilities. It only ever calls `veridion scan`
and `veridion diff`, matching the reasoning above: CI needs something fast and deterministic,
not a full agent-driven audit.

## Continuity

Every `scan` (and `audit`, which scans first) saves a timestamped snapshot to
`.veridion/history/` (last 20 kept). `veridion query changes` / `veridion_changes` diff the
two most recent snapshots, and the dashboard's trend charts read the full history.
