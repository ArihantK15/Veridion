# Aletheore CLI Quality-of-Life Gaps Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Close four real, user-facing gaps in the `aletheore` CLI's command surface: no `--version` flag, no `logout` command, shell completion explicitly disabled, and no way to scaffold a `.aletheore.json` config file.

**Architecture:** All four are additive, isolated changes to `prototype/aletheore/cli.py` (plus one new function in `prototype/aletheore/credentials.py`). No existing command's behavior changes. No new dependencies.

**Tech Stack:** Python 3.11+, Typer, Rich (existing stack, unchanged).

## Global Constraints

- No new dependencies.
- Follow the existing lazy-import pattern in `cli.py`: heavy imports (e.g. `aletheore.credentials`, `aletheore.device_auth`) are imported inside the command function body, not at module top level (see `login`/`status` for the existing pattern). This matters — a regression here previously caused CLI startup to take seconds; see the commit `930e5c9` history for why.
- Every new/changed behavior needs a test in `prototype/tests/test_cli.py` (existing file, has a `CliRunner`-based pattern already — check its imports before adding tests).

---

### Task 1: Add `clear_api_key` to `credentials.py`

**Files:**
- Modify: `prototype/aletheore/credentials.py`
- Test: `prototype/tests/test_credentials.py` (existing file - check its patterns before adding)

**Interfaces:**
- Produces: `clear_api_key(provider_name: str, credentials_path: Path = DEFAULT_CREDENTIALS_PATH) -> bool` — removes the key for `provider_name` from the credentials JSON file if present. Returns `True` if a key was actually removed, `False` if there was nothing to remove (file missing, or key not present). Never raises for a missing file.

- [ ] **Step 1: Write the failing test**

```python
def test_clear_api_key_removes_saved_key(tmp_path):
    from aletheore.credentials import clear_api_key, save_api_token, has_api_key

    path = tmp_path / "credentials.json"
    save_api_token("aletheore-managed-audit", "tok-123", path)
    assert has_api_key("UNUSED_ENV", "aletheore-managed-audit", credentials_path=path)

    removed = clear_api_key("aletheore-managed-audit", path)

    assert removed is True
    assert not has_api_key("UNUSED_ENV", "aletheore-managed-audit", credentials_path=path)


def test_clear_api_key_returns_false_when_nothing_to_clear(tmp_path):
    from aletheore.credentials import clear_api_key

    path = tmp_path / "credentials.json"
    assert clear_api_key("aletheore-managed-audit", path) is False
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd prototype && python -m pytest tests/test_credentials.py -k clear_api_key -v`
Expected: FAIL with `ImportError: cannot import name 'clear_api_key'`

- [ ] **Step 3: Write minimal implementation**

Add to `prototype/aletheore/credentials.py`, right after the existing `_save_key` function (reuse its file-reading pattern exactly):

```python
def clear_api_key(provider_name: str, credentials_path: Path = DEFAULT_CREDENTIALS_PATH) -> bool:
    if not credentials_path.exists():
        return False
    try:
        data = json.loads(credentials_path.read_text())
    except json.JSONDecodeError:
        return False
    if not isinstance(data, dict) or provider_name not in data:
        return False
    del data[provider_name]
    credentials_path.write_text(json.dumps(data, indent=2))
    return True
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd prototype && python -m pytest tests/test_credentials.py -k clear_api_key -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add prototype/aletheore/credentials.py prototype/tests/test_credentials.py
git commit -m "feat: add clear_api_key for CLI logout support"
```

---

### Task 2: Add `aletheore logout` command

**Files:**
- Modify: `prototype/aletheore/cli.py`
- Test: `prototype/tests/test_cli.py`

**Interfaces:**
- Consumes: `clear_api_key` from Task 1 (`from aletheore.credentials import clear_api_key`), `DEFAULT_CREDENTIALS_PATH` from `aletheore.credentials`.
- Produces: a new `aletheore logout` Typer command.

