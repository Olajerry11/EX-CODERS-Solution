# =============================================================================
# EX-DIGITAL — Session Management Routes (/api/v1/sessions)
# =============================================================================
# Endpoints for lecturers to initiate, view, and lock lecture sessions.
# =============================================================================

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session as DBSession

from database.config import get_db
from database.models import (
    User,
    UserRole,
    Course,
    Session,
    SessionStatus,
    AttendanceLog,
)
from ..auth import get_current_user, require_role
from ..schemas import SessionCreate, SessionOut, SessionLockResponse, MessageResponse

router = APIRouter(prefix="/api/v1/sessions", tags=["Session Management"])


# ── POST /api/v1/sessions — Initiate a new session ────────────────────────

@router.post(
    "/",
    response_model=SessionOut,
    status_code=status.HTTP_201_CREATED,
)
def create_session(
    body: SessionCreate,
    current_user: User = Depends(require_role(UserRole.LECTURER, UserRole.ADMIN)),
    db: DBSession = Depends(get_db),
):
    """
    Initiate a new lecture session.

    - Only LECTURER or ADMIN roles can create sessions.
    - The lecturer must own (or be admin of) the course.
    - Default duration is 2 hours; configurable via `duration_hours`.
    """
    # Validate course exists
    course = db.query(Course).filter(Course.id == body.course_id).first()
    if not course:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Course not found",
        )

    # Lecturers can only open sessions for their own courses
    if (
        current_user.role == UserRole.LECTURER
        and course.lecturer_id != current_user.id
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You are not the assigned lecturer for this course",
        )

    # Prevent overlapping ACTIVE sessions for the same course
    active_exists = (
        db.query(Session)
        .filter(
            Session.course_id == body.course_id,
            Session.status == SessionStatus.ACTIVE,
        )
        .first()
    )
    if active_exists:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"An active session already exists for this course (id: {active_exists.id})",
        )

    now = datetime.now(timezone.utc)
    duration = body.duration_hours or 2
    new_session = Session(
        course_id=body.course_id,
        lecturer_id=current_user.id,
        start_time=now,
        end_time=now + timedelta(hours=duration),
        status=SessionStatus.ACTIVE,
        location=body.location,
        notes=body.notes,
    )
    db.add(new_session)
    db.commit()
    db.refresh(new_session)
    return new_session


# ── GET /api/v1/sessions — List sessions ──────────────────────────────────

@router.get("/", response_model=list[SessionOut])
def list_sessions(
    course_id: str | None = None,
    status_filter: str | None = None,
    limit: int = 50,
    current_user: User = Depends(get_current_user),
    db: DBSession = Depends(get_db),
):
    """
    List sessions. Optionally filter by course_id and/or status.
    """
    query = db.query(Session)

    if course_id:
        query = query.filter(Session.course_id == course_id)
    if status_filter:
        query = query.filter(Session.status == status_filter)

    # Lecturers see only their own sessions
    if current_user.role == UserRole.LECTURER:
        query = query.filter(Session.lecturer_id == current_user.id)

    return query.order_by(Session.start_time.desc()).limit(limit).all()


# ── GET /api/v1/sessions/{session_id} — Get session details ───────────────

@router.get("/{session_id}", response_model=SessionOut)
def get_session(
    session_id: str,
    current_user: User = Depends(get_current_user),
    db: DBSession = Depends(get_db),
):
    """Retrieve a single session by ID."""
    session = db.query(Session).filter(Session.id == session_id).first()
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Session not found",
        )
    return session


# ── PATCH /api/v1/sessions/{session_id}/lock — Lock a session ─────────────

@router.patch("/{session_id}/lock", response_model=SessionLockResponse)
def lock_session(
    session_id: str,
    current_user: User = Depends(require_role(UserRole.LECTURER, UserRole.ADMIN)),
    db: DBSession = Depends(get_db),
):
    """
    Manually lock a session. Once locked, no further attendance scans
    are accepted for this session.
    """
    session = db.query(Session).filter(Session.id == session_id).first()
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Session not found",
        )

    # Lecturers can only lock their own sessions
    if (
        current_user.role == UserRole.LECTURER
        and session.lecturer_id != current_user.id
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only lock your own sessions",
        )

    if session.status == SessionStatus.LOCKED:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Session is already locked",
        )

    now = datetime.now(timezone.utc)
    session.status = SessionStatus.LOCKED
    session.end_time = now  # Snap end_time to actual lock time
    db.commit()
    db.refresh(session)

    # Count attendance for the summary
    attendance_count = (
        db.query(AttendanceLog)
        .filter(AttendanceLog.session_id == session.id)
        .count()
    )

    return SessionLockResponse(
        id=session.id,
        status=session.status.value,
        locked_at=now,
        message=f"Session locked successfully. {attendance_count} attendance records captured.",
    )
