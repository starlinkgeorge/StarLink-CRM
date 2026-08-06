from collections.abc import Generator
from functools import lru_cache

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.config import get_settings

@lru_cache
def get_session_factory() -> sessionmaker[Session]:
    database_url = get_settings()["database_url"]
    if not database_url:
        raise RuntimeError("DATABASE_URL must be configured before using the database.")
    engine = create_engine(database_url, pool_pre_ping=True)
    return sessionmaker(bind=engine, autocommit=False, autoflush=False)


def get_db_session() -> Generator[Session, None, None]:
    """Yield a transactional database session for future API routes."""
    session = get_session_factory()()
    try:
        yield session
    finally:
        session.close()
