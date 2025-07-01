"""
Opérations CRUD pour les liens entre expressions.
"""
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import delete, exc
from typing import Optional

from app.db import models

async def create_link(db: AsyncSession, source_id: int, target_id: int) -> Optional[models.ExpressionLink]:
    """
    Crée un lien entre deux expressions.
    """
    link = models.ExpressionLink(source_id=source_id, target_id=target_id)
    try:
        db.add(link)
        await db.commit()
        await db.refresh(link)
        return link
    except exc.IntegrityError:
        # Le lien existe déjà, ce n'est pas une erreur.
        await db.rollback()
        return None

async def delete_links_for_expression(db: AsyncSession, source_id: int):
    """
    Supprime tous les liens sortants d'une expression.
    """
    stmt = delete(models.ExpressionLink).where(models.ExpressionLink.source_id == source_id)
    await db.execute(stmt)
    await db.commit()
