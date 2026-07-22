from datetime import datetime, timedelta, timezone

import pytest

from app_server.evidence_limits import EvidenceTooLargeError, MAX_EVIDENCE_BYTES
from app_server.db import (
    add_installation_member,
    check_and_reserve_managed_audit,
    count_active_tokens,
    count_installation_members,
    create_api_token,
    create_session,
    delete_installation,
    delete_session,
    get_extra_seats,
    get_installation_by_token_hash,
    get_installation,
    get_llm_spend_this_month,
    get_recent_history,
    get_max_tokens,
    get_session,
    insert_repo_history,
    is_installation_member,
    list_api_tokens,
    list_installation_members,
    remove_installation_member,
    revoke_api_token,
    record_llm_spend,
    set_health_check_config,
    set_installation_plan,
    set_webhook_url,
    touch_api_token,
    upsert_installation,
)


@pytest.mark.asyncio
async def test_upsert_installation_creates_row(pool):
    await upsert_installation(pool, 123, "octocat")
    row = await get_installation(pool, 123)
    assert row["account_login"] == "octocat"
    assert row["plan"] == "free"


@pytest.mark.asyncio
async def test_upsert_installation_is_idempotent(pool):
    await upsert_installation(pool, 123, "octocat")
    await upsert_installation(pool, 123, "octocat")
    row = await get_installation(pool, 123)
    assert row["account_login"] == "octocat"


@pytest.mark.asyncio
async def test_set_installation_plan_updates_plan(pool):
    await upsert_installation(pool, 123, "octocat")
    await set_installation_plan(pool, 123, "pro")
    row = await get_installation(pool, 123)
    assert row["plan"] == "pro"


@pytest.mark.asyncio
async def test_delete_installation_removes_row(pool):
    await upsert_installation(pool, 123, "octocat")
    await delete_installation(pool, 123)
    assert await get_installation(pool, 123) is None


@pytest.mark.asyncio
async def test_delete_installation_cascades_to_history(pool):
    await upsert_installation(pool, 123, "octocat")
    await insert_repo_history(pool, 123, "octocat/repo", datetime.now(timezone.utc), {"x": 1})
    await delete_installation(pool, 123)
    assert await get_recent_history(pool, 123, "octocat/repo") == []


@pytest.mark.asyncio
async def test_insert_repo_history_rejects_oversized_evidence(pool):
    await upsert_installation(pool, 123, "octocat")
    oversized = {"padding": "x" * (MAX_EVIDENCE_BYTES + 1)}
    with pytest.raises(EvidenceTooLargeError):
        await insert_repo_history(pool, 123, "octocat/repo", datetime.now(timezone.utc), oversized)
    assert await get_recent_history(pool, 123, "octocat/repo") == []


@pytest.mark.asyncio
async def test_repo_history_rotation_keeps_only_20(pool):
    await upsert_installation(pool, 123, "octocat")
    start = datetime(2026, 1, 1, tzinfo=timezone.utc)
    for i in range(21):
        await insert_repo_history(pool, 123, "octocat/repo", start + timedelta(minutes=i), {"n": i})

    history = await get_recent_history(pool, 123, "octocat/repo", limit=100)
    assert len(history) == 20
    assert history[0]["evidence"]["n"] == 20
    assert history[-1]["evidence"]["n"] == 1


@pytest.mark.asyncio
async def test_session_lifecycle(pool):
    expires = datetime.now(timezone.utc) + timedelta(hours=1)
    await create_session(pool, "sess-1", 42, "octocat", "encrypted", expires)
    row = await get_session(pool, "sess-1")
    assert row["github_login"] == "octocat"
    await delete_session(pool, "sess-1")
    assert await get_session(pool, "sess-1") is None


@pytest.mark.asyncio
async def test_webhook_url_and_token_lifecycle(pool):
    await upsert_installation(pool, 100, "octocat")
    await set_webhook_url(pool, 100, "https://hooks.slack.com/services/x")
    installation = await get_installation(pool, 100)
    assert installation["webhook_url"] == "https://hooks.slack.com/services/x"
    assert await get_max_tokens(pool, 100) == 3

    await create_api_token(pool, 100, "hash1", "laptop", "octocat")
    assert await count_active_tokens(pool, 100) == 1
    assert (await get_installation_by_token_hash(pool, "hash1"))["installation_id"] == 100
    await touch_api_token(pool, "hash1")
    tokens = await list_api_tokens(pool, 100)
    assert tokens[0]["last_used_at"] is not None
    assert "token_hash" not in tokens[0]
    await revoke_api_token(pool, 100, tokens[0]["id"])
    assert await count_active_tokens(pool, 100) == 0
    assert await get_installation_by_token_hash(pool, "hash1") is None


@pytest.mark.asyncio
async def test_set_health_check_config(pool):
    await upsert_installation(pool, 300, "octocat")
    await set_health_check_config(pool, 300, "https://api.example.com", 3000)
    row = await get_installation(pool, 300)
    assert row["health_check_base_url"] == "https://api.example.com"
    assert row["health_check_latency_threshold_ms"] == 3000


@pytest.mark.asyncio
async def test_set_health_check_config_clears_with_none(pool):
    await upsert_installation(pool, 300, "octocat")
    await set_health_check_config(pool, 300, "https://api.example.com", 3000)
    await set_health_check_config(pool, 300, None, None)
    row = await get_installation(pool, 300)
    assert row["health_check_base_url"] is None
    assert row["health_check_latency_threshold_ms"] is None


