"""Galaxy Legal — FastAPI backend entry point."""
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from config import settings
from routes import auth, cases, documents, runs, drafts, drive, health


@asynccontextmanager
async def lifespan(app: FastAPI):
    print(f"[galaxy-legal] starting on Supabase ref {settings.SUPABASE_PROJECT_REF}")
    yield


app = FastAPI(
    title="Galaxy Legal API",
    version="0.1.0",
    description="AI-powered legal workspace backend",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Emergent ingress routes /api/* → backend on :8001.
# All Galaxy Legal routes are namespaced under /api so the same backend
# works locally (port 8000) and behind Emergent's preview URL.
API_PREFIX = "/api"

app.include_router(health.router, prefix=API_PREFIX)
app.include_router(auth.router, prefix=f"{API_PREFIX}/auth", tags=["auth"])
app.include_router(cases.router, prefix=f"{API_PREFIX}/cases", tags=["cases"])
app.include_router(documents.router, prefix=f"{API_PREFIX}/documents", tags=["documents"])
app.include_router(runs.router, prefix=f"{API_PREFIX}/runs", tags=["runs"])
app.include_router(drafts.router, prefix=f"{API_PREFIX}/drafts", tags=["drafts"])
app.include_router(drive.router, prefix=f"{API_PREFIX}/drive", tags=["drive"])


@app.get(f"{API_PREFIX}/")
def root():
    return {"name": "Galaxy Legal API", "version": "0.1.0", "docs": "/docs"}
