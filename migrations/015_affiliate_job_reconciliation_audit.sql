-- Atomic operator reconciliation for uncertain scheduler jobs.
-- Append-only evidence ledger; no scheduler execution or Pinterest calls.

CREATE TABLE affiliate_job_reconciliation_audit (
    id BIGSERIAL PRIMARY KEY,
    job_id BIGINT NOT NULL REFERENCES affiliate_pin_jobs(id) ON DELETE RESTRICT,
    schedule_id BIGINT NOT NULL REFERENCES affiliate_publishing_schedules(id) ON DELETE RESTRICT,
    account_id TEXT NOT NULL,
    publication_id BIGINT REFERENCES pin_publications(id) ON DELETE RESTRICT,
    outcome TEXT NOT NULL CHECK (outcome IN ('succeeded', 'failed')),
    pinterest_pin_id TEXT,
    operator_evidence TEXT NOT NULL
        CHECK (char_length(btrim(operator_evidence)) BETWEEN 12 AND 2000),
    reconciled_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT affiliate_job_reconciliation_audit_job_unique UNIQUE (job_id),
    CHECK (
        (outcome = 'succeeded' AND pinterest_pin_id IS NOT NULL)
        OR (outcome = 'failed' AND pinterest_pin_id IS NULL)
    )
);

CREATE INDEX affiliate_job_reconciliation_audit_account_idx
    ON affiliate_job_reconciliation_audit (account_id, reconciled_at DESC);

CREATE OR REPLACE FUNCTION affiliate_job_reconciliation_audit_immutable()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    RAISE EXCEPTION 'Scheduler reconciliation audit is append-only';
END;
$$;

CREATE TRIGGER affiliate_job_reconciliation_audit_no_mutation
BEFORE UPDATE OR DELETE ON affiliate_job_reconciliation_audit
FOR EACH ROW EXECUTE FUNCTION affiliate_job_reconciliation_audit_immutable();

-- Prevent accidental bulk truncation through ordinary application SQL access.
CREATE TRIGGER affiliate_job_reconciliation_audit_no_truncate
BEFORE TRUNCATE ON affiliate_job_reconciliation_audit
FOR EACH STATEMENT EXECUTE FUNCTION affiliate_job_reconciliation_audit_immutable();
