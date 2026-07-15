# Veridion Git-History Secret Scanning Design

**Status:** Draft, pending review
**Date:** 2026-07-15

## Problem

Part V's secrets detector (`find_secrets`) scans only the current working tree. A secret that
was committed and later removed is still exposed in every clone of the repository forever —
tree-only scanning cannot see it. This spec was explicitly deferred when Part V shipped ("git
history scanning is a natural, well-understood follow-up... it just wasn't included here to
keep this increment small") and is now being picked up.

## Goals

- Walk full commit history via `git log -p`, regex-matching the exact same `SECRET_PATTERNS`
  ruleset `find_secrets` already uses against every added line (`+`-prefixed diff lines,
  excluding `+++` file-header lines) in every non-merge commit.
- Reuse `secrets.py`'s existing pattern list, redaction (`_redact`), and placeholder heuristic
  (`_is_likely_placeholder`) as-is via import — this spec adds no new detection logic, only a
  new traversal mechanism over the same rules.
- Add `evidence.security.secrets.history_findings` and `history_scanned_commits`, on by
  default, with a `--no-scan-git-history` opt-out flag.

## Non-Goals

- No changes to `find_secrets`'s existing tree-only detection, redaction, or placeholder logic
  — purely additive.
- No deduplication logic — diff semantics (a line only appears as `+` when genuinely added)
  already keep repeated reporting naturally sparse; verified empirically (see below), not
  assumed.
- No merge-commit diff scanning — `git log -p`'s default behavior (no `-m` flag) already skips
  merge-commit diffs, which is kept as-is rather than overridden, since `-m` would show each
  merge's diff against every parent separately, largely duplicating content already scanned
  in the individual commits being merged.
- No new UI/report changes beyond the new evidence fields — Part V's manual already instructs
  the agent to read `evidence.security.secrets`; a small addition to that manual covers the
  new sub-fields (this spec does not re-litigate Part V's manual structure).

## Mechanism, Verified Empirically

Command: `git log -p --format="COMMIT_START%x1f%H%x1f%ad" --date=iso-strict` (no `-m`, no
`--first-parent` — relies on git's own default merge-commit-skipping behavior).

Parsing, streaming line-by-line (not loading the full output into memory at once):
- A line starting with `COMMIT_START\x1f` updates the current commit hash/date (split on
  `\x1f`).
- A line starting with `+++ b/` updates the current file path (strip the `+++ b/` prefix).
- A line starting with `+++` (the file-header line itself) is skipped — not a content line.
- A line starting with `+` (and not `+++`) is a genuinely added line — strip the leading `+`,
  run `SECRET_PATTERNS` against the remainder exactly as `find_secrets` does per tree line.

**Verified against Procta's real 1,703-commit history** (not a synthetic fixture — the actual
target repo this whole project has dogfooded against all session): the `git log -p` command
itself completed in 3.6 seconds, producing ~581K lines / 54MB of diff output. Parsing and
regex-matching all 345,644 added lines against all 7 patterns took a further 1.55 seconds.
**Total: under 5 seconds on the largest real repo available for testing.** This directly
contradicts the original assumption (going into this design) that history scanning would be a
meaningful regression to scan speed — it is not, at this scale, which is why the default lands
on "on," not "opt-in."

## Evidence Schema Addition

```json
"security": {
  "secrets": {
    "scanned_files": 4070,
    "findings": [
      {"path": "app/config.py", "line": 12, "pattern": "aws_access_key_id",
       "match_preview": "AKIA****...WXYZ", "likely_placeholder": false}
    ],
    "history_scanned_commits": 1703,
    "history_findings": [
      {"commit": "abc123def456...", "commit_date": "2026-03-01T10:00:00+00:00",
       "path": "app/config.py", "pattern": "aws_access_key_id",
       "match_preview": "AKIA****...WXYZ", "likely_placeholder": false}
    ]
  }
}
```

`history_findings` entries omit `line` (unlike tree `findings`) — a line number within a
specific historical diff isn't a stable or generally useful pointer once you're not looking at
the current tree; `commit` + `path` is what you'd actually use to go inspect it
(`git show <commit>:<path>`, or `git log -p -- <path>`).

When `--no-scan-git-history` is passed: `history_scanned_commits: 0`, `history_findings: []`
— same "explicit, not silently empty" pattern as `dependency_vulnerabilities`'s
`checked`/`reason` fields, though here the signal is the `--no-scan-git-history` flag itself
being documented in the manual as the reason, since there's no separate `checked` boolean
proposed for this (mirroring `unparseable_files`'s pattern of "empty means genuinely
nothing found," not `security`'s `checked`/`reason` pattern — this is a deliberate,
noted choice: adding a third field shape to `secrets` when `scanned_files`/`findings` already
established "count + list, no checked/reason wrapper" would be inconsistent with the sibling
fields in the same dict).

## Default Behavior and Flag

- On by default. `--no-scan-git-history` opts out (naming matches
  `--no-check-vulnerabilities`'s existing convention).
- No new timeout or size-based auto-disable for v1 — the 5-second measurement on a
  1,703-commit repo is the only real data point available; if a much larger repo turns out to
  be genuinely slow, that's a concrete future refinement once real evidence of the problem
  exists, not something to build defensively now without a repo that actually demonstrates it.

## Testing Strategy

Unit tests against a synthetic git repo (built via `subprocess` calls in the test, same
pattern already used in `test_git_intel.py`'s `make_git_repo` fixture) with a scripted
history: a commit that adds a real-pattern-matching secret, a later commit that removes it,
confirming the removed secret still appears in `history_findings`. A separate scripted case
confirms a merge commit's own diff is not scanned (matching the non-goal above). No live
network calls anywhere — this feature is 100% local git operations.

## Success Criteria

1. Running against Procta completes in a comparable timeframe to the measurement above (under
   10 seconds for the history-scanning step specifically) — confirms the performance
   assumption holds outside this one-time manual measurement.
2. A secret committed and later removed in Procta's real history (if one exists — not
   guaranteed, this is a real repo, not a fixture) is either found and correctly redacted, or
   `history_findings` is confirmed empty and that's accepted as a genuine "none found" result,
   not treated as a failure either way.
3. `--no-scan-git-history` correctly produces `history_scanned_commits: 0`,
   `history_findings: []` with no `git log -p` subprocess call made at all (verify via timing —
   the flagged-off run should be measurably faster, not just report empty results).
4. No secret's real value appears anywhere in `evidence.json` for history findings, same
   redaction guarantee as tree findings — spot-checked, not assumed from code review alone.
