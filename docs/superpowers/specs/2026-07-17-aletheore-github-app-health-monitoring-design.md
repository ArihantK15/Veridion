# Aletheore GitHub App — Endpoint Health Monitoring

**Status:** Draft, pending review
**Date:** 2026-07-17

## Problem

The paid tier's Slack/Teams alerts and Check Runs are entirely event-driven — a GitHub webhook
fires, a job runs. This spec adds the one capability raised during that design session and
deliberately parked as its own future spec: periodically ping a paid installation's mapped API
endpoints and alert if one goes down (or recovers). This is the App's first *time-driven*
capability — nothing today runs on a schedule, everything runs in response to a webhook.

## Goals

- A new scheduler (Ofelia — already proven on the sibling Procta project for exactly this kind
  of periodic job, ~3MB image, reads schedule labels off another container and execs a command
  inside it) triggers a sweep every 3 minutes.
- The sweep enqueues one job onto the existing RQ `scans` queue — the actual ping-and-compare
  work is just another job function in `scan_worker/`, the same shape as every other piece of
  work in this codebase, not a new execution model.
- Reuses `aletheore healthcheck`'s existing deterministic logic (`run_healthcheck(endpoints,
  base_url)`, already shipped, already tested) as the actual ping — no new HTTP-probing code.
- A new `installations.health_check_base_url` column (nullable, same pattern as `webhook_url` —
  unset means monitoring is off), settable from the existing admin page via a new route.
- Alerts fire only on a **reachability flip** — an endpoint that was reachable on the last check
  becomes unreachable, or vice versa (confirming recovery). Fully deterministic: no latency
  threshold, no arbitrary number invented without evidence behind it — the exact discipline this
  project has applied everywhere else (no risk scores, no fuzzy heuristics dressed as facts).

## Non-Goals

- **No latency-threshold alerting.** Explicitly considered and rejected: picking a "too slow"
  number (3000ms? 5000ms?) would be an arbitrary judgment call with no real data behind it,
  inconsistent with this project's standing refusal to invent unfounded thresholds elsewhere.
  Reachability is binary and unambiguous; latency degradation is not, and isn't worth a fuzzy
  heuristic just to seem more thorough.
- **No per-repo base URL for multi-repo installations.** `health_check_base_url` is scoped per
  *installation* (matching `webhook_url`'s existing scope, set from the same admin page), not
  per repo. A single installation's sweep checks every repo it covers against that one shared
  base URL — a coherent real-world shape (one company, one production deployment, multiple
  contributing repos), but a real, deliberate v1 limitation for an installation whose repos
  genuinely deploy to different URLs. Documented here so it isn't mistaken for an oversight.
- **No historical uptime dashboard/percentage in this spec.** The stored `endpoint_health` rows
  are enough to compare consecutive checks and could support a future "99.9% uptime this month"
  view, but building that view is out of scope here — this spec only needs the comparison, not a
  presentation layer for it.

## Architecture

### 1. Scheduler

Add an `ofelia` service to `github-app/docker-compose.yml`, directly mirroring Procta's
proven configuration (`mcuadros/ofelia`, read-only `docker.sock` mount, `job-exec` label on the
target container):

```yaml
  scan-worker:
    # ...existing config...
    labels:
      ofelia.enabled: "true"
      ofelia.job-exec.health-sweep.schedule: "@every 3m"
      ofelia.job-exec.health-sweep.command: >
        python -c "from redis import Redis; from rq import Queue;
        Queue('scans', connection=Redis.from_url('redis://redis:6379/0')).enqueue('scan_worker.jobs.run_health_check_sweep_job')"

  ofelia:
    image: mcuadros/ofelia:latest
    restart: unless-stopped
    depends_on:
      - scan-worker
    command: daemon --docker
    volumes:
      - /var/run/docker.sock:/var/run/docker.sock:ro
