CREATE TABLE IF NOT EXISTS pinterest_board_operations (
    id BIGSERIAL PRIMARY KEY,
    account_id TEXT NOT NULL,
    idempotency_key TEXT NOT NULL,
    request_fingerprint TEXT NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('in_progress', 'succeeded', 'uncertain', 'failed')),
    result JSONB,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (account_id, idempotency_key),
    CHECK ((status = 'succeeded' AND result IS NOT NULL) OR status <> 'succeeded')
);

CREATE INDEX IF NOT EXISTS idx_pinterest_board_operations_updated
    ON pinterest_board_operations (updated_at);
