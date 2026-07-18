# AIR Expansion Phase 1: Database Model Detection Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a new `repository.database` block to AIR (`air.json`/`air.toon`) reporting ORM/database-framework usage, migration directories, and known schema files — the first of the two deterministic-friendly categories in the AIR expansion (database models now, infrastructure+environments next; threat model/business model are out of scope for evidence-block work entirely, per prior decision — they're inferential, not deterministic, and belong in the LLM-authored `Perspectives` report section instead).

**Architecture:** Mirrors `detect_ai_usage`/`detect_frameworks` in `aletheore/scanner/detect.py` exactly — dependency-manifest marker matching (already-parsed `requirements.txt`/`pyproject.toml`/`package.json` data, zero new dependencies) plus two new filesystem-existence checks (migration directories, schema files). Wires into the same five places every existing evidence block already wires into: `evidence.py`'s `scan_repository`, `query.py`'s `QUERY_FUNCTIONS`, `mcp_server.py`'s tool registry, and `openai_compatible.py`'s `EVIDENCE_SCHEMA_MAP`.

**Tech Stack:** Python 3.12, pytest, no new dependencies.

## Global Constraints

- Zero new dependencies — everything here is stdlib `pathlib`/`json`/`tomllib`, matching every existing `detect.py` function.
- File-names-only branding from the prior AIR rename stays as-is: this plan only touches `air.json`/`air.toon`'s *content* (a new key), never its filename.
- Every new fact must be a raw, citable, deterministic fact — no scores, no "quality" judgments (matches this project's standing rule, restated in the prior deterministic-evidence-enrichment spec).
- All new code lives in `prototype/aletheore/`; all paths below are relative to `prototype/` unless stated otherwise.

---

### Task 1: Add database marker dicts and generalize the marker-matching helper

**Files:**
- Modify: `aletheore/scanner/detect.py:65-92` (marker dicts), `:211-225` (`_match_ai_markers` → rename to `_match_dependency_markers`), `:228-244` (`detect_ai_usage`'s four call sites)
- Test: `tests/test_detect.py`

**Interfaces:**
- Produces: `_match_dependency_markers(pip_markers: dict[str, str], js_markers: dict[str, str], pip_lines: list[tuple[str, str, str]], npm_deps: dict[str, str]) -> list[dict]` — same signature and behavior as the old `_match_ai_markers`, just renamed since Task 2 reuses it outside the AI-usage context.
- Produces: `DB_ORM_MARKERS_PY: dict[str, str]`, `DB_ORM_MARKERS_JS: dict[str, str]` — consumed by Task 2's `detect_database`.

- [ ] **Step 1: Write the failing test for the rename**

The existing AI-usage tests already exercise `_match_ai_markers` indirectly through `detect_ai_usage` — add one direct test of the renamed helper to lock the public name in:

```python
def test_match_dependency_markers_matches_pip_and_npm():
    from aletheore.scanner.detect import _match_dependency_markers

    pip_lines = [("sqlalchemy", "sqlalchemy==2.0.0", "requirements.txt")]
    npm_deps = {"Prisma": "^5.0.0"}
    matches = _match_dependency_markers(
        {"sqlalchemy": "sqlalchemy"}, {"prisma": "prisma"}, pip_lines, npm_deps
    )
    names = {m["name"] for m in matches}
    assert names == {"sqlalchemy", "prisma"}
```

Add this to `tests/test_detect.py`.

- [ ] **Step 2: Run test to verify it fails**

Run: `cd prototype && python3 -m pytest tests/test_detect.py::test_match_dependency_markers_matches_pip_and_npm -v`
Expected: FAIL with `ImportError: cannot import name '_match_dependency_markers'`

- [ ] **Step 3: Rename the helper and add the new marker dicts**

In `aletheore/scanner/detect.py`, rename `_match_ai_markers` to `_match_dependency_markers` (the function body is unchanged — only the name changes):

```python
def _match_dependency_markers(
    pip_markers: dict[str, str],
    js_markers: dict[str, str],
    pip_lines: list[tuple[str, str, str]],
    npm_deps: dict[str, str],
) -> list[dict]:
    matches: list[dict] = []
    for package_name, line, source in pip_lines:
        if package_name in pip_markers:
            matches.append({"name": pip_markers[package_name], "evidence": f"{source}:{line}"})
    for name, version in npm_deps.items():
        key = name.lower()
        if key in js_markers:
            matches.append({"name": js_markers[key], "evidence": f"package.json:{name}@{version}"})
    return matches
```

Update `detect_ai_usage`'s five call sites (`providers`, `orchestration`, `vector_stores`, `local_inference`, `mcp`) to call `_match_dependency_markers` instead of `_match_ai_markers`. The function body of `detect_ai_usage` is otherwise unchanged.

Add these new marker dicts near the existing `AI_MCP_MARKERS_JS` dict (around line 91):

```python
DB_ORM_MARKERS_PY = {
    "sqlalchemy": "sqlalchemy",
    "django": "django-orm",
    "peewee": "peewee",
    "tortoise-orm": "tortoise-orm",
    "mongoengine": "mongoengine",
}

DB_ORM_MARKERS_JS = {
    "prisma": "prisma",
    "@prisma/client": "prisma",
    "typeorm": "typeorm",
    "sequelize": "sequelize",
    "mongoose": "mongoose",
    "knex": "knex",
}
```

- [ ] **Step 4: Run test to verify it passes, and confirm no regression in the existing AI-usage tests**

Run: `cd prototype && python3 -m pytest tests/test_detect.py -v`
Expected: All tests pass, including `test_match_dependency_markers_matches_pip_and_npm` and every pre-existing `test_detect_ai_usage_*` test (they exercise the same code path through `detect_ai_usage`, now calling the renamed helper internally).

- [ ] **Step 5: Commit**

```bash
cd prototype
git add aletheore/scanner/detect.py tests/test_detect.py
git commit -m "refactor: generalize _match_ai_markers to _match_dependency_markers for reuse"
```

---

### Task 2: Implement migration-directory and schema-file detection, and `detect_database`

**Files:**
- Modify: `aletheore/scanner/detect.py` (new constants + three new functions, appended after `detect_monorepo`)
- Test: `tests/test_detect.py`

**Interfaces:**
- Consumes: `_match_dependency_markers`, `DB_ORM_MARKERS_PY`, `DB_ORM_MARKERS_JS` (Task 1), `_iter_pip_package_lines`, `_npm_dependencies`, `IGNORED_DIRS` (all pre-existing in `detect.py`).
- Produces: `detect_database(repo_path: Path) -> dict` with shape `{"orm_frameworks": list[dict], "migration_directories": list[dict], "schema_files": list[str]}` — consumed by Task 3 (`evidence.py`), Task 4 (`query.py`), Task 5 (`mcp_server.py`).

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_detect.py`:

```python
from aletheore.scanner.detect import detect_database


def test_detect_database_finds_orm_in_requirements_txt(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "requirements.txt").write_text("sqlalchemy==2.0.0\n")

    result = detect_database(repo)

    names = {p["name"] for p in result["orm_frameworks"]}
    assert "sqlalchemy" in names


def test_detect_database_finds_orm_in_package_json(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "package.json").write_text(json.dumps({"dependencies": {"prisma": "^5.0.0"}}))

    result = detect_database(repo)

    names = {p["name"] for p in result["orm_frameworks"]}
    assert "prisma" in names


def test_detect_database_finds_generic_migrations_directory(tmp_path):
    repo = tmp_path / "repo"
    migrations = repo / "migrations"
    migrations.mkdir(parents=True)
    (migrations / "001_initial.sql").write_text("CREATE TABLE x (id INT);\n")
    (migrations / "002_add_column.sql").write_text("ALTER TABLE x ADD y INT;\n")
    (migrations / "README.md").write_text("not a migration\n")

    result = detect_database(repo)

    assert result["migration_directories"] == [{"path": "migrations", "file_count": 2}]


def test_detect_database_finds_nested_django_style_migrations(tmp_path):
    repo = tmp_path / "repo"
    migrations = repo / "app" / "migrations"
    migrations.mkdir(parents=True)
    (migrations / "0001_initial.py").write_text("class Migration:\n    pass\n")

    result = detect_database(repo)

    assert result["migration_directories"] == [{"path": "app/migrations", "file_count": 1}]


def test_detect_database_finds_alembic_versions(tmp_path):
    repo = tmp_path / "repo"
    versions = repo / "alembic" / "versions"
    versions.mkdir(parents=True)
    (versions / "abc123_initial.py").write_text("def upgrade():\n    pass\n")
    (versions / "def456_add_index.py").write_text("def upgrade():\n    pass\n")

    result = detect_database(repo)

    assert {"path": "alembic/versions", "file_count": 2} in result["migration_directories"]


def test_detect_database_finds_rails_style_migrate_dir(tmp_path):
    repo = tmp_path / "repo"
    migrate = repo / "db" / "migrate"
    migrate.mkdir(parents=True)
    (migrate / "20260101000000_create_users.rb").write_text("class CreateUsers; end\n")

    result = detect_database(repo)

    assert {"path": "db/migrate", "file_count": 1} in result["migration_directories"]


def test_detect_database_ignores_migrations_dir_inside_node_modules(tmp_path):
    repo = tmp_path / "repo"
    vendored = repo / "node_modules" / "some-orm" / "migrations"
    vendored.mkdir(parents=True)
    (vendored / "001.js").write_text("module.exports = {};\n")

    result = detect_database(repo)

    assert result["migration_directories"] == []


def test_detect_database_finds_prisma_schema_file(tmp_path):
    repo = tmp_path / "repo"
    (repo / "prisma").mkdir()
    (repo / "prisma" / "schema.prisma").write_text("datasource db {}\n")

    result = detect_database(repo)

    assert result["schema_files"] == ["prisma/schema.prisma"]


def test_detect_database_returns_empty_when_nothing_present(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "main.py").write_text("x = 1\n")

    result = detect_database(repo)

    assert result == {"orm_frameworks": [], "migration_directories": [], "schema_files": []}
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd prototype && python3 -m pytest tests/test_detect.py -k detect_database -v`
Expected: FAIL with `ImportError: cannot import name 'detect_database'`

- [ ] **Step 3: Implement the new constants and functions**

Add near the other marker constants in `aletheore/scanner/detect.py` (after the `DB_ORM_MARKERS_JS` dict added in Task 1):

```python
MIGRATION_DIR_NAME_MARKERS = ("migrations",)

SCHEMA_FILE_MARKERS = (
    "prisma/schema.prisma",
    "db/schema.rb",
    "db/structure.sql",
)
```

Append these three functions after `detect_monorepo` (end of the file):

```python
def _detect_migration_directories(repo_path: Path) -> list[dict]:
    results: list[dict] = []
    for name in MIGRATION_DIR_NAME_MARKERS:
        for candidate in repo_path.rglob(name):
            if not candidate.is_dir():
                continue
            rel_parts = candidate.relative_to(repo_path).parts
            if any(part in IGNORED_DIRS for part in rel_parts):
                continue
            file_count = sum(
                1 for f in candidate.iterdir()
                if f.is_file() and f.suffix in (".py", ".sql", ".js", ".ts", ".rb")
            )
            results.append(
                {"path": candidate.relative_to(repo_path).as_posix(), "file_count": file_count}
            )

    # Alembic (SQLAlchemy's migration tool) and Rails both use a directory name
    # ("versions", "migrate") that the generic "migrations" glob above never matches -
    # each needs its own explicit check.
    alembic_versions = repo_path / "alembic" / "versions"
    if alembic_versions.is_dir():
        file_count = sum(1 for f in alembic_versions.iterdir() if f.is_file() and f.suffix == ".py")
        results.append({"path": "alembic/versions", "file_count": file_count})

    rails_migrate = repo_path / "db" / "migrate"
    if rails_migrate.is_dir():
        file_count = sum(1 for f in rails_migrate.iterdir() if f.is_file() and f.suffix == ".rb")
        results.append({"path": "db/migrate", "file_count": file_count})

    return results


def _detect_schema_files(repo_path: Path) -> list[str]:
    return [marker for marker in SCHEMA_FILE_MARKERS if (repo_path / marker).exists()]


def detect_database(repo_path: Path) -> dict:
    pip_lines = _iter_pip_package_lines(repo_path)
    npm_deps = _npm_dependencies(repo_path)
    return {
        "orm_frameworks": _match_dependency_markers(
            DB_ORM_MARKERS_PY, DB_ORM_MARKERS_JS, pip_lines, npm_deps
        ),
        "migration_directories": _detect_migration_directories(repo_path),
        "schema_files": _detect_schema_files(repo_path),
    }
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd prototype && python3 -m pytest tests/test_detect.py -v`
Expected: All tests pass, including all 9 new `test_detect_database_*` tests.

- [ ] **Step 5: Commit**

```bash
cd prototype
git add aletheore/scanner/detect.py tests/test_detect.py
git commit -m "feat: add detect_database (ORM markers, migration dirs, schema files)"
```

---

### Task 3: Wire `detect_database` into `scan_repository`

**Files:**
- Modify: `aletheore/evidence.py:11-18` (import), `:51-57` (detection call), `:128-140` (dict assembly)
- Test: `tests/test_evidence.py`

**Interfaces:**
- Consumes: `detect_database(repo_path: Path) -> dict` (Task 2).
- Produces: `evidence["repository"]["database"]` — the real dict shape from Task 2, now present in every `scan_repository()` return value.

- [ ] **Step 1: Write the failing test**

Add to `tests/test_evidence.py`, next to `test_scan_repository_includes_ai_usage_in_repository_block`:

```python
def test_scan_repository_includes_database_in_repository_block(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "requirements.txt").write_text("sqlalchemy==2.0.0\n")
    (repo / "main.py").write_text("x = 1\n")

    with patch("aletheore.evidence.check_dependency_vulnerabilities") as mock_check:
        mock_check.return_value = {"checked": True, "reason": None, "findings": []}
        evidence = scan_repository(repo, check_licenses=False)

    assert "database" in evidence["repository"]
    names = {p["name"] for p in evidence["repository"]["database"]["orm_frameworks"]}
    assert "sqlalchemy" in names
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd prototype && python3 -m pytest tests/test_evidence.py::test_scan_repository_includes_database_in_repository_block -v`
Expected: FAIL with `KeyError: 'database'`

- [ ] **Step 3: Wire it into `scan_repository`**

In `aletheore/evidence.py`, add `detect_database` to the existing import block (line 11-18):

```python
from aletheore.scanner.detect import (
    detect_ai_usage,
    detect_build_tools,
    detect_database,
    detect_frameworks,
    detect_languages,
    detect_monorepo,
    detect_policy_docs,
)
```

Add the detection call right after `monorepo = detect_monorepo(repo_path)` (line 57):

```python
    monorepo = detect_monorepo(repo_path)
    database = detect_database(repo_path)
```

Add `"database": database,` to the `repository` dict (after `"monorepo": monorepo,` at line 134):

```python
        "repository": {
            "languages": languages,
            "frameworks": frameworks,
            "ai_usage": ai_usage,
            "policy_docs": policy_docs,
            "build_tools": build_tools,
            "monorepo": monorepo,
            "database": database,
            "modules": modules,
            "dependency_graph": dependency_graph,
            "unparseable_files": unparseable_files,
            "api_endpoints": api_endpoints_data,
            "dead_code": dead_code_data,
        },
```

- [ ] **Step 4: Run test to verify it passes, and the full evidence suite**

Run: `cd prototype && python3 -m pytest tests/test_evidence.py -v`
Expected: All tests pass, including the new one.

- [ ] **Step 5: Commit**

```bash
cd prototype
git add aletheore/evidence.py tests/test_evidence.py
git commit -m "feat: wire detect_database into scan_repository as repository.database"
```

---

### Task 4: Add `find_database` to the query registry

**Files:**
- Modify: `aletheore/query.py:108-130`
- Test: `tests/test_query.py`

**Interfaces:**
- Consumes: `evidence["repository"]["database"]` (Task 3's output shape).
- Produces: `find_database(evidence: dict, target: str | None) -> dict`, registered in `QUERY_FUNCTIONS["database"] = (find_database, False)` — consumed by Task 5 (MCP) and automatically by `cli.py`'s `QUERY_KIND_CHOICES` (already derived from `QUERY_FUNCTIONS.keys()`, no manual edit needed there).

- [ ] **Step 1: Write the failing tests**

In `tests/test_query.py`, add `"database"` to the `make_evidence()` fixture's `repository` dict, alongside the existing `"dead_code"` key:

```python
            "dead_code": {
                "unreachable_modules": [{"path": "app/unused.py", "reason": "no imports"}],
                "unused_dependencies": [],
                "entry_points_detected": ["app/main.py"],
            },
            "database": {
                "orm_frameworks": [{"name": "sqlalchemy", "evidence": "requirements.txt:sqlalchemy==2.0.0"}],
                "migration_directories": [{"path": "migrations", "file_count": 3}],
                "schema_files": [],
            },
```

Add `find_database` to the import block at the top of the file:

```python
from aletheore.query import (
    QUERY_FUNCTIONS,
    BranchNotFoundInEvidenceError,
    ModuleNotFoundInEvidenceError,
    SymbolNotFoundInEvidenceError,
    find_branch,
    find_cluster,
    find_database,
    find_dead_code_evidence,
    find_endpoints,
    find_hotspots,
    find_imported_by,
    find_imports,
    find_layer_violations,
    find_licenses,
    find_ownership,
    find_secrets_for_file,
    find_symbol_source,
    find_symbols,
    find_vulnerabilities,
)
```

Add these tests next to `test_find_dead_code_evidence_returns_the_whole_block_ignoring_target`:

```python
def test_find_database_returns_the_whole_block_ignoring_target():
    assert find_database(make_evidence(), None) == make_evidence()["repository"]["database"]
```

Update `test_query_functions_registry_has_all_kinds_with_correct_requires_target`'s `expected` dict to add `"database": False`.

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd prototype && python3 -m pytest tests/test_query.py -v`
Expected: FAIL with `ImportError: cannot import name 'find_database'`

- [ ] **Step 3: Implement `find_database` and register it**

In `aletheore/query.py`, add next to `find_dead_code_evidence`:

```python
def find_database(evidence: dict, target: str | None) -> dict:
    return evidence["repository"]["database"]
```

Add to the `QUERY_FUNCTIONS` dict:

```python
QUERY_FUNCTIONS: dict[str, tuple[Callable[[dict, str | None], Any], bool]] = {
    "imports": (find_imports, True),
    "imported-by": (find_imported_by, True),
    "symbols": (find_symbols, True),
    "branch": (find_branch, True),
    "ownership": (find_ownership, False),
    "secrets": (find_secrets_for_file, True),
    "vulnerabilities": (find_vulnerabilities, False),
    "licenses": (find_licenses, False),
    "endpoints": (find_endpoints, False),
    "cluster": (find_cluster, True),
    "layer-violations": (find_layer_violations, False),
    "dead-code": (find_dead_code_evidence, False),
    "hotspots": (find_hotspots, False),
    "database": (find_database, False),
}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd prototype && python3 -m pytest tests/test_query.py -v`
Expected: All tests pass.

- [ ] **Step 5: Commit**

```bash
cd prototype
git add aletheore/query.py tests/test_query.py
git commit -m "feat: add find_database query kind (aletheore query database)"
```

---

### Task 5: Register the `aletheore_database` MCP tool

**Files:**
- Modify: `aletheore/mcp_server.py:45-59`
- Test: `tests/test_mcp_server.py`

**Interfaces:**
- Consumes: `QUERY_FUNCTIONS["database"]` (Task 4).
- Produces: an MCP tool named `aletheore_database`, callable exactly like `aletheore_dead_code`/`aletheore_hotspots`.

- [ ] **Step 1: Write the failing test**

In `tests/test_mcp_server.py`, find the `make_repo_with_evidence` fixture's evidence dict (it contains a `"dead_code"` key inside `repository`) and add a `"database"` key alongside it:

```python
            "database": {
                "orm_frameworks": [],
                "migration_directories": [{"path": "migrations", "file_count": 4}],
                "schema_files": [],
            },
```

Add this test next to `test_aletheore_dead_code_tool_returns_toon_results`:

```python
@pytest.mark.asyncio
async def test_aletheore_database_tool_returns_toon_results(tmp_path):
    repo = make_repo_with_evidence(tmp_path)
    server = build_server(repo)

    result = await server.call_tool("aletheore_database", {})

    assert tool_result_body(result)["result"]["migration_directories"][0]["path"] == "migrations"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd prototype && python3 -m pytest tests/test_mcp_server.py::test_aletheore_database_tool_returns_toon_results -v`
Expected: FAIL — the tool `aletheore_database` doesn't exist yet, so `server.call_tool` raises or returns an unknown-tool error.

- [ ] **Step 3: Register the tool**

In `aletheore/mcp_server.py`, add one entry to `_TOOL_NAME_TO_QUERY_KIND`:

```python
_TOOL_NAME_TO_QUERY_KIND = {
    "aletheore_imports": "imports",
    "aletheore_imported_by": "imported-by",
    "aletheore_symbols": "symbols",
    "aletheore_branch": "branch",
    "aletheore_ownership": "ownership",
    "aletheore_secrets": "secrets",
    "aletheore_vulnerabilities": "vulnerabilities",
    "aletheore_licenses": "licenses",
    "aletheore_endpoints": "endpoints",
    "aletheore_cluster": "cluster",
    "aletheore_layer_violations": "layer-violations",
    "aletheore_dead_code": "dead-code",
    "aletheore_hotspots": "hotspots",
    "aletheore_database": "database",
}
```

- [ ] **Step 4: Run test to verify it passes, and the full MCP suite**

Run: `cd prototype && python3 -m pytest tests/test_mcp_server.py -v`
Expected: All tests pass.

- [ ] **Step 5: Commit**

```bash
cd prototype
git add aletheore/mcp_server.py tests/test_mcp_server.py
git commit -m "feat: register aletheore_database MCP tool"
```

---

### Task 6: Document `repository.database` in `EVIDENCE_SCHEMA_MAP`

**Files:**
- Modify: `aletheore/adapters/openai_compatible.py:83-109`
- Test: `tests/test_openai_compatible_adapter.py`

**Interfaces:**
- Consumes: nothing new (documentation only).
- Produces: an updated `EVIDENCE_SCHEMA_MAP` string, automatically picked up by `anthropic_native.py` (which imports the constant from this module) with no separate edit needed there.

- [ ] **Step 1: Write the failing test**

Add to `tests/test_openai_compatible_adapter.py`:

```python
def test_evidence_schema_map_documents_database_block():
    from aletheore.adapters.openai_compatible import EVIDENCE_SCHEMA_MAP

    assert "repository.database" in EVIDENCE_SCHEMA_MAP
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd prototype && python3 -m pytest tests/test_openai_compatible_adapter.py::test_evidence_schema_map_documents_database_block -v`
Expected: FAIL — `"repository.database"` not in the string.

- [ ] **Step 3: Add the line**

In `aletheore/adapters/openai_compatible.py`, add one line to `EVIDENCE_SCHEMA_MAP` right after the `repository.monorepo` line:

```python
EVIDENCE_SCHEMA_MAP = """
repository.languages[]              - {name, file_count, loc}
repository.frameworks[]             - {name, evidence}
repository.ai_usage                 - {providers[], orchestration[], vector_stores[], local_inference[], mcp[]}
repository.policy_docs[]
repository.build_tools[]
repository.monorepo                 - {detected, workspaces[]}
repository.database                 - {orm_frameworks[]: {name, evidence}, migration_directories[]: {path, file_count}, schema_files[]}
repository.modules[]                - {path, imports[], imported_by[], symbols: {functions[]: {name, start_line, end_line}, classes[]: {name, start_line, end_line}}}
repository.dependency_graph         - {nodes[], edges[]}
repository.unparseable_files[]      - {path, reason}
repository.api_endpoints            - {checked, endpoints[]: {method, path, framework, file, line, handler, unresolved, note}}
repository.dead_code                - {unreachable_modules[]: {path, reason}, unused_dependencies[]: {ecosystem, package}, entry_points_detected[]}
git.available                       - false if not a git repo
git.branches[]                      - {name, type, stale_days, ahead_of_main, behind_main}
git.ownership[]                     - {email, names[], commit_count, percent}
git.total_commits
git.commit_cadence                  - {weekly_counts[], trend}
git.repo_age_days
git.hotspots[]                      - {path, churn_count, co_change_partners[]: {path, co_occurrences}, dependents_count}
security.secrets                    - {scanned_files, findings[], history_scanned_commits, history_findings[]}
security.dependency_vulnerabilities - {checked, reason, findings[]: {ecosystem, package, installed_version, advisory_id, summary, severity}}
security.dependency_licenses        - {checked, reason, repo_license: {category, detected_from}, findings[]: {ecosystem, package, installed_version, license, category}}
architecture.clusters[]             - {id, modules[], internal_edges}
architecture.cross_cluster_edges
architecture.layer_violations       - {convention_detected, layers[], violations[]}
architecture.config_applied         - null, or the repo's .aletheore.json config if present
""".strip()
```

- [ ] **Step 4: Run test to verify it passes, and the full adapter suite**

Run: `cd prototype && python3 -m pytest tests/test_openai_compatible_adapter.py tests/test_anthropic_adapter.py -v`
Expected: All tests pass (the Anthropic adapter test suite should be unaffected since it imports `EVIDENCE_SCHEMA_MAP` from this same module rather than duplicating it).

- [ ] **Step 5: Commit**

```bash
cd prototype
git add aletheore/adapters/openai_compatible.py tests/test_openai_compatible_adapter.py
git commit -m "docs: document repository.database in EVIDENCE_SCHEMA_MAP"
```

---

### Task 7: Real end-to-end verification against this repo

**Files:** none modified — verification only.

**Interfaces:**
- Consumes: the fully-wired `detect_database` from Tasks 1-6.

- [ ] **Step 1: Run the full test suite**

Run: `cd prototype && python3 -m pytest tests/ -q`
Expected: All tests pass (should be 552 + the ~14 new tests added across Tasks 1-6, so ~566).

- [ ] **Step 2: Re-scan this actual repo and inspect the real output**

Run:
```bash
cd /Users/arihantkaul/Documents/GitHub/Veridion && aletheore scan .
python3 -c "
import json
data = json.loads(open('.aletheore/air.json').read())
print(json.dumps(data['repository']['database'], indent=2))
"
```

Expected: `orm_frameworks` is `[]` — this repo's `github-app/` backend uses raw `asyncpg`/`psycopg`, not an ORM, so an empty list here is the *correct* fact, not a detection failure. `migration_directories` includes `{"path": "github-app/migrations", "file_count": 4}` (the four real `.sql` files: `001_initial_schema.sql`, `002_paid_tier.sql`, `003_health_monitoring.sql`, `004_managed_audit_rate_limit.sql`). `schema_files` is `[]` (no `prisma/schema.prisma` or Rails schema file in this repo).

- [ ] **Step 3: Confirm no false positive by checking the count precisely**

Run:
```bash
ls /Users/arihantkaul/Documents/GitHub/Veridion/github-app/migrations/*.sql | wc -l
```

Expected: `4` — matching `migration_directories`'s reported `file_count` exactly. If this doesn't match, the file-extension filter in `_detect_migration_directories` (Task 2, Step 3) needs re-checking against what's actually in that directory.

- [ ] **Step 4: No commit needed — this task is verification-only**

If Steps 1-3 all pass as expected, the feature is confirmed working end-to-end on a real repo with a real, hand-verifiable answer. If anything is off, return to the relevant task above, fix it, and re-run this task from Step 1.
