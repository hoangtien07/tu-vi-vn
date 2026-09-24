"""SPEC_V03 §III — email+password auth, HttpOnly cookie session, self-hosted."""

import hashlib
import secrets
import time
from collections import defaultdict
from datetime import UTC, datetime, timedelta
from typing import Annotated
from uuid import uuid4

from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError
from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, Field
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.infrastructure.db.models import AuthSession, ProductEvent, User
from app.infrastructure.db.session import get_session

router = APIRouter(prefix="/api/auth", tags=["auth"])

_hasher = PasswordHasher()
_SESSION_TTL = timedelta(days=30)
_SESSION_COOKIE = "tv_session"
# In-process login throttle — 10 attempts / 5 min / ip. Sufficient for the
# self-hosted V1; swap for a shared store when deployments go multi-node.
_login_attempts: dict[str, list[float]] = defaultdict(list)
_LOGIN_WINDOW = 300.0
_LOGIN_MAX = 10


class CredentialsIn(BaseModel):
    email: str = Field(min_length=3, max_length=254)
    password: str = Field(min_length=8, max_length=256)


def _new_session_token(session: Session, user_id: str) -> tuple[str, datetime]:
    raw = secrets.token_urlsafe(32)
    expires = datetime.now(UTC) + _SESSION_TTL
    session.add(
        AuthSession(
            id=hashlib.sha256(raw.encode()).hexdigest(),
            user_id=user_id,
            expires_at=expires,
        )
    )
    return raw, expires


def _set_cookie(response: Response, raw: str, expires: datetime) -> None:
    response.set_cookie(
        _SESSION_COOKIE,
        raw,
        httponly=True,
        samesite="lax",
        secure=False,  # flipped by deployment env in v0.4 hardening
        path="/api",
        expires=int(expires.timestamp()),
    )


def _throttle_login(ip: str) -> None:
    now = time.monotonic()
    hits = [t for t in _login_attempts[ip] if now - t < _LOGIN_WINDOW]
    if len(hits) >= _LOGIN_MAX:
        raise HTTPException(status_code=429, detail="too many attempts")
    hits.append(now)
    _login_attempts[ip] = hits


def current_user(
    request: Request, session: Session = Depends(get_session)
) -> User | None:
    """Optional auth — returns None when anonymous (anonymous paths stay)."""
    raw = request.cookies.get(_SESSION_COOKIE)
    if not raw:
        return None
    row = session.get(AuthSession, hashlib.sha256(raw.encode()).hexdigest())
    if row is None:
        return None
    expires = row.expires_at
    if expires.tzinfo is None:
        expires = expires.replace(tzinfo=UTC)
    if expires < datetime.now(UTC):
        return None
    return session.get(User, row.user_id)


def require_user(
    user: Annotated[User | None, Depends(current_user)],
) -> User:
    if user is None:
        raise HTTPException(status_code=401, detail="login required")
    return user


OptionalUser = Annotated[User | None, Depends(current_user)]


@router.post("/register", status_code=201)
def register(
    body: CredentialsIn,
    response: Response,
    session: Session = Depends(get_session),
) -> dict[str, str]:
    email = body.email.strip().lower()
    existing = session.scalar(select(User).where(User.email == email))
    if existing is not None:
        raise HTTPException(status_code=409, detail="email already registered")
    user = User(
        id=f"u_{uuid4().hex[:16]}",
        email=email,
        password_hash=_hasher.hash(body.password),
    )
    session.add(user)
    session.add(
        ProductEvent(id=f"ev_{uuid4().hex[:16]}", event="auth_registered")
    )
    raw, expires = _new_session_token(session, user.id)
    session.commit()
    _set_cookie(response, raw, expires)
    return {"id": user.id, "email": user.email}


@router.post("/login")
def login(
    body: CredentialsIn,
    request: Request,
    response: Response,
    session: Session = Depends(get_session),
) -> dict[str, str]:
    _throttle_login(request.client.host if request.client else "unknown")
    email = body.email.strip().lower()
    user = session.scalar(select(User).where(User.email == email))
    if user is None:
        raise HTTPException(status_code=401, detail="invalid credentials")
    try:
        _hasher.verify(user.password_hash, body.password)
    except VerifyMismatchError as exc:
        raise HTTPException(status_code=401, detail="invalid credentials") from exc
    session.add(
        ProductEvent(id=f"ev_{uuid4().hex[:16]}", event="auth_login")
    )
    raw, expires = _new_session_token(session, user.id)
    session.commit()
    _set_cookie(response, raw, expires)
    return {"id": user.id, "email": user.email}


@router.post("/logout", status_code=204)
def logout(request: Request, response: Response, session: Session = Depends(get_session)) -> None:
    raw = request.cookies.get(_SESSION_COOKIE)
    if raw:
        session.execute(
            delete(AuthSession).where(
                AuthSession.id == hashlib.sha256(raw.encode()).hexdigest()
            )
        )
        session.commit()
    response.delete_cookie(_SESSION_COOKIE, path="/api")


@router.get("/me")
def me(user: Annotated[User, Depends(require_user)]) -> dict[str, str]:
    return {"id": user.id, "email": user.email}


__all__ = ["OptionalUser", "current_user", "require_user", "router"]
