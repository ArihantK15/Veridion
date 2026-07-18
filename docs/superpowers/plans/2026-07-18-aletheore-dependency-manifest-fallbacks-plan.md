# Aletheore Dependency Manifest Fallbacks Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Stop `check_vulnerabilities`/`check_dependency_licenses` from silently reporting "0
findings" (indistinguishable from a clean scan) when a project's dependencies are declared in a
manifest the current lockfile-only parsers don't read - confirmed today on real repos (Django's
`pyproject.toml`, Rust/PHP libraries with no committed lockfile, Spring Boot's BOM-inherited
versions, C#'s Central Package Management, Maven multi-module repos).

**Architecture:** Each of the 8 ecosystem parsers in `prototype/aletheore/vulnerabilities.py`
gains either a fallback parser (used when its lockfile is absent) or, for Maven, direct fixes to
its single existing function. No new ecosystem, no new `_LICENSE_FETCHERS` entry, no change to
`check_vulnerabilities`/`check_dependency_licenses` themselves - every fix is inside a
`_parse_*_pins` function's own file-discovery logic, still returning
`list[tuple[str, str, str]]` with the same ecosystem strings the existing fetchers already key
off.

**Tech Stack:** Python 3.11+ stdlib only (`tomllib`, `json`, `re`, `xml.etree.ElementTree`),
`pytest` with `tmp_path` fixtures - identical toolchain to the existing parsers, no new
dependency.

## Global Constraints

- Every new/modified parser still returns `list[tuple[str, str, str]]` (`name, version,
  ecosystem`) - the exact type every existing caller (`check_vulnerabilities`,
  `check_dependency_licenses`) already expects.
- No new `_LICENSE_FETCHERS` entries and no new OSV.dev ecosystem identifiers - every fallback
  reuses the ecosystem string its lockfile-based counterpart already uses (`"npm"`,
  `"crates.io"`, `"Packagist"`, `"RubyGems"`, `"NuGet"`, `"PyPI"`, `"Maven"`).
  the existing `_LICENSE_FETCHERS` dispatch dict.
- A missing/unresolvable version is skipped, never guessed or fabricated - matches every existing
  parser's `if name and version:` style guard.
- No network calls in unit tests - every test uses a `tmp_path` fixture repo, matching
  `prototype/tests/test_vulnerabilities.py`'s and `test_licenses.py`'s existing style
  (`_mock_response`/`patch("aletheore.vulnerabilities.urllib.request.urlopen", ...)` only used for
  the two existing OSV/registry-facing tests, never for parser-only tests).
- Maven's external-parent-POM limitation (versions only knowable by fetching a parent POM not
  vendored in the repo) is an explicit, honest non-goal - such dependencies remain skipped, not
  silently faked.

---

### Task 1: npm - prefer resolved lockfile version over declared range

**Files:**
- Modify: `prototype/aletheore/vulnerabilities.py` (`_parse_npm_pins`, currently lines 42-56)
- Test: `prototype/tests/test_vulnerabilities.py`

**Interfaces:**
- Produces: `_parse_npm_pins(repo_path: Path) -> list[tuple[str, str, str]]` (signature unchanged)

- [ ] **Step 1: Write the failing precedence test**

Add to `prototype/tests/test_vulnerabilities.py`:

```python
def test_parse_npm_pins_prefers_lockfile_resolved_version(tmp_path):
    from aletheore.vulnerabilities import _parse_npm_pins

    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "package.json").write_text(
        json.dumps({"dependencies": {"left-pad": "^1.3.0"}, "devDependencies": {}})
    )
    (repo / "package-lock.json").write_text(
        json.dumps({"dependencies": {"left-pad": {"version": "1.3.1"}}})
    )

    pins = _parse_npm_pins(repo)

    assert ("left-pad", "1.3.1", "npm") in pins
    assert not any(p[1] == "1.3.0" for p in pins)


def test_parse_npm_pins_falls_back_to_package_json_when_no_lockfile(tmp_path):
    from aletheore.vulnerabilities import _parse_npm_pins

    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "package.json").write_text(
        json.dumps({"dependencies": {"left-pad": "^1.3.0"}, "devDependencies": {}})
    )

    pins = _parse_npm_pins(repo)

    assert ("left-pad", "1.3.0", "npm") in pins
```

- [ ] **Step 2: Run tests to verify the precedence test fails**

