# Veridion Continuity/History Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a rolling local history of past scans to Veridion, and a `veridion query changes` command that deterministically reports what changed between the two most recent scans.

**Architecture:** A new `veridion/history.py` module owns two concerns: snapshotting (`save_snapshot`/`list_snapshots`, storing full evidence.json copies under `.veridion/history/`, rotated to the last 20) and diffing (`compute_diff`, a pure function comparing two evidence dicts — curated by default, raw `--full` on request). `cli.py` wires `save_snapshot` into the existing `_scan()` path (used by both `scan` and `audit`) and adds a `changes` kind to the `query` subcommand.

**Tech Stack:** Python 3.12 stdlib only (`json`, `pathlib`, `datetime`) — no new dependencies, matching the project's existing no-new-dependency discipline.

## Global Constraints

- Snapshot retention is hardcoded at 20 (FIFO) — no config flag in this increment.
- `.veridion/history/` is gitignored/local-only — same as `.veridion/` today. No change to `.gitignore` is needed (the existing `.veridion/` entry already covers it).
- `compute_diff` must be a pure function: no file I/O, no network calls, same two dict inputs always produce byte-identical output.
- No wiring into the reasoning-phase audit report or manual/ directory in this increment — CLI/query-layer only.
- Identity keys for curated diffing (fixed, not guessed — confirmed against the current schema):
  - Secrets (working-tree): `(path, pattern, match_preview)` from `security.secrets.findings`
  - Secrets (git history): `(commit, path, pattern)` from `security.secrets.history_findings`
  - Dependency vulnerabilities: `(ecosystem, package, advisory_id)` from `security.dependency_vulnerabilities.findings`
  - Layer violations: `(from, to)` from `architecture.layer_violations.violations`

---

### Task 1: Snapshot storage — `save_snapshot` / `list_snapshots`

**Files:**
- Create: `prototype/veridion/history.py`
- Test: `prototype/tests/test_history.py`

**Interfaces:**
- Produces: `save_snapshot(evidence: dict, repo_path: Path, keep: int = 20) -> Path` — writes a snapshot, rotates old ones, returns the path written.
- Produces: `list_snapshots(repo_path: Path) -> list[Path]` — chronological (oldest first), `[]` if no history dir exists.

- [ ] **Step 1: Write the failing tests**

```python
# prototype/tests/test_history.py
import json
from pathlib import Path

from veridion.history import list_snapshots, save_snapshot


def make_evidence(scanned_at: str) -> dict:
    return {"veridion_version": "0.1.0", "scanned_at": scanned_at, "repo_path": "/tmp/repo"}


def test_save_snapshot_creates_history_dir_if_absent(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()

    save_snapshot(make_evidence("2026-07-15T10:00:00.000000+00:00"), repo)

    assert (repo / ".veridion" / "history").is_dir()


def test_save_snapshot_writes_readable_json(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()

    path = save_snapshot(make_evidence("2026-07-15T10:00:00.000000+00:00"), repo)

    assert json.loads(path.read_text())["scanned_at"] == "2026-07-15T10:00:00.000000+00:00"


def test_list_snapshots_returns_empty_list_when_no_history_dir(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()

    assert list_snapshots(repo) == []


def test_list_snapshots_returns_chronological_order(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()

    save_snapshot(make_evidence("2026-07-15T10:00:00.000000+00:00"), repo)
    save_snapshot(make_evidence("2026-07-15T09:00:00.000000+00:00"), repo)
    save_snapshot(make_evidence("2026-07-15T11:00:00.000000+00:00"), repo)

    snapshots = list_snapshots(repo)
    scanned_ats = [json.loads(p.read_text())["scanned_at"] for p in snapshots]
    assert scanned_ats == [
        "2026-07-15T09:00:00.000000+00:00",
        "2026-07-15T10:00:00.000000+00:00",
        "2026-07-15T11:00:00.000000+00:00",
    ]


def test_save_snapshot_rotates_at_21st_save_keeping_the_20_newest(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()

    for hour in range(21):
        save_snapshot(make_evidence(f"2026-07-15T{hour:02d}:00:00.000000+00:00"), repo)

    snapshots = list_snapshots(repo)
    assert len(snapshots) == 20
    scanned_ats = [json.loads(p.read_text())["scanned_at"] for p in snapshots]
    assert scanned_ats[0] == "2026-07-15T01:00:00.000000+00:00"
    assert scanned_ats[-1] == "2026-07-15T20:00:00.000000+00:00"


def test_save_snapshot_handles_same_timestamp_collision_without_losing_data(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()

    save_snapshot(make_evidence("2026-07-15T10:00:00.000000+00:00"), repo)
    save_snapshot(make_evidence("2026-07-15T10:00:00.000000+00:00"), repo)

    snapshots = list_snapshots(repo)
    assert len(snapshots) == 2
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd prototype && python3 -m pytest tests/test_history.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'veridion.history'`

