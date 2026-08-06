from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.user import User
from app.security import hash_password
from app.schemas.user import UserCreate
from app.services.access_service import ensure_user_management_access
from app.services.errors import ConflictError, NotFoundError


def list_users(session: Session) -> list[User]:
    return list(session.scalars(select(User).order_by(User.name, User.id)))


def get_user(session: Session, user_id: int) -> User:
    user = session.get(User, user_id)
    if user is None:
        raise NotFoundError("User not found.")
    return user


def create_user(session: Session, payload: UserCreate) -> User:
    if session.scalar(select(User.id).where(User.email == payload.email)) is not None:
        raise ConflictError("A user with this email already exists.")
    data = payload.model_dump()
    password = data.pop("password")
    user = User(**data, password_hash=hash_password(password))
    session.add(user)
    try:
        session.commit()
    except IntegrityError as error:
        session.rollback()
        raise ConflictError("A user with this email already exists.") from error
    session.refresh(user)
    return user
