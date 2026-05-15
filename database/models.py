# =============================================================================
# EX-DIGITAL — SQLAlchemy ORM Models (Phase 1)
# =============================================================================
# Robust relational schema covering:
#   • Users (Student / Lecturer / Admin with RBAC)
#   • Courses & Enrollments
#   • Sessions (time‑boxed lecture windows)
#   • Attendance Logs (with entry‑method tracking)
#   • Sync Logs (external portal integration audit trail)
#
# All tables use UUID primary keys for distributed‑safe identity and include
# created_at / updated_at audit columns.
# =============================================================================

import uuid
import enum
from datetime import datetime, timezone

from sqlalchemy import (
    Column,
    String,
    Text,
    Boolean,
    Integer,
    DateTime,
    Enum,
    ForeignKey,
    UniqueConstraint,
    Index,
    CheckConstraint,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from .config import Base


# ┌───────────────────────────────────────────────────────────────────────────┐
# │                              ENUMERATIONS                                │
# └───────────────────────────────────────────────────────────────────────────┘

class UserRole(str, enum.Enum):
    """Defines the three principal roles within EX-DIGITAL."""
    STUDENT = "STUDENT"
    LECTURER = "LECTURER"
    ADMIN = "ADMIN"


class SessionStatus(str, enum.Enum):
    """
    Lifecycle states for a lecture session.
      • ACTIVE — currently accepting scans
      • LOCKED — manually or automatically closed; no further scans accepted
    """
    ACTIVE = "ACTIVE"
    LOCKED = "LOCKED"


class EntryMethod(str, enum.Enum):
    """
    How an attendance record was captured.
      • RAPID_BARCODE   — high‑speed barcode / QR scan
      • MANUAL_OVERRIDE — admin or lecturer manual entry
      • NFC_TAP         — near‑field communication tap (future)
      • BIOMETRIC       — fingerprint / face (future)
    """
    RAPID_BARCODE = "RAPID_BARCODE"
    MANUAL_OVERRIDE = "MANUAL_OVERRIDE"
    NFC_TAP = "NFC_TAP"
    BIOMETRIC = "BIOMETRIC"


class SyncStatus(str, enum.Enum):
    """
    Tracks the synchronisation state with the external university portal.
      • PENDING  — queued, not yet attempted
      • SUCCESS  — successfully pushed upstream
      • FAILED   — push attempted but failed; will be retried
      • SKIPPED  — intentionally skipped (e.g., test data)
    """
    PENDING = "PENDING"
    SUCCESS = "SUCCESS"
    FAILED = "FAILED"
    SKIPPED = "SKIPPED"


# ┌───────────────────────────────────────────────────────────────────────────┐
# │                            UTILITY MIXIN                                 │
# └───────────────────────────────────────────────────────────────────────────┘

class TimestampMixin:
    """
    Adds created_at and updated_at audit columns to every model.
    Uses timezone‑aware UTC timestamps.
    """
    created_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    updated_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )


# ┌───────────────────────────────────────────────────────────────────────────┐
# │                             1. USERS TABLE                               │
# └───────────────────────────────────────────────────────────────────────────┘

