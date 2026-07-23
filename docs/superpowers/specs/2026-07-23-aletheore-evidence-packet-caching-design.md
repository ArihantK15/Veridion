# Aletheore Evidence Packet, TOON Exchange, and Similarity Caching Design

**Status:** Draft, pending implementation
**Date:** 2026-07-23

## Problem

The product's cost model depends on a two-stage pattern: a cheap model filters/extracts what
matters from deterministic evidence, then a tier-routed model reasons over the filtered result.
Today only AIRview has any shape of this (a cheap naming call, then a tier-routed writing call),
and even there the two calls just pass plain Python dicts in-process - there is no canonical,
model-neutral schema, no TOON compression, and no reuse of prior computation across similar
inputs. `managed_audit.py` and `flash_review.py` are single model calls with no filtering stage at
all.

This means every AIRview build, managed audit, and Flash review pays full token cost even when the
underlying evidence is nearly identical to something already processed - e.g. a repo's dependency
cluster barely changes between two adjacent pushes, but the writing stage currently regenerates its
full description from scratch every time.

TOON encoding infrastructure already exists (`prototype/aletheore/toon_encoding.py`, used for
`air.toon`), and a canonical evidence-resolution schema already exists
(`prototype/aletheore/evidence_resolution.py`, file/line/symbol/owner/commit/dependency/risk/
confidence). Neither is wired into the model-routing pipeline itself.

## Goals

- Introduce one canonical `EvidencePacket` schema, shared between the CLI and the hosted app, that
  the cheap stage produces and the expensive stage consumes.
- TOON-encode the packet before it is sent to the downstream model, as a real cost-reduction step
  on an actual filtered payload, not compression of nothing.
- Add a similarity-based result cache so a near-identical packet can skip the expensive model call
  entirely, with a hard safety gate: a cache hit is only ever served after re-running the exact
  same validation the fresh-call path already runs, against *current* evidence.
