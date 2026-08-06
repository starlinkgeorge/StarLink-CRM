"""Create the first StarLink CRM administrator without exposing public registration."""

from getpass import getpass

from sqlalchemy import select

from app.db.session import get_session_factory
from app.models.user import User, UserRole
from app.security import hash_password


def main() -> None:
    name = input("Administrator name: ").strip()
    email = input("Administrator email: ").strip().lower()
    password = getpass("Administrator password: ")
    if not name or not email or len(password) < 8 or len(password) > 72:
        raise SystemExit("Name, email, and an 8-72 character password are required.")

    session = get_session_factory()()
    try:
        if session.scalar(select(User.id).where(User.email == email)) is not None:
            raise SystemExit("A user with this email already exists.")
        session.add(User(name=name, email=email, password_hash=hash_password(password), role=UserRole.ADMIN))
        session.commit()
    finally:
        session.close()
    print("Administrator created.")


if __name__ == "__main__":
    main()
