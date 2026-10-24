"""Run versioned PostgreSQL migrations explicitly before application rollout."""
from app.database import close_pool, run_migrations


def main() -> None:
    try:
        run_migrations()
        print("Database migrations applied successfully.")
    finally:
        close_pool()


if __name__ == "__main__":
    main()
