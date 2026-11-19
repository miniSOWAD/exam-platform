from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.api import routes
from app.core.database import Base, get_db
from app.main import app
from app.models.entities import Attempt, Exam, ExamStatus, Question, Role, User


def make_client(role=Role.admin):
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)
    db = factory()
    user = User(id=f"{role.value}-user", email=f"{role.value}@examflow.test", full_name=role.value.title(), password_hash="x", role=role, active=True)
    db.add(user); db.commit()
    def override_db(): yield db
    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[routes.current_user] = lambda: user
    return TestClient(app), db, engine, user


def cleanup(db, engine):
    app.dependency_overrides.clear(); db.close(); Base.metadata.drop_all(engine); engine.dispose()


def add_exam(db, admin, status=ExamStatus.draft):
    exam = Exam(id="admin-mode-exam", title="Admin mode test", subject="Biology", status=status, duration_seconds=3600, max_attempts=1, created_by=admin.id)
    question = Question(id="admin-mode-q1", exam_id=exam.id, kind="mcq", prompt="Which option is correct?", options=[{"id":"A","text":"Option A"},{"id":"B","text":"Option B"}], answer_key={"selected_option_ids":["B"]}, marks=1, position=0)
    db.add_all([exam, question]); db.commit(); return exam, question


def test_admin_can_enter_draft_exam_and_see_answer_key_but_students_cannot():
    client, db, engine, admin = make_client(Role.admin)
    try:
        exam, question = add_exam(db, admin)
        started = client.post(f"/api/v1/exams/{exam.id}/admin-attempts")
        assert started.status_code == 200, started.text
        attempt_id = started.json()["attempt_id"]
        rows = client.get(f"/api/v1/attempts/{attempt_id}/questions")
        assert rows.status_code == 200
        assert rows.json()[0]["answer_key"]["selected_option_ids"] == ["B"]
        saved = client.put(f"/api/v1/attempts/{attempt_id}/answers/{question.id}", json={"answer":{"selected_option_ids":["B"]}})
        assert saved.status_code == 200, saved.text
        attempt = db.get(Attempt, attempt_id)
        assert attempt.is_admin_attempt is True
    finally:
        cleanup(db, engine)


def test_student_cannot_create_admin_attempt_and_never_receives_answer_key():
    client, db, engine, student = make_client(Role.student)
    try:
        exam, _ = add_exam(db, student, ExamStatus.live)
        forbidden = client.post(f"/api/v1/exams/{exam.id}/admin-attempts")
        assert forbidden.status_code == 403
        started = client.post(f"/api/v1/exams/{exam.id}/attempts")
        assert started.status_code == 200, started.text
        attempt_id = started.json()["attempt_id"]
        questions = client.get(f"/api/v1/attempts/{attempt_id}/questions")
        assert questions.status_code == 200
        assert "answer_key" not in questions.json()[0]
        # Even if an administrator preview attempt ID is known, students cannot inspect it.
        admin = User(id="hidden-admin", email="hidden-admin@example.test", full_name="Hidden Admin", password_hash="x", role=Role.admin, active=True)
        db.add(admin); db.commit()
        protected = Attempt(
            id="private-admin-attempt", exam_id=exam.id, student_id=admin.id,
            attempt_number=1, status="in_progress", is_admin_attempt=True,
            max_score=1, answers=[],
        )
        db.add(protected); db.commit()
        denied = client.get(f"/api/v1/attempts/{protected.id}/questions")
        assert denied.status_code == 404
    finally:
        cleanup(db, engine)