- [ ] **Step 3: Write the implementation**

```python
# prototype/veridion/history.py
import json
from pathlib import Path


def _history_dir(repo_path: Path) -> Path:
    return repo_path / ".veridion" / "history"


def _rotate(history_dir: Path, keep: int) -> None:
    snapshots = sorted(history_dir.glob("*.json"))
    excess = len(snapshots) - keep
    for path in snapshots[:excess]:
        path.unlink()


def save_snapshot(evidence: dict, repo_path: Path, keep: int = 20) -> Path:
    history_dir = _history_dir(repo_path)
    history_dir.mkdir(parents=True, exist_ok=True)

    safe_name = evidence["scanned_at"].replace(":", "-")
    snapshot_path = history_dir / f"{safe_name}.json"
    suffix = 1
    while snapshot_path.exists():
        snapshot_path = history_dir / f"{safe_name}-{suffix}.json"
        suffix += 1

    snapshot_path.write_text(json.dumps(evidence, indent=2))
    _rotate(history_dir, keep)
    return snapshot_path


def list_snapshots(repo_path: Path) -> list[Path]:
    history_dir = _history_dir(repo_path)
    if not history_dir.exists():
        return []
    return sorted(history_dir.glob("*.json"))
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd prototype && python3 -m pytest tests/test_history.py -v`
Expected: 6 passed

- [ ] **Step 5: Commit**

```bash
cd prototype && git add veridion/history.py tests/test_history.py
git commit -m "feat: add snapshot storage for scan history"
```

---

### Task 2: Diff computation — `compute_diff`

**Files:**
- Modify: `prototype/veridion/history.py`
- Modify: `prototype/tests/test_history.py`

**Interfaces:**
- Consumes: nothing from Task 1 directly (pure function, but lives in the same module).
- Produces: `compute_diff(old: dict, new: dict, full: bool = False) -> dict`. Curated shape:
  `{"caveats": [str, ...]}` (key only present if non-empty) plus `"secrets"`, `"history_secrets"`,
  `"vulnerabilities"`, `"layer_violations"` (each `{"new": [...], "resolved": [...]}`), plus
  `"aggregate_deltas"` (`{"module_count": int, "dependency_graph_edge_count": int, "total_commits": int}`).
  Full shape: `{"added": [...], "removed": [...], "changed": [...]}`.

**Important note on the scan-configuration-changed caveat:** the design spec's stated proxy for
"was git-history secret scanning enabled" is "whether `history_findings` was populated" — but
this is ambiguous, since a repo scanned *with* history scanning enabled can legitimately have
zero history findings (e.g. Procta's own history scan found only 3 findings across 1,703
commits — most scans of most repos will have zero). The correct, unambiguous proxy is
`security.secrets.history_scanned_commits`, which is exactly `0` when `--no-scan-git-history`
was used (per `evidence.py`'s `else: history_data = {"history_scanned_commits": 0,
"history_findings": []}` branch) and otherwise reflects the real commit count. This plan uses
`history_scanned_commits` rather than the spec's literal wording — the underlying design intent
(don't misattribute a checking-state change as new findings) is unchanged. One residual edge
case, worth a code comment but not further engineering: a genuinely empty/non-git repo also
produces `history_scanned_commits == 0` even with scanning enabled, which is indistinguishable
from "scanning was disabled" using this proxy alone. This is a known, minor limitation, not a
bug to fix here.

- [ ] **Step 1: Write the failing tests**

Append to `prototype/tests/test_history.py`:

```python
from veridion.history import compute_diff


