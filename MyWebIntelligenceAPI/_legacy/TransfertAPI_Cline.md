# Plan de Migration Complet: MyWebIntelligence Legacy vers MyWebIntelligenceAPI

## 1. Analyse Comparative des Fonctionnalités

### 1.1 Structure Générale

**Legacy (SQLite/Peewee):**
- Base de données SQLite avec WAL mode
- Modèles Peewee pour ORM
- Système de configuration personnalisé via settings.py
- Pipeline de traitement en ligne de commande

**API Actuelle (PostgreSQL/SQLAlchemy):**
- Base de données PostgreSQL avec asyncpg
- Modèles SQLAlchemy avec relations
- Configuration Pydantic avec variables d'environnement
- API RESTful avec FastAPI

### 1.2 Fonctionnalités Principales

| Module | Legacy | API Actuelle | Statut Migration |
|--------|--------|--------------|------------------|
| **Core Functions** | ✅ Complet | ✅ Partiel | 🟡 En cours |
| **Controller System** | ✅ Complet | ✅ Partiel | 🟡 En cours |
| **Export System** | ✅ Complet | ✅ Partiel | 🟡 En cours |
| **Readable Pipeline** | ✅ Complet (Mercury) | ❌ Manquant | 🔴 À migrer |
| **Embedding Pipeline** | ✅ Complet | ❌ Manquant | 🔴 À migrer |
| **Semantic Pipeline** | ✅ Complet | ❌ Manquant | 🔴 À migrer |
| **LLM OpenRouter** | ✅ Complet | ❌ Manquant | 🔴 À migrer |
| **Media Analyzer** | ✅ Complet | ✅ Partiel | 🟡 En cours |
| **CLI System** | ✅ Complet | ❌ Manquant | 🔴 À migrer |

## 2. Analyse Détaillée par Module

### 2.1 Core Functions (.legacy/core.py)

**Fonctionnalités Legacy:**
- ✅ Extraction de contenu avec Trafilatura
- ✅ Media dynamique avec Playwright
- ✅ Gestion SERP API (SerpAPI)
- ✅ SEO Rank API integration
- ✅ NLTK tokenization et stemming
- ✅ Crawling de domaines
- ✅ Consolidation d'expressions
- ✅ Extraction de métadonnées

**Équivalent API Actuelle:**
- ✅ `app/core/content_extractor.py` - Extraction de contenu
- ✅ `app/core/crawler_engine.py` - Crawling d'expressions
- ✅ `app/core/text_processing.py` - Traitement de texte
- ✅ `app/core/media_processor.py` - Analyse média
- ⚠️ `app/core/http_client.py` - Client HTTP basique

**Fonctionnalités Manquantes:**
- ❌ SERP API integration
- ❌ SEO Rank API integration
- ❌ Playwright pour media dynamique
- ❌ Crawling de domaines avancé
- ❌ Fonctions utilitaires CLI (confirm, check_args, etc.)

### 2.2 Controller System (.legacy/controller.py)

**Fonctionnalités Legacy:**
- ✅ DbController (migrate, setup)
- ✅ LandController (medianalyse, seorank, consolidate, list, create, addterm, addurl, urlist, delete, crawl, readable, export, llm_validate)
- ✅ EmbeddingController (generate, similarity, check, reset)
- ✅ DomainController (crawl)
- ✅ TagController (export)
- ✅ HeuristicController (update)

**Équivalent API Actuelle:**
- ✅ API Endpoints dans `app/api/v1/endpoints/`
- ✅ Services dans `app/services/`
- ✅ Tâches Celery dans `app/tasks/`
- ⚠️ CRUD dans `app/crud/`

**Fonctionnalités Manquantes:**
- ❌ Commandes CLI complètes
- ❌ Migration de base de données avancée
- ❌ Validation LLM via OpenRouter
- ❌ Gestion des heuristiques
- ❌ Export de tags avancé

### 2.3 Export System (.legacy/export.py)

**Fonctionnalités Legacy:**
- ✅ Export CSV (pagecsv, fullpagecsv, nodecsv, mediacsv)
- ✅ Export GEXF (pagegexf, nodegexf)
- ✅ Export Corpus (texte brut avec métadonnées)
- ✅ Export Pseudolinks (similarité sémantique)
- ✅ Export Tags (matrix, content)
- ✅ Support SEO Rank dans exports

