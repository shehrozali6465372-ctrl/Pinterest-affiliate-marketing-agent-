CREATE TABLE content_versions (
    id BIGSERIAL PRIMARY KEY,
    product_id BIGINT NOT NULL REFERENCES products(id) ON DELETE CASCADE,
    version_number INTEGER NOT NULL CHECK (version_number > 0),
    provider TEXT NOT NULL,
    model_id TEXT NOT NULL,
    prompt_version TEXT NOT NULL,
    pin_idea TEXT NOT NULL,
    title TEXT NOT NULL,
    description TEXT NOT NULL,
    alt_text TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (product_id, version_number)
);
CREATE INDEX content_versions_product_created_idx
    ON content_versions (product_id, created_at DESC);
