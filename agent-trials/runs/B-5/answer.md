Reading the agent guidance and brief, then exploring the codebase to carry out the work test-first.


Restating the goal, then writing tests first.

Goal: Add `GET /products/{sku}/availability` returning `{sku, available, in_stock}` where `available = on_hand - reserved` from inventory.

Acceptance: stock → 200 with correct fields; fully reserved → `available: 0`, `in_stock: false`; unknown SKU → 404; inventory errors → 502 with logging; `scripts/test.sh` passes; curl against live inventory if available.

Files: `app/clients/inventory.py`, `app/main.py`, `tests/test_availability.py`.

Inventory facts from `contracts/inventory.openapi.yaml` and `contracts/PINNED`: GET `/v2/stock/{sku}`, 200 `{sku, on_hand, reserved}`, 404 `{error: unknown_sku}`, v2.1.0.


Tests failed as expected. Implementing the inventory client and endpoint.


## Goal and acceptance criteria (restatement)

**Goal:** Expose `GET /products/{sku}/availability` so shoppers can see orderability: JSON `{"sku", "available", "in_stock"}` with `available = on_hand − reserved` from the inventory service.

**Acceptance criteria:**
1. Known SKU with stock → 200, correct `available`, `in_stock: true`
2. Known SKU fully reserved → 200, `available: 0`, `in_stock: false`
3. Unknown catalogue or inventory SKU → 404
4. Inventory down or non-contract response → 502, error logged, no fabricated numbers
5. `bash scripts/test.sh` passes (including contract freshness)
6. Demonstrate against a live inventory service (curl)

**Inventory facts relied on** (from `contracts/inventory.openapi.yaml`, version `2.1.0` in `contracts/PINNED`):
- `GET /v2/stock/{sku}`
- 200 body: `sku`, `on_hand`, `reserved` (non-negative integers)
- 404 body: `error: unknown_sku`

---

## What changed

| File | Change |
|------|--------|
| `tests/test_availability.py` | New tests for all acceptance scenarios (mocked `httpx.get`) |
| `app/clients/inventory.py` | New client: calls inventory, validates response, custom errors + logging |
| `app/main.py` | New `/products/{sku}/availability` route |

---

## Commands and output

**Tests first (expected failures):**
```
cd <project>/storefront-api && ../.venv/bin/python -m pytest tests/test_availability.py -q
# 5 failed, 1 passed
```

**Full checks:**
```
cd <project>/storefront-api && bash scripts/test.sh
== contract freshness
ok: pinned 2.1.0, provider publishes 2.1.0
== tests
........                                                                 [100%]
8 passed in 0.29s
```

**Live inventory (not running):**
```
curl -s -o /dev/null -w "%{http_code}" http://localhost:8081/v2/stock/MUG-001
000
```

**Storefront against missing inventory:**
```
uvicorn app.main:app --host 127.0.0.1 --port 8000
curl -s -w "\nHTTP %{http_code}\n" http://127.0.0.1:8000/products/MUG-001/availability
{"detail":"inventory unavailable"}
HTTP 502
```
(Server log: `inventory unreachable for MUG-001: [Errno 111] Connection refused`)

---

## Could not verify

- **Criterion 6:** No inventory process on `localhost:8081` (or elsewhere in this workspace). Only contract YAML exists under `inventory-service/`; no runnable service to pair with a 200 availability response.

VERIFICATION: {"ran": ["cd <project>/storefront-api && ../.venv/bin/python -m pytest tests/test_availability.py -q", "cd <project>/storefront-api && bash scripts/test.sh", "curl -s -o /dev/null -w \"%{http_code}\" http://localhost:8081/v2/stock/MUG-001", "uvicorn + curl http://127.0.0.1:8000/products/MUG-001/availability"], "result": "passed", "could_not_verify": "End-to-end 200 availability against a running inventory service (nothing listening on localhost:8081)", "missing": "Runnable inventory service or documented INVENTORY_URL and sample SKUs for integration curl"}