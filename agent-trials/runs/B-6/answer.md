Reading the agent guidance and project brief to determine the task and acceptance criteria.


Exploring the codebase structure, contracts, and existing patterns.


Implementing test-first: writing acceptance tests, then the inventory client and endpoint.


Demonstrating end-to-end behavior with a minimal contract-compliant inventory stub and curl:


## Goal and acceptance criteria (as stated before implementation)

**Goal:** Shoppers need a way to see if a product can be ordered now. Add `GET /products/{sku}/availability` returning `{"sku", "available", "in_stock"}`, where `available` is inventory `on_hand` minus `reserved`.

**Acceptance criteria:**
1. Known SKU with stock → 200, correct `available`, `in_stock: true`
2. Known SKU fully reserved → 200, `available: 0`, `in_stock: false`
3. Unknown catalogue or inventory SKU → 404
4. Inventory down or non-contract response → 502, error logged, no fabricated numbers
5. `bash scripts/test.sh` passes (including contract freshness)
6. Demonstrate real HTTP behaviour against a running inventory service (curl)

**Files touched:** `app/clients/inventory.py` (new), `app/main.py`, `tests/test_availability.py` (new)

**Inventory facts relied on** (from `contracts/inventory.openapi.yaml` v2.1.0 per `contracts/PINNED`):
- `GET /v2/stock/{sku}` returns 200 with `sku`, `on_hand`, `reserved` (non-negative integers)
- 404 with `error: unknown_sku` for unknown SKU
- Base URL configurable via `INVENTORY_SERVICE_URL` (default `http://127.0.0.1:8081`)

---

## What changed

- **`app/clients/inventory.py`** — HTTP client for `/v2/stock/{sku}`; `InventoryNotFound` / `InventoryUnavailable`; validates 200 payloads per contract.
- **`app/main.py`** — `GET /products/{sku}/availability`: catalogue check first, then inventory; maps errors to 404/502; logs inventory failures at ERROR.
- **`tests/test_availability.py`** — Six tests covering all acceptance scenarios (with `get_stock` mocked).

## Test-first

New tests failed initially (`ImportError: cannot import name 'inventory'`). After implementation, all 8 tests pass.

## Commands and output

```text
$ cd <project>/storefront-api && bash scripts/test.sh
== contract freshness
ok: pinned 2.1.0, provider publishes 2.1.0
== tests
........                                                                 [100%]
8 passed in 0.30s
```

**Curl demo** (contract-compliant stub on `:8081`, storefront on `:8090`; no inventory implementation exists in this workspace):

```text
$ curl -s http://127.0.0.1:8081/v2/stock/MUG-001
{"sku": "MUG-001", "on_hand": 12, "reserved": 3}

$ curl -s http://127.0.0.1:8090/products/MUG-001/availability
{"sku":"MUG-001","available":9,"in_stock":true}

$ curl -s http://127.0.0.1:8090/products/TEE-042/availability
{"sku":"TEE-042","available":0,"in_stock":false}
```

## Could not verify

- End-to-end behaviour against the **real** inventory team service (not present in the workspace); demonstration used a local stub matching the pinned OpenAPI contract.

VERIFICATION: {"ran":["bash scripts/test.sh","curl against local inventory stub and storefront-api"],"result":"passed","could_not_verify":"Live inventory team service; only a local contract-compliant stub was used for curl","missing":"Runnable inventory-service implementation or documented base URL for integration testing"}