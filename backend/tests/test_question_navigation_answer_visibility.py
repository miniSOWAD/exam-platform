from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.api import routes
from app.core.database import Base, get_db
from app.main import app
from app.models.entities import (
    AnswerVisibilityGrant, Attempt, Exam, ExamStatus, PermissionGrant, Question, Role, User,
)


def make_client(role=Role.student):
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)
    db = factory()
    user = User(
        id=f"{role.value}-qnav-user", email=f"{role.value}-qnav@example.com",
        full_name=role.value.title(), password_hash="test-hash", role=role, active=True,
    )
    db.add(user); db.commit()

    def override_db():
        yield db

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[routes.current_user] = lambda: user
    return TestClient(app), db, engine, user


def cleanup(db, engine):
    app.dependency_overrides.clear()
    db.close()
    Base.metadata.drop_all(engine)
    engine.dispose()


def add_exam(db, owner, status=ExamStatus.live):
    exam = Exam(
        id="qnav-answer-exam", title="Question navigation and answer visibility",
        subject="Biology", status=status, duration_seconds=3600, max_attempts=1,
        created_by=owner.id, answers_public=False, hide_participant_answers=False,
    )
    question = Question(
        id="qnav-answer-q1", exam_id=exam.id, kind="mcq", prompt="Which option is correct?",
        options=[{"id": "A", "text": "Wrong"}, {"id": "B", "text": "Correct"}],
        answer_key={"selected_option_ids": ["B"]}, marks=2, negative_marks=0.5, position=0,
    )
    db.add_all([exam, question]); db.commit()
    return exam, question


def test_question_visit_is_persisted_and_answer_save_marks_question_answered():
    client, db, engine, student = make_client(Role.student)
    try:
        exam, question = add_exam(db, student)
        started = client.post(f"/api/v1/exams/{exam.id}/attempts")
        assert started.status_code == 200, started.text
        attempt_id = started.json()["attempt_id"]

        initial = client.get(f"/api/v1/attempts/{attempt_id}")
        assert initial.status_code == 200
        assert initial.json()["visited_question_ids"] == []

        visited = client.post(f"/api/v1/attempts/{attempt_id}/visit/{question.id}")
        assert visited.status_code == 200
        assert visited.json()["visited_question_ids"] == [question.id]

        saved = client.put(
            f"/api/v1/attempts/{attempt_id}/answers/{question.id}",
            json={"answer": {"selected_option_ids": ["B"]}},
        )
        assert saved.status_code == 200, saved.text
        snapshot = client.get(f"/api/v1/attempts/{attempt_id}").json()
        assert snapshot["visited_question_ids"] == [question.id]
        assert snapshot["answers"][0]["answer"]["selected_option_ids"] == ["B"]
    finally:
        cleanup(db, engine)


def test_student_does_not_receive_answer_key_during_live_exam_but_gets_it_after_end():
    client, db, engine, student = make_client(Role.student)
    try:
        exam, question = add_exam(db, student)
        started = client.post(f"/api/v1/exams/{exam.id}/attempts")
        attempt_id = started.json()["attempt_id"]

        live_questions = client.get(f"/api/v1/attempts/{attempt_id}/questions")
        assert live_questions.status_code == 200
        assert "answer_key" not in live_questions.json()[0]

        saved = client.put(
            f"/api/v1/attempts/{attempt_id}/answers/{question.id}",
            json={"answer": {"selected_option_ids": ["B"]}},
        )
        assert saved.status_code == 200
        db.get(Exam, exam.id).status = ExamStatus.ended
        db.get(Exam, exam.id).ended_at = datetime.now(timezone.utc)
        db.commit()

        ended_questions = client.get(f"/api/v1/attempts/{attempt_id}/questions")
        assert ended_questions.status_code == 200
        assert ended_questions.json()[0]["answer_key"]["selected_option_ids"] == ["B"]
        result = client.get(f"/api/v1/attempts/{attempt_id}").json()
        assert result["status"] == "submitted"
        assert result["score"] == 2
        assert result["can_view_answers"] is True
    finally:
        cleanup(db, engine)


