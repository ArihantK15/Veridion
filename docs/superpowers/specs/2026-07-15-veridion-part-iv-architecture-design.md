# Veridion Part IV (Architecture Review) Design — Structural Clustering & Layer-Direction Violations

**Status:** Draft, pending review
**Date:** 2026-07-15

## Problem

Part IV was explicitly deferred when Part V (security) shipped first. Its place in the
original 10-part vision was large and fuzzy: pattern detection (DDD, hexagonal, clean,
layered, MVC, CQRS, event sourcing, microservices), module coupling, circular dependencies,
dependency direction, abstraction quality, interface design, bounded contexts, and named
design patterns (repository, factory, mediator, observer).

Most of that list doesn't survive contact with what Part II already does. Part II's existing
evidence (`dependency_graph`, per-module `imports`/`imported_by`/`symbols`) and its manual
already instruct the reasoning agent to flag high-fan-in modules, circular import chains, and
single-file god-modules — this was directly observed in the real Procta audit report
generated earlier in this project. A real Part IV has to add something structurally new, not
repackage Part II's coverage under a different name.

This spec scopes Part IV down to two capabilities that are genuinely new relative to Part II
and stay inside the project's evidence-grounding discipline: **structural clustering**
(finding natural module groupings from the dependency graph itself, via a real, deterministic
graph-clustering algorithm) and **layer-direction violations** (detecting when a module in an
inner architectural layer, by folder-naming convention, imports from an outer layer).
Everything else from the original wishlist — named pattern labeling, abstraction-quality
judgment, named design-pattern detection — requires semantic code understanding that a
deterministic scanner cannot ground, and is excluded (see Non-Goals).

## Goals

- Detect natural module clusters from the existing dependency graph using a real,
  deterministic graph-clustering algorithm (not folder layout, which mostly re-describes
  information already visible from the directory tree and can miss coupling that crosses
  folder boundaries).
- Detect dependency-direction violations against a folder-naming-convention-based layer model,
  when such a convention is recognizable — and say plainly when it isn't, rather than forcing
  a guess.
- Extend `evidence.json` with a new top-level `architecture` block, following the same
  "scanner computes facts, manual instructs interpretation" pattern as Parts II, III, and V.
- Ship a Part IV manual section with the same two-tier structure (mandatory rules, then
  interpretation guidance) as every other part.

## Non-Goals

- Named architectural pattern labeling (DDD, hexagonal, clean, layered, MVC, CQRS, event
  sourcing, microservices) — requires interpreting code semantics and intent, not just import
  structure; not evidence-groundable at the scanner level.
- Abstraction-quality or interface-design judgment (e.g., Liskov substitution violations).
- Named design-pattern detection (repository, factory, mediator, observer, etc.).
- Auto-remediation or refactoring suggestions.
- Architecture diagrams or any visual output — text findings only, matching every other part.
- Cross-repository or microservice-boundary analysis — single-repo scope, matching the rest of
  the scanner.

## Evidence Schema Addition (`evidence.architecture`)

```json
"architecture": {
  "clusters": [
    {
      "id": 0,
      "modules": ["app/routers/auth.py", "app/services/auth.py"],
      "internal_edges": 12
    }
  ],
  "cross_cluster_edges": [
    {
      "from_cluster": 0,
      "to_cluster": 1,
      "count": 3,
      "edges": [["app/routers/auth.py", "app/services/billing.py"]]
    }
  ],
  "layer_violations": {
    "convention_detected": true,
    "layers": [
      {"name": "domain", "rank": 0, "folders": ["app/domain"]},
      {"name": "infrastructure", "rank": 2, "folders": ["app/infra"]}
    ],
    "violations": [
      {
        "from": "app/domain/user.py",
        "to": "app/infra/db.py",
        "reason": "inner layer 'domain' imports outer layer 'infrastructure'"
      }
    ]
  }
}
```

When no recognizable layer-naming convention exists in the repo, `convention_detected: false`,
`layers: []`, `violations: []` — an explicit "not determinable," never a forced or guessed
layering.

## Structural Clustering

- **Algorithm**: `networkx.algorithms.community.greedy_modularity_communities` (Clauset-
  Newman-Moore greedy modularity maximization) — confirmed live before writing this spec to be
  fully deterministic across repeated runs on the same graph (three runs against a synthetic
  two-cluster-plus-bridge-edge graph produced byte-identical output each time). This resolves
  the reproducibility concern that ruled out a randomized clustering method (e.g. Louvain
  without a fixed seed).
- **Input**: the existing `repository.dependency_graph`, converted to an undirected NetworkX
  graph — clustering cares about "these two modules are coupled," which is symmetric,
  regardless of which one imports the other.
