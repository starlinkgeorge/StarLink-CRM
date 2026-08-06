"""Create the first StarLink CRM administrator without exposing public registration."""

from getpass import getpass
from pathlib import Path
import sys

from sqlalchemy import select

# Allow this standalone script to import the sibling /app package in the container.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.db.session import get_session_factory
from app.models.user import User
from app.security import hash_password


def sanitize_input(value: str) -> str:
    """Remove invalid Unicode code points before storing input in PostgreSQL."""
    return value.encode("utf-8", errors="ignore").decode("utf-8").strip()


def main() -> None:
    name = sanitize_input(input("Administrator name: "))
    email = sanitize_input(input("Administrator email: ")).lower()
    password = sanitize_input(getpass("Administrator password: "))
    if not name or not email or len(password) < 8 or len(password) > 72:
        raise SystemExit("Name, email, and an 8-72 character password are required.")

    session = get_session_factory()()
    try:
        if session.scalar(select(User.id).where(User.email == email)) is not None:
            raise SystemExit("A user with this email already exists.")
        session.add(User(name=name, email=email, password_hash=hash_password(password), role="Admin"))
        session.commit()
    finally:
        session.close()
    print("Administrator created.")


if __name__ == "__main__":
    main()
