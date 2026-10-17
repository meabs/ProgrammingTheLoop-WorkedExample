from fastapi import FastAPI, HTTPException

from app.clients import catalogue, inventory

app = FastAPI(title="storefront-api")


@app.get("/products/{sku}")
def read_product(sku: str):
    product = catalogue.get_product(sku)
    if product is None:
        raise HTTPException(status_code=404, detail="unknown product")
    return product


@app.get("/products/{sku}/availability")
def read_availability(sku: str):
    if catalogue.get_product(sku) is None:
        raise HTTPException(status_code=404, detail="unknown product")
    try:
        stock = inventory.get_stock(sku)
    except inventory.InventoryUnavailable:
        raise HTTPException(status_code=502, detail="inventory unavailable") from None
    if stock is None:
        raise HTTPException(status_code=404, detail="unknown to inventory")
    on_hand, reserved = stock
    available = max(on_hand - reserved, 0)
    return {"sku": sku, "available": available, "in_stock": available > 0}
