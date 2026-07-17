# Aletheore Semantic Search / RAG Q&A Design

**Status:** Draft, pending review
**Date:** 2026-07-17

## Problem

RepoWise's `search_codebase()` (natural-language semantic search over source, via LanceDB or
pgvector) and `get_answer()` (confidence-gated, cited 2-5 sentence RAG answer) are real
capabilities Aletheore doesn't have. Everything Aletheore can query today is exact-match:
`aletheore_search` does literal/regex text search, and every other query kind looks up a
specific evidence field by exact path/name. There's no way to ask "where does this repo handle
authentication" and get a ranked, relevant answer - only ways to ask "what's in
`repository.modules[3]`."

This is architecturally different from every other Aletheore feature built so far: it's the
first evidence-adjacent feature that genuinely needs new infrastructure (a vector store and an
embedding model), not just another extension of the existing deterministic scanner. It's
deliberately a separate spec from
`2026-07-17-aletheore-deterministic-evidence-enrichment-design.md` for that reason - different
risk profile, different dependency footprint, and it has a real prerequisite on that spec's
Task 1 (exact symbol line bounds), needed to slice real source text into meaningful chunks.

## Goals

- `aletheore index [path]`: builds a local, embedded vector index over the repository's code
  (per-symbol source chunks, using exact line bounds from the deterministic-enrichment spec)
  plus module-level metadata, stored at `.aletheore/index.lancedb`.
- `aletheore query search-codebase "<natural language query>"` / `aletheore_search_codebase`
  MCP tool: ranked semantic search over that index, TOON-encoded results - RepoWise's
  `search_codebase()` equivalent, retrieval only, no LLM synthesis.
- `aletheore query answer "<question>"` / `aletheore_answer` MCP tool: retrieves the same way,
  then reuses the *existing* multi-provider `AgentAdapter` infrastructure (built for `audit`) to
  synthesize a short, cited answer from the retrieved chunks - RepoWise's `get_answer()`
  equivalent. Gated on retrieval confidence: if nothing retrieved is actually relevant, says so
  plainly instead of forcing an answer.
- Free and fully local by default: embeddings computed via a local Ollama embedding model, no
  API key required for the common case.
- All retrieval results TOON-encoded, matching every other MCP tool response in Aletheore today
  - and unlike RepoWise, whose public docs never mention TOON and describe raw context token
    counts consistent with plain JSON.

## Non-Goals

