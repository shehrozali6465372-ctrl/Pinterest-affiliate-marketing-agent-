CREATE TABLE IF NOT EXISTS pinterest_trend_snapshots (
    id BIGSERIAL PRIMARY KEY,
    account_id TEXT NOT NULL,
    region TEXT NOT NULL CHECK (region IN ('US', 'GB+IE')),
    trend_type TEXT NOT NULL,
    snapshot_date DATE NOT NULL,
    fetched_at TIMESTAMPTZ NOT NULL,
    data JSONB NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (account_id, region, trend_type, snapshot_date)
);
CREATE INDEX IF NOT EXISTS idx_pinterest_trend_snapshots_account_date
    ON pinterest_trend_snapshots (account_id, snapshot_date DESC);
