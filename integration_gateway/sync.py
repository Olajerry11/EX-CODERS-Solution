# =============================================================================
# EX-DIGITAL — External Sync Service
# =============================================================================
# Background function / callable route that processes unsynced attendance
# records from the Sync_Logs table and formats them into JSON payloads
# ready to be pushed to an external ERP or university portal.
#
# Endpoints:
#   POST /gateway/v1/sync/trigger     — Manually trigger a sync batch
#   GET  /gateway/v1/sync/status      — View sync queue statistics
#   GET  /gateway/v1/sync/history     — View recent sync attempts
# =============================================================================

import uuid
import logging
from datetime import datetime, timezone

import httpx
from flask import Blueprint, jsonify, request

from sqlalchemy import func
from sqlalchemy.orm import Session as DBSession

from database.config import SessionLocal
from database.models import (
    User,
    Course,
    Session,
    AttendanceLog,
    SyncLog,
    SyncStatus,
)
from .auth import require_api_key
from .config import GatewayConfig

sync_bp = Blueprint("sync", __name__, url_prefix="/gateway/v1/sync")

logger = logging.getLogger("exdigital.sync")


def _get_db() -> DBSession:
    return SessionLocal()


# ┌───────────────────────────────────────────────────────────────────────────┐
# │                   CORE SYNC LOGIC (Background Task)                      │
# └───────────────────────────────────────────────────────────────────────────┘

def _build_sync_payload(
    sync_log: SyncLog,
    attendance: AttendanceLog,
    student: User,
    course: Course,
    session: Session,
) -> dict:
    """
    Format a single attendance record into the JSON payload expected
    by the external university portal / ERP system.
    """
    return {
        "external_reference": str(uuid.uuid4()),
        "source_system": "EX-DIGITAL",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "data": {
            "student": {
                "external_system_id": student.external_system_id,
                "matriculation_number": student.matriculation_number,
                "full_name": student.full_name,
                "department": student.department,
            },
            "course": {
                "course_code": course.course_code,
                "course_title": course.course_title,
                "semester": course.semester,
            },
            "session": {
                "start_time": session.start_time.isoformat(),
                "end_time": session.end_time.isoformat(),
                "location": session.location,
                "status": session.status.value,
            },
            "attendance": {
                "scanned_at": attendance.scanned_at.isoformat(),
                "entry_method": attendance.entry_method.value,
                "is_valid": attendance.is_valid,
            },
        },
    }


def _push_to_external_portal(payload: dict) -> tuple[bool, str]:
    """
    Attempt to push a formatted payload to the external portal.

    Returns (success: bool, message: str).
    In a real deployment, this sends an HTTP POST to the portal's API.
    For development, it simulates the push.
    """
    portal_url = GatewayConfig.EXTERNAL_PORTAL_BASE_URL
    api_key = GatewayConfig.EXTERNAL_PORTAL_API_KEY

    # ── If no real portal is configured, simulate success ──────────────
    if "portal.university.edu" in portal_url or api_key == "your_external_api_key_here":
        logger.info(
            "🔧 DEV MODE: Simulating external push for ref %s",
            payload.get("external_reference", "unknown"),
        )
        return True, payload["external_reference"]

    # ── Production: POST to external portal ────────────────────────────
    try:
        with httpx.Client(timeout=30.0) as client:
            response = client.post(
                f"{portal_url}/attendance/sync",
                json=payload,
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                    "X-Source-System": "EX-DIGITAL",
                },
            )

        if response.status_code in (200, 201):
            ref_id = response.json().get(
                "reference_id", payload["external_reference"]
            )
            return True, ref_id
        else:
            return False, f"HTTP {response.status_code}: {response.text[:200]}"

    except httpx.TimeoutException:
        return False, "Connection timed out"
    except httpx.RequestError as exc:
        return False, f"Request error: {str(exc)[:200]}"


