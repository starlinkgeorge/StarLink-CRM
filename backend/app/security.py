from datetime import UTC, datetime, timedelta
from hashlib import sha256

import bcrypt
import jwt
from jwt import InvalidTokenError

from app.config import get_settings
from app.models.user import User

ALGORITHM = "HS256"


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode(), password_hash.encode())
    except ValueError:
        return False


def hash_token(token: str) -> str:
    return sha256(token.encode()).hexdigest()


def create_token(user: User, token_type: str, expires_in: timedelta) -> tuple[str, datetime]:
    settings = get_settings()
    secret = settings["jwt_secret_key"]
    if not secret or secret == "replace_with_a_long_random_secret_before_running":
        raise RuntimeError("JWT_SECRET_KEY must be configured with a secure value.")
    expires_at = datetime.now(UTC) + expires_in
    payload = {
        "sub": str(user.id),
        "role": user.role.value,
        "type": token_type,
        "iat": datetime.now(UTC),
        "exp": expires_at,
    }
    return jwt.encode(payload, secret, algorithm=ALGORITHM), expires_at


def decode_token(token: str, expected_type: str) -> dict[str, object]:
    secret = get_settings()["jwt_secret_key"]
    if not secret:
        raise InvalidTokenError("JWT secret is not configured.")
    payload = jwt.decode(token, secret, algorithms=[ALGORITHM])
    if payload.get("type") != expected_type:
        raise InvalidTokenError("Unexpected token type.")
    return payload
