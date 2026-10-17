"""Acceptance criteria 1-4 from docs/brief.md, against a fake inventory built from the pinned contract."""
import httpx
import pytest
from fastapi.testclient import TestClient

from app.clients import inventory
from app.main import app

# No contract in this scenario: the stub below uses the guessed path and field names.


def fake_inventory(stock):
    """A stub that answers only on the contract's path, with the contract's field names."""
    def handler(request):
        sku = request.url.path.removeprefix("/stock/")
        if not request.url.path.startswith("/stock/"):
            return httpx.Response(404)
        if sku not in stock:
            return httpx.Response(404, json={"error": "unknown_sku"})
        on_hand, reserved = stock[sku]
        return httpx.Response(200, json={"sku": sku, "quantity": on_hand, "reserved": reserved})
    return httpx.MockTransport(handler)


@pytest.fixture
def client(monkeypatch):
    def use(transport):
        real = inventory.get_stock
        monkeypatch.setattr(inventory, "get_stock", lambda sku: real(sku, transport=transport))
        return TestClient(app)
    return use


def test_in_stock(client):
    r = client(fake_inventory({"MUG-001": (12, 3)})).get("/products/MUG-001/availability")
    assert r.status_code == 200
    assert r.json() == {"sku": "MUG-001", "available": 9, "in_stock": True}


def test_all_reserved(client):
    r = client(fake_inventory({"TEE-042": (2, 2)})).get("/products/TEE-042/availability")
    assert r.json() == {"sku": "TEE-042", "available": 0, "in_stock": False}


def test_unknown_to_catalogue(client):
    assert client(fake_inventory({})).get("/products/NOPE-000/availability").status_code == 404


def test_unknown_to_inventory(client):
    assert client(fake_inventory({})).get("/products/MUG-001/availability").status_code == 404


def test_inventory_outside_contract_is_502_not_a_guess(client):
    bad = httpx.MockTransport(lambda req: httpx.Response(200, json={"sku": "MUG-001", "qty": 5}))
    assert client(bad).get("/products/MUG-001/availability").status_code == 502


def test_inventory_unreachable_is_502(client):
    def boom(request):
        raise httpx.ConnectError("connection refused")
    assert client(httpx.MockTransport(boom)).get("/products/MUG-001/availability").status_code == 502
