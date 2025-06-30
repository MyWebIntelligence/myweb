# MyWebIntelligence API - Plan de Développement Produit (PVD)

## Executive Summary

Ce document présente le plan de développement produit pour la création d'une API FastAPI qui encapsule les fonctionnalités du crawler MyWebIntelligencePython, permettant son intégration avec MyWebClient et ouvrant la voie à un déploiement SaaS scalable.

## 1. Analyse du Système Existant

### 1.1 Architecture Actuelle

#### MyWebIntelligencePython (Crawler)
- **Interface**: CLI (Command Line Interface)
- **Base de données**: SQLite locale
- **Modules principaux**:
  - `cli.py`: Interface ligne de commande
  - `controller.py`: Contrôleurs métier (Land, Domain, Tag, Heuristic)
  - `core.py`: Logique de crawling et traitement
  - `model.py`: Modèles de données Peewee ORM
  - `export.py`: Export des données (CSV, GEXF, Corpus)
  - `media_analyzer.py`: Analyse des médias
  - `readable_pipeline.py`: Pipeline Mercury Parser

#### MyWebClient
- **Frontend**: React.js
- **Backend**: Node.js/Express
- **Communication**: API REST avec le backend Node.js

### 1.2 Fonctionnalités Clés du Crawler

1. **Gestion des Lands** (projets de crawling)
   - Création, suppression, listing
   - Ajout de termes et URLs
   - Crawling avec filtres (profondeur, relevance, HTTP status)
   - Consolidation et analyse

2. **Crawling Avancé**
   - Pipeline robuste: Direct → Trafilatura → Archive.org
   - Extraction de contenu readable
   - Analyse de pertinence basée sur dictionnaire
   - Extraction de médias (statique et dynamique avec Playwright)

3. **Analyse de Médias**
   - Dimensions et métadonnées
   - Analyse des couleurs dominantes
   - Extraction EXIF
   - Hash perceptuel

4. **Export de Données**
   - Formats multiples: CSV, GEXF (Gephi), Corpus ZIP
   - Filtrage par pertinence
   - Export de tags et matrices

## 2. Architecture Cible FastAPI

### 2.1 Structure du Projet

```
MyWebIntelligenceAPI/
├── app/
│   ├── __init__.py
│   ├── main.py                 # Point d'entrée FastAPI
│   ├── config.py               # Configuration
│   ├── dependencies.py         # Dépendances communes
│   │
│   ├── api/
│   │   ├── __init__.py
│   │   ├── v1/
│   │   │   ├── __init__.py
│   │   │   ├── endpoints/
│   │   │   │   ├── __init__.py
│   │   │   │   ├── lands.py
│   │   │   │   ├── domains.py
│   │   │   │   ├── expressions.py
│   │   │   │   ├── crawling.py
│   │   │   │   ├── media.py
│   │   │   │   ├── tags.py
│   │   │   │   ├── export.py
│   │   │   │   ├── auth.py
│   │   │   │   └── websocket.py
│   │   │   └── router.py
│   │   │
│   │   └── v2/              # Future versions
│   │
│   ├── core/                # Logique métier (depuis crawler)
│   │   ├── __init__.py
│   │   ├── crawling.py
│   │   ├── media_analyzer.py
│   │   ├── readable_pipeline.py
│   │   └── export.py
│   │
│   ├── models/
│   │   ├── __init__.py
│   │   ├── database.py      # Configuration DB
│   │   ├── schemas.py       # Pydantic schemas
│   │   └── orm.py          # Modèles SQLAlchemy
│   │
│   ├── services/
│   │   ├── __init__.py
│   │   ├── land_service.py
│   │   ├── crawl_service.py
│   │   ├── media_service.py
│   │   ├── export_service.py
│   │   └── auth_service.py
│   │
│   ├── tasks/              # Tâches asynchrones
│   │   ├── __init__.py
│   │   ├── celery_app.py
│   │   ├── crawl_tasks.py
│   │   └── media_tasks.py
│   │
│   └── utils/
│       ├── __init__.py
│       ├── validators.py
│       ├── exceptions.py
│       └── helpers.py
│
├── migrations/             # Alembic migrations
├── tests/
├── docker/
├── docs/
├── requirements.txt
├── docker-compose.yml
└── README.md
```

### 2.2 Stack Technologique

- **Framework**: FastAPI 0.104+
- **Database**: PostgreSQL 15+
- **ORM**: SQLAlchemy 2.0 (migration depuis Peewee vers PostgreSQL)
- **Validation**: Pydantic v2
- **Async**: asyncio, aiohttp
- **Queue**: Celery + Redis
- **Cache**: Redis
- **WebSocket**: FastAPI WebSocket
- **Auth**: JWT (PyJWT) + OAuth2
- **Monitoring**: Prometheus + Grafana
- **Logging**: structlog
- **Testing**: pytest + pytest-asyncio