- **No API-based embedding providers in v1** (OpenAI's `text-embedding-3-small`, etc.). Scoped
  down deliberately, the same way the companion spec scoped down per-symbol unused-export
  detection: Ollama-only keeps this genuinely free and dependency-light for the common case,
  and multi-provider embedding support can be added later following the exact consent/adapter
  pattern already established for `audit`, without redesigning anything here.
- **No automatic re-indexing on every `scan`.** `aletheore index` is a separate, explicit
  command, not bundled into `scan`. `scan` stays fast, deterministic, and zero-LLM/zero-network
  (beyond the existing OSV.dev/license-registry calls it already makes) - embedding every
  symbol in a large repo is a real, possibly slow, network-dependent (to localhost Ollama)
  operation that doesn't belong silently inside the command every other Aletheore feature
  depends on staying fast.
- **No full-file semantic indexing for unparsed languages.** Per-symbol chunking only works for
  languages with a tree-sitter grammar. Files with no extracted symbols (config files, unparsed
  languages, plain scripts) get a single whole-module fallback chunk (or first 200 lines, for
  very large files) rather than being invisible to search - a real fallback, not a claim that
  every language gets equally rich search.
- **No writing back to the vector index from `audit` or any other command.** `index` is the only
  writer. Every read path (`search-codebase`, `answer`) is read-only against whatever the last
  `aletheore index` run produced - staleness is possible (same as `scan`'s evidence.json can go
  stale relative to the working tree) and is the user's responsibility to manage by re-running
  `index`, exactly like `scan`.

## Architecture

### Corpus and chunking

One chunk per extracted symbol (function or class), built by reading the real file at
`start_line`..`end_line` (from the deterministic-enrichment spec's Task 1 - **this spec
requires that one to ship first**), plus a small header giving the model something to match
against beyond raw code: `"{module_path}::{symbol_name} ({language})\n{source_text}"`. For
modules with zero extracted symbols, one fallback chunk: the first 200 lines of the file
verbatim, headed `"{module_path} (no extracted symbols)"`.

Each chunk's stored metadata: `module_path`, `symbol_name` (`null` for fallback chunks),
`start_line`, `end_line`, `language`.

### Embedding

Local-only for v1: Ollama's OpenAI-compatible `/v1/embeddings` endpoint (confirmed real,
supports the standard `dimensions`/`encoding_format` parameters), called via the *existing*
`openai` Python package already a dependency (`OpenAI(base_url="http://localhost:11434/v1",
api_key="not-needed").embeddings.create(model="nomic-embed-text", input=chunk_text)`) - no new
HTTP client, only a different endpoint on the same client already used for `audit`'s `ollama`
adapter. Default model: `nomic-embed-text` (Ollama's own standard recommendation, 768
dimensions, confirmed to outperform `text-embedding-ada-002`/`text-embedding-3-small` on
Ollama's own published benchmarks) - **not installed by default**, `aletheore index` checks for
it via the same `_local_server_reachable`-style probe pattern `OpenAICompatibleAdapter` already
uses and fails with a clear, actionable message (`ollama pull nomic-embed-text`) rather than a
confusing connection error if it's missing.

### Storage

[LanceDB](https://github.com/lancedb/lancedb) (confirmed real, embedded - no separate server
process, stores as local files, `pip install lancedb`), one table per repository at
`.aletheore/index.lancedb/`. This is the **one new dependency** this spec introduces. Chosen
over `pgvector` (RepoWise's other listed option) specifically because it requires no running
database server - consistent with Aletheore's "just works locally" positioning, the same reason
Ollama itself was chosen as the default local LLM path over anything requiring separate
infrastructure.

### Retrieval (`search-codebase`)

Embed the query text the same way chunks were embedded, run LanceDB's vector similarity search,
return the top-K (default 10) chunks ranked by similarity score, each with its metadata and a
truncated source preview. Pure retrieval - no LLM call, no consent prompt needed (nothing leaves
the machine; the embedding call itself already goes to localhost Ollama, same trust boundary
`audit --agent ollama` already has).

### RAG Q&A (`answer`)

Same retrieval, then hands the top-K chunks plus the question to **one of the existing
`AgentAdapter` implementations** (`KNOWN_ADAPTERS` - the exact same registry `audit` already
uses) to synthesize a 2-5 sentence answer citing which chunk(s) (`module_path::symbol_name`) it
drew from.

**Correction made during spec self-review, worth stating explicitly rather than silently
fixing**: this does *not* reuse `AgentAdapter.invoke()` unchanged, and an earlier draft of this
spec claimed "zero new code," which checking the real implementation showed to be wrong for
6 of the 12 adapters. `invoke(instruction, cwd)` is generically a thin subprocess wrapper for
the 6 CLI-based adapters (`instruction` really is just "the prompt," so `answer` can call it
directly with a Q&A-specific instruction, unchanged) - but for the 6 API-based/native adapters
(`OpenAICompatibleAdapter`, `AnthropicAdapter`), `invoke()` hard-codes `audit`'s own
`SYSTEM_PROMPT_TEMPLATE` and its 9-section tool-calling loop internally, regardless of what
`instruction` contains; calling it for a simple question would incorrectly trigger the full
audit contract. Real fix: both adapter classes gain one new, small method,
`simple_completion(system_prompt: str, user_prompt: str) -> str`, reusing each adapter's
*existing* client-construction and API-key logic (same `get_api_key`/`credentials_path`, same
`base_url`/`model`) but making one plain completion call with no tools and no loop. CLI-based
adapters get the same method name for a uniform call site, implemented as a one-line wrapper:
`return self.invoke(f"{system_prompt}\n\n{user_prompt}", cwd)`. This is genuinely small, targeted
new code - not a new subsystem - but it is new code, and this spec should say so accurately.
What *is* reused with zero changes:

- Provider selection (always-prompt-interactively / `--agent`-required-non-interactively).
- Per-run consent for API-based providers (an `answer` call using `--agent openai` shows the
  exact same consent prompt `audit` does, since it's the exact same `requires_consent` flag on
  the exact same adapter object).
- API key handling (`credentials.py`, unchanged).

**Confidence gate**: if the top retrieved chunk's similarity score is below a fixed threshold
(exact value tuned during implementation against real queries, not guessed here), skip the LLM
call entirely and return `"not enough evidence in the codebase to answer this confidently"` -
the same "not enough evidence" language already used throughout `audit`'s report contract,
applied here too. This is what makes the RAG answer trustworthy rather than a model asked to
sound confident regardless of whether it found anything real.

### TOON encoding

Both `search-codebase` and `answer` results go through the existing `to_toon()`/`_toon_result()`
helpers already used by every other MCP tool - no new encoding path, same pattern.

## CLI / MCP surface

| Command | MCP tool | Needs LLM adapter? | Needs consent? |
|---|---|---|---|
| `aletheore index [path]` | n/a (not exposed as an on-demand MCP tool - building the index is a deliberate, possibly slow action, not a cheap query) | No (embeddings only) | No (local Ollama only) |
| `aletheore query search-codebase "<q>"` | `aletheore_search_codebase` | No | No |
| `aletheore query answer "<q>" [--agent NAME]` | `aletheore_answer` | Yes | Only if the chosen adapter's `requires_consent` is `True` (identical rule `audit` already uses) |

## Testing Strategy

- Unit tests for chunk construction (given evidence with known symbols + a real file, confirm
  exact chunk boundaries and headers) with a fake embedding function injected (no real network
  calls in unit tests, same pattern `OpenAICompatibleAdapter`'s tests already use for
  `get_api_key`).
- Unit tests for the confidence gate (mocked low-similarity retrieval short-circuits before any
  adapter call).
- Real verification: a real local Ollama instance with `nomic-embed-text` pulled, indexing
  Aletheore's own repository, running a handful of real natural-language queries
  ("where does Aletheore check dependency licenses") and manually judging whether the top
  result is actually relevant - the only way to know if retrieval quality is any good at all,
  since that can't be asserted in a unit test.
- Real verification of `answer`: at least one real end-to-end run against a real local Ollama
  chat model, confirming the returned answer actually cites a real, relevant chunk and isn't
  hallucinated - same discipline as every other adapter-invoking feature in this project.

## Success Criteria

1. `aletheore index .` on a real repo produces a real, queryable LanceDB table with one chunk
   per extracted symbol plus fallback chunks for unparsed files.
2. `aletheore query search-codebase "<real question about this repo>"` returns real, relevant
   results ranked sensibly, verified by manual judgment against Aletheore's own repository.
3. `aletheore query answer "<real question>"` produces a short, cited answer that references a
   real chunk, reusing the existing `AgentAdapter`/consent/credentials infrastructure with zero
   new code in those systems.
4. A query with no relevant match in the repo triggers the confidence gate instead of a
   hallucinated answer, verified with a real out-of-scope question against a real index.
5. Both new query kinds are TOON-encoded, matching every other Aletheore query result.
6. Exactly one new dependency added (`lancedb`); no API key required for the default path.
