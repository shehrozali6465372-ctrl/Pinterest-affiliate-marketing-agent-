CREATE TABLE pinterest_credentials (
    id BIGSERIAL PRIMARY KEY,
    account_id TEXT NOT NULL UNIQUE,
    pinterest_user_id TEXT NOT NULL,
    username TEXT NOT NULL DEFAULT '',
    access_token_ciphertext BYTEA NOT NULL,
    refresh_token_ciphertext BYTEA,
    token_type TEXT NOT NULL DEFAULT 'bearer',
    scope TEXT NOT NULL DEFAULT '',
    expires_at TIMESTAMPTZ,
    refresh_token_expires_at TIMESTAMPTZ,
    status TEXT NOT NULL DEFAULT 'connected' CHECK (status IN ('connected', 'revoked')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX pinterest_credentials_user_idx ON pinterest_credentials (pinterest_user_id);