## 3. Spécifications API

### 3.1 Endpoints RESTful

#### Lands Management
```
GET    /api/v1/lands                    # Liste des lands
POST   /api/v1/lands                    # Créer un land
GET    /api/v1/lands/{land_id}          # Détails d'un land
PUT    /api/v1/lands/{land_id}          # Modifier un land
DELETE /api/v1/lands/{land_id}          # Supprimer un land
POST   /api/v1/lands/{land_id}/terms    # Ajouter des termes
POST   /api/v1/lands/{land_id}/urls     # Ajouter des URLs
```

#### Crawling Operations
```
POST   /api/v1/lands/{land_id}/crawl    # Lancer un crawl
GET    /api/v1/crawl/jobs/{job_id}      # Status d'un job
POST   /api/v1/crawl/jobs/{job_id}/cancel # Annuler un job
POST   /api/v1/lands/{land_id}/consolidate # Consolider
POST   /api/v1/lands/{land_id}/readable # Pipeline readable
```

#### Expressions
```
GET    /api/v1/expressions              # Liste avec filtres
GET    /api/v1/expressions/{expr_id}    # Détails
PUT    /api/v1/expressions/{expr_id}    # Modifier
DELETE /api/v1/expressions/{expr_id}    # Supprimer
GET    /api/v1/expressions/{expr_id}/media # Médias associés
GET    /api/v1/expressions/{expr_id}/links # Liens sortants
```

#### Media Analysis
```
POST   /api/v1/media/analyze            # Analyser des médias
GET    /api/v1/media/{media_id}         # Détails média
DELETE /api/v1/media/{media_id}         # Supprimer média
POST   /api/v1/lands/{land_id}/media/analyze # Analyse batch
```

#### Export
```
POST   /api/v1/export/csv               # Export CSV
POST   /api/v1/export/gexf              # Export GEXF
POST   /api/v1/export/corpus            # Export Corpus
GET    /api/v1/export/jobs/{job_id}     # Status export
GET    /api/v1/export/download/{file_id} # Télécharger
```

#### WebSocket
```
WS     /api/v1/ws/crawl/{land_id}       # Updates temps réel
```

### 3.2 Schémas Pydantic

```python
# Exemple de schémas principaux
class LandCreate(BaseModel):
    name: str
    description: str
    lang: List[str] = ["fr"]

class LandResponse(BaseModel):
    id: int
    name: str
    description: str
    lang: List[str]
    created_at: datetime
    stats: LandStats

class CrawlJobCreate(BaseModel):
    limit: Optional[int] = None
    depth: Optional[int] = None
    http_status: Optional[str] = None
    
class CrawlJobResponse(BaseModel):
    job_id: str
    status: JobStatus
    progress: float
    processed: int
    errors: int
    eta: Optional[datetime]
```

## 4. Plan de Migration

### 4.1 Phase 1: Foundation (Semaines 1-4)

**Semaine 1-2: Setup et Architecture**
- [ ] Initialiser le projet FastAPI
- [ ] Configurer l'environnement Docker
- [ ] Migrer les modèles Peewee vers SQLAlchemy
- [ ] Créer les schémas Pydantic de base
- [ ] Setup Alembic pour les migrations

**Semaine 3-4: Core API**
- [ ] Implémenter l'authentification JWT
- [ ] Créer les endpoints CRUD de base (Lands, Domains)
- [ ] Intégrer la logique de validation
- [ ] Tests unitaires fondamentaux

### 4.2 Phase 2: Crawling Engine (Semaines 5-8)

**Semaine 5-6: Migration Core**
- [ ] Porter `core.py` en service asynchrone
- [ ] Adapter le pipeline de crawling
- [ ] Intégrer Celery pour les tâches longues
- [ ] WebSocket pour updates temps réel

**Semaine 7-8: Features Avancées**
- [ ] Porter `readable_pipeline.py`
- [ ] Porter `media_analyzer.py`
- [ ] Implémenter la consolidation
- [ ] Tests d'intégration

### 4.3 Phase 3: Export & Analytics (Semaines 9-10)

- [ ] Porter les fonctionnalités d'export
- [ ] Créer les endpoints d'analytics
- [ ] Optimiser les requêtes complexes
- [ ] Caching avec Redis

### 4.4 Phase 4: Production Ready (Semaines 11-12)

- [ ] Monitoring et métriques
- [ ] Documentation OpenAPI complète
- [ ] Tests de charge
- [ ] CI/CD pipeline
- [ ] Déploiement initial

