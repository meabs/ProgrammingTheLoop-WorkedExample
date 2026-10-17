Reading the agent guidance and brief, then exploring the codebase to restate goals and proceed test-first.


Implementing test-first: writing availability tests, then the inventory client and endpoint.


## Goal and acceptance criteria (restated)

Shoppers need a way to see if a product can be ordered now. The API should expose `GET /products/{sku}/availability` returning `{"sku", "available", "in_stock"}`, where `available` is inventory `on_hand − reserved` and `in_stock` is true when `available > 0`. Known SKUs with stock return 200 with correct numbers; fully reserved SKUs return `available: 0` and `in_stock: false`; unknown catalogue or inventory SKUs return 404; inventory failures or invalid responses return 502 with error logging and no invented stock; `bash scripts/test.sh` must pass; live-style behaviour is demonstrated via curl (attached in `docs/availability-curl.txt`).

## Files touched

- `app/clients/inventory.py` (new)
- `app/main.py`
- `tests/test_availability.py` (new)
- `scripts/inventory_stub.py` (new, for curl demo)
- `docs/availability-curl.txt` (new)

## Inventory facts relied on

From `contracts/inventory.openapi.yaml` (version `2.1.0` per `contracts/PINNED`):

- `GET /v2/stock/{sku}`
- 200 body: `sku`, `on_hand`, `reserved` (non-negative integers)
- 404 body: `error: unknown_sku`

## What changed

- **`app/clients/inventory.py`**: HTTP client (`INVENTORY_URL`, default `http://localhost:9000`) calling `/v2/stock/{sku}`, validates the contract-shaped payload, maps 404 to `None`, raises `InventoryServiceError` on transport/other status/invalid JSON (with `logger.error`).
- **`app/main.py`**: New availability route — catalogue check first, then inventory, compute `available` and `in_stock`.
- **`tests/test_availability.py`**: Six tests covering all five functional acceptance criteria via `httpx.MockTransport`.
- **`docs/availability-curl.txt`**: Curl output against uvicorn + contract-shaped stub.

## Commands and output

```bash
cd <project>/storefront-api && ../.venv/bin/python -m pytest tests/test_availability.py -q
```
```
......                                                                   [100%]
6 passed in 0.25s
```
(Tests were added in the same pass as the implementation; they would fail with 404 on the new path before `main.py` and the inventory client existed.)

```bash
bash scripts/test.sh
```
```
== contract freshness
ok: pinned 2.1.0, provider publishes 2.1.0
== tests
........                                                                 [100%]
8 passed in 0.27s
```

Curl demo (also in `docs/availability-curl.txt`):
```
{"sku":"MUG-001","available":9,"in_stock":true}
HTTP 200
{"sku":"TEE-042","available":0,"in_stock":false}
HTTP 200
```

## Could not verify

The real inventory-service application is not in this workspace (only its contract at `../inventory-service/contracts/inventory.openapi.yaml`). Curl used `scripts/inventory_stub.py`, which implements the pinned contract locally, not the other team’s running deployment.

VERIFICATION: {"ran":["bash scripts/test.sh","../.venv/bin/python -m pytest tests/test_availability.py -q","curl demo with inventory_stub.py + uvicorn"],"result":"passed","could_not_verify":"End-to-end call against the inventory team's live service (not present in workspace; used contract-shaped stub instead).","missing":"A runnable inventory-service binary or documented dev URL for criterion 6 without a local stub."}