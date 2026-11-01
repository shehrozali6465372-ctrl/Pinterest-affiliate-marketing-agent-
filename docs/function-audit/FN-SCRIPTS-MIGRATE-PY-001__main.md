# main

- **Unique ID:** `FN-SCRIPTS-MIGRATE-PY-001`
- **Source:** `scripts/migrate.py:5-15`
- **Source blob SHA:** `83e9e4551781888892691dc375da7e43fde2c18e`
- **Status:** `UNVERIFIED`

## Logic explanation

CLI entry point for running database migrations. Verify argument parsing, database target selection, migration ordering and failure exit code. This is a database-mutating operation and was not executed.

## Exact isolated source

```python
def main() -> None:
    try:
        run_migrations()
        print("Database migrations applied successfully.")
    finally:
        close_pool()


if __name__ == "__main__":
    main()
```

## Verification tags

- `VERIFIED — SOURCE PRESENT`: exact source retrieved.
- `UNVERIFIED — EXECUTION SAFETY`: command-line defaults and disposable DB guard need test review.
- `UNVERIFIED — LIVE DATABASE`: no migration command run.
