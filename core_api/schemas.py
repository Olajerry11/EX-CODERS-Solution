# =============================================================================
# EX-DIGITAL — Pydantic Request / Response Schemas
# =============================================================================
# Strict validation layer between the HTTP boundary and the ORM.
# =============================================================================

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, EmailStr, Field


# ┌───────────────────────────────────────────────────────────────────────────┐
# │                          AUTHENTICATION                                  │
# └───────────────────────────────────────────────────────────────────────────┘

class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=6)


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    role: str
    user_id: str
    full_name: str


class TokenPayload(BaseModel):
    """Decoded JWT payload."""
    sub: str          # user ID
    role: str
    email: str
    exp: int


# ┌───────────────────────────────────────────────────────────────────────────┐
# │                          USER SCHEMAS                                    │
# └───────────────────────────────────────────────────────────────────────────┘

class UserCreate(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=8)
    full_name: str = Field(..., min_length=2, max_length=255)
    role: str = Field(..., pattern="^(STUDENT|LECTURER|ADMIN)$")
    matriculation_number: Optional[str] = None
    external_system_id: Optional[str] = None
    department: Optional[str] = None


class UserOut(BaseModel):
    id: uuid.UUID
    email: str
    full_name: str
    role: str
    matriculation_number: Optional[str] = None
    external_system_id: Optional[str] = None
    department: Optional[str] = None
    is_active: bool
    created_at: datetime

    class Config:
        from_attributes = True


# ┌───────────────────────────────────────────────────────────────────────────┐
# │                       SESSION MANAGEMENT                                 │
# └───────────────────────────────────────────────────────────────────────────┘

class SessionCreate(BaseModel):
    """Payload to initiate a new lecture session."""
    course_id: uuid.UUID
    location: Optional[str] = None
    notes: Optional[str] = None
    duration_hours: Optional[int] = Field(
        default=2, ge=1, le=8,
        description="Session duration in hours (default: 2)",
    )


class SessionOut(BaseModel):
    id: uuid.UUID
    course_id: uuid.UUID
    lecturer_id: uuid.UUID
    start_time: datetime
    end_time: datetime
    status: str
    location: Optional[str] = None
    notes: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True


class SessionLockResponse(BaseModel):
    id: uuid.UUID
    status: str
    locked_at: datetime
    message: str


# ┌───────────────────────────────────────────────────────────────────────────┐
# │                        RAPID-SCAN ENDPOINT                               │
# └───────────────────────────────────────────────────────────────────────────┘

class RapidScanRequest(BaseModel):
    """
    Accepts a batch of scanned matriculation numbers for a given session.
    """
    session_id: uuid.UUID
    matriculation_numbers: list[str] = Field(
        ..., min_length=1, max_length=500,
        description="List of scanned student matriculation numbers",
    )
    entry_method: Optional[str] = Field(
        default="RAPID_BARCODE",
        pattern="^(RAPID_BARCODE|MANUAL_OVERRIDE|NFC_TAP|BIOMETRIC)$",
    )


class ScanResultItem(BaseModel):
    matriculation_number: str
    status: str  # "SUCCESS" | "DUPLICATE" | "NOT_ENROLLED" | "NOT_FOUND" | "ERROR"
    message: str


class RapidScanResponse(BaseModel):
    session_id: uuid.UUID
    total_submitted: int
    successful: int
    duplicates: int
    failed: int
    results: list[ScanResultItem]


# ┌───────────────────────────────────────────────────────────────────────────┐
# │                        GENERIC RESPONSES                                 │
# └───────────────────────────────────────────────────────────────────────────┘

class MessageResponse(BaseModel):
    message: str
    detail: Optional[str] = None
