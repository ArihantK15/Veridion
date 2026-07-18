# AIR Expansion Phase 2: Infrastructure + Environment Variables Detection Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add two new AIR evidence blocks — `repository.infrastructure` (Docker Compose services, Kubernetes manifests, Terraform files, Helm charts) and `repository.environment_variables` (declared env var names from `.env.example`-style files) — the second and final deterministic-friendly AIR expansion category, after database models (already shipped: commits `40ce4d9`..`8a6f38a`).

**Architecture:** Same `detect.py` marker/existence pattern as `detect_database`, wired through the same five integration points every AIR evidence block uses (`evidence.py`, `query.py`, `mcp_server.py`, `openai_compatible.py`'s `EVIDENCE_SCHEMA_MAP`). One deliberate deviation from the database-model plan's "zero new dependencies" constraint: this category is YAML-shaped by nature (Docker Compose, Kubernetes manifests, Helm all use YAML), and hand-rolling indent-tracking YAML parsing is fragile in ways that would produce silently wrong facts — the opposite of what a "cite the exact fact" tool should ever do. PyYAML is added as a narrow, justified exception.

**Tech Stack:** Python 3.12, pytest, PyYAML (new dependency — see Task 1).

## Global Constraints

- New dependency: `pyyaml>=6.0,<7.0` — the one exception to "zero new dependencies," justified because this category's file formats (Compose, K8s manifests, Helm charts) are all YAML, and there is no stdlib YAML parser (unlike JSON/TOML, which the codebase already handles via stdlib `json`/`tomllib`).
- Environment-variable detection reports **variable names only, never values** — even from `.env.example`-style files, which are conventionally safe but not guaranteed to be. This is a hard rule, not a judgment call, matching the project's existing secrets-detection posture of never echoing raw sensitive content.
- Every filesystem walk (`rglob`) must exclude `IGNORED_DIRS` (from `aletheore/scanner/detect.py`), matching every existing walker in this file.
- All new code lives in `prototype/aletheore/`; all paths below are relative to `prototype/` unless stated otherwise.

---

### Task 1: Add the PyYAML dependency

**Files:**
- Modify: `pyproject.toml:21-44` (dependencies list)

**Interfaces:**
- Produces: `import yaml` becomes available to every module in the package — consumed by Task 2.

- [ ] **Step 1: Add the dependency**

In `pyproject.toml`, add one line to the `dependencies` list (matches the existing alphabetical-ish grouping near `python-toon`):

```toml
dependencies = [
    "tree-sitter>=0.25,<0.26",
    "tree-sitter-python>=0.25,<0.26",
    "tree-sitter-javascript>=0.25,<0.26",
    "tree-sitter-typescript>=0.23,<0.24",
    "tree-sitter-go>=0.25,<0.26",
    "tree-sitter-rust>=0.24,<0.25",
    "tree-sitter-java>=0.23,<0.24",
    "tree-sitter-ruby>=0.23,<0.24",
    "tree-sitter-php>=0.24,<0.25",
    "tree-sitter-c>=0.24,<0.25",
    "tree-sitter-cpp>=0.23,<0.24",
    "tree-sitter-c-sharp>=0.23,<0.24",
    "anthropic>=0.40,<1.0",
    "certifi>=2024.0.0",
    "httpx>=0.28.1,<1.0",
    "lancedb>=0.15,<1.0",
    "networkx>=3.0,<4.0",
    "mcp>=1.23,<2.0",
    "openai>=2.0,<3.0",
    "python-toon>=0.1.3,<0.2",
    "pyyaml>=6.0,<7.0",
    "typer>=0.24,<0.25",
    "rich>=13.0",
]
```

- [ ] **Step 2: Install and verify it's importable**

Run: `cd prototype && pip install -e . && python3 -c "import yaml; print(yaml.__version__)"`
Expected: prints a version like `6.0.x`, no `ModuleNotFoundError`.

- [ ] **Step 3: Commit**

```bash
cd prototype
git add pyproject.toml
git commit -m "chore: add pyyaml dependency for infrastructure detection"
```

---

### Task 2: Docker Compose service detection

**Files:**
- Modify: `aletheore/scanner/detect.py` (new constant + function, appended after `_detect_schema_files` from the database-model work)
- Test: `tests/test_detect.py`

**Interfaces:**
- Consumes: `IGNORED_DIRS` (pre-existing), `yaml` (Task 1).
- Produces: `_detect_docker_compose_services(repo_path: Path) -> list[dict]` with shape `[{"file": str, "services": list[str]}]` — consumed by Task 5's `detect_infrastructure`.

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_detect.py`:

```python
import yaml


def test_detect_docker_compose_services_finds_real_services(tmp_path):
    from aletheore.scanner.detect import _detect_docker_compose_services

    repo = tmp_path / "repo"
    repo.mkdir()
    compose = {
        "services": {
            "app-server": {"build": "."},
            "postgres": {"image": "postgres:16"},
        },
        "volumes": {"data": None},
    }
    (repo / "docker-compose.yml").write_text(yaml.dump(compose))

    result = _detect_docker_compose_services(repo)

    assert result == [{"file": "docker-compose.yml", "services": ["app-server", "postgres"]}]


def test_detect_docker_compose_services_finds_a_compose_file_in_a_subdirectory(tmp_path):
    # Monorepos put the compose file under a sub-project directory
    # (github-app/docker-compose.yml in this very repo), not the scanned root -
    # the same class of bug as the original monorepo dependency-graph fix earlier
    # this session. A root-only check would silently miss this.
    from aletheore.scanner.detect import _detect_docker_compose_services

    repo = tmp_path / "repo"
    service_dir = repo / "backend-service"
    service_dir.mkdir(parents=True)
    compose = {"services": {"web": {"image": "nginx"}}}
    (service_dir / "docker-compose.yml").write_text(yaml.dump(compose))

    result = _detect_docker_compose_services(repo)

    assert result == [{"file": "backend-service/docker-compose.yml", "services": ["web"]}]


def test_detect_docker_compose_services_returns_empty_when_no_compose_file(tmp_path):
    from aletheore.scanner.detect import _detect_docker_compose_services

    repo = tmp_path / "repo"
    repo.mkdir()

    assert _detect_docker_compose_services(repo) == []


def test_detect_docker_compose_services_skips_malformed_yaml(tmp_path):
    from aletheore.scanner.detect import _detect_docker_compose_services

    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "docker-compose.yml").write_text("services:\n  app: [unterminated\n")

    assert _detect_docker_compose_services(repo) == []