**Context:** The existing `login` command (search for `def login()` in `cli.py`) saves a token under the provider name `"aletheore-managed-audit"` via `save_api_token`. `logout` must clear that same key. Follow the existing lazy-import convention: import `aletheore.credentials` inside the function body, matching how `login` and `status` already do it — do NOT add this import to the module's top-level imports.

- [ ] **Step 1: Write the failing test**

Add to `prototype/tests/test_cli.py` (check the top of the file for the existing `CliRunner`/`runner` fixture pattern used by other command tests, and match it):

```python
def test_logout_clears_saved_token(tmp_path, monkeypatch):
    import aletheore.credentials as credentials

    creds_path = tmp_path / "credentials.json"
    monkeypatch.setattr(credentials, "DEFAULT_CREDENTIALS_PATH", creds_path)
    credentials.save_api_token("aletheore-managed-audit", "tok-123", creds_path)

    result = runner.invoke(app, ["logout"])

    assert result.exit_code == 0
    assert not credentials.has_api_key(
        "UNUSED_ENV", "aletheore-managed-audit", credentials_path=creds_path
    )


def test_logout_when_not_logged_in_says_so(tmp_path, monkeypatch):
    import aletheore.credentials as credentials

    creds_path = tmp_path / "credentials.json"
    monkeypatch.setattr(credentials, "DEFAULT_CREDENTIALS_PATH", creds_path)

    result = runner.invoke(app, ["logout"])

    assert result.exit_code == 0
    assert "not logged in" in result.stdout.lower()
```

