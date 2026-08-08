from collections.abc import Generator
import os
from pathlib import Path
import tempfile

os.environ["JWT_SECRET_KEY"] = "test-secret-key-that-is-long-enough-for-local-tests"
os.environ["QUOTATION_OUTPUT_DIR"] = str(
    Path(tempfile.gettempdir()) / "starlink-crm-test-quotations"
)
os.environ["FOLLOWUP_ATTACHMENT_DIR"] = str(
    Path(tempfile.gettempdir()) / "starlink-crm-test-followup-attachments"
)

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.base import Base
import app.models  # noqa: F401
from app.db.session import get_db_session
from app.main import app
from app.models.user import User, UserRole
from app.security import hash_password


@pytest.fixture()
def client() -> Generator[TestClient, None, None]:
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    test_session = sessionmaker(bind=engine, autocommit=False, autoflush=False)
    seed_session = test_session()
    seed_session.add(
        User(
            name="Administrator",
            email="admin@example.com",
            password_hash=hash_password("AdminPass123!"),
            role=UserRole.ADMIN,
        )
    )
    seed_session.commit()
    seed_session.close()

    def override_session() -> Generator[Session, None, None]:
        session = test_session()
        try:
            yield session
        finally:
            session.close()

    app.dependency_overrides[get_db_session] = override_session
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()
    Base.metadata.drop_all(engine)