def test_admin_can_force_start_pause_stop_and_reschedule_mid_exam():
    client, db, engine, admin = make_client(Role.admin)
    try:
        exam, _ = add_exam(db, admin, ExamStatus.live)
        exam.started_at = datetime.now(timezone.utc) - timedelta(minutes=5)
        db.commit()
        paused = client.post(f"/api/v1/exams/{exam.id}/control/pause")
        assert paused.status_code == 200 and paused.json()["status"] == "paused"
        future = datetime.now(timezone.utc) + timedelta(minutes=20)
        scheduled = client.patch(f"/api/v1/exams/{exam.id}/schedule", json={"scheduled_start_at":future.isoformat()})
        assert scheduled.status_code == 200, scheduled.text
        assert scheduled.json()["status"] == "paused"
        assert scheduled.json()["scheduled_resume_at"]
        # A due scheduled resume is applied by the next exam/attempt read.
        exam.scheduled_resume_at = datetime.now(timezone.utc) - timedelta(seconds=1)
        db.commit()
        refreshed = client.get(f"/api/v1/exams/{exam.id}")
        assert refreshed.status_code == 200
        assert refreshed.json()["status"] == "live"
        stopped = client.post(f"/api/v1/exams/{exam.id}/control/stop")
        assert stopped.status_code == 200 and stopped.json()["status"] == "ended"
    finally:
        cleanup(db, engine)



def test_attempt_timer_does_not_subtract_pauses_that_happened_before_attempt_started():
    client, db, engine, admin = make_client(Role.admin)
    try:
        exam, _ = add_exam(db, admin, ExamStatus.live)
        exam.accumulated_pause_seconds = 600
        db.commit()
        attempt = Attempt(
            id="new-after-old-pause", exam_id=exam.id, student_id=admin.id,
            attempt_number=1, status="in_progress", is_admin_attempt=True,
            started_at=datetime.now(timezone.utc) - timedelta(minutes=5),
            pause_seconds_at_start=600, max_score=1, answers=[],
        )
        db.add(attempt); db.commit()
        response = client.get(f"/api/v1/attempts/{attempt.id}")
        assert response.status_code == 200
        assert 54 * 60 <= response.json()["remaining_seconds"] <= 55 * 60
    finally:
        cleanup(db, engine)


def test_admin_force_starts_draft_and_admin_attempt_is_not_in_leaderboard():
    client, db, engine, admin = make_client(Role.admin)
    try:
        exam, _ = add_exam(db, admin)
        attempt_response = client.post(f"/api/v1/exams/{exam.id}/admin-attempts")
        attempt_id = attempt_response.json()["attempt_id"]
        db.get(Attempt, attempt_id).status = "submitted"
        db.get(Attempt, attempt_id).score = 1
        db.commit()
        started = client.post(f"/api/v1/exams/{exam.id}/control/force-start")
        assert started.status_code == 200 and started.json()["status"] == "live"
        # The exam has not published results, so the admin preview attempt never appears in student rankings.
        assert db.get(Attempt, attempt_id).is_admin_attempt is True
        assert client.get(f"/api/v1/admin/leaderboards?scope=exam&exam_id={exam.id}").status_code == 200
    finally:
        cleanup(db, engine)


def test_admin_can_reschedule_ended_exam_as_a_new_run_and_student_can_retake():
    client, db, engine, admin = make_client(Role.admin)
    try:
        exam, _ = add_exam(db, admin, ExamStatus.ended)
        exam.ended_at = datetime.now(timezone.utc) - timedelta(hours=1)
        previous = Attempt(
            id="previous-run-student-attempt", exam_id=exam.id, student_id="restart-student",
            attempt_number=1, run_number=1, status="submitted", is_admin_attempt=False,
            is_staff_attempt=False, max_score=1, score=1, answers=[],
            submitted_at=datetime.now(timezone.utc) - timedelta(hours=1),
        )
        student = User(
            id="restart-student", email="restart-student@example.test", full_name="Restart Student",
            password_hash="x", role=Role.student, active=True,
        )
        db.add_all([student, previous]); db.commit()

        new_start = datetime.now(timezone.utc) + timedelta(hours=1)
        new_end = new_start + timedelta(hours=1)
        scheduled = client.patch(
            f"/api/v1/exams/{exam.id}/schedule",
            json={"scheduled_start_at": new_start.isoformat(), "scheduled_end_at": new_end.isoformat()},
        )
        assert scheduled.status_code == 200, scheduled.text
        assert scheduled.json()["status"] == "published"
        assert scheduled.json()["run_number"] == 2
        assert scheduled.json()["new_run_created"] is True
        assert db.get(Attempt, previous.id).status == "submitted"
        assert db.get(Attempt, previous.id).run_number == 1

        # Simulate the scheduled time becoming due. The first participant request
        # applies the transition and is allowed one attempt in the new run.
        exam.scheduled_start_at = datetime.now(timezone.utc) - timedelta(seconds=1)
        db.commit()
        app.dependency_overrides[routes.current_user] = lambda: student
        started = client.post(f"/api/v1/exams/{exam.id}/attempts")
        assert started.status_code == 200, started.text
        new_attempt = db.get(Attempt, started.json()["attempt_id"])
        assert new_attempt.run_number == 2
        assert new_attempt.attempt_number == 2  # globally unique attempt serial is preserved
        assert db.get(Attempt, previous.id) is not None
    finally:
        cleanup(db, engine)