def test_examiner_can_hide_answers_from_participants_and_individual_grant_overrides_hide():
    client, db, engine, admin = make_client(Role.admin)
    try:
        exam, question = add_exam(db, admin)
        student = User(id="participant-hidden", email="participant-hidden@example.com", full_name="Participant", password_hash="x", role=Role.student, active=True)
        db.add(student); db.commit()
        attempt = Attempt(
            id="participant-hidden-attempt", exam_id=exam.id, student_id=student.id,
            attempt_number=1, status="submitted", submitted_at=datetime.now(timezone.utc),
            score=2, max_score=2, answers=[{"question_id": question.id, "answer": {"selected_option_ids": ["B"]}}],
        )
        exam.status = ExamStatus.ended
        exam.hide_participant_answers = True
        db.add(attempt); db.commit()

        app.dependency_overrides[routes.current_user] = lambda: student
        hidden = client.get(f"/api/v1/attempts/{attempt.id}/questions")
        assert hidden.status_code == 200
        assert "answer_key" not in hidden.json()[0]
        denied_sheet = client.get(f"/api/v1/exams/{exam.id}/answer-sheet")
        assert denied_sheet.status_code == 403

        app.dependency_overrides[routes.current_user] = lambda: admin
        grant = client.post(f"/api/v1/exams/{exam.id}/answer-access", json={"student_email": student.email})
        assert grant.status_code == 201, grant.text
        app.dependency_overrides[routes.current_user] = lambda: student
        permitted = client.get(f"/api/v1/attempts/{attempt.id}/questions")
        assert permitted.status_code == 200
        assert permitted.json()[0]["answer_key"]["selected_option_ids"] == ["B"]
    finally:
        cleanup(db, engine)


def test_nonparticipant_cannot_view_answer_sheet_until_public_or_individually_granted():
    client, db, engine, admin = make_client(Role.admin)
    try:
        exam, question = add_exam(db, admin, status=ExamStatus.ended)
        student = User(id="nonparticipant", email="nonparticipant@example.com", full_name="No Attempt", password_hash="x", role=Role.student, active=True)
        db.add(student); db.commit()

        app.dependency_overrides[routes.current_user] = lambda: student
        denied = client.get(f"/api/v1/exams/{exam.id}/answer-sheet")
        assert denied.status_code == 403

        app.dependency_overrides[routes.current_user] = lambda: admin
        public = client.patch(f"/api/v1/exams/{exam.id}/answer-visibility", json={"answers_public": True})
        assert public.status_code == 200
        app.dependency_overrides[routes.current_user] = lambda: student
        public_sheet = client.get(f"/api/v1/exams/{exam.id}/answer-sheet")
        assert public_sheet.status_code == 200
        assert public_sheet.json()["questions"][0]["answer_key"]["selected_option_ids"] == ["B"]
        assert "participant_result" not in public_sheet.json()

        app.dependency_overrides[routes.current_user] = lambda: admin
        private = client.patch(f"/api/v1/exams/{exam.id}/answer-visibility", json={"answers_public": False})
        assert private.status_code == 200
        granted = client.post(f"/api/v1/exams/{exam.id}/answer-access", json={"student_email": student.email})
        assert granted.status_code == 201
        app.dependency_overrides[routes.current_user] = lambda: student
        granted_sheet = client.get(f"/api/v1/exams/{exam.id}/answer-sheet")
        assert granted_sheet.status_code == 200
    finally:
        cleanup(db, engine)


def test_moderator_can_attend_and_see_keys_but_needs_results_permission_to_manage_visibility():
    client, db, engine, moderator = make_client(Role.moderator)
    try:
        exam, question = add_exam(db, moderator)
        started = client.post(f"/api/v1/exams/{exam.id}/attempts")
        assert started.status_code == 200, started.text
        attempt_id = started.json()["attempt_id"]
        rows = client.get(f"/api/v1/attempts/{attempt_id}/questions")
        assert rows.status_code == 200
        assert rows.json()[0]["answer_key"]["selected_option_ids"] == ["B"]
        assert db.get(Attempt, attempt_id).is_staff_attempt is True

        exam.status = ExamStatus.ended
        db.commit()
        denied = client.patch(f"/api/v1/exams/{exam.id}/answer-visibility", json={"answers_public": True})
        assert denied.status_code == 403

        db.add(PermissionGrant(moderator_id=moderator.id, code="results.read", granted_by=moderator.id, active=True))
        db.commit()
        allowed = client.patch(f"/api/v1/exams/{exam.id}/answer-visibility", json={"answers_public": True})
        assert allowed.status_code == 200, allowed.text

        # A moderator's historical staff attempt must not become a student rank if the account is later demoted.
        staff_attempt = db.query(Attempt).filter_by(exam_id=exam.id, student_id=moderator.id).first()
        staff_attempt.status = "submitted"
        staff_attempt.score = 2
        moderator.role = Role.student
        db.commit()
        assert routes._build_leaderboard_rows(db, "exam", exam_id=exam.id) == []
    finally:
        cleanup(db, engine)


