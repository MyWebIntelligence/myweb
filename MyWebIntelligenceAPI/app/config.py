"""
Configuration de l'application avec Pydantic BaseSettings
"""

from pydantic_settings import BaseSettings
from typing import List, Optional
import os
from pathlib import Path


class Settings(BaseSettings):
    """Configuration principale de l'application"""
    
    # Configuration de base
    APP_NAME: str = "MyWebIntelligence API"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = False
    
    # Configuration serveur
    HOST: str = "0.0.0.0"
    PORT: int = 8000
    
    # Configuration base de données
    DATABASE_URL: str = "postgresql+asyncpg://mwi_user:mwi_password@localhost:5432/mwi_db"
    DATABASE_ECHO: bool = False
    
    # Configuration Redis
    REDIS_URL: str = "redis://localhost:6379/0"
    
    # Configuration Celery
    CELERY_BROKER_URL: str = "redis://localhost:6379/1"
    CELERY_RESULT_BACKEND: str = "redis://localhost:6379/2"
    
    # Configuration JWT
    JWT_SECRET_KEY: str = "your-secret-key-change-in-production"
    JWT_ALGORITHM: str = "HS256"
    JWT_ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    JWT_REFRESH_TOKEN_EXPIRE_DAYS: int = 7
    
    # Configuration CORS
    CORS_ORIGINS: List[str] = ["http://localhost:3000", "http://localhost:8000"]
    ALLOWED_HOSTS: List[str] = ["localhost", "127.0.0.1"]
    
    # Configuration de sécurité
    API_KEY_HEADER: str = "X-API-Key"
    RATE_LIMIT_PER_MINUTE: int = 60
    
    # Configuration crawling
    DEFAULT_CRAWL_DEPTH: int = 3
    MAX_CRAWL_DEPTH: int = 10
    DEFAULT_CRAWL_LIMIT: int = 1000
    MAX_CRAWL_LIMIT: int = 10000
    
    # Configuration des médias
    MEDIA_STORAGE_PATH: str = "./media"
    MAX_FILE_SIZE_MB: int = 100
    ALLOWED_IMAGE_TYPES: List[str] = ["jpeg", "jpg", "png", "gif", "webp", "svg"]
    ALLOWED_VIDEO_TYPES: List[str] = ["mp4", "webm", "avi", "mov"]
    
    # Configuration export
    EXPORT_STORAGE_PATH: str = "./exports"
    EXPORT_RETENTION_DAYS: int = 7
    
    # Configuration logging
    LOG_LEVEL: str = "INFO"
    LOG_FILE: Optional[str] = None
    
    # Configuration monitoring
    ENABLE_METRICS: bool = True
    METRICS_PORT: int = 8001
    
    # Configuration email (pour notifications)
    SMTP_HOST: Optional[str] = None
    SMTP_PORT: int = 587
    SMTP_USERNAME: Optional[str] = None
    SMTP_PASSWORD: Optional[str] = None
    FROM_EMAIL: Optional[str] = None
    
    def create_directories(self):
        """Créer les répertoires nécessaires s'ils n'existent pas"""
        Path(self.MEDIA_STORAGE_PATH).mkdir(parents=True, exist_ok=True)
        Path(self.EXPORT_STORAGE_PATH).mkdir(parents=True, exist_ok=True)
    
    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "case_sensitive": True,
        "extra": "ignore"
    }


# Instance globale des settings
settings = Settings()

# Créer les répertoires au démarrage
settings.create_directories()