class User(TimestampMixin, Base):
    """
    Unified user table for Students, Lecturers, and Admins.

    • `matriculation_number` is nullable — only students carry one.
    • `external_system_id` maps this user to the main university portal or
      ERP system for data sync.
    • `hashed_password` stores bcrypt / argon2 output — never plaintext.
    """
    __tablename__ = "users"

    id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    email = Column(String(255), unique=True, nullable=False, index=True)
    hashed_password = Column(Text, nullable=False)
    full_name = Column(String(255), nullable=False)
    role = Column(
        Enum(UserRole, name="user_role_enum", create_constraint=True),
        nullable=False,
        index=True,
    )
    matriculation_number = Column(
        String(50),
        unique=True,
        nullable=True,
        index=True,
        comment="Only applicable for STUDENT role",
    )
    external_system_id = Column(
        String(100),
        unique=True,
        nullable=True,
        index=True,
        comment="Maps to the main university portal / ERP user ID",
    )
    department = Column(String(150), nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)

    # ── Relationships ──────────────────────────────────────────────────────
    enrollments = relationship(
        "Enrollment", back_populates="student", cascade="all, delete-orphan"
    )
    taught_courses = relationship(
        "Course", back_populates="lecturer", cascade="all, delete-orphan"
    )
    led_sessions = relationship(
        "Session", back_populates="lecturer", cascade="all, delete-orphan"
    )
    attendance_logs = relationship(
        "AttendanceLog", back_populates="student", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return (
            f"<User(id={self.id!s}, email={self.email!r}, "
            f"role={self.role.value})>"
        )


# ┌───────────────────────────────────────────────────────────────────────────┐
# │                            2. COURSES TABLE                              │
# └───────────────────────────────────────────────────────────────────────────┘

class Course(TimestampMixin, Base):
    """
    Represents an academic course / module.

    Each course is assigned to exactly one lecturer (the primary instructor).
    """
    __tablename__ = "courses"

    id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    course_code = Column(
        String(20), unique=True, nullable=False, index=True,
        comment="E.g., CSC301, ENG204",
    )
    course_title = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    credit_units = Column(Integer, nullable=False, default=3)
    semester = Column(String(20), nullable=True, comment="E.g., 2025/2026-1")
    lecturer_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    # ── Relationships ──────────────────────────────────────────────────────
    lecturer = relationship("User", back_populates="taught_courses")
    enrollments = relationship(
        "Enrollment", back_populates="course", cascade="all, delete-orphan"
    )
    sessions = relationship(
        "Session", back_populates="course", cascade="all, delete-orphan"
    )

    # ── Constraints ────────────────────────────────────────────────────────
    __table_args__ = (
        CheckConstraint("credit_units > 0", name="ck_courses_credit_positive"),
    )

    def __repr__(self) -> str:
        return (
            f"<Course(id={self.id!s}, code={self.course_code!r}, "
            f"title={self.course_title!r})>"
        )


# ┌───────────────────────────────────────────────────────────────────────────┐
# │                          3. ENROLLMENTS TABLE                            │
# └───────────────────────────────────────────────────────────────────────────┘

class Enrollment(TimestampMixin, Base):
    """
    Junction table linking students to courses.

    A composite unique constraint prevents duplicate enrollment of the same
    student in the same course.
    """
    __tablename__ = "enrollments"

    id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    student_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    course_id = Column(
        UUID(as_uuid=True),
        ForeignKey("courses.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    is_active = Column(Boolean, default=True, nullable=False)

    # ── Relationships ──────────────────────────────────────────────────────
    student = relationship("User", back_populates="enrollments")
    course = relationship("Course", back_populates="enrollments")

    # ── Constraints ────────────────────────────────────────────────────────
    __table_args__ = (
        UniqueConstraint(
            "student_id", "course_id",
            name="uq_enrollment_student_course",
        ),
    )

    def __repr__(self) -> str:
        return (
            f"<Enrollment(student={self.student_id!s}, "
            f"course={self.course_id!s})>"
        )


# ┌───────────────────────────────────────────────────────────────────────────┐
# │                           4. SESSIONS TABLE                              │
# └───────────────────────────────────────────────────────────────────────────┘

class Session(TimestampMixin, Base):
    """
    A time‑boxed lecture / lab window during which attendance can be captured.

    • `status` starts as ACTIVE when a lecturer opens a session.
    • Transitions to LOCKED either manually or after end_time elapses.
    • Once LOCKED, the rapid‑scan endpoint rejects further submissions.
    """
    __tablename__ = "sessions"

    id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    course_id = Column(
        UUID(as_uuid=True),
        ForeignKey("courses.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    lecturer_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    start_time = Column(DateTime(timezone=True), nullable=False)
    end_time = Column(DateTime(timezone=True), nullable=False)
    status = Column(
        Enum(SessionStatus, name="session_status_enum", create_constraint=True),
        nullable=False,
        default=SessionStatus.ACTIVE,
        index=True,
    )
    location = Column(
        String(150), nullable=True,
        comment="Room / venue identifier",
    )
    notes = Column(Text, nullable=True)

    # ── Relationships ──────────────────────────────────────────────────────
    course = relationship("Course", back_populates="sessions")
    lecturer = relationship("User", back_populates="led_sessions")
    attendance_logs = relationship(
        "AttendanceLog", back_populates="session", cascade="all, delete-orphan"
    )

    # ── Constraints ────────────────────────────────────────────────────────
    __table_args__ = (
        CheckConstraint(
            "end_time > start_time",
            name="ck_sessions_end_after_start",
        ),
    )

    def __repr__(self) -> str:
        return (
            f"<Session(id={self.id!s}, course={self.course_id!s}, "
            f"status={self.status.value})>"
        )


# ┌───────────────────────────────────────────────────────────────────────────┐
# │                       5. ATTENDANCE LOGS TABLE                           │
# └───────────────────────────────────────────────────────────────────────────┘

class AttendanceLog(TimestampMixin, Base):
    """
    Records an individual student's attendance at a specific session.

    • `entry_method` captures how the attendance was registered (barcode scan,
      manual override, NFC, etc.).
    • A composite unique constraint prevents duplicate scan entries for the
      same student in the same session.
    • `scanned_at` is the moment the scan actually occurred (may differ from
      `created_at` if there's network latency).
    """
    __tablename__ = "attendance_logs"

    id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    session_id = Column(
        UUID(as_uuid=True),
        ForeignKey("sessions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    student_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    scanned_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    entry_method = Column(
        Enum(EntryMethod, name="entry_method_enum", create_constraint=True),
        nullable=False,
        default=EntryMethod.RAPID_BARCODE,
    )
    is_valid = Column(
        Boolean, default=True, nullable=False,
        comment="False if later invalidated by an admin",
    )

    # ── Relationships ──────────────────────────────────────────────────────
    session = relationship("Session", back_populates="attendance_logs")
    student = relationship("User", back_populates="attendance_logs")
    sync_log = relationship(
        "SyncLog", back_populates="attendance_log", uselist=False,
        cascade="all, delete-orphan",
    )

    # ── Constraints ────────────────────────────────────────────────────────
    __table_args__ = (
        UniqueConstraint(
            "session_id", "student_id",
            name="uq_attendance_session_student",
        ),
        Index(
            "ix_attendance_session_student",
            "session_id", "student_id",
        ),
    )

    def __repr__(self) -> str:
        return (
            f"<AttendanceLog(session={self.session_id!s}, "
            f"student={self.student_id!s}, method={self.entry_method.value})>"
        )


# ┌───────────────────────────────────────────────────────────────────────────┐
# │                         6. SYNC LOGS TABLE                               │
# └───────────────────────────────────────────────────────────────────────────┘

class SyncLog(TimestampMixin, Base):
    """
    Integration audit trail — tracks whether each attendance record has been
    successfully pushed to the external university portal / ERP.

    • One SyncLog per AttendanceLog (one‑to‑one).
    • `sync_status` starts as PENDING; the Flask integration gateway
      processes the queue and updates to SUCCESS / FAILED.
    • `attempts` counts how many times a push was tried (for retry logic).
    • `external_reference_id` stores the upstream system's confirmation ID
      once a push succeeds.
    • `last_error` captures the most recent failure reason for debugging.
    """
    __tablename__ = "sync_logs"

    id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    attendance_log_id = Column(
        UUID(as_uuid=True),
        ForeignKey("attendance_logs.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )
    sync_status = Column(
        Enum(SyncStatus, name="sync_status_enum", create_constraint=True),
        nullable=False,
        default=SyncStatus.PENDING,
        index=True,
    )
    attempts = Column(Integer, default=0, nullable=False)
    last_attempted_at = Column(DateTime(timezone=True), nullable=True)
    last_error = Column(Text, nullable=True)
    external_reference_id = Column(
        String(200), nullable=True,
        comment="Confirmation ID returned by the external system",
    )

    # ── Relationships ──────────────────────────────────────────────────────
    attendance_log = relationship("AttendanceLog", back_populates="sync_log")

    def __repr__(self) -> str:
        return (
            f"<SyncLog(attendance={self.attendance_log_id!s}, "
            f"status={self.sync_status.value}, attempts={self.attempts})>"
        )