def test_detect_docker_compose_services_ignores_node_modules(tmp_path):
    from aletheore.scanner.detect import _detect_docker_compose_services

    repo = tmp_path / "repo"
    vendored = repo / "node_modules" / "some-pkg"
    vendored.mkdir(parents=True)
    (vendored / "docker-compose.yml").write_text(yaml.dump({"services": {"x": {}}}))

    assert _detect_docker_compose_services(repo) == []
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd prototype && python3 -m pytest tests/test_detect.py -k docker_compose_services -v`
Expected: FAIL with `ImportError: cannot import name '_detect_docker_compose_services'`

- [ ] **Step 3: Implement it**

Add near the top of `aletheore/scanner/detect.py`, after the existing imports:

```python
import yaml
```

Append after `_detect_schema_files` (the last function from the database-model work):

```python
COMPOSE_FILE_NAMES = ("docker-compose.yml", "docker-compose.yaml", "compose.yml", "compose.yaml")


def _detect_docker_compose_services(repo_path: Path) -> list[dict]:
    # A monorepo puts its compose file under a sub-project directory
    # (github-app/docker-compose.yml in this repo), not the scanned root - walk
    # the whole tree rather than only checking repo_path directly.
    results: list[dict] = []
    for filename in COMPOSE_FILE_NAMES:
        for compose_file in repo_path.rglob(filename):
            rel_parts = compose_file.relative_to(repo_path).parts
            if any(part in IGNORED_DIRS for part in rel_parts):
                continue
            try:
                data = yaml.safe_load(compose_file.read_text(encoding="utf-8", errors="ignore"))
            except yaml.YAMLError:
                continue
            if not isinstance(data, dict):
                continue
            services = list(data.get("services", {}).keys())
            if services:
                results.append(
                    {"file": compose_file.relative_to(repo_path).as_posix(), "services": services}
                )
    return results
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd prototype && python3 -m pytest tests/test_detect.py -k docker_compose_services -v`
Expected: All 3 pass.

- [ ] **Step 5: Commit**

```bash
cd prototype
git add aletheore/scanner/detect.py tests/test_detect.py
git commit -m "feat: add Docker Compose service detection"
```

---

### Task 3: Kubernetes manifest, Terraform, and Helm chart detection

**Files:**
- Modify: `aletheore/scanner/detect.py`
- Test: `tests/test_detect.py`

**Interfaces:**
- Consumes: `IGNORED_DIRS`, `yaml` (Task 1/2).
- Produces: `_detect_kubernetes_manifests(repo_path: Path) -> list[str]`, `_detect_terraform_files(repo_path: Path) -> list[str]`, `_detect_helm_charts(repo_path: Path) -> list[str]` — all consumed by Task 5's `detect_infrastructure`.

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_detect.py`:

```python
def test_detect_kubernetes_manifests_finds_a_real_deployment(tmp_path):
    from aletheore.scanner.detect import _detect_kubernetes_manifests

    repo = tmp_path / "repo"
    k8s = repo / "k8s"
    k8s.mkdir(parents=True)
    manifest = {
        "apiVersion": "apps/v1",
        "kind": "Deployment",
        "metadata": {"name": "web"},
    }
    (k8s / "deployment.yaml").write_text(yaml.dump(manifest))

    result = _detect_kubernetes_manifests(repo)

    assert result == ["k8s/deployment.yaml"]


def test_detect_kubernetes_manifests_ignores_non_k8s_yaml(tmp_path):
    from aletheore.scanner.detect import _detect_kubernetes_manifests

    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "config.yaml").write_text(yaml.dump({"some_setting": True}))

    assert _detect_kubernetes_manifests(repo) == []


def test_detect_kubernetes_manifests_ignores_node_modules(tmp_path):
    from aletheore.scanner.detect import _detect_kubernetes_manifests

    repo = tmp_path / "repo"
    vendored = repo / "node_modules" / "some-pkg"
    vendored.mkdir(parents=True)
    manifest = {"apiVersion": "v1", "kind": "Service", "metadata": {"name": "x"}}
    (vendored / "service.yaml").write_text(yaml.dump(manifest))

    assert _detect_kubernetes_manifests(repo) == []


def test_detect_terraform_files_finds_tf_files(tmp_path):
    from aletheore.scanner.detect import _detect_terraform_files

    repo = tmp_path / "repo"
    terraform = repo / "terraform"
    terraform.mkdir(parents=True)
    (terraform / "main.tf").write_text('resource "aws_instance" "web" {}\n')

    result = _detect_terraform_files(repo)

    assert result == ["terraform/main.tf"]


def test_detect_helm_charts_finds_chart_yaml(tmp_path):
    from aletheore.scanner.detect import _detect_helm_charts

    repo = tmp_path / "repo"
    chart_dir = repo / "charts" / "myapp"
    chart_dir.mkdir(parents=True)
    (chart_dir / "Chart.yaml").write_text("apiVersion: v2\nname: myapp\nversion: 0.1.0\n")

    result = _detect_helm_charts(repo)

    assert result == ["charts/myapp/Chart.yaml"]


def test_detect_infrastructure_categories_return_empty_when_nothing_present(tmp_path):
    from aletheore.scanner.detect import (
        _detect_helm_charts,
        _detect_kubernetes_manifests,
        _detect_terraform_files,
    )

    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "main.py").write_text("x = 1\n")

    assert _detect_kubernetes_manifests(repo) == []
    assert _detect_terraform_files(repo) == []
    assert _detect_helm_charts(repo) == []
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd prototype && python3 -m pytest tests/test_detect.py -k "kubernetes_manifests or terraform_files or helm_charts" -v`
Expected: FAIL with `ImportError` for each missing function.

- [ ] **Step 3: Implement them**

Append to `aletheore/scanner/detect.py`:

