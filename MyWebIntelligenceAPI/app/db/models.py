"""
Modèles SQLAlchemy pour MyWebIntelligence API

Basé sur l'analyse du système existant MyWebClient SQLite.
Ces modèles représentent les entités principales :
- Land : Projets de crawling
- Domain : Sites web analysés
- Expression : Contenu extrait
- Tag : Système de catégorisation hiérarchique
- TaggedContent : Contenu taggé
- Media : Médias associés aux expressions
- ExpressionLink : Liens entre expressions
"""

from sqlalchemy import (
    Column, Integer, String, Text, Float, DateTime, Boolean,
    ForeignKey, Index, JSON, Enum, UniqueConstraint
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import enum

from .base import Base


class CrawlStatus(str, enum.Enum):
    """Statuts de crawling"""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class MediaType(str, enum.Enum):
    """Types de médias"""
    IMAGE = "img"
    VIDEO = "video"
    AUDIO = "audio"
    DOCUMENT = "document"


class User(Base):
    """Modèle utilisateur pour authentification"""
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(50), unique=True, index=True, nullable=False)
    email = Column(String(255), unique=True, index=True, nullable=True)
    hashed_password = Column(String(255), nullable=False)
    is_active = Column(Boolean, default=True)
    is_admin = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    last_login = Column(DateTime(timezone=True), nullable=True)
    failed_attempts = Column(Integer, default=0)
    blocked_until = Column(DateTime(timezone=True), nullable=True)
    reset_token = Column(String(255), nullable=True)
    reset_token_expires = Column(DateTime(timezone=True), nullable=True)

    # Relations
    lands = relationship("Land", back_populates="owner")
    access_logs = relationship("AccessLog", back_populates="user")


class AccessLog(Base):
    """Logs d'accès utilisateur"""
    __tablename__ = "access_logs"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    ip_address = Column(String(45), nullable=True)
    user_agent = Column(Text, nullable=True)
    action = Column(String(100), nullable=True)
    timestamp = Column(DateTime(timezone=True), server_default=func.now())
    success = Column(Boolean, default=True)

    # Relations
    user = relationship("User", back_populates="access_logs")


class Land(Base):
    """
    Modèle Land - Projets de crawling
    
    Un Land représente un projet de crawling avec ses paramètres,
    son état et toutes les expressions qu'il contient.
    """
    __tablename__ = "lands"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False, index=True)
    description = Column(Text, nullable=True)
    
    # Métadonnées du projet
    owner_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # Configuration du crawling
    start_urls = Column(JSON, nullable=True)  # Liste des URLs de départ
    lang = Column(String(255), nullable=True) # Langues du projet (ex: "en,fr")
    crawl_depth = Column(Integer, default=3)
    crawl_limit = Column(Integer, default=1000)
    crawl_status = Column(Enum(CrawlStatus), default=CrawlStatus.PENDING)
    
    # Statistiques
    total_expressions = Column(Integer, default=0)
    total_domains = Column(Integer, default=0)
    last_crawl = Column(DateTime(timezone=True), nullable=True)
    
    # Configuration additionnelle
    settings = Column(JSON, nullable=True)  # Configuration spécifique du crawling

    # Relations
    owner = relationship("User", back_populates="lands")
    expressions = relationship("Expression", back_populates="land", cascade="all, delete-orphan")
    domains = relationship("Domain", back_populates="land", cascade="all, delete-orphan")
    tags = relationship("Tag", back_populates="land", cascade="all, delete-orphan")
    crawl_jobs = relationship("CrawlJob", back_populates="land")
    words = relationship(
        "Word",
        secondary="land_dictionaries",
        backref="lands",
        lazy="dynamic"
    )

    # Index
    __table_args__ = (
        Index('ix_lands_owner_name', 'owner_id', 'name'),
        Index('ix_lands_status', 'crawl_status'),
    )


