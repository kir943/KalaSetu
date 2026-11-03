from fastapi.testclient import TestClient
from backend.main import app

client = TestClient(app)

def test_health_endpoint():
    response = client.get("/api/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["app"] == "KalaSetu v2"
    assert "sarvam_configured" in data
    # Ensure api key itself is never leaked in the response
    assert "sk_" not in str(data)
