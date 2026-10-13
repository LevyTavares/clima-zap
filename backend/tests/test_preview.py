from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

def test_forecast_preview_endpoint():
    response = client.get("/api/v1/forecast/preview")
    assert response.status_code == 200
    data = response.json()
    assert data["cidade"] == "Juazeiro do Norte"
    assert data["temperatura"] == "28°C"
    assert data["condicao"] == "Chuva forte"