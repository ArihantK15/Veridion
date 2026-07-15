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