(If `test_cli.py` doesn't already import `app`/`runner`/`monkeypatch`-style fixtures the way shown above, match whatever pattern the existing tests in that file use instead — e.g. some tests in this file use `CliRunner().invoke(...)` inline rather than a shared fixture. Look at `test_index_command_builds_index_from_existing_evidence` or a neighboring test for the exact idiom before writing this.)

- [ ] **Step 2: Run test to verify it fails**

Run: `cd prototype && python -m pytest tests/test_cli.py -k logout -v`
Expected: FAIL (no such command "logout")

- [ ] **Step 3: Write minimal implementation**

Add to `prototype/aletheore/cli.py`, directly after the existing `login` command function (before `status`):

```python
@app.command(help="clear the locally saved managed-audit API token")
def logout() -> None:
    from aletheore.credentials import clear_api_key

    removed = clear_api_key("aletheore-managed-audit")
    if removed:
        console.print("[bold green]Logged out.[/bold green] Saved token removed.")
    else:
        console.print("Not logged in - nothing to clear.")
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd prototype && python -m pytest tests/test_cli.py -k logout -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add prototype/aletheore/cli.py prototype/tests/test_cli.py
git commit -m "feat: add aletheore logout command"
```

---

### Task 3: Add `--version` flag to the root command

**Files:**
- Modify: `prototype/aletheore/cli.py`
- Test: `prototype/tests/test_cli.py`

**Context:** `cli.py` already has a `_main_callback` function decorated with `@app.callback(invoke_without_command=True)` (search for it — it currently just prints the banner panel when no subcommand is given). Typer's standard pattern for a `--version` flag is an eager `Option` callback on this same root callback. The version string must come from `importlib.metadata.version("aletheore")` — this exact call already appears in the `status` command; reuse it, don't hardcode a version string.

- [ ] **Step 1: Write the failing test**

```python
def test_version_flag_prints_version_and_exits(monkeypatch):
    result = runner.invoke(app, ["--version"])

    assert result.exit_code == 0
    import importlib.metadata
    assert importlib.metadata.version("aletheore") in result.stdout
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd prototype && python -m pytest tests/test_cli.py -k version_flag -v`
Expected: FAIL (no such option "--version")

- [ ] **Step 3: Write minimal implementation**

Modify the existing `_main_callback` in `prototype/aletheore/cli.py`:

```python
def _version_callback(value: bool) -> None:
    if value:
        import importlib.metadata

        console.print(f"aletheore {importlib.metadata.version('aletheore')}")
        raise typer.Exit(code=0)


@app.callback(invoke_without_command=True)
def _main_callback(
    ctx: typer.Context,
    version: bool = typer.Option(
        False,
        "--version",
        callback=_version_callback,
        is_eager=True,
        help="show the installed version and exit",
    ),
) -> None:
    if ctx.invoked_subcommand is None:
        console.print(_banner_panel())
        raise typer.Exit(code=0)
```

Note: `is_eager=True` is required so `--version` short-circuits before Typer tries to resolve a subcommand.

- [ ] **Step 4: Run test to verify it passes**

Run: `cd prototype && python -m pytest tests/test_cli.py -k version_flag -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add prototype/aletheore/cli.py prototype/tests/test_cli.py
git commit -m "feat: add --version flag to aletheore CLI"
```

---

### Task 4: Enable shell completion

**Files:**
- Modify: `prototype/aletheore/cli.py`

**Context:** The `Typer(...)` app constructor currently has `add_completion=False` set explicitly (search for it near the top of the `app = typer.Typer(...)` block). This disables Typer's built-in `--install-completion` and `--show-completion` options entirely, for no documented reason. Flipping it to `True` is the entire change — Typer/Click handle the rest (shell detection, completion script generation) automatically, no new code needed.

- [ ] **Step 1: Make the change**

In `prototype/aletheore/cli.py`, change:
```python
app = typer.Typer(
    name="aletheore",
    help="Evidence-grounded repository audit — a deterministic scanner, MCP server, live "
    "dashboard, and a GitHub Action that posts PR diffs.",
    add_completion=False,
    no_args_is_help=False,
)
```
to:
```python
app = typer.Typer(
    name="aletheore",
    help="Evidence-grounded repository audit — a deterministic scanner, MCP server, live "
    "dashboard, and a GitHub Action that posts PR diffs.",
    add_completion=True,
    no_args_is_help=False,
)
```

- [ ] **Step 2: Verify manually**

Run: `cd prototype && aletheore --help` (or `python -m aletheore.cli --help` if not installed as an entry point)
Expected: the help output now lists `--install-completion` and `--show-completion` among the root options (Typer adds these automatically once `add_completion=True`).

There is nothing to unit-test here — this is a single constructor argument change delegated entirely to Typer/Click's own (already-tested) machinery. Do not write a test that shells out to install completion in a CI environment; that's testing Typer's library code, not this project's code.

- [ ] **Step 3: Commit**

```bash
git add prototype/aletheore/cli.py
git commit -m "feat: enable shell completion (aletheore --install-completion)"
```

---

### Task 5: Add `aletheore init` command to scaffold `.aletheore.json`

**Files:**
- Modify: `prototype/aletheore/cli.py`
- Test: `prototype/tests/test_cli.py`

**Interfaces:**
- Produces: a new `aletheore init` Typer command that writes a `.aletheore.json` file with commented-via-adjacent-help placeholder content into the target repo path, without overwriting an existing one.

**Context — the real, current `.aletheore.json` schema** (verified by reading `prototype/aletheore/architecture.py:8-35` and `prototype/aletheore/secrets.py:77-91` — do not invent fields beyond these, they are the only ones any code actually reads):

| Key | Type | Read by | Meaning |
|---|---|---|---|
| `layer_markers` | `dict[str, int]` | `architecture.py` | Maps a folder-name marker to a layer-order integer, for custom layer-violation conventions (e.g. `{"domain": 0, "infrastructure": 2}`). |
| `cluster_resolution` | `float` (default `1.0`) | `architecture.py` | Tunes the greedy-modularity clustering resolution used for architecture cluster detection. |
| `dead_code_entry_points` | `list[str]` | `dead_code.py` | Extra file paths to treat as dead-code entry points (in addition to the built-in detected ones), e.g. a WSGI/ASGI entry script the tool can't infer automatically. |
| `accepted_secrets` | `list[dict]` | `secrets.py` | A baseline of previously-reviewed secret findings to suppress from future diffs (each entry matches the shape of a real finding — do not fabricate the exact sub-schema; leave this as an empty list `[]` in the scaffolded file, since populating it correctly requires copying real finding objects from an actual scan, not hand-authoring). |

JSON has no native comment syntax, so the scaffolded file itself is data-only; explain each field in the command's terminal output instead (printed before/after writing the file), not inside the JSON.

- [ ] **Step 1: Write the failing test**

```python
def test_init_writes_aletheore_json_with_defaults(tmp_path):
    result = runner.invoke(app, ["init", str(tmp_path)])

    assert result.exit_code == 0
    config_path = tmp_path / ".aletheore.json"
    assert config_path.exists()
    import json
    data = json.loads(config_path.read_text())
    assert data == {
        "layer_markers": {},
        "cluster_resolution": 1.0,
        "dead_code_entry_points": [],
        "accepted_secrets": [],
    }


def test_init_refuses_to_overwrite_existing_config(tmp_path):
    config_path = tmp_path / ".aletheore.json"
    config_path.write_text('{"cluster_resolution": 2.0}')

    result = runner.invoke(app, ["init", str(tmp_path)])

    assert result.exit_code == 1
    assert json.loads(config_path.read_text()) == {"cluster_resolution": 2.0}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd prototype && python -m pytest tests/test_cli.py -k "test_init" -v`
Expected: FAIL (no such command "init")

- [ ] **Step 3: Write minimal implementation**

Add to `prototype/aletheore/cli.py`, near the other repo-scoped commands (e.g. right before `scan`):

```python
@app.command(help="scaffold a .aletheore.json config file in a repository")
def init(path: str = typer.Argument(".", help="repository path")) -> None:
    config_path = Path(path) / ".aletheore.json"
    if config_path.exists():
        console.print(f"[bold red]error:[/bold red] {config_path} already exists - not overwriting it.")
        raise typer.Exit(code=1)

    default_config = {
        "layer_markers": {},
        "cluster_resolution": 1.0,
        "dead_code_entry_points": [],
        "accepted_secrets": [],
    }
    config_path.write_text(json.dumps(default_config, indent=2) + "\n")
    console.print(f"[bold green]Wrote {config_path}[/bold green]")
    console.print(
        "  layer_markers: folder-name -> layer-order int, for custom layer-violation "
        "conventions (e.g. {\"domain\": 0, \"infrastructure\": 2})"
    )
    console.print("  cluster_resolution: tunes architecture cluster detection (default 1.0)")
    console.print("  dead_code_entry_points: extra file paths to treat as entry points")
    console.print("  accepted_secrets: baseline of reviewed secret findings to suppress (leave empty for now)")
```

`json` and `Path` are already imported at the top of `cli.py` — no new imports needed for this task.

- [ ] **Step 4: Run test to verify it passes**

Run: `cd prototype && python -m pytest tests/test_cli.py -k "test_init" -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add prototype/aletheore/cli.py prototype/tests/test_cli.py
git commit -m "feat: add aletheore init command to scaffold .aletheore.json"
```

---

### Task 6: Full regression pass

- [ ] **Step 1: Run the complete prototype suite**

Run: `cd prototype && python -m pytest -q`
Expected: all tests pass, including the ones added in Tasks 1-5, with no regressions in the existing 591.

- [ ] **Step 2: Manual smoke check**

Run each of these against this repo itself (or any repo) and confirm sane output:
```bash
aletheore --version
aletheore login   # (skip if no GitHub App to auth against in this environment)
aletheore logout
aletheore init /tmp/some-empty-dir
aletheore --help  # confirm --install-completion/--show-completion now appear
```

- [ ] **Step 3: Final commit if anything was fixed during the regression pass**

Only commit if Step 1 or 2 uncovered something to fix; otherwise this task is just verification, no new commit.
