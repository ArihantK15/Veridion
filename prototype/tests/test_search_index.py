from unittest.mock import MagicMock, patch

import pytest

from aletheore.search_index import (
    EmbeddingProviderUnavailableError,
    IndexNotFoundError,
    build_chunks,
    build_index,
    embed_texts,
    open_index,
    search_index,
)


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
                    "path": "auth.py",
                    "language": "python",
                    "symbols": {
                        "functions": [{"name": "login", "start_line": 1, "end_line": 2}],
                        "classes": [],
                    },
                },
                {
                    "path": "math.py",
                    "language": "python",
                    "symbols": {
                        "functions": [{"name": "add", "start_line": 1, "end_line": 2}],
                        "classes": [],
                    },
                },
            ]
        }
    }
    mock_embed_texts.side_effect = [[[0.9, 0.1], [0.1, 0.9]], [[0.85, 0.15]]]

    build_index(tmp_path, evidence)
    results = search_index(tmp_path, "how does authentication work", k=1)

    assert len(results) == 1
    assert results[0]["module_path"] == "auth.py"
    assert results[0]["symbol_name"] == "login"
    assert "score" in results[0]
