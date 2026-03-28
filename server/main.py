"""FastAPI server — bridges the sidebar UI and the Python AI pipeline.

Start with:
    py -m uvicorn server.main:app --reload --port 7474

Endpoints:
    GET  /api/signals?symbol=SPY&use_claude=false
    GET  /api/context?symbol=SPY
    GET  /api/journal
    POST /api/scan        { symbol, use_claude, start_date, end_date }
    WS   /ws/signals      real-time push of new signals
"""

import asyncio
import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from server.routes import router
from server.websocket import ws_router, broadcast_loop

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

SIDEBAR_DIST = os.path.join(os.path.dirname(__file__), "..", "sidebar", "dist")


@asynccontextmanager
async def lifespan(app: FastAPI):
    task = asyncio.create_task(broadcast_loop())
    yield
    task.cancel()


app = FastAPI(
    title="SMC AI Trading Analyst",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],   # localhost extension / standalone app
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router, prefix="/api")
app.include_router(ws_router)

# Serve the built sidebar if it exists
if os.path.isdir(SIDEBAR_DIST):
    app.mount("/", StaticFiles(directory=SIDEBAR_DIST, html=True), name="static")
