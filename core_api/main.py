# =============================================================================
# EX-DIGITAL — FastAPI Application Factory (main.py)
# =============================================================================
# Entry point for the Core API Engine. Mounts all routers, configures CORS,
# and provides health/status endpoints.
#
# Run:  uvicorn core_api.main:app --host 0.0.0.0 --port 8000 --reload
# =============================================================================

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from database.config import engine, Base
from database.models import User, Course, Enrollment, Session, AttendanceLog, SyncLog  # noqa: F401

from .routes.auth import router as auth_router
from .routes.sessions import router as sessions_router
from .routes.attendance import router as attendance_router
from .settings import settings


# ---------------------------------------------------------------------------
# Lifespan — run table creation on startup (safe — uses IF NOT EXISTS)
# ---------------------------------------------------------------------------

@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(bind=engine)
    yield


# ---------------------------------------------------------------------------
# Application
# ---------------------------------------------------------------------------

app = FastAPI(
    title="EX-DIGITAL Core API",
    description=(
        "Enterprise-grade attendance management system — "
        "Core API Engine handling authentication, session management, "
        "and high-speed rapid-scan attendance processing."
    ),
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

# ---------------------------------------------------------------------------
# CORS — allow the Flask gateway and any frontend to connect
# ---------------------------------------------------------------------------

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Tighten in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------------------------------------------------------
# Mount Routers
# ---------------------------------------------------------------------------

app.include_router(auth_router)
app.include_router(sessions_router)
app.include_router(attendance_router)


# ---------------------------------------------------------------------------
# Health Check
# ---------------------------------------------------------------------------

@app.get("/", tags=["Health"])
def root():
    return {
        "service": "EX-DIGITAL Core API",
        "status": "operational",
        "version": "1.0.0",
        "docs": "/docs",
    }


@app.get("/health", tags=["Health"])
def health_check():
    return {"status": "healthy"}
