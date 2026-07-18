# OpenAI Embedding Fallback Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** When Ollama's embedding endpoint is unreachable, `embed_texts` falls back to OpenAI's
`text-embedding-3-small` API if `OPENAI_API_KEY` is configured - gated behind an explicit,
every-single-time consent prompt in interactive contexts, and refused outright (never silently
used) in non-interactive contexts like the MCP server.

**Architecture:** A single function (`embed_texts` in `prototype/aletheore/search_index.py`)
gains a try-Ollama-then-fallback-to-OpenAI path, reusing the existing `credentials.py`
(`has_api_key`/`get_api_key`) and the same `OpenAI` client class already imported. No new files,
no new CLI flags, no changes to `build_index`/`search_index`'s public signatures.

**Tech Stack:** Python 3.11+ stdlib + the existing `openai` package already a dependency;
`pytest` with `unittest.mock.patch`/`MagicMock`, matching `test_search_index.py`'s existing style.

## Global Constraints

- `embed_texts`'s existing Ollama-success path and signature stay unchanged - every current
  caller and test not related to the failure path continues to work identically.
- The OpenAI fallback is only ever attempted when `OPENAI_API_KEY` is configured (env var or
  saved credential via `credentials.py`) - never attempted with no key.
- The OpenAI fallback is only ever attempted when `sys.stdin.isatty()` is true - never in a
  non-interactive/MCP context, regardless of whether a key is configured.
- Consent is asked fresh every call, never cached/remembered - matching `_audit`'s existing
  `requires_consent` pattern in `cli.py`.
- No new ecosystem/provider beyond OpenAI - Anthropic has no embeddings API, so no Claude
  fallback is added.

---

### Task 1: Add the OpenAI fallback path to `embed_texts`

**Files:**
- Modify: `prototype/aletheore/search_index.py`
- Test: `prototype/tests/test_search_index.py`

