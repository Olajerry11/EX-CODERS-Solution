# =============================================================================
# EX-DIGITAL — Data Export Blueprint
# =============================================================================
# Secure webhook/endpoint that external systems (university portal, ERP)
# can call to fetch compiled attendance data.
#
# Endpoints:
#   GET  /gateway/v1/export/student/<ext_id>/attendance
#   GET  /gateway/v1/export/course/<course_code>/attendance
#   GET  /gateway/v1/export/course/<course_code>/summary
# =============================================================================

from flask import Blueprint, jsonify, request

from sqlalchemy import func, case
from sqlalchemy.orm import Session as DBSession

from database.config import SessionLocal
from database.models import (
    User,
    UserRole,
    Course,
    Enrollment,
    Session,
    SessionStatus,
    AttendanceLog,
)
from .auth import require_api_key

export_bp = Blueprint("export", __name__, url_prefix="/gateway/v1/export")


def _get_db() -> DBSession:
    """Create a scoped database session for Flask request context."""
    return SessionLocal()


# ── GET /gateway/v1/export/student/<external_id>/attendance ────────────────

@export_bp.route("/student/<external_id>/attendance", methods=["GET"])
@require_api_key
def get_student_attendance(external_id: str):
    """
    Fetch compiled attendance percentages for a specific student,
    identified by their `external_system_id` (university portal ID).

    Query params:
      • semester (optional) — filter by semester string
      • course_code (optional) — filter to a specific course

    Returns per-course attendance percentages and overall average.
    """
    db = _get_db()
    try:
        # Resolve student
        student = (
            db.query(User)
            .filter(
                User.external_system_id == external_id,
                User.role == UserRole.STUDENT,
            )
            .first()
        )
        if not student:
            return jsonify({
                "error": "Student not found",
                "detail": f"No student with external_system_id: {external_id}",
            }), 404

        # Build enrollment query
        enrollment_query = (
            db.query(Enrollment, Course)
            .join(Course, Enrollment.course_id == Course.id)
            .filter(
                Enrollment.student_id == student.id,
                Enrollment.is_active == True,
            )
        )

        semester = request.args.get("semester")
        if semester:
            enrollment_query = enrollment_query.filter(Course.semester == semester)

        course_code = request.args.get("course_code")
        if course_code:
            enrollment_query = enrollment_query.filter(
                Course.course_code == course_code.upper()
            )

        enrollments = enrollment_query.all()

        if not enrollments:
            return jsonify({
                "student": {
                    "external_id": external_id,
                    "full_name": student.full_name,
                    "matriculation_number": student.matriculation_number,
                },
                "courses": [],
                "overall_percentage": 0.0,
                "message": "No active enrollments found",
            }), 200

        # Calculate per-course attendance
        course_results = []
        total_sessions_all = 0
        total_attended_all = 0

        for enrollment, course in enrollments:
            # Count total LOCKED sessions (completed)
            total_sessions = (
                db.query(func.count(Session.id))
                .filter(
                    Session.course_id == course.id,
                    Session.status == SessionStatus.LOCKED,
                )
                .scalar()
            )

            # Count sessions this student attended
            attended = (
                db.query(func.count(AttendanceLog.id))
                .join(Session, AttendanceLog.session_id == Session.id)
                .filter(
                    Session.course_id == course.id,
                    AttendanceLog.student_id == student.id,
                    AttendanceLog.is_valid == True,
                )
                .scalar()
            )

            percentage = (
                round((attended / total_sessions) * 100, 2)
                if total_sessions > 0
                else 0.0
            )

            course_results.append({
                "course_code": course.course_code,
                "course_title": course.course_title,
                "semester": course.semester,
                "total_sessions": total_sessions,
                "sessions_attended": attended,
                "attendance_percentage": percentage,
            })

            total_sessions_all += total_sessions
            total_attended_all += attended

        overall = (
            round((total_attended_all / total_sessions_all) * 100, 2)
            if total_sessions_all > 0
            else 0.0
        )

        return jsonify({
            "student": {
                "external_id": external_id,
                "full_name": student.full_name,
                "matriculation_number": student.matriculation_number,
                "department": student.department,
            },
            "courses": course_results,
            "overall_percentage": overall,
            "total_sessions": total_sessions_all,
            "total_attended": total_attended_all,
        }), 200

    finally:
        db.close()


# ── GET /gateway/v1/export/course/<course_code>/attendance ─────────────────

