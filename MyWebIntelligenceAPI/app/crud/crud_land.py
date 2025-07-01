"""
Fonctions CRUD pour les Lands
"""
from typing import List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload

from app.db import models
from app.schemas.land import LandCreate, LandUpdate
from app.schemas.job import JobStatus

async def get_land(db: AsyncSession, land_id: int) -> Optional[models.Land]:
    """Récupère un land par son ID."""
    result = await db.execute(select(models.Land).filter(models.Land.id == land_id))
    return result.scalar_one_or_none()

async def get_lands_by_owner(db: AsyncSession, owner_id: int, skip: int = 0, limit: int = 100) -> List[models.Land]:
    """Récupère les lands d'un utilisateur."""
    query = (
        select(models.Land)
        .where(models.Land.owner_id == owner_id)
        .offset(skip)
        .limit(limit)
        .order_by(models.Land.created_at.desc())
    )
    result = await db.execute(query)
    return list(result.scalars().all())

async def create_land(db: AsyncSession, *, land_in: LandCreate, owner_id: int) -> models.Land:
    """Crée un nouveau land."""
    db_land = models.Land(**land_in.dict(), owner_id=owner_id)
    db.add(db_land)
    await db.commit()
    await db.refresh(db_land)
    return db_land

async def update_land(db: AsyncSession, *, db_land: models.Land, land_in: LandUpdate) -> models.Land:
    """Met à jour un land."""
    update_data = land_in.dict(exclude_unset=True)
    for field, value in update_data.items():
        setattr(db_land, field, value)
    db.add(db_land)
    await db.commit()
    await db.refresh(db_land)
    return db_land

async def delete_land(db: AsyncSession, *, land_id: int) -> Optional[models.Land]:
    """Supprime un land."""
    land = await get_land(db, land_id)
    if land:
        await db.delete(land)
        await db.commit()
    return land

async def update_land_status(db: AsyncSession, land_id: int, status: JobStatus):
    """Met à jour le statut de crawling d'un land."""
    land = await get_land(db, land_id)
    if land:
        land.crawl_status = status.value
        await db.commit()