### 4.5 Plan de Migration de Base de Données (SQLite vers PostgreSQL)

La migration de SQLite vers PostgreSQL est une étape clé pour la scalabilité et la robustesse.

**Étapes Clés :**
1.  **Adaptation du Schéma :**
    -   Mettre à jour les modèles SQLAlchemy pour qu'ils soient entièrement compatibles avec les types de données et contraintes de PostgreSQL.
    -   Utiliser Alembic pour générer le schéma cible dans la base de données PostgreSQL.

2.  **Migration des Données :**
    -   Développer un script de migration dédié (en Python, utilisant SQLAlchemy Core ou `pandas`) pour transférer les données de SQLite vers PostgreSQL.
    -   Alternativement, utiliser un outil comme `pgloader` qui peut gérer la migration de manière déclarative.
    -   Le script devra gérer les clés étrangères et les types de données spécifiques.

3.  **Configuration :**
    -   Mettre à jour la configuration de l'application pour utiliser la nouvelle chaîne de connexion PostgreSQL.
    -   Gérer les variables d'environnement pour les credentials de la base de données.

4.  **Validation :**
    -   Effectuer des tests de non-régression pour s'assurer que l'API fonctionne comme prévu avec PostgreSQL.
    -   Valider l'intégrité des données migrées (comptages, vérifications ponctuelles).

## 5. Intégration avec MyWebClient

### 5.1 Stratégie de Migration

1. **Approche Progressive**
   - Maintenir la compatibilité avec l'API Node.js existante
   - Créer un proxy/adapter dans MyWebClient
   - Migration endpoint par endpoint

2. **Nouveau Service Layer**
   ```javascript
   // services/apiService.js
   class APIService {
     constructor(baseURL, version = 'v1') {
       this.client = axios.create({
         baseURL: `${baseURL}/api/${version}`,
         headers: {
           'Content-Type': 'application/json'
         }
       });
     }
     
     // Méthodes pour chaque endpoint
     async getLands() { ... }
     async createLand(data) { ... }
     async startCrawl(landId, options) { ... }
   }
   ```

3. **WebSocket Integration**
   ```javascript
   // services/websocketService.js
   class WebSocketService {
     connectToCrawl(landId, callbacks) {
       this.ws = new WebSocket(`ws://api/v1/ws/crawl/${landId}`);
       this.ws.onmessage = (event) => {
         const data = JSON.parse(event.data);
         callbacks.onProgress?.(data);
       };
     }
   }
   ```

## 6. Considérations de Production

### 6.1 Scalabilité

1. **Architecture Microservices-Ready**
   - Services découplés
   - Communication via message queue
   - Stateless API servers

2. **Architecture Docker Modulaire**
   Le déploiement sera orchestré via `docker-compose.yml` pour assurer une modularité maximale entre les services. Chaque composant sera un service distinct, permettant un développement, un déploiement et une mise à l'échelle indépendants.

   **Exemple de `docker-compose.yml` :**
   ```yaml
   version: '3.8'

   services:
     # API FastAPI (anciennement crawler)
     api:
       build:
         context: .
         dockerfile: docker/api/Dockerfile
       ports:
         - "8000:8000"
       depends_on:
         - postgres
         - redis
       environment:
         - DATABASE_URL=postgresql://user:password@postgres/mydatabase
         - REDIS_URL=redis://redis:6379

     # Frontend React (MyWebClient)
     client:
       build:
         context: ./MyWebClient # Supposant que le client est dans un sous-dossier
         dockerfile: Dockerfile
       ports:
         - "3000:3000"
       depends_on:
         - api

     # Base de données PostgreSQL
     postgres:
       image: postgres:15-alpine
       volumes:
         - postgres_data:/var/lib/postgresql/data/
       environment:
         - POSTGRES_USER=user
         - POSTGRES_PASSWORD=password
         - POSTGRES_DB=mydatabase

     # Redis pour Celery et Caching
     redis:
       image: redis:7-alpine

     # Celery Worker pour les tâches asynchrones
     celery_worker:
       build:
         context: .
         dockerfile: docker/worker/Dockerfile
       command: celery -A app.tasks.celery_app worker --loglevel=info
       depends_on:
         - redis
         - api

   volumes:
     postgres_data:
   ```
   Cette structure garantit que :
   - **L'API, le client et la base de données sont des conteneurs distincts.**
   - Ils peuvent être déployés ensemble ou séparément.
   - La configuration est gérée par des variables d'environnement, assurant la portabilité.

3. **Horizontal Scaling**
   - Load balancer (Nginx/Traefik)
   - Multiple API instances
   - Celery workers auto-scaling
   - Redis cluster

### 6.2 Sécurité

1. **Authentication & Authorization**
   - JWT avec refresh tokens
   - OAuth2 pour intégrations tierces
   - Rate limiting par utilisateur/IP
   - API keys pour accès programmatique

2. **Data Protection**
   - Chiffrement des données sensibles
   - HTTPS obligatoire
   - Validation stricte des inputs
   - Protection CSRF/XSS

### 6.3 Performance

1. **Optimisations**
   - Query optimization avec indexes
   - Pagination efficace
   - Compression des réponses
   - CDN pour les exports

2. **Caching Strategy**
   - Redis pour cache de session
   - Cache des résultats fréquents
   - Invalidation intelligente

## 7. Monitoring & Observability

### 7.1 Métriques

- **Application Metrics**
  - Requêtes par seconde
  - Temps de réponse P50/P95/P99
  - Taux d'erreur
  - Queue length

- **Business Metrics**
  - Nombre de crawls actifs
  - URLs traitées par heure
  - Taux de succès des extractions

### 7.2 Logging

```python
# Configuration structlog
import structlog

