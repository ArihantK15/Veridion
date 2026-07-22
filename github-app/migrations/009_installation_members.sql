CREATE TABLE IF NOT EXISTS installation_members (
    installation_id        BIGINT NOT NULL REFERENCES installations(installation_id) ON DELETE CASCADE,
    github_login           TEXT NOT NULL,
    added_by_github_login  TEXT NOT NULL,
    added_at               TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (installation_id, github_login)
);
