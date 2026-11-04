-- Persistent affiliate URL scheduling queue. No schedules or jobs are seeded.
-- New schedules remain draft until an explicit operator activation action.
CREATE TABLE affiliate_publishing_schedules (
 id BIGSERIAL PRIMARY KEY,
 account_id TEXT NOT NULL CHECK (char_length(account_id) BETWEEN 1 AND 200),
 timezone TEXT NOT NULL CHECK (char_length(timezone) BETWEEN 1 AND 100),
 starts_on DATE NOT NULL,
 ends_on DATE NOT NULL,
 daily_pin_limit SMALLINT NOT NULL DEFAULT 5 CHECK (daily_pin_limit BETWEEN 1 AND 5),
 board_name TEXT NOT NULL CHECK (char_length(board_name) BETWEEN 1 AND 100),
 board_description TEXT NOT NULL DEFAULT '' CHECK (char_length(board_description) <= 500),
 status TEXT NOT NULL DEFAULT 'draft' CHECK (status IN ('draft','active','paused','completed','cancelled')),
 created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
 updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
 CHECK (ends_on >= starts_on),
 CHECK (ends_on <= starts_on + 29)
);
CREATE TABLE affiliate_product_sources (
 id BIGSERIAL PRIMARY KEY,
 schedule_id BIGINT NOT NULL REFERENCES affiliate_publishing_schedules(id) ON DELETE CASCADE,
 product_name TEXT NOT NULL CHECK (char_length(product_name) BETWEEN 1 AND 300),
 product_details TEXT NOT NULL CHECK (char_length(product_details) BETWEEN 1 AND 10000),
 affiliate_url TEXT NOT NULL CHECK (char_length(affiliate_url) BETWEEN 8 AND 4096),
 selection_weight SMALLINT NOT NULL DEFAULT 1 CHECK (selection_weight BETWEEN 1 AND 100),
 enabled BOOLEAN NOT NULL DEFAULT TRUE,
 created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
 UNIQUE (id, schedule_id)
);
CREATE TABLE affiliate_pin_jobs (
 id BIGSERIAL PRIMARY KEY,
 schedule_id BIGINT NOT NULL REFERENCES affiliate_publishing_schedules(id) ON DELETE CASCADE,
 source_id BIGINT NOT NULL,
 run_at TIMESTAMPTZ NOT NULL,
 local_run_date DATE NOT NULL,
 daily_slot SMALLINT NOT NULL CHECK (daily_slot BETWEEN 1 AND 5),
 idempotency_key TEXT NOT NULL UNIQUE CHECK (char_length(idempotency_key) BETWEEN 8 AND 200),
 status TEXT NOT NULL DEFAULT 'queued' CHECK (status IN ('queued','processing','succeeded','failed','uncertain','cancelled')),
 attempt_count SMALLINT NOT NULL DEFAULT 0 CHECK (attempt_count >= 0),
 locked_at TIMESTAMPTZ,
 finished_at TIMESTAMPTZ,
 product_id BIGINT REFERENCES products(id) ON DELETE SET NULL,
 pinterest_pin_id TEXT,
 safe_error_code TEXT,
 created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
 FOREIGN KEY (source_id, schedule_id) REFERENCES affiliate_product_sources(id, schedule_id) ON DELETE CASCADE,
 UNIQUE (schedule_id, local_run_date, daily_slot)
);
CREATE INDEX affiliate_pin_jobs_due_idx ON affiliate_pin_jobs (run_at, id) WHERE status = 'queued';
CREATE INDEX affiliate_pin_jobs_recovery_idx ON affiliate_pin_jobs (locked_at, id) WHERE status = 'processing';
CREATE INDEX affiliate_product_sources_schedule_idx ON affiliate_product_sources (schedule_id, enabled, id);

-- One active schedule per Pinterest account prevents overlapping plans from
-- exceeding the account-level daily publication cap.
CREATE UNIQUE INDEX affiliate_one_active_schedule_per_account_idx
 ON affiliate_publishing_schedules (account_id)
 WHERE status = 'active';
