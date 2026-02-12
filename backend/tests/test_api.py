from app.main import app
from fastapi.testclient import TestClient

client = TestClient(app)


def test_health():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_list_configs():
    response = client.get("/configs")
    assert response.status_code == 200
    assert isinstance(response.json(), list)


def test_get_results():
    response = client.get("/results")
    assert response.status_code == 200
    assert isinstance(response.json(), list)
