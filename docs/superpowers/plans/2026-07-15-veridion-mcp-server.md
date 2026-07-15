# Veridion MCP Server Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Expose Veridion's evidence-query capabilities as an MCP server, so a coding agent can call tools directly (imports, ownership, search, a fresh scan, etc.) instead of shelling out to the CLI or re-reading files to rediscover facts Veridion already computed.

**Architecture:** A new `prototype/veridion/mcp_server.py` module builds a `FastMCP` instance (from the official `mcp` Python SDK) with 13 tools, all bound to one fixed repo path via closures — this file has no business logic of its own beyond `veridion_neighborhood`, `veridion_search`, and `veridion_scan`; the other 10 tools are thin wrappers around functions that already exist in `veridion/query.py` and `veridion/history.py`. A new `veridion mcp <path>` CLI subcommand constructs the server for a resolved repo path and runs it over stdio.

**Tech Stack:** Python 3.11+, the official `mcp` SDK (`FastMCP`, decorator-based tool registration, `run(transport="stdio")`) — confirmed installed locally at v1.23.3, confirmed this is a justified new dependency (building this without the official SDK means hand-rolling MCP's JSON-RPC framing, unreasonable when the official SDK exists — same reasoning already used for `tree-sitter`/`networkx`/`certifi`).

## Global Constraints

- One MCP server instance handles exactly one repo, fixed at construction/startup time — never a repo-path parameter on individual tool calls.
- No new `evidence.json` fields, no changes to any existing function in `query.py`, `history.py`, or `evidence.py` — this plan only adds new wrapper/composite code, reusing what exists.
- `veridion_search` matching is literal-substring or regex only — no semantic/embedding search.
- Every tool call reads `.veridion/evidence.json` fresh from disk on every invocation — no in-memory caching across calls, since the evidence can change mid-session (e.g. via `veridion_scan` itself, or an external `veridion scan` run).
- `get_why`/`get_risk`-style reasoning tools are explicitly out of scope — not part of any task below.

## Reference: confirmed `mcp` SDK API (verified locally against the installed v1.23.3, do not deviate from this shape)

```python
from mcp.server.fastmcp import FastMCP

mcp_instance = FastMCP("veridion")

@mcp_instance.tool()
def example_tool(x: int) -> dict:
    """Docstring becomes the tool's MCP description."""
    return {"result": x * 2}

# JSON schema for tool arguments is auto-derived from type hints - no manual schema needed.
# Tools can be registered inside a function body (closures over an outer variable work fine -
# this is how repo_path gets bound to each tool without FastMCP needing to know about it).

mcp_instance.run(transport="stdio")  # blocks, serves over stdio until the process exits
```

Client-side (for Task 6's live smoke test):
```python
from mcp import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client

server_params = StdioServerParameters(
    command="python3", args=["-m", "veridion.cli", "mcp", "/path/to/repo"]
)

async def call_one_tool():
    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            result = await session.call_tool("veridion_ownership", {})
            return result
```

---

### Task 1: Add the `mcp` dependency

**Files:**
- Modify: `prototype/pyproject.toml`

**Interfaces:**
- Produces: the `mcp` package importable from any later task's code.

- [ ] **Step 1: Add the dependency**

In `prototype/pyproject.toml`, add to the `dependencies` list (matching the existing
floor/ceiling constraint style used by `tree-sitter`/`networkx`):

```toml
dependencies = [
    "tree-sitter>=0.25,<0.26",
    "tree-sitter-python>=0.25,<0.26",
    "tree-sitter-javascript>=0.25,<0.26",
    "tree-sitter-typescript>=0.23,<0.24",
    "certifi>=2024.0.0",
    "networkx>=3.0,<4.0",
    "mcp>=1.23,<2.0",
]
```

Also add `pytest-asyncio` to `[project.optional-dependencies]`'s `dev` list — Task 2 onward
adds `async def` tests using `@pytest.mark.asyncio` (required because `FastMCP.list_tools()`
and `.call_tool()` are async methods). `pytest-asyncio` is NOT currently declared as a project
dependency anywhere — confirmed by grepping `pyproject.toml` for it and finding nothing, even
though it happens to already be installed in this particular environment. Relying on that would
be fragile for anyone running these tests in a clean environment, so it must be declared
explicitly:

```toml
[project.optional-dependencies]
dev = ["pytest>=8.0", "pytest-asyncio>=0.24"]
```

- [ ] **Step 2: Verify the editable install still works**

Run: `cd prototype && pip install -e ".[dev]" --quiet && python3 -c "from mcp.server.fastmcp import FastMCP; import pytest_asyncio; print('OK')"`
Expected: `OK`

- [ ] **Step 3: Commit**

```bash
cd prototype && git add pyproject.toml
git commit -m "chore: add mcp SDK dependency for the Veridion MCP server"
```

---

### Task 2: 10 existing-query wrapper tools

**Files:**
- Create: `prototype/veridion/mcp_server.py`
- Test: `prototype/tests/test_mcp_server.py`

**Interfaces:**
- Consumes: `QUERY_FUNCTIONS`, `ModuleNotFoundInEvidenceError`, `BranchNotFoundInEvidenceError`
  from `veridion.query` (exact shape: `QUERY_FUNCTIONS: dict[str, tuple[Callable[[dict, str |
  None], Any], bool]]`, keys are `imports`, `imported-by`, `symbols`, `branch`, `ownership`,
  `secrets`, `vulnerabilities`, `cluster`, `layer-violations`). Consumes `compute_diff`,
  `list_snapshots` from `veridion.history` (`compute_diff(old: dict, new: dict, full: bool =
  False) -> dict`, `list_snapshots(repo_path: Path) -> list[Path]`).
- Produces: `build_server(repo_path: Path) -> FastMCP` — the function every later task and
  Task 6's CLI wiring calls. Produces module-level helper `_read_evidence(repo_path: Path) ->
  dict` (raises `FileNotFoundError` with a clear message if `.veridion/evidence.json` is
  missing) used by every tool in this file.

- [ ] **Step 1: Write the failing tests**

```python
# prototype/tests/test_mcp_server.py
import json
from pathlib import Path

import pytest

from veridion.mcp_server import build_server


def make_repo_with_evidence(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    veridion_dir = repo / ".veridion"
    veridion_dir.mkdir(parents=True)
    evidence = {
        "veridion_version": "0.1.0",
        "scanned_at": "2026-07-15T10:00:00+00:00",
        "repo_path": str(repo),
        "repository": {
            "languages": [{"name": "python", "file_count": 2}],
            "modules": [
                {
                    "path": "a.py",
                    "imports": ["b.py"],
                    "imported_by": [],
                    "symbols": {"functions": ["foo"], "classes": []},
                },
                {
                    "path": "b.py",
                    "imports": [],
                    "imported_by": ["a.py"],
                    "symbols": {"functions": [], "classes": []},
                },
            ],
            "dependency_graph": {"nodes": ["a.py", "b.py"], "edges": [["a.py", "b.py"]]},
        },
        "git": {
            "branches": [{"name": "main", "ahead_of_main": 0}],
            "ownership": [{"path": "a.py", "top_author": "alice"}],
            "total_commits": 5,
        },
        "security": {
            "secrets": {
                "findings": [],
                "history_scanned_commits": 0,
                "history_findings": [],
            },
            "dependency_vulnerabilities": {"checked": True, "reason": None, "findings": []},
        },
        "architecture": {
            "clusters": [{"id": 0, "modules": ["a.py", "b.py"]}],
            "cross_cluster_edges": [],
            "layer_violations": {"convention_detected": False, "layers": [], "violations": []},
        },
    }
    (veridion_dir / "evidence.json").write_text(json.dumps(evidence))
    return repo


@pytest.mark.asyncio
async def test_build_server_registers_all_10_wrapper_tools(tmp_path):
    repo = make_repo_with_evidence(tmp_path)
    server = build_server(repo)

    tools = await server.list_tools()
    names = {t.name for t in tools}

    expected = {
        "veridion_imports",
        "veridion_imported_by",
        "veridion_symbols",
        "veridion_branch",
        "veridion_ownership",
        "veridion_secrets",
        "veridion_vulnerabilities",
        "veridion_cluster",
        "veridion_layer_violations",
        "veridion_changes",
    }
    assert expected.issubset(names)


@pytest.mark.asyncio
async def test_veridion_imports_tool_returns_correct_result(tmp_path):
    repo = make_repo_with_evidence(tmp_path)
    server = build_server(repo)

    result = await server.call_tool("veridion_imports", {"target": "a.py"})

    assert result.structuredContent == {"result": ["b.py"]}


@pytest.mark.asyncio
async def test_veridion_ownership_tool_needs_no_target(tmp_path):
    repo = make_repo_with_evidence(tmp_path)
    server = build_server(repo)

    result = await server.call_tool("veridion_ownership", {})

    assert result.structuredContent == {"result": [{"path": "a.py", "top_author": "alice"}]}


@pytest.mark.asyncio
async def test_veridion_imports_tool_raises_for_unknown_module(tmp_path):
    repo = make_repo_with_evidence(tmp_path)
    server = build_server(repo)

    result = await server.call_tool("veridion_imports", {"target": "does/not/exist.py"})

    assert result.isError is True


@pytest.mark.asyncio
async def test_veridion_changes_tool_reports_no_prior_snapshot(tmp_path):
    repo = make_repo_with_evidence(tmp_path)
    server = build_server(repo)

    result = await server.call_tool("veridion_changes", {})

    assert result.structuredContent["result"]["message"].startswith("no prior snapshot")
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd prototype && python3 -m pytest tests/test_mcp_server.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'veridion.mcp_server'`.
`pytest-asyncio` was declared as a dev dependency in Task 1 and installed via
`pip install -e ".[dev]"` — no `asyncio_mode` config is needed in
`prototype/pyproject.toml`'s `[tool.pytest.ini_options]` because every async test in this file
uses the explicit `@pytest.mark.asyncio` decorator, which `pytest-asyncio` picks up
automatically in its default "strict" mode.

- [ ] **Step 3: Write the implementation**

```python
# prototype/veridion/mcp_server.py
import json
from pathlib import Path

from mcp.server.fastmcp import FastMCP

from veridion.history import compute_diff, list_snapshots
from veridion.query import (
    BranchNotFoundInEvidenceError,
    ModuleNotFoundInEvidenceError,
    QUERY_FUNCTIONS,
)


def _read_evidence(repo_path: Path) -> dict:
    evidence_path = repo_path / ".veridion" / "evidence.json"
    if not evidence_path.exists():
        raise FileNotFoundError(
            f"no evidence found at {evidence_path} - run 'veridion scan {repo_path}' first "
            "or call the veridion_scan tool"
        )
    return json.loads(evidence_path.read_text())


_TOOL_NAME_TO_QUERY_KIND = {
    "veridion_imports": "imports",
    "veridion_imported_by": "imported-by",
    "veridion_symbols": "symbols",
    "veridion_branch": "branch",
    "veridion_ownership": "ownership",
    "veridion_secrets": "secrets",
    "veridion_vulnerabilities": "vulnerabilities",
    "veridion_cluster": "cluster",
    "veridion_layer_violations": "layer-violations",
}


def _register_query_wrapper_tools(mcp_instance: FastMCP, repo_path: Path) -> None:
    for tool_name, kind in _TOOL_NAME_TO_QUERY_KIND.items():
        func, requires_target = QUERY_FUNCTIONS[kind]

        def make_tool(func=func, requires_target=requires_target, kind=kind):
            if requires_target:
                def tool(target: str) -> dict:
                    evidence = _read_evidence(repo_path)
                    return {"result": func(evidence, target)}
            else:
                def tool() -> dict:
                    evidence = _read_evidence(repo_path)
                    return {"result": func(evidence, None)}
            return tool

        tool_func = make_tool()
        tool_func.__name__ = tool_name
        tool_func.__doc__ = f"Query '{kind}' from the scanned repository's evidence."
        mcp_instance.tool(name=tool_name)(tool_func)


def _register_changes_tool(mcp_instance: FastMCP, repo_path: Path) -> None:
    @mcp_instance.tool(name="veridion_changes")
    def veridion_changes(full: bool = False) -> dict:
        """What changed between the two most recent scans of this repo."""
        snapshots = list_snapshots(repo_path)
        if len(snapshots) < 2:
            return {"result": {"message": "no prior snapshot to compare against"}}
        try:
            old = json.loads(snapshots[-2].read_text())
        except json.JSONDecodeError:
            return {"result": {"message": f"most recent snapshot is unreadable ({snapshots[-2]})"}}
        new = json.loads(snapshots[-1].read_text())
        return {"result": compute_diff(old, new, full=full)}


def build_server(repo_path: Path) -> FastMCP:
    mcp_instance = FastMCP("veridion")
    _register_query_wrapper_tools(mcp_instance, repo_path)
    _register_changes_tool(mcp_instance, repo_path)
    return mcp_instance
```

**Note on error handling:** `ModuleNotFoundInEvidenceError`/`BranchNotFoundInEvidenceError`
raised inside a tool function propagate up through FastMCP's own call-tool handling, which
converts any raised exception into a `CallToolResult` with `isError=True` — this is FastMCP's
built-in behavior (already exercised by `test_veridion_imports_tool_raises_for_unknown_module`
above), no manual try/except needed inside the tool bodies for this case. `_read_evidence`
raising `FileNotFoundError` is handled the same way.

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd prototype && python3 -m pytest tests/test_mcp_server.py -v`
Expected: 5 passed

- [ ] **Step 5: Commit**

```bash
cd prototype && git add veridion/mcp_server.py tests/test_mcp_server.py
git commit -m "feat: add MCP server with wrapper tools for existing queries"
```

---

### Task 3: `veridion_neighborhood` composite tool

**Files:**
- Modify: `prototype/veridion/mcp_server.py`
- Modify: `prototype/tests/test_mcp_server.py`

**Interfaces:**
- Consumes: `find_imports`, `find_imported_by`, `find_cluster`, `ModuleNotFoundInEvidenceError`
  from `veridion.query` (all already imported in Task 2's file, `find_cluster` needs adding to
  the import line).
- Produces: registers `veridion_neighborhood` tool on the `FastMCP` instance inside
  `build_server`.

- [ ] **Step 1: Write the failing tests**

Append to `prototype/tests/test_mcp_server.py`:

```python
@pytest.mark.asyncio
async def test_veridion_neighborhood_combines_imports_imported_by_and_cluster(tmp_path):
    repo = make_repo_with_evidence(tmp_path)
    server = build_server(repo)

    result = await server.call_tool("veridion_neighborhood", {"target": "a.py"})

    assert result.structuredContent["result"] == {
        "target": "a.py",
        "imports": ["b.py"],
        "imported_by": [],
        "cluster": {"id": 0, "modules": ["a.py", "b.py"]},
    }


@pytest.mark.asyncio
async def test_veridion_neighborhood_cluster_is_null_when_unclustered(tmp_path):
    repo = make_repo_with_evidence(tmp_path)
    evidence_path = repo / ".veridion" / "evidence.json"
    evidence = json.loads(evidence_path.read_text())
    evidence["architecture"]["clusters"] = []
    evidence_path.write_text(json.dumps(evidence))
    server = build_server(repo)

    result = await server.call_tool("veridion_neighborhood", {"target": "a.py"})

    assert result.structuredContent["result"]["cluster"] is None


@pytest.mark.asyncio
async def test_veridion_neighborhood_raises_for_unknown_module(tmp_path):
    repo = make_repo_with_evidence(tmp_path)
    server = build_server(repo)

    result = await server.call_tool("veridion_neighborhood", {"target": "does/not/exist.py"})

    assert result.isError is True
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd prototype && python3 -m pytest tests/test_mcp_server.py -v -k neighborhood`
Expected: FAIL — `veridion_neighborhood` tool not found (error calling unknown tool).

- [ ] **Step 3: Write the implementation**

In `prototype/veridion/mcp_server.py`, update the import line to add `find_cluster`,
`find_imported_by`, `find_imports`:

```python
from veridion.query import (
    BranchNotFoundInEvidenceError,
    ModuleNotFoundInEvidenceError,
    QUERY_FUNCTIONS,
    find_cluster,
    find_imported_by,
    find_imports,
)
```

Add this function and call it from `build_server`:

```python
def _register_neighborhood_tool(mcp_instance: FastMCP, repo_path: Path) -> None:
    @mcp_instance.tool(name="veridion_neighborhood")
    def veridion_neighborhood(target: str) -> dict:
        """A module's imports, dependents, and cluster in one call."""
        evidence = _read_evidence(repo_path)
        imports = find_imports(evidence, target)
        imported_by = find_imported_by(evidence, target)
        try:
            cluster = find_cluster(evidence, target)
        except ModuleNotFoundInEvidenceError:
            cluster = None
        return {
            "result": {
                "target": target,
                "imports": imports,
                "imported_by": imported_by,
                "cluster": cluster,
            }
        }
```

Update `build_server`:

```python
def build_server(repo_path: Path) -> FastMCP:
    mcp_instance = FastMCP("veridion")
    _register_query_wrapper_tools(mcp_instance, repo_path)
    _register_changes_tool(mcp_instance, repo_path)
    _register_neighborhood_tool(mcp_instance, repo_path)
    return mcp_instance
```

**Design note:** `find_imports`/`find_imported_by` are called first and will raise
`ModuleNotFoundInEvidenceError` themselves (propagating as a tool error) if `target` isn't a
known module at all — this is the desired "raises for unknown module" behavior. `find_cluster`
raising that same exception is caught separately and translated to `cluster: None`, since not
every module belongs to a cluster (that's a normal state, not an error) — but a target that
doesn't exist in `repository.modules` at all fails earlier at the `find_imports` call, before
`find_cluster` is ever reached.

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd prototype && python3 -m pytest tests/test_mcp_server.py -v`
Expected: all pass (8 total so far)

- [ ] **Step 5: Commit**

```bash
cd prototype && git add veridion/mcp_server.py tests/test_mcp_server.py
git commit -m "feat: add veridion_neighborhood composite MCP tool"
```

---

### Task 4: `veridion_search` tool

**Files:**
- Modify: `prototype/veridion/secrets.py` (rename `_iter_all_files` to `iter_all_files` — a
  small, directly-motivated change: this exact file-walking logic, excluding `IGNORED_DIRS`
  and skipping `BINARY_EXTENSIONS`, is what the new search tool needs, and duplicating it
  rather than reusing it would violate this codebase's own established pattern of sharing
  `IGNORED_DIRS`-based walking logic across modules)
- Modify: `prototype/veridion/mcp_server.py`
- Modify: `prototype/tests/test_mcp_server.py`

**Interfaces:**
- Consumes: `iter_all_files(repo_path: Path)` (renamed, was `_iter_all_files`) from
  `veridion.secrets`.
- Produces: registers `veridion_search` tool on the `FastMCP` instance.

**Confirmed before writing this plan:** `grep -rn "_iter_all_files" .` from `prototype/`
returns exactly two lines, both inside `veridion/secrets.py` itself (the function definition
and its one call site inside `find_secrets`) — no test file imports or references it directly,
so no test file needs updating for the rename.

- [ ] **Step 1: Confirm no other references exist before renaming**

Run: `cd prototype && grep -rn "_iter_all_files" .`
Expected: exactly 2 matches, both in `veridion/secrets.py` (matching what was confirmed above
— if this doesn't match, stop and update the additional reference too before proceeding).

- [ ] **Step 2: Write the failing tests**

Append to `prototype/tests/test_mcp_server.py`:

```python
def make_repo_with_files(tmp_path: Path, files: dict[str, str]) -> Path:
    repo = tmp_path / "search_repo"
    repo.mkdir()
    (repo / ".veridion").mkdir()
    (repo / ".veridion" / "evidence.json").write_text(
        json.dumps({"repository": {"modules": []}})
    )
    for rel_path, content in files.items():
        full_path = repo / rel_path
        full_path.parent.mkdir(parents=True, exist_ok=True)
        full_path.write_text(content)
    return repo


@pytest.mark.asyncio
async def test_veridion_search_finds_a_literal_match(tmp_path):
    repo = make_repo_with_files(
        tmp_path, {"app/main.py": "def hello():\n    return 'world'\n"}
    )
    server = build_server(repo)

    result = await server.call_tool("veridion_search", {"pattern": "def hello"})

    matches = result.structuredContent["result"]["matches"]
    assert len(matches) == 1
    assert matches[0] == {"path": "app/main.py", "line": 1, "text": "def hello():"}


@pytest.mark.asyncio
async def test_veridion_search_regex_mode(tmp_path):
    repo = make_repo_with_files(tmp_path, {"a.py": "x = 1\ny = 2\nz = 3\n"})
    server = build_server(repo)

    result = await server.call_tool(
        "veridion_search", {"pattern": r"^[xy] = \d", "regex": True}
    )

    matches = result.structuredContent["result"]["matches"]
    assert len(matches) == 2


@pytest.mark.asyncio
async def test_veridion_search_respects_path_glob(tmp_path):
    repo = make_repo_with_files(
        tmp_path,
        {"src/a.py": "TARGET\n", "tests/b.py": "TARGET\n"},
    )
    server = build_server(repo)

    result = await server.call_tool(
        "veridion_search", {"pattern": "TARGET", "path_glob": "src/*"}
    )

    matches = result.structuredContent["result"]["matches"]
    assert len(matches) == 1
    assert matches[0]["path"] == "src/a.py"


@pytest.mark.asyncio
async def test_veridion_search_ignores_ignored_dirs(tmp_path):
    repo = make_repo_with_files(
        tmp_path,
        {"node_modules/lib.js": "TARGET\n", "app.js": "TARGET\n"},
    )
    server = build_server(repo)

    result = await server.call_tool("veridion_search", {"pattern": "TARGET"})

    matches = result.structuredContent["result"]["matches"]
    assert len(matches) == 1
    assert matches[0]["path"] == "app.js"


@pytest.mark.asyncio
async def test_veridion_search_caps_at_200_and_flags_truncated(tmp_path):
    content = "\n".join(f"MATCH_ME line {i}" for i in range(250))
    repo = make_repo_with_files(tmp_path, {"big.py": content})
    server = build_server(repo)

    result = await server.call_tool("veridion_search", {"pattern": "MATCH_ME"})

    result_body = result.structuredContent["result"]
    assert len(result_body["matches"]) == 200
    assert result_body["truncated"] is True
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `cd prototype && python3 -m pytest tests/test_mcp_server.py -v -k search`
Expected: FAIL — `veridion_search` tool not found.

- [ ] **Step 4: Rename `_iter_all_files` to `iter_all_files` in `prototype/veridion/secrets.py`**

Change the function definition (currently at the top of the file) from
`def _iter_all_files(repo_path: Path):` to `def iter_all_files(repo_path: Path):`, and update
its one call site inside `find_secrets` from `_iter_all_files(repo_path)` to
`iter_all_files(repo_path)`. Update any other reference found in Step 1.

- [ ] **Step 5: Run the full existing test suite to confirm the rename didn't break anything**

Run: `cd prototype && python3 -m pytest -v`
Expected: all pass (no regressions from the rename)

- [ ] **Step 6: Write the `veridion_search` implementation**

In `prototype/veridion/mcp_server.py`, add the import:

```python
import re
from pathlib import PurePath

from veridion.secrets import iter_all_files
```

Add this function and call it from `build_server`:

```python
_SEARCH_MATCH_CAP = 200


def _register_search_tool(mcp_instance: FastMCP, repo_path: Path) -> None:
    @mcp_instance.tool(name="veridion_search")
    def veridion_search(pattern: str, regex: bool = False, path_glob: str | None = None) -> dict:
        """Deterministic literal or regex search over the repo's tracked source files."""
        compiled = re.compile(pattern) if regex else None
        matches: list[dict] = []
        truncated = False

        for path in iter_all_files(repo_path):
            rel_path = path.relative_to(repo_path).as_posix()
            if path_glob is not None and not PurePath(rel_path).match(path_glob):
                continue
            try:
                text = path.read_text(encoding="utf-8", errors="ignore")
            except OSError:
                continue
            for line_no, line in enumerate(text.splitlines(), start=1):
                found = compiled.search(line) if regex else pattern in line
                if found:
                    if len(matches) >= _SEARCH_MATCH_CAP:
                        truncated = True
                        break
                    matches.append({"path": rel_path, "line": line_no, "text": line})
            if truncated:
                break

        return {"result": {"matches": matches, "truncated": truncated}}
```

Update `build_server`:

```python
def build_server(repo_path: Path) -> FastMCP:
    mcp_instance = FastMCP("veridion")
    _register_query_wrapper_tools(mcp_instance, repo_path)
    _register_changes_tool(mcp_instance, repo_path)
    _register_neighborhood_tool(mcp_instance, repo_path)
    _register_search_tool(mcp_instance, repo_path)
    return mcp_instance
```

- [ ] **Step 7: Run tests to verify they pass**

Run: `cd prototype && python3 -m pytest tests/test_mcp_server.py -v`
Expected: all pass (13 total so far)

Run: `cd prototype && python3 -m pytest -v`
Expected: all pass, no regressions

- [ ] **Step 8: Commit**

```bash
cd prototype && git add veridion/secrets.py veridion/mcp_server.py tests/test_secrets.py tests/test_mcp_server.py
git commit -m "feat: add veridion_search MCP tool"
```

---

### Task 5: `veridion_scan` tool

**Files:**
- Modify: `prototype/veridion/mcp_server.py`
- Modify: `prototype/tests/test_mcp_server.py`

**Interfaces:**
- Consumes: `scan_repository(repo_path: Path, check_vulnerabilities: bool = True,
  scan_git_history: bool = True) -> dict` from `veridion.evidence`, `write_evidence(evidence:
  dict, repo_path: Path) -> Path` from `veridion.evidence`, `save_snapshot(evidence: dict,
  repo_path: Path, keep: int = 20) -> Path` from `veridion.history`.
- Produces: registers `veridion_scan` tool on the `FastMCP` instance.

- [ ] **Step 1: Write the failing tests**

Append to `prototype/tests/test_mcp_server.py`:

```python
import subprocess


def make_git_repo_with_source(tmp_path: Path) -> Path:
    repo = tmp_path / "git_repo"
    repo.mkdir()
    (repo / "main.py").write_text("x = 1\n")
    subprocess.run(["git", "init", "-b", "main"], cwd=repo, check=True, capture_output=True)
    subprocess.run(
        ["git", "config", "user.email", "a@example.com"], cwd=repo, check=True, capture_output=True
    )
    subprocess.run(["git", "config", "user.name", "Alice"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "add", "."], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", "init"], cwd=repo, check=True, capture_output=True)
    return repo


@pytest.mark.asyncio
async def test_veridion_scan_returns_compact_summary(tmp_path):
    repo = make_git_repo_with_source(tmp_path)
    server = build_server(repo)

    result = await server.call_tool("veridion_scan", {})

    summary = result.structuredContent["result"]
    assert summary["module_count"] == 1
    assert "scanned_at" in summary
    assert summary["secrets"] == {"total_findings": 0, "real_findings": 0, "history_findings": 0}
    assert summary["vulnerabilities"]["checked"] is True
    assert summary["layer_violations"]["convention_detected"] is False
    assert "cluster_count" in summary


@pytest.mark.asyncio
async def test_veridion_scan_writes_a_history_snapshot(tmp_path):
    repo = make_git_repo_with_source(tmp_path)
    server = build_server(repo)

    await server.call_tool("veridion_scan", {})

    history_files = list((repo / ".veridion" / "history").glob("*.json"))
    assert len(history_files) == 1


@pytest.mark.asyncio
async def test_veridion_scan_real_findings_excludes_placeholders(tmp_path):
    repo = make_git_repo_with_source(tmp_path)
    (repo / "tests").mkdir()
    (repo / "tests" / "fixture.py").write_text('AWS_KEY = "AKIAABCDEFGHIJKLMNOP"\n')
    server = build_server(repo)

    result = await server.call_tool("veridion_scan", {})

    summary = result.structuredContent["result"]
    assert summary["secrets"]["total_findings"] == 1
    assert summary["secrets"]["real_findings"] == 0
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd prototype && python3 -m pytest tests/test_mcp_server.py -v -k scan`
Expected: FAIL — `veridion_scan` tool not found.

- [ ] **Step 3: Write the implementation**

In `prototype/veridion/mcp_server.py`, add the import:

```python
from veridion.evidence import scan_repository, write_evidence
from veridion.history import save_snapshot
```

(combine with the existing `from veridion.history import compute_diff, list_snapshots` line
into one `from veridion.history import compute_diff, list_snapshots, save_snapshot`.)

Add this function and call it from `build_server`:

```python
def _register_scan_tool(mcp_instance: FastMCP, repo_path: Path) -> None:
    @mcp_instance.tool(name="veridion_scan")
    def veridion_scan() -> dict:
        """Trigger a fresh scan of this repo and return a compact summary."""
        evidence = scan_repository(repo_path)
        write_evidence(evidence, repo_path)
        save_snapshot(evidence, repo_path)

        findings = evidence["security"]["secrets"]["findings"]
        real_findings = [f for f in findings if not f.get("likely_placeholder", False)]

        return {
            "result": {
                "scanned_at": evidence["scanned_at"],
                "module_count": len(evidence["repository"]["modules"]),
                "languages": evidence["repository"]["languages"],
                "secrets": {
                    "total_findings": len(findings),
                    "real_findings": len(real_findings),
                    "history_findings": len(evidence["security"]["secrets"]["history_findings"]),
                },
                "vulnerabilities": {
                    "checked": evidence["security"]["dependency_vulnerabilities"]["checked"],
                    "finding_count": len(
                        evidence["security"]["dependency_vulnerabilities"]["findings"]
                    ),
                },
                "layer_violations": {
                    "convention_detected": evidence["architecture"]["layer_violations"][
                        "convention_detected"
                    ],
                    "violation_count": len(
                        evidence["architecture"]["layer_violations"]["violations"]
                    ),
                },
                "cluster_count": len(evidence["architecture"]["clusters"]),
            }
        }
```

Update `build_server`:

```python
def build_server(repo_path: Path) -> FastMCP:
    mcp_instance = FastMCP("veridion")
    _register_query_wrapper_tools(mcp_instance, repo_path)
    _register_changes_tool(mcp_instance, repo_path)
    _register_neighborhood_tool(mcp_instance, repo_path)
    _register_search_tool(mcp_instance, repo_path)
    _register_scan_tool(mcp_instance, repo_path)
    return mcp_instance
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd prototype && python3 -m pytest tests/test_mcp_server.py -v`
Expected: all pass (16 total so far)

Run: `cd prototype && python3 -m pytest -v`
Expected: all pass, no regressions

- [ ] **Step 5: Commit**

```bash
cd prototype && git add veridion/mcp_server.py tests/test_mcp_server.py
git commit -m "feat: add veridion_scan MCP tool"
```

---

### Task 6: `veridion mcp` CLI command and live verification

**Files:**
- Modify: `prototype/veridion/cli.py`

**Interfaces:**
- Consumes: `build_server(repo_path: Path) -> FastMCP` from `veridion.mcp_server`.

- [ ] **Step 1: Add the CLI subcommand**

In `prototype/veridion/cli.py`, add the import:

```python
from veridion.mcp_server import build_server
```

Add a new function near `_diff`:

```python
def _mcp(repo_path: str) -> int:
    repo = Path(repo_path).resolve()
    server = build_server(repo)
    server.run(transport="stdio")
    return 0
```

In `main()`, add the subparser (alongside `diff_parser`, before `args = parser.parse_args()`):

```python
    mcp_parser = subparsers.add_parser("mcp", help="run an MCP server scoped to a repository")
    mcp_parser.add_argument("path", nargs="?", default=".")
```

And in the dispatch section:

```python
    if args.command == "mcp":
        return _mcp(args.path)
```

- [ ] **Step 2: Run the full test suite**

Run: `cd prototype && python3 -m pytest -v`
Expected: all pass, no regressions from the CLI change (no new automated test needed for
`_mcp` itself — `server.run()` blocks forever serving stdio, which isn't unit-testable the same
way; it's covered by the live smoke test below instead).

- [ ] **Step 3: Commit**

```bash
cd prototype && git add veridion/cli.py
git commit -m "feat: add veridion mcp CLI command"
```

- [ ] **Step 4: Live verification — all 4 spec success criteria**

Not automated — no live agent call needed, matching the pattern used for every prior
increment's final task this session. Run each check against a real repo and record the actual
output.

**4a. All 13 tools individually callable via a real stdio connection, matching CLI output**
(Success Criterion 1):

```bash
cd prototype
python3 -m veridion.cli scan /Users/arihantkaul/proctored-browser --no-check-vulnerabilities --no-scan-git-history
python3 -c "
import asyncio
from mcp import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client

server_params = StdioServerParameters(
    command='python3', args=['-m', 'veridion.cli', 'mcp', '/Users/arihantkaul/proctored-browser']
)

async def main():
    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            tools = await session.list_tools()
            print('registered tools:', sorted(t.name for t in tools.tools))
            result = await session.call_tool('veridion_ownership', {})
            print('ownership result:', result.structuredContent)

asyncio.run(main())
"
```

Expected: 13 tool names printed, `ownership result` matches
`python3 -m veridion.cli query ownership --path /Users/arihantkaul/proctored-browser` run
separately for comparison.

**4b. `veridion_search` correctness, `IGNORED_DIRS` respected, cap+truncation on a
high-frequency term** (Success Criterion 2): run the same client pattern as above calling
`veridion_search` with a pattern known to exist in Procta's codebase (e.g. a common import
name), and separately with a deliberately common short pattern (e.g. `"import"`) to confirm
`truncated: true` and exactly 200 matches.

**4c. `veridion_scan` participates in the same history mechanism as CLI scans** (Success
Criterion 3): call `veridion_scan` via the client, then run
`python3 -m veridion.cli query changes --path /Users/arihantkaul/proctored-browser` via the CLI
separately and confirm the new snapshot is visible (i.e. `list_snapshots` picks up the
MCP-triggered scan's output, not a separate untracked file).

**4d. `veridion_neighborhood` matches the 3 individual tool calls it composes** (Success
Criterion 4): call `veridion_neighborhood` for a real module in Procta, and separately call
`veridion_imports`, `veridion_imported_by`, `veridion_cluster` for the same target — confirm
the neighborhood result's three fields exactly match the three individual results.

Record the actual output of each check when reporting completion — do not report this task
done without having run all four and inspected real output, matching the review discipline
used for every other increment this session.
