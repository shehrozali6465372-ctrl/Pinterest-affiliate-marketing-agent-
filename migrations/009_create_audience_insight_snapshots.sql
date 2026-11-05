CREATE TABLE IF NOT EXISTS pinterest_audience_insight_snapshots (
    id BIGSERIAL PRIMARY KEY,
    account_id TEXT NOT NULL,
    ad_account_id TEXT NOT NULL,
    audience_insight_type TEXT NOT NULL CHECK (
        audience_insight_type IN ('YOUR_TOTAL_AUDIENCE', 'YOUR_ENGAGED_AUDIENCE')
    ),
    period_start DATE NOT NULL,
    period_end DATE NOT NULL,
    data JSONB NOT NULL,
    fetched_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (account_id, ad_account_id, audience_insight_type, period_start, period_end)
);

CREATE INDEX IF NOT EXISTS pinterest_audience_account_fetched_idx
    ON pinterest_audience_insight_snapshots (account_id, fetched_at DESC);