```python
K8S_KIND_MARKERS = {
    "Deployment", "Service", "Ingress", "ConfigMap", "Secret", "StatefulSet",
    "DaemonSet", "Job", "CronJob", "Namespace", "PersistentVolumeClaim",
}

YAML_EXTENSIONS = (".yaml", ".yml")


def _detect_kubernetes_manifests(repo_path: Path) -> list[str]:
    results: list[str] = []
    for extension in YAML_EXTENSIONS:
        for candidate in repo_path.rglob(f"*{extension}"):
            rel_parts = candidate.relative_to(repo_path).parts
            if any(part in IGNORED_DIRS for part in rel_parts):
                continue
            try:
                docs = list(
                    yaml.safe_load_all(candidate.read_text(encoding="utf-8", errors="ignore"))
                )
            except yaml.YAMLError:
                continue
            for doc in docs:
                if (
                    isinstance(doc, dict)
                    and doc.get("kind") in K8S_KIND_MARKERS
                    and "apiVersion" in doc
                ):
                    results.append(candidate.relative_to(repo_path).as_posix())
                    break
    return results


def _detect_terraform_files(repo_path: Path) -> list[str]:
    results: list[str] = []
    for candidate in repo_path.rglob("*.tf"):
        rel_parts = candidate.relative_to(repo_path).parts
        if any(part in IGNORED_DIRS for part in rel_parts):
            continue
        results.append(candidate.relative_to(repo_path).as_posix())
    return results


def _detect_helm_charts(repo_path: Path) -> list[str]:
    results: list[str] = []
    for candidate in repo_path.rglob("Chart.yaml"):
        rel_parts = candidate.relative_to(repo_path).parts
        if any(part in IGNORED_DIRS for part in rel_parts):
            continue
        results.append(candidate.relative_to(repo_path).as_posix())
    return results
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd prototype && python3 -m pytest tests/test_detect.py -k "kubernetes_manifests or terraform_files or helm_charts" -v`
Expected: All 6 pass.

- [ ] **Step 5: Commit**

```bash
cd prototype
git add aletheore/scanner/detect.py tests/test_detect.py
git commit -m "feat: add Kubernetes manifest, Terraform, and Helm chart detection"
```

---

### Task 4: Environment variable name detection

**Files:**
- Modify: `aletheore/scanner/detect.py`
- Test: `tests/test_detect.py`

**Interfaces:**
- Consumes: `IGNORED_DIRS`.
- Produces: `_detect_declared_env_vars(repo_path: Path) -> list[dict]` with shape `[{"name": str, "source": str}]` — consumed by Task 5's `detect_environment_variables`.

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_detect.py`:

```python
def test_detect_declared_env_vars_reads_names_only_never_values(tmp_path):
    from aletheore.scanner.detect import _detect_declared_env_vars

    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / ".env.example").write_text(
        "DATABASE_URL=postgresql://user:supersecretpassword@host/db\n"
        "# a comment\n"
        "\n"
        "API_KEY=\n"
    )

    result = _detect_declared_env_vars(repo)

    assert result == [
        {"name": "DATABASE_URL", "source": ".env.example"},
        {"name": "API_KEY", "source": ".env.example"},
    ]
    dumped = str(result)
    assert "supersecretpassword" not in dumped


def test_detect_declared_env_vars_reads_multiple_marker_filenames(tmp_path):
    from aletheore.scanner.detect import _detect_declared_env_vars

    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / ".env.sample").write_text("FOO=bar\n")

    result = _detect_declared_env_vars(repo)

    assert result == [{"name": "FOO", "source": ".env.sample"}]


def test_detect_declared_env_vars_returns_empty_when_no_env_files(tmp_path):
    from aletheore.scanner.detect import _detect_declared_env_vars

    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "main.py").write_text("x = 1\n")

    assert _detect_declared_env_vars(repo) == []
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd prototype && python3 -m pytest tests/test_detect.py -k declared_env_vars -v`
Expected: FAIL with `ImportError: cannot import name '_detect_declared_env_vars'`

- [ ] **Step 3: Implement it**

Append to `aletheore/scanner/detect.py`:

```python
ENV_FILE_MARKERS = (".env.example", ".env.sample", ".env.template", "env.example")


