ALTER TABLE products ADD COLUMN IF NOT EXISTS idempotency_key TEXT;
CREATE UNIQUE INDEX IF NOT EXISTS products_idempotency_key_unique
    ON products (idempotency_key)
    WHERE idempotency_key IS NOT NULL;
