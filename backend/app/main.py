import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.health import router as health_router
from app.api.tasks import router as tasks_router
from app.api.websocket import router as websocket_router, subscribe_to_events


@asynccontextmanager
async def lifespan(app: FastAPI):
    subscriber = asyncio.create_task(subscribe_to_events())
    try:
        yield
    finally:
        subscriber.cancel()
        await asyncio.gather(subscriber, return_exceptions=True)


app = FastAPI(title="AI Task Bot", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health_router, prefix="/api")
app.include_router(tasks_router, prefix="/api")
app.include_router(websocket_router)