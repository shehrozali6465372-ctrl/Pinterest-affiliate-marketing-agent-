-- Model 2 foundation: single-operator account registry, explicit niche mapping,
-- immutable publication attribution, and evidence-backed niche aggregates.
-- Additive only. No existing Model 1 rows are backfilled or rewritten.
-- Apply only after Phase 2 approval and only to a verified disposable DB in tests.

CREATE TABLE IF NOT EXISTS model2_niches (
    id BIGSERIAL PRIMARY KEY,
    slug TEXT NOT NULL UNIQUE
        CHECK (slug = lower(slug) AND slug ~ '^[a-z0-9]+(-[a-z0-9]+)*$'),
    display_name TEXT NOT NULL
        CHECK (char_length(btrim(display_name)) BETWEEN 1 AND 120),
    description TEXT NOT NULL DEFAULT ''
        CHECK (char_length(description) <= 2000),
    default_region TEXT NOT NULL DEFAULT 'US'
        CHECK (default_region IN ('US', 'GB+IE')),
    status TEXT NOT NULL DEFAULT 'active'
        CHECK (status IN ('active', 'archived')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS model2_account_profiles (
    account_id TEXT PRIMARY KEY
        CHECK (
            char_length(btrim(account_id)) BETWEEN 10 AND 200
            AND account_id ~ '^pinterest:[^:[:space:]]+$'
        )
        REFERENCES pinterest_credentials(account_id) ON DELETE RESTRICT,
    display_name TEXT NOT NULL DEFAULT ''
        CHECK (char_length(display_name) <= 120),
    status TEXT NOT NULL DEFAULT 'active'
        CHECK (status IN ('active', 'paused')),
    timezone TEXT NOT NULL DEFAULT 'UTC'
        CHECK (char_length(timezone) BETWEEN 1 AND 100),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS model2_account_niches (
    account_id TEXT NOT NULL
        REFERENCES model2_account_profiles(account_id) ON DELETE RESTRICT,
    niche_id BIGINT NOT NULL
        REFERENCES model2_niches(id) ON DELETE RESTRICT,
    is_primary BOOLEAN NOT NULL DEFAULT FALSE,
    status TEXT NOT NULL DEFAULT 'active'
        CHECK (status IN ('active', 'paused')),
    settings JSONB NOT NULL DEFAULT '{}'::jsonb
        CHECK (
            jsonb_typeof(settings) = 'object'
            AND settings = '{}'::jsonb
            AND pg_column_size(settings) <= 1024
        ),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (account_id, niche_id)
);

CREATE UNIQUE INDEX IF NOT EXISTS model2_one_primary_niche_per_account_idx
    ON model2_account_niches(account_id)
    WHERE is_primary = TRUE AND status = 'active';

CREATE INDEX IF NOT EXISTS model2_account_niches_niche_idx
    ON model2_account_niches(niche_id, status, account_id);

CREATE UNIQUE INDEX IF NOT EXISTS pin_publications_id_account_unique_idx
    ON pin_publications(id, account_id);

CREATE TABLE IF NOT EXISTS model2_publication_niche_attributions (
    publication_id BIGINT PRIMARY KEY,
    account_id TEXT NOT NULL,
    niche_id BIGINT NOT NULL,
    attribution_source TEXT NOT NULL
        CHECK (attribution_source IN ('workflow', 'operator_verified')),
    attributed_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    FOREIGN KEY (publication_id, account_id)
        REFERENCES pin_publications(id, account_id) ON DELETE RESTRICT,
    FOREIGN KEY (account_id, niche_id)
        REFERENCES model2_account_niches(account_id, niche_id) ON DELETE RESTRICT
);

CREATE INDEX IF NOT EXISTS model2_publication_niche_account_idx
    ON model2_publication_niche_attributions(account_id, niche_id, attributed_at DESC);

CREATE OR REPLACE FUNCTION model2_reject_attribution_mutation()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    RAISE EXCEPTION 'Model 2 publication niche attribution is immutable';
END;
$$;

DROP TRIGGER IF EXISTS model2_publication_attribution_immutable
    ON model2_publication_niche_attributions;
CREATE TRIGGER model2_publication_attribution_immutable
    BEFORE UPDATE OR DELETE ON model2_publication_niche_attributions
    FOR EACH ROW EXECUTE FUNCTION model2_reject_attribution_mutation();

CREATE TABLE IF NOT EXISTS model2_learning_snapshots (
    id BIGSERIAL PRIMARY KEY,
    account_id TEXT NOT NULL,
    niche_id BIGINT NOT NULL,
    period_start DATE NOT NULL,
    period_end DATE NOT NULL,
    metrics JSONB NOT NULL
        CHECK (
            jsonb_typeof(metrics) = 'object'
            AND pg_column_size(metrics) <= 4096
            AND (metrics - ARRAY['impression', 'save', 'pin_click', 'outbound_click']::text[]) = '{}'::jsonb
            AND COALESCE(jsonb_typeof(metrics -> 'impression') IN ('number', 'null'), TRUE)
            AND COALESCE(jsonb_typeof(metrics -> 'save') IN ('number', 'null'), TRUE)
            AND COALESCE(jsonb_typeof(metrics -> 'pin_click') IN ('number', 'null'), TRUE)
            AND COALESCE(jsonb_typeof(metrics -> 'outbound_click') IN ('number', 'null'), TRUE)
            AND COALESCE(jsonb_typeof(metrics -> 'impression') <> 'number' OR (metrics ->> 'impression')::numeric >= 0, TRUE)
            AND COALESCE(jsonb_typeof(metrics -> 'save') <> 'number' OR (metrics ->> 'save')::numeric >= 0, TRUE)
            AND COALESCE(jsonb_typeof(metrics -> 'pin_click') <> 'number' OR (metrics ->> 'pin_click')::numeric >= 0, TRUE)
            AND COALESCE(jsonb_typeof(metrics -> 'outbound_click') <> 'number' OR (metrics ->> 'outbound_click')::numeric >= 0, TRUE)
        ),
    sample_size INTEGER NOT NULL CHECK (sample_size >= 0),
    source_snapshot_count INTEGER NOT NULL
        CHECK (source_snapshot_count >= 0 AND source_snapshot_count >= sample_size),
    -- Bumped by each source insert to force a parent-row version change.
    -- This also makes concurrent REPEATABLE READ writers serialize-fail safely.
    source_lock_version BIGINT NOT NULL DEFAULT 0 CHECK (source_lock_version >= 0),
    learning_status TEXT NOT NULL DEFAULT 'descriptive_only'
        CHECK (learning_status IN ('descriptive_only', 'insufficient_data')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CHECK (period_end >= period_start),
    FOREIGN KEY (account_id, niche_id)
        REFERENCES model2_account_niches(account_id, niche_id) ON DELETE RESTRICT,
    UNIQUE (account_id, niche_id, period_start, period_end)
);

CREATE INDEX IF NOT EXISTS model2_learning_account_period_idx
    ON model2_learning_snapshots(account_id, period_end DESC);

CREATE INDEX IF NOT EXISTS model2_learning_niche_period_idx
    ON model2_learning_snapshots(niche_id, period_end DESC);

-- Preserve exact raw analytics lineage for every niche aggregate.
CREATE UNIQUE INDEX IF NOT EXISTS model2_publication_attribution_lineage_idx
    ON model2_publication_niche_attributions(publication_id, account_id, niche_id);

CREATE UNIQUE INDEX IF NOT EXISTS model2_learning_snapshot_lineage_idx
    ON model2_learning_snapshots(id, account_id, niche_id);

CREATE UNIQUE INDEX IF NOT EXISTS pin_analytics_snapshot_publication_lineage_idx
    ON pin_analytics_snapshots(id, publication_id);

CREATE TABLE IF NOT EXISTS model2_learning_snapshot_sources (
    learning_snapshot_id BIGINT NOT NULL,
    analytics_snapshot_id BIGINT NOT NULL,
    publication_id BIGINT NOT NULL,
    account_id TEXT NOT NULL,
    niche_id BIGINT NOT NULL,
    -- Immutable copy of the raw metrics as consumed by this aggregate.
    -- Model 1 refreshes raw analytics rows in place on repeated fetches.
    source_metrics JSONB NOT NULL
        CHECK (
            jsonb_typeof(source_metrics) = 'object'
            AND pg_column_size(source_metrics) <= 4096
            AND (source_metrics - ARRAY['impression', 'save', 'pin_click', 'outbound_click']::text[]) = '{}'::jsonb
            AND COALESCE(jsonb_typeof(source_metrics -> 'impression') IN ('number', 'null'), TRUE)
            AND COALESCE(jsonb_typeof(source_metrics -> 'save') IN ('number', 'null'), TRUE)
            AND COALESCE(jsonb_typeof(source_metrics -> 'pin_click') IN ('number', 'null'), TRUE)
            AND COALESCE(jsonb_typeof(source_metrics -> 'outbound_click') IN ('number', 'null'), TRUE)
            AND COALESCE(jsonb_typeof(source_metrics -> 'impression') <> 'number' OR (source_metrics ->> 'impression')::numeric >= 0, TRUE)
            AND COALESCE(jsonb_typeof(source_metrics -> 'save') <> 'number' OR (source_metrics ->> 'save')::numeric >= 0, TRUE)
            AND COALESCE(jsonb_typeof(source_metrics -> 'pin_click') <> 'number' OR (source_metrics ->> 'pin_click')::numeric >= 0, TRUE)
            AND COALESCE(jsonb_typeof(source_metrics -> 'outbound_click') <> 'number' OR (source_metrics ->> 'outbound_click')::numeric >= 0, TRUE)
        ),
    PRIMARY KEY (learning_snapshot_id, analytics_snapshot_id),
    FOREIGN KEY (learning_snapshot_id, account_id, niche_id)
        REFERENCES model2_learning_snapshots(id, account_id, niche_id) ON DELETE RESTRICT,
    FOREIGN KEY (analytics_snapshot_id, publication_id)
        REFERENCES pin_analytics_snapshots(id, publication_id) ON DELETE RESTRICT,
    FOREIGN KEY (publication_id, account_id, niche_id)
        REFERENCES model2_publication_niche_attributions(publication_id, account_id, niche_id)
        ON DELETE RESTRICT
);

CREATE INDEX IF NOT EXISTS model2_learning_sources_publication_idx
    ON model2_learning_snapshot_sources(publication_id, account_id, niche_id);

CREATE OR REPLACE FUNCTION model2_capture_learning_source_metrics()
RETURNS trigger
LANGUAGE plpgsql
AS $$
DECLARE
    captured_metrics JSONB;
BEGIN
    SELECT metrics
      INTO captured_metrics
      FROM pin_analytics_snapshots
     WHERE id = NEW.analytics_snapshot_id
       AND publication_id = NEW.publication_id;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'Model 2 learning source analytics row does not exist';
    END IF;

    NEW.source_metrics := captured_metrics;
    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS model2_learning_source_metrics_capture
    ON model2_learning_snapshot_sources;
CREATE TRIGGER model2_learning_source_metrics_capture
    BEFORE INSERT ON model2_learning_snapshot_sources
    FOR EACH ROW EXECUTE FUNCTION model2_capture_learning_source_metrics();

-- Serialize source inserts per learning snapshot before FK checks. Writers inserting for multiple snapshots should use ascending learning_snapshot_id order to avoid cross-snapshot deadlocks.
CREATE OR REPLACE FUNCTION model2_lock_learning_snapshot_source_parent()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    -- A real UPDATE (not only SELECT FOR UPDATE) creates a new parent-row
    -- version. READ COMMITTED writers then see the prior committed source;
    -- REPEATABLE READ / SERIALIZABLE writers with an old snapshot receive
    -- SQLSTATE 40001 and must retry the whole transaction.
    UPDATE model2_learning_snapshots
       SET source_lock_version = source_lock_version + 1
     WHERE id = NEW.learning_snapshot_id;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'Model 2 learning snapshot parent does not exist';
    END IF;

    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS model2_learning_source_parent_lock
    ON model2_learning_snapshot_sources;
CREATE TRIGGER model2_learning_source_parent_lock
    BEFORE INSERT ON model2_learning_snapshot_sources
    FOR EACH ROW EXECUTE FUNCTION model2_lock_learning_snapshot_source_parent();

CREATE OR REPLACE FUNCTION model2_validate_learning_snapshot_source_counts()
RETURNS trigger
LANGUAGE plpgsql
AS $$
DECLARE
    target_snapshot_id BIGINT;
    expected_publications INTEGER;
    expected_snapshots INTEGER;
    actual_publications BIGINT;
    actual_snapshots BIGINT;
BEGIN
    IF TG_TABLE_NAME = 'model2_learning_snapshots' THEN
        target_snapshot_id := NEW.id;
    ELSIF TG_OP = 'DELETE' THEN
        target_snapshot_id := OLD.learning_snapshot_id;
    ELSE
        target_snapshot_id := NEW.learning_snapshot_id;
    END IF;

    SELECT sample_size, source_snapshot_count
      INTO expected_publications, expected_snapshots
      FROM model2_learning_snapshots
     WHERE id = target_snapshot_id;

    IF NOT FOUND THEN
        RETURN NULL;
    END IF;

    SELECT COUNT(DISTINCT publication_id), COUNT(*)
      INTO actual_publications, actual_snapshots
      FROM model2_learning_snapshot_sources
     WHERE learning_snapshot_id = target_snapshot_id;

    IF actual_publications <> expected_publications
       OR actual_snapshots <> expected_snapshots THEN
        RAISE EXCEPTION
            'Model 2 learning source counts do not match snapshot %: publications %, snapshots %',
            target_snapshot_id, actual_publications, actual_snapshots;
    END IF;

    RETURN NULL;
END;
$$;

DROP TRIGGER IF EXISTS model2_learning_snapshot_counts_deferred
    ON model2_learning_snapshots;
CREATE CONSTRAINT TRIGGER model2_learning_snapshot_counts_deferred
    AFTER INSERT OR UPDATE ON model2_learning_snapshots
    DEFERRABLE INITIALLY DEFERRED
    FOR EACH ROW EXECUTE FUNCTION model2_validate_learning_snapshot_source_counts();

DROP TRIGGER IF EXISTS model2_learning_sources_counts_deferred
    ON model2_learning_snapshot_sources;
CREATE CONSTRAINT TRIGGER model2_learning_sources_counts_deferred
    AFTER INSERT OR DELETE ON model2_learning_snapshot_sources
    DEFERRABLE INITIALLY DEFERRED
    FOR EACH ROW EXECUTE FUNCTION model2_validate_learning_snapshot_source_counts();

CREATE OR REPLACE FUNCTION model2_reject_learning_source_mutation()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    RAISE EXCEPTION 'Model 2 learning snapshot source lineage is immutable';
END;
$$;

DROP TRIGGER IF EXISTS model2_learning_sources_immutable
    ON model2_learning_snapshot_sources;
CREATE TRIGGER model2_learning_sources_immutable
    BEFORE UPDATE OR DELETE ON model2_learning_snapshot_sources
    FOR EACH ROW EXECUTE FUNCTION model2_reject_learning_source_mutation();
