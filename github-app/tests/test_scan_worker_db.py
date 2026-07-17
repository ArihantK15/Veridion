from datetime import datetime, timezone
import os

import pytest

from scan_worker.db import (
    get_last_endpoint_health,
    get_latest_evidence,
    insert_endpoint_health,
    insert_repo_history,
    list_monitored_installations,
    list_repos_for_installation,
)

TEST_DATABASE_URL = os.environ.get(
    "TEST_DATABASE_URL",
    "postgresql://postgres:test@localhost:55433/aletheore_test",
)


async def _insert_installation(pool, installation_id: int, account_login: str, **values) -> None:
    columns = ["installation_id", "account_login", *values.keys()]
    params = [installation_id, account_login, *values.values()]
    placeholders = ", ".join(f"${i}" for i in range(1, len(params) + 1))
    await pool.execute(
        f"INSERT INTO installations ({', '.join(columns)}) VALUES ({placeholders})",
        *params,
    )


@pytest.mark.asyncio
async def test_list_monitored_installations_filters_plan_and_url(pool):
    await _insert_installation(
        pool,
        301,
        "a",
        plan="pro",
        health_check_base_url="https://a.example.com",
    )
    await _insert_installation(
        pool,
        302,
        "b",
        plan="free",
        health_check_base_url="https://b.example.com",
    )
    await _insert_installation(pool, 303, "c", plan="pro")

    ids = {row["installation_id"] for row in list_monitored_installations(TEST_DATABASE_URL)}
    assert ids == {301}


@pytest.mark.asyncio
async def test_list_monitored_installations_includes_webhook_url(pool):
    await _insert_installation(
        pool,
        304,
        "d",
        plan="pro",
        health_check_base_url="https://d.example.com",
        webhook_url="https://hooks.slack.com/d",
    )

    result = list_monitored_installations(TEST_DATABASE_URL)
    row = next(r for r in result if r["installation_id"] == 304)
    assert row["webhook_url"] == "https://hooks.slack.com/d"


@pytest.mark.asyncio
async def test_list_repos_for_installation(pool):
    await _insert_installation(pool, 301, "a")
    insert_repo_history(TEST_DATABASE_URL, 301, "a/repo1", datetime.now(timezone.utc), {"x": 1})
    insert_repo_history(TEST_DATABASE_URL, 301, "a/repo2", datetime.now(timezone.utc), {"x": 1})

    repos = list_repos_for_installation(TEST_DATABASE_URL, 301)
    assert set(repos) == {"a/repo1", "a/repo2"}


@pytest.mark.asyncio
async def test_get_latest_evidence_returns_most_recent(pool):
    await _insert_installation(pool, 301, "a")
    insert_repo_history(TEST_DATABASE_URL, 301, "a/repo1", datetime(2026, 1, 1, tzinfo=timezone.utc), {"v": 1})
    insert_repo_history(TEST_DATABASE_URL, 301, "a/repo1", datetime(2026, 1, 2, tzinfo=timezone.utc), {"v": 2})

    evidence = get_latest_evidence(TEST_DATABASE_URL, 301, "a/repo1")
    assert evidence["v"] == 2


@pytest.mark.asyncio
async def test_insert_and_get_last_endpoint_health(pool):
    await _insert_installation(pool, 301, "a")

    assert get_last_endpoint_health(TEST_DATABASE_URL, 301, "a/repo1", "GET", "/x") is None
    insert_endpoint_health(TEST_DATABASE_URL, 301, "a/repo1", "GET", "/x", True, 200, 120.5)
    last = get_last_endpoint_health(TEST_DATABASE_URL, 301, "a/repo1", "GET", "/x")
    assert last["reachable"] is True
    assert last["latency_ms"] == 120.5


@pytest.mark.asyncio
async def test_endpoint_health_rotation_keeps_20(pool):
    await _insert_installation(pool, 301, "a")
    for _ in range(21):
        insert_endpoint_health(TEST_DATABASE_URL, 301, "a/repo1", "GET", "/x", True, 200, 100.0, keep=20)

    async with pool.acquire() as conn:
        count = await conn.fetchval("SELECT count(*) FROM endpoint_health WHERE installation_id = 301")
    assert count == 20