**Équivalent API Actuelle:**
- ✅ `app/services/export_service.py` - Services d'export
- ✅ `app/api/v1/endpoints/export.py` - Endpoints API
- ✅ `app/tasks/export_task.py` - Tâches d'export
- ⚠️ Formats limités (CSV, GEXF, Corpus)

**Fonctionnalités Manquantes:**
- ❌ Export Pseudolinks
- ❌ Export Tags matrix/content
- ❌ Support SEO Rank dans exports
- ❌ Normalisation des valeurs (na, unknown)
- ❌ Support ZIP pour corpus

### 2.4 Readable Pipeline (.legacy/readable_pipeline.py)

**Fonctionnalités Legacy:**
- ✅ Pipeline Mercury Parser complet
- ✅ Fallback Wayback Machine
- ✅ Stratégies de fusion (mercury_priority, preserve_existing, smart_merge)
- ✅ Extraction médias et liens du markdown
- ✅ Validation LLM via OpenRouter
- ✅ Traitement par batch
- ✅ Gestion des erreurs et retries

**Équivalent API Actuelle:**
- ❌ Aucun équivalent direct
- ⚠️ `app/core/content_extractor.py` - Extraction basique

**Fonctionnalités Manquantes:**
- 🔴 Pipeline Mercury Parser complet
- 🔴 Fallback Wayback Machine
- 🔴 Stratégies de fusion intelligentes
- 🔴 Extraction médias/liens avancée
- 🔴 Validation LLM intégrée

### 2.5 Embedding Pipeline (.legacy/embedding_pipeline.py)

**Fonctionnalités Legacy:**
- ✅ Splitting de paragraphes
- ✅ Génération d'embeddings multi-fournisseurs
- ✅ Similarité cosinus brute-force et LSH
- ✅ Support providers: fake, http, openai, mistral, gemini, huggingface, ollama
- ✅ Batch processing
- ✅ Persistance dans base de données

**Équivalent API Actuelle:**
- ❌ Aucun équivalent direct
- ⚠️ Modèles dans `app/db/models.py` (Paragraph, ParagraphEmbedding, ParagraphSimilarity)

**Fonctionnalités Manquantes:**
- 🔴 Pipeline d'embedding complet
- 🔴 Support multi-fournisseurs
- 🔴 Similarité LSH
- 🔴 Services d'embedding

### 2.6 Semantic Pipeline (.legacy/semantic_pipeline.py)

**Fonctionnalités Legacy:**
- ✅ Similarité sémantique avec ANN (FAISS/brute-force)
- ✅ Classification NLI (entailment/neutral/contradiction)
- ✅ Support CrossEncoder et transformers
- ✅ Batch processing avec fallback
- ✅ Optimisation CPU/MPS

**Équivalent API Actuelle:**
- ❌ Aucun équivalent direct

**Fonctionnalités Manquantes:**
- 🔴 Pipeline sémantique complet
- 🔴 Support NLI
- 🔴 Services de similarité sémantique

### 2.7 LLM OpenRouter (.legacy/llm_openrouter.py)

**Fonctionnalités Legacy:**
- ✅ Validation de pertinence via LLM
- ✅ Prompt engineering en français
- ✅ Support OpenRouter API
- ✅ Normalisation des réponses
- ✅ Gestion des erreurs et budget

**Équivalent API Actuelle:**
- ❌ Aucun équivalent direct

**Fonctionnalités Manquantes:**
- 🔴 Validation LLM intégrée
- 🔴 Services OpenRouter
- 🔴 Prompt engineering

### 2.8 Media Analyzer (.legacy/media_analyzer.py)

**Fonctionnalités Legacy:**
- ✅ Analyse d'images asynchrone
- ✅ Couleurs dominantes avec KMeans
- ✅ Palette web-safe
- ✅ EXIF metadata
- ✅ Hash perceptuel
- ✅ Transparence detection

**Équivalent API Actuelle:**
- ✅ `app/core/media_processor.py` - Analyse média
- ✅ `MediaProcessor.analyze_image()` - Analyse complète
- ✅ Couleurs dominantes et web-safe
- ✅ EXIF metadata
- ✅ Hash perceptuel

**Fonctionnalités Manquantes:**
- ⚠️ Transparence detection précise
- ⚠️ Méthodes helper sur modèle Media

### 2.9 Modèles de Données

