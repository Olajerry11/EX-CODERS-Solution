# =============================================================================
# EX-DIGITAL — JWT Authentication & RBAC Utilities
# =============================================================================
# Provides token creation, verification, and role-gated dependency injectors
# for FastAPI route protection.
# =============================================================================

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
import bcrypt
from sqlalchemy.orm import Session as DBSession

from database.config import get_db
from database.models import User, UserRole
from .settings import settings

# ---------------------------------------------------------------------------
# Password hashing (using bcrypt directly for Python 3.14 compatibility)
# ---------------------------------------------------------------------------

def verify_password(plain: str, hashed: str) -> bool:
    return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))

def hash_password(plain: str) -> str:
    return bcrypt.hashpw(plain.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")

# ---------------------------------------------------------------------------
# OAuth2 scheme (reads the Bearer token from the Authorization header)
# ---------------------------------------------------------------------------
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")

# ---------------------------------------------------------------------------
# Token creation
# ---------------------------------------------------------------------------

def create_access_token(
    user_id: str,
    email: str,
    role: str,
    expires_delta: timedelta | None = None,
) -> str:
    """
    Create a signed JWT containing the user's identity and role.
    """
    expire = datetime.now(timezone.utc) + (
        expires_delta or timedelta(minutes=settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    payload = {
        "sub": user_id,
        "email": email,
        "role": role,
        "exp": expire,
    }
    return jwt.encode(payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)

# ---------------------------------------------------------------------------
# Token verification & current-user dependency
# ---------------------------------------------------------------------------

def _decode_token(token: str) -> dict:
    """Decode and validate a JWT, raising 401 on failure."""
    try:
        payload = jwt.decode(
            token,
            settings.JWT_SECRET_KEY,
            algorithms=[settings.JWT_ALGORITHM],
        )
        if payload.get("sub") is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token payload missing subject",
            )
        return payload
    except JWTError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid or expired token: {exc}",
            headers={"WWW-Authenticate": "Bearer"},
        )


def get_current_user(
    token: Annotated[str, Depends(oauth2_scheme)],
    db: DBSession = Depends(get_db),
) -> User:
    """
    FastAPI dependency — resolves the authenticated user from the JWT.
    """
    payload = _decode_token(token)
    user = db.query(User).filter(User.id == payload["sub"]).first()
    if user is None or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or deactivated",
        )
    return user

# ---------------------------------------------------------------------------
# Role-gated dependencies
# ---------------------------------------------------------------------------

def require_role(*allowed_roles: UserRole):
    """
    Factory that returns a FastAPI dependency enforcing role-based access.

    Usage:
        @router.get("/admin-only", dependencies=[Depends(require_role(UserRole.ADMIN))])
    """
    def _role_checker(current_user: User = Depends(get_current_user)) -> User:
        if current_user.role not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Access denied. Required roles: {[r.value for r in allowed_roles]}",
            )
        return current_user
    return _role_checker
