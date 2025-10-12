# Plan de Migration de .legacy vers MyWebIntelligenceAPI

Ce document détaille le plan de migration des fonctionnalités de l'ancien code situé dans le répertoire `.legacy` vers la nouvelle architecture de l'API FastAPI structurée dans `app/`.

## Analyse Globale

L'ancien code est un monolithe procédural basé sur Peewee ORM et une CLI `argparse`. La nouvelle architecture est une API moderne basée sur FastAPI, avec une séparation claire des préoccupations (API, Services, CRUD, Schémas Pydantic, Modèles SQLAlchemy).

La migration consiste principalement à "traduire" la logique métier des anciens `controller.py` et `core.py` en services et opérations CRUD dans la nouvelle structure, et à exposer ces services via des endpoints FastAPI dans `app/api/`.

## Plan de Migration par Fichier `.legacy`

### 1. `model.py` (Peewee)
- **Analyse**: Définit les modèles de données avec Peewee.
- **Correspondance**: `app/db/models.py` (SQLAlchemy) et `app/schemas/` (Pydantic).
- **Statut**: **Terminé**. Les modèles semblent avoir été recréés avec SQLAlchemy (`models.py`) et les schémas de sérialisation/validation avec Pydantic (`schemas/*.py`).
- **Action Requise**: Vérifier que tous les champs et relations de l'ancien `model.py` sont présents dans les nouveaux `app/db/models.py` and `app/schemas/`. Une attention particulière doit être portée aux types de données et aux contraintes (unicité, etc.).

### 2. `cli.py` & `controller.py`
- **Analyse**: Cœur de la logique applicative. `cli.py` parse les arguments et appelle les méthodes statiques dans les différentes classes de `controller.py` (`LandController`, `EmbeddingController`, etc.).
- **Correspondance**: `app/api/router.py`, `app/api/v1/endpoints/*.py`, et `app/services/*.py`.
- **Statut**: **Partiellement Migré**. La structure des routeurs existe, mais il faut vérifier que chaque commande de la CLI a un équivalent en endpoint d'API et que la logique métier a été déplacée dans un service.
- **Plan d'action**:
    1.  **Mapper chaque commande CLI** (`land list`, `land crawl`, `embedding generate`, etc.) à un endpoint FastAPI.
    2.  **`LandController`**:
        - `list`, `create`, `delete`: Doit correspondre à des opérations CRUD dans `app/crud/crud_land.py` exposées via `app/api/v1/endpoints/land.py`.
        - `crawl`, `readable`, `consolidate`, `medianalyse`, `llm_validate`: Ces opérations longues devraient devenir des tâches de fond (background tasks) Celery. La logique doit être déplacée dans `app/services/crawling_service.py` ou des services similaires. L'endpoint de l'API ne fait que déclencher la tâche.
    3.  **`EmbeddingController`**:
        - `generate`, `similarity`: Logique à déplacer dans un `app/services/embedding_service.py`. Doivent être des tâches Celery.
        - `check`, `reset`: Peuvent être des endpoints synchrones simples.
    4.  **`DomainController`**, **`TagController`**, **`HeuristicController`**: La logique doit être migrée vers des services et des endpoints CRUD correspondants.

### 3. `core.py`
- **Analyse**: Contient la logique de bas niveau (crawling, calcul de pertinence, parsing HTML, etc.).
- **Correspondance**: `app/core/`, `app/utils/`, et `app/services/`.
- **Statut**: **Migration en cours**. Des fichiers comme `app/core/crawler_engine.py` existent, mais une vérification exhaustive est nécessaire.
- **Plan d'action**:
    1.  **`crawl_land`, `crawl_expression_*`**: La logique doit être dans `app/core/crawler_engine.py` et `app/services/crawling_service.py`.
    2.  **`expression_relevance`, `get_land_dictionary`**: Logique à placer dans un module utilitaire ou un service de scoring.
    3.  **`add_expression`, `link_expression`**: Doit faire partie de `app/crud/crud_expression.py` et `crud_link.py`.
    4.  **`fetch_serpapi_url_list`, `update_seorank_for_land`**: À migrer dans un service dédié, par exemple `app/services/enrichment_service.py`.
    5.  **Fonctions de parsing (`get_title`, `get_description`, etc.)**: À regrouper dans `app/core/content_extractor.py` ou un module similaire.

