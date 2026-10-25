CREATE TABLE IF NOT EXISTS pin_analytics_snapshots (
    id BIGSERIAL PRIMARY KEY,
    publication_id BIGINT NOT NULL REFERENCES pin_publications(id) ON DELETE CASCADE,
    pinterest_pin_id TEXT NOT NULL,
    period_start DATE NOT NULL,
    period_end DATE NOT NULL,
    metrics JSONB NOT NULL,
    fetched_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (pinterest_pin_id, period_start, period_end)
);
CREATE INDEX IF NOT EXISTS pin_analytics_pin_fetched_idx
    ON pin_analytics_snapshots (pinterest_pin_id, fetched_at DESC);
