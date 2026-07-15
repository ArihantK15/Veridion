# Veridion `scan`/`query` Subcommands Design (Task 13 rescoped)

**Status:** Draft, pending review
**Date:** 2026-07-15

## Problem

Task 13 in the v1 plan (`docs/superpowers/plans/2026-07-14-veridion-v1-scanner.md`) sketched a
token-saving query interface: run a deterministic scan once, then answer cheap, targeted
questions against the resulting `evidence.json` instead of an agent re-reading or re-grepping
the whole repository. It was written before Part IV (architecture) and Part V (security)
existed, so it only covered `repository.modules` (imports/imported-by/symbols). It was never
implemented. This spec rescopes it against the current, complete `evidence.json` shape —
`repository`, `git`, `security`, and `architecture` — and replaces the stale Task 13 entry.

## Goals

- `veridion scan [path]`: run only the deterministic scan phase (no agent invocation), as its
  own first-class subcommand rather than the `--agent nonexistent-placeholder` workaround used
  throughout this project's own dogfooding so far.
- `veridion query <kind> [target] [--path REPO]`: answer a single targeted question by reading
  an existing `evidence.json` directly — no re-scanning, no network, no agent call.
- Cover all four top-level evidence blocks that exist today, not just the original
  `repository`-only scope.

## Non-Goals

- A live/always-fresh index, file-watching, or an MCP server — `query` answers from whatever
  `evidence.json` was last written, exact as of that scan and stale after. This tradeoff was
  already decided when Task 13 was first sketched and isn't revisited here.
- Any new evidence computation — `query` only reads fields that `scan_repository` already
  produces. No new scanning logic, no new evidence schema.
- Fuzzy or partial-match lookups (e.g. "find files matching a glob") — exact key lookups only,
  matching the precision the rest of the project holds evidence claims to.

## `veridion scan`

Factor the scan-phase logic already inlined at the top of `_audit` (in `cli.py`) into a shared
`_scan` function, called by both `_audit` and the new `scan` subcommand. Same
`--no-check-vulnerabilities` flag `audit` already exposes, since scanning is scanning
regardless of which subcommand triggers it.

## `veridion query`

One subcommand, nine lookup kinds, one shared registry pattern:

| `kind` | requires `target`? | evidence source |
|---|---|---|
| `imports` | file path | `repository.modules[].imports` |
| `imported-by` | file path | `repository.modules[].imported_by` |
| `symbols` | file path | `repository.modules[].symbols` |
| `branch` | branch name | `git.branches[]` |
| `ownership` | no | `git.ownership` (whole list) |
| `secrets` | file path | `security.secrets.findings[]`, filtered to that path |
| `vulnerabilities` | no | `security.dependency_vulnerabilities` (whole block) |
| `cluster` | file path | `architecture.clusters[]` containing that file |
| `layer-violations` | no | `architecture.layer_violations` (whole block) |

A registry maps each `kind` string to `(function, requires_target: bool)`. The CLI validates
`requires_target` **before** calling the lookup function, so a missing target produces a clear
"query type 'branch' requires a target argument" rather than a confusing downstream failure.
Every lookup function takes `(evidence: dict, target: str | None) -> Any` for signature
uniformity, even though functions that don't require a target (`ownership`,
`vulnerabilities`, `layer-violations`) simply ignore it.

**Error handling**: if `.veridion/evidence.json` doesn't exist, print a clear error naming the
expected path and suggesting `veridion scan <path>`, exit 1 — no crash, no traceback. If a
file-path or branch-name lookup finds nothing, raise a specific typed error
(`ModuleNotFoundInEvidenceError` / `BranchNotFoundInEvidenceError`) caught at the CLI layer and
printed as a clear one-line error, exit 1.

**Output**: `json.dumps(result, indent=2)` to stdout for every query kind — consistent,
parseable, no per-kind formatting logic.

## Testing Strategy

Each lookup function unit-tested directly against a small synthetic `evidence` dict covering
all four blocks (no real scan needed — these are pure dict lookups). CLI-level tests cover: the
"requires target but none given" error path, the "evidence.json missing" error path, and one
success path per subcommand (`scan` writes evidence and prints its path; `query` for at least
one target-requiring and one non-target-requiring kind returns the expected JSON).

## Success Criteria

1. `veridion scan .` writes `evidence.json` and prints its path, without ever invoking an
   adapter or making a network/LLM call.
2. `veridion query imports <file> --path <repo>` and `veridion query cluster <file> --path
   <repo>`, run against a real scanned repo, return results that match the corresponding fields
   in that repo's actual `evidence.json` exactly.
3. `veridion query ownership --path <repo>` (a no-target kind) succeeds without a target
   argument.
4. Running `query` before ever running `scan` on a fresh directory produces the clear
   "run `veridion scan` first" error, not a stack trace.
