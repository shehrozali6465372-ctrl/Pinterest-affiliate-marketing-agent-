-- Associate each newly confirmed publication with the Pinterest account that owns it.
-- Legacy rows remain NULL because their original account cannot be safely inferred.
ALTER TABLE pin_publications
    ADD COLUMN account_id TEXT;

CREATE INDEX pin_publications_account_status_idx
    ON pin_publications (account_id, status, updated_at DESC);
