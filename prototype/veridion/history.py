import json
from pathlib import Path


def _history_dir(repo_path: Path) -> Path:
    return repo_path / ".veridion" / "history"


def _rotate(history_dir: Path, keep: int) -> None:
    snapshots = sorted(history_dir.glob("*.json"))
    excess = len(snapshots) - keep
    if excess <= 0:
        return
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
