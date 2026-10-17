from fastapi import FastAPI, HTTPException

from app.clients import catalogue

app = FastAPI(title="storefront-api")


@app.get("/products/{sku}")
def read_product(sku: str):
    product = catalogue.get_product(sku)
    if product is None:
        raise HTTPException(status_code=404, detail="unknown product")
    return product
