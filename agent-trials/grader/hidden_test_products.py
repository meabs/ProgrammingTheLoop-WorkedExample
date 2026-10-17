from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_known_product():
    r = client.get("/products/MUG-001")
    assert r.status_code == 200
    assert r.json()["name"] == "Loop mug"


def test_unknown_product():
    assert client.get("/products/NOPE-000").status_code == 404