def _detect_declared_env_vars(repo_path: Path) -> list[dict]:
    results: list[dict] = []
    for marker in ENV_FILE_MARKERS:
        for candidate in repo_path.rglob(marker):
            rel_parts = candidate.relative_to(repo_path).parts
            if any(part in IGNORED_DIRS for part in rel_parts):
                continue
            source = candidate.relative_to(repo_path).as_posix()
            for line in candidate.read_text(encoding="utf-8", errors="ignore").splitlines():
                stripped = line.strip()
                if not stripped or stripped.startswith("#"):
                    continue
                name = stripped.split("=", 1)[0].strip()
                if name and all(c.isalnum() or c == "_" for c in name):
                    results.append({"name": name, "source": source})
    return results
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd prototype && python3 -m pytest tests/test_detect.py -k declared_env_vars -v`
Expected: All 3 pass.

- [ ] **Step 5: Commit**

```bash
cd prototype
git add aletheore/scanner/detect.py tests/test_detect.py
git commit -m "feat: add declared env-var name detection (never values)"
```

---

### Task 5: Combine into `detect_infrastructure` and `detect_environment_variables`, wire into `scan_repository`

**Files:**
- Modify: `aletheore/scanner/detect.py` (two new combining functions), `aletheore/evidence.py:11-18` (import), `:51-57` (detection calls), `:128-140` (dict assembly)
- Test: `tests/test_detect.py`, `tests/test_evidence.py`

**Interfaces:**
- Consumes: all six detector functions from Tasks 2-4.
- Produces: `detect_infrastructure(repo_path: Path) -> dict` with shape `{"docker_compose_services": list[dict], "kubernetes_manifests": list[str], "terraform_files": list[str], "helm_charts": list[str]}`, and `detect_environment_variables(repo_path: Path) -> dict` with shape `{"declared": list[dict]}` — both consumed by `evidence.py`'s `scan_repository`, and by Task 6 (query.py) and Task 7 (mcp_server.py).

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_detect.py`:

```python
def test_detect_infrastructure_combines_all_categories(tmp_path):
    from aletheore.scanner.detect import detect_infrastructure

    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "docker-compose.yml").write_text(yaml.dump({"services": {"web": {"image": "nginx"}}}))
    (repo / "main.tf").write_text('resource "aws_instance" "x" {}\n')

    result = detect_infrastructure(repo)

    assert result["docker_compose_services"] == [{"file": "docker-compose.yml", "services": ["web"]}]
    assert result["terraform_files"] == ["main.tf"]
    assert result["kubernetes_manifests"] == []
    assert result["helm_charts"] == []


def test_detect_environment_variables_wraps_declared_list(tmp_path):
    from aletheore.scanner.detect import detect_environment_variables

    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / ".env.example").write_text("FOO=bar\n")

    result = detect_environment_variables(repo)

    assert result == {"declared": [{"name": "FOO", "source": ".env.example"}]}
```

Add to `tests/test_evidence.py`, next to `test_scan_repository_includes_database_in_repository_block`:

```python
def test_scan_repository_includes_infrastructure_and_environment_variables(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "docker-compose.yml").write_text("services:\n  web:\n    image: nginx\n")
    (repo / ".env.example").write_text("FOO=bar\n")
    (repo / "main.py").write_text("x = 1\n")

    with patch("aletheore.evidence.check_dependency_vulnerabilities") as mock_check:
        mock_check.return_value = {"checked": True, "reason": None, "findings": []}
        evidence = scan_repository(repo, check_licenses=False)

    assert evidence["repository"]["infrastructure"]["docker_compose_services"] == [
        {"file": "docker-compose.yml", "services": ["web"]}
    ]
    assert evidence["repository"]["environment_variables"]["declared"] == [
        {"name": "FOO", "source": ".env.example"}
    ]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd prototype && python3 -m pytest tests/test_detect.py -k "detect_infrastructure or detect_environment_variables" tests/test_evidence.py::test_scan_repository_includes_infrastructure_and_environment_variables -v`
