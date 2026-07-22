CREATE TABLE IF NOT EXISTS wiki_overview (
    installation_id  BIGINT NOT NULL REFERENCES installations(installation_id) ON DELETE CASCADE,
    repo_full_name   TEXT NOT NULL,
    description      TEXT NOT NULL,
    diagram_mermaid  TEXT NOT NULL,
    source_commit    TEXT,
    updated_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (installation_id, repo_full_name)
);

CREATE TABLE IF NOT EXISTS wiki_subsystems (
    installation_id  BIGINT NOT NULL REFERENCES installations(installation_id) ON DELETE CASCADE,
    repo_full_name   TEXT NOT NULL,
    subsystem_id     TEXT NOT NULL,
    name             TEXT NOT NULL,
    description      TEXT NOT NULL,
    files            JSONB NOT NULL,
    diagram_mermaid  TEXT NOT NULL,
    source_commit    TEXT,
    updated_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (installation_id, repo_full_name, subsystem_id)
);

CREATE INDEX IF NOT EXISTS wiki_subsystems_lookup
ON wiki_subsystems (installation_id, repo_full_name);
