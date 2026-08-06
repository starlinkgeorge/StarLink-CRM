from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.config import get_settings

settings = get_settings()

if not settings["database_url"]:
    raise RuntimeError("DATABASE_URL must be configured before using the database.")

engine = create_engine(settings["database_url"], pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)


def get_db_session() -> Generator[Session, None, None]:
    """Yield a transactional database session for future API routes."""
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()
