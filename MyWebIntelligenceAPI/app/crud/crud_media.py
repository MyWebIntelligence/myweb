"""
Opérations CRUD pour les médias.
"""
from typing import Dict, Any, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import delete, select

from app.db import models
from app.schemas.media import MediaCreate

class CRUDMedia:
    async def create_media(self, db: AsyncSession, expression_id: int, media_data: Dict[str, Any]) -> models.Media:
        """
        Crée un nouvel enregistrement de média dans la base de données.
        """
        media_obj = models.Media(
            expression_id=expression_id,
            **media_data
        )
        db.add(media_obj)
        await db.commit()
        await db.refresh(media_obj)
        return media_obj

    async def media_exists(self, db: AsyncSession, expression_id: int, url: str) -> bool:
        """
        Vérifie si un média existe déjà pour une expression donnée.
        """
        query = select(models.Media).where(models.Media.expression_id == expression_id, models.Media.url == url)
        result = await db.execute(query)
        return result.scalar_one_or_none() is not None

    async def delete_media_for_expression(self, db: AsyncSession, expression_id: int):
        """
        Supprime tous les médias associés à une expression.
        """
        stmt = delete(models.Media).where(models.Media.expression_id == expression_id)
        await db.execute(stmt)
        await db.commit()

media = CRUDMedia()
