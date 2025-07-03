"""
Fonctions CRUD pour les Expressions
"""
from typing import List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload

from app.db import models
from app.schemas.expression import ExpressionCreate, ExpressionUpdate
from app.crud import crud_domain

async def get_expressions_to_crawl(
    db: AsyncSession, land_id: int, limit: int = 0, http_status: Optional[str] = None, depth: Optional[int] = None
) -> List[models.Expression]:
    """
    Récupère une liste d'expressions à crawler pour un land donné.
    """
    query = (
        select(models.Expression)
        .where(models.Expression.land_id == land_id)
        .where(models.Expression.fetched_at.is_(None))
        .order_by(models.Expression.depth.asc(), models.Expression.created_at.asc())
    )

    if http_status:
        query = query.where(models.Expression.http_status == http_status)
    
    if depth is not None:
        query = query.where(models.Expression.depth == depth)

    if limit > 0:
        query = query.limit(limit)

    result = await db.execute(query)
    return list(result.scalars().all())

async def get_or_create_expression(
    db: AsyncSession, land_id: int, url: str, depth: int
) -> Optional[models.Expression]:
    """
    Récupère une expression par URL ou la crée si elle n'existe pas.
    """
    # 1. Vérifier si l'expression existe déjà
    query = select(models.Expression).where(models.Expression.url == url, models.Expression.land_id == land_id)
    result = await db.execute(query)
    db_expression = result.scalar_one_or_none()

    if db_expression:
        return db_expression

    # 2. Si elle n'existe pas, la créer
    domain_name = crud_domain.get_domain_name(url)
    domain = await crud_domain.get_or_create(db, name=domain_name)
    
    expression_in = ExpressionCreate(
        url=url,
        depth=depth,
        land_id=land_id,
        domain_id=domain.id
    )
    
    new_expression = models.Expression(**expression_in.dict())
    db.add(new_expression)
    await db.commit()
    await db.refresh(new_expression)
    return new_expression

async def update_expression(
    db: AsyncSession, *, db_obj: models.Expression, obj_in: ExpressionUpdate
) -> models.Expression:
    """
    Met à jour une expression.
    """
    update_data = obj_in.dict(exclude_unset=True)
    for field, value in update_data.items():
        setattr(db_obj, field, value)
    
    db.add(db_obj)
    await db.commit()
    await db.refresh(db_obj)
    return db_obj

async def get_distinct_depths(db: AsyncSession, land_id: int, http_status: Optional[str] = None) -> List[int]:
    """
    Récupère les profondeurs distinctes des expressions à crawler.
    """
    query = select(models.Expression.depth).where(models.Expression.land_id == land_id).distinct().order_by(models.Expression.depth)
    if http_status:
        query = query.where(models.Expression.http_status == http_status)
    else:
        query = query.where(models.Expression.fetched_at.is_(None))
    
    result = await db.execute(query)
    return list(result.scalars().all())

async def get_by_url_and_land(db: AsyncSession, url: str, land_id: int) -> Optional[models.Expression]:
    """
    Récupère une expression par URL et ID de land.
    """
    query = select(models.Expression).where(models.Expression.url == url, models.Expression.land_id == land_id)
    result = await db.execute(query)
    return result.scalar_one_or_none()

async def create_expression(db: AsyncSession, land_id: int, domain_id: int, url: str, depth: int) -> models.Expression:
    """
    Crée une nouvelle expression.
    """
    expression_in = ExpressionCreate(
        url=url,
        depth=depth,
        land_id=land_id,
        domain_id=domain_id
    )
    
    new_expression = models.Expression(**expression_in.dict())
    db.add(new_expression)
    await db.commit()
    await db.refresh(new_expression)
    return new_expression

async def get_expressions_to_consolidate(
    db: AsyncSession, land_id: int, limit: int = 0, depth: Optional[int] = None
) -> List[models.Expression]:
    """
    Récupère les expressions qui ont déjà été crawlées et qui ont besoin d'être consolidées.
    """
    query = (
        select(models.Expression)
        .where(models.Expression.land_id == land_id)
        .where(models.Expression.fetched_at.isnot(None))
        .order_by(models.Expression.fetched_at.asc())
    )

    if depth is not None:
        query = query.where(models.Expression.depth <= depth)

    if limit > 0:
        query = query.limit(limit)

    result = await db.execute(query)
    return list(result.scalars().all())