Run: `cd prototype && python -m pytest tests/test_vulnerabilities.py -k npm_pins -v`
Expected: `test_parse_npm_pins_prefers_lockfile_resolved_version` FAILS (finds `1.3.0`, not
`1.3.1`); `test_parse_npm_pins_falls_back_to_package_json_when_no_lockfile` already PASSES
(today's unchanged behavior).

- [ ] **Step 3: Modify `_parse_npm_pins`**

Replace the existing function body in `prototype/aletheore/vulnerabilities.py`:

```python
def _parse_npm_pins(repo_path: Path) -> list[tuple[str, str, str]]:
    package_json = repo_path / "package.json"
    if not package_json.exists():
        return []
    try:
        data = json.loads(package_json.read_text(encoding="utf-8", errors="ignore"))
    except json.JSONDecodeError:
        return []
    deps = {**data.get("dependencies", {}), **data.get("devDependencies", {})}

    resolved: dict[str, str] = {}
    lock_file = repo_path / "package-lock.json"
    if lock_file.exists():
        try:
            lock_data = json.loads(lock_file.read_text(encoding="utf-8", errors="ignore"))
            resolved = {
                name: details["version"]
                for name, details in lock_data.get("dependencies", {}).items()
                if "version" in details
            }
        except json.JSONDecodeError:
            resolved = {}

    pins = []
    for name, version in deps.items():
        if name in resolved:
            pins.append((name, resolved[name], "npm"))
            continue
        cleaned = version.lstrip("^~>=< ").strip()
        if cleaned and cleaned[0].isdigit():
            pins.append((name, cleaned, "npm"))
    return pins
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd prototype && python -m pytest tests/test_vulnerabilities.py -k npm_pins -v`
Expected: both tests PASS. Also run the pre-existing
`test_check_vulnerabilities_parses_pinned_pip_and_npm_versions` to confirm no regression (its
fixture has no `package-lock.json`, so behavior is unchanged).

- [ ] **Step 5: Commit**

```bash
cd prototype && git add aletheore/vulnerabilities.py tests/test_vulnerabilities.py
git commit -m "fix: prefer package-lock.json resolved version over package.json range"
```

---

### Task 2: Rust - fall back to Cargo.toml when Cargo.lock is absent

**Files:**
- Modify: `prototype/aletheore/vulnerabilities.py` (`_parse_cargo_pins`, currently lines 84-96)
- Test: `prototype/tests/test_vulnerabilities.py`

**Interfaces:**
- Produces: `_parse_cargo_pins(repo_path: Path) -> list[tuple[str, str, str]]` (signature
  unchanged); new private helper `_parse_cargo_toml_pins(repo_path: Path) -> list[tuple[str, str,
  str]]`

- [ ] **Step 1: Write the failing tests**

Add to `prototype/tests/test_vulnerabilities.py`:

```python
def test_parse_cargo_pins_falls_back_to_cargo_toml_when_no_lock(tmp_path):
    from aletheore.vulnerabilities import _parse_cargo_pins

    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "Cargo.toml").write_text(
        "[package]\n"
        'name = "mycrate"\n'
        "\n"
        "[dependencies]\n"
        'serde = "1.0.210"\n'
        'tokio = { version = "1.40.0", features = ["full"] }\n'
        'local_dep = { path = "../local_dep" }\n'
        'workspace_dep = { workspace = true }\n'
    )

    pins = _parse_cargo_pins(repo)

    assert ("serde", "1.0.210", "crates.io") in pins
    assert ("tokio", "1.40.0", "crates.io") in pins
    assert not any(p[0] == "local_dep" for p in pins)
    assert not any(p[0] == "workspace_dep" for p in pins)


def test_parse_cargo_pins_prefers_lock_file_when_present(tmp_path):
    from aletheore.vulnerabilities import _parse_cargo_pins

    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "Cargo.toml").write_text(
        '[dependencies]\nserde = "1.0.0"\n'
    )
    (repo / "Cargo.lock").write_text(
        '[[package]]\nname = "serde"\nversion = "1.0.210"\n'
    )

    pins = _parse_cargo_pins(repo)

    assert ("serde", "1.0.210", "crates.io") in pins
    assert not any(p[1] == "1.0.0" for p in pins)
```

- [ ] **Step 2: Run tests to verify the new ones fail**

Run: `cd prototype && python -m pytest tests/test_vulnerabilities.py -k cargo_pins -v`
Expected: `test_parse_cargo_pins_falls_back_to_cargo_toml_when_no_lock` FAILS (returns `[]` today);
`test_parse_cargo_pins_prefers_lock_file_when_present` and the existing
`test_parse_cargo_pins_reads_package_tables`/`test_parse_cargo_pins_empty_when_no_cargo_lock`
PASS unchanged.

- [ ] **Step 3: Modify `_parse_cargo_pins` and add the fallback helper**

```python
def _parse_cargo_pins(repo_path: Path) -> list[tuple[str, str, str]]:
    cargo_lock = repo_path / "Cargo.lock"
    if not cargo_lock.exists():
        return _parse_cargo_toml_pins(repo_path)
    try:
        data = tomllib.loads(cargo_lock.read_text(encoding="utf-8", errors="ignore"))
    except tomllib.TOMLDecodeError:
        return []
    return [
        (pkg["name"], pkg["version"], "crates.io")
        for pkg in data.get("package", [])
        if "name" in pkg and "version" in pkg
    ]


def _parse_cargo_toml_pins(repo_path: Path) -> list[tuple[str, str, str]]:
    cargo_toml = repo_path / "Cargo.toml"
    if not cargo_toml.exists():
        return []
    try:
        data = tomllib.loads(cargo_toml.read_text(encoding="utf-8", errors="ignore"))
    except tomllib.TOMLDecodeError:
        return []
    pins = []
    for section in ("dependencies", "dev-dependencies"):
        for name, value in data.get(section, {}).items():
            if isinstance(value, str):
                version = value.lstrip("^~>=< ").strip()
            elif isinstance(value, dict):
                version = str(value.get("version", "")).lstrip("^~>=< ").strip()
            else:
                continue
            if version and version[0].isdigit():
                pins.append((name, version, "crates.io"))
    return pins
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd prototype && python -m pytest tests/test_vulnerabilities.py -k cargo_pins -v`
Expected: all 4 tests PASS.

- [ ] **Step 5: Commit**

```bash
cd prototype && git add aletheore/vulnerabilities.py tests/test_vulnerabilities.py
git commit -m "feat: fall back to Cargo.toml when Cargo.lock is absent"
```

---

### Task 3: PHP - fall back to composer.json when composer.lock is absent

**Files:**
- Modify: `prototype/aletheore/vulnerabilities.py` (`_parse_composer_pins`, currently lines
  150-163)
- Test: `prototype/tests/test_vulnerabilities.py`

**Interfaces:**
- Produces: `_parse_composer_pins(repo_path: Path) -> list[tuple[str, str, str]]` (signature
  unchanged); new private helper `_parse_composer_json_pins(repo_path: Path) -> list[tuple[str,
  str, str]]`

- [ ] **Step 1: Write the failing tests**

Add to `prototype/tests/test_vulnerabilities.py`:

```python
def test_parse_composer_pins_falls_back_to_composer_json_when_no_lock(tmp_path):
    from aletheore.vulnerabilities import _parse_composer_pins

    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "composer.json").write_text(
        json.dumps(
            {
                "require": {
                    "php": "^7.2.5 || ^8.0",
                    "ext-json": "*",
                    "guzzlehttp/promises": "^2.5.1",
                }
            }
        )
    )

    pins = _parse_composer_pins(repo)

    assert ("guzzlehttp/promises", "2.5.1", "Packagist") in pins
    assert not any(p[0] == "php" for p in pins)
    assert not any(p[0] == "ext-json" for p in pins)


def test_parse_composer_pins_prefers_lock_file_when_present(tmp_path):
    from aletheore.vulnerabilities import _parse_composer_pins

    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "composer.json").write_text(
        json.dumps({"require": {"guzzlehttp/promises": "^2.5.1"}})
    )
    (repo / "composer.lock").write_text(
        json.dumps({"packages": [{"name": "guzzlehttp/promises", "version": "v2.5.3"}]})
    )

    pins = _parse_composer_pins(repo)

    assert ("guzzlehttp/promises", "2.5.3", "Packagist") in pins
    assert not any(p[1] == "2.5.1" for p in pins)
```

- [ ] **Step 2: Run tests to verify the new one fails**

Run: `cd prototype && python -m pytest tests/test_vulnerabilities.py -k composer_pins -v`
Expected: `test_parse_composer_pins_falls_back_to_composer_json_when_no_lock` FAILS (returns `[]`
today); the lock-file precedence test and existing
`test_parse_composer_pins_reads_packages_array`/`test_parse_composer_pins_empty_when_no_composer_lock`
PASS unchanged.

- [ ] **Step 3: Modify `_parse_composer_pins` and add the fallback helper**

```python
def _parse_composer_pins(repo_path: Path) -> list[tuple[str, str, str]]:
    composer_lock = repo_path / "composer.lock"
    if not composer_lock.exists():
        return _parse_composer_json_pins(repo_path)
    try:
        data = json.loads(composer_lock.read_text(encoding="utf-8", errors="ignore"))
    except json.JSONDecodeError:
        return []
    return [
        (pkg["name"], pkg["version"].lstrip("v"), "Packagist")
        for pkg in data.get("packages", [])
        if "name" in pkg and "version" in pkg
    ]


def _parse_composer_json_pins(repo_path: Path) -> list[tuple[str, str, str]]:
    composer_json = repo_path / "composer.json"
    if not composer_json.exists():
        return []
    try:
        data = json.loads(composer_json.read_text(encoding="utf-8", errors="ignore"))
    except json.JSONDecodeError:
        return []
    pins = []
    for name, version in data.get("require", {}).items():
        if "/" not in name:
            continue
        cleaned = version.lstrip("^~>=< ").strip().split("|")[0].strip()
        if cleaned and cleaned[0].isdigit():
            pins.append((name, cleaned, "Packagist"))
    return pins
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd prototype && python -m pytest tests/test_vulnerabilities.py -k composer_pins -v`
Expected: all 4 tests PASS.

- [ ] **Step 5: Commit**

```bash
cd prototype && git add aletheore/vulnerabilities.py tests/test_vulnerabilities.py
git commit -m "feat: fall back to composer.json when composer.lock is absent"
```

---

### Task 4: Ruby - fall back to *.gemspec when Gemfile.lock is absent

**Files:**
- Modify: `prototype/aletheore/vulnerabilities.py` (`_parse_gemfile_lock_pins`, currently lines
  123-146)
- Test: `prototype/tests/test_vulnerabilities.py`

**Interfaces:**
- Produces: `_parse_gemfile_lock_pins(repo_path: Path) -> list[tuple[str, str, str]]` (signature
  unchanged); new private helper `_parse_gemspec_pins(repo_path: Path) -> list[tuple[str, str,
  str]]`

- [ ] **Step 1: Write the failing tests**

Add to `prototype/tests/test_vulnerabilities.py`:

```python
def test_parse_gemfile_lock_pins_falls_back_to_gemspec_when_no_lock(tmp_path):
    from aletheore.vulnerabilities import _parse_gemfile_lock_pins

    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "mygem.gemspec").write_text(
        "Gem::Specification.new do |s|\n"
        '  s.name = "mygem"\n'
        '  s.add_dependency "activesupport", "~> 8.0.0"\n'
        '  s.add_runtime_dependency "nokogiri", ">= 1.16.7"\n'
        "  s.add_dependency \"actionpack\", version\n"
        "end\n"
    )

    pins = _parse_gemfile_lock_pins(repo)

    assert ("activesupport", "8.0.0", "RubyGems") in pins
    assert ("nokogiri", "1.16.7", "RubyGems") in pins
    assert not any(p[0] == "actionpack" for p in pins)


def test_parse_gemfile_lock_pins_prefers_lock_file_when_present(tmp_path):
    from aletheore.vulnerabilities import _parse_gemfile_lock_pins

    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "mygem.gemspec").write_text(
        'Gem::Specification.new do |s|\n  s.add_dependency "activesupport", "~> 8.0.0"\nend\n'
    )
    (repo / "Gemfile.lock").write_text(
        "GEM\n  remote: https://rubygems.org/\n  specs:\n    activesupport (8.0.1)\n\n"
        "PLATFORMS\n  ruby\n"
    )

    pins = _parse_gemfile_lock_pins(repo)

    assert ("activesupport", "8.0.1", "RubyGems") in pins
    assert not any(p[1] == "8.0.0" for p in pins)
```

- [ ] **Step 2: Run tests to verify the new one fails**

Run: `cd prototype && python -m pytest tests/test_vulnerabilities.py -k gemfile_lock_pins -v`
Expected: `test_parse_gemfile_lock_pins_falls_back_to_gemspec_when_no_lock` FAILS (returns `[]`
today); the other two PASS unchanged (existing tests plus the new precedence test, which matches
today's behavior already since `Gemfile.lock` exists in that fixture).

- [ ] **Step 3: Modify `_parse_gemfile_lock_pins` and add the fallback helper**

Add `import re` is already present at the top of the file (used by `_parse_gemfile_lock_pins`
already). Replace the function:

```python
def _parse_gemfile_lock_pins(repo_path: Path) -> list[tuple[str, str, str]]:
    gemfile_lock = repo_path / "Gemfile.lock"
    if not gemfile_lock.exists():
        return _parse_gemspec_pins(repo_path)
    pins = []
    in_gem_section = False
    in_gem_specs = False
    for line in gemfile_lock.read_text(encoding="utf-8", errors="ignore").splitlines():
        if line == "GEM":
            in_gem_section = True
            in_gem_specs = False
            continue
        if line and not line.startswith(" "):
            in_gem_section = False
            in_gem_specs = False
            continue
        if in_gem_section and line == "  specs:":
            in_gem_specs = True
            continue
        if not in_gem_specs:
            continue
        match = re.match(r"^ {4}(\S+) \(([^)]+)\)$", line)
        if match:
            pins.append((match.group(1), match.group(2), "RubyGems"))
    return pins


def _parse_gemspec_pins(repo_path: Path) -> list[tuple[str, str, str]]:
    pins = []
    for gemspec in repo_path.glob("*.gemspec"):
        text = gemspec.read_text(encoding="utf-8", errors="ignore")
        for match in re.finditer(
            r'add_(?:runtime_)?dependency\s+["\']([^"\']+)["\']\s*,\s*["\']([^"\']+)["\']',
            text,
        ):
            name, version = match.groups()
            cleaned = version.lstrip("~>=< ").strip()
            if cleaned and cleaned[0].isdigit():
                pins.append((name, cleaned, "RubyGems"))
    return pins
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd prototype && python -m pytest tests/test_vulnerabilities.py -k gemfile_lock_pins -v`
Expected: all tests PASS.

- [ ] **Step 5: Commit**

```bash
cd prototype && git add aletheore/vulnerabilities.py tests/test_vulnerabilities.py
git commit -m "feat: fall back to *.gemspec when Gemfile.lock is absent"
```

---

### Task 5: C# - two-tier fallback (.csproj, then Directory.Packages.props)

**Files:**
- Modify: `prototype/aletheore/vulnerabilities.py` (`_parse_nuget_pins`, currently lines 165-180)
- Test: `prototype/tests/test_vulnerabilities.py`

**Interfaces:**
- Produces: `_parse_nuget_pins(repo_path: Path) -> list[tuple[str, str, str]]` (signature
  unchanged); new private helpers `_parse_csproj_pins(repo_path: Path) -> list[tuple[str, str,
  str]]` and `_parse_directory_packages_props(repo_path: Path) -> dict[str, str]`

- [ ] **Step 1: Write the failing tests**

Add to `prototype/tests/test_vulnerabilities.py`:

```python
def test_parse_nuget_pins_falls_back_to_csproj_with_explicit_version(tmp_path):
    from aletheore.vulnerabilities import _parse_nuget_pins

    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "src").mkdir()
    (repo / "src" / "Web.csproj").write_text(
        '<Project Sdk="Microsoft.NET.Sdk.Web">\n'
        "  <ItemGroup>\n"
        '    <PackageReference Include="Serilog" Version="3.1.1" />\n'
        "  </ItemGroup>\n"
        "</Project>\n"
    )

    pins = _parse_nuget_pins(repo)

    assert ("Serilog", "3.1.1", "NuGet") in pins


def test_parse_nuget_pins_resolves_central_package_management(tmp_path):
    from aletheore.vulnerabilities import _parse_nuget_pins

    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "Directory.Packages.props").write_text(
        "<Project>\n"
        "  <ItemGroup>\n"
        '    <PackageVersion Include="Serilog" Version="3.1.1" />\n'
        "  </ItemGroup>\n"
        "</Project>\n"
    )
    (repo / "src").mkdir()
    (repo / "src" / "Web.csproj").write_text(
        "<Project>\n"
        "  <ItemGroup>\n"
        '    <PackageReference Include="Serilog" />\n'
        "  </ItemGroup>\n"
        "</Project>\n"
    )

    pins = _parse_nuget_pins(repo)

    assert ("Serilog", "3.1.1", "NuGet") in pins


def test_parse_nuget_pins_prefers_lock_file_when_present(tmp_path):
    from aletheore.vulnerabilities import _parse_nuget_pins

    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "src").mkdir()
    (repo / "src" / "Web.csproj").write_text(
        '<Project><ItemGroup><PackageReference Include="Serilog" Version="3.1.1" />'
        "</ItemGroup></Project>\n"
    )
    (repo / "packages.lock.json").write_text(
        json.dumps({"dependencies": {"net8.0": {"Serilog": {"resolved": "3.1.2"}}}})
    )

    pins = _parse_nuget_pins(repo)

    assert ("Serilog", "3.1.2", "NuGet") in pins
    assert not any(p[1] == "3.1.1" for p in pins)
```

- [ ] **Step 2: Run tests to verify the new ones fail**

Run: `cd prototype && python -m pytest tests/test_vulnerabilities.py -k nuget_pins -v`
Expected: `test_parse_nuget_pins_falls_back_to_csproj_with_explicit_version` and
`test_parse_nuget_pins_resolves_central_package_management` FAIL (return `[]` today);
`test_parse_nuget_pins_prefers_lock_file_when_present` and the existing
`test_parse_nuget_pins_reads_resolved_versions`/`test_parse_nuget_pins_empty_when_no_lock_file`
PASS unchanged.

- [ ] **Step 3: Modify `_parse_nuget_pins` and add the fallback helpers**

```python
def _parse_nuget_pins(repo_path: Path) -> list[tuple[str, str, str]]:
    lock_file = repo_path / "packages.lock.json"
    if not lock_file.exists():
        return _parse_csproj_pins(repo_path)
    try:
        data = json.loads(lock_file.read_text(encoding="utf-8", errors="ignore"))
    except json.JSONDecodeError:
        return []
    pins = []
    for framework_deps in data.get("dependencies", {}).values():
        for name, details in framework_deps.items():
            resolved = details.get("resolved")
            if resolved:
                pins.append((name, resolved, "NuGet"))
    return pins


def _parse_directory_packages_props(repo_path: Path) -> dict[str, str]:
    props_file = repo_path / "Directory.Packages.props"
    if not props_file.exists():
        return {}
    try:
        root = ElementTree.fromstring(props_file.read_text(encoding="utf-8", errors="ignore"))
    except ElementTree.ParseError:
        return {}
    return {
        ref.get("Include"): ref.get("Version")
        for ref in root.findall(".//PackageVersion")
        if ref.get("Include") and ref.get("Version")
    }


def _parse_csproj_pins(repo_path: Path) -> list[tuple[str, str, str]]:
    central_versions = _parse_directory_packages_props(repo_path)
    pins = []
    for csproj in repo_path.rglob("*.csproj"):
        try:
            root = ElementTree.fromstring(csproj.read_text(encoding="utf-8", errors="ignore"))
        except ElementTree.ParseError:
            continue
        for ref in root.findall(".//PackageReference"):
            name = ref.get("Include")
            if not name:
                continue
            version = ref.get("Version") or central_versions.get(name)
            if version:
                pins.append((name, version, "NuGet"))
    return pins
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd prototype && python -m pytest tests/test_vulnerabilities.py -k nuget_pins -v`
Expected: all 5 tests PASS.

- [ ] **Step 5: Commit**

```bash
cd prototype && git add aletheore/vulnerabilities.py tests/test_vulnerabilities.py
git commit -m "feat: fall back to .csproj/Directory.Packages.props when packages.lock.json is absent"
```

---

### Task 6: Python - additive pyproject.toml parsing (PEP 621 + Poetry)

**Files:**
- Modify: `prototype/aletheore/vulnerabilities.py` (add new function; wire into
  `check_vulnerabilities` and add corresponding wiring note for `check_dependency_licenses` in
  `licenses.py`)
- Modify: `prototype/aletheore/licenses.py` (`check_dependency_licenses`'s pin concatenation)
- Test: `prototype/tests/test_vulnerabilities.py`

**Interfaces:**
- Produces: `_parse_pyproject_pins(repo_path: Path) -> list[tuple[str, str, str]]`
- Consumes: none (new, independent parser)

- [ ] **Step 1: Write the failing tests**

Add to `prototype/tests/test_vulnerabilities.py`:

```python
def test_parse_pyproject_pins_reads_pep621_dependencies(tmp_path):
    from aletheore.vulnerabilities import _parse_pyproject_pins

    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "pyproject.toml").write_text(
        "[project]\n"
        'name = "django"\n'
        "dependencies = [\n"
        '  "asgiref>=3.12.1",\n'
        '  "sqlparse>=0.5.0",\n'
        '  "tzdata; sys_platform == \'win32\'",\n'
        "]\n"
    )

    pins = _parse_pyproject_pins(repo)

    assert ("asgiref", "3.12.1", "PyPI") in pins
    assert ("sqlparse", "0.5.0", "PyPI") in pins
    assert not any(p[0] == "tzdata" for p in pins)


def test_parse_pyproject_pins_reads_poetry_dependencies(tmp_path):
    from aletheore.vulnerabilities import _parse_pyproject_pins

    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "pyproject.toml").write_text(
        "[tool.poetry.dependencies]\n"
        'python = "^3.11"\n'
        'requests = "^2.31.0"\n'
        'flask = { version = "^3.0.0", optional = true }\n'
    )

    pins = _parse_pyproject_pins(repo)

    assert ("requests", "2.31.0", "PyPI") in pins
    assert ("flask", "3.0.0", "PyPI") in pins
    assert not any(p[0] == "python" for p in pins)


def test_parse_pyproject_pins_empty_when_no_pyproject(tmp_path):
    from aletheore.vulnerabilities import _parse_pyproject_pins

    repo = tmp_path / "repo"
    repo.mkdir()

    assert _parse_pyproject_pins(repo) == []
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd prototype && python -m pytest tests/test_vulnerabilities.py -k pyproject_pins -v`
Expected: all 3 FAIL with `ImportError: cannot import name '_parse_pyproject_pins'`.

- [ ] **Step 3: Add `_parse_pyproject_pins`**

Add to `prototype/aletheore/vulnerabilities.py`, near `_parse_pip_pins`:

```python
def _parse_pyproject_pins(repo_path: Path) -> list[tuple[str, str, str]]:
    pyproject = repo_path / "pyproject.toml"
    if not pyproject.exists():
        return []
    try:
        data = tomllib.loads(pyproject.read_text(encoding="utf-8", errors="ignore"))
    except tomllib.TOMLDecodeError:
        return []

    pins = []
    for entry in data.get("project", {}).get("dependencies", []):
        match = re.match(r"^([A-Za-z0-9_.\-]+)\s*(==|>=)\s*([0-9][^;,\s]*)", entry)
        if match:
            name, _, version = match.groups()
            pins.append((name.lower(), version, "PyPI"))

    poetry_deps = data.get("tool", {}).get("poetry", {}).get("dependencies", {})
    for name, value in poetry_deps.items():
        if name.lower() == "python":
            continue
        if isinstance(value, str):
            version = value.lstrip("^~>=< ").strip()
        elif isinstance(value, dict):
            version = str(value.get("version", "")).lstrip("^~>=< ").strip()
        else:
            continue
        if version and version[0].isdigit():
            pins.append((name.lower(), version, "PyPI"))
    return pins
```

`import re` and `import tomllib` are already present at the top of the file.

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd prototype && python -m pytest tests/test_vulnerabilities.py -k pyproject_pins -v`
Expected: all 3 PASS.

- [ ] **Step 5: Wire into `check_vulnerabilities` and `check_dependency_licenses`**

In `prototype/aletheore/vulnerabilities.py`, `check_vulnerabilities`'s pin concatenation, add
`+ _parse_pyproject_pins(repo_path)` alongside the existing `_parse_pip_pins(repo_path)` line.

In `prototype/aletheore/licenses.py`:
- Add `_parse_pyproject_pins` to the `from aletheore.vulnerabilities import (...)` block.
- In `check_dependency_licenses`'s pin concatenation, add `+ _parse_pyproject_pins(repo_path)`
  alongside the existing `_parse_pip_pins(repo_path)` line.

Add one integration-level test to `prototype/tests/test_vulnerabilities.py` confirming both
sources combine:

```python
def test_check_vulnerabilities_includes_pyproject_pins(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "pyproject.toml").write_text(
        '[project]\ndependencies = ["asgiref>=3.12.1"]\n'
    )
    batch_response = _mock_response({"results": [{}]})

    with patch(
        "aletheore.vulnerabilities.urllib.request.urlopen", return_value=batch_response
    ) as mock_urlopen:
        result = check_vulnerabilities(repo)

    assert result == {"checked": True, "reason": None, "findings": []}
    sent_body = json.loads(mock_urlopen.call_args[0][0].data)
    assert {"package": {"name": "asgiref", "ecosystem": "PyPI"}, "version": "3.12.1"} in sent_body[
        "queries"
    ]
```

- [ ] **Step 6: Run the full vulnerabilities and licenses test suites**

Run: `cd prototype && python -m pytest tests/test_vulnerabilities.py tests/test_licenses.py -v`
Expected: all tests PASS, including the new integration test.

- [ ] **Step 7: Commit**

```bash
cd prototype && git add aletheore/vulnerabilities.py aletheore/licenses.py tests/test_vulnerabilities.py
git commit -m "feat: parse pyproject.toml dependencies (PEP 621 + Poetry) additively"
```

---

### Task 7: Maven - scope XPath correctly, resolve properties/BOM, traverse modules

**Files:**
- Modify: `prototype/aletheore/vulnerabilities.py` (`_parse_maven_pins`, currently lines 99-121)
- Test: `prototype/tests/test_vulnerabilities.py`

**Interfaces:**
- Produces: `_parse_maven_pins(repo_path: Path) -> list[tuple[str, str, str]]` (signature
  unchanged from the outside; gains an internal `_pom_path` keyword-only parameter used only for
  its own recursive module traversal, not part of the public contract other modules rely on)

- [ ] **Step 1: Write the failing tests**

Add to `prototype/tests/test_vulnerabilities.py`. This replaces the existing
`test_parse_maven_pins_reads_direct_dependencies` fixture with one that also exercises the
profile/dependencyManagement over-counting fix, plus three new tests:

```python
def test_parse_maven_pins_reads_direct_dependencies_only(tmp_path):
    from aletheore.vulnerabilities import _parse_maven_pins

    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "pom.xml").write_text(
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<project xmlns="http://maven.apache.org/POM/4.0.0">\n'
        "  <dependencies>\n"
        "    <dependency>\n"
        "      <groupId>org.springframework</groupId>\n"
        "      <artifactId>spring-core</artifactId>\n"
        "      <version>6.1.14</version>\n"
        "    </dependency>\n"
        "  </dependencies>\n"
        "  <dependencyManagement>\n"
        "    <dependencies>\n"
        "      <dependency>\n"
        "        <groupId>com.example</groupId>\n"
        "        <artifactId>managed-only</artifactId>\n"
        "        <version>2.0.0</version>\n"
        "      </dependency>\n"
        "    </dependencies>\n"
        "  </dependencyManagement>\n"
        "  <profiles>\n"
        "    <profile>\n"
        "      <id>test</id>\n"
        "      <dependencies>\n"
        "        <dependency>\n"
        "          <groupId>com.example</groupId>\n"
        "          <artifactId>profile-only</artifactId>\n"
        "          <version>1.0.0</version>\n"
        "        </dependency>\n"
        "      </dependencies>\n"
        "    </profile>\n"
        "  </profiles>\n"
        "</project>\n"
    )

    pins = _parse_maven_pins(repo)

    assert ("org.springframework:spring-core", "6.1.14", "Maven") in pins
    assert not any(p[0] == "com.example:managed-only" for p in pins)
    assert not any(p[0] == "com.example:profile-only" for p in pins)


def test_parse_maven_pins_resolves_property_placeholder_version(tmp_path):
    from aletheore.vulnerabilities import _parse_maven_pins

    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "pom.xml").write_text(
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<project xmlns="http://maven.apache.org/POM/4.0.0">\n'
        "  <properties>\n"
        "    <webjars-locator.version>0.52</webjars-locator.version>\n"
        "  </properties>\n"
        "  <dependencies>\n"
        "    <dependency>\n"
        "      <groupId>org.webjars</groupId>\n"
        "      <artifactId>webjars-locator-lite</artifactId>\n"
        "      <version>${webjars-locator.version}</version>\n"
        "    </dependency>\n"
        "    <dependency>\n"
        "      <groupId>com.example</groupId>\n"
        "      <artifactId>unresolvable</artifactId>\n"
        "      <version>${not.defined.anywhere}</version>\n"
        "    </dependency>\n"
        "  </dependencies>\n"
        "</project>\n"
    )

    pins = _parse_maven_pins(repo)

    assert ("org.webjars:webjars-locator-lite", "0.52", "Maven") in pins
    assert not any(p[0] == "com.example:unresolvable" for p in pins)


def test_parse_maven_pins_falls_back_to_same_file_dependency_management(tmp_path):
    from aletheore.vulnerabilities import _parse_maven_pins

    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "pom.xml").write_text(
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<project xmlns="http://maven.apache.org/POM/4.0.0">\n'
        "  <dependencyManagement>\n"
        "    <dependencies>\n"
        "      <dependency>\n"
        "        <groupId>org.springframework.boot</groupId>\n"
        "        <artifactId>spring-boot-starter-web</artifactId>\n"
        "        <version>3.3.4</version>\n"
        "      </dependency>\n"
        "    </dependencies>\n"
        "  </dependencyManagement>\n"
        "  <dependencies>\n"
        "    <dependency>\n"
        "      <groupId>org.springframework.boot</groupId>\n"
        "      <artifactId>spring-boot-starter-web</artifactId>\n"
        "    </dependency>\n"
        "    <dependency>\n"
        "      <groupId>com.example</groupId>\n"
        "      <artifactId>no-version-anywhere</artifactId>\n"
        "    </dependency>\n"
        "  </dependencies>\n"
        "</project>\n"
    )

    pins = _parse_maven_pins(repo)

    assert ("org.springframework.boot:spring-boot-starter-web", "3.3.4", "Maven") in pins
    assert not any(p[0] == "com.example:no-version-anywhere" for p in pins)


