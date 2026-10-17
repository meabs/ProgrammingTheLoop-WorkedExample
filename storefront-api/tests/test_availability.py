"""Acceptance criteria 1-4 from docs/brief.md, against a fake inventory built from the pinned contract."""
import pathlib

import httpx
import pytest
import yaml
from fastapi.testclient import TestClient

from app.clients import inventory
from app.main import app

CONTRACT = yaml.safe_load((pathlib.Path(__file__).parent.parent / "contracts" / "inventory.openapi.yaml").read_text())
OK_SCHEMA = CONTRACT["paths"]["/v2/stock/{sku}"]["get"]["responses"]["200"]["content"]["application/json"]


def fake_inventory(stock):
    """A stub that answers only on the contract's path, with the contract's field names."""
    def handler(request):
        sku = request.url.path.removeprefix("/v2/stock/")
        if not request.url.path.startswith("/v2/stock/"):
            return httpx.Response(404)
        if sku not in stock:
            return httpx.Response(404, json={"error": "unknown_sku"})
        on_hand, reserved = stock[sku]
        return httpx.Response(200, json={"sku": sku, "on_hand": on_hand, "reserved": reserved})
    return httpx.MockTransport(handler)


@pytest.fixture
def client(monkeypatch):
    def use(transport):
        real = inventory.get_stock
        monkeypatch.setattr(inventory, "get_stock", lambda sku: real(sku, transport=transport))
        return TestClient(app)
    return use


def test_contract_example_matches_fields_we_read():
    example = OK_SCHEMA["example"]
    assert {"on_hand", "reserved"} <= set(OK_SCHEMA["schema"]["required"])
    assert inventory.get_stock("MUG-001", transport=httpx.MockTransport(
        lambda req: httpx.Response(200, json=example))) == (12, 3)


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
    bad = httpx.MockTransport(lambda req: httpx.Response(200, json={"sku": "MUG-001", "quantity": 5}))
    assert client(bad).get("/products/MUG-001/availability").status_code == 502


def test_inventory_unreachable_is_502(client):
    def boom(request):
        raise httpx.ConnectError("connection refused")
    assert client(httpx.MockTransport(boom)).get("/products/MUG-001/availability").status_code == 502