**Interfaces:**
- Produces: `embed_texts(texts: list[str], base_url: str = DEFAULT_EMBEDDING_BASE_URL, model:
  str = DEFAULT_EMBEDDING_MODEL, credentials_path: Path = DEFAULT_CREDENTIALS_PATH, confirm_fn:
  Callable[[], bool] | None = None) -> list[list[float]]` - three new keyword-only-by-convention
  parameters added with defaults, so every existing call site (`build_index`'s
  `embed_texts([chunk["text"] for chunk in chunks])`, `search_index`'s `embed_texts([query_text])[0]`)
  keeps working with zero changes.
- Consumes: `aletheore.credentials.has_api_key`, `aletheore.credentials.get_api_key`,
  `aletheore.credentials.DEFAULT_CREDENTIALS_PATH` (all already exist, used by
  `aletheore/adapters/openai_compatible.py` today).

- [ ] **Step 1: Write the failing test for "no OpenAI key configured" (today's unchanged behavior)**

Add to `prototype/tests/test_search_index.py`:

```python
@patch("aletheore.search_index.has_api_key", return_value=False)
@patch("aletheore.search_index.OpenAI")
def test_embed_texts_raises_ollama_error_when_no_openai_key_configured(
    mock_openai_class, mock_has_api_key, tmp_path
):
    mock_client = MagicMock()
    mock_openai_class.return_value = mock_client
    mock_client.embeddings.create.side_effect = RuntimeError("connection refused")

    with pytest.raises(EmbeddingProviderUnavailableError, match="ollama pull nomic-embed-text"):
        embed_texts(["chunk one"], credentials_path=tmp_path / "credentials.json")

    mock_has_api_key.assert_called_once_with(
        "OPENAI_API_KEY", "OpenAI", tmp_path / "credentials.json"
    )
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd prototype && python -m pytest tests/test_search_index.py -k no_openai_key -v`
Expected: FAIL - `has_api_key` isn't imported/called in `search_index.py` yet, so the mock target
doesn't exist (`AttributeError` or the mock patch fails to apply).

- [ ] **Step 3: Write the failing test for the successful OpenAI fallback**

```python
@patch("aletheore.search_index.sys")
@patch("aletheore.search_index.get_api_key", return_value="sk-test-key")
@patch("aletheore.search_index.has_api_key", return_value=True)
@patch("aletheore.search_index.OpenAI")
def test_embed_texts_falls_back_to_openai_when_ollama_unavailable(
    mock_openai_class, mock_has_api_key, mock_get_api_key, mock_sys, tmp_path
):
    mock_sys.stdin.isatty.return_value = True

    ollama_client = MagicMock()
    ollama_client.embeddings.create.side_effect = RuntimeError("connection refused")
    openai_client = MagicMock()
    openai_client.embeddings.create.return_value = MagicMock(
        data=[MagicMock(embedding=[0.5, 0.6])]
    )
    mock_openai_class.side_effect = [ollama_client, openai_client]

    confirm_fn = MagicMock(return_value=True)

    result = embed_texts(
        ["chunk one"], credentials_path=tmp_path / "credentials.json", confirm_fn=confirm_fn
    )

    assert result == [[0.5, 0.6]]
    confirm_fn.assert_called_once()
    openai_call = openai_client.embeddings.create.call_args
    assert openai_call.kwargs["model"] == "text-embedding-3-small"
    assert openai_call.kwargs["input"] == ["chunk one"]
    second_client_call = mock_openai_class.call_args_list[1]
    assert second_client_call.kwargs["base_url"] == "https://api.openai.com/v1"
    assert second_client_call.kwargs["api_key"] == "sk-test-key"
```

- [ ] **Step 4: Write the failing test for declined consent**

```python
@patch("aletheore.search_index.sys")
@patch("aletheore.search_index.get_api_key", return_value="sk-test-key")
@patch("aletheore.search_index.has_api_key", return_value=True)
@patch("aletheore.search_index.OpenAI")
def test_embed_texts_raises_when_openai_fallback_declined(
    mock_openai_class, mock_has_api_key, mock_get_api_key, mock_sys, tmp_path
):
    mock_sys.stdin.isatty.return_value = True
    ollama_client = MagicMock()
    ollama_client.embeddings.create.side_effect = RuntimeError("connection refused")
    mock_openai_class.return_value = ollama_client

    confirm_fn = MagicMock(return_value=False)

    with pytest.raises(EmbeddingProviderUnavailableError, match="declined"):
        embed_texts(
            ["chunk one"], credentials_path=tmp_path / "credentials.json", confirm_fn=confirm_fn
        )

    confirm_fn.assert_called_once()
    assert mock_openai_class.call_count == 1  # only the Ollama client was ever built
```

- [ ] **Step 5: Write the failing test for the non-interactive/MCP refusal**

```python
@patch("aletheore.search_index.sys")
@patch("aletheore.search_index.get_api_key", return_value="sk-test-key")
@patch("aletheore.search_index.has_api_key", return_value=True)
@patch("aletheore.search_index.OpenAI")
def test_embed_texts_refuses_fallback_when_not_interactive(
    mock_openai_class, mock_has_api_key, mock_get_api_key, mock_sys, tmp_path
):
    mock_sys.stdin.isatty.return_value = False
    ollama_client = MagicMock()
    ollama_client.embeddings.create.side_effect = RuntimeError("connection refused")
    mock_openai_class.return_value = ollama_client

    with pytest.raises(EmbeddingProviderUnavailableError, match="interactive"):
        embed_texts(["chunk one"], credentials_path=tmp_path / "credentials.json")

    assert mock_openai_class.call_count == 1  # never built a second (OpenAI) client
    mock_get_api_key.assert_not_called()
```

- [ ] **Step 6: Write the failing test for both providers failing**

```python
@patch("aletheore.search_index.sys")
@patch("aletheore.search_index.get_api_key", return_value="sk-test-key")
@patch("aletheore.search_index.has_api_key", return_value=True)
@patch("aletheore.search_index.OpenAI")
def test_embed_texts_names_both_failures_when_openai_also_fails(
    mock_openai_class, mock_has_api_key, mock_get_api_key, mock_sys, tmp_path
):
    mock_sys.stdin.isatty.return_value = True
    ollama_client = MagicMock()
    ollama_client.embeddings.create.side_effect = RuntimeError("connection refused")
    openai_client = MagicMock()
    openai_client.embeddings.create.side_effect = RuntimeError("invalid api key")
    mock_openai_class.side_effect = [ollama_client, openai_client]

    with pytest.raises(EmbeddingProviderUnavailableError, match="Ollama unavailable.*OpenAI"):
        embed_texts(
            ["chunk one"],
            credentials_path=tmp_path / "credentials.json",
            confirm_fn=lambda: True,
        )
```

- [ ] **Step 7: Run all five new tests to confirm they fail**

Run: `cd prototype && python -m pytest tests/test_search_index.py -k "openai or interactive or declined or both_failures" -v`
Expected: all FAIL (function doesn't have the new behavior yet).

- [ ] **Step 8: Implement the fallback in `search_index.py`**

Add near the top of `prototype/aletheore/search_index.py`, alongside the existing imports:

```python
import sys

from aletheore.credentials import DEFAULT_CREDENTIALS_PATH, get_api_key, has_api_key
```

Add new constants next to `DEFAULT_EMBEDDING_BASE_URL`/`DEFAULT_EMBEDDING_MODEL`:

```python
OPENAI_EMBEDDING_BASE_URL = "https://api.openai.com/v1"
OPENAI_EMBEDDING_MODEL = "text-embedding-3-small"
```

Add a default confirm function and replace `embed_texts`:

```python
def _default_confirm_openai_fallback() -> bool:
    print(
        "Ollama is unavailable. Aletheore can fall back to OpenAI's "
        f"'{OPENAI_EMBEDDING_MODEL}' embeddings API instead - this sends this "
        "repository's source code chunks to OpenAI's API."
    )
    return input("Continue with OpenAI embeddings? [y/N]: ").strip().lower() == "y"


def embed_texts(
    texts: list[str],
    base_url: str = DEFAULT_EMBEDDING_BASE_URL,
    model: str = DEFAULT_EMBEDDING_MODEL,
    credentials_path: Path = DEFAULT_CREDENTIALS_PATH,
    confirm_fn: Callable[[], bool] | None = None,
) -> list[list[float]]:
    client = OpenAI(base_url=base_url, api_key="not-needed")
    try:
        response = client.embeddings.create(model=model, input=texts)
        return [item.embedding for item in response.data]
    except Exception as ollama_exc:
        ollama_hint = (
            f"could not reach embedding model '{model}' at {base_url} "
            f"({type(ollama_exc).__name__}) - try 'ollama pull {model}' and confirm "
            "ollama is running"
        )
        if not has_api_key("OPENAI_API_KEY", "OpenAI", credentials_path):
            raise EmbeddingProviderUnavailableError(ollama_hint) from ollama_exc

        if not sys.stdin.isatty():
            raise EmbeddingProviderUnavailableError(
                f"{ollama_hint}. An OPENAI_API_KEY is configured and could be used as a "
                "fallback, but this isn't an interactive terminal, so Aletheore won't send "
                "code to OpenAI without being asked - run this from a real terminal to be "
                "prompted."
            ) from ollama_exc

        confirm = confirm_fn if confirm_fn is not None else _default_confirm_openai_fallback
        if not confirm():
            raise EmbeddingProviderUnavailableError(
                "Ollama is unavailable and the OpenAI embeddings fallback was declined - "
                "no data was sent."
            ) from ollama_exc

        api_key = get_api_key("OPENAI_API_KEY", "OpenAI", credentials_path)
        openai_client = OpenAI(base_url=OPENAI_EMBEDDING_BASE_URL, api_key=api_key)
        try:
            response = openai_client.embeddings.create(
                model=OPENAI_EMBEDDING_MODEL, input=texts
            )
        except Exception as openai_exc:
            raise EmbeddingProviderUnavailableError(
                f"Ollama unavailable ({type(ollama_exc).__name__}) and OpenAI embeddings "
                f"also failed ({type(openai_exc).__name__}) - confirm ollama is running or "
                "OPENAI_API_KEY is valid"
            ) from openai_exc
        return [item.embedding for item in response.data]
```

Add `from collections.abc import Callable` to the imports if not already present (check the top
of the file first - `credentials.py` already imports it this way).

- [ ] **Step 9: Run all new tests to verify they pass**

Run: `cd prototype && python -m pytest tests/test_search_index.py -v`
Expected: all tests PASS, including every pre-existing test in the file (the Ollama-success path
and `build_index`/`open_index` tests are untouched by this change).

- [ ] **Step 10: Run the full test suite**

Run: `cd prototype && python -m pytest tests/ -v`
Expected: all tests PASS - no other module imports or calls `embed_texts` in a way this change
could break (confirmed: only `build_index` and `search_index` call it, both with positional
`texts` only, so the new keyword-only-by-default parameters don't affect them).

- [ ] **Step 11: Commit**

```bash
cd prototype && git add aletheore/search_index.py tests/test_search_index.py
git commit -m "feat: fall back to OpenAI embeddings when Ollama is unavailable, gated by interactive consent"
```

---

### Task 2: Update `aletheore index`'s CLI message and README

**Files:**
- Modify: `prototype/aletheore/cli.py` (the `_index` function's status line, currently
  `"Building semantic search index (embedding via local Ollama)..."`)
- Modify: `prototype/README.md` (the `aletheore index` section)

**Interfaces:**
- Consumes: nothing new - this task only updates strings, no logic changes.

- [ ] **Step 1: Update the CLI status message**

In `prototype/aletheore/cli.py`, change:

```python
console.print("Building semantic search index (embedding via local Ollama)...")
```

to:

```python
console.print("Building semantic search index (embedding via local Ollama, falling back to OpenAI if unavailable)...")
```

- [ ] **Step 2: Update the README**

In `prototype/README.md`'s `### aletheore index [path]` section, after the existing sentence
"Embeddings use local Ollama's OpenAI-compatible endpoint and the `nomic-embed-text` model.",
add:

```markdown
If Ollama is unreachable and `OPENAI_API_KEY` is configured (same lookup `audit` already uses -
environment variable first, then a saved credential), Aletheore asks for explicit confirmation
before falling back to OpenAI's `text-embedding-3-small` embeddings instead - this sends real
source code chunks to OpenAI's API, so it's never used silently and never used at all when
running non-interactively (e.g. from the MCP server).
```

- [ ] **Step 3: Run the full test suite to confirm no regression from the string changes**

Run: `cd prototype && python -m pytest tests/ -v`
Expected: all tests PASS (no test asserts the exact old CLI status string; confirm this by
grepping first: `grep -rn "embedding via local Ollama" tests/` - if a test does match the exact
old string, update that assertion to match the new one before running).

- [ ] **Step 4: Commit**

```bash
cd prototype && git add aletheore/cli.py README.md
git commit -m "docs: document the OpenAI embedding fallback in the CLI status line and README"
```
