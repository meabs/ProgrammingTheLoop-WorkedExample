Reading project guidance and the brief, then exploring the codebase to restate goals and plan work.
Restating the goal, then writing tests first.

Goal: Add `GET /products/{sku}/availability` returning `sku`, `available` (on_hand − reserved), and `in_stock`.

Acceptance: stock/reserved/404/502 cases per brief; `scripts/test.sh` passes; curl demo if a service is reachable.

Files: `app/clients/inventory.py`, `app/main.py`, `tests/test_availability.py` (and possibly `tests/test_inventory_client.py`).

Inventory facts from `contracts/inventory.openapi.yaml` (pinned in `contracts/PINNED`): `GET /v2/stock/{sku}`; 200 with `sku`, `on_hand`, `reserved`; 404 with `error: unknown_sku`.
Simplifying client tests and implementing the inventory client and endpoint.
Starting a minimal inventory stub and demonstrating end-to-end with curl (acceptance criterion 6).
## Goal (restated)

Add **`GET /products/{sku}/availability`** so shoppers see whether a product can be ordered. The JSON body is `sku`, `available` (inventory `on_hand` minus `reserved`), and `in_stock` (`available > 0`).

## Acceptance criteria (restated)

1. Known catalogue SKU with free stock → **200**, correct `available`, `in_stock: true`.
2. Known SKU fully reserved → **200**, `available: 0`, `in_stock: false`.
3. Unknown catalogue SKU or inventory **404** → **404**.
4. Inventory down or non-contract response → **502**, error logged in the client, no invented numbers.
5. **`bash scripts/test.sh`** passes (including contract freshness).
6. Demonstrate real HTTP behaviour against a running inventory service (curl).

## What changed

| File | Change |
|------|--------|
| `app/clients/inventory.py` | New HTTP client: `GET {INVENTORY_BASE_URL}/v2/stock/{sku}`, validates contract fields, `InventoryNotFound` / `InventoryError`, logging on failures |
| `app/main.py` | New `read_availability` route |
| `tests/test_availability.py` | Endpoint tests (criteria 1–4) |
| `tests/test_inventory_client.py` | Client tests including logging on bad payload and network errors |

**Inventory facts used** (from `contracts/inventory.openapi.yaml`, version **2.1.0** in `contracts/PINNED`):

- Path: `GET /v2/stock/{sku}`
- **200**: `sku`, `on_hand`, `reserved` (non-negative integers)
- **404**: `error: unknown_sku`

Base URL: `INVENTORY_BASE_URL` (default `http://localhost:8080`).

## Commands and output

**New tests before implementation** (import error — no `inventory` module yet):

```
ERROR tests/test_availability.py - ImportError: cannot import name 'inventory'
ERROR tests/test_inventory_client.py - ImportError: cannot import name 'inventory'
```

**Full checks after implementation:**

```
== contract freshness
ok: pinned 2.1.0, provider publishes 2.1.0
== tests
...........                                                              [100%]
11 passed in 0.30s
```

**Manual e2e** (local inventory stub on `:18080` implementing the pinned contract; storefront on `:18081`):

```
=== inventory direct ===
{"sku": "MUG-001", "on_hand": 12, "reserved": 3}
=== storefront availability ===
{"sku":"MUG-001","available":9,"in_stock":true}
HTTP 200
=== fully reserved ===
{"sku":"TEE-042","available":0,"in_stock":false}
HTTP 200
```

There is no runnable inventory service in this workspace (only `inventory-service/contracts/`). The curl demo used a temporary stub at `<tmp>/inventory_stub.py`, not committed.

VERIFICATION: {"ran":["bash scripts/test.sh","../.venv/bin/python -m pytest tests/test_availability.py tests/test_inventory_client.py -q (pre-implementation)","curl against stub inventory :18080 and storefront :18081"],"result":"passed","could_not_verify":["End-to-end against a real inventory team deployment (no service binary in repo); only contract-aligned stub"],"missing":["Runnable inventory service or docker compose in workspace for criterion 6 without a local stub"]}