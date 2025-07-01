"""
Fixtures Pytest pour les tests
"""

import pytest
from typing import AsyncGenerator
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.main import app
from app.db.base import Base, get_db
from app.config import settings

# Utiliser une base de données de test en mémoire
TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"

engine = create_async_engine(TEST_DATABASE_URL, echo=True)
TestingSessionLocal = async_sessionmaker(autocommit=False, autoflush=False, bind=engine, class_=AsyncSession)

async def override_get_db() -> AsyncGenerator[AsyncSession, None]:
    """
    Dépendance pour surcharger la base de données de production
    avec une base de données de test.
    """
    async with TestingSessionLocal() as session:
        yield session

app.dependency_overrides[get_db] = override_get_db

@pytest.fixture(scope="session")
async def db() -> AsyncGenerator[AsyncSession, None]:
    """
    Fixture pour la base de données de test.
    """
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    async with TestingSessionLocal() as session:
        yield session
    
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)

@pytest.fixture(scope="session")
async def client(db: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    """
    Fixture pour le client HTTP de test.
    """
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c
