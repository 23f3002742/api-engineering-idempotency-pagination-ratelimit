import time
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

TOTAL_ORDERS = 52
RATE_LIMIT = 16
WINDOW_SECONDS = 10
idempotency_store = {}
rate_store = {}
order_counter = 0


@app.post("/orders")
async def create_order(request: Request):
    key = request.headers.get("Idempotency-Key")
    if key and key in idempotency_store:
        return idempotency_store[key]
    global order_counter
    order_counter += 1
    order = {"id": str(order_counter), "status": "created", "total": TOTAL_ORDERS}
    if key:
        idempotency_store[key] = order
    return JSONResponse(status_code=201, content=order)


@app.get("/orders")
async def list_orders(limit: int = 10, cursor: str | None = None):
    start = 1
    if cursor:
        try:
            start = int(cursor) + 1
        except ValueError:
            start = 1
    end = min(start + limit, TOTAL_ORDERS + 1)
    items = [{"id": i, "product": f"item-{i}"} for i in range(start, end)]
    next_cursor = None
    if end <= TOTAL_ORDERS:
        next_cursor = str(end - 1)
    return {"items": items, "next_cursor": next_cursor}


@app.middleware("http")
async def rate_limiter(request: Request, call_next):
    client_id = request.headers.get("X-Client-Id")
    if client_id:
        now = time.monotonic()
        bucket = rate_store.setdefault(client_id, [])
        while bucket and now - bucket[0] >= WINDOW_SECONDS:
            bucket.pop(0)
        if len(bucket) >= RATE_LIMIT:
            retry_after = max(1, int(WINDOW_SECONDS - (now - bucket[0])) + 1)
            return JSONResponse(
                status_code=429,
                content={"error": "rate_limited"},
                headers={"Retry-After": str(retry_after)},
            )
        bucket.append(now)
    return await call_next(request)


@app.get("/")
async def root():
    return {"status": "ok"}
