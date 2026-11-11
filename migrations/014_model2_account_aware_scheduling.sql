-- Model 2 scheduling extension. Legacy Model 1 schedules remain niche_id NULL.
-- Additive only; no existing schedule/job data is backfilled or rewritten.

ALTER TABLE affiliate_publishing_schedules
    ADD COLUMN niche_id BIGINT;

ALTER TABLE affiliate_publishing_schedules
    ADD CONSTRAINT affiliate_schedule_account_niche_fk
    FOREIGN KEY (account_id, niche_id)
    REFERENCES model2_account_niches (account_id, niche_id)
    ON DELETE RESTRICT;

ALTER TABLE affiliate_publishing_schedules
    ADD CONSTRAINT affiliate_schedule_model2_account_id_check
    CHECK (
        niche_id IS NULL
        OR account_id ~ '^pinterest:[^:[:space:]]+$'
    );

CREATE INDEX affiliate_schedules_account_niche_idx
    ON affiliate_publishing_schedules (account_id, niche_id, status);

CREATE INDEX affiliate_pin_jobs_account_quota_idx
    ON affiliate_pin_jobs (schedule_id, status, locked_at, finished_at)
    WHERE status IN ('processing', 'succeeded', 'uncertain');

CREATE OR REPLACE FUNCTION model2_guard_activated_schedule_immutability()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    -- Preserve all legacy Model 1 schedule update semantics. These state and
    -- immutability rules apply only when a schedule has Model 2 niche context.
    IF OLD.niche_id IS NOT NULL OR NEW.niche_id IS NOT NULL THEN
        IF NEW.status IS DISTINCT FROM OLD.status
           AND NOT (
               (OLD.status = 'draft' AND NEW.status = 'active')
               OR (OLD.status = 'active' AND NEW.status IN ('paused', 'completed', 'cancelled'))
           ) THEN
            RAISE EXCEPTION 'Invalid Model 2 schedule state transition'
                USING ERRCODE = 'check_violation';
        END IF;

        IF OLD.status <> 'draft' OR NEW.status <> 'draft' THEN
            IF ROW(
                NEW.account_id,
                NEW.niche_id,
                NEW.timezone,
                NEW.starts_on,
                NEW.ends_on,
                NEW.daily_pin_limit,
                NEW.board_name,
                NEW.board_description
            ) IS DISTINCT FROM ROW(
                OLD.account_id,
                OLD.niche_id,
                OLD.timezone,
                OLD.starts_on,
                OLD.ends_on,
                OLD.daily_pin_limit,
                OLD.board_name,
                OLD.board_description
            ) THEN
                RAISE EXCEPTION 'Activated schedule configuration is immutable'
                    USING ERRCODE = 'check_violation';
            END IF;
        END IF;
    END IF;
    RETURN NEW;
END;
$$;

CREATE TRIGGER affiliate_schedule_immutability_guard
BEFORE UPDATE ON affiliate_publishing_schedules
FOR EACH ROW
EXECUTE FUNCTION model2_guard_activated_schedule_immutability();
