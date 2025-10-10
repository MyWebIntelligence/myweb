"""
Point d'entrée principal de l'application FastAPI
"""

from fastapi import FastAPI
from starlette.middleware.cors import CORSMiddleware

from .api.router import api_router
from .api.v2.router import api_router as api_v2_router
from .api.versioning import VersioningMiddleware
from app.config import settings

app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    openapi_url=f"{settings.API_V1_PREFIX}/openapi.json",
)

# Configuration des middlewares
# 1. Versioning middleware (en premier pour traiter les headers de version)
app.add_middleware(VersioningMiddleware)

# 2. Configuration CORS
if settings.CORS_ORIGINS:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[str(origin) for origin in settings.CORS_ORIGINS],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

app.include_router(api_router, prefix=settings.API_V1_PREFIX)
app.include_router(api_v2_router, prefix="/api/v2")

@app.get("/")
def read_root():
    return {"message": f"Welcome to {settings.APP_NAME}"}
