CREATE TABLE IF NOT EXISTS pinterest_refresh_operations (
    id BIGSERIAL PRIMARY KEY,
    account_id TEXT NOT NULL,
    request_fingerprint TEXT NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('in_progress', 'succeeded', 'uncertain', 'failed')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (account_id, request_fingerprint)
);

CREATE INDEX IF NOT EXISTS idx_pinterest_refresh_operations_updated
    ON pinterest_refresh_operations (updated_at);
