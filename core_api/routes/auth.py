# =============================================================================
# EX-DIGITAL — Auth Routes (/api/v1/auth)
# =============================================================================

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session as DBSession

from database.config import get_db
from database.models import User, UserRole
from ..auth import verify_password, hash_password, create_access_token, get_current_user
from ..schemas import LoginRequest, TokenResponse, UserCreate, UserOut, MessageResponse

router = APIRouter(prefix="/api/v1/auth", tags=["Authentication"])


# ── POST /api/v1/auth/login ────────────────────────────────────────────────

@router.post("/login", response_model=TokenResponse)
def login(body: LoginRequest, db: DBSession = Depends(get_db)):
    """
    Authenticate a user with email + password and return a signed JWT.
    """
    user = db.query(User).filter(User.email == body.email).first()
    if not user or not verify_password(body.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is deactivated",
        )

    token = create_access_token(
        user_id=str(user.id),
        email=user.email,
        role=user.role.value,
    )
    return TokenResponse(
        access_token=token,
        role=user.role.value,
        user_id=str(user.id),
        full_name=user.full_name,
    )


# ── POST /api/v1/auth/register ─────────────────────────────────────────────

@router.post(
    "/register",
    response_model=UserOut,
    status_code=status.HTTP_201_CREATED,
)
def register(body: UserCreate, db: DBSession = Depends(get_db)):
    """
    Register a new user account.
    Only Admins should call this in production (enforced at gateway level).
    """
    # Check duplicate email
    if db.query(User).filter(User.email == body.email).first():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Email already registered",
        )

    # Check duplicate matriculation number (students only)
    if body.matriculation_number:
        if db.query(User).filter(
            User.matriculation_number == body.matriculation_number
        ).first():
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Matriculation number already registered",
            )

    new_user = User(
        email=body.email,
        hashed_password=hash_password(body.password),
        full_name=body.full_name,
        role=UserRole(body.role),
        matriculation_number=body.matriculation_number,
        external_system_id=body.external_system_id,
        department=body.department,
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    return new_user


# ── GET /api/v1/auth/me ────────────────────────────────────────────────────

@router.get("/me", response_model=UserOut)
def get_profile(current_user: User = Depends(get_current_user)):
    """Return the authenticated user's profile."""
    return current_user
