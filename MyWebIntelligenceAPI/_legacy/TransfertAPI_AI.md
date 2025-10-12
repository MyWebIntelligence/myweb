# Transfert MyWebIntelligence -> MyWebIntelligenceAPI

## 1. Methodologie de verification
- Inventaire automatique des fonctions legacy via AST (FunctionDef et AsyncFunctionDef) sur `MyWebIntelligenceAPI/.legacy`.
- Construction de l'ensemble des fonctions/methodes disponibles dans `MyWebIntelligenceAPI/app` (hors `.legacy`) pour identifier les correspondances exactes ou simplement renommee.
- Verification manuelle des equivalents quand la comparaison par nom est insuffisante (lecture des modules `app/core`, `app/services`, `app/api` et `app/tasks`).
- Synthese des resultats par module puis elaboration d'un plan de migration.

## 2. Synthese du portage des fonctions `.legacy`

| Module legacy | Fonctions | Portage direct | Portage remanie | Restant a migrer |
|---------------|-----------|----------------|-----------------|------------------|
| controller.py | 23        | 0              | 3               | 20               |
| core.py       | 54        | 7              | 0               | 47               |
| media_analyzer.py | 9     | 3              | 5               | 1                |
| export.py     | 23        | 0              | 9               | 14               |
| model.py      | 4         | 0              | 0               | 4                |
| embedding_pipeline.py | 17 | 0             | 0               | 17               |
| readable_pipeline.py | 23 | 0             | 1               | 22               |
| semantic_pipeline.py | 12 | 0             | 2               | 10               |
| llm_openrouter.py | 5     | 0              | 0               | 5                |
| cli.py        | 4         | 0              | 0               | 4                |

> Portage direct = meme nom detectable; Portage remanie = logique apparente mais sous autre structure (ex: methode de service); Restant a migrer = aucune trace dans le code actuel.

## 3. Analyse detaillee par module

### controller.py
- **Couverture actuelle** : les actions CRUD sur les lands sont exposees via les endpoints `app/api/v2/endpoints/lands_v2.py` (list, create, update, delete) et `app/api/v1/endpoints/lands.py` (crawl). Les operations de crawl declenchent `app/services/crawling_service.py` et les taches Celery `app/tasks/crawling_task.py`.
- **Fonctions toujours absentes** : commandes CLI (`DbController.migrate/setup/medianalyse`, `LandController.addterm/addurl/urlist/medianalyse/seorank/consolidate/export/llm_validate`, `DomainController.crawl`, `TagController.export`, `EmbeddingController.*`, `HeuristicController.update`). Aucun equivalent pour le dispatcher CLI ou les workflows batch.
- **Actions recommandees** :
  - Formaliser des endpoints d'administration (ou scripts manage.py) pour remplacer les commandes CLI critiques (migrations, reset).
  - Porter les cas d'usage manquants (ajout de termes, liste d'URL, consolidation, medianalyse) en s'appuyant sur les CRUD `app/crud` et sur les services existants.
  - Documenter la strategie de migration vers Alembic (`alembic upgrade head`) pour couvrir `DbController.migrate/setup`.

### core.py
- **Couverture actuelle** :
  - Extraction de contenu: `app/core/content_extractor.py` (fonctions `get_readable_content`, `get_title`, `get_description`, `get_keywords`, `clean_html`).
  - Relevance dictionnaire: `app/core/text_processing.py` (async `get_land_dictionary`, `expression_relevance`).
  - Crawl expression: `app/core/crawler_engine.py` (classe `CrawlerEngine` avec `_extract_and_save_links`, `_extract_and_save_media`).
  - Media dynamiques et analyses de couleur deplacees dans `app/core/media_processor.py`.
- **Fonctions manquantes** :
  - Toute la couche SERP (`fetch_serpapi_url_list`, `_build_serpapi_params`, `_serpapi_google_domain`, `_advance_date`, etc.).
  - Gestion heuristique (`update_heuristic`, `process_domain_content`, `process_expression_content`, `crawl_domains`).
  - Outils CLI (`confirm`, `check_args`, `split_arg`, `get_arg_option`), utilitaires SEO (`fetch_seorank_for_url`, `update_seorank_for_land`), calculs de tags (`export_land`, `export_tags`), nettoyage NLTK resilient (`_ensure_nltk_tokenizers`, `_cleanup_nltk_resource`).
