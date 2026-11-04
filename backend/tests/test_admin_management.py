from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.api import routes
from app.core.database import Base, get_db
from app.main import app
from app.models.entities import (
    Attempt, Exam, ExamStatus, Question, Role, User,
)


def _client_with_admin():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)
    db = session_factory()
    admin = User(
        id="admin-control-test", email="admin-control@example.test", full_name="Control Admin",
        password_hash="test-hash", role=Role.admin, active=True,
    )
    db.add(admin)
    db.commit()

    def override_db():
        yield db

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[routes.current_user] = lambda: admin
    return TestClient(app), db, engine, admin


def _cleanup(db, engine):
    app.dependency_overrides.clear()
    db.close()
    Base.metadata.drop_all(engine)
    engine.dispose()


def test_admin_can_create_promote_block_unblock_and_remove_user():
    client, db, engine, admin = _client_with_admin()
    try:
        created = client.post("/api/v1/admin/users", json={
            "full_name": "Test Learner", "email": "learner@example.com",
            "password": "safe-password-123", "role": "student",
        })
        assert created.status_code == 201, created.text
        user_id = created.json()["id"]

        promoted = client.patch(f"/api/v1/admin/users/{user_id}/role", json={"role": "moderator"})
        assert promoted.status_code == 200
        assert promoted.json()["role"] == "moderator"
        retained_exam = Exam(
            id="moderator-created-exam", title="Moderator created exam", subject="Physics",
            status=ExamStatus.draft, duration_seconds=3600, max_attempts=1, created_by=user_id,
        )
        db.add(retained_exam)
        db.commit()

        blocked = client.patch(f"/api/v1/admin/users/{user_id}/status", json={"active": False})
        assert blocked.status_code == 200
        assert blocked.json()["active"] is False

        unblocked = client.patch(f"/api/v1/admin/users/{user_id}/status", json={"active": True})
        assert unblocked.status_code == 200
        assert unblocked.json()["active"] is True

        removed = client.delete(f"/api/v1/admin/users/{user_id}")
        assert removed.status_code == 200, removed.text
        assert db.get(User, user_id) is None
        db.refresh(retained_exam)
        assert retained_exam.created_by == admin.id
    finally:
        _cleanup(db, engine)


def test_admin_can_set_duration_up_or_down_while_exam_is_live():
    client, db, engine, admin = _client_with_admin()
    try:
        started = datetime.now(timezone.utc) - timedelta(minutes=45)
        exam = Exam(
            id="duration-live-exam", title="Live duration test", subject="Biology",
            status=ExamStatus.live, duration_seconds=60 * 60, max_attempts=1,
            created_by=admin.id, started_at=started,
        )
        db.add(exam)
        db.add(Attempt(
            id="duration-live-attempt", exam_id=exam.id, student_id=admin.id,
            attempt_number=1, status="in_progress", started_at=started,
            max_score=1, answers=[],
        ))
        db.commit()

        reduced = client.patch(f"/api/v1/exams/{exam.id}/duration", json={"duration_minutes": 40})
        assert reduced.status_code == 200, reduced.text
        assert reduced.json()["duration_seconds"] == 40 * 60
        assert reduced.json()["attempts_now_out_of_time"] == 1

        increased = client.patch(f"/api/v1/exams/{exam.id}/duration", json={"duration_minutes": 75})
        assert increased.status_code == 200, increased.text
        assert increased.json()["duration_seconds"] == 75 * 60
    finally:
        _cleanup(db, engine)