class Domain(Base):
    """
    Modèle Domain - Sites web analysés
    
    Représente un domaine web avec ses métadonnées extraites.
    """
    __tablename__ = "domains"

    id = Column(Integer, primary_key=True, index=True)
    land_id = Column(Integer, ForeignKey("lands.id"), nullable=False)
    
    # Informations de base
    name = Column(String(255), nullable=False, index=True)  # exemple.com
    title = Column(Text, nullable=True)
    description = Column(Text, nullable=True)
    keywords = Column(Text, nullable=True)
    
    # Métadonnées techniques
    ip_address = Column(String(45), nullable=True)
    robots_txt = Column(Text, nullable=True)
    favicon_url = Column(Text, nullable=True)
    
    # Statistiques
    total_expressions = Column(Integer, default=0)
    avg_http_status = Column(Float, nullable=True)
    first_crawled = Column(DateTime(timezone=True), nullable=True)
    last_crawled = Column(DateTime(timezone=True), nullable=True)
    
    # Analyse de contenu
    language = Column(String(10), nullable=True)
    encoding = Column(String(50), nullable=True)
    
    # Relations
    land = relationship("Land", back_populates="domains")
    expressions = relationship("Expression", back_populates="domain")

    # Index et contraintes
    __table_args__ = (
        Index('ix_domains_land_name', 'land_id', 'name'),
        UniqueConstraint('land_id', 'name', name='uq_domain_land_name'),
    )


class Expression(Base):
    """
    Modèle Expression - Contenu extrait
    
    Représente une page web analysée avec son contenu extrait,
    ses métadonnées et ses relations.
    """
    __tablename__ = "expressions"

    id = Column(Integer, primary_key=True, index=True)
    land_id = Column(Integer, ForeignKey("lands.id"), nullable=False)
    domain_id = Column(Integer, ForeignKey("domains.id"), nullable=False)
    
    # Informations de base
    url = Column(Text, nullable=False, index=True)
    title = Column(Text, nullable=True)
    description = Column(Text, nullable=True)
    keywords = Column(Text, nullable=True)
    
    # Contenu
    content = Column(Text, nullable=True)  # Contenu HTML brut
    readable = Column(Text, nullable=True)  # Contenu lisible (markdown)
    summary = Column(Text, nullable=True)  # Résumé automatique
    
    # Métadonnées de crawling
    http_status = Column(Integer, nullable=True, index=True)
    crawled_at = Column(DateTime(timezone=True), nullable=True)
    readable_at = Column(DateTime(timezone=True), nullable=True)
    depth = Column(Integer, nullable=True, index=True)
    relevance = Column(Float, nullable=True, index=True)
    
    # Analyse de contenu
    language = Column(String(10), nullable=True)
    word_count = Column(Integer, nullable=True)
    reading_time = Column(Integer, nullable=True)  # En minutes
    
    # Métadonnées SEO
    meta_title = Column(Text, nullable=True)
    meta_description = Column(Text, nullable=True)
    meta_keywords = Column(Text, nullable=True)
    canonical_url = Column(Text, nullable=True)
    
    # Headers HTTP
    content_type = Column(String(100), nullable=True)
    content_length = Column(Integer, nullable=True)
    last_modified = Column(DateTime(timezone=True), nullable=True)
    etag = Column(String(255), nullable=True)
    
    # Scores d'analyse
    sentiment_score = Column(Float, nullable=True)  # Analyse de sentiment
    quality_score = Column(Float, nullable=True)   # Score de qualité du contenu
    
    # Configuration
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Relations
    land = relationship("Land", back_populates="expressions")
    domain = relationship("Domain", back_populates="expressions")
    media = relationship("Media", back_populates="expression", cascade="all, delete-orphan")
    tagged_content = relationship("TaggedContent", back_populates="expression", cascade="all, delete-orphan")
    
    # Liens sortants et entrants
    outgoing_links = relationship(
        "ExpressionLink", 
        foreign_keys="ExpressionLink.source_id",
        back_populates="source_expression",
        cascade="all, delete-orphan"
    )
    incoming_links = relationship(
        "ExpressionLink", 
        foreign_keys="ExpressionLink.target_id", 
        back_populates="target_expression"
    )

    # Index
    __table_args__ = (
        Index('ix_expressions_land_status', 'land_id', 'http_status'),
        Index('ix_expressions_relevance_depth', 'relevance', 'depth'),
        Index('ix_expressions_crawled', 'crawled_at'),
        Index('ix_expressions_url_hash', 'url'),  # Pour recherche rapide par URL
    )


class Tag(Base):
    """
    Modèle Tag - Système de catégorisation hiérarchique
    
    Permet une organisation hiérarchique du contenu avec couleurs
    et tri personnalisé.
    """
    __tablename__ = "tags"

    id = Column(Integer, primary_key=True, index=True)
    land_id = Column(Integer, ForeignKey("lands.id"), nullable=False)
    parent_id = Column(Integer, ForeignKey("tags.id"), nullable=True)
    
    # Informations de base
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    color = Column(String(7), nullable=True)  # Couleur hex #RRGGBB
    
    # Organisation
    sorting = Column(Integer, default=0)  # Ordre d'affichage
    level = Column(Integer, default=0)    # Niveau dans la hiérarchie
    path = Column(Text, nullable=True)    # Chemin complet (ex: "Parent / Enfant")
    
    # Métadonnées
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # Statistiques
    usage_count = Column(Integer, default=0)  # Nombre d'utilisations

    # Relations
    land = relationship("Land", back_populates="tags")
    parent = relationship("Tag", remote_side=[id], backref="children")
    tagged_content = relationship("TaggedContent", back_populates="tag", cascade="all, delete-orphan")

    # Index
    __table_args__ = (
        Index('ix_tags_land_parent', 'land_id', 'parent_id'),
        Index('ix_tags_sorting', 'land_id', 'sorting'),
        Index('ix_tags_path', 'path'),
    )


