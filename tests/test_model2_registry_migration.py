from pathlib import Path


MIGRATION = (
    Path(__file__).resolve().parents[1]
    / "migrations"
    / "013_model2_account_niche_registry.sql"
)


def test_model2_registry_migration_is_additive_and_scoped():
    sql = MIGRATION.read_text(encoding="utf-8").lower()

    for table in (
        "model2_niches",
        "model2_account_profiles",
        "model2_account_niches",
        "model2_publication_niche_attributions",
        "model2_learning_snapshots",
        "model2_learning_snapshot_sources",
    ):
        assert f"create table if not exists {table}" in sql

    assert "references pinterest_credentials(account_id) on delete restrict" in sql
    assert "account_id ~ '^pinterest:[^:[:space:]]+$'" in sql
    assert "model2_one_primary_niche_per_account_idx" in sql
    assert "references pin_publications(id, account_id) on delete restrict" in sql
    assert "references model2_account_niches(account_id, niche_id) on delete restrict" in sql
    assert "model2_publication_attribution_immutable" in sql
    assert "pg_column_size(metrics) <= 4096" in sql
    assert "metrics - array['impression', 'save', 'pin_click', 'outbound_click']" in sql

    forbidden = (
        "insert into pinterest_credentials",
        "update pinterest_credentials",
        "delete from pinterest_credentials",
        "insert into affiliate_publishing_schedules",
        "update affiliate_publishing_schedules",
        "delete from affiliate_publishing_schedules",
        "insert into pin_publications",
        "update pin_publications",
        "delete from pin_publications",
        "delete from pin_analytics_snapshots",
        "update pin_analytics_snapshots",
        "drop table",
        "truncate ",
    )
    assert not any(statement in sql for statement in forbidden)


def test_model2_attribution_is_account_and_niche_scoped_and_immutable():
    sql = MIGRATION.read_text(encoding="utf-8").lower()
    attribution = sql.split(
        "create table if not exists model2_publication_niche_attributions", 1
    )[1].split("create index", 1)[0]

    assert "foreign key (publication_id, account_id)" in attribution
    assert "references pin_publications(id, account_id)" in attribution
    assert "foreign key (account_id, niche_id)" in attribution
    assert "references model2_account_niches(account_id, niche_id)" in attribution
    assert "before update or delete" in sql
    assert "raise exception 'model 2 publication niche attribution is immutable'" in sql


def test_model2_learning_snapshot_has_bounded_metrics_and_source_counts():
    sql = MIGRATION.read_text(encoding="utf-8").lower()
    learning_table = sql.split(
        "create table if not exists model2_learning_snapshots", 1
    )[1]

    assert "foreign key (account_id, niche_id)" in learning_table
    assert "references model2_account_niches(account_id, niche_id) on delete restrict" in learning_table
    assert "sample_size integer not null check (sample_size >= 0)" in learning_table
    assert "source_snapshot_count >= sample_size" in learning_table
    assert "pg_column_size(metrics) <= 4096" in learning_table
    assert "metrics -> 'impression'" in learning_table
    assert "metrics -> 'outbound_click'" in learning_table



def test_model2_learning_sources_prove_raw_analytics_and_publication_attribution():
    sql = MIGRATION.read_text(encoding="utf-8").lower()
    sources = sql.split(
        "create table if not exists model2_learning_snapshot_sources", 1
    )[1].split("create index", 1)[0]

    assert "references model2_learning_snapshots(id, account_id, niche_id) on delete restrict" in sources
    assert "references pin_analytics_snapshots(id, publication_id) on delete restrict" in sources
    assert "references model2_publication_niche_attributions(publication_id, account_id, niche_id)" in sources
    assert "model2_validate_learning_snapshot_source_counts" in sql
    assert "deferrable initially deferred" in sql
    assert "source_metrics jsonb not null" in sources
    assert "model2_capture_learning_source_metrics" in sql
    assert "before insert on model2_learning_snapshot_sources" in sql
    assert "new.source_metrics := captured_metrics" in sql
    assert "count(distinct publication_id)" in sql
    assert "count(*)" in sql
    assert "model 2 learning snapshot source lineage is immutable" in sql



def test_model2_learning_source_writers_serialize_on_parent_snapshot():
    sql = MIGRATION.read_text(encoding="utf-8").lower()
    assert "create or replace function model2_lock_learning_snapshot_source_parent()" in sql
    lock_function = sql.split(
        "create or replace function model2_lock_learning_snapshot_source_parent()", 1
    )[1].split("create or replace function model2_validate_learning_snapshot_source_counts()", 1)[0]
    assert "source_lock_version = source_lock_version + 1" in lock_function
    assert "update model2_learning_snapshots" in lock_function
    assert "before insert on model2_learning_snapshot_sources" in lock_function
    assert "source_lock_version bigint not null default 0" in sql


def test_model2_postgres_fixture_cleanup_covers_concurrency_suffixes():
    source = (MIGRATION.parents[1] / "tests" / "test_model2_registry_postgres.py").read_text(encoding="utf-8").lower()
    assert "where pinterest_pin_id like %s" in source
    assert "and board_id like %s" in source
    assert "product_name like %s" in source


MIGRATION_014 = (
    Path(__file__).resolve().parents[1]
    / "migrations"
    / "014_model2_account_aware_scheduling.sql"
)


def test_model2_scheduler_migration_is_additive_and_preserves_legacy_schedules():
    sql = MIGRATION_014.read_text(encoding="utf-8").lower()
    assert "add column niche_id bigint" in sql
    assert "foreign key (account_id, niche_id)" in sql
    assert "references model2_account_niches (account_id, niche_id)" in sql
    assert "niche_id is null" in sql
    assert "status in ('processing', 'succeeded', 'uncertain')" in sql
    assert "affiliate_one_active_schedule_per_account_idx" not in sql
    assert "update affiliate_publishing_schedules" not in sql
    assert "delete from affiliate_publishing_schedules" not in sql
    assert "update affiliate_pin_jobs" not in sql
    assert "delete from affiliate_pin_jobs" not in sql


def test_model2_activated_schedule_configuration_is_database_immutable():
    sql = MIGRATION_014.read_text(encoding="utf-8").lower()
    assert "create or replace function model2_guard_activated_schedule_immutability()" in sql
    assert "before update on affiliate_publishing_schedules" in sql
    assert "old.niche_id is not null or new.niche_id is not null" in sql
    assert "invalid model 2 schedule state transition" in sql
    assert "new.daily_pin_limit" in sql
    assert "new.board_name" in sql
    assert "activated schedule configuration is immutable" in sql
