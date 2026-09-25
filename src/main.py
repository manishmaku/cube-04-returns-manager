"""FastAPI application entry point for the Returns Manager service."""

from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.api.health import router as health_router
from src.api.agent import router as agent_router
from src.config import APP_ENV, DEBUG
from src.storage.database import init_db


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan context for startup and shutdown routines."""
    # Ensure SQLite database schema is initialized on startup
    init_db()
    yield


app = FastAPI(
    title="Cube Buildathon 2026 · Returns Manager (RTN)",
    description=(
        "Operational intelligence agent assessing customer returns: "
        "Identity verification, completeness verification, Amazon-scale condition assessment, "
        "and deterministic disposition recommendation."
    ),
    version="1.0.0",
    debug=DEBUG,
    lifespan=lifespan,
)

# CORS Middleware for local development and frontend access
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include API Routers
app.include_router(health_router)
app.include_router(agent_router)


if __name__ == "__main__":
    import uvicorn
    from src.config import HOST, PORT
    uvicorn.run("src.main:app", host=HOST, port=PORT, reload=DEBUG)
