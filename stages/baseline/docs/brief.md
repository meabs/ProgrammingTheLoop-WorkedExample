# Brief: product availability endpoint (temporary task brief; delete or archive when merged)

Goal: shoppers can see whether a product can be ordered now.

Change: add `GET /products/{sku}/availability` to storefront-api.
Response 200: `{"sku": str, "available": int, "in_stock": bool}` where
`available` = units on hand minus units reserved, as reported by the inventory service.

Acceptance criteria
1. Known SKU with stock: 200, correct `available`, `in_stock: true`.
2. Known SKU with everything reserved: 200, `available: 0`, `in_stock: false`.
3. SKU unknown to the catalogue or to inventory: 404.
4. Inventory unreachable or answering outside its contract: 502, error logged, never a made-up number.
5. `bash scripts/test.sh` passes, including the contract-freshness check.
6. Real behaviour shown against a running inventory service (curl output attached).

Context: the inventory service belongs to another team and is not in this workspace.
Use the pinned contract in `contracts/`. Follow `app/clients/catalogue.py` for client style.

Out of scope: caching, changing the contract, touching `/products/{sku}`, UI.