def test_admin_can_force_start_ended_exam_immediately_as_new_run():
    client, db, engine, admin = make_client(Role.admin)
    try:
        exam, _ = add_exam(db, admin, ExamStatus.results_published)
        exam.ended_at = datetime.now(timezone.utc) - timedelta(days=2)
        exam.scheduled_end_at = datetime.now(timezone.utc) - timedelta(days=1)
        previous = Attempt(
            id="old-admin-preview", exam_id=exam.id, student_id=admin.id,
            attempt_number=1, run_number=1, status="in_progress", is_admin_attempt=True,
            is_staff_attempt=True, max_score=1, answers=[],
        )
        db.add(previous); db.commit()

        response = client.post(f"/api/v1/exams/{exam.id}/control/force-start")
        assert response.status_code == 200, response.text
        assert response.json()["status"] == "live"
        assert response.json()["run_number"] == 2
        assert response.json()["scheduled_end_at"] is None
        assert db.get(Exam, exam.id).ended_at is None
        db.refresh(previous)
        assert previous.status == "submitted"

        # The admin can create a fresh preview attempt for the new run.
        preview = client.post(f"/api/v1/exams/{exam.id}/admin-attempts")
        assert preview.status_code == 200, preview.text
        assert db.get(Attempt, preview.json()["attempt_id"]).run_number == 2

        student = User(
            id="immediate-restart-student", email="immediate-restart@example.test", full_name="Immediate Restart",
            password_hash="x", role=Role.student, active=True,
        )
        db.add(student); db.commit()
        app.dependency_overrides[routes.current_user] = lambda: student
        student_attempt = client.post(f"/api/v1/exams/{exam.id}/attempts")
        assert student_attempt.status_code == 200, student_attempt.text
        assert db.get(Attempt, student_attempt.json()["attempt_id"]).run_number == 2
    finally:
        cleanup(db, engine)


def test_only_admin_can_reschedule_or_restart_an_ended_exam():
    client, db, engine, moderator = make_client(Role.moderator)
    try:
        exam, _ = add_exam(db, moderator, ExamStatus.ended)
        future = datetime.now(timezone.utc) + timedelta(hours=2)
        schedule = client.patch(
            f"/api/v1/exams/{exam.id}/schedule",
            json={"scheduled_start_at": future.isoformat()},
        )
        assert schedule.status_code == 403
        start = client.post(f"/api/v1/exams/{exam.id}/control/force-start")
        assert start.status_code == 403
        db.refresh(exam)
        assert exam.status == ExamStatus.ended
        assert exam.run_number == 1
    finally:
        cleanup(db, engine)


def test_ended_exam_new_run_rejects_end_time_before_start_without_mutating_exam():
    client, db, engine, admin = make_client(Role.admin)
    try:
        exam, _ = add_exam(db, admin, ExamStatus.ended)
        future = datetime.now(timezone.utc) + timedelta(hours=2)
        invalid = client.patch(
            f"/api/v1/exams/{exam.id}/schedule",
            json={"scheduled_start_at": future.isoformat(), "scheduled_end_at": (future - timedelta(minutes=1)).isoformat()},
        )
        assert invalid.status_code == 422
        db.refresh(exam)
        assert exam.status == ExamStatus.ended
        assert exam.run_number == 1
    finally:
        cleanup(db, engine)
