CREATE TABLE IF NOT EXISTS managed_audit_rate_limits (
    installation_id  BIGINT NOT NULL REFERENCES installations(installation_id) ON DELETE CASCADE,
    repo_full_name   TEXT NOT NULL,
    last_run_at      TIMESTAMPTZ NOT NULL,
    PRIMARY KEY (installation_id, repo_full_name)
);
