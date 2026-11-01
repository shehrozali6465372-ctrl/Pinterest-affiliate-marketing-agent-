# migrate.main — source-level review

- ID: `FN-SCRIPTS-MIGRATE-PY-001`; source `scripts/migrate.py:5-15`; baseline `336d8bcd793843e4c3bb0aa626005fc6b82f0ef0`.
- Source review: COMPLETE. Runtime DB verification: NOT RUN.

## Behavior
Calls database.run_migrations(); prints success only after it returns; always calls close_pool() in finally. Migration exceptions propagate after pool close, producing non-zero script failure unless caller suppresses it. The __main__ guard prevents migration execution on import.

## Operational risk
The script uses DATABASE_URL from application settings and has no environment/target confirmation prompt or CLI override. Running it against production changes schema. It was not executed; no migration was applied.
