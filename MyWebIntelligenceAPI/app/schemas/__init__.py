"""
Schémas Pydantic pour l'API MyWebIntelligence

Ces schémas sont utilisés pour la validation des données entrantes et sortantes
de l'API, assurant la cohérence et la sécurité des échanges.
"""

from .user import User, UserCreate, UserUpdate, Token, TokenData
from .land import Land, LandCreate, LandUpdate, LandAddTerms
from .domain import Domain, DomainCreate, DomainUpdate
from .expression import Expression, ExpressionCreate, ExpressionUpdate
from .tag import Tag, TagCreate, TagUpdate
from .tagged_content import TaggedContent, TaggedContentCreate, TaggedContentUpdate
from .media import Media, MediaCreate, MediaUpdate
from .job import CrawlJob, CrawlJobCreate, CrawlJobUpdate
from .export import Export, ExportCreate, ExportUpdate