def base_evidence() -> dict:
    return {
        "repository": {
            "modules": [{"path": "a.py"}, {"path": "b.py"}],
            "dependency_graph": {"nodes": ["a.py", "b.py"], "edges": [["a.py", "b.py"]]},
        },
        "git": {"total_commits": 10},
        "security": {
            "secrets": {
                "findings": [
                    {"path": "a.py", "pattern": "aws_access_key_id", "match_preview": "AKIA...MNOP", "likely_placeholder": False}
                ],
                "history_scanned_commits": 5,
                "history_findings": [],
            },
            "dependency_vulnerabilities": {
                "checked": True,
                "reason": None,
                "findings": [
                    {"ecosystem": "PyPI", "package": "requests", "installed_version": "2.0.0", "advisory_id": "GHSA-1", "summary": "x", "severity": []}
                ],
            },
        },
        "architecture": {
            "layer_violations": {
                "violations": [{"from": "app/routers/a.py", "to": "app/domain/b.py", "reason": "x"}]
            }
        },
    }


def test_compute_diff_reports_no_new_or_resolved_when_identical():
    evidence = base_evidence()
    diff = compute_diff(evidence, evidence)

    assert diff["secrets"] == {"new": [], "resolved": []}
    assert diff["vulnerabilities"] == {"new": [], "resolved": []}
    assert diff["layer_violations"] == {"new": [], "resolved": []}
    assert diff["aggregate_deltas"] == {
        "module_count": 0,
        "dependency_graph_edge_count": 0,
        "total_commits": 0,
    }
    assert "caveats" not in diff


def test_compute_diff_detects_a_new_secret_finding():
    old = base_evidence()
    new = base_evidence()
    new["security"]["secrets"]["findings"].append(
        {"path": "c.py", "pattern": "generic_credential_assignment", "match_preview": "test****...cret", "likely_placeholder": True}
    )

    diff = compute_diff(old, new)

    assert len(diff["secrets"]["new"]) == 1
    assert diff["secrets"]["new"][0]["path"] == "c.py"
    assert diff["secrets"]["resolved"] == []


def test_compute_diff_detects_a_resolved_vulnerability():
    old = base_evidence()
    new = base_evidence()
    new["security"]["dependency_vulnerabilities"]["findings"] = []

    diff = compute_diff(old, new)

    assert diff["vulnerabilities"]["new"] == []
    assert len(diff["vulnerabilities"]["resolved"]) == 1
    assert diff["vulnerabilities"]["resolved"][0]["advisory_id"] == "GHSA-1"


def test_compute_diff_detects_a_new_layer_violation():
    old = base_evidence()
    new = base_evidence()
    new["architecture"]["layer_violations"]["violations"].append(
        {"from": "app/routers/x.py", "to": "app/domain/y.py", "reason": "y"}
    )

    diff = compute_diff(old, new)

    assert len(diff["layer_violations"]["new"]) == 1


def test_compute_diff_aggregate_deltas_reflect_real_changes():
    old = base_evidence()
    new = base_evidence()
    new["repository"]["modules"].append({"path": "c.py"})
    new["git"]["total_commits"] = 13

    diff = compute_diff(old, new)

    assert diff["aggregate_deltas"]["module_count"] == 1
    assert diff["aggregate_deltas"]["total_commits"] == 3


def test_compute_diff_caveat_fires_when_vulnerability_checking_toggled():
    old = base_evidence()
    old["security"]["dependency_vulnerabilities"]["checked"] = False
    old["security"]["dependency_vulnerabilities"]["findings"] = []
    new = base_evidence()

    diff = compute_diff(old, new)

    assert "caveats" in diff
    assert any("vulnerability" in c for c in diff["caveats"])


def test_compute_diff_caveat_fires_when_history_scanning_toggled():
    old = base_evidence()
    old["security"]["secrets"]["history_scanned_commits"] = 0
    new = base_evidence()

    diff = compute_diff(old, new)

    assert "caveats" in diff
    assert any("history" in c for c in diff["caveats"])


def test_compute_diff_no_caveat_when_configuration_unchanged():
    evidence = base_evidence()

    diff = compute_diff(evidence, evidence)

    assert "caveats" not in diff


def test_compute_diff_full_mode_shows_added_removed_changed():
    old = {"a": 1, "b": {"c": 2}, "d": [1, 2]}
    new = {"a": 1, "b": {"c": 3}, "e": "new"}

    diff = compute_diff(old, new, full=True)

    assert {"path": "e", "value": "new"} in diff["added"]
    assert {"path": "d[0]", "value": 1} in diff["removed"]
    assert {"path": "d[1]", "value": 2} in diff["removed"]
    assert {"path": "b.c", "old_value": 2, "new_value": 3} in diff["changed"]


