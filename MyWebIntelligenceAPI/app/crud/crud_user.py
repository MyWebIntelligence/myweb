"""
Fonctions CRUD pour les utilisateurs
"""

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from typing import Optional

from ..db.models import User
from ..schemas.user import UserCreate, UserUpdate
from ..core.security import get_password_hash

async def get_user_by_id(db: AsyncSession, user_id: int) -> Optional[User]:
    """Récupérer un utilisateur par son ID"""
    return await db.get(User, user_id)

async def get_user_by_username(db: AsyncSession, username: str) -> Optional[User]:
    """Récupérer un utilisateur par son nom d'utilisateur"""
    result = await db.execute(select(User).filter(User.username == username))
    return result.scalars().first()

async def get_user_by_email(db: AsyncSession, email: str) -> Optional[User]:
    """Récupérer un utilisateur par son email"""
    result = await db.execute(select(User).filter(User.email == email))
    return result.scalars().first()

async def create_user(db: AsyncSession, *, user_in: UserCreate) -> User:
    """Créer un nouvel utilisateur"""
    hashed_password = get_password_hash(user_in.password)
    db_user = User(
        username=user_in.username,
        email=user_in.email,
        hashed_password=hashed_password,
        is_admin=user_in.is_admin
    )
    db.add(db_user)
    await db.commit()
    await db.refresh(db_user)
    return db_user

async def update_user(db: AsyncSession, *, db_user: User, user_in: UserUpdate) -> User:
    """Mettre à jour un utilisateur"""
    update_data = user_in.model_dump(exclude_unset=True)
    if "password" in update_data and update_data["password"]:
        hashed_password = get_password_hash(update_data["password"])
        del update_data["password"]
        db_user.hashed_password = hashed_password
    
    for field, value in update_data.items():
        setattr(db_user, field, value)
        
    await db.commit()
    await db.refresh(db_user)
    return db_user

async def delete_user(db: AsyncSession, *, user_id: int) -> Optional[User]:
    """Supprimer un utilisateur"""
    user = await get_user_by_id(db, user_id)
    if user:
        await db.delete(user)
        await db.commit()
    return user
