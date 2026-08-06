from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session
from jwt import InvalidTokenError

from app.config import get_settings
from app.models.auth import RefreshToken
from app.models.user import User
from app.schemas.auth import LoginRequest, TokenPair
from app.security import create_token, decode_token, hash_token, verify_password


def _issue_token_pair(session: Session, user: User) -> TokenPair:
    settings = get_settings()
    access_token, access_expires_at = create_token(
        user, "access", timedelta(minutes=int(settings["jwt_access_token_minutes"]))
    )
    refresh_token, refresh_expires_at = create_token(
        user, "refresh", timedelta(days=int(settings["jwt_refresh_token_days"]))
    )
    session.add(
        RefreshToken(user_id=user.id, token_hash=hash_token(refresh_token), expires_at=refresh_expires_at)
    )
    session.commit()
    return TokenPair(
        access_token=access_token,
        refresh_token=refresh_token,
        user=user,
        access_token_expires_at=access_expires_at,
    )


def login(session: Session, payload: LoginRequest) -> TokenPair | None:
    user = session.scalar(select(User).where(User.email == payload.email))
    if user is None or not verify_password(payload.password, user.password_hash):
        return None
    user.last_login_at = datetime.now(UTC)
    return _issue_token_pair(session, user)


def refresh(session: Session, refresh_token: str) -> TokenPair | None:
    try:
        payload = decode_token(refresh_token, "refresh")
        user_id = int(payload["sub"])
    except (InvalidTokenError, KeyError, TypeError, ValueError):
        return None
    token_record = session.scalar(
        select(RefreshToken).where(RefreshToken.token_hash == hash_token(refresh_token))
    )
    if token_record is None:
        return None
    expires_at = token_record.expires_at
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=UTC)
    if (
        token_record.revoked_at is not None
        or expires_at <= datetime.now(UTC)
    ):
        return None
    user = session.get(User, user_id)
    if user is None or token_record.user_id != user.id:
        return None
    token_record.revoked_at = datetime.now(UTC)
    return _issue_token_pair(session, user)
