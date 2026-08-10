"""Database URL helpers shared by the API and migration tooling."""


def normalize_database_url(database_url: str) -> str:
    """Select SQLAlchemy's psycopg v3 dialect for PostgreSQL URLs.

    Neon commonly supplies a standard ``postgresql://`` URL. SQLAlchemy uses
    its legacy default driver for that unqualified scheme, while this project
    installs psycopg v3 exclusively.
    """
    normalized = database_url.strip()
    if normalized.startswith("postgresql://"):
        return normalized.replace("postgresql://", "postgresql+psycopg://", 1)
    if normalized.startswith("postgres://"):
        return normalized.replace("postgres://", "postgresql+psycopg://", 1)
    return normalized
