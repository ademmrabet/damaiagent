"""
Password hashing, JWT issuance/verification, and login-attempt rate
limiting - the pieces every login path (form, Google, Microsoft) ends
up sharing once a User row exists. OAuth-specific redirect/callback
logic lives in webapp/oauth.py; this module is deliberately unaware
of which login path produced the user it's issuing a token for.

Matches the design already committed to in the thesis (Chapter 5):
bcrypt for password hashing, JWT signed HS256 with an 8-hour
expiry, account id + role + expiry as the token's claims, and a
generic "incorrect email or password" failure message that doesn't
reveal whether the email exists (so /api/auth/login can't be used to
enumerate valid accounts).
"""

import os
import time
from collections import defaultdict
from datetime import datetime, timedelta, timezone

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy.orm import Session

from webapp.db import get_db
from webapp.models import User

JWT_SECRET_KEY = os.environ["JWT_SECRET_KEY"]
JWT_ALGORITHM = "HS256"
JWT_EXPIRY = timedelta(hours=8)

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
bearer_scheme = HTTPBearer(auto_error=False)


def hash_password(plain_password: str) -> str:
    return pwd_context.hash(plain_password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)


def create_access_token(user: User) -> str:
    now = datetime.now(timezone.utc)
    claims = {
        "sub": str(user.id),
        "email": user.email,
        "role": user.role.value if hasattr(user.role, "value") else user.role,
        "iat": now,
        "exp": now + JWT_EXPIRY,
    }
    return jwt.encode(claims, JWT_SECRET_KEY, algorithm=JWT_ALGORITHM)


def decode_access_token(token: str) -> dict:
    """Raises jose.JWTError on anything wrong (expired, bad signature, malformed)."""
    return jwt.decode(token, JWT_SECRET_KEY, algorithms=[JWT_ALGORITHM])


def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> User:
    """
    FastAPI dependency for any endpoint that requires a logged-in
    user. Add `user: User = Depends(get_current_user)` to a route's
    signature and FastAPI handles extracting + validating the
    Authorization header before the route body ever runs.
    """
    if credentials is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")

    try:
        payload = decode_access_token(credentials.credentials)
    except JWTError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired token")

    user = db.get(User, payload.get("sub"))
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User no longer exists")

    return user


def require_admin(user: User = Depends(get_current_user)) -> User:
    """
    Stricter version of get_current_user for administrator-only
    routes (the dashboard and analytics endpoints per Chapter 5's
    role table - the analytics layer exposes organisation-wide query
    patterns, which is sensitive in a way an individual's own
    conversation isn't).
    """
    role = user.role.value if hasattr(user.role, "value") else user.role
    if role != "administrator":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Administrator access required")
    return user


_LOGIN_ATTEMPTS: dict[str, list[float]] = defaultdict(list)
_MAX_ATTEMPTS = 5
_WINDOW_SECONDS = 5 * 60


def check_login_rate_limit(client_ip: str) -> None:
    now = time.time()
    attempts = _LOGIN_ATTEMPTS[client_ip]
    attempts[:] = [t for t in attempts if now - t < _WINDOW_SECONDS]

    if len(attempts) >= _MAX_ATTEMPTS:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many login attempts. Try again in a few minutes.",
        )

    attempts.append(now)