def test_parse_maven_pins_traverses_modules(tmp_path):
    from aletheore.vulnerabilities import _parse_maven_pins

    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "pom.xml").write_text(
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<project xmlns="http://maven.apache.org/POM/4.0.0">\n'
        "  <modules>\n"
        "    <module>dubbo-common</module>\n"
        "    <module>missing-module</module>\n"
        "  </modules>\n"
        "</project>\n"
    )
    (repo / "dubbo-common").mkdir()
    (repo / "dubbo-common" / "pom.xml").write_text(
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<project xmlns="http://maven.apache.org/POM/4.0.0">\n'
        "  <dependencies>\n"
        "    <dependency>\n"
        "      <groupId>org.apache.commons</groupId>\n"
        "      <artifactId>commons-lang3</artifactId>\n"
        "      <version>3.14.0</version>\n"
        "    </dependency>\n"
        "  </dependencies>\n"
        "</project>\n"
    )

    pins = _parse_maven_pins(repo)

    assert ("org.apache.commons:commons-lang3", "3.14.0", "Maven") in pins
```

- [ ] **Step 2: Run tests to verify the new ones fail and the modified one fails as expected**

Run: `cd prototype && python -m pytest tests/test_vulnerabilities.py -k maven_pins -v`
Expected: `test_parse_maven_pins_reads_direct_dependencies_only` FAILS (today's XPath also matches
`managed-only` and `profile-only`); the three new tests FAIL (property/BOM/module features don't
exist yet); `test_parse_maven_pins_empty_when_no_pom` PASSES unchanged.

- [ ] **Step 3: Rewrite `_parse_maven_pins`**

Replace the existing function in `prototype/aletheore/vulnerabilities.py`:

```python
def _parse_maven_pins(
    repo_path: Path, _pom_path: Path | None = None
) -> list[tuple[str, str, str]]:
    pom_path = _pom_path if _pom_path is not None else repo_path / "pom.xml"
    if not pom_path.exists():
        return []
    try:
        root = ElementTree.fromstring(pom_path.read_text(encoding="utf-8", errors="ignore"))
    except ElementTree.ParseError:
        return []
    ns = {"m": "http://maven.apache.org/POM/4.0.0"}

    properties_el = root.find("m:properties", ns)
    properties = {
        child.tag.split("}")[-1]: (child.text or "").strip()
        for child in (properties_el if properties_el is not None else [])
    }

    managed_versions: dict[str, str] = {}
    dep_mgmt = root.find("m:dependencyManagement/m:dependencies", ns)
    if dep_mgmt is not None:
        for dep in dep_mgmt.findall("m:dependency", ns):
            group = dep.find("m:groupId", ns)
            artifact = dep.find("m:artifactId", ns)
            version = dep.find("m:version", ns)
            if (
                group is not None
                and artifact is not None
                and version is not None
                and group.text
                and artifact.text
                and version.text
            ):
                key = f"{group.text.strip()}:{artifact.text.strip()}"
                managed_versions[key] = version.text.strip()

    pins = []
    direct_deps = root.find("m:dependencies", ns)
    for dep in direct_deps.findall("m:dependency", ns) if direct_deps is not None else []:
        group = dep.find("m:groupId", ns)
        artifact = dep.find("m:artifactId", ns)
        if group is None or artifact is None or not group.text or not artifact.text:
            continue
        key = f"{group.text.strip()}:{artifact.text.strip()}"

        version_el = dep.find("m:version", ns)
        version_text = (version_el.text or "").strip() if version_el is not None else ""

        if version_text.startswith("${") and version_text.endswith("}"):
            version_text = properties.get(version_text[2:-1], "")

        if not version_text:
            version_text = managed_versions.get(key, "")

        if version_text and not version_text.startswith("$"):
            pins.append((key, version_text, "Maven"))

    modules_el = root.find("m:modules", ns)
    for module in (modules_el.findall("m:module", ns) if modules_el is not None else []):
        if not module.text:
            continue
        module_pom = pom_path.parent / module.text.strip() / "pom.xml"
        if module_pom.exists():
            pins.extend(_parse_maven_pins(repo_path, _pom_path=module_pom))

    return pins
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd prototype && python -m pytest tests/test_vulnerabilities.py -k maven_pins -v`
Expected: all 5 tests PASS.

- [ ] **Step 5: Run the full regression suite**

Run: `cd prototype && python -m pytest tests/ -v`
Expected: all tests PASS - the Maven rewrite touches only `_parse_maven_pins`, which no other
parser or fetcher depends on structurally.

- [ ] **Step 6: Commit**

```bash
cd prototype && git add aletheore/vulnerabilities.py tests/test_vulnerabilities.py
git commit -m "fix: scope Maven dependency discovery correctly, resolve properties/BOM, traverse modules"
```

---

### Task 8: Real-world validation and showcase data regeneration

**Files:**
- No source changes - validation only.
- Modify: `website/showcase-data.js` (regenerated, not hand-edited)

- [ ] **Step 1: Run the full prototype test suite one more time**

Run: `cd prototype && python -m pytest tests/ -v`
Expected: all tests PASS (should already be true after Task 7, this is a final confirmation
before the real-world run).

- [ ] **Step 2: Re-scan Django at its existing pinned commit**

```bash
mkdir -p /tmp/aletheore-manifest-validation
cd /tmp/aletheore-manifest-validation
git clone --quiet https://github.com/django/django.git django
cd django
git checkout --quiet 3d34265d5d1b83fee5df3c1b6f55087b1a6a1ded
aletheore scan .
python3 -c "
import json
data = json.load(open('.aletheore/evidence.json'))
lic = data['security']['dependency_licenses']
vuln = data['security']['dependency_vulnerabilities']
print('license findings:', len(lic['findings']), 'checked:', lic['checked'])
print('vulnerability findings:', len(vuln['findings']), 'checked:', vuln['checked'])
"
```

Expected: both `checked: True`; the pin count backing these checks is no longer zero (Django's
`pyproject.toml` declares `asgiref>=3.12.1` and `sqlparse>=0.5.0`) - a small, honest number is
expected here, not a dramatic one. Do not hand-wave this: if both counts are still 0, treat that
as a real regression to investigate (e.g. a typo in the `[project]` key lookup) before proceeding,
not as an acceptable outcome.

- [ ] **Step 3: Re-scan Express at its existing pinned commit**

```bash
cd /tmp/aletheore-manifest-validation
git clone --quiet https://github.com/expressjs/express.git express
cd express
git checkout --quiet ae6dd37680e3a00618d6c8a3e522f0ee4eeba1a4
aletheore scan .
python3 -c "
import json
data = json.load(open('.aletheore/evidence.json'))
lic = data['security']['dependency_licenses']
vuln = data['security']['dependency_vulnerabilities']
print('license findings:', len(lic['findings']), 'checked:', lic['checked'])
print('vulnerability findings:', len(vuln['findings']), 'checked:', vuln['checked'])
"
```

Expected: `checked: True` for both, same as before this plan (Express's `package.json` was
already parsed correctly pre-fix) - confirms the npm lockfile-preference change didn't regress a
repo with no lockfile.

- [ ] **Step 4: Regenerate `website/showcase-data.js`**

```bash
cd "/Users/arihantkaul/Documents/GitHub/Veridion"
bash scripts/generate-showcase-data.sh
```

If `scripts/generate-showcase-data.sh` expects the three repos cloned at specific local paths,
point it at the fresh clones from Steps 2-3 above (Kubernetes does not need to be re-cloned or
re-scanned - its `go.mod`-based numbers are unaffected by this plan, which touches no Go logic).
Confirm the regenerated file still has non-`0` numbers for Kubernetes matching what's already
committed, and now non-`0` `licenseFindingsCount`/dependency pin coverage for Django reflecting
Step 2's real result.

- [ ] **Step 5: Diff and review the regenerated file before committing**

```bash
git diff website/showcase-data.js
```

Confirm only Django's (and, if applicable, Express's) numeric fields changed, and that
Kubernetes's block and the `toonDemo` block are untouched.

- [ ] **Step 6: Commit**

```bash
git add website/showcase-data.js
git commit -m "chore: regenerate showcase data now that pyproject.toml dependencies are detected"
```
