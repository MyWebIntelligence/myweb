"""
Fonctions CRUD pour les Domaines
"""
import re
from urllib.parse import urlparse
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.db import models
from app.schemas.domain import DomainCreate

def get_domain_name(url: str) -> str:
    """
    Extrait le nom de domaine d'une URL, en appliquant des heuristiques si nécessaire.
    """
    try:
        domain_name = urlparse(url).netloc
        # NOTE: Les heuristiques de l'ancien projet ne sont pas portées pour le moment.
        # Elles pourraient être ajoutées ici si nécessaire.
        return domain_name
    except Exception:
        return ""

async def get_or_create_domain(db: AsyncSession, name: str) -> models.Domain:
    """
    Récupère un domaine par nom ou le crée s'il n'existe pas.
    """
    query = select(models.Domain).where(models.Domain.name == name)
    result = await db.execute(query)
    db_domain = result.scalar_one_or_none()

    if db_domain:
        return db_domain

    domain_in = DomainCreate(name=name)
    new_domain = models.Domain(**domain_in.dict())
    db.add(new_domain)
    await db.commit()
    await db.refresh(new_domain)
    return new_domain