**Legacy (SQLite):**
- ✅ Land, Domain, Expression, ExpressionLink
- ✅ Word, LandDictionary
- ✅ Media avec analyse complète
- ✅ Paragraph, ParagraphEmbedding, ParagraphSimilarity
- ✅ Tag, TaggedContent

**API Actuelle (PostgreSQL):**
- ✅ Land, Domain, Expression, ExpressionLink
- ✅ Tag, TaggedContent
- ✅ Media avec analyse basique
- ✅ CrawlJob, User, AccessLog
- ✅ Export
- ⚠️ Word, LandDictionary (partiel)
- ❌ Paragraph, ParagraphEmbedding, ParagraphSimilarity

## 3. Plan de Migration Détaillé

### Phase 1: Infrastructure et Base (Semaine 1-2)

#### 3.1 Modèles de Données
```
Tâches:
- [ ] Ajouter les modèles manquants: Paragraph, ParagraphEmbedding, ParagraphSimilarity
- [ ] Compléter Word et LandDictionary
- [ ] Ajouter les indexes manquants
- [ ] Migrer les méthodes helper des modèles legacy
```

#### 3.2 Configuration et Services de Base
```
Tâches:
- [ ] Intégrer SERP API dans la configuration
- [ ] Intégrer SEO Rank API dans la configuration
- [ ] Configurer Playwright pour media dynamique
- [ ] Ajouter les settings legacy dans config.py
```

### Phase 2: Pipeline de Contenu Avancé (Semaine 3-4)

#### 4.1 Readable Pipeline
```
Tâches:
- [ ] Créer service `app/services/readable_pipeline.py`
- [ ] Intégrer Mercury Parser avec fallback Wayback
- [ ] Implémenter stratégies de fusion
- [ ] Ajouter extraction médias/liens avancée
- [ ] Intégrer validation LLM
- [ ] Créer endpoints API correspondants
```

#### 4.2 Media Analyzer Amélioré
```
Tâches:
- [ ] Ajouter méthode `_has_transparency()` dans MediaProcessor
- [ ] Compléter méthodes helper sur modèle Media
- [ ] Optimiser l'extraction de couleurs
- [ ] Améliorer l'extraction EXIF
```

### Phase 3: Intelligence Artificielle (Semaine 5-6)

#### 5.1 Embedding Pipeline
```
Tâches:
- [ ] Créer service `app/services/embedding_service.py`
- [ ] Implémenter splitting de paragraphes
- [ ] Intégrer fournisseurs multi-embeddings
- [ ] Ajouter similarité cosinus et LSH
- [ ] Créer tâches Celery correspondantes
```

#### 5.2 Semantic Pipeline
```
Tâches:
- [ ] Créer service `app/services/semantic_service.py`
- [ ] Intégrer FAISS pour ANN
- [ ] Implémenter classification NLI
- [ ] Ajouter support CrossEncoder/transformers
- [ ] Créer endpoints API pour similarité
```

#### 5.3 LLM OpenRouter
```
Tâches:
- [ ] Créer service `app/services/llm_service.py`
- [ ] Intégrer OpenRouter API
- [ ] Implémenter prompt engineering
- [ ] Ajouter validation de pertinence
- [ ] Créer endpoints pour validation LLM
```

### Phase 4: Export et CLI Avancé (Semaine 7-8)

#### 6.1 Export Complet
```
Tâches:
- [ ] Ajouter export pseudolinks
- [ ] Ajouter export tags (matrix/content)
- [ ] Intégrer support SEO Rank
- [ ] Ajouter normalisation des valeurs
- [ ] Support ZIP pour corpus
```

#### 6.2 Système CLI
```
Tâches:
- [ ] Créer CLI avec Typer/Click
- [ ] Implémenter commandes DbController
- [ ] Implémenter commandes LandController
- [ ] Implémenter commandes EmbeddingController
- [ ] Implémenter commandes DomainController/TagController
```

### Phase 5: Validation et Documentation (Semaine 9-10)

#### 7.1 Tests et Validation
```
Tâches:
- [ ] Créer tests unitaires pour nouveaux services
- [ ] Créer tests d'intégration
- [ ] Valider parité fonctionnelle
- [ ] Comparer exports legacy vs API
```

