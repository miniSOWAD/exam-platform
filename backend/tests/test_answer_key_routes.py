from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.api import routes
from app.core.database import Base, get_db
from app.main import app
from app.models.entities import Exam, ExamStatus, Question, Role, User


def _test_client():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    testing_session = sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)
    db = testing_session()
    admin = User(
        id="answer-key-admin", email="answer-key-admin@example.test", full_name="Answer Key Admin",
        password_hash="test-hash", role=Role.admin, active=True,
    )
    db.add(admin)
    exam = Exam(
        id="answer-key-exam", title="Answer Key Test", subject="Biology", status=ExamStatus.draft,
        access_mode="all_students", duration_seconds=3600, max_attempts=1, pass_marks=0,
        created_by=admin.id,
    )
    db.add(exam)
    for index in range(4):
        db.add(Question(
            id=f"answer-key-q{index + 1}", exam_id=exam.id, kind="mcq",
            prompt=f"Question {index + 1}?",
            options=[{"key": key, "text": f"Option {key}"} for key in "ABCD"],
            answer_key={"selected_option_ids": ["D"]} if index == 3 else {},
            marks=1, negative_marks=0, position=index,
        ))
    db.commit()

    def override_db():
        try:
            yield db
        finally:
            pass

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[routes.current_user] = lambda: admin
    return TestClient(app), db, engine


def test_answer_key_preview_and_apply_maps_bengali_and_english_labels():
    client, db, engine = _test_client()
    try:
        preview = client.post(
            "/api/v1/exams/answer-key-exam/answer-key/preview",
            files={"file": ("answers.txt", "১.ক ২)খ\n3. C", "text/plain")},
        )
        assert preview.status_code == 200
        result = preview.json()
        assert result["ready_count"] == 3
        assert result["missing_question_numbers"] == [4]

        apply = client.post(
            "/api/v1/exams/answer-key-exam/answer-key/apply",
            json={"answers": [
                {"question_number": item["question_number"], "option_indices": item["option_indices"]}
                for item in result["answers"] if item["status"] == "ready"
            ]},
        )
        assert apply.status_code == 200
        assert apply.json()["applied_count"] == 3
        assert apply.json()["unanswered_question_numbers"] == []

        managed = client.get("/api/v1/exams/answer-key-exam/questions/manage")
        assert managed.status_code == 200
        selected = [item["answer_key"]["selected_option_ids"] for item in managed.json()]
        assert selected == [["A"], ["B"], ["C"], ["D"]]
    finally:
        app.dependency_overrides.clear()
        db.close()
        Base.metadata.drop_all(engine)
        engine.dispose()


def test_conflicting_single_correct_answers_are_flagged_in_preview():
    client, db, engine = _test_client()
    try:
        preview = client.post(
            "/api/v1/exams/answer-key-exam/answer-key/preview",
            files={"file": ("answers.txt", "1.A 1.C 2.B", "text/plain")},
        )
        assert preview.status_code == 200
        entries = {item["question_number"]: item for item in preview.json()["answers"]}
        assert entries[1]["status"] == "conflict"
        assert entries[2]["status"] == "ready"
    finally:
        app.dependency_overrides.clear()
        db.close()
        Base.metadata.drop_all(engine)
        engine.dispose()