class TaggedContent(Base):
    """
    Modèle TaggedContent - Contenu taggé
    
    Associe des portions de texte d'expressions avec des tags,
    permettant l'annotation fine du contenu.
    """
    __tablename__ = "tagged_content"

    id = Column(Integer, primary_key=True, index=True)
    tag_id = Column(Integer, ForeignKey("tags.id"), nullable=False)
    expression_id = Column(Integer, ForeignKey("expressions.id"), nullable=False)
    
    # Contenu taggé
    text = Column(Text, nullable=False)      # Texte sélectionné
    from_char = Column(Integer, nullable=False)  # Position de début
    to_char = Column(Integer, nullable=False)    # Position de fin
    
    # Contexte additionnel
    context_before = Column(Text, nullable=True)  # Contexte avant
    context_after = Column(Text, nullable=True)   # Contexte après
    
    # Métadonnées
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    created_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    confidence = Column(Float, nullable=True)  # Score de confiance (pour tagging auto)
    
    # Validation
    is_validated = Column(Boolean, default=True)  # Validation humaine
    
    # Relations
    tag = relationship("Tag", back_populates="tagged_content")
    expression = relationship("Expression", back_populates="tagged_content")
    creator = relationship("User")

    # Index
    __table_args__ = (
        Index('ix_tagged_content_expression_tag', 'expression_id', 'tag_id'),
        Index('ix_tagged_content_positions', 'from_char', 'to_char'),
        Index('ix_tagged_content_created', 'created_at'),
    )


class Media(Base):
    """
    Modèle Media - Médias associés aux expressions
    
    Représente les images, vidéos et autres médias extraits
    des pages web avec leurs métadonnées.
    """
    __tablename__ = "media"

    id = Column(Integer, primary_key=True, index=True)
    expression_id = Column(Integer, ForeignKey("expressions.id"), nullable=False)
    
    # Informations de base
    url = Column(Text, nullable=False, index=True)
    type = Column(Enum(MediaType), nullable=False, index=True)
    mime_type = Column(String(100), nullable=True)
    
    # Métadonnées fichier
    filename = Column(String(255), nullable=True)
    file_size = Column(Integer, nullable=True)
    file_path = Column(Text, nullable=True)  # Chemin local si téléchargé
    
    # Métadonnées médias
    width = Column(Integer, nullable=True)
    height = Column(Integer, nullable=True)
    duration = Column(Float, nullable=True)  # Pour vidéos/audio (secondes)
    
    # Métadonnées EXIF/techniques
    exif_data = Column(JSON, nullable=True)
    color_palette = Column(JSON, nullable=True)  # Couleurs dominantes
    
    # Contexte d'extraction
    alt_text = Column(Text, nullable=True)
    caption = Column(Text, nullable=True)
    source_element = Column(String(50), nullable=True)  # img, video, etc.
    
    # Analyse de contenu
    detected_objects = Column(JSON, nullable=True)  # Objets détectés par IA
    text_content = Column(Text, nullable=True)      # Texte extrait (OCR)
    
    # Métadonnées
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    processed_at = Column(DateTime(timezone=True), nullable=True)
    
    # Status de traitement
    is_processed = Column(Boolean, default=False)
    processing_error = Column(Text, nullable=True)

    # Relations
    expression = relationship("Expression", back_populates="media")

    # Index
    __table_args__ = (
        Index('ix_media_expression_type', 'expression_id', 'type'),
        Index('ix_media_url_hash', 'url'),
        Index('ix_media_processed', 'is_processed'),
    )


