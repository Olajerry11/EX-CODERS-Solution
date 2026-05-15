# =============================================================================
# EX-DIGITAL — Database Seeder
# =============================================================================
# Run:  python -m database.seed
# =============================================================================

import uuid
from datetime import datetime, timedelta, timezone
import bcrypt
from .config import engine, SessionLocal, Base
from .models import (
    User, UserRole, Course, Enrollment, Session, SessionStatus,
    AttendanceLog, EntryMethod, SyncLog, SyncStatus,
)


def _hash(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def seed():
    print("⏳  Dropping & recreating tables …")
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    print("✅  Tables ready.")

    db = SessionLocal()
    try:
        now = datetime.now(timezone.utc)

        # Users
        admin = User(email="admin@exdigital.edu", hashed_password=_hash("Admin@1234"),
                      full_name="System Administrator", role=UserRole.ADMIN,
                      external_system_id="EXT-ADMIN-001", department="ICT Services")
        lec1 = User(email="dr.okonkwo@exdigital.edu", hashed_password=_hash("Lecturer@1234"),
                     full_name="Dr. Chinedu Okonkwo", role=UserRole.LECTURER,
                     external_system_id="EXT-LEC-001", department="Computer Science")
        lec2 = User(email="prof.adeyemi@exdigital.edu", hashed_password=_hash("Lecturer@1234"),
                     full_name="Prof. Funke Adeyemi", role=UserRole.LECTURER,
                     external_system_id="EXT-LEC-002", department="Electrical Engineering")
        students = [
            User(email=f"student{i:02d}@exdigital.edu", hashed_password=_hash("Student@1234"),
                 full_name=f"Student {i:02d}", role=UserRole.STUDENT,
                 matriculation_number=f"EXD/2024/{i:04d}", external_system_id=f"EXT-STU-{i:03d}",
                 department="Computer Science" if i <= 7 else "Electrical Engineering")
            for i in range(1, 11)
        ]
        db.add_all([admin, lec1, lec2, *students]); db.flush()

        # Courses
        csc301 = Course(course_code="CSC301", course_title="Software Engineering",
                        credit_units=3, semester="2025/2026-1", lecturer_id=lec1.id)
        eeg205 = Course(course_code="EEG205", course_title="Circuit Analysis II",
                        credit_units=4, semester="2025/2026-1", lecturer_id=lec2.id)
        csc405 = Course(course_code="CSC405", course_title="Artificial Intelligence",
                        credit_units=3, semester="2025/2026-1", lecturer_id=lec1.id)
        db.add_all([csc301, eeg205, csc405]); db.flush()

        # Enrollments
        enrollments = []
        for s in students[:7]:
            enrollments += [Enrollment(student_id=s.id, course_id=csc301.id),
                            Enrollment(student_id=s.id, course_id=csc405.id)]
        for s in students[7:]:
            enrollments.append(Enrollment(student_id=s.id, course_id=eeg205.id))
        db.add_all(enrollments); db.flush()

        # Sessions
        s_active = Session(course_id=csc301.id, lecturer_id=lec1.id,
                           start_time=now - timedelta(minutes=30),
                           end_time=now + timedelta(hours=1, minutes=30),
                           status=SessionStatus.ACTIVE, location="LT-A Block 3")
        s_locked = Session(course_id=csc301.id, lecturer_id=lec1.id,
                           start_time=now - timedelta(days=1, hours=2),
                           end_time=now - timedelta(days=1),
                           status=SessionStatus.LOCKED, location="LT-A Block 3")
        s_eeg = Session(course_id=eeg205.id, lecturer_id=lec2.id,
                        start_time=now - timedelta(minutes=15),
                        end_time=now + timedelta(hours=1, minutes=45),
                        status=SessionStatus.ACTIVE, location="ENG-Lab 2")
        db.add_all([s_active, s_locked, s_eeg]); db.flush()

        # Attendance Logs
        logs = []
        for s in students[:5]:
            logs.append(AttendanceLog(session_id=s_active.id, student_id=s.id, entry_method=EntryMethod.RAPID_BARCODE))
        for s in students[7:]:
            logs.append(AttendanceLog(session_id=s_eeg.id, student_id=s.id, entry_method=EntryMethod.RAPID_BARCODE))
        logs.append(AttendanceLog(session_id=s_locked.id, student_id=students[0].id, entry_method=EntryMethod.MANUAL_OVERRIDE))
        db.add_all(logs); db.flush()

        # Sync Logs
        for i, log in enumerate(logs):
            status = SyncStatus.SUCCESS if i < 5 else SyncStatus.PENDING
            db.add(SyncLog(attendance_log_id=log.id, sync_status=status,
                           attempts=1 if status == SyncStatus.SUCCESS else 0,
                           last_attempted_at=now if status == SyncStatus.SUCCESS else None,
                           external_reference_id=f"PORTAL-{uuid.uuid4().hex[:8].upper()}" if status == SyncStatus.SUCCESS else None))

        db.commit()
        print("🎉  Database seeding complete!")
    except Exception as exc:
        db.rollback()
        print(f"❌  Seeding failed: {exc}")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    seed()
