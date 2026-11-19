from fastapi.testclient import TestClient
from app.main import app


def test_health():
    response = TestClient(app).get('/api/v1/health')
    assert response.status_code == 200
    assert response.json()['status'] == 'ok'


def test_platform_root_and_health_are_not_404():
    client = TestClient(app)
    root = client.get('/')
    health = client.get('/health')
    assert root.status_code == 200
    assert root.json()['api'] == '/api/v1'
    assert health.status_code == 200
    assert health.json()['status'] == 'ok'


def test_openapi_docs_are_available_when_enabled():
    if app.docs_url:
        assert TestClient(app).get('/docs').status_code == 200