- Prove the full pipeline end-to-end on one real consumer (AIRview's writing stage) before
  extending it anywhere else.
- Keep the cache strictly scoped per installation - never let one customer's cached computation
  become a candidate match for another customer's lookup, regardless of how evidence resolution
  might later prove a specific hit "safe."

## Non-Goals

- No changes to managed audits or Flash review in this phase. Both are real, valuable fast-follow
  work, but caching a security/review *verdict* is a materially different risk than caching an
  architecture *description* (see "Cache eligibility" below) and deserves its own design pass
  rather than inheriting this one by default.
- No `pgvector` or dedicated vector database. Per-installation, per-repo cache volume is expected
  to be small (dozens of rows, not millions); Python-side cosine similarity over a bounded recent
  set is enough for this phase. `pgvector` is a documented upgrade path, not built now.
- No cache-warmth gatekeeper (the master-brief idea of rebuilding a compact summary when cache
  coverage drops below some threshold). More machinery than this phase's simple lookup-or-miss
  design needs.
- No reliance on provider-side prompt caching (DeepSeek/OpenAI/Anthropic's own native caching).
  Separate mechanism, not wired into or assumed by this design.
- No cache eviction/TTL policy. Rows accumulate for now; a cleanup job is an explicit known
  follow-up, not a silent gap.
- No cache-hit-rate dashboard. The `hit_count` column supports direct-query introspection only.
- No fake `test_coverage` data. The packet field exists per the canonical schema but stays `null`
  until a real test-coverage signal exists in the scanner - the schema having a field is not
  permission to invent a value for it.

## Design

### EvidencePacket schema

New shared module `prototype/aletheore/evidence_packet.py`, alongside the existing
`evidence_resolution.py` and `toon_encoding.py` (both already imported by the hosted `github-app`,
so this follows the established pattern rather than introducing a new one).

```python
{
    "repository": str,
    "base_commit": str | None,
    "head_commit": str | None,
    "changed_files": list[str],
    "changed_symbols": list[str],
    "changed_routes": list[str],
    "changed_dependencies": list[str],
    "owners": list[str],
    "evidence_locations": list[<evidence_resolution.py resolution object>],
    "risk_classification": list[dict],
    "graph_edges_before": list[dict] | None,
    "graph_edges_after": list[dict] | None,
    "endpoint_telemetry": dict | None,
    "historical_failures": list[dict] | None,
    "test_coverage": None,   # always null this phase - no source for this signal yet
    "model_routing_reason": str,
    "cache_eligible": bool,  # see Cache eligibility below
}
```

`evidence_locations` reuses `evidence_resolution.py` objects directly rather than a parallel
format - that module already carries the file/line/symbol/owner/commit/dependency/risk/confidence
shape this schema needs.

`build_evidence_packet(evidence, target)` assembles this from data already present in
`air.json` plus the diff/cluster being processed. No new repository scanning is introduced; this
is a filtering/reshaping step over what the deterministic scanner already produced.

### Cache eligibility

Not every packet type should be cache-eligible by default. `cache_eligible` is set explicitly by
the caller building the packet, not inferred. For this phase, only AIRview's cluster-description
packets are marked eligible. This exists so that when managed audits/Flash review are wired in
later, a deliberate decision is required per content type rather than caching silently inheriting
into a higher-stakes surface. The reasoning: citation verification proves the evidence a claim
points to is real, but it does not prove a *conclusion* drawn about that evidence is still correct
for a different-but-similar diff. For an architecture description, "these files exist and connect
this way" is close to the entire claim, so verified citations cover almost the whole quality bar.
For a security finding, the verdict itself needs separate validation that this phase does not
build.

### TOON encoding

Once a packet is being sent to the downstream model (cache miss, or nothing eligible for caching),
it is TOON-encoded via the existing `toon_encoding.py` before being included in the prompt -
reusing the same encoder already used for `air.toon`, not a new format.

The same TOON-encoded string doubles as the embedding input (see below) - one serialization of the
packet, not a second bespoke format invented just for embedding.

### Embeddings and the hosted Ollama container

Similarity matching needs embeddings, not a chat/reasoning model. The CLI already has a local
embedding pipeline (`prototype/aletheore/search_index.py`, Ollama's `nomic-embed-text`, ~274MB,
embedding-only, not text-generating) for local semantic search, but the hosted server has no
Ollama today. This design adds Ollama as a new service in `github-app/docker-compose.yml`,
running only `nomic-embed-text`, used only to turn an `EvidencePacket`'s TOON-encoded string (the
same string that would otherwise go straight into the model prompt) into a vector for cache
lookups. All actual reasoning continues through the existing tier-routed DeepSeek/GPT-4o/Claude
Opus adapters unchanged - Ollama never writes any user-visible content.

### Cache storage

New table `evidence_packet_cache`:

```sql
CREATE TABLE evidence_packet_cache (
    id             BIGSERIAL PRIMARY KEY,
    installation_id BIGINT NOT NULL REFERENCES installations(installation_id) ON DELETE CASCADE,
    repo_full_name TEXT NOT NULL,
    content_hash   TEXT NOT NULL,       -- exact-match fast path
    embedding      DOUBLE PRECISION[] NOT NULL,
    packet_json    JSONB NOT NULL,
    model_output   TEXT NOT NULL,
    model_used     TEXT NOT NULL,
    created_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
    last_hit_at    TIMESTAMPTZ,
    hit_count      INT NOT NULL DEFAULT 0
);
CREATE INDEX evidence_packet_cache_lookup
ON evidence_packet_cache (installation_id, repo_full_name);
```

A lookup fetches the most recent 200 rows for `(installation_id, repo_full_name)` - never across
installations, regardless of similarity score - and computes cosine similarity in Python against
each. Tenant isolation is enforced at the query level, not by trusting re-verification to catch a
cross-tenant match after the fact. 200 is a starting point sized for "small per-repo cache," not a
measured value; revisit if a single repo's cache genuinely grows past that.

A hit requires cosine similarity >= 0.92 against the closest row. This starting threshold is
deliberately high: a false "similar enough" match costs nothing extra (it still has to pass full
re-verification before being served, per the data flow below), but a threshold that is too loose
would waste lookup time on candidates that were always going to fail re-verification anyway. Tune
empirically once real hit-rate data exists - the `hit_count` column exists specifically to support
that later analysis.

### Data flow (AIRview writing stage, the one consumer this phase)

1. Naming stage (unchanged) - cheap DeepSeek Flash call produces cluster names.
2. `build_evidence_packet()` assembles the packet for the cluster.
3. If `cache_eligible`: embed the packet via hosted Ollama.
4. Look up the closest cached packet for this installation+repo above a similarity threshold.
5. **Cache hit** -> re-run *both* of AIRview's existing validations against *current* evidence, not
   the evidence at cache-write time: the structured `key_symbols` match against the current brief
   (exact name+line match, from `_sanitize_written_files`/`_symbol_matches_brief`), and
   `verify_citations` against current evidence for the free-text description (file-existence
   check - this is a pre-existing limitation of `verify_citations`, not something this design
   weakens further). Both pass -> serve the cached result, the writing adapter is never called.
   Either fails -> treat as a miss.
6. **Cache miss** (not eligible, no match, or failed re-verification) -> TOON-encode the packet,
   call the tier-routed writing adapter exactly as today, validate the fresh result the same way
   it is validated today, then write packet + embedding + result to the cache.
7. Store to `wiki_subsystems` as today.

## Security

- Cache lookups are always scoped to `installation_id` at the query level - never a candidate
  match across tenants, independent of similarity score or post-hoc verification.
- A cache hit is never served without re-running both of AIRview's existing citation/symbol
  validations against current evidence - caching never lowers the bar a fresh call already has to
  clear.
- Ollama is reachable only from inside the deployment network, never exposed publicly - it never
  handles anything but embedding calls for already-derived evidence text, no raw source code.
- Any failure in the caching path (Ollama unreachable/timed out, malformed cached row, failed
  re-verification) degrades to the pre-existing fresh-call behavior. Caching must never be able to
  block or break a build.

## Expected Implementation Order

1. `evidence_packet.py` schema + `build_evidence_packet()`, unit tested against fixture evidence.
2. TOON round-trip test for the packet shape.
3. Hosted Ollama container in `docker-compose.yml`, model pulled on startup.
4. `evidence_packet_cache` migration.
5. `packet_cache.py`: embedding call, similarity lookup, dual re-verification, write-back - unit
   tested with hand-crafted fake vectors, no real Ollama required in CI.
6. Wire into AIRview's writing stage (`live_wiki.py` / `jobs.py`) behind `cache_eligible=True`.
7. End-to-end test: second build of a similar cluster skips the writing-adapter call
   (assert call count is zero).
8. Tenant isolation test: two installations with near-identical evidence never cross-match.
9. Deploy, verify a real repeated AIRview build actually skips a model call in production logs.

## Success Criteria

- A second AIRview build of a near-identical cluster serves from cache and makes zero calls to the
  tier-routed writing adapter.
- Every cache hit re-passes the same validation a fresh call would have to pass, against current
  evidence, not stale evidence from cache-write time.
- A cache lookup for one installation never returns another installation's cached row.
- Ollama being down, slow, or returning a bad response never blocks or fails an AIRview build - it
  only forces a fresh (slightly more expensive) call.
- Existing AIRview tests and behavior are unchanged when nothing is cache-eligible or nothing
  matches.
- `managed_audit.py` and `flash_review.py` are untouched by this phase.
