"""Inventory service (provider). Owned by another team; the storefront agent cannot read this repo."""
import os
from fastapi import FastAPI
from fastapi.responses import JSONResponse

API_VERSION = os.environ.get("INVENTORY_API_VERSION", "2.1.0")
STOCK = {"MUG-001": (12, 3), "TEE-042": (2, 2)}

app = FastAPI(title="inventory-service", version=API_VERSION)


@app.get("/v2/stock/{sku}")
def get_stock(sku: str):
    if sku not in STOCK:
        return JSONResponse({"error": "unknown_sku"}, status_code=404)
    on_hand, reserved = STOCK[sku]
    if API_VERSION.startswith("3."):
        # v3.0.0 renamed the field (a breaking change, announced in the v3 contract)
        return {"sku": sku, "quantity_on_hand": on_hand, "reserved": reserved}
    return {"sku": sku, "on_hand": on_hand, "reserved": reserved}
