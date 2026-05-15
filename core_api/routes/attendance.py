# =============================================================================
# EX-DIGITAL — Attendance Routes (/api/v1/attendance)
# =============================================================================
# Includes the high-performance Rapid-Scan endpoint for batch attendance
# processing and standard attendance query endpoints.
# =============================================================================

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session as DBSession

from database.config import get_db
from database.models import (
    User,
    UserRole,
    Session,
    SessionStatus,
    Enrollment,
    AttendanceLog,
    EntryMethod,
    SyncLog,
    SyncStatus,
)
from ..auth import get_current_user, require_role
from ..schemas import (
    RapidScanRequest,
    RapidScanResponse,
    ScanResultItem,
)

router = APIRouter(prefix="/api/v1/attendance", tags=["Attendance"])


# ── POST /api/v1/attendance/rapid-scan ─────────────────────────────────────

@router.post("/rapid-scan", response_model=RapidScanResponse)
async def rapid_scan(
    body: RapidScanRequest,
    current_user: User = Depends(require_role(UserRole.LECTURER, UserRole.ADMIN)),
    db: DBSession = Depends(get_db),
):
    """
    🚀 **Rapid-Scan Endpoint** — High-speed batch attendance processing.

    Accepts a session ID and a list of scanned matriculation numbers.
    For each number, the endpoint:
      1. Validates the student exists
      2. Validates the student is enrolled in the session's course
      3. Checks for duplicate attendance
      4. Writes the attendance log + creates a PENDING sync log
      5. Returns a per-item result summary

    Designed for barcode / QR scanners pushing batches in real-time.
    """
    # ── 1. Validate session ────────────────────────────────────────────────
    session = db.query(Session).filter(Session.id == body.session_id).first()
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Session not found",
        )

    if session.status == SessionStatus.LOCKED:
        raise HTTPException(
            status_code=status.HTTP_423_LOCKED,
            detail="Session is locked — no further attendance can be recorded",
        )

    # Check if session has expired by time
    now = datetime.now(timezone.utc)
    if now > session.end_time:
        # Auto-lock the expired session
        session.status = SessionStatus.LOCKED
        db.commit()
        raise HTTPException(
            status_code=status.HTTP_423_LOCKED,
            detail="Session has expired and has been auto-locked",
        )

    # ── 2. Pre-fetch enrolled students for this course (single query) ──────
    enrolled_students = (
        db.query(User)
        .join(Enrollment, Enrollment.student_id == User.id)
        .filter(
            Enrollment.course_id == session.course_id,
            Enrollment.is_active == True,
            User.role == UserRole.STUDENT,
            User.is_active == True,
        )
        .all()
    )
    enrolled_map: dict[str, User] = {
        s.matriculation_number: s for s in enrolled_students if s.matriculation_number
    }

    # ── 3. Pre-fetch existing attendance for this session (dedup check) ────
    existing_attendance = (
        db.query(AttendanceLog.student_id)
        .filter(AttendanceLog.session_id == session.id)
        .all()
    )
    already_scanned: set[uuid.UUID] = {row[0] for row in existing_attendance}

    # ── 4. Resolve entry method ────────────────────────────────────────────
    try:
        entry_method = EntryMethod(body.entry_method)
    except ValueError:
        entry_method = EntryMethod.RAPID_BARCODE

    # ── 5. Process each matriculation number ───────────────────────────────
    results: list[ScanResultItem] = []
    successful = 0
    duplicates = 0
    failed = 0

    new_logs: list[AttendanceLog] = []
    new_syncs: list[SyncLog] = []

    for matric in body.matriculation_numbers:
        matric_clean = matric.strip()

        # 5a. Student not found at all
        if matric_clean not in enrolled_map:
            # Check if the student exists but isn't enrolled
            student_exists = (
                db.query(User)
                .filter(
                    User.matriculation_number == matric_clean,
                    User.role == UserRole.STUDENT,
                )
                .first()
            )
            if student_exists:
                results.append(ScanResultItem(
                    matriculation_number=matric_clean,
                    status="NOT_ENROLLED",
                    message=f"Student exists but is not enrolled in this course",
                ))
            else:
                results.append(ScanResultItem(
                    matriculation_number=matric_clean,
                    status="NOT_FOUND",
                    message="No student found with this matriculation number",
                ))
            failed += 1
            continue

        student = enrolled_map[matric_clean]

        # 5b. Duplicate check
        if student.id in already_scanned:
            results.append(ScanResultItem(
                matriculation_number=matric_clean,
                status="DUPLICATE",
                message="Attendance already recorded for this session",
            ))
            duplicates += 1
            continue

        # 5c. Success — create attendance log
        log = AttendanceLog(
            session_id=session.id,
            student_id=student.id,
            scanned_at=now,
            entry_method=entry_method,
            is_valid=True,
        )
        new_logs.append(log)

        # Mark as scanned to catch duplicates within the same batch
        already_scanned.add(student.id)

        results.append(ScanResultItem(
            matriculation_number=matric_clean,
            status="SUCCESS",
            message=f"Attendance recorded for {student.full_name}",
        ))
        successful += 1

    # ── 6. Bulk insert attendance logs ─────────────────────────────────────
    if new_logs:
        db.add_all(new_logs)
        db.flush()  # Get IDs for sync logs

        # Create PENDING sync log for each new attendance record
        for log in new_logs:
            new_syncs.append(SyncLog(
                attendance_log_id=log.id,
                sync_status=SyncStatus.PENDING,
                attempts=0,
            ))
        db.add_all(new_syncs)
        db.commit()

    return RapidScanResponse(
        session_id=session.id,
        total_submitted=len(body.matriculation_numbers),
        successful=successful,
        duplicates=duplicates,
        failed=failed,
        results=results,
    )


# ── GET /api/v1/attendance/session/{session_id} — Session attendance ──────

@router.get("/session/{session_id}")
def get_session_attendance(
    session_id: str,
    current_user: User = Depends(get_current_user),
    db: DBSession = Depends(get_db),
):
    """
    Retrieve all attendance records for a given session.
    """
    session = db.query(Session).filter(Session.id == session_id).first()
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Session not found",
        )

    logs = (
        db.query(AttendanceLog, User)
        .join(User, AttendanceLog.student_id == User.id)
        .filter(AttendanceLog.session_id == session_id)
        .order_by(AttendanceLog.scanned_at.asc())
        .all()
    )

    return {
        "session_id": str(session.id),
        "course_id": str(session.course_id),
        "status": session.status.value,
        "total_records": len(logs),
        "records": [
            {
                "student_id": str(log.student_id),
                "full_name": user.full_name,
                "matriculation_number": user.matriculation_number,
                "scanned_at": log.scanned_at.isoformat(),
                "entry_method": log.entry_method.value,
                "is_valid": log.is_valid,
            }
            for log, user in logs
        ],
    }
