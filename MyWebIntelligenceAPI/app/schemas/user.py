"""
Schémas Pydantic pour les utilisateurs et l'authentification
"""

from pydantic import BaseModel, EmailStr
from typing import Optional
from datetime import datetime

# Schéma de base pour un utilisateur
class UserBase(BaseModel):
    username: str
    email: Optional[EmailStr] = None
    is_active: bool = True
    is_superuser: bool = False

# Schéma pour la création d'un utilisateur
class UserCreate(UserBase):
    password: str

# Schéma pour la mise à jour d'un utilisateur
class UserUpdate(UserBase):
    password: Optional[str] = None

# Schéma pour l'affichage d'un utilisateur (sans mot de passe)
class User(UserBase):
    id: int
    created_at: datetime
    last_login: Optional[datetime] = None

# Schéma pour le token JWT
class Token(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str

# Schéma pour les données contenues dans le token
class TokenData(BaseModel):
    username: Optional[str] = None