### 4. `readable_pipeline.py` & `media_analyzer.py`
- **Analyse**: Pipelines pour l'extraction de contenu lisible (Mercury) et l'analyse de médias.
- **Correspondance**: `app/core/content_extractor.py`, `app/core/media_processor.py`.
- **Statut**: **Probablement à migrer**.
- **Plan d'action**:
    1.  La logique de `run_readable_pipeline` doit être intégrée dans un service, probablement appelé par une tâche Celery. Le code interagissant avec Mercury Parser doit être dans `app/core/content_extractor.py`.
    2.  La classe `MediaAnalyzer` doit être portée dans `app/core/media_processor.py`.

### 5. `embedding_pipeline.py` & `semantic_pipeline.py`
- **Analyse**: Pipelines pour la génération d'embeddings et l'analyse de similarité sémantique (NLI).
- **Correspondance**: `app/services/embedding_service.py`, `app/core/text_processing.py`.
- **Statut**: **Probablement à migrer**.
- **Plan d'action**:
    1.  Toute la logique de génération d'embedding (`_openai_embed`, `_mistral_embed`, etc.) doit être centralisée, potentiellement dans `app/core/text_processing.py`.
    2.  La logique de `generate_embeddings_for_paragraphs` et `compute_paragraph_similarities` doit être dans `app/services/embedding_service.py` et exécutée via des tâches Celery.
    3.  La logique de `run_semantic_similarity` (NLI) doit également être dans `app/services/embedding_service.py` en tant que tâche Celery.

### 6. `llm_openrouter.py`
- **Analyse**: Logique pour appeler l'API OpenRouter pour la validation de pertinence.
- **Correspondance**: `app/services/llm_service.py` ou intégré dans un service d'enrichissement.
- **Statut**: **À migrer**.
- **Plan d'action**: Créer un service `llm_service.py` qui encapsule les appels à OpenRouter. Ce service sera appelé par d'autres services (comme le service de crawling/readable) lorsque la validation LLM est activée.

### 7. `export.py`
- **Analyse**: Exporte les données dans divers formats (CSV, GEXF).
- **Correspondance**: `app/api/v1/endpoints/export.py` et `app/services/export_service.py`.
- **Statut**: **À migrer**.
- **Plan d'action**:
    1.  Créer un `app/services/export_service.py` qui contient la logique de génération des fichiers (CSV, GEXF).
    2.  Créer un endpoint `/api/v1/export/{land_name}` qui prend un type d'export en paramètre.
    3.  Pour les exports longs, l'endpoint devrait déclencher une tâche Celery qui génère le fichier et le stocke. Un autre endpoint permettra de vérifier le statut de la tâche et de télécharger le fichier une fois prêt.

### 8. `queries.py`
- **Analyse**: Fichier vide.
- **Statut**: **Obsolète**.
- **Action Requise**: Aucune. Ignorer.

## Prochaines Étapes Recommandées

1.  **Validation des Modèles et Schémas**: Comparer `model.py` avec `app/db/models.py` et `app/schemas/` pour s'assurer de la parité complète.
2.  **Migration des Services**: Commencer par migrer la logique de `core.py` et `controller.py` dans les services appropriés (`crawling_service`, `embedding_service`, `export_service`).
3.  **Implémentation des Tâches Celery**: Envelopper les opérations longues (crawl, embedding, export) dans des tâches Celery.
4.  **Création des Endpoints API**: Exposer les fonctionnalités des services via des endpoints FastAPI, en suivant les patrons de conception de `app/api/router.py`.
5.  **Tests**: Écrire des tests d'intégration pour chaque endpoint afin de valider que la fonctionnalité migrée se comporte comme attendu.