- **New dependency**: `networkx`. A single, stable, extremely well-established graph library —
  justified the same way `certifi` was justified for Part V: strictly necessary for the actual
  capability, not a convenience addition.
- **Output**: each cluster's exact module membership and internal edge count, plus every
  cross-cluster edge as an explicit `(from_module, to_module)` pair — every claim the
  reasoning agent makes about coupling must trace to a real edge in this list, never an
  inferred or approximate one.

## Layer-Direction Violations

- **Layer detection**: a small curated mapping of common folder-naming conventions to a
  layer rank (0 = innermost/most protected, higher = outer): `domain`/`core`/`entities` → 0,
  `application`/`services`/`use_cases` → 1, `infrastructure`/`adapters`/`api`/`routers`/`web`/
  `controllers` → 2. A repo's convention is "detected" only if at least two distinct ranks are
  both present as actual folders in the scanned repo — a single matching folder name in
  isolation (e.g. just an `api/` folder with no `domain/` or `services/` counterpart) is not
  enough evidence of an intentional layering scheme.
- **Violation rule**: a module at rank *N* importing a module at rank *M* where *M > N* (an
  inner layer depending on an outer one) is a violation — this is exactly the Clean
  Architecture / Hexagonal dependency rule, applied mechanically once folders are ranked.
  Same-rank or inner-importing-from-outer-in-the-*other*-direction (outer depends on inner) is
  normal and not flagged.
- **When no convention is detected**: `convention_detected: false`. This is expected to be the
  common case — most real repositories, including both Procta and Veridion's own prototype,
  don't use domain/infrastructure-style folder naming. The manual must treat this as a
  legitimate, common outcome, not an error or a coverage gap to apologize for.

## Part IV Manual Content

Same two-tier structure as every other part:

- **Mandatory, primary**: a cluster is a structural grouping derived from import coupling, not
  evidence of intentional architectural design — never claim a cluster represents a deliberate
  module boundary the author chose. When `layer_violations.convention_detected` is `false`,
  state plainly that no layering convention was detected — this is a normal, common outcome,
  not a gap to flag as a limitation. Every cross-cluster or violation claim must cite the exact
  file pair(s) from `cross_cluster_edges` or `violations`, never a cluster ID or count alone.
- **Interpretation guidance, secondary**: a `layer_violations.violations` entry is worth
  naming explicitly, both files involved, and the layer names crossed. A high
  `cross_cluster_edges` count relative to a cluster's `internal_edges` is worth noting as
  "worth investigating," never "confirmed bad" — a shared utility module legitimately imported
  by many otherwise-unrelated clusters is expected, normal structure, not a violation; the
  agent must distinguish "many clusters depend on this one shared module" (usually fine) from
  "these two specific clusters are unexpectedly tangled with each other" (more interesting)
  before treating cross-cluster coupling as noteworthy.

## Testing Strategy

- **Clustering**: unit-tested against synthetic dependency graphs with a known expected
  partition (the two-cluster-plus-thin-bridge fixture already verified live during design is
  the natural starting fixture), confirming both correct cluster assignment and exact
  `cross_cluster_edges` content.
- **Layer violations**: unit-tested against synthetic folder/import fixtures covering (a) a
  real violation (inner layer importing outer), (b) a clean case with a detected convention
  and no violations, and (c) no convention detected at all.
- **Honest coverage gap, stated up front rather than discovered later**: neither Procta nor
  Veridion's own repo uses domain/infrastructure-style folder naming. The live dogfood gate
  (below) can only validate the `convention_detected: false` path against real-world data —
  the "convention found, violation caught" path is exercised only by synthetic unit tests,
  never against messy real code. This is a known, accepted limitation of this increment, not
  an oversight to be silently papered over.

## Success Criteria

1. Clustering completes against Procta's real ~600-module dependency graph and is
   reproducible: two separate scans of the same commit produce byte-identical cluster
   assignments.
2. Layer-violation detection correctly reports `convention_detected: false` on both Procta and
   Veridion's own repo (neither uses a recognizable layering convention) — not a false
   positive forced from folder names that don't actually signal intentional layering.
3. A full reasoning-phase report against Procta cites exact cluster membership and real
   cross-cluster edges for any coupling claim, and contains zero named-architecture-pattern
   claims (no "this is hexagonal," "this follows MVC," etc.) anywhere in the output.

## Open Questions for Post-Part-IV

- Whether the layer-naming convention list should become user-configurable (a project-level
  config file naming its own layer folders) once real-world testing shows the curated
  defaults are too narrow — not addressed here; the curated list is a fixed, hardcoded
  starting point for this increment.
- Whether clustering granularity (the modularity-maximization algorithm's natural cluster
  count) needs tuning controls once tested against a wider variety of real repositories beyond
  Procta and Veridion's own prototype.
