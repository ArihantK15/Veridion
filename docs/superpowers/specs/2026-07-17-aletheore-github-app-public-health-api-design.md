# Aletheore GitHub App — Public Health Metrics API

**Status:** Draft, pending review
**Date:** 2026-07-17

## Problem

Corrects an earlier misunderstanding: the goal is not for Aletheore to host a status page. It's a
clean, public API exposing the endpoint-health data the just-shipped health-monitoring feature
already collects, so a customer can build and host their *own* status page on their *own*
website, calling this endpoint directly from client-side JS.

## Goals

- `GET /v1/health/{org}/{repo}` — public, unauthenticated, CORS-open (`Access-Control-Allow-Origin: *`
  — the response contains nothing sensitive, and requiring origin registration would add friction
  for no real security benefit).
- Returns the most recent `endpoint_health` row per `(endpoint_method, endpoint_path)` for that
  repo — the same "latest row per key" shape `get_last_endpoint_health` (health-monitoring's own
  sweep job) already computes, just exposed publicly instead of used internally for flip
  detection.
- 404 when the repo has no `endpoint_health` rows — matches `GET /app/{org}/{repo}`'s existing
  "no data" convention exactly.

## Non-Goals

- **No new storage.** Reads `endpoint_health` as-is; no new table, no new column.
- **No plan check in this endpoint's own code.** `endpoint_health` rows only exist for paid
  installations with monitoring configured (health monitoring's own sweep already filters
  `plan != 'free'`) — the gating is automatic via data existence, not something this endpoint
  needs to enforce separately. Confirmed with the user: health monitoring stays paid-only,
  consistent with the rest of the paid tier's "real ongoing cost" rationale.
- **No historical/uptime-percentage aggregation.** Returns the latest snapshot per endpoint, not
  a rolled-up "99.9% this month" figure — the customer's own status page can compute that from
  repeated calls to this endpoint if they want it; Aletheore doesn't need to pre-aggregate it.

## Architecture

New route in `app_server/dashboard.py` (same file as the existing public
`GET /app/{org}/{repo}`, since both are public read-only JSON endpoints over installation-scoped
data — one file, one responsibility: public data reads):

```python
@dashboard_router.get("/v1/health/{org}/{repo}")
async def get_public_health(org: str, repo: str, request: Request, response: Response):
    response.headers["Access-Control-Allow-Origin"] = "*"
    repo_full_name = f"{org}/{repo}"
    pool = request.app.state.db_pool
    rows = await pool.fetch(
        """
        SELECT DISTINCT ON (endpoint_method, endpoint_path)
            endpoint_method, endpoint_path, reachable, status_code, latency_ms, checked_at
        FROM endpoint_health
        WHERE repo_full_name = $1
        ORDER BY endpoint_method, endpoint_path, checked_at DESC
        """,
        repo_full_name,
    )
    if not rows:
        raise HTTPException(status_code=404, detail="no health data for this repo")
    return {
        "repo_full_name": repo_full_name,
        "endpoints": [
            {
                "method": r["endpoint_method"],
                "path": r["endpoint_path"],
                "reachable": r["reachable"],
                "status_code": r["status_code"],
                "latency_ms": float(r["latency_ms"]) if r["latency_ms"] is not None else None,
                "checked_at": r["checked_at"].isoformat(),
            }
            for r in rows
        ],
    }
```

`DISTINCT ON (endpoint_method, endpoint_path) ... ORDER BY ... checked_at DESC` is Postgres's
native way to get "latest row per key" in one query — no need to fetch all 20 rotated rows per
endpoint and filter in Python.

## Testing

- Real repo with `endpoint_health` rows for two distinct endpoints returns both, each showing
  its own latest values (not accidentally the same row twice, not mixing method/path pairs).
- Repo with no `endpoint_health` rows returns 404.
- Response includes `Access-Control-Allow-Origin: *`.
- An endpoint with a `NULL` `latency_ms` (an unreachable check) serializes as `null` in the JSON
  response, not an error or a dropped field.

## Success Criteria

1. A real browser page on a different origin (e.g. a local `file://` or a throwaway static page,
   not `aletheore.com`) successfully fetches this endpoint via client-side `fetch()` with no CORS
   error in the console — proves the CORS header is real and sufficient, not just present in a
   unit test.
2. The returned data for a real monitored repo matches what the sweep job most recently wrote to
   `endpoint_health`, confirmed by comparing against a direct database read.
