ALTER TABLE installations ADD COLUMN IF NOT EXISTS health_check_base_url TEXT;
ALTER TABLE installations ADD COLUMN IF NOT EXISTS health_check_latency_threshold_ms INT;

CREATE TABLE IF NOT EXISTS endpoint_health (
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

CREATE INDEX IF NOT EXISTS endpoint_health_lookup
ON endpoint_health (installation_id, repo_full_name, endpoint_method, endpoint_path, checked_at DESC);
