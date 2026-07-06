import sys
import os
import uuid

sys.path.append(os.path.dirname(os.path.dirname(__file__)))

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.sessions import SessionMiddleware
from dotenv import load_dotenv

from app.db.database import engine, Base
from api.auth.models import User
from api.auth.router import router as auth_router
from api.routes.writing import router as writing_router
from api.routes.reading import router as reading_router
from api.routes.progress import router as progress_router
from api.routes.memory import router as memory_router
from api.routes.speaking import router as speaking_router
from api.routes.listening import router as listening_router
from api.routes.chat import router as chat_router
from app.mcp.memory_server import mcp as memory_mcp
from app.utils.logger import get_logger, set_request_id

load_dotenv()

logger = get_logger("api.main")

# Create all tables on startup
Base.metadata.create_all(bind=engine)

# ─── MCP app created ONCE ────────────────────────────────────────────────────
mcp_http_app = memory_mcp.http_app()

# ─── FastAPI app ──────────────────────────────────────────────────────────────
app = FastAPI(
    title="IELTS MemoryCoach API",
    description=(
        "AI-powered IELTS coaching with persistent memory, "
        "skill ranking, and conversational tutoring. "
        "Built on Alibaba Cloud Model Studio."
    ),
    version="1.0.0",
    lifespan=mcp_http_app.lifespan
)

# ─── MCP mounted ONCE ────────────────────────────────────────────────────────
app.mount("/mcp-server", mcp_http_app)

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
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://localhost:3000",
        os.getenv("FRONTEND_URL", "http://localhost:5173")
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"]
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


@app.get("/")
async def root():
    return {
        "message": "IELTS MemoryCoach API",
        "status": "running",
        "inference": "Alibaba Cloud Model Studio",
        "docs": "/docs"
    }


@app.get("/health")
async def health():
    return {"status": "healthy"}
