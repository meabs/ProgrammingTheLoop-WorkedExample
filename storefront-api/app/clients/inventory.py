"""Client for the inventory service. Contract: contracts/inventory.openapi.yaml (pinned in contracts/PINNED)."""
import logging
import os

import httpx

log = logging.getLogger(__name__)
BASE_URL = os.environ.get("INVENTORY_URL", "http://localhost:8001")


class InventoryUnavailable(Exception):
    """Inventory could not be reached or answered outside its contract."""


def get_stock(sku: str, transport: httpx.BaseTransport | None = None):
    """Return (on_hand, reserved), or None if inventory does not know the SKU."""
    try:
        with httpx.Client(base_url=BASE_URL, transport=transport, timeout=2.0) as http:
            r = http.get(f"/v2/stock/{sku}")
    except httpx.HTTPError as exc:
        log.error("inventory unreachable for %s: %s", sku, exc)
        raise InventoryUnavailable(str(exc)) from exc
    if r.status_code == 404:
        return None
    if r.status_code != 200:
        log.error("inventory returned %s for %s", r.status_code, sku)
        raise InventoryUnavailable(f"status {r.status_code}")
    body = r.json()
    try:
        return int(body["on_hand"]), int(body["reserved"])
    except (KeyError, TypeError, ValueError) as exc:
        log.error("inventory response outside contract for %s: %r", sku, body)
        raise InventoryUnavailable("response outside contract") from exc
