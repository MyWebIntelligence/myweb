"""
Sessions synchrones pour les tâches Celery et les dépendances sync
"""

from typing import Generator
from sqlalchemy import create_engine
from sqlalchemy.engine.url import make_url
from sqlalchemy.orm import sessionmaker, Session

from app.config import settings

_base_url = make_url(settings.DATABASE_URL)

if "+asyncpg" in _base_url.drivername:
    sync_driver = _base_url.drivername.replace("+asyncpg", "")
else:
    sync_driver = _base_url.drivername

sync_url = _base_url.set(drivername=sync_driver)

engine = create_engine(str(sync_url), pool_pre_ping=True)

SessionLocal = sessionmaker(
    bind=engine,
    autocommit=False,
    autoflush=False,
    expire_on_commit=False,
)


def get_session() -> Session:
    """Retourne une session synchrone non gérée."""
    return SessionLocal()


def get_sync_db() -> Generator[Session, None, None]:
    """Dépendance FastAPI pour obtenir une session synchrone."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