def test_compute_diff_is_deterministic():
    old = base_evidence()
    new = base_evidence()
    new["security"]["secrets"]["findings"].append(
        {"path": "c.py", "pattern": "generic_credential_assignment", "match_preview": "test****...cret", "likely_placeholder": True}
    )

    first = compute_diff(old, new)
    second = compute_diff(old, new)

    assert first == second
    assert json.dumps(first, sort_keys=True) == json.dumps(second, sort_keys=True)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd prototype && python3 -m pytest tests/test_history.py -v -k compute_diff`
Expected: FAIL with `ImportError: cannot import name 'compute_diff'`

- [ ] **Step 3: Write the implementation**

Append to `prototype/veridion/history.py`:

```python
def _identity_key(finding: dict, fields: tuple[str, ...]) -> tuple:
    return tuple(finding.get(field) for field in fields)


def _new_and_resolved(
    old_findings: list[dict], new_findings: list[dict], fields: tuple[str, ...]
) -> tuple[list[dict], list[dict]]:
    old_keys = {_identity_key(f, fields) for f in old_findings}
    new_keys = {_identity_key(f, fields) for f in new_findings}
    new_only = [f for f in new_findings if _identity_key(f, fields) not in old_keys]
    resolved = [f for f in old_findings if _identity_key(f, fields) not in new_keys]
    return new_only, resolved


def _compute_curated_diff(old: dict, new: dict) -> dict:
    result: dict = {}
    caveats = []

    old_vuln_checked = old["security"]["dependency_vulnerabilities"]["checked"]
    new_vuln_checked = new["security"]["dependency_vulnerabilities"]["checked"]
    if old_vuln_checked != new_vuln_checked:
        caveats.append(
            "dependency-vulnerability checking state changed between scans "
            f"(was checked={old_vuln_checked}, now checked={new_vuln_checked}) - "
            "new/resolved vulnerability findings below may reflect checking being "
            "toggled on/off, not necessarily real changes"
        )

    old_history_scanned = old["security"]["secrets"]["history_scanned_commits"] > 0
    new_history_scanned = new["security"]["secrets"]["history_scanned_commits"] > 0
    if old_history_scanned != new_history_scanned:
        caveats.append(
            "git-history secret scanning state changed between scans "
            f"(was scanned={old_history_scanned}, now scanned={new_history_scanned}) - "
            "new/resolved history secret findings below may reflect scanning being "
            "toggled on/off, not necessarily real changes"
        )

    if caveats:
        result["caveats"] = caveats

    new_secrets, resolved_secrets = _new_and_resolved(
        old["security"]["secrets"]["findings"],
        new["security"]["secrets"]["findings"],
        ("path", "pattern", "match_preview"),
    )
    result["secrets"] = {"new": new_secrets, "resolved": resolved_secrets}

    new_history_secrets, resolved_history_secrets = _new_and_resolved(
        old["security"]["secrets"]["history_findings"],
        new["security"]["secrets"]["history_findings"],
        ("commit", "path", "pattern"),
    )
    result["history_secrets"] = {"new": new_history_secrets, "resolved": resolved_history_secrets}

    new_vulns, resolved_vulns = _new_and_resolved(
        old["security"]["dependency_vulnerabilities"]["findings"],
        new["security"]["dependency_vulnerabilities"]["findings"],
        ("ecosystem", "package", "advisory_id"),
    )
    result["vulnerabilities"] = {"new": new_vulns, "resolved": resolved_vulns}

    new_violations, resolved_violations = _new_and_resolved(
        old["architecture"]["layer_violations"]["violations"],
        new["architecture"]["layer_violations"]["violations"],
        ("from", "to"),
    )
    result["layer_violations"] = {"new": new_violations, "resolved": resolved_violations}

    result["aggregate_deltas"] = {
        "module_count": len(new["repository"]["modules"]) - len(old["repository"]["modules"]),
        "dependency_graph_edge_count": (
            len(new["repository"]["dependency_graph"]["edges"])
            - len(old["repository"]["dependency_graph"]["edges"])
        ),
        "total_commits": new["git"]["total_commits"] - old["git"]["total_commits"],
    }

    return result


