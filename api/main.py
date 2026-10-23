import sys
import os
import uuid
import asyncio
import hmac
from contextlib import asynccontextmanager

sys.path.append(os.path.dirname(os.path.dirname(__file__)))

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.sessions import SessionMiddleware
from dotenv import load_dotenv

from api.auth.models import User
from api.auth.router import router as auth_router
from api.routes.writing import router as writing_router
from api.routes.reading import router as reading_router
from api.routes.progress import router as progress_router
from api.routes.memory import router as memory_router
from api.routes.speaking import router as speaking_router
from api.routes.listening import router as listening_router
from api.routes.chat import router as chat_router
from api.routes.pedagogy import router as pedagogy_router
from api.routes.schedule import router as schedule_router
from api.routes.telegram import router as telegram_router
from api.routes.whatsapp import router as whatsapp_router
from api.routes.channels import router as channels_router
from app.mcp.memory_server import mcp as memory_mcp
from app.utils.logger import get_logger, set_request_id

load_dotenv()

logger = get_logger("api.main")

# Schema is owned by Alembic — see scripts/migrate.py (runs before the API starts).

# ─── TTS Cache Warmup ─────────────────────────────────────────────────────────

async def warm_tts_cache():
    """
    Pre-generates TTS audio for all Listening tracks on startup.
    Runs in background — does not block app startup.
    After warmup, all Listening track audio loads instantly (0 API cost).
    """
    await asyncio.sleep(10)  # wait for app to fully start

    try:
        from app.services.listening_service import (
            get_all_tracks_summary, get_track_by_id
        )
        from app.services.tts_service import generate_listening_audio

        tracks = get_all_tracks_summary()
        logger.info(f"TTS warmup: pre-generating audio for {len(tracks)} tracks...")

        for track_summary in tracks:
            track = get_track_by_id(track_summary["track_id"])
            if track:
                result = generate_listening_audio(track)
                status = "from cache" if result.get("from_cache") else "generated"
                logger.info(
                    f"TTS warmup: '{track_summary['title']}' — {status}"
                )

        logger.info("TTS warmup complete — all Listening tracks ready")

    except Exception as e:
        logger.warning(f"TTS cache warmup failed (non-blocking): {e}")


# ─── Lifespan ─────────────────────────────────────────────────────────────────

mcp_http_app = memory_mcp.http_app()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Combined lifespan for MCP server + TTS warmup.
    MCP lifespan handles MCP server startup/shutdown.
    TTS warmup pre-generates audio for Listening tracks.
    """
    async with mcp_http_app.lifespan(app):
        asyncio.create_task(warm_tts_cache())
        yield


# ─── FastAPI app ──────────────────────────────────────────────────────────────

app = FastAPI(
    title="BandUp IELTS API",
    description=(
        "AI-powered IELTS coaching with persistent memory, "
        "skill ranking, and conversational tutoring. "
        "BandUp — Grasp English. Retain for life. "
        "Built on Alibaba Cloud Model Studio."
    ),
    version="1.0.0",
    lifespan=lifespan
)

class _RequireBearerToken:
    """Rejects every request unless it carries `Authorization: Bearer $MCP_API_TOKEN`.
    MCP tools take a learner_id argument, so this endpoint is admin-only."""

    def __init__(self, app, token: str | None):
        self.app = app
        self.expected = f"Bearer {token}".encode() if token else None

    async def __call__(self, scope, receive, send):
        if scope["type"] == "http":
            auth = dict(scope.get("headers") or []).get(b"authorization", b"")
            if not self.expected or not hmac.compare_digest(auth, self.expected):
                await JSONResponse({"detail": "Unauthorized"}, status_code=401)(scope, receive, send)
                return
        await self.app(scope, receive, send)


app.mount("/mcp-server", _RequireBearerToken(mcp_http_app, os.getenv("MCP_API_TOKEN")))


# ─── Request ID Middleware ────────────────────────────────────────────────────

@app.middleware("http")
async def request_id_middleware(request: Request, call_next):
    req_id = str(uuid.uuid4())[:8]
    set_request_id(req_id)
    logger.info(f"→ {request.method} {request.url.path}")
    response = await call_next(request)
    logger.info(f"← {response.status_code} {request.url.path}")
    response.headers["X-Request-ID"] = req_id
    return response


# ─── Session middleware ───────────────────────────────────────────────────────

app.add_middleware(
    SessionMiddleware,
    secret_key=os.getenv("JWT_SECRET", "fallback-secret")
)

# ─── CORS ─────────────────────────────────────────────────────────────────────

_frontend_url = os.getenv("FRONTEND_URL", "").strip()
_allow_origins = ["http://localhost:5173", "http://127.0.0.1:5173"]
if _frontend_url and _frontend_url not in _allow_origins:
    _allow_origins.append(_frontend_url)

app.add_middleware(
    CORSMiddleware,
    allow_origins=_allow_origins,
    allow_origin_regex=r"http://(localhost|127\.0\.0\.1)(:\d+)?",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ─── Routers ──────────────────────────────────────────────────────────────────

app.include_router(auth_router)
app.include_router(writing_router)
app.include_router(reading_router)
app.include_router(progress_router)
app.include_router(memory_router)
app.include_router(speaking_router)
app.include_router(listening_router)
app.include_router(chat_router)
app.include_router(pedagogy_router)
app.include_router(schedule_router)
app.include_router(telegram_router)
app.include_router(whatsapp_router)
app.include_router(channels_router)


@app.get("/")
async def root():
    return {
        "message": "BandUp IELTS API",
        "status": "running",
        "inference": "Alibaba Cloud Model Studio",
        "docs": "/docs"
    }


@app.get("/health")
async def health():
    return {"status": "healthy"}