#### 7.2 Documentation
```
Tâches:
- [ ] Mettre à jour documentation API
- [ ] Documenter nouveaux endpoints
- [ ] Créer guide migration legacy
- [ ] Mettre à jour README.md
```

## 4. Priorités de Migration

### Priorité Haute (À faire en premier):
1. **Readable Pipeline** - Essentiel pour qualité d'extraction
2. **Media Analyzer** - Amélioration analyse média
3. **Export Complet** - Parité fonctionnelle exports
4. **LLM OpenRouter** - Validation pertinence

### Priorité Moyenne:
1. **Embedding Pipeline** - Intelligence sémantique
2. **Semantic Pipeline** - Analyse relations
3. **Système CLI** - Administration
4. **Modèles de données** - Base complète

### Priorité Basse:
1. **SERP API** - Recherche initiale
2. **SEO Rank** - Métadonnées supplémentaires
3. **Domain Crawling** - Analyse sites

## 5. Dépendances Techniques

### 5.1 Nouvelles Dépendances à Ajouter:
```requirements.txt
# LLM et Embeddings
openai>=1.0.0
sentence-transformers>=2.2.0
transformers>=4.0.0
torch>=1.0.0
faiss-cpu>=1.7.0

# Web et Parsing
playwright>=1.0.0
mercury-parser>=1.0.0

# CLI
typer>=0.9.0
click>=8.0.0

# Utilitaires
lxml>=4.9.0
scikit-learn>=1.0.0
```

### 5.2 Services Externes:
- OpenRouter API (LLM)
- Mercury Parser (extraction)
- SERP API (recherche)
- SEO Rank API (métadonnées)

## 6. Stratégie de Déploiement

### 6.1 Approche Progressive:
1. **Développement parallèle** - Maintenir legacy pendant migration
2. **API Gateway** - Router vers bonne version
3. **Migration données** - Script de transfert
4. **Validation** - Comparaison résultats
5. **Retrait legacy** - Une fois parité atteinte

### 6.2 Points de Contrôle:
- **Semaine 2:** Infrastructure complète
- **Semaine 4:** Pipeline contenu opérationnel
- **Semaine 6:** IA fonctionnelle
- **Semaine 8:** Export/CLI complet
- **Semaine 10:** Validation finale

## 7. Risques et Mitigations

### 7.1 Risques Techniques:
- **Performance:** Embedding/NLI peut être lourd
  - *Mitigation:* Batch processing, CPU optimization
- **Dépendances:** Nouvelles libs peuvent casser
  - *Mitigation:* Pin versions, tests rigoureux
- **Compatibilité:** Différences SQLite/PostgreSQL
  - *Mitigation:* Scripts migration, validation

### 7.2 Risques Fonctionnels:
- **Parité:** Difficile d'atteindre 100% parité
  - *Mitigation:* Focus sur fonctionnalités critiques
- **Utilisateurs:** Habitués à CLI legacy
  - *Mitigation:* CLI équivalent + documentation

## 8. Livrables Attendus

### 8.1 Code:
- Services complets dans `app/services/`
- Endpoints API dans `app/api/v1/endpoints/`
- Tâches Celery dans `app/tasks/`
- Modèles mis à jour dans `app/db/models.py`

### 8.2 Documentation:
- Guide migration legacy → API
- Documentation API complète
- Exemples d'utilisation
- Guide CLI

### 8.3 Tests:
- Tests unitaires pour chaque service
- Tests d'intégration
- Tests de non-régression
- Comparaison résultats legacy/API

## 9. Suivi et Monitoring

### 9.1 Métriques:
- **Couverture fonctionnelle:** % fonctionnalités migrées
- **Performance:** Temps traitement vs legacy
- **Qualité:** Précision extraction/validation
- **Stabilité:** Taux erreurs, uptime

### 9.2 Outils:
- **Monitoring:** Prometheus/Grafana pour métriques
- **Logging:** Structured logging pour debug
- **Alerting:** Notifications erreurs critiques
- **Dashboard:** Vue d'ensemble migration

## 10. Conclusion

Cette migration représente une refonte complète de l'architecture tout en préservant les fonctionnalités essentielles. L'approche par phases permet de maintenir la continuité du service tout en apportant des améliorations significatives en termes de performance, de scalabilité et de maintenabilité.

La clé du succès sera de maintenir un équilibre entre l'innovation apportée par l'API moderne et la fidélité aux fonctionnalités éprouvées du système legacy.