def _flatten(obj, prefix: str = "") -> dict:
    flat: dict = {}
    if isinstance(obj, dict):
        for key, val in obj.items():
            new_prefix = f"{prefix}.{key}" if prefix else key
            flat.update(_flatten(val, new_prefix))
    elif isinstance(obj, list):
        for idx, val in enumerate(obj):
            flat.update(_flatten(val, f"{prefix}[{idx}]"))
    else:
        flat[prefix] = obj
    return flat


def _compute_full_diff(old: dict, new: dict) -> dict:
    old_flat = _flatten(old)
    new_flat = _flatten(new)

    added = [
        {"path": path, "value": value}
        for path, value in sorted(new_flat.items())
        if path not in old_flat
    ]
    removed = [
        {"path": path, "value": value}
        for path, value in sorted(old_flat.items())
        if path not in new_flat
    ]
    changed = [
        {"path": path, "old_value": old_flat[path], "new_value": new_flat[path]}
        for path in sorted(old_flat.keys() & new_flat.keys())
        if old_flat[path] != new_flat[path]
    ]

    return {"added": added, "removed": removed, "changed": changed}


def compute_diff(old: dict, new: dict, full: bool = False) -> dict:
    if full:
        return _compute_full_diff(old, new)
    return _compute_curated_diff(old, new)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd prototype && python3 -m pytest tests/test_history.py -v`
Expected: 15 passed

- [ ] **Step 5: Commit**

```bash
cd prototype && git add veridion/history.py tests/test_history.py
git commit -m "feat: add curated and full evidence diffing"
```

---

### Task 3: CLI wiring — snapshot-on-scan and `query changes`

**Files:**
- Modify: `prototype/veridion/cli.py`
- Modify: `prototype/tests/test_cli.py`

**Interfaces:**
- Consumes: `save_snapshot(evidence, repo_path)` and `list_snapshots(repo_path)` and
  `compute_diff(old, new, full)` from Task 1/2.
- Produces: `_query_changes(repo_path: str, full: bool) -> int` (new), and `_query`'s signature
  changes to `_query(kind, target, repo_path, full=False)`.

- [ ] **Step 1: Write the failing tests**

Append to `prototype/tests/test_cli.py`:

```python
def test_main_scan_saves_a_history_snapshot(tmp_path, monkeypatch):
    repo = tmp_path
    (repo / "main.py").write_text("x = 1\n")
    monkeypatch.setattr(
        sys, "argv", ["veridion", "scan", str(repo), "--no-check-vulnerabilities"]
    )

    main()

    history_files = list((repo / ".veridion" / "history").glob("*.json"))
    assert len(history_files) == 1


def test_main_query_changes_reports_no_prior_snapshot_on_first_scan(tmp_path, monkeypatch, capsys):
    repo = tmp_path
    (repo / "main.py").write_text("x = 1\n")
    monkeypatch.setattr(
        sys, "argv", ["veridion", "scan", str(repo), "--no-check-vulnerabilities"]
    )
    main()

    monkeypatch.setattr(sys, "argv", ["veridion", "query", "changes", "--path", str(repo)])
    exit_code = main()

    assert exit_code == 0
    captured = capsys.readouterr()
    assert "no prior snapshot" in captured.out


def test_main_query_changes_reports_corrupt_snapshot(tmp_path, monkeypatch, capsys):
    repo = tmp_path
    (repo / "main.py").write_text("x = 1\n")
    monkeypatch.setattr(
        sys, "argv", ["veridion", "scan", str(repo), "--no-check-vulnerabilities"]
    )
    main()
    main()

    history_dir = repo / ".veridion" / "history"
    oldest = sorted(history_dir.glob("*.json"))[0]
    oldest.write_text("{not valid json")

    monkeypatch.setattr(sys, "argv", ["veridion", "query", "changes", "--path", str(repo)])
    exit_code = main()

    assert exit_code == 1
    captured = capsys.readouterr()
    assert "unreadable" in captured.out


def test_main_query_changes_shows_a_real_diff_between_two_scans(tmp_path, monkeypatch, capsys):
    repo = tmp_path
    (repo / "main.py").write_text("x = 1\n")
    monkeypatch.setattr(
        sys, "argv", ["veridion", "scan", str(repo), "--no-check-vulnerabilities"]
    )
    main()

    (repo / "second.py").write_text("y = 2\n")
    main()

    monkeypatch.setattr(sys, "argv", ["veridion", "query", "changes", "--path", str(repo)])
    exit_code = main()

    assert exit_code == 0
    captured = capsys.readouterr()
    result = json.loads(captured.out)
    assert result["aggregate_deltas"]["module_count"] == 1