@pytest.mark.asyncio
async def test_check_and_reserve_managed_audit_allows_first_run(pool):
    await upsert_installation(pool, 400, "octocat")
    allowed = await check_and_reserve_managed_audit(pool, 400, "octocat/widgets", cooldown_seconds=3600)
    assert allowed is True


@pytest.mark.asyncio
async def test_check_and_reserve_managed_audit_blocks_second_run_within_cooldown(pool):
    await upsert_installation(pool, 400, "octocat")
    assert await check_and_reserve_managed_audit(pool, 400, "octocat/widgets", cooldown_seconds=3600) is True
    assert await check_and_reserve_managed_audit(pool, 400, "octocat/widgets", cooldown_seconds=3600) is False


@pytest.mark.asyncio
async def test_check_and_reserve_managed_audit_allows_after_cooldown_elapses(pool):
    await upsert_installation(pool, 400, "octocat")
    old_run = datetime.now(timezone.utc) - timedelta(hours=2)
    async with pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO managed_audit_rate_limits (installation_id, repo_full_name, last_run_at)
            VALUES ($1, $2, $3)
            """,
            400,
            "octocat/widgets",
            old_run,
        )
    allowed = await check_and_reserve_managed_audit(pool, 400, "octocat/widgets", cooldown_seconds=3600)
    assert allowed is True


@pytest.mark.asyncio
async def test_check_and_reserve_managed_audit_is_independent_per_repo(pool):
    await upsert_installation(pool, 400, "octocat")
    assert await check_and_reserve_managed_audit(pool, 400, "octocat/widgets", cooldown_seconds=3600) is True
    assert await check_and_reserve_managed_audit(pool, 400, "octocat/gizmos", cooldown_seconds=3600) is True


@pytest.mark.asyncio
async def test_get_llm_spend_this_month_returns_zero_when_no_rows(pool):
    await upsert_installation(pool, 500, "octocat")
    assert await get_llm_spend_this_month(pool, 500) == 0.0


@pytest.mark.asyncio
async def test_record_llm_spend_accumulates_within_the_same_month(pool):
    await upsert_installation(pool, 500, "octocat")
    await record_llm_spend(pool, 500, 0.05)
    await record_llm_spend(pool, 500, 0.03)
    assert await get_llm_spend_this_month(pool, 500) == pytest.approx(0.08)


@pytest.mark.asyncio
async def test_record_llm_spend_is_independent_per_installation(pool):
    await upsert_installation(pool, 500, "octocat")
    await upsert_installation(pool, 501, "acme")
    await record_llm_spend(pool, 500, 1.00)
    await record_llm_spend(pool, 501, 2.00)
    assert await get_llm_spend_this_month(pool, 500) == pytest.approx(1.00)
    assert await get_llm_spend_this_month(pool, 501) == pytest.approx(2.00)


@pytest.mark.asyncio
async def test_get_extra_seats_defaults_to_zero(pool):
    await upsert_installation(pool, 500, "octocat")
    assert await get_extra_seats(pool, 500) == 0


@pytest.mark.asyncio
async def test_get_extra_seats_reads_the_real_column(pool):
    await upsert_installation(pool, 500, "octocat")
    async with pool.acquire() as conn:
        await conn.execute("UPDATE installations SET extra_seats = 3 WHERE installation_id = $1", 500)
    assert await get_extra_seats(pool, 500) == 3


@pytest.mark.asyncio
async def test_installation_member_lifecycle(pool):
    await upsert_installation(pool, 600, "octocat")
    assert await is_installation_member(pool, 600, "octocat") is False

    await add_installation_member(pool, 600, "octocat", "octocat")
    assert await is_installation_member(pool, 600, "octocat") is True
    assert await count_installation_members(pool, 600) == 1

    members = await list_installation_members(pool, 600)
    assert members[0]["github_login"] == "octocat"
    assert members[0]["added_by_github_login"] == "octocat"

    await remove_installation_member(pool, 600, "octocat")
    assert await is_installation_member(pool, 600, "octocat") is False
    assert await count_installation_members(pool, 600) == 0


@pytest.mark.asyncio
async def test_add_installation_member_is_idempotent(pool):
    await upsert_installation(pool, 600, "octocat")
    await add_installation_member(pool, 600, "octocat", "octocat")
    await add_installation_member(pool, 600, "octocat", "octocat")
    assert await count_installation_members(pool, 600) == 1


@pytest.mark.asyncio
async def test_installation_members_are_independent_per_installation(pool):
    await upsert_installation(pool, 600, "octocat")
    await upsert_installation(pool, 601, "acme")
    await add_installation_member(pool, 600, "alice", "octocat")
    await add_installation_member(pool, 601, "bob", "acme")
    assert await is_installation_member(pool, 600, "bob") is False
    assert await is_installation_member(pool, 601, "alice") is False


@pytest.mark.asyncio
async def test_removing_installation_cascades_to_members(pool):
    await upsert_installation(pool, 600, "octocat")
    await add_installation_member(pool, 600, "alice", "octocat")
    await delete_installation(pool, 600)
    await upsert_installation(pool, 600, "octocat")
    assert await count_installation_members(pool, 600) == 0