def test_leaderboard_combines_live_attempts_and_manual_entries_and_can_remove_them():
    client, db, engine, admin = _client_with_admin()
    try:
        student = User(
            id="leaderboard-student", email="ranked@example.test", full_name="Ranked Student",
            password_hash="test-hash", role=Role.student, active=True,
        )
        exam = Exam(
            id="leaderboard-exam", title="Biology 1st Paper", subject="Biology",
            paper="1st Paper", status=ExamStatus.results_published, duration_seconds=3600,
            max_attempts=1, created_by=admin.id,
        )
        db.add_all([student, exam])
        q1 = Question(
            id="leaderboard-q1", exam_id=exam.id, kind="mcq", prompt="Q1",
            options=[{"id": "A", "text": "A"}, {"id": "B", "text": "B"}],
            answer_key={"selected_option_ids": ["A"]}, marks=1, position=0,
        )
        q2 = Question(
            id="leaderboard-q2", exam_id=exam.id, kind="mcq", prompt="Q2",
            options=[{"id": "A", "text": "A"}, {"id": "B", "text": "B"}],
            answer_key={"selected_option_ids": ["A"]}, marks=1, position=1,
        )
        db.add_all([q1, q2])
        db.add(Attempt(
            id="leaderboard-attempt", exam_id=exam.id, student_id=student.id,
            attempt_number=1, status="submitted", started_at=datetime.now(timezone.utc),
            submitted_at=datetime.now(timezone.utc), score=1, max_score=2,
            answers=[
                {"question_id": q1.id, "answer": {"selected_option_ids": ["A"]}},
                {"question_id": q2.id, "answer": {"selected_option_ids": ["B"]}},
            ],
        ))
        db.commit()

        manual = client.post("/api/v1/admin/leaderboards/entries", json={
            "scope": "exam", "display_name": "Manual Champion", "exam_id": exam.id,
            "score": 1.8, "max_score": 2,
        })
        assert manual.status_code == 201, manual.text
        entry_id = manual.json()["id"]

        response = client.get(f"/api/v1/admin/leaderboards?scope=exam&exam_id={exam.id}")
        assert response.status_code == 200, response.text
        result = response.json()["rows"]
        assert [row["student"] for row in result] == ["Manual Champion", "Ranked Student"]
        assert result[0]["accuracy"] == 90
        assert result[1]["accuracy"] == 50

        paper_rank = client.get("/api/v1/admin/leaderboards?scope=paper&paper=1st%20Paper&subject=Biology")
        assert paper_rank.status_code == 200, paper_rank.text
        assert any(row["student"] == "Ranked Student" for row in paper_rank.json()["rows"])
        subject_rank = client.get("/api/v1/admin/leaderboards?scope=subject&subject=Biology")
        assert subject_rank.status_code == 200, subject_rank.text
        assert any(row["student"] == "Ranked Student" for row in subject_rank.json()["rows"])

        remove_manual = client.post("/api/v1/admin/leaderboards/remove", json={
            "scope": "exam", "exam_id": exam.id, "entry_id": entry_id,
        })
        assert remove_manual.status_code == 200, remove_manual.text

        remove_attempt = client.post("/api/v1/admin/leaderboards/remove", json={
            "scope": "exam", "exam_id": exam.id, "student_id": student.id,
        })
        assert remove_attempt.status_code == 200, remove_attempt.text
        after = client.get(f"/api/v1/admin/leaderboards?scope=exam&exam_id={exam.id}")
        assert after.status_code == 200
        assert after.json()["rows"] == []
    finally:
        _cleanup(db, engine)


def test_admin_workspace_examination_list_returns_existing_exams():
    client, db, engine, admin = _client_with_admin()
    try:
        exam = Exam(
            id="workspace-list-exam", title="Workspace list regression", subject="Biology",
            status=ExamStatus.draft, duration_seconds=3600, max_attempts=1,
            created_by=admin.id, paper="2nd Paper",
        )
        db.add(exam)
        db.commit()

        response = client.get("/api/v1/exams")
        assert response.status_code == 200, response.text
        rows = response.json()
        assert len(rows) == 1
        assert rows[0]["id"] == exam.id
        assert rows[0]["paper"] == "2nd Paper"
    finally:
        _cleanup(db, engine)
