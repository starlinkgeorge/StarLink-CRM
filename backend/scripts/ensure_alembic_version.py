"""Ensure Alembic can persist long revision identifiers before migrations run."""

import os
import sys
from pathlib import Path

from sqlalchemy import create_engine, text


# This script is invoked as ``python scripts/ensure_alembic_version.py`` by
# Docker, so ensure the backend root is importable before using the shared URL
# normalizer.
BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.db.url import normalize_database_url


def main() -> None:
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        raise RuntimeError("DATABASE_URL must be set before preparing Alembic.")

    engine = create_engine(normalize_database_url(database_url))
    with engine.begin() as connection:
        # Creating the table here handles a brand-new database. Existing
        # databases are altered idempotently before Alembic reaches 0011.
        connection.execute(
            text(
                "CREATE TABLE IF NOT EXISTS alembic_version ("
                "version_num VARCHAR(100) NOT NULL PRIMARY KEY)"
            )
        )
        connection.execute(
            text(
                "ALTER TABLE alembic_version "
                "ALTER COLUMN version_num TYPE VARCHAR(100)"
            )
        )


if __name__ == "__main__":
    main()