def test_main_query_changes_full_flag_returns_raw_diff(tmp_path, monkeypatch, capsys):
    repo = tmp_path
    (repo / "main.py").write_text("x = 1\n")
    monkeypatch.setattr(
        sys, "argv", ["veridion", "scan", str(repo), "--no-check-vulnerabilities"]
    )
    main()
    main()

    monkeypatch.setattr(
        sys, "argv", ["veridion", "query", "changes", "--path", str(repo), "--full"]
    )
    exit_code = main()

    assert exit_code == 0
    captured = capsys.readouterr()
    result = json.loads(captured.out)
    assert set(result.keys()) == {"added", "removed", "changed"}
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd prototype && python3 -m pytest tests/test_cli.py -v -k changes`
Expected: FAIL — `test_main_scan_saves_a_history_snapshot` fails (no history dir created), the
`query changes` tests fail with an argparse error (`invalid choice: 'changes'`).

- [ ] **Step 3: Write the implementation**

In `prototype/veridion/cli.py`, add the import:

```python
from veridion.history import compute_diff, list_snapshots, save_snapshot
```

Modify `_scan` to save a snapshot right after writing evidence:

```python
def _scan(repo_path: str, check_vulnerabilities: bool, scan_git_history: bool) -> tuple[int, dict, Path]:
    repo = Path(repo_path).resolve()
    print(f"Scanning {repo}...")
    evidence = scan_repository(
        repo, check_vulnerabilities=check_vulnerabilities, scan_git_history=scan_git_history
    )
    evidence_path = write_evidence(evidence, repo)
    print(f"Evidence written to {evidence_path}")
    snapshot_path = save_snapshot(evidence, repo)
    print(f"Snapshot saved to {snapshot_path}")
    return 0, evidence, evidence_path
```

Add `_query_changes` and modify `_query`'s signature to accept `full`:

```python
def _query_changes(repo_path: str, full: bool) -> int:
    repo = Path(repo_path).resolve()
    snapshots = list_snapshots(repo)

    if len(snapshots) < 2:
        print("no prior snapshot to compare against - run 'veridion scan' again later to compare")
        return 0

    try:
        old = json.loads(snapshots[-2].read_text())
    except json.JSONDecodeError:
        print(f"error: most recent snapshot is unreadable ({snapshots[-2]})")
        return 1

    new = json.loads(snapshots[-1].read_text())
    diff = compute_diff(old, new, full=full)
    print(json.dumps(diff, indent=2))
    return 0


def _query(kind: str, target: str | None, repo_path: str, full: bool = False) -> int:
    if kind == "changes":
        return _query_changes(repo_path, full)

    repo = Path(repo_path).resolve()
    evidence_path = repo / ".veridion" / "evidence.json"
    if not evidence_path.exists():
        print(f"error: no evidence found at {evidence_path}")
        print(f"Run 'veridion scan {repo}' first.")
        return 1

    func, requires_target = QUERY_FUNCTIONS[kind]
    if requires_target and target is None:
        print(f"error: query type '{kind}' requires a target argument")
        return 1

    evidence = json.loads(evidence_path.read_text())
    try:
        result = func(evidence, target)
    except (ModuleNotFoundInEvidenceError, BranchNotFoundInEvidenceError) as exc:
        print(f"error: {exc}")
        return 1

    print(json.dumps(result, indent=2))
    return 0
```

In `main()`, update the query subparser and dispatch call:

```python
    query_parser = subparsers.add_parser("query", help="query an existing evidence.json")
    query_parser.add_argument("kind", choices=list(QUERY_FUNCTIONS.keys()) + ["changes"])
    query_parser.add_argument("target", nargs="?", default=None)
    query_parser.add_argument("--path", dest="repo_path", default=".")
    query_parser.add_argument(
        "--full",
        action="store_true",
        default=False,
        help="show the full raw diff instead of the curated summary (only applies to 'changes')",
    )
