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

### 2.1 Structure du Projet (Révisée)

La structure est optimisée pour une séparation claire des responsabilités (SoC) et pour isoler la logique métier portée depuis le crawler original.

```
MyWebIntelligenceAPI/
├── app/
│   ├── __init__.py
│   ├── main.py                 # Point d'entrée FastAPI
│   ├── config.py               # Configuration (Pydantic BaseSettings)
│   ├── dependencies.py         # Dépendances (ex: get_db, get_current_user)
│   │
│   ├── api/
│   │   ├── __init__.py
│   │   ├── router.py             # Routeur principal (v1, v2...)
│   │   └── v1/
│   │       ├── __init__.py
│   │       ├── endpoints/
│   │       │   ├── lands.py
│   │       │   ├── expressions.py
│   │       │   ├── crawling.py
│   │       │   ├── media.py
│   │       │   ├── export.py
│   │       │   └── auth.py
│   │       └── router.py         # Routeur de la v1
│   │
│   ├── core/                   # Logique métier de bas niveau (portage du crawler)
│   │   ├── __init__.py
│   │   ├── crawler_engine.py     # Adaptation de `core.py` et `controller.py`
│   │   ├── media_processor.py    # Adaptation de `media_analyzer.py`
│   │   ├── content_extractor.py  # Adaptation de `readable_pipeline.py`
│   │   └── data_exporter.py      # Adaptation de `export.py`
│   │
│   ├── db/
│   │   ├── __init__.py
│   │   ├── database.py           # SessionFactory et moteur SQLAlchemy
│   │   ├── orm_models.py         # Modèles SQLAlchemy (ex: Land, Expression)
│   │   └── schemas.py            # Modèles Pydantic (ex: LandCreate, LandResponse)
│   │
│   ├── services/                 # Services de haut niveau, orchestrent le `core`
│   │   ├── __init__.py
│   │   ├── land_service.py
│   │   ├── crawl_service.py
│   │   ├── export_service.py
│   │   └── auth_service.py       # Logique d'authentification et gestion user
│   │
│   ├── tasks/                    # Tâches asynchrones (Celery)
│   │   ├── __init__.py
│   │   ├── celery_app.py
│   │   ├── crawl_tasks.py        # Tâches: start_crawl, consolidate, analyze_media
│   │   └── export_tasks.py       # Tâches: generate_csv, generate_gexf
│   │
│   └── utils/
│       ├── __init__.py
│       ├── exceptions.py
│       └── security.py           # Helpers pour JWT, mots de passe
│
├── migrations/                 # Alembic migrations
├── tests/
├── .env.example                # Fichier d'exemple pour les variables d'environnement
├── requirements.txt
├── docker-compose.yml
└── README.md
```

### 2.2 Stack Technologique

- **Framework**: FastAPI 0.104+
- **Database**: PostgreSQL 15+
- **ORM**: SQLAlchemy 2.0 (style asynchrone)
- **Validation & Configuration**: Pydantic v2 (y compris `BaseSettings` pour la config)
- **Async**: `asyncio`, `aiohttp` (pour les requêtes HTTP sortantes)
- **Tâches Asynchrones**: Celery + Redis (ou RabbitMQ)
- **Cache**: Redis
- **WebSocket**: FastAPI WebSocket pour le suivi en temps réel
- **Authentification**: JWT (PyJWT) + `python-multipart` pour les formulaires OAuth2
- **Migrations DB**: Alembic
- **Monitoring**: Prometheus (via `starlette-prometheus`) + Grafana
- **Logging**: `structlog` pour des logs structurés et clairs
- **Testing**: `pytest` + `pytest-asyncio` + `httpx` pour les tests d'API asynchrones

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