Expected: FAIL — `detect_infrastructure`/`detect_environment_variables` don't exist yet, and `evidence["repository"]["infrastructure"]` raises `KeyError`.

- [ ] **Step 3: Implement the combining functions and wire them in**

Append to `aletheore/scanner/detect.py`:

```python
def detect_infrastructure(repo_path: Path) -> dict:
    return {
        "docker_compose_services": _detect_docker_compose_services(repo_path),
        "kubernetes_manifests": _detect_kubernetes_manifests(repo_path),
        "terraform_files": _detect_terraform_files(repo_path),
        "helm_charts": _detect_helm_charts(repo_path),
    }


def detect_environment_variables(repo_path: Path) -> dict:
    return {"declared": _detect_declared_env_vars(repo_path)}
```

In `aletheore/evidence.py`, update the import block to include both new functions:

```python
from aletheore.scanner.detect import (
    detect_ai_usage,
    detect_build_tools,
    detect_database,
    detect_environment_variables,
    detect_frameworks,
    detect_infrastructure,
    detect_languages,
    detect_monorepo,
    detect_policy_docs,
)
```

Add the detection calls right after `database = detect_database(repo_path)` (added by the database-model plan):

```python
    database = detect_database(repo_path)
    infrastructure = detect_infrastructure(repo_path)
    environment_variables = detect_environment_variables(repo_path)
```

Add both keys to the `repository` dict, after `"database": database,`:

```python
        "repository": {
            "languages": languages,
            "frameworks": frameworks,
            "ai_usage": ai_usage,
            "policy_docs": policy_docs,
            "build_tools": build_tools,
            "monorepo": monorepo,
            "database": database,
            "infrastructure": infrastructure,
            "environment_variables": environment_variables,
            "modules": modules,
            "dependency_graph": dependency_graph,
            "unparseable_files": unparseable_files,
            "api_endpoints": api_endpoints_data,
            "dead_code": dead_code_data,
        },
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd prototype && python3 -m pytest tests/test_detect.py tests/test_evidence.py -v`
Expected: All pass.

- [ ] **Step 5: Commit**

```bash
cd prototype
git add aletheore/scanner/detect.py aletheore/evidence.py tests/test_detect.py tests/test_evidence.py
git commit -m "feat: wire infrastructure and environment_variables into scan_repository"
```

---

### Task 6: Add `find_infrastructure` and `find_environment_variables` to the query registry

**Files:**
- Modify: `aletheore/query.py`
- Test: `tests/test_query.py`

**Interfaces:**
- Consumes: `evidence["repository"]["infrastructure"]`, `evidence["repository"]["environment_variables"]` (Task 5).
- Produces: `find_infrastructure(evidence, target) -> dict`, `find_environment_variables(evidence, target) -> dict`, registered as `QUERY_FUNCTIONS["infrastructure"] = (find_infrastructure, False)` and `QUERY_FUNCTIONS["environment-variables"] = (find_environment_variables, False)`.

- [ ] **Step 1: Write the failing tests**

In `tests/test_query.py`, add to the `make_evidence()` fixture's `repository` dict, alongside `"database"`:

```python
            "infrastructure": {
                "docker_compose_services": [{"file": "docker-compose.yml", "services": ["web", "db"]}],
                "kubernetes_manifests": [],
                "terraform_files": [],
                "helm_charts": [],
            },
            "environment_variables": {
                "declared": [{"name": "DATABASE_URL", "source": ".env.example"}],
            },
```

Add to the import block:

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
    find_environment_variables,
    find_hotspots,
    find_imported_by,
    find_imports,
    find_infrastructure,
    find_layer_violations,
    find_licenses,
    find_ownership,
    find_secrets_for_file,
    find_symbol_source,
    find_symbols,
    find_vulnerabilities,
)
```

Add tests next to `test_find_database_returns_the_whole_block_ignoring_target`:

```python
def test_find_infrastructure_returns_the_whole_block_ignoring_target():
    assert find_infrastructure(make_evidence(), None) == make_evidence()["repository"]["infrastructure"]


def test_find_environment_variables_returns_the_whole_block_ignoring_target():
    result = find_environment_variables(make_evidence(), None)
    assert result == make_evidence()["repository"]["environment_variables"]