@export_bp.route("/course/<course_code>/attendance", methods=["GET"])
@require_api_key
def get_course_attendance(course_code: str):
    """
    Fetch attendance records for all students in a specific course.

    Query params:
      • semester (optional) — filter by semester

    Returns a list of students with their attendance percentages.
    """
    db = _get_db()
    try:
        query = db.query(Course).filter(
            Course.course_code == course_code.upper()
        )
        semester = request.args.get("semester")
        if semester:
            query = query.filter(Course.semester == semester)

        course = query.first()
        if not course:
            return jsonify({
                "error": "Course not found",
                "detail": f"No course with code: {course_code.upper()}",
            }), 404

        # Total locked sessions
        total_sessions = (
            db.query(func.count(Session.id))
            .filter(
                Session.course_id == course.id,
                Session.status == SessionStatus.LOCKED,
            )
            .scalar()
        )

        # Get enrolled students with their attendance counts
        enrolled_students = (
            db.query(User, Enrollment)
            .join(Enrollment, Enrollment.student_id == User.id)
            .filter(
                Enrollment.course_id == course.id,
                Enrollment.is_active == True,
            )
            .all()
        )

        student_results = []
        for student, enrollment in enrolled_students:
            attended = (
                db.query(func.count(AttendanceLog.id))
                .join(Session, AttendanceLog.session_id == Session.id)
                .filter(
                    Session.course_id == course.id,
                    AttendanceLog.student_id == student.id,
                    AttendanceLog.is_valid == True,
                )
                .scalar()
            )

            percentage = (
                round((attended / total_sessions) * 100, 2)
                if total_sessions > 0
                else 0.0
            )

            student_results.append({
                "external_system_id": student.external_system_id,
                "matriculation_number": student.matriculation_number,
                "full_name": student.full_name,
                "department": student.department,
                "sessions_attended": attended,
                "attendance_percentage": percentage,
            })

        # Sort by percentage descending
        student_results.sort(
            key=lambda x: x["attendance_percentage"], reverse=True
        )

        return jsonify({
            "course": {
                "course_code": course.course_code,
                "course_title": course.course_title,
                "semester": course.semester,
                "total_locked_sessions": total_sessions,
            },
            "total_students": len(student_results),
            "students": student_results,
        }), 200

    finally:
        db.close()


# ── GET /gateway/v1/export/course/<course_code>/summary ────────────────────

@export_bp.route("/course/<course_code>/summary", methods=["GET"])
@require_api_key
def get_course_summary(course_code: str):
    """
    High-level attendance summary for a course:
    average attendance, at-risk students (< 75%), etc.
    """
    db = _get_db()
    try:
        course = (
            db.query(Course)
            .filter(Course.course_code == course_code.upper())
            .first()
        )
        if not course:
            return jsonify({"error": "Course not found"}), 404

        total_sessions = (
            db.query(func.count(Session.id))
            .filter(
                Session.course_id == course.id,
                Session.status == SessionStatus.LOCKED,
            )
            .scalar()
        )

        enrolled = (
            db.query(User)
            .join(Enrollment, Enrollment.student_id == User.id)
            .filter(
                Enrollment.course_id == course.id,
                Enrollment.is_active == True,
            )
            .all()
        )

        at_risk = []
        percentages = []

        for student in enrolled:
            attended = (
                db.query(func.count(AttendanceLog.id))
                .join(Session, AttendanceLog.session_id == Session.id)
                .filter(
                    Session.course_id == course.id,
                    AttendanceLog.student_id == student.id,
                    AttendanceLog.is_valid == True,
                )
                .scalar()
            )
            pct = (
                round((attended / total_sessions) * 100, 2)
                if total_sessions > 0
                else 0.0
            )
            percentages.append(pct)

            if pct < 75.0:
                at_risk.append({
                    "external_system_id": student.external_system_id,
                    "matriculation_number": student.matriculation_number,
                    "full_name": student.full_name,
                    "attendance_percentage": pct,
                })

        avg_attendance = (
            round(sum(percentages) / len(percentages), 2)
            if percentages
            else 0.0
        )

        return jsonify({
            "course_code": course.course_code,
            "course_title": course.course_title,
            "semester": course.semester,
            "total_locked_sessions": total_sessions,
            "total_enrolled": len(enrolled),
            "average_attendance_percentage": avg_attendance,
            "at_risk_count": len(at_risk),
            "at_risk_students": at_risk,
        }), 200

    finally:
        db.close()
