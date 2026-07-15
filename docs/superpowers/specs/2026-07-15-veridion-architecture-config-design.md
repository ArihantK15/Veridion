# Veridion Clustering & Layer-Convention Configurability Design

**Status:** Draft, pending review
**Date:** 2026-07-15

## Problem

Part IV's design spec left two things explicitly as "Open Questions for Post-Part-IV": whether
`LAYER_FOLDER_MARKERS` should become configurable (the curated list is a fixed, hardcoded
starting point), and whether clustering granularity needs tuning controls once tested against
more real repositories. Both are being picked up together, since they're the same underlying
need — Part IV's defaults have worked on every repo tested so far (Veridion itself, Procta),
but a repo using different naming conventions (`biz/` instead of any built-in name) or wanting
different cluster granularity currently has no way to get useful output from either function.

## Goals

- Let a scanned repo declare its own layer-folder-to-rank markers and/or clustering resolution
  via a `.veridion.json` file committed in the repo's own root.
- Custom `layer_markers` extend/override the built-in `LAYER_FOLDER_MARKERS` on key collision —
  not a full replacement of the curated list.
- Custom `cluster_resolution` is passed directly to `greedy_modularity_communities`'s existing
  `resolution` parameter; absent config keeps today's default (`1.0`) unchanged.
- Surface exactly what config was loaded and applied as new evidence
  (`evidence.architecture.config_applied`), making a repo's declared conventions citable in a
  report rather than an invisible side-channel input.

## Non-Goals

- No invoker-supplied configuration (CLI flags, personal config files, `--config` paths) — the
  scanned repo's own committed `.veridion.json` is the only configuration source. This was a
  deliberate architectural choice, not an oversight: it keeps `evidence.json` a deterministic
  function of the repo's own content, the same reproducibility property every other evidence
  field already has.
- No schema validation beyond "is this valid JSON with the expected top-level key types" —
  malformed entries are treated the same as a missing file (ignored, defaults apply), not
  rejected with an error. A more rigorous schema/validation layer is future scope if malformed
  configs turn out to be a real problem in practice.
- No configurability for anything outside `LAYER_FOLDER_MARKERS` and clustering
  `resolution` in this increment — other Part IV/V/VI curated lists (secret patterns, AI
  provider markers, policy-doc markers) are not addressed here.

## Config File Schema

`.veridion.json` in the scanned repo's root:

```json
{
  "layer_markers": {"biz": 1, "handlers": 2},
  "cluster_resolution": 1.5
}
```

Both keys optional. A missing file, invalid JSON, or a value of the wrong type for either key
is treated identically to an absent file — no crash, defaults apply, matching the existing
`_npm_dependencies` pattern of returning `{}` on `JSONDecodeError` rather than raising.

## Reproducibility

Explicitly holds. `.veridion.json` is part of the scanned repo's own committed state — scanning
the same commit twice reads the identical config both times. This is not a new category of
input; it's the same kind of deterministic, repo-content-derived input `requirements.txt`,
`pyproject.toml`, and `policy_docs`'s marker files already are.

## Evidence Schema Addition

```json
"architecture": {
  "clusters": [...],
  "cross_cluster_edges": [...],
  "layer_violations": {...},
  "config_applied": {
    "layer_markers": {"biz": 1, "handlers": 2},
    "cluster_resolution": 1.5
  }
}
```

`config_applied` is `null` when no `.veridion.json` was found (or it was found but empty/
malformed) — not an empty dict, so the distinction between "no config" and "an empty config
object" stays visible if it ever matters, and so the reasoning phase has an unambiguous single
field to check before citing anything about repo-declared conventions.

## Implementation Approach

- New function `_load_architecture_config(repo_path: Path) -> dict | None` in `architecture.py`,
  reading `.veridion.json`, returning `None` on missing/invalid, otherwise a dict with
  `layer_markers` (dict, default `{}` if key absent) and `cluster_resolution` (float, default
  `1.0` if key absent) — always both keys present in the returned dict when the file exists and
  parses, so callers don't need to re-check key presence.
- `build_clusters(dependency_graph: dict, resolution: float = 1.0) -> tuple[list[dict], list[dict]]`
  gains one new optional parameter, passed straight to `greedy_modularity_communities`.
- `detect_layer_violations(dependency_graph: dict, custom_markers: dict[str, int] | None = None) -> dict`
  gains one new optional parameter; when provided, merged over `LAYER_FOLDER_MARKERS`
  (`{**LAYER_FOLDER_MARKERS, **custom_markers}`) before classification runs — custom entries
  win on key collision, everything else from the built-in list still applies.
- `evidence.py` calls `_load_architecture_config` once, passes the relevant piece to each
  function, and sets `config_applied` in the returned `architecture` dict directly from what
  was loaded (or `None`).

## Testing Strategy

Unit tests for `_load_architecture_config` (present + valid, missing, malformed JSON, partial
— only one of the two keys present). Unit tests for `build_clusters` with a non-default
`resolution` confirming the parameter is actually threaded through (a synthetic graph shaped so
that different resolutions produce visibly different community counts — verified empirically
before being written into the plan, not assumed). Unit tests for `detect_layer_violations` with
a custom marker confirming a folder name absent from the built-in list (e.g. `"biz"`) is now
correctly classified, and that a custom entry overriding a built-in key changes that key's
effective rank.

## Success Criteria

1. A repo with a `.veridion.json` declaring a custom layer marker produces
   `convention_detected: true` for a folder name that would otherwise never match any built-in
   entry — verified against a real synthetic repo, not just a unit-test mock.
2. A repo with no `.veridion.json` produces byte-identical `architecture` evidence to before
   this change (`config_applied: null`, default resolution, default markers) — explicit
   regression check against Procta and Veridion's own repo, both of which lack a
   `.veridion.json` today.
3. `cluster_resolution` set in config measurably changes `build_clusters`'s output on a graph
   where different resolutions are known to produce different community counts.
4. Reproducibility holds: scanning the same repo (with or without `.veridion.json`) twice
   produces identical `architecture.config_applied` and identical cluster assignments both
   times.
