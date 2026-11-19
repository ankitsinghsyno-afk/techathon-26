import pytest
from fastapi.testclient import TestClient
from src.server import app

client = TestClient(app)


def test_api_status():
    response = client.get("/api/status")
    assert response.status_code == 200
    data = response.json()
    assert "floor_name" in data or "status" in data


def test_api_scenario():
    response = client.post("/api/scenario", json={"scenario": "only_team_a"})
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert data["scenario"] == "only_team_a"


def test_api_manual_override():
    response = client.post("/api/override", json={"zone_id": "zone_alpha", "lights_state": True})
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert data["lights_state"] is True


def test_api_invalid_scenario():
    response = client.post("/api/scenario", json={"scenario": "invalid_scenario_xyz"})
    assert response.status_code == 400