def process_sync_batch(batch_size: int | None = None) -> dict:
    """
    Core sync function — grabs unsynced (PENDING / FAILED) records from
    Sync_Logs, formats them, and pushes to the external portal.

    Returns a summary dict of the sync operation.
    """
    batch_size = batch_size or GatewayConfig.SYNC_BATCH_SIZE
    max_retries = GatewayConfig.SYNC_MAX_RETRIES

    db = _get_db()
    now = datetime.now(timezone.utc)

    try:
        # Fetch PENDING and retryable FAILED records
        pending_records = (
            db.query(SyncLog)
            .filter(
                SyncLog.sync_status.in_([SyncStatus.PENDING, SyncStatus.FAILED]),
                SyncLog.attempts < max_retries,
            )
            .order_by(SyncLog.created_at.asc())
            .limit(batch_size)
            .all()
        )

        if not pending_records:
            return {
                "status": "idle",
                "message": "No records to sync",
                "processed": 0,
                "succeeded": 0,
                "failed": 0,
                "timestamp": now.isoformat(),
            }

        succeeded = 0
        failed = 0
        errors = []

        for sync_log in pending_records:
            # Load related records
            attendance = (
                db.query(AttendanceLog)
                .filter(AttendanceLog.id == sync_log.attendance_log_id)
                .first()
            )
            if not attendance:
                sync_log.sync_status = SyncStatus.SKIPPED
                sync_log.last_error = "Attendance record not found"
                sync_log.last_attempted_at = now
                continue

            student = db.query(User).filter(User.id == attendance.student_id).first()
            session = db.query(Session).filter(Session.id == attendance.session_id).first()
            course = db.query(Course).filter(Course.id == session.course_id).first() if session else None

            if not all([student, session, course]):
                sync_log.sync_status = SyncStatus.SKIPPED
                sync_log.last_error = "Related record(s) missing"
                sync_log.last_attempted_at = now
                continue

            # Build payload and push
            payload = _build_sync_payload(sync_log, attendance, student, course, session)
            success, ref_or_error = _push_to_external_portal(payload)

            sync_log.attempts += 1
            sync_log.last_attempted_at = now

            if success:
                sync_log.sync_status = SyncStatus.SUCCESS
                sync_log.external_reference_id = ref_or_error
                sync_log.last_error = None
                succeeded += 1
            else:
                sync_log.sync_status = SyncStatus.FAILED
                sync_log.last_error = ref_or_error
                failed += 1
                errors.append({
                    "sync_log_id": str(sync_log.id),
                    "error": ref_or_error,
                })

        db.commit()

        return {
            "status": "completed",
            "processed": len(pending_records),
            "succeeded": succeeded,
            "failed": failed,
            "errors": errors[:10],  # Cap error list
            "timestamp": now.isoformat(),
        }

    except Exception as exc:
        db.rollback()
        logger.exception("Sync batch failed")
        return {
            "status": "error",
            "message": str(exc),
            "timestamp": now.isoformat(),
        }
    finally:
        db.close()


# ┌───────────────────────────────────────────────────────────────────────────┐
# │                          FLASK ROUTES                                    │
# └───────────────────────────────────────────────────────────────────────────┘

# ── POST /gateway/v1/sync/trigger — Manually trigger sync ──────────────────

@sync_bp.route("/trigger", methods=["POST"])
@require_api_key
def trigger_sync():
    """
    Manually trigger a sync batch. Processes unsynced records and pushes
    them to the external portal.

    Optional JSON body: { "batch_size": 50 }
    """
    body = request.get_json(silent=True) or {}
    batch_size = body.get("batch_size", GatewayConfig.SYNC_BATCH_SIZE)

    result = process_sync_batch(batch_size=batch_size)
    status_code = 200 if result["status"] != "error" else 500

    return jsonify(result), status_code


# ── GET /gateway/v1/sync/status — Queue statistics ─────────────────────────

@sync_bp.route("/status", methods=["GET"])
@require_api_key
def sync_status():
    """
    View current sync queue statistics:
    pending, failed, succeeded, skipped counts.
    """
    db = _get_db()
    try:
        stats = (
            db.query(
                SyncLog.sync_status,
                func.count(SyncLog.id).label("count"),
            )
            .group_by(SyncLog.sync_status)
            .all()
        )

        counts = {s.value: 0 for s in SyncStatus}
        for status_val, count in stats:
            counts[status_val.value] = count

        total = sum(counts.values())

        return jsonify({
            "total_records": total,
            "breakdown": counts,
            "sync_health": (
                "healthy"
                if counts.get("FAILED", 0) == 0
                else "degraded"
                if counts["FAILED"] < counts.get("SUCCESS", 1)
                else "critical"
            ),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }), 200

    finally:
        db.close()


# ── GET /gateway/v1/sync/history — Recent sync attempts ────────────────────

@sync_bp.route("/history", methods=["GET"])
@require_api_key
def sync_history():
    """
    View the most recent sync attempts with their results.

    Query params:
      • limit (int, default 20) — number of records to return
      • status (str, optional) — filter by sync status
    """
    db = _get_db()
    try:
        limit = request.args.get("limit", 20, type=int)
        status_filter = request.args.get("status")

        query = db.query(SyncLog)

        if status_filter:
            try:
                query = query.filter(
                    SyncLog.sync_status == SyncStatus(status_filter.upper())
                )
            except ValueError:
                return jsonify({"error": f"Invalid status: {status_filter}"}), 400

        records = (
            query.order_by(SyncLog.last_attempted_at.desc().nullslast())
            .limit(limit)
            .all()
        )

        return jsonify({
            "count": len(records),
            "records": [
                {
                    "id": str(r.id),
                    "attendance_log_id": str(r.attendance_log_id),
                    "sync_status": r.sync_status.value,
                    "attempts": r.attempts,
                    "last_attempted_at": (
                        r.last_attempted_at.isoformat()
                        if r.last_attempted_at
                        else None
                    ),
                    "external_reference_id": r.external_reference_id,
                    "last_error": r.last_error,
                }
                for r in records
            ],
        }), 200

    finally:
        db.close()