```

```python
    if args.command == "query":
        return _query(args.kind, args.target, args.repo_path, args.full)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd prototype && python3 -m pytest tests/test_cli.py -v`
Expected: all pass (existing tests + 5 new)

Run: `cd prototype && python3 -m pytest -v`
Expected: all pass, no regressions

- [ ] **Step 5: Commit**

```bash
cd prototype && git add veridion/cli.py tests/test_cli.py
git commit -m "feat: snapshot on scan and add veridion query changes"
```

---

### Task 4: Live verification

Not automated — no live agent call needed, matches the pattern used for prior increments'
Task 4s this session. Run each check against a real repo and record the actual output.

- [ ] **Step 1: No-op double-scan against Procta shows zero diff**

```bash
cd prototype
python3 -m veridion.cli scan /Users/arihantkaul/proctored-browser --no-check-vulnerabilities
python3 -m veridion.cli scan /Users/arihantkaul/proctored-browser --no-check-vulnerabilities
python3 -m veridion.cli query changes --path /Users/arihantkaul/proctored-browser
```

Expected: `secrets`, `history_secrets`, `vulnerabilities`, `layer_violations` all show
`{"new": [], "resolved": []}`, `aggregate_deltas` for `module_count` and
`dependency_graph_edge_count` are `0` (`total_commits` may be non-zero only if a real commit
happened on Procta between the two scans — note this rather than treating it as a failure).

- [ ] **Step 2: A real added-secret scratch-repo scan shows up as a new finding**

```bash
SCRATCH=/private/tmp/claude-501/-Users-arihantkaul-Desktop-AI-Face-Detect-Base-Code/1788d1c3-3517-4ca5-a065-d785dce2edbc/scratchpad/history-check
rm -rf "$SCRATCH" && mkdir -p "$SCRATCH"
echo "x = 1" > "$SCRATCH/main.py"
cd prototype
python3 -m veridion.cli scan "$SCRATCH" --no-check-vulnerabilities --no-scan-git-history
echo 'AWS_KEY = "AKIAABCDEFGHIJKLMNOP"' >> "$SCRATCH/main.py"
python3 -m veridion.cli scan "$SCRATCH" --no-check-vulnerabilities --no-scan-git-history
python3 -m veridion.cli query changes --path "$SCRATCH"
```

Expected: `secrets.new` contains exactly one finding with `path: "main.py"`,
`pattern: "aws_access_key_id"`.

- [ ] **Step 3: Toggling `--no-check-vulnerabilities` triggers the caveat, not a misleading list**

```bash
SCRATCH2=/private/tmp/claude-501/-Users-arihantkaul-Desktop-AI-Face-Detect-Base-Code/1788d1c3-3517-4ca5-a065-d785dce2edbc/scratchpad/history-check-2
rm -rf "$SCRATCH2" && mkdir -p "$SCRATCH2"
echo "x = 1" > "$SCRATCH2/main.py"
cd prototype
python3 -m veridion.cli scan "$SCRATCH2" --no-check-vulnerabilities --no-scan-git-history
python3 -m veridion.cli scan "$SCRATCH2" --no-scan-git-history
python3 -m veridion.cli query changes --path "$SCRATCH2"
```

Expected: `caveats` key present with a message mentioning "vulnerability checking state changed".

- [ ] **Step 4: The 21st scan against the same repo leaves exactly 20 snapshots**

```bash
SCRATCH3=/private/tmp/claude-501/-Users-arihantkaul-Desktop-AI-Face-Detect-Base-Code/1788d1c3-3517-4ca5-a065-d785dce2edbc/scratchpad/history-check-3
rm -rf "$SCRATCH3" && mkdir -p "$SCRATCH3"
echo "x = 1" > "$SCRATCH3/main.py"
cd prototype
for i in $(seq 1 21); do
  python3 -m veridion.cli scan "$SCRATCH3" --no-check-vulnerabilities --no-scan-git-history
done
ls "$SCRATCH3/.veridion/history" | wc -l
```

Expected: `20`.

- [ ] **Step 5: `compute_diff` is deterministic on real data**

```bash
cd prototype
python3 -c "
import json
from pathlib import Path
from veridion.history import compute_diff, list_snapshots

snapshots = list_snapshots(Path('/Users/arihantkaul/proctored-browser'))
old = json.loads(snapshots[-2].read_text())
new = json.loads(snapshots[-1].read_text())

first = json.dumps(compute_diff(old, new), sort_keys=True)
second = json.dumps(compute_diff(old, new), sort_keys=True)
assert first == second
print('deterministic: OK')
"
```

Expected: `deterministic: OK`.
