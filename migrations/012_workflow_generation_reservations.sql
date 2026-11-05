CREATE TABLE IF NOT EXISTS workflow_generation_reservations (
    idempotency_key TEXT PRIMARY KEY CHECK (char_length(idempotency_key) BETWEEN 8 AND 200),
    request_fingerprint TEXT NOT NULL CHECK (char_length(request_fingerprint) = 64),
    status TEXT NOT NULL DEFAULT 'generating'
        CHECK (status IN ('generating', 'retryable', 'persisted')),
    lease_token UUID,
    lease_expires_at TIMESTAMPTZ,
    image_data_url TEXT,
    image_model TEXT,
    generated_content JSONB,
    content_model TEXT,
    product_id BIGINT REFERENCES products(id) ON DELETE SET NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CHECK ((image_data_url IS NULL) = (image_model IS NULL)),
    CHECK ((generated_content IS NULL) = (content_model IS NULL)),
    CHECK (status <> 'generating' OR (lease_token IS NOT NULL AND lease_expires_at IS NOT NULL))
);
CREATE INDEX IF NOT EXISTS workflow_generation_reservations_expiry_idx
    ON workflow_generation_reservations (lease_expires_at)
    WHERE status = 'generating';
