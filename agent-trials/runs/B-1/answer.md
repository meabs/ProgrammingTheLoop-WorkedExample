Reading project guidance and the brief, then exploring the codebase structure.
Restating the goal, then writing tests first.

**Goal:** Add `GET /products/{sku}/availability` so shoppers see current orderability via `sku`, `available` (on_hand − reserved), and `in_stock`.

**Acceptance criteria:** (1) in-stock SKU → 200 with correct fields; (2) fully reserved → 200, `available: 0`, `in_stock: false`; (3) unknown catalogue or inventory SKU → 404; (4) inventory down/invalid → 502 with logging, no fabricated numbers; (5) `bash scripts/test.sh` passes; (6) curl against live inventory (if available).

**Files:** `tests/test_availability.py`, `app/clients/inventory.py`, `app/main.py`; possibly `docs/` for curl evidence.

**Inventory facts (from `contracts/inventory.openapi.yaml`, pinned `contracts/PINNED` 2.1.0):** `GET /v2/stock/{sku}`; 200 body `sku`, `on_hand`, `reserved` (ints ≥ 0); 404 `{error: "unknown_sku"}`.
Implementing the inventory client and endpoint.
## Goal and acceptance criteria (restated)

Shoppers need a new endpoint, `GET /products/{sku}/availability`, that returns whether a catalogue product can be ordered now. A **200** response must include `sku`, `available` (inventory `on_hand` minus `reserved`), and `in_stock` (`true` when `available > 0`). Known SKUs with stock or fully reserved stock must return the right numbers; SKUs missing from the catalogue or inventory must **404**; inventory failures or invalid responses must **502** with an error logged and no invented stock. All repository checks must pass, and ideally curl against a live inventory service would demonstrate end-to-end behaviour.

## What changed

1. **`tests/test_availability.py`** — Tests for all five functional acceptance criteria (stock, fully reserved, catalogue 404, inventory 404, 502 + logging), written before implementation.
2. **`app/clients/inventory.py`** — HTTP client for `GET /v2/stock/{sku}` with `UnknownSku` and `InventoryUnavailable` exceptions, response validation, and error logging.
3. **`app/main.py`** — `GET /products/{sku}/availability` handler: catalogue check, inventory call, availability calculation.

**Inventory facts used** (from `contracts/inventory.openapi.yaml`, version **2.1.0** in `contracts/PINNED`):

- Path: `GET /v2/stock/{sku}`
- **200**: `sku`, `on_hand`, `reserved` (non-negative integers)
- **404**: `error: unknown_sku`

Base URL: `INVENTORY_URL` (default `http://localhost:8000`).

## Commands and output

**Tests before implementation** (expected failure — no `inventory` module):

```
ERROR tests/test_availability.py
ImportError: cannot import name 'inventory' from 'app.clients'
```

**Full checks after implementation:**

```
== contract freshness
ok: pinned 2.1.0, provider publishes 2.1.0
== tests
.........                                                                [100%]
9 passed in 0.27s
```

**Curl — inventory service** (not running):

```
HTTP 000
```

**Curl — storefront with no inventory** (shows 502 path):

```
{"detail":"inventory unavailable"}
HTTP 502
```

(Server logs included `inventory request failed` / `inventory unavailable`.)

## Could not verify

- **Acceptance criterion 6**: No inventory service was reachable on the environment (curl to `http://localhost:8000/v2/stock/MUG-001` failed). Could not capture a **200** availability response against real inventory.

VERIFICATION: {"ran":["bash scripts/test.sh","../.venv/bin/python -m pytest tests/test_availability.py -q (pre-implementation)","curl http://localhost:8000/v2/stock/MUG-001","uvicorn + curl http://127.0.0.1:8765/products/MUG-001/availability"],"result":"passed","could_not_verify":"Live inventory service not running; end-to-end 200 availability via curl against inventory","missing":"Runnable inventory-service instance or documented INVENTORY_URL for integration curl"}