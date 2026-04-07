import os
import secrets
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from fastapi.staticfiles import StaticFiles

from app.api.routes import router as api_router
from app.api.websocket import router as ws_router

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

from app.config import settings
_APP_PASSWORD = (settings.app_password or "").strip()


async def password_middleware(request: Request, call_next):
    """Require APP_PASSWORD via HTTP Basic Auth if the env var is set."""
    if not _APP_PASSWORD or request.url.path == "/health":
        return await call_next(request)

    auth = request.headers.get("Authorization", "")
    if auth.startswith("Basic "):
        import base64
        try:
            decoded = base64.b64decode(auth[6:]).decode()
            _, _, password = decoded.partition(":")
            if secrets.compare_digest(password, _APP_PASSWORD):
                return await call_next(request)
        except Exception:
            pass

    return Response(
        status_code=401,
        headers={"WWW-Authenticate": 'Basic realm="Delphee Lead Hunter"'},
    )


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Run startup logic: initialise the database."""
    from app.config import settings

    if settings.db_backend == "sql":
        from app.db_sql import init_db
        await init_db()
        logger.info("Database initialised (SQL backend)")
    else:
        logger.info("Using Firestore backend — no migration needed")

    yield


app = FastAPI(
    title="Delphee Lead Hunter",
    version="1.0.0",
    description="AI-powered IFRS 9 opportunity scanner for developing markets",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)
app.middleware("http")(password_middleware)

app.include_router(api_router)
app.include_router(ws_router)


@app.get("/health", tags=["system"])
async def health():
    return {"status": "ok", "service": "delphee-lead-hunter"}


# Serve React frontend in production (after `npm run build`)
_frontend_dist = os.path.join(os.path.dirname(__file__), "..", "frontend", "dist")
if os.path.isdir(_frontend_dist):
    app.mount("/", StaticFiles(directory=_frontend_dist, html=True), name="frontend")
