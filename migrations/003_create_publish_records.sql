CREATE TABLE pin_publications (
    id BIGSERIAL PRIMARY KEY,
    product_id BIGINT NOT NULL REFERENCES products(id) ON DELETE CASCADE,
    content_version_id BIGINT NOT NULL REFERENCES content_versions(id) ON DELETE CASCADE,
    board_id TEXT NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('pending', 'succeeded', 'failed', 'unknown')),
    attempt_count INTEGER NOT NULL DEFAULT 1 CHECK (attempt_count > 0),
    pinterest_pin_id TEXT,
    http_status INTEGER,
    error_code TEXT,
    response_metadata JSONB,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    last_attempt_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (content_version_id, board_id),
    CHECK (
        (status = 'succeeded' AND pinterest_pin_id IS NOT NULL)
        OR status <> 'succeeded'
    )
);
CREATE INDEX pin_publications_product_updated_idx
    ON pin_publications (product_id, updated_at DESC);