```

Ofelia execs a one-liner *inside* the already-running `scan-worker` container every 3 minutes,
which just enqueues a job — the actual work happens on the normal RQ worker loop, not inside
Ofelia's exec call. This means a slow or stuck sweep can never block the next scheduled trigger
(Ofelia's exec returns the instant the job is enqueued), and the sweep job itself is retried and
observed exactly like every other job already running through this queue.

### 2. The sweep job

`run_health_check_sweep_job()` in `scan_worker/jobs.py`:

1. Query all installations where `plan != 'free'` and `health_check_base_url IS NOT NULL`.
2. For each, find every distinct `repo_full_name` that installation has scanned (from
   `repo_history` — reusing existing data, no new endpoint-tracking mechanism).
3. For each repo, fetch its most recent evidence snapshot (`get_recent_history`'s sync
   equivalent, limit 1) and read `repository.api_endpoints.endpoints`.
4. Call `run_healthcheck(endpoints, base_url)` (existing, unchanged) against the
   installation's `health_check_base_url`.
5. For each result, look up the most recent prior `endpoint_health` row for that exact
   `(installation_id, repo_full_name, path, method)`. If `reachable` differs from the prior
   value (or there is no prior value and the new result is `reachable: false` — a first-ever
   check finding something down is still worth surfacing), send a Slack alert.
6. Insert a new `endpoint_health` row for every checked endpoint, then prune to the most recent
   20 per `(installation_id, repo_full_name, path, method)` — same rotation shape
   `repo_history` already uses.

### 3. Storage

```sql
ALTER TABLE installations ADD COLUMN health_check_base_url TEXT;

CREATE TABLE endpoint_health (
    id               BIGSERIAL PRIMARY KEY,
    installation_id  BIGINT NOT NULL REFERENCES installations(installation_id) ON DELETE CASCADE,
    repo_full_name   TEXT NOT NULL,
    endpoint_method  TEXT NOT NULL,
    endpoint_path    TEXT NOT NULL,
    reachable        BOOLEAN NOT NULL,
    status_code      INT,
    latency_ms       NUMERIC,
    checked_at       TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX endpoint_health_lookup
    ON endpoint_health (installation_id, repo_full_name, endpoint_method, endpoint_path, checked_at DESC);
```

### 4. Admin route

`PUT /admin/{org}/{repo}/health-check-url` (body `{"health_check_base_url": str | None}`),
identical shape to the existing `PUT /admin/{org}/{repo}/webhook-url` route — same
`_require_admin_installation` gate (login + administers this installation + paid plan).

### 5. Slack alert format

A new formatter, distinct from the existing new-findings message:

```
*Aletheore*: endpoint down on `octocat/hello-world`
`GET /api/users` is unreachable (was reachable as of the last check)
```

or, on recovery:

```
*Aletheore*: endpoint recovered on `octocat/hello-world`
`GET /api/users` is reachable again
```

Sent via the same `webhook_url`/HTTP-POST mechanism `scan_worker/slack.py` already uses — no new
delivery channel, just a new message body for a different trigger.

## Testing

- **Reachability-flip detection**: reachable→unreachable fires an alert; unreachable→reachable
  fires a (different) alert; reachable→reachable and unreachable→unreachable fire nothing (four
  explicit cases, not one assumed symmetric behavior).
- **First-ever check**: no prior row and the endpoint is unreachable fires an alert; no prior row
  and the endpoint is reachable does not (starting state matters, not just deltas).
- **Multi-repo installation**: a sweep for an installation covering two repos checks both against
  the same shared `health_check_base_url` and stores rows scoped correctly per repo (proving the
  installation-level scoping decision is actually implemented as designed, not accidentally
  per-repo or accidentally global).
- **Installation filtering**: a free-plan installation with `health_check_base_url` set is not
  swept (plan gate wins); a paid installation with `health_check_base_url` unset is not swept
  (unset means off, not "check something").
- **Rotation**: inserting a 21st `endpoint_health` row for the same `(installation, repo, method,
  path)` leaves exactly 20, oldest dropped — same proof style already used for `repo_history`.
- **Scheduler config validation**: `docker compose config --quiet` passes with the new `ofelia`
  service and `scan-worker` labels present (same validation already used for every prior
  Compose change this session).

## Success Criteria

1. A real endpoint deliberately taken down on a real test deployment triggers a real Slack
   message within one sweep cycle (observed live, not just asserted in a unit test).
2. Bringing that same endpoint back up triggers a real recovery message on the next sweep.
3. An installation with no `health_check_base_url` set is never pinged - confirmed by checking
   `docker compose logs scan-worker` shows no outbound requests for it during a live sweep.
4. `docker compose ps` shows the new `ofelia` service running with `RestartCount: 0` after a
   real deploy, matching the same zero-restart bar every other service in this stack has been
   held to all session.
