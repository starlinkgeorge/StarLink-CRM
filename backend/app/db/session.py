from collections.abc import Generator
from functools import lru_cache

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import NullPool

from app.config import get_settings

@lru_cache
def get_session_factory() -> sessionmaker[Session]:
    database_url = get_settings()["database_url"]
    if not database_url:
        raise RuntimeError("DATABASE_URL must be configured before using the database.")
    # Neon commonly provides a standard ``postgresql://`` URL. SQLAlchemy's
    # modern psycopg dialect needs the explicit driver marker used by this app.
    if database_url.startswith("postgresql://"):
        database_url = database_url.replace("postgresql://", "postgresql+psycopg://", 1)
    elif database_url.startswith("postgres://"):
        database_url = database_url.replace("postgres://", "postgresql+psycopg://", 1)

    engine_options = {"pool_pre_ping": True}
    if get_settings()["database_pool_mode"] == "null":
        # Serverless instances must not retain idle database connections.
        engine_options["poolclass"] = NullPool
    engine = create_engine(database_url, **engine_options)
    return sessionmaker(bind=engine, autocommit=False, autoflush=False)


def get_db_session() -> Generator[Session, None, None]:
    """Yield a transactional database session for future API routes."""
    session = get_session_factory()()
    try:
        yield session
    finally:
        session.close()
