"""Student rankings must never serialize staff-only provenance or unpublished attempts."""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from app.core.database import Base, get_db
from app.core.security import create_token
from app.main import app
from app.models.entities import Attempt, Exam, ExamStatus, LeaderboardEntry, Role, User


@pytest.fixture
def seeded():
    engine = create_engine('sqlite://', connect_args={'check_same_thread': False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    db = sessionmaker(bind=engine, expire_on_commit=False)()
    admin = User(id='admin', email='admin@example.com', full_name='Admin', role=Role.admin, password_hash='unused')
    student = User(id='student', email='student@example.com', full_name='Student One', role=Role.student, password_hash='unused')
    db.add_all([admin, student]); db.commit()
    for key, status in [('draft', ExamStatus.draft), ('live', ExamStatus.live), ('published', ExamStatus.results_published), ('hidden', ExamStatus.draft), ('empty', ExamStatus.results_published)]:
        db.add(Exam(id=key, title=key.title() + ' examination', subject='Biology', paper='1st Paper', status=status, created_by=admin.id))
    db.commit()
    db.add_all([
        LeaderboardEntry(id='manual-draft', scope='exam', exam_id='draft', display_name='Md Shihab', student_identifier='private-identifier', score=97, created_by=admin.id),
        LeaderboardEntry(id='manual-live', scope='exam', exam_id='live', student_id=student.id, display_name='Student One', score=10, max_score=20, created_by=admin.id),
        LeaderboardEntry(id='manual-paper', scope='paper', paper='2nd Paper', subject='Chemistry', display_name='Paper Student', score=80, max_score=100, created_by=admin.id),
        LeaderboardEntry(id='manual-subject', scope='subject', subject='Physics', display_name='Subject Student', score=70, max_score=100, created_by=admin.id),
        Attempt(id='live-attempt', exam_id='live', student_id=student.id, status='submitted', score=999, max_score=1000, answers=[]),
        Attempt(id='published-attempt', exam_id='published', student_id=student.id, status='submitted', score=85, max_score=100, answers=[]),
    ]); db.commit()
    def override_db():
        yield db
    app.dependency_overrides[get_db] = override_db
    client = TestClient(app)
    client.cookies.set('access_token', create_token(student.id, 'student'))
    try:
        yield client, db, admin, student
    finally:
        client.close(); app.dependency_overrides.clear(); db.close(); engine.dispose()


def test_catalog_includes_manual_draft_and_published_rankings(seeded):
    client, *_ = seeded
    res = client.get('/api/v1/leaderboards/catalog')
    assert res.status_code == 200, res.text
    catalog = res.json()
    assert {exam['id'] for exam in catalog['exams']} == {'draft', 'live', 'published'}
    assert set(catalog['papers']) == {'1st Paper', '2nd Paper'}
    assert set(catalog['subjects']) == {'Biology', 'Chemistry', 'Physics'}
    assert all(set(exam) == {'id', 'title', 'subject'} for exam in catalog['exams'])


def test_manual_draft_record_and_private_fields(seeded):
    client, *_ = seeded
    res = client.get('/api/v1/exams/draft/leaderboard')
    assert res.status_code == 200, res.text
    assert res.json() == [{'rank': 1, 'student': 'Md Shihab', 'score': 97.0, 'max_score': None, 'accuracy': None}]
    assert client.get('/api/v1/exams/draft').status_code == 404
    assert client.get('/api/v1/exams/hidden/leaderboard').status_code == 403
    assert client.get('/api/v1/admin/leaderboards', params={'exam_id': 'draft'}).status_code == 403


def test_live_attempt_not_disclosed_even_when_manual_record_exists(seeded):
    client, *_ = seeded
    res = client.get('/api/v1/exams/live/leaderboard')
    assert res.status_code == 200, res.text
    assert res.json() == [{'rank':1, 'student':'Student One','score':10.0,'max_score':20.0,'accuracy':50.0}]
    res = client.get('/api/v1/leaderboards', params={'scope':'subject','subject':'Biology'})
    assert res.status_code == 200
    assert [row['score'] for row in res.json()] == [85]
    res = client.get('/api/v1/leaderboards', params={'scope':'paper','paper':'1st Paper'})
    assert res.status_code == 200
    assert [row['score'] for row in res.json()] == [85]


def test_paper_and_subject_manual_rankings(seeded):
    client, *_ = seeded
    for params, name, score in [({'scope':'paper','paper':'2nd Paper','subject':'Chemistry'},'Paper Student',80), ({'scope':'subject','subject':'Physics'},'Subject Student',70)]:
        res = client.get('/api/v1/leaderboards', params=params)
        assert res.status_code == 200, res.text
        assert res.json() == [{'rank':1,'student':name,'score':score,'max_score':100,'accuracy':score}]
    assert client.get('/api/v1/leaderboards', params={'scope':'paper'}).status_code == 422


def test_admin_provenance_retained_and_login_required(seeded):
    client, db, admin, student = seeded
    client.cookies.set('access_token', create_token(admin.id, 'admin'))
    res = client.get('/api/v1/admin/leaderboards', params={'exam_id':'draft'})
    assert res.status_code == 200, res.text
    assert res.json()['rows'][0]['source'] == 'manual'
    assert res.json()['rows'][0]['email'] == 'private-identifier'
    assert client.get('/api/v1/exams/draft/leaderboard').json()[0].keys() == {'rank','student','score','max_score','accuracy'}
    client.cookies.clear()
    for path in ['/api/v1/leaderboards/catalog', '/api/v1/leaderboards?exam_id=draft', '/api/v1/exams/draft/leaderboard']:
        assert client.get(path).status_code == 401
