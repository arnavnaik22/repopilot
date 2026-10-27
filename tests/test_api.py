from fastapi.testclient import TestClient
from repopilot.api.main import app


def test_health_and_validation():
    client=TestClient(app)
    assert client.get("/health").json()=={"status":"ok"}
    assert client.post("/query",json={"repository_id":"bad","question":"hi"}).status_code==422
    assert client.get("/repositories/invalid/status").status_code==404
