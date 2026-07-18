ALTER TABLE installations ADD COLUMN IF NOT EXISTS extra_seats INT NOT NULL DEFAULT 0;

CREATE TABLE IF NOT EXISTS llm_spend (
    installation_id  BIGINT NOT NULL REFERENCES installations(installation_id) ON DELETE CASCADE,
    month            DATE NOT NULL,
    total_cost_usd   NUMERIC NOT NULL DEFAULT 0,
    PRIMARY KEY (installation_id, month)
);