```

Update `test_query_functions_registry_has_all_kinds_with_correct_requires_target`'s `expected` dict to add `"infrastructure": False` and `"environment-variables": False`.

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd prototype && python3 -m pytest tests/test_query.py -v`
Expected: FAIL with `ImportError: cannot import name 'find_infrastructure'`

- [ ] **Step 3: Implement and register both**

In `aletheore/query.py`, add next to `find_database`:

```python
def find_infrastructure(evidence: dict, target: str | None) -> dict:
    return evidence["repository"]["infrastructure"]


def find_environment_variables(evidence: dict, target: str | None) -> dict:
    return evidence["repository"]["environment_variables"]
```

Add both to `QUERY_FUNCTIONS`:

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
    "infrastructure": (find_infrastructure, False),
    "environment-variables": (find_environment_variables, False),
}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd prototype && python3 -m pytest tests/test_query.py -v`
Expected: All pass.

- [ ] **Step 5: Commit**

```bash
cd prototype
git add aletheore/query.py tests/test_query.py
git commit -m "feat: add infrastructure and environment-variables query kinds"
```

---

### Task 7: Register `aletheore_infrastructure` and `aletheore_environment_variables` MCP tools

**Files:**
- Modify: `aletheore/mcp_server.py:45-59`
- Test: `tests/test_mcp_server.py`

**Interfaces:**
- Consumes: `QUERY_FUNCTIONS["infrastructure"]`, `QUERY_FUNCTIONS["environment-variables"]` (Task 6).
- Produces: two MCP tools, `aletheore_infrastructure` and `aletheore_environment_variables`, callable exactly like `aletheore_database`.

- [ ] **Step 1: Write the failing tests**

In `tests/test_mcp_server.py`, add to the `make_repo_with_evidence` fixture's evidence dict, alongside `"database"`:

```python
            "infrastructure": {
                "docker_compose_services": [{"file": "docker-compose.yml", "services": ["web"]}],
                "kubernetes_manifests": [],
                "terraform_files": [],
                "helm_charts": [],
            },
            "environment_variables": {"declared": [{"name": "FOO", "source": ".env.example"}]},
```

Add tests next to `test_aletheore_database_tool_returns_toon_results`:

```python
@pytest.mark.asyncio
async def test_aletheore_infrastructure_tool_returns_toon_results(tmp_path):
    repo = make_repo_with_evidence(tmp_path)
    server = build_server(repo)

    result = await server.call_tool("aletheore_infrastructure", {})

    assert tool_result_body(result)["result"]["docker_compose_services"][0]["file"] == "docker-compose.yml"


@pytest.mark.asyncio
async def test_aletheore_environment_variables_tool_returns_toon_results(tmp_path):
    repo = make_repo_with_evidence(tmp_path)
    server = build_server(repo)

    result = await server.call_tool("aletheore_environment_variables", {})

    assert tool_result_body(result)["result"]["declared"][0]["name"] == "FOO"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd prototype && python3 -m pytest tests/test_mcp_server.py -k "infrastructure or environment_variables" -v`
Expected: FAIL — neither tool is registered yet.

- [ ] **Step 3: Register both tools**

In `aletheore/mcp_server.py`, add two entries to `_TOOL_NAME_TO_QUERY_KIND`:

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
    "aletheore_infrastructure": "infrastructure",
    "aletheore_environment_variables": "environment-variables",
}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd prototype && python3 -m pytest tests/test_mcp_server.py -v`
Expected: All pass.

- [ ] **Step 5: Commit**

```bash
cd prototype
git add aletheore/mcp_server.py tests/test_mcp_server.py
git commit -m "feat: register aletheore_infrastructure and aletheore_environment_variables MCP tools"
```

---

### Task 8: Document both blocks in `EVIDENCE_SCHEMA_MAP`

**Files:**
- Modify: `aletheore/adapters/openai_compatible.py:83-109`
- Test: `tests/test_openai_compatible_adapter.py`

**Interfaces:**
- Consumes: nothing new (documentation only).
- Produces: an updated `EVIDENCE_SCHEMA_MAP` string, automatically inherited by `anthropic_native.py`.

