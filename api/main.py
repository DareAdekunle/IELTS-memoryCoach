import sys
import os

# Make sure Python can find the app/ services from the api/ folder
sys.path.append(os.path.dirname(os.path.dirname(__file__)))

from fastapi import FastAPI
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

load_dotenv()

# Create all tables including the new users table
Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="IELTS MemoryCoach API",
    description="AI-powered IELTS coaching with persistent memory",
    version="1.0.0"
)

# Session middleware required for OAuth state parameter
app.add_middleware(
    SessionMiddleware,
    secret_key=os.getenv("JWT_SECRET", "fallback-secret")
)

# CORS — allows React (port 5173) to call FastAPI (port 8000)
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

# Register routers
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
        "docs": "/docs"
    }


@app.get("/health")
async def health():
    return {"status": "healthy"}