"""Catalogue lookups. Kept in-process for the example; real code would call a service."""
PRODUCTS = {"MUG-001": {"sku": "MUG-001", "name": "Loop mug", "price_pence": 899},
            "TEE-042": {"sku": "TEE-042", "name": "Shipyard tee", "price_pence": 1599}}


def get_product(sku: str):
    return PRODUCTS.get(sku)