- [ ] **Step 1: Write the failing test**

Add to `tests/test_openai_compatible_adapter.py`, next to `test_evidence_schema_map_documents_database_block`:

```python
def test_evidence_schema_map_documents_infrastructure_and_environment_variables():
    from aletheore.adapters.openai_compatible import EVIDENCE_SCHEMA_MAP

    assert "repository.infrastructure" in EVIDENCE_SCHEMA_MAP
    assert "repository.environment_variables" in EVIDENCE_SCHEMA_MAP
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd prototype && python3 -m pytest tests/test_openai_compatible_adapter.py::test_evidence_schema_map_documents_infrastructure_and_environment_variables -v`
Expected: FAIL — neither string is present yet.

- [ ] **Step 3: Add the two lines**

In `aletheore/adapters/openai_compatible.py`, add two lines to `EVIDENCE_SCHEMA_MAP` right after the `repository.database` line (added by the database-model plan):

```python
EVIDENCE_SCHEMA_MAP = """
repository.languages[]              - {name, file_count, loc}
repository.frameworks[]             - {name, evidence}
repository.ai_usage                 - {providers[], orchestration[], vector_stores[], local_inference[], mcp[]}
repository.policy_docs[]
repository.build_tools[]
repository.monorepo                 - {detected, workspaces[]}
repository.database                 - {orm_frameworks[]: {name, evidence}, migration_directories[]: {path, file_count}, schema_files[]}
repository.infrastructure           - {docker_compose_services[]: {file, services[]}, kubernetes_manifests[], terraform_files[], helm_charts[]}
repository.environment_variables    - {declared[]: {name, source}} - names only, never values
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
Expected: All pass.

- [ ] **Step 5: Commit**

```bash
cd prototype
git add aletheore/adapters/openai_compatible.py tests/test_openai_compatible_adapter.py
git commit -m "docs: document infrastructure and environment_variables in EVIDENCE_SCHEMA_MAP"
```

---

### Task 9: Real end-to-end verification against this repo

**Files:** none modified — verification only.

- [ ] **Step 1: Run the full test suite**

Run: `cd prototype && python3 -m pytest tests/ -q`
Expected: All tests pass (566 from before this plan, plus ~19 new tests across Tasks 2-8, so ~585).

- [ ] **Step 2: Re-scan this actual repo and inspect the real output**

Run:
```bash
cd /Users/arihantkaul/Documents/GitHub/Veridion && aletheore scan .
python3 -c "
import json
data = json.loads(open('.aletheore/air.json').read())
print(json.dumps(data['repository']['infrastructure'], indent=2))
print(json.dumps(data['repository']['environment_variables'], indent=2))
"
```

Expected: `docker_compose_services` includes `{"file": "github-app/docker-compose.yml", "services": ["app-server", "scan-worker", "postgres", "redis", "caddy", "ofelia"]}` (6 real services, found via the recursive walk in Task 2). `kubernetes_manifests`, `terraform_files`, and `helm_charts` are all `[]` — correctly, since none exist in this repo. `environment_variables.declared` includes all 11 real names from `github-app/.env.example`: `DATABASE_URL`, `POSTGRES_PASSWORD`, `REDIS_URL`, `GITHUB_APP_ID`, `GITHUB_APP_PRIVATE_KEY`, `GITHUB_WEBHOOK_SECRET`, `GITHUB_CLIENT_ID`, `GITHUB_CLIENT_SECRET`, `SESSION_SECRET`, `PUBLIC_BASE_URL`, `ANTHROPIC_API_KEY` — and no values, confirmed by checking that no result string contains `=` or any real secret text.

- [ ] **Step 3: Confirm the docker-compose service count by hand**

Run: `grep -c '^  [a-z-]*:$' /Users/arihantkaul/Documents/GitHub/Veridion/github-app/docker-compose.yml`
Expected: `6` — matching the reported `services` list length exactly.

- [ ] **Step 4: No commit needed — this task is verification-only**

If Steps 1-3 all pass, the feature is confirmed working end-to-end on this real repo.
