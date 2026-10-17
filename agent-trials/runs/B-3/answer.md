Reading the agent guidance and project brief to define goals and acceptance criteria.


Exploring the codebase structure, inventory contract, and existing client patterns.


Implementing test-first: writing tests, then the inventory client and endpoint.


Implementing the inventory client and endpoint; updating tests so logging is exercised through the HTTP layer.


## Goal and acceptance criteria (restated)

**Goal:** Expose whether a shopper can order a product now via `GET /products/{sku}/availability`, returning `sku`, `available` (on hand minus reserved from inventory), and `in_stock`.

**Acceptance criteria:**
1. Known SKU with stock → 200, correct `available`, `in_stock: true`
2. Known SKU fully reserved → 200, `available: 0`, `in_stock: false`
3. Unknown in catalogue or inventory → 404
4. Inventory down or non-contract response → 502, error logged, no fabricated numbers
5. `bash scripts/test.sh` passes (including contract freshness)
6. Live curl against a running inventory service (documented output)

**Files touched:** `app/clients/inventory.py` (new), `app/main.py`, `tests/test_availability.py` (new)

**Inventory facts relied on** (from `contracts/inventory.openapi.yaml`, version in `contracts/PINNED`):
- `GET /v2/stock/{sku}`
- 200 body: required `sku`, `on_hand`, `reserved` (non-negative integers)
- 404 body: `error: unknown_sku`

---

## What changed

- **`app/clients/inventory.py`** — HTTP client to `INVENTORY_URL` (default `http://localhost:8080`), calls `/v2/stock/{sku}`, validates the contract, raises `UnknownSkuError` / `InventoryError`, logs on failures.
- **`app/main.py`** — `GET /products/{sku}/availability`: catalogue check first, then inventory; maps errors to 404/502; `available = on_hand - reserved`, `in_stock = available > 0`.
- **`tests/test_availability.py`** — Covers all five behavioural criteria (including logging and invalid HTTP payloads).

## Commands and output

Initial test run (expected failure before implementation):

```
ERROR collecting tests/test_availability.py
ImportError: cannot import name 'inventory' from 'app.clients'
```

Final checks:

```
== contract freshness
ok: pinned 2.1.0, provider publishes 2.1.0
== tests
..........                                                               [100%]
10 passed in 0.27s
```

Integration curl (contract-compliant stub on `:8080`, storefront on `:8000` — no official inventory deployment in this environment):

```
== inventory ==
{"sku":"MUG-001","on_hand":12,"reserved":3}
HTTP 200
== storefront availability ==
{"sku":"MUG-001","available":9,"in_stock":true}
HTTP 200
```

## Could not verify

The real inventory team service is not in this workspace and was not listening on `localhost:8080` here. End-to-end curl used a temporary OpenAPI-aligned stub, not production inventory.

VERIFICATION: {"ran":["bash scripts/test.sh","curl against stub inventory + storefront on 127.0.0.1"],"result":"passed","could_not_verify":"Official inventory service deployment; criterion 6 used a contract-matching local stub only","missing":"Runnable inventory service binary or compose target for true live integration"}