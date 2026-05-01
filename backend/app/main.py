"""FastAPI entry point: lifespan, routers, static frontend serving."""

from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from db import queries
from db.database import get_db, init_db
from market.factory import create_market_provider

from .portfolio import compute_total_value
from .routes.auth import router as auth_router
from .routes.chat import router as chat_router
from .routes.health import router as health_router
from .routes.portfolio import router as portfolio_router
from .routes.prices import router as prices_router
from .routes.watchlist import router as watchlist_router

PROJECT_ROOT = Path(__file__).resolve().parents[2]
load_dotenv(PROJECT_ROOT / ".env")

logger = logging.getLogger("finally.app")
logging.basicConfig(level=logging.INFO)

SNAPSHOT_INTERVAL = 30          # seconds between portfolio snapshots
CLEANUP_INTERVAL = 3600         # seconds between old-snapshot purges (1 hour)
SNAPSHOT_RETENTION_DAYS = 7     # delete snapshots older than this


async def _snapshot_loop(app: FastAPI) -> None:
    """Record a portfolio value snapshot every SNAPSHOT_INTERVAL seconds for all users.

    Also purges snapshots older than SNAPSHOT_RETENTION_DAYS once per hour to
    prevent unbounded table growth.
    """
    ticks_until_cleanup = CLEANUP_INTERVAL // SNAPSHOT_INTERVAL
    tick = 0
    while True:
        try:
            await asyncio.sleep(SNAPSHOT_INTERVAL)
            async with get_db(app.state.db_path) as db:
                user_ids = await queries.get_all_user_ids(db)
                for user_id in user_ids:
                    total = await compute_total_value(db, app.state.market, user_id)
                    await queries.record_snapshot(db, user_id, total)
                tick += 1
                if tick >= ticks_until_cleanup:
                    tick = 0
                    for user_id in user_ids:
                        await queries.delete_old_snapshots(
                            db, user_id, keep_days=SNAPSHOT_RETENTION_DAYS
                        )
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("snapshot loop error")


@asynccontextmanager
async def lifespan(app: FastAPI):
    if Path("/app/data").exists():
        db_path = "/app/data/finally.db"
    else:
        db_path = str(PROJECT_ROOT / "db" / "finally.db")

    Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    app.state.db_path = db_path

    await init_db(db_path)

    provider = create_market_provider()
    app.state.market = provider

    async with get_db(db_path) as db:
        all_tickers = await queries.get_all_watchlist_tickers(db)
    provider.set_tickers(all_tickers)
    await provider.start()

    snapshot_task = asyncio.create_task(_snapshot_loop(app))
    app.state.snapshot_task = snapshot_task

    try:
        yield
    finally:
        snapshot_task.cancel()
        try:
            await snapshot_task
        except asyncio.CancelledError:
            pass
        await provider.stop()


app = FastAPI(title="FinAlly", lifespan=lifespan)

app.include_router(auth_router)
app.include_router(health_router)
app.include_router(prices_router)
app.include_router(portfolio_router)
app.include_router(watchlist_router)
app.include_router(chat_router)


STATIC_DIR = Path(__file__).resolve().parent.parent / "static"
if STATIC_DIR.exists():
    app.mount("/_next", StaticFiles(directory=STATIC_DIR / "_next"), name="next-assets")

    @app.get("/{full_path:path}")
    async def spa_catch_all(full_path: str):
        if full_path.startswith("api/"):
            return FileResponse(STATIC_DIR / "404.html", status_code=404)
        candidate = STATIC_DIR / full_path
        if candidate.is_file():
            return FileResponse(candidate)
        html = STATIC_DIR / f"{full_path}.html"
        if html.is_file():
            return FileResponse(html)
        return FileResponse(STATIC_DIR / "index.html")
