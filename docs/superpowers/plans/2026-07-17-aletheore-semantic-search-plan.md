# Aletheore Semantic Search / RAG Q&A Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add `aletheore index` (builds a local embedded vector index over the repo's code),
`aletheore query search-codebase` (semantic retrieval), and `aletheore query answer` (retrieval
+ cited LLM answer, reusing the existing multi-provider adapter infrastructure).

**Architecture:** One new module (`aletheore/search_index.py`) handles chunking, embedding
(via Ollama's OpenAI-compatible `/v1/embeddings` endpoint, reusing the already-installed
`openai` package), and LanceDB storage/retrieval. `AgentAdapter` gains one new method,
`simple_completion(system_prompt, user_prompt, cwd) -> str`, with a sensible default in the
base class (delegates to the existing `invoke()`, correct as-is for all 6 CLI-subprocess
adapters) and a real override in the two API-based adapter classes (whose `invoke()` is
audit-locked and can't be reused for a plain completion).

**Tech Stack:** Python 3.11+, `lancedb` (new dependency), the existing `openai` package (already
a dependency) for both embeddings and, via `simple_completion`, chat completions.

## Global Constraints

- Exactly one new dependency: `lancedb`.
- **This plan requires `2026-07-17-aletheore-deterministic-evidence-enrichment-plan.md`'s Task 1
  (symbol line bounds) to be implemented and merged first** - chunking reads
  `symbols.functions`/`.classes`'s `start_line`/`end_line`, which don't exist without it.
- No API-key embedding providers in this plan - Ollama-only, matching the spec's explicit scope.
- `aletheore index` is a separate, explicit command - never triggered automatically by `scan`.
- Every new query result is TOON-encoded via the existing `to_toon()`/`_toon_result()` helpers.

---

### Task 1: `AgentAdapter.simple_completion` - base default + two real overrides

**Files:**
- Modify: `aletheore/adapters/base.py`
- Modify: `aletheore/adapters/openai_compatible.py`
- Modify: `aletheore/adapters/anthropic_native.py`
- Test: `tests/test_adapters.py`, `tests/test_openai_compatible_adapter.py`,
  `tests/test_anthropic_adapter.py`

**Interfaces:**
- Produces: `AgentAdapter.simple_completion(self, system_prompt: str, user_prompt: str, cwd: str) -> str`,
  default implementation `return self.invoke(f"{system_prompt}\n\n{user_prompt}", cwd)`.
- Produces: `OpenAICompatibleAdapter.simple_completion(...)` and
  `AnthropicAdapter.simple_completion(...)` overrides - one plain completion call, no tools, no
  loop, reusing each adapter's existing `get_api_key`/`credentials_path`/`base_url`/`model`.

- [ ] **Step 1: Write the failing tests**

```python
# append to prototype/tests/test_adapters.py
from unittest.mock import MagicMock, patch


def test_simple_completion_default_delegates_to_invoke():
    adapter = ClaudeCodeAdapter()
    with patch.object(adapter, "invoke", return_value="the answer") as mock_invoke:
        result = adapter.simple_completion("system text", "user text", cwd="/repo")
    assert result == "the answer"
    mock_invoke.assert_called_once_with("system text\n\nuser text", "/repo")
```

```python
# append to prototype/tests/test_openai_compatible_adapter.py
@patch("aletheore.adapters.openai_compatible.OpenAI")
def test_simple_completion_makes_one_plain_completion_call(mock_openai_class, tmp_path):
    mock_client = MagicMock()
    mock_openai_class.return_value = mock_client
    mock_message = MagicMock()
    mock_message.content = "a short cited answer"
    mock_message.tool_calls = None
    mock_response = MagicMock()
    mock_response.choices = [MagicMock(message=mock_message)]
    mock_client.chat.completions.create.return_value = mock_response

    adapter = _adapter(tmp_path)
    with patch("aletheore.adapters.openai_compatible.get_api_key", return_value="sk-test"):
        result = adapter.simple_completion("system text", "user text", cwd="/repo")

    assert result == "a short cited answer"
    call = mock_client.chat.completions.create.call_args
    assert call.kwargs["messages"] == [
        {"role": "system", "content": "system text"},
        {"role": "user", "content": "user text"},
    ]
    assert "tools" not in call.kwargs
```

```python
# append to prototype/tests/test_anthropic_adapter.py
@patch("aletheore.adapters.anthropic_native.Anthropic")
def test_simple_completion_makes_one_plain_completion_call(mock_anthropic_class, tmp_path):
    mock_client = MagicMock()
    mock_anthropic_class.return_value = mock_client
    text_block = MagicMock()
    text_block.type = "text"
    text_block.text = "a short cited answer"
    mock_response = MagicMock()
    mock_response.content = [text_block]
    mock_client.messages.create.return_value = mock_response

    adapter = _adapter(tmp_path)
    with patch("aletheore.adapters.anthropic_native.get_api_key", return_value="sk-ant-test"):
        result = adapter.simple_completion("system text", "user text", cwd="/repo")

    assert result == "a short cited answer"
    call = mock_client.messages.create.call_args
    assert call.kwargs["system"] == "system text"
    assert call.kwargs["messages"] == [{"role": "user", "content": "user text"}]
    assert "tools" not in call.kwargs
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd prototype && python -m pytest tests/test_adapters.py tests/test_openai_compatible_adapter.py tests/test_anthropic_adapter.py -k simple_completion -v`
Expected: FAIL - `AttributeError: 'ClaudeCodeAdapter' object has no attribute 'simple_completion'`

- [ ] **Step 3: Implement the base default**

```python
# aletheore/adapters/base.py - add to AgentAdapter
    def simple_completion(self, system_prompt: str, user_prompt: str, cwd: str) -> str:
        return self.invoke(f"{system_prompt}\n\n{user_prompt}", cwd)
```

- [ ] **Step 4: Implement the `OpenAICompatibleAdapter` override**

```python
# aletheore/adapters/openai_compatible.py - add as a new method on OpenAICompatibleAdapter
    def simple_completion(self, system_prompt: str, user_prompt: str, cwd: str) -> str:
        api_key = None
        if self._needs_key:
            api_key = get_api_key(self._api_key_env_var, self.name, self._credentials_path)
            if not api_key:
                raise AdapterInvocationError(f"no API key available for {self.name}")

        client = OpenAI(base_url=self._base_url, api_key=api_key or "not-needed")
        try:
            response = client.chat.completions.create(
                model=self._model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                timeout=self._request_timeout_seconds,
            )
        except Exception as exc:
            raise AdapterInvocationError(
                f"{self.name} invocation failed: {type(exc).__name__}"
            ) from exc
        return response.choices[0].message.content or ""
```

- [ ] **Step 5: Implement the `AnthropicAdapter` override**

```python
# aletheore/adapters/anthropic_native.py - add as a new method on AnthropicAdapter
    def simple_completion(self, system_prompt: str, user_prompt: str, cwd: str) -> str:
        api_key = get_api_key("ANTHROPIC_API_KEY", self.name, self._credentials_path)
        if not api_key:
            raise AdapterInvocationError("no API key available for anthropic")

        client = Anthropic(api_key=api_key)
        try:
            response = client.messages.create(
                model=self._model,
                max_tokens=MAX_TOKENS,
                system=system_prompt,
                messages=[{"role": "user", "content": user_prompt}],
            )
        except Exception as exc:
            raise AdapterInvocationError(
                f"anthropic invocation failed: {type(exc).__name__}"
            ) from exc
        text_blocks = [b.text for b in response.content if b.type == "text"]
        return "\n".join(text_blocks)
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `cd prototype && python -m pytest tests/test_adapters.py tests/test_openai_compatible_adapter.py tests/test_anthropic_adapter.py -v`
Expected: all pass

- [ ] **Step 7: Commit**

```bash
git add aletheore/adapters/base.py aletheore/adapters/openai_compatible.py aletheore/adapters/anthropic_native.py tests/test_adapters.py tests/test_openai_compatible_adapter.py tests/test_anthropic_adapter.py
git commit -m "feat: add simple_completion to AgentAdapter for non-audit LLM calls"
```

---

### Task 2: Chunking, embedding, and LanceDB storage (`aletheore/search_index.py`)

**Files:**
- Create: `aletheore/search_index.py`
- Modify: `prototype/pyproject.toml`
- Test: `tests/test_search_index.py`

**Interfaces:**
- Consumes: `repository.modules[].symbols.functions`/`.classes` (with `start_line`/`end_line`
  from the deterministic-enrichment plan's Task 1).
- Produces: `build_chunks(evidence: dict, repo_path: Path) -> list[dict]`, each chunk
  `{"module_path": str, "symbol_name": str | None, "start_line": int, "end_line": int, "language": str, "text": str}`.
- Produces: `embed_texts(texts: list[str], base_url: str = "http://localhost:11434/v1", model: str = "nomic-embed-text") -> list[list[float]]`,
  raises `EmbeddingProviderUnavailableError` with an actionable message
  (`"ollama pull nomic-embed-text"`) if the model isn't reachable.
- Produces: `build_index(repo_path: Path, evidence: dict) -> int` (returns chunk count),
  `open_index(repo_path: Path)` returning the LanceDB table (raises
  `IndexNotFoundError` if `.aletheore/index.lancedb` doesn't exist), `search_index(repo_path: Path, query_text: str, k: int = 10) -> list[dict]`.

- [ ] **Step 1: Write the failing tests for chunking**

```python
# prototype/tests/test_search_index.py
from pathlib import Path
from unittest.mock import patch

import pytest

from aletheore.search_index import build_chunks


def _evidence_with_module(module_path, functions, classes=None):
    return {
        "repository": {
            "modules": [
                {
                    "path": module_path,
                    "language": "python",
                    "symbols": {"functions": functions, "classes": classes or []},
                }
            ]
        }
    }


def test_build_chunks_slices_real_source_per_symbol(tmp_path):
    (tmp_path / "app.py").write_text("x = 1\ndef greet():\n    return 'hi'\n")
    evidence = _evidence_with_module(
        "app.py", [{"name": "greet", "start_line": 2, "end_line": 3}]
    )

    chunks = build_chunks(evidence, tmp_path)

    assert len(chunks) == 1
    chunk = chunks[0]
    assert chunk["module_path"] == "app.py"
    assert chunk["symbol_name"] == "greet"
    assert chunk["start_line"] == 2
    assert chunk["end_line"] == 3
    assert "app.py::greet" in chunk["text"]
    assert "def greet():" in chunk["text"]


def test_build_chunks_falls_back_to_whole_file_when_no_symbols(tmp_path):
    (tmp_path / "config.py").write_text("SETTING = 1\n")
    evidence = _evidence_with_module("config.py", [])

    chunks = build_chunks(evidence, tmp_path)

    assert len(chunks) == 1
    assert chunks[0]["symbol_name"] is None
    assert "SETTING = 1" in chunks[0]["text"]


def test_build_chunks_skips_module_when_file_missing_on_disk(tmp_path):
    evidence = _evidence_with_module(
        "gone.py", [{"name": "f", "start_line": 1, "end_line": 1}]
    )
    chunks = build_chunks(evidence, tmp_path)
    assert chunks == []
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd prototype && python -m pytest tests/test_search_index.py -k build_chunks -v`
Expected: FAIL - `ModuleNotFoundError: No module named 'aletheore.search_index'`

- [ ] **Step 3: Implement chunking**

```python
# prototype/aletheore/search_index.py
from pathlib import Path

FALLBACK_CHUNK_MAX_LINES = 200


class EmbeddingProviderUnavailableError(Exception):
    pass


class IndexNotFoundError(Exception):
    pass


def build_chunks(evidence: dict, repo_path: Path) -> list[dict]:
    chunks: list[dict] = []
    for module in evidence["repository"]["modules"]:
        module_path = module["path"]
        file_path = repo_path / module_path
        if not file_path.exists():
            continue
        try:
            lines = file_path.read_text(encoding="utf-8", errors="ignore").splitlines()
        except OSError:
            continue

        symbols = module["symbols"]["functions"] + module["symbols"]["classes"]
        if not symbols:
            snippet = "\n".join(lines[:FALLBACK_CHUNK_MAX_LINES])
            chunks.append({
                "module_path": module_path,
                "symbol_name": None,
                "start_line": 1,
                "end_line": min(len(lines), FALLBACK_CHUNK_MAX_LINES),
                "language": module.get("language", "unknown"),
                "text": f"{module_path} (no extracted symbols)\n{snippet}",
            })
            continue

        for symbol in symbols:
            source = "\n".join(lines[symbol["start_line"] - 1 : symbol["end_line"]])
            header = f"{module_path}::{symbol['name']} ({module.get('language', 'unknown')})"
            chunks.append({
                "module_path": module_path,
                "symbol_name": symbol["name"],
                "start_line": symbol["start_line"],
                "end_line": symbol["end_line"],
                "language": module.get("language", "unknown"),
                "text": f"{header}\n{source}",
            })

    return chunks
```

- [ ] **Step 4: Run chunking tests to verify they pass**

Run: `cd prototype && python -m pytest tests/test_search_index.py -v`
Expected: all pass

- [ ] **Step 5: Write the failing tests for embedding**

```python
# append to prototype/tests/test_search_index.py
from unittest.mock import MagicMock

from aletheore.search_index import EmbeddingProviderUnavailableError, embed_texts


@patch("aletheore.search_index.OpenAI")
def test_embed_texts_returns_one_vector_per_input(mock_openai_class):
    mock_client = MagicMock()
    mock_openai_class.return_value = mock_client
    mock_client.embeddings.create.return_value = MagicMock(
        data=[MagicMock(embedding=[0.1, 0.2]), MagicMock(embedding=[0.3, 0.4])]
    )

    result = embed_texts(["chunk one", "chunk two"])

    assert result == [[0.1, 0.2], [0.3, 0.4]]
    call = mock_client.embeddings.create.call_args
    assert call.kwargs["input"] == ["chunk one", "chunk two"]
    assert call.kwargs["model"] == "nomic-embed-text"


@patch("aletheore.search_index.OpenAI")
def test_embed_texts_raises_actionable_error_when_model_unavailable(mock_openai_class):
    mock_client = MagicMock()
    mock_openai_class.return_value = mock_client
    mock_client.embeddings.create.side_effect = RuntimeError("model not found")

    with pytest.raises(EmbeddingProviderUnavailableError, match="ollama pull nomic-embed-text"):
        embed_texts(["chunk one"])
```

- [ ] **Step 6: Run tests to verify they fail**

Run: `cd prototype && python -m pytest tests/test_search_index.py -k embed_texts -v`
Expected: FAIL - `ImportError: cannot import name 'embed_texts'`

- [ ] **Step 7: Implement embedding**

```python
# prototype/aletheore/search_index.py - add imports and function
from openai import OpenAI

DEFAULT_EMBEDDING_BASE_URL = "http://localhost:11434/v1"
DEFAULT_EMBEDDING_MODEL = "nomic-embed-text"


def embed_texts(
    texts: list[str],
    base_url: str = DEFAULT_EMBEDDING_BASE_URL,
    model: str = DEFAULT_EMBEDDING_MODEL,
) -> list[list[float]]:
    client = OpenAI(base_url=base_url, api_key="not-needed")
    try:
        response = client.embeddings.create(model=model, input=texts)
    except Exception as exc:
        raise EmbeddingProviderUnavailableError(
            f"could not reach embedding model '{model}' at {base_url} "
            f"({type(exc).__name__}) - try 'ollama pull {model}' and confirm "
            "ollama is running"
        ) from exc
    return [item.embedding for item in response.data]
```

- [ ] **Step 8: Run tests to verify they pass**

Run: `cd prototype && python -m pytest tests/test_search_index.py -v`
Expected: all pass

- [ ] **Step 9: Write the failing tests for index build/search**

```python
# append to prototype/tests/test_search_index.py
from aletheore.search_index import IndexNotFoundError, build_index, open_index, search_index


@patch("aletheore.search_index.embed_texts")
def test_build_index_creates_lancedb_table(mock_embed_texts, tmp_path):
    (tmp_path / "app.py").write_text("def greet():\n    return 'hi'\n")
    evidence = _evidence_with_module(
        "app.py", [{"name": "greet", "start_line": 1, "end_line": 2}]
    )
    mock_embed_texts.return_value = [[0.1, 0.2]]

    count = build_index(tmp_path, evidence)

    assert count == 1
    assert (tmp_path / ".aletheore" / "index.lancedb").exists()


def test_open_index_raises_when_missing(tmp_path):
    with pytest.raises(IndexNotFoundError):
        open_index(tmp_path)


@patch("aletheore.search_index.embed_texts")
def test_search_index_returns_ranked_results(mock_embed_texts, tmp_path):
    (tmp_path / "auth.py").write_text("def login():\n    return True\n")
    (tmp_path / "math.py").write_text("def add(a, b):\n    return a + b\n")
    evidence = {
        "repository": {
            "modules": [
                {
                    "path": "auth.py", "language": "python",
                    "symbols": {"functions": [{"name": "login", "start_line": 1, "end_line": 2}], "classes": []},
                },
                {
                    "path": "math.py", "language": "python",
                    "symbols": {"functions": [{"name": "add", "start_line": 1, "end_line": 2}], "classes": []},
                },
            ]
        }
    }
    # first two calls embed the two chunks during build_index, third embeds the query
    mock_embed_texts.side_effect = [[[0.9, 0.1], [0.1, 0.9]], [[0.85, 0.15]]]

    build_index(tmp_path, evidence)
    results = search_index(tmp_path, "how does authentication work", k=1)

    assert len(results) == 1
    assert results[0]["module_path"] == "auth.py"
    assert results[0]["symbol_name"] == "login"
    assert "score" in results[0]
```

- [ ] **Step 10: Run tests to verify they fail**

Run: `cd prototype && python -m pytest tests/test_search_index.py -k "build_index or open_index or search_index" -v`
Expected: FAIL - `ImportError`

- [ ] **Step 11: Implement index build/open/search**

```python
# prototype/aletheore/search_index.py - add import and functions
import lancedb

INDEX_DIRNAME = "index.lancedb"
TABLE_NAME = "chunks"


def _index_path(repo_path: Path) -> Path:
    return repo_path / ".aletheore" / INDEX_DIRNAME


def build_index(repo_path: Path, evidence: dict) -> int:
    chunks = build_chunks(evidence, repo_path)
    if not chunks:
        return 0

    vectors = embed_texts([c["text"] for c in chunks])
    rows = [{**chunk, "vector": vector} for chunk, vector in zip(chunks, vectors)]

    index_path = _index_path(repo_path)
    index_path.parent.mkdir(parents=True, exist_ok=True)
    db = lancedb.connect(str(index_path))
    db.create_table(TABLE_NAME, data=rows, mode="overwrite")
    return len(rows)


def open_index(repo_path: Path):
    index_path = _index_path(repo_path)
    if not index_path.exists():
        raise IndexNotFoundError(
            f"no index found at {index_path} - run 'aletheore index {repo_path}' first"
        )
    db = lancedb.connect(str(index_path))
    return db.open_table(TABLE_NAME)


def search_index(repo_path: Path, query_text: str, k: int = 10) -> list[dict]:
    table = open_index(repo_path)
    query_vector = embed_texts([query_text])[0]
    raw_results = table.search(query_vector).limit(k).to_list()
    return [
        {
            "module_path": r["module_path"],
            "symbol_name": r["symbol_name"],
            "start_line": r["start_line"],
            "end_line": r["end_line"],
            "language": r["language"],
            "text": r["text"],
            "score": r.get("_distance"),
        }
        for r in raw_results
    ]
```

(LanceDB's `.search(vector).limit(k).to_list()` result rows include a reserved `_distance`
field for vector search automatically - confirm this exact field name against the real
installed `lancedb` version at implementation time rather than trust it blindly; some versions
call it `_distance`, and it is *lower is more similar* for the default L2 metric, not higher -
get this right before wiring the confidence gate in Task 4, since an inverted comparison there
would silently do the opposite of what's intended.)

- [ ] **Step 12: Run tests to verify they pass**

Run: `cd prototype && python -m pytest tests/test_search_index.py -v`
Expected: all pass

- [ ] **Step 13: Add the dependency**

```toml
# prototype/pyproject.toml - add to the existing dependencies list
    "lancedb>=0.15,<1.0",
```

- [ ] **Step 14: Run the full suite**

Run: `cd prototype && python -m pytest -q`
Expected: all pass

- [ ] **Step 15: Commit**

```bash
git add aletheore/search_index.py prototype/pyproject.toml tests/test_search_index.py
git commit -m "feat: chunking, embedding, and LanceDB index build/search"
```

---

### Task 3: `aletheore index` CLI command

**Files:**
- Modify: `aletheore/cli.py`
- Test: `tests/test_cli.py`

**Interfaces:**
- Consumes: `build_index` (Task 2).

- [ ] **Step 1: Write the failing test**

```python
# append to prototype/tests/test_cli.py
def test_index_command_builds_index_from_existing_evidence(tmp_path):
    repo = tmp_path
    (repo / "app.py").write_text("def greet():\n    return 'hi'\n")
    result = runner.invoke(app, ["scan", str(repo)])
    assert result.exit_code == 0

    with patch("aletheore.cli.build_index", return_value=3) as mock_build:
        result = runner.invoke(app, ["index", str(repo)])

    assert result.exit_code == 0
    assert "3" in result.output
    mock_build.assert_called_once()


def test_index_command_fails_clearly_without_prior_scan(tmp_path):
    repo = tmp_path
    result = runner.invoke(app, ["index", str(repo)])
    assert result.exit_code == 1
    assert "scan" in result.output.lower()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd prototype && python -m pytest tests/test_cli.py -k index_command -v`
Expected: FAIL - no `index` command registered

- [ ] **Step 3: Implement**

```python
# aletheore/cli.py - add import
from aletheore.search_index import build_index

# new command, alongside the existing scan/audit/query/diff commands
@app.command(help="build a local semantic search index over the repository's code")
def index(path: str = typer.Argument(".", help="repository path")) -> None:
    evidence_path = Path(path) / ".aletheore" / "evidence.json"
    if not evidence_path.exists():
        console.print(f"[bold red]error:[/bold red] no evidence found at {evidence_path}")
        console.print(f"Run 'aletheore scan {path}' first.")
        raise typer.Exit(code=1)
    evidence = json.loads(evidence_path.read_text())
    console.print("Building semantic search index (embedding via local Ollama)...")
    count = build_index(Path(path), evidence)
    console.print(f"[green]Indexed {count} chunks.[/green]")
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd prototype && python -m pytest tests/test_cli.py -v`
Expected: all pass

- [ ] **Step 5: Commit**

```bash
git add aletheore/cli.py tests/test_cli.py
git commit -m "feat: add aletheore index CLI command"
```

---

### Task 4: `search-codebase` query - CLI and MCP

**Files:**
- Modify: `aletheore/cli.py`
- Modify: `aletheore/mcp_server.py`
- Test: `tests/test_cli.py`

**Interfaces:**
- Consumes: `search_index` (Task 2).

- [ ] **Step 1: Write the failing tests**

```python
# append to prototype/tests/test_cli.py
def test_search_codebase_command_prints_results(tmp_path):
    with patch(
        "aletheore.cli.search_index",
        return_value=[
            {"module_path": "auth.py", "symbol_name": "login", "start_line": 1, "end_line": 2, "score": 0.1}
        ],
    ):
        result = runner.invoke(app, ["query", "search-codebase", "how does auth work", str(tmp_path)])
    assert result.exit_code == 0
    assert "auth.py" in result.output
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd prototype && python -m pytest tests/test_cli.py -k search_codebase_command -v`
Expected: FAIL - no such command

- [ ] **Step 3: Implement the CLI command**

`search-codebase` and `answer` both take a free-text query argument that doesn't fit the
existing single-`target` `QUERY_FUNCTIONS` dispatch pattern used for every other `aletheore
query <kind>` lookup - the same reasoning already applied to `symbol-source` in the companion
plan. Both get their own top-level Typer commands instead of a `QUERY_FUNCTIONS` entry:

```python
# aletheore/cli.py - add import
from aletheore.search_index import IndexNotFoundError, search_index

@app.command(name="search-codebase", help="semantic search over the repository's indexed code")
def search_codebase(
    query_text: str = typer.Argument(..., help="natural language query"),
    path: str = typer.Argument(".", help="repository path"),
    k: int = typer.Option(10, help="number of results"),
) -> None:
    try:
        results = search_index(Path(path), query_text, k=k)
    except IndexNotFoundError as exc:
        console.print(f"[bold red]error:[/bold red] {exc}")
        raise typer.Exit(code=1)
    for r in results:
        console.print(
            f"[bold]{r['module_path']}"
            f"{'::' + r['symbol_name'] if r['symbol_name'] else ''}"
            f"[/bold] (lines {r['start_line']}-{r['end_line']}, score={r['score']:.4f})"
        )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd prototype && python -m pytest tests/test_cli.py -v`
Expected: all pass

- [ ] **Step 5: Wire the MCP tool**

```python
# aletheore/mcp_server.py
def _register_search_codebase_tool(mcp_instance: FastMCP, repo_path: Path) -> None:
    @mcp_instance.tool(name="aletheore_search_codebase")
    def aletheore_search_codebase(query: str, k: int = 10) -> str:
        """Semantic search over the repository's indexed code (run 'aletheore index' first)."""
        results = search_index(repo_path, query, k=k)
        return _toon_result(results)
```

Add `from aletheore.search_index import search_index` to `mcp_server.py`'s imports, and
`_register_search_codebase_tool(mcp_instance, repo_path)` to `build_server()`.

- [ ] **Step 6: Run the full suite**

Run: `cd prototype && python -m pytest -q`
Expected: all pass

- [ ] **Step 7: Commit**

```bash
git add aletheore/cli.py aletheore/mcp_server.py tests/test_cli.py
git commit -m "feat: add search-codebase query, CLI command, and MCP tool"
```

---

### Task 5: `answer` query - retrieval + confidence gate + adapter reuse

**Files:**
- Create: `aletheore/answer.py`
- Modify: `aletheore/cli.py`
- Modify: `aletheore/mcp_server.py`
- Test: `tests/test_answer.py`

**Interfaces:**
- Consumes: `search_index` (Task 2), `simple_completion` (Task 1), `KNOWN_ADAPTERS`/
  `select_adapter` (existing, from `aletheore/report.py` and `aletheore/cli.py`).
- Produces: `answer_question(repo_path: Path, question: str, adapter: AgentAdapter, k: int = 5, confidence_threshold: float = 0.5) -> dict`
  returning `{"answer": str, "cited_chunks": [str], "confidence_gated": bool}`.
- Produces: `build_server(repo_path: Path, answer_adapter: AgentAdapter | None = None) -> FastMCP`
  (modifies the existing signature - was `build_server(repo_path: Path)`; the new parameter is
  optional and defaults to `None` so every existing call site that doesn't care about `answer`
  keeps working unchanged), and `_mcp(repo_path: str, forced_agent: str | None = None) -> int`
  (same - new optional parameter, old call sites unaffected).

**Confidence gate direction, stated precisely because Task 2's implementation note flagged this
as needing real confirmation**: LanceDB's default `_distance` is L2 distance - lower means more
similar. `confidence_threshold` here is a maximum acceptable distance, not a minimum score - a
result is confident enough only when `top_result["score"] <= confidence_threshold`. Confirm this
against the real `lancedb` version installed before trusting the direction of this comparison,
per Task 2's own note.

- [ ] **Step 1: Write the failing tests**

```python
# prototype/tests/test_answer.py
from unittest.mock import MagicMock, patch

from aletheore.answer import answer_question


@patch("aletheore.answer.search_index")
def test_answer_question_calls_adapter_with_retrieved_context(mock_search_index, tmp_path):
    mock_search_index.return_value = [
        {
            "module_path": "auth.py", "symbol_name": "login", "start_line": 1, "end_line": 3,
            "language": "python", "text": "auth.py::login\ndef login():\n    return True",
            "score": 0.1,
        }
    ]
    adapter = MagicMock()
    adapter.simple_completion.return_value = "Login is handled in auth.py::login."

    result = answer_question(tmp_path, "how does login work", adapter)

    assert result["confidence_gated"] is False
    assert result["answer"] == "Login is handled in auth.py::login."
    assert "auth.py::login" in result["cited_chunks"]
    adapter.simple_completion.assert_called_once()
    call_args = adapter.simple_completion.call_args
    assert "how does login work" in call_args.args[1] or "how does login work" in call_args.kwargs.get("user_prompt", "")


@patch("aletheore.answer.search_index")
def test_answer_question_confidence_gate_skips_adapter_call(mock_search_index, tmp_path):
    mock_search_index.return_value = [
        {
            "module_path": "unrelated.py", "symbol_name": "noop", "start_line": 1, "end_line": 1,
            "language": "python", "text": "unrelated.py::noop\ndef noop(): pass",
            "score": 0.95,
        }
    ]
    adapter = MagicMock()

    result = answer_question(tmp_path, "how does login work", adapter, confidence_threshold=0.5)

    assert result["confidence_gated"] is True
    assert "not enough evidence" in result["answer"].lower()
    adapter.simple_completion.assert_not_called()


@patch("aletheore.answer.search_index")
def test_answer_question_gates_when_nothing_retrieved(mock_search_index, tmp_path):
    mock_search_index.return_value = []
    adapter = MagicMock()

    result = answer_question(tmp_path, "how does login work", adapter)

    assert result["confidence_gated"] is True
    adapter.simple_completion.assert_not_called()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd prototype && python -m pytest tests/test_answer.py -v`
Expected: FAIL - `ModuleNotFoundError: No module named 'aletheore.answer'`

- [ ] **Step 3: Implement**

```python
# prototype/aletheore/answer.py
from pathlib import Path

from aletheore.adapters.base import AgentAdapter
from aletheore.search_index import search_index

ANSWER_SYSTEM_PROMPT = """You answer questions about a specific codebase using only the code
chunks provided below. Answer in 2-5 sentences. Cite which chunk(s) you used by their
"module_path::symbol_name" label. If the provided chunks don't actually answer the question,
say so plainly rather than guessing."""


def answer_question(
    repo_path: Path,
    question: str,
    adapter: AgentAdapter,
    k: int = 5,
    confidence_threshold: float = 0.5,
) -> dict:
    results = search_index(repo_path, question, k=k)

    if not results or results[0]["score"] > confidence_threshold:
        return {
            "answer": "Not enough evidence in the indexed codebase to answer this confidently.",
            "cited_chunks": [],
            "confidence_gated": True,
        }

    context = "\n\n---\n\n".join(r["text"] for r in results)
    user_prompt = f"Question: {question}\n\nRetrieved code chunks:\n\n{context}"
    answer_text = adapter.simple_completion(ANSWER_SYSTEM_PROMPT, user_prompt, str(repo_path))

    cited_chunks = [
        f"{r['module_path']}::{r['symbol_name']}" if r["symbol_name"] else r["module_path"]
        for r in results
    ]

    return {"answer": answer_text, "cited_chunks": cited_chunks, "confidence_gated": False}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd prototype && python -m pytest tests/test_answer.py -v`
Expected: all pass

- [ ] **Step 5: Wire the CLI command**

```python
# aletheore/cli.py - add import
from aletheore.answer import answer_question
from aletheore.report import select_adapter, AmbiguousAdapterError, NoAdapterAvailableError

@app.command(help="ask a natural-language question about the repository, answered from the semantic index")
def answer(
    question: str = typer.Argument(..., help="natural language question"),
    path: str = typer.Argument(".", help="repository path"),
    forced_agent: str = typer.Option(None, "--agent", help="which provider to use"),
) -> None:
    try:
        adapter = select_adapter(
            KNOWN_ADAPTERS, forced_name=forced_agent, interactive=sys.stdin.isatty()
        )
    except (NoAdapterAvailableError, AmbiguousAdapterError) as exc:
        console.print(f"[bold red]error:[/bold red] {exc}")
        raise typer.Exit(code=1)

    if adapter.requires_consent:
        console.print(
            f"[bold yellow]This will send retrieved code chunks and your question "
            f"to {adapter.name}'s API.[/bold yellow]"
        )
        if input("Continue? [y/N]: ").strip().lower() != "y":
            console.print("Cancelled - no data was sent.")
            raise typer.Exit(code=0)

    try:
        result = answer_question(Path(path), question, adapter)
    except IndexNotFoundError as exc:
        console.print(f"[bold red]error:[/bold red] {exc}")
        raise typer.Exit(code=1)

    console.print(result["answer"])
    if result["cited_chunks"]:
        console.print(f"[dim]Cited: {', '.join(result['cited_chunks'])}[/dim]")
```

(This duplicates the exact consent-prompt wording pattern already in `_audit()` - match it
against `_audit()`'s real current wording at implementation time so the two don't drift into
inconsistent phrasing for the same underlying guarantee.)

- [ ] **Step 6: Run the full suite so far**

Run: `cd prototype && python -m pytest -q`
Expected: all pass

- [ ] **Step 7: Wire the MCP tool**

```python
# aletheore/mcp_server.py
def _register_answer_tool(mcp_instance: FastMCP, repo_path: Path, adapter: AgentAdapter) -> None:
    @mcp_instance.tool(name="aletheore_answer")
    def aletheore_answer(question: str) -> str:
        """Answer a natural-language question about this repository from the semantic index."""
        result = answer_question(repo_path, question, adapter)
        return _toon_result(result)
```

**Real decision, made here rather than left for implementation time**: confirmed by reading the
actual code (`aletheore/cli.py`), `_mcp(repo_path)`/the public `mcp` command take only a
repository path today - no provider selection happens anywhere in that startup path, and
`build_server(repo_path)` takes only `repo_path`. MCP tool calls have no interactive-prompt
affordance (unlike the CLI, there's no TTY to show a selection menu or a consent prompt to mid-
call), so provider selection for `aletheore_answer` has to be resolved once, non-interactively,
at server startup - the same rule the CLI already applies to non-interactive `audit` runs
(`--agent` required, no silent auto-pick). Concretely:

```python
# aletheore/cli.py - mcp command gains an --agent option
@app.command(help="run an MCP server scoped to a repository")
def mcp(
    path: str = typer.Argument(".", help="repository path"),
    forced_agent: str = typer.Option(
        None, "--agent", help="provider for the aletheore_answer tool (omit to disable it)"
    ),
) -> None:
    raise typer.Exit(code=_mcp(path, forced_agent))


def _mcp(repo_path: str, forced_agent: str | None = None) -> int:
    repo = Path(repo_path).resolve()
    answer_adapter = None
    if forced_agent is not None:
        try:
            answer_adapter = select_adapter(KNOWN_ADAPTERS, forced_name=forced_agent, interactive=False)
        except (NoAdapterAvailableError, AmbiguousAdapterError) as exc:
            console.print(f"[bold red]error:[/bold red] {exc}")
            return 1
    server = build_server(repo, answer_adapter=answer_adapter)
    server.run(transport="stdio")
    return 0
```

```python
# aletheore/mcp_server.py - build_server gains an optional adapter parameter;
# the tool is only registered if one was actually resolved, rather than
# registering a tool that would fail on every call
def build_server(repo_path: Path, answer_adapter: AgentAdapter | None = None) -> FastMCP:
    mcp_instance = FastMCP("aletheore")
    _register_query_wrapper_tools(mcp_instance, repo_path)
    _register_changes_tool(mcp_instance, repo_path)
    _register_neighborhood_tool(mcp_instance, repo_path)
    _register_search_tool(mcp_instance, repo_path)
    _register_scan_tool(mcp_instance, repo_path)
    _register_healthcheck_tool(mcp_instance, repo_path)
    _register_search_codebase_tool(mcp_instance, repo_path)
    if answer_adapter is not None:
        _register_answer_tool(mcp_instance, repo_path, answer_adapter)
    return mcp_instance
```

Running `aletheore mcp .` with no `--agent` simply doesn't expose `aletheore_answer` at all
(every other tool, including the new `aletheore_search_codebase`, is unaffected) - explicit and
safe, rather than a tool that's present but errors on every call.

- [ ] **Step 8: Write and pass a test for the conditional registration**

```python
# append to prototype/tests/test_mcp_server.py
from aletheore.mcp_server import build_server


def test_answer_tool_absent_without_adapter(tmp_path):
    server = build_server(tmp_path, answer_adapter=None)
    tool_names = {t.name for t in server._tool_manager.list_tools()}
    assert "aletheore_answer" not in tool_names
    assert "aletheore_search_codebase" in tool_names


def test_answer_tool_present_with_adapter(tmp_path):
    from unittest.mock import MagicMock

    server = build_server(tmp_path, answer_adapter=MagicMock())
    tool_names = {t.name for t in server._tool_manager.list_tools()}
    assert "aletheore_answer" in tool_names
```

(`server._tool_manager.list_tools()` reaches into `FastMCP`'s internals - check the real
installed `mcp` package version for its actual public introspection API before trusting this
exact attribute path; use whatever `tests/test_mcp_server.py` already does today to assert a
tool is registered, matching its existing convention rather than inventing a new one.)

Run: `cd prototype && python -m pytest tests/test_mcp_server.py -v`
Expected: all pass

- [ ] **Step 9: Run the full suite**

Run: `cd prototype && python -m pytest -q`
Expected: all pass

- [ ] **Step 10: Commit**

```bash
git add aletheore/answer.py aletheore/cli.py aletheore/mcp_server.py tests/test_answer.py tests/test_mcp_server.py
git commit -m "feat: add answer query with confidence gate, reusing adapter infrastructure"
```

---

### Task 6: Real verification against Aletheore's own repository

Not a TDD task - the same live-verification discipline used throughout this project.

- [ ] **Step 1: Real embedding verification**

```bash
ollama pull nomic-embed-text
cd prototype && python -m aletheore.cli scan .
python -m aletheore.cli index .
```

Confirm a real chunk count is reported and `.aletheore/index.lancedb` contains real data.

- [ ] **Step 2: Real retrieval quality check**

Run several real natural-language queries against Aletheore's own indexed repository
(`aletheore query search-codebase "how does the scanner detect languages" .`,
`"where are secrets found in git history"`, `"how does the audit consent prompt work"`) and
manually judge whether the top result is actually the right code - this cannot be asserted in a
unit test, it has to be read and judged.

- [ ] **Step 3: Real `answer` verification with a real local Ollama chat model**

```bash
python -m aletheore.cli answer "how does aletheore detect dead code" . --agent ollama
```

Confirm the answer is real, cites a real chunk, and isn't hallucinated - cross-check the cited
chunk against the actual file.

- [ ] **Step 4: Confidence gate verification**

Ask a question genuinely unrelated to this repository's content (e.g. "how does this repo
process credit card payments") and confirm the confidence gate fires with the "not enough
evidence" response instead of a hallucinated answer.

- [ ] **Step 5: Verify the LanceDB `_distance` field/direction assumption from Task 2/5**

Print raw `score` values from a real `search_index` call for a clearly-relevant query versus a
clearly-irrelevant one, and confirm the relevant one has the *lower* score, matching this plan's
assumption (L2 distance, lower = more similar). If the installed `lancedb` version's real
behavior differs, fix the comparison direction in `answer_question` (Task 5) and re-verify.

## Success Criteria (from the spec, restated for final verification)

1. `aletheore index .` on a real repo produces a real, queryable LanceDB table with one chunk
   per extracted symbol plus fallback chunks for unparsed files.
2. `aletheore query search-codebase "<real question>"` returns real, relevant results ranked
   sensibly, verified by manual judgment against Aletheore's own repository.
3. `aletheore query answer "<real question>"` produces a short, cited answer that references a
   real chunk, reusing the existing `AgentAdapter`/consent/credentials infrastructure via the
   new `simple_completion` method.
4. A query with no relevant match in the repo triggers the confidence gate instead of a
   hallucinated answer, verified with a real out-of-scope question against a real index.
5. Both new query kinds are TOON-encoded, matching every other Aletheore query result.
6. Exactly one new dependency added (`lancedb`); no API key required for the default (`ollama`)
   path.