class ExpressionLink(Base):
    """
    Modèle ExpressionLink - Liens entre expressions
    
    Représente les liens hypertext entre les expressions,
    permettant l'analyse de la structure du site.
    """
    __tablename__ = "expression_links"

    id = Column(Integer, primary_key=True, index=True)
    source_id = Column(Integer, ForeignKey("expressions.id"), nullable=False)
    target_id = Column(Integer, ForeignKey("expressions.id"), nullable=False)
    
    # Métadonnées du lien
    anchor_text = Column(Text, nullable=True)
    link_type = Column(String(50), nullable=True)  # internal, external, etc.
    rel_attribute = Column(String(100), nullable=True)
    
    # Position dans la page source
    position = Column(Integer, nullable=True)
    
    # Métadonnées
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relations
    source_expression = relationship("Expression", foreign_keys=[source_id], back_populates="outgoing_links")
    target_expression = relationship("Expression", foreign_keys=[target_id], back_populates="incoming_links")

    # Index et contraintes
    __table_args__ = (
        Index('ix_expression_links_source', 'source_id'),
        Index('ix_expression_links_target', 'target_id'),
        UniqueConstraint('source_id', 'target_id', name='uq_expression_link'),
    )


class CrawlJob(Base):
    """
    Modèle CrawlJob - Tâches de crawling asynchrones
    
    Représente les jobs de crawling avec leur état et progression.
    """
    __tablename__ = "crawl_jobs"

    id = Column(Integer, primary_key=True, index=True)
    land_id = Column(Integer, ForeignKey("lands.id"), nullable=False)
    
    # Configuration du job
    job_type = Column(String(50), nullable=False)  # crawl, analyze, export, etc.
    parameters = Column(JSON, nullable=True)
    
    # État du job
    status = Column(Enum(CrawlStatus), default=CrawlStatus.PENDING, index=True)
    progress = Column(Float, default=0.0)  # Pourcentage de completion
    current_step = Column(String(255), nullable=True)
    
    # Résultats
    result_data = Column(JSON, nullable=True)
    error_message = Column(Text, nullable=True)
    log_data = Column(JSON, nullable=True)
    
    # Timing
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    started_at = Column(DateTime(timezone=True), nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    
    # Worker info
    worker_id = Column(String(255), nullable=True)
    celery_task_id = Column(String(255), nullable=True, index=True)

    # Relations
    land = relationship("Land", back_populates="crawl_jobs")

    # Index
    __table_args__ = (
        Index('ix_crawl_jobs_status_created', 'status', 'created_at'),
        Index('ix_crawl_jobs_land_status', 'land_id', 'status'),
    )


class Word(Base):
    """Modèle pour les mots et leurs lemmes"""
    __tablename__ = "words"

    id = Column(Integer, primary_key=True, index=True)
    word = Column(String(255), unique=True, nullable=False, index=True)
    lemma = Column(String(255), nullable=False, index=True)

class LandDictionary(Base):
    """Table de liaison pour les dictionnaires de lands"""
    __tablename__ = "land_dictionaries"

    id = Column(Integer, primary_key=True, index=True)
    land_id = Column(Integer, ForeignKey("lands.id"), nullable=False)
    word_id = Column(Integer, ForeignKey("words.id"), nullable=False)

    __table_args__ = (
        UniqueConstraint('land_id', 'word_id', name='uq_land_word'),
    )

class Export(Base):
    """
    Modèle Export - Exports de données
    
    Représente les exports de données générés par l'API.
    """
    __tablename__ = "exports"

    id = Column(Integer, primary_key=True, index=True)
    land_id = Column(Integer, ForeignKey("lands.id"), nullable=False)
    created_by = Column(Integer, ForeignKey("users.id"), nullable=False)
    
    # Configuration de l'export
    export_type = Column(String(50), nullable=False)  # csv, gexf, corpus, etc.
    format_version = Column(String(20), nullable=True)
    parameters = Column(JSON, nullable=True)
    
    # Métadonnées fichier
    filename = Column(String(255), nullable=False)
    file_path = Column(Text, nullable=False)
    file_size = Column(Integer, nullable=True)
    mime_type = Column(String(100), nullable=True)
    
    # Statistiques de l'export
    total_records = Column(Integer, nullable=True)
    compression_ratio = Column(Float, nullable=True)
    
    # État
    status = Column(String(50), default="completed")
    error_message = Column(Text, nullable=True)
    
    # Métadonnées temporelles
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    expires_at = Column(DateTime(timezone=True), nullable=True)
    downloaded_at = Column(DateTime(timezone=True), nullable=True)

    # Relations
    land = relationship("Land")
    creator = relationship("User")

    # Index
    __table_args__ = (
        Index('ix_exports_land_type', 'land_id', 'export_type'),
        Index('ix_exports_created', 'created_at'),
        Index('ix_exports_expires', 'expires_at'),
    )