#### Crawling Operations & Jobs
```
POST   /api/v1/lands/{land_id}/crawl    # Lancer un crawl (retourne un job_id)
POST   /api/v1/lands/{land_id}/consolidate # Lancer une consolidation (job)
GET    /api/v1/jobs/{job_id}            # Status d'un job (crawl, export, etc.)
POST   /api/v1/jobs/{job_id}/cancel     # Annuler un job
POST   /api/v1/lands/{land_id}/consolidate # Lancer une consolidation (job)
POST   /api/v1/lands/{land_id}/readable # Lancer le pipeline readable (job)
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
WS     /api/v1/ws/jobs/{job_id}         # Updates temps réel pour un job spécifique
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

### 4.1 Phase 1: Foundation & Auth (Semaines 1-4)

**Objectif**: Mettre en place une base applicative solide et sécurisée.

**Semaine 1-2: Setup et Architecture**
- [x] Initialiser le projet FastAPI avec la structure de dossiers révisée.
- [ ] Configurer l'environnement Docker (API, Postgres, Redis) via `docker-compose.yml`.
- [x] Définir les modèles SQLAlchemy dans `db/models.py` et les schémas Pydantic dans `schemas/`.
- [ ] Mettre en place Alembic et générer la migration initiale de la base de données.
- [x] Configurer `config.py` avec Pydantic `BaseSettings` pour gérer les variables d'environnement.

**Semaine 3-4: Authentification et CRUD de base**
- [x] Implémenter le `auth_service.py` en portant la logique de `AdminDB.js` (gestion des utilisateurs, mots de passe hashés, tentatives de connexion, blocage).
- [x] Créer les endpoints d'authentification (`/token`, `/users/me`) avec dépendances de sécurité.
- [x] Implémenter les endpoints CRUD complets pour la ressource `Land`.
- [x] Rédiger les tests unitaires et d'intégration pour l'authentification et les `Lands`.

### 4.2 Phase 2: Porting the Crawling Engine (Semaines 5-8)

**Objectif**: Migrer le cœur fonctionnel du crawler et le rendre accessible via l'API.

**Semaine 5-6: Migration de la Logique Métier**
- [x] Adapter la logique de `core.py` et `controller.py` dans le `services/crawling_service.py` en utilisant des méthodes asynchrones et des sessions SQLAlchemy.
- [x] Mettre en place Celery et créer la première tâche asynchrone: `start_crawl_task`.
- [x] Créer le `crawl_service.py` qui orchestre l'appel à la tâche Celery.
- [x] Implémenter l'endpoint `POST /api/v1/lands/{land_id}/crawl`.
- [ ] Mettre en place le WebSocket pour suivre la progression d'un job.

**Semaine 7-8: Intégration des Pipelines**
- [ ] Porter la logique de `readable_pipeline.py` dans `core/content_extractor.py` et l'intégrer comme une tâche Celery.
- [ ] Porter la logique de `media_analyzer.py` dans `core/media_processor.py` et l'intégrer comme une tâche Celery.
- [ ] Implémenter les endpoints pour lancer la consolidation et l'analyse des médias.
- [ ] Rédiger des tests d'intégration complets pour le pipeline de crawling.

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
   Le déploiement sera orchestré via `docker-compose.yml` pour assurer une modularité maximale.

   **Exemple de `docker-compose.yml` amélioré :**
   ```yaml
   version: '3.8'

   services:
     # API FastAPI
     api:
       build:
         context: .
         dockerfile: Dockerfile # Dockerfile à la racine pour l'API
       command: uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
       volumes:
         - .:/app
       ports:
         - "8000:8000"
       env_file:
         - .env
       depends_on:
         - postgres
         - redis

     # Frontend React (MyWebClient) - Exécuté séparément ou via un autre compose
     # Pour le développement, il est souvent préférable de le lancer localement.
     # Pour la production, il serait servi par un serveur web comme Nginx.

     # Base de données PostgreSQL
     postgres:
       image: postgres:15-alpine
       volumes:
         - postgres_data:/var/lib/postgresql/data/
       ports:
         - "5432:5432" # Exposer pour un accès local si nécessaire
       env_file:
         - .env

     # Redis pour Celery et Caching
     redis:
       image: redis:7-alpine

     # Celery Worker pour les tâches asynchrones
     celery_worker:
       build:
         context: .
         dockerfile: Dockerfile
       command: celery -A app.celery_app worker --loglevel=info
       volumes:
         - .:/app
       env_file:
         - .env
       depends_on:
         - redis
         - postgres

   volumes:
     postgres_data:
   ```
   Cette structure utilise un fichier `.env` pour la configuration, ce qui est une meilleure pratique de sécurité et de flexibilité que de coder en dur les variables dans le fichier `compose`.
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

#### 10.2.1 Coûts de Développement
- **Lead Developer** (12 semaines): €60,000
- **Backend Developers** (2 × 12 semaines): €96,000
- **DevOps Engineer** (6 semaines équivalent): €30,000
- **QA Engineer** (9 semaines équivalent): €27,000
- **Technical Writer** (3 semaines équivalent): €9,000
- **Total Développement**: €222,000

#### 10.2.2 Coûts Infrastructure (Année 1)
- **Cloud Computing** (AWS/GCP): €18,000
- **Database** (PostgreSQL managed): €4,800
- **Monitoring & Logging**: €3,600
- **CDN & Storage**: €2,400
- **Total Infrastructure**: €28,800

#### 10.2.3 Outils & Licences
- **CI/CD & Development Tools**: €6,000
- **Security & Monitoring Tools**: €4,800
- **Documentation Platform**: €1,200
- **Total Outils**: €12,000

#### 10.2.4 Budget Total
- **Développement**: €222,000
- **Infrastructure**: €28,800
- **Outils & Licences**: €12,000
- **Contingence (15%)**: €39,420
- **Total Projet**: €302,220

### 10.3 Risques et Mitigation

| Risque | Impact | Probabilité | Mitigation | Actions Préventives |
|--------|--------|-------------|------------|-------------------|
| Migration de données complexe | Élevé | Moyen | Tests exhaustifs, rollback plan | POC migration, validation incrémentale |
| Performance dégradée | Moyen | Faible | Benchmarks continus, optimisation | Tests de charge précoces, profiling |
| Adoption utilisateurs | Moyen | Moyen | Documentation, support actif | Beta users, feedback loops |
| Sécurité des données | Élevé | Faible | Audits sécurité, best practices | Pen testing, review code |
| Complexité intégration | Moyen | Élevé | Architecture découplée, APIs bien définies | Prototypage, tests d'intégration |
| Dépassement planning | Moyen | Moyen | Buffer temps, priorisation features | Sprints agiles, reviews fréquentes |
| Scalabilité insuffisante | Élevé | Faible | Architecture cloud-native, tests charge | Load testing, architecture review |

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