logger = structlog.get_logger()

logger.info("crawl_started", 
    land_id=land_id,
    user_id=user_id,
    options=options
)
```

### 7.3 Alerting

- Seuils d'alerte pour:
  - Taux d'erreur > 5%
  - Temps de réponse > 2s
  - Queue backlog > 1000
  - Espace disque < 20%

## 8. Documentation

### 8.1 Documentation Technique

1. **OpenAPI/Swagger**
   - Auto-générée par FastAPI
   - Exemples pour chaque endpoint
   - Schémas détaillés

2. **Developer Guide**
   - Quick start
   - Authentication flow
   - Code examples (Python, JS, cURL)
   - Webhooks guide

### 8.2 Documentation Utilisateur

1. **API Reference**
   - Endpoints groupés par fonctionnalité
   - Cas d'usage courants
   - Limites et quotas

2. **Migration Guide**
   - De CLI vers API
   - Breaking changes
   - Outils de migration

## 9. Roadmap Détaillée

### Q1 2025: MVP
- Core API fonctionnelle
- Crawling de base
- Export CSV/JSON
- Documentation basique

### Q2 2025: Enhanced Features
- Media analysis complet
- WebSocket real-time
- Advanced filtering
- Multi-tenancy

### Q3 2025: Enterprise Features
- SSO/SAML
- Audit logs
- Custom workflows
- API versioning

### Q4 2025: Scale & Optimize
- Performance tuning
- Global deployment
- Advanced analytics
- ML integration

## 10. Estimations et Ressources

### 10.1 Équipe Requise

- **Lead Developer**: 1 (full-time)
- **Backend Developers**: 2 (full-time)
- **DevOps Engineer**: 1 (50%)
- **QA Engineer**: 1 (75%)
- **Technical Writer**: 1 (25%)

### 10.2 Budget Estimé

- **Développement**: 12 semaines × 5 personnes = ~€150,000
- **Infrastructure** (année 1): ~€24,000
- **Outils & Licences**: ~€10,000
- **Total**: ~€184,000

### 10.3 Risques et Mitigation

| Risque | Impact | Probabilité | Mitigation |
|--------|--------|-------------|------------|
| Migration de données complexe | Élevé | Moyen | Tests exhaustifs, rollback plan |
| Performance dégradée | Moyen | Faible | Benchmarks continus, optimisation |
| Adoption utilisateurs | Moyen | Moyen | Documentation, support actif |
| Sécurité des données | Élevé | Faible | Audits sécurité, best practices |

## 11. Critères de Succès

### 11.1 KPIs Techniques
- ✓ 100% des fonctionnalités CLI portées
- ✓ Temps de réponse < 200ms (P95)
- ✓ Disponibilité > 99.9%
- ✓ Zero data loss

### 11.2 KPIs Business
- ✓ 50+ utilisateurs actifs (mois 3)
- ✓ 1M+ URLs crawlées (mois 6)
- ✓ 5+ intégrations tierces
- ✓ NPS > 8

## 12. Conclusion

Ce plan de développement produit fournit une feuille de route complète pour transformer MyWebIntelligencePython en une API moderne et scalable. L'approche progressive permet de minimiser les risques tout en offrant rapidement de la valeur aux utilisateurs.

La migration vers FastAPI apportera:
- **Performance**: Traitement asynchrone natif
- **Scalabilité**: Architecture cloud-native
- **Maintenabilité**: Code moderne et bien structuré
- **Extensibilité**: Base solide pour futures fonctionnalités

Le succès de ce projet ouvrira la voie à une offre SaaS complète pour l'intelligence web.