- **Actions recommandees** :
  - Decider si les fonctions SERP et heuristiques restent pertinentes; si oui, integrer une couche de services dediee (`app/services/search_service.py` par exemple) et creer les modeles pydantic associes.
  - Migrer les utilitaires NLTK et tokenisation en renforcant `app/core/text_processing.py` (ajout d'un fallback `_simple_word_tokenize` et de gestion SSL/offline).
  - Reimplementer les fonctions SEO et export de dictionnaire en s'appuyant sur SQLAlchemy et sur `app/services/export_service.py`.

### media_analyzer.py
- **Couverture actuelle** : `generer_palette_web_safe`, `distance_rgb`, `convertir_vers_web_safe` et l'analyse image sont integrees dans `app/core/media_processor.py` (classe `MediaProcessor.analyze_image`, `_extract_colors`, `_extract_exif`), avec support async et integration CRUD.
- **Manques identifies** : verification explicite de transparence `_has_transparency` (actuellement remplacee par un simple test sur les canaux alpha) et persistance des resultats dans le modele (les helpers du modele legacy n'existent plus).
- **Actions recommandees** : recreer `_has_transparency` pour aligner les resultats, et reactiver la logique de sauvegarde (mise a jour des champs `color_palette`, `exif_data`, `is_processed` dans `app/db/models.py`).

### export.py
- **Couverture actuelle** : les methodes d'ecriture CSV/GEXF/Corpus ont ete transposees sous forme async (`app/services/export_service.py`) et sync (`app/services/export_service_sync.py`) avec des signatures `write_pagecsv`, `write_nodegexf`, `slugify`, etc.
- **Fonctions manquantes** :
  - Orchestration `Export.write`, `get_sql_cursor`, `write_csv`, normalization des payloads SEO (`_fetch_page_rows_with_seorank`, `_parse_seorank_payload`, `_normalize_value`).
  - Export pseudo-liens (`write_pseudolinks*`), `export_tags`, enrichissements metadonnees (`to_metadata`, `get_gexf`, `gexf_node/edge` specifiques).
- **Actions recommandees** :
  - Finaliser `ExportService.export_data` pour couvrir la normalisation SEO et ajoutez la partie tags/pseudolinks.
  - Verifier la correspondance schemas entre Peewee (legacy) et SQLAlchemy (nouveau) pour s'assurer que les requetes reproduisent la meme jointure.

### model.py
- **Etat** : les helpers `Media.get_content_tags_list`, `get_dominant_colors_list`, `get_exif_dict`, `is_conforming` ne sont pas presentes dans `app/db/models.py` (modele SQLAlchemy).
- **Actions recommandees** : reintroduire ces methodes en les adaptant aux types SQLAlchemy (conversion JSON -> liste, validation des couleurs, etc.) ou les deplacer dans `app/core/media_processor.py` si prefere.

### embedding_pipeline.py
- **Etat** : aucun equivalent moderne pour la generation d'embeddings (`_clean_text`, `split_into_paragraphs`, `_openai_embed`, `_compute_similarities_*`, etc.).
- **Actions recommandees** :
  - Definir un service embeddings (`app/services/embedding_service.py`) capable d'appeler les fournisseurs (HTTP, OpenAI, Mistral, HuggingFace, Ollama, Gemini).
  - Reprendre la logique de persistance (`paragraph`, `paragraph_embedding`, `paragraph_similarity`) avec SQLAlchemy.
  - Prevoir une interface asynchrone compatible avec les workers Celery.

### readable_pipeline.py
- **Couverture partielle** : seule l'initialisation du pipeline a un echo (nouvelles fonctions de nettoyage dans `app/core/content_extractor.py`).
- **Fonctions absentes** : gestion des lots `_get_expressions_to_process`, interactions Mercury, merge intelligent `_apply_merge_strategy`, extraction liens/medias detaillee, mise a jour DB `_apply_updates`, calculs de relevance `_calculate_relevance`, stats `_get_pipeline_stats`.
- **Actions recommandees** : creer un service `ReadablePipeline` module (`app/services/readable_pipeline.py`) reprenant l'orchestration, ou enrichir `CrawlerEngine` pour couvrir ces etapes (avec hooks pour Mercury, merge, stats).

### semantic_pipeline.py
- **Etat** : seul le nom des constructeurs d'index apparait via d'autres classes; le moteur complet (chargement FAISS, fallback brute-force, NLI predictor, `run_semantic_similarity`, `_flush_similarities`) est absent.
- **Actions recommandees** :
  - Mettre en place un module `app/services/semantic_similarity.py` integrant FAISS (optionnel) et un fallback numpy/scikit.
  - Porter le scheduler Celery associe et la persistance des similarites (creation des tables via Alembic).

### llm_openrouter.py
- **Etat** : aucune fonction trouvee dans le nouveau code (pas d'appel OpenRouter, normalisation yes/no, prompts).
- **Actions recommandees** : decider si l'usage LLM est maintenu; si oui, integrer un service LLM (`app/services/llm_service.py`) avec parametrage (provider, prompt templating, validation) et stockage des resultats dans les schemas `app/schemas`.

### cli.py
- **Etat** : le CLI legacy (`command_run`, `command_input`, `dispatch`, `call`) est supprime; la commande utilisateur passe par FastAPI.
- **Actions recommandees** : fournir une CLI minimale (Typer/Click) pour les operations d'administration, ou documenter des equivalents (scripts `uvicorn`, `alembic`, jobs Celery).

## 4. Plan de migration recommande

### Phase 0 - Preparation (cadre technique)
- Cartographier les dependances legacy (SERP API, Mercury, FAISS, OpenRouter) et valider les licences/outils encore souhaites.
- Ajouter des tests de non regression sur les exports existants (`tests/test_api_complete.py`, `tests/test_api_crawl.py`) afin de couvrir les chemins critiques avant ajout de nouvelles fonctionnalites.
- Documenter l'utilisation d'Alembic au lieu des commandes Peewee (remplacer `DbController.setup/migrate`).

### Phase 1 - Parite sur les fonctionnalites essentielles
1. **Gestion Lands & Dictionnaires**
   - Completer `crud_land.add_terms_to_land` avec endpoints REST (v1 ou v2) pour couvrir `LandController.addterm/urlist`.
   - Ajouter un endpoint pour ajouter des URL manuellement (creation d'expressions) en reutilisant `crud_expression.get_or_create_expression`.
2. **Exports**
   - Finaliser `ExportService` pour recuperer SEO rank, tags et pseudolinks (porter `_fetch_page_rows_with_seorank`, `_normalize_value`, etc.).
   - Introduire un endpoint/tag export (remplacement de `TagController.export`).
3. **Media analysis**
   - Restaurer `_has_transparency` et les helpers modele afin que les pipelines medias retrouvent les memes donnees que `Media.is_conforming`.

### Phase 2 - Pipelines d'enrichissement
1. **Readable Pipeline**
   - Porter le workflow Mercury (ou son equivalent) dans un service dedie; prevoir un mode degrade lorsque Mercury n'est pas disponible.
   - Reintroduire `_apply_merge_strategy` et les updates atomiques pour garantir la coherence des expressions.
2. **Embedding & Similarity**
   - Implementer `embedding_service` (clients multi-fournisseurs, insertion DB).
   - Porter `compute_paragraph_similarities` avec options brute-force/LSH, et creer les taches Celery afferentes.
3. **Semantic / LLM**
   - Creer le service LLM (OpenRouter) puis relier a un endpoint pour `LandController.llm_validate`.
   - Reintegrer `semantic_pipeline.run_semantic_similarity` avec gestion FAISS fallback.

### Phase 3 - Automatisation & CLI
- Reintroduire les heuristiques domaine (`HeuristicController.update`, `core.update_heuristic`) en s'appuyant sur une table de configuration SQL ou YAML.
- Fournir un CLI ou des scripts `python -m app.cli` couvrant: migrations, reseed, taches lot (medianalyse, reset).
- Mettre a jour la documentation (`README.md`, `.memory/Architecture.md`) avec la nouvelle architecture et les equivalences legacy -> API.

### Phase 4 - Validation & Observabilite
- Etendre les tests d'integration pour couvrir les nouveaux endpoints (lands v2, exports async, pipelines).
- Ajouter de la telemetrie (logs structurés, metrics dans `prometheus.yml`) pour suivre les taches longues (crawl, embeddings, exports).
- Planifier une phase de comparaison de donnees (exports legacy vs API) sur un jeu de lands de reference pour valider la parite fonctionnelle avant demolition definitive du dossier `.legacy`.

## 5. Prochaines etapes
- Valider avec l'equipe produit les fonctionnalites legacy a conserver.
- Prioriser la migration selon l'usage (ex: exports et crawl avant modules LLM).
- Creer des issues ou epics Git correspondant aux phases ci-dessus afin de suivre l'avancement et les dependances.
