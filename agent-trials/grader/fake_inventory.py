"""Contract-shaped fake inventory for black-box grading. FAKE_MODE selects the behaviour.
contract: v2.1.0 shape (MUG-001 12/3, TEE-042 2/2); unknown_mug: MUG-001 is 404; outside: 200 with wrong fields;
error500: every call 500."""
import os
from fastapi import FastAPI
from fastapi.responses import JSONResponse

MODE = os.environ.get("FAKE_MODE", "contract")
STOCK = {"MUG-001": (12, 3), "TEE-042": (2, 2)}
app = FastAPI()


@app.get("/{path:path}")
def any_path(path: str):
    if MODE == "error500":
        return JSONResponse({"error": "boom"}, status_code=500)
    if not path.startswith("v2/stock/"):
        return JSONResponse({"detail": "Not Found"}, status_code=404)
    sku = path.removeprefix("v2/stock/")
    if MODE == "outside":
        return {"sku": sku, "quantity": 5}
    if MODE == "unknown_mug" and sku == "MUG-001":
        return JSONResponse({"error": "unknown_sku"}, status_code=404)
    if sku not in STOCK:
        return JSONResponse({"error": "unknown_sku"}, status_code=404)
    on_hand, reserved = STOCK[sku]
    return {"sku": sku, "on_hand": on_hand, "reserved": reserved}
