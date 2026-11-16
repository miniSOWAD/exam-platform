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