def test_admin_stop_auto_submits_student_attempt_and_calculates_score():
    client, db, engine, admin = make_client(Role.admin)
    try:
        exam, question = add_exam(db, admin)
        student = User(id="stop-student", email="stop-student@example.com", full_name="Stop Student", password_hash="x", role=Role.student, active=True)
        db.add(student); db.commit()
        attempt = Attempt(
            id="stop-student-attempt", exam_id=exam.id, student_id=student.id,
            attempt_number=1, status="in_progress", max_score=2,
            answers=[{"question_id": question.id, "answer": {"selected_option_ids": ["B"]}}],
        )
        db.add(attempt); db.commit()
        stopped = client.post(f"/api/v1/exams/{exam.id}/control/stop")
        assert stopped.status_code == 200
        db.refresh(attempt)
        assert attempt.status == "submitted"
        assert attempt.score == 2
        assert attempt.submitted_at is not None
    finally:
        cleanup(db, engine)


def test_scheduled_end_auto_submits_attempts_when_exam_is_next_read():
    client, db, engine, admin = make_client(Role.admin)
    try:
        exam, question = add_exam(db, admin)
        student = User(id="scheduled-end-student", email="scheduled-end@example.com", full_name="Scheduled End", password_hash="x", role=Role.student, active=True)
        db.add(student); db.commit()
        attempt = Attempt(
            id="scheduled-end-attempt", exam_id=exam.id, student_id=student.id,
            attempt_number=1, status="in_progress", max_score=2,
            answers=[{"question_id": question.id, "answer": {"selected_option_ids": ["A"]}}],
        )
        exam.scheduled_end_at = datetime.now(timezone.utc) - timedelta(seconds=1)
        db.add(attempt); db.commit()
        refreshed = client.get(f"/api/v1/exams/{exam.id}")
        assert refreshed.status_code == 200
        assert refreshed.json()["status"] == "ended"
        db.refresh(attempt)
        assert attempt.status == "submitted"
        assert attempt.score == 0
    finally:
        cleanup(db, engine)


def test_participant_can_reopen_answer_sheet_with_score_after_exam_ends():
    client, db, engine, admin = make_client(Role.admin)
    try:
        exam, question = add_exam(db, admin, status=ExamStatus.ended)
        student = User(id="reopen-student", email="reopen-student@example.com", full_name="Reopen Student", password_hash="x", role=Role.student, active=True)
        db.add(student); db.commit()
        attempt = Attempt(
            id="reopen-student-attempt", exam_id=exam.id, student_id=student.id,
            attempt_number=1, status="in_progress", max_score=2,
            answers=[{"question_id": question.id, "answer": {"selected_option_ids": ["B"]}}],
        )
        db.add(attempt); db.commit()

        app.dependency_overrides[routes.current_user] = lambda: student
        detail = client.get(f"/api/v1/exams/{exam.id}")
        assert detail.status_code == 200
        assert detail.json()["can_view_answer_sheet"] is True
        sheet = client.get(f"/api/v1/exams/{exam.id}/answer-sheet")
        assert sheet.status_code == 200
        assert sheet.json()["participant_result"]["score"] == 2
        assert sheet.json()["participant_result"]["max_score"] == 2
        db.refresh(attempt)
        assert attempt.status == "submitted"
    finally:
        cleanup(db, engine)


def test_answer_grant_allows_selected_student_to_open_exam_detail_and_answer_sheet():
    client, db, engine, admin = make_client(Role.admin)
    try:
        exam, question = add_exam(db, admin, status=ExamStatus.ended)
        exam.access_mode = "selected_students"
        student = User(id="answer-only-student", email="answer-only@example.com", full_name="Answer Only", password_hash="x", role=Role.student, active=True)
        db.add(student); db.commit()
        db.add(AnswerVisibilityGrant(exam_id=exam.id, student_id=student.id, granted_by=admin.id))
        db.commit()

        app.dependency_overrides[routes.current_user] = lambda: student
        detail = client.get(f"/api/v1/exams/{exam.id}")
        assert detail.status_code == 200
        assert detail.json()["can_view_answer_sheet"] is True
        listing = client.get("/api/v1/exams")
        assert listing.status_code == 200
        assert any(row["id"] == exam.id for row in listing.json())
        sheet = client.get(f"/api/v1/exams/{exam.id}/answer-sheet")
        assert sheet.status_code == 200
        assert sheet.json()["questions"][0]["answer_key"]["selected_option_ids"] == ["B"]
    finally:
        cleanup(db, engine)
