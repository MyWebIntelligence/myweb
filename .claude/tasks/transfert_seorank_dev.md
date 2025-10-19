# Plan de développement — Pipeline SEO Rank (v2)

## 1. Contexte & objectifs
- Le legacy propose une commande `land seorank` qui enrichit `expression.seorank` avec le payload brut de l’API SEO Rank (`update_seorank_for_land`).
- L’API actuelle expose un endpoint placeholder (`POST /lands/{id}/seorank`) sans implémentation.
- Objectif : réintroduire la fonctionnalité SEO Rank dans l’architecture moderne (FastAPI + Celery) en respectant la logique legacy et les recommandations `.claude/AGENTS.md`.

## 2. Comportement legacy à reproduire
- **Sélection des expressions** :
  - Filtres : `limit`, `depth`, `http_status` (par défaut `200`), `min_relevance` (par défaut 1), `force_refresh` (ignore cache).
  - Tri par `expression.id`.
- **Appel API** :
  - Endpoint configurable (`settings.seorank_api_base_url`), clé `settings.seorank_api_key` ou `MWI_SEORANK_API_KEY`.
  - Timeout configurable (`settings.seorank_timeout`), sleep entre requêtes (`settings.seorank_request_delay`).
  - En cas d’échec (HTTP != 200, JSON invalide, exception), logs `[seorank]`.
- **Persistance** :
  - Stockage du JSON brut dans `expression.seorank`.
  - Mise à jour d'un timestamp pour marquer le traitement.
- **CLI feedback** :
  - Résumé des paramètres utilisés (limit, depth, http, minrel, force).
  - Message si aucun élément sélectionné.
- **Exports** :
  - `Export._fetch_page_rows_with_seorank` parse le JSON pour enrichir CSV/GEXF (keys dynamiques).

## 2.1. Nouveaux champs de traçabilité (recommandé)
- `expression.seorank_processed_at` (`DateTime`): Horodatage du dernier traitement SEO Rank.
- `expression.seorank_data_source` (`String`): Source des données (ex: `api`, `cache`, `manual`).

## 3. État actuel de l’API
- Modèle : `Expression.seo_rank` (`seorank`) présent (`app/db/models.py:224`).
- Endpoint `POST /api/v1/lands/{land_id}/seorank` → placeholder (retourne “not yet implemented”).
- Aucun service/task dédié (`seorank` absent de `app/services`, `app/tasks`).
- Pompes d’exports (`ExportService`) n’interprètent pas encore `seo_rank`.

## 4. Périmètre du transfert
- Implémenter l’équivalent `update_seorank_for_land` côté services API.
- Offrir un endpoint REST (v1/v2) + tâche Celery pour traitement en arrière-plan avec logs + WebSocket.
- Assurer la compatibilité avec `ExportService` (CSV/GEXF) en parse le JSON comme legacy.
- Ajouter outils de reprocessing + tests automatiques.

## 5. Architecture cible
1. **Service** `app/services/seorank_service.py`
   - Méthode principale `run_batch_for_land(land_id, options)` qui orchestre la sélection, l'appel API et la persistance.
   - Logique de sélection robuste (filtres, `seorank_processed_at` pour `force_refresh`).
   - Persistance par lots (ex: `commit` toutes les 100 expressions) pour optimiser les transactions.
2. **Tâche Celery** `app/tasks/seorank_task.py`
   - Entrée : `land_id`, `limit`, `depth`, `http_status`, `min_relevance`, `force`.
   - Progress tracking via `websocket_manager.send_job_progress` sur le canal `seorank_progress_{job_id}`.
   - Gestion d'erreurs robuste : loggue les échecs par expression sans bloquer le batch.
3. **Endpoints** (v1/v2) `POST /lands/{id}/seorank`
   - Valider permissions (owner).
   - Créer un job de type `enrichment` (plutôt que `crawl_jobs`) via `crud_job`.
   - Retourner `job_id`, `ws_channel`.
4. **Exports** :
   - Adapter `ExportService`/`ExportServiceSync` pour parse `seo_rank` JSON (comme `_legacy/export.py`).
   - Ajout mapping `seorank` → colonnes dynamiques (CSV) & attributs GEXF.
5. **Config** :
   - `app/config.py` : `SEORANK_API_BASE_URL`, `SEORANK_API_KEY`, `SEORANK_TIMEOUT`, `SEORANK_REQUEST_DELAY`, `ENABLE_SEORANK`.
6. **Client API** `app/core/clients/seorank_client.py`
   - Wrapper `httpx` unique conçu pour le moteur synchrone et réutilisable par Celery.

## 6. Étapes de livraison

### Phase 0 — Cadrage (0.5 sprint)
- Confirmer disponibilité clé API (OpenRouter doc `.claude/tasks/OPENROUTER_SETUP.md` pour modèle).
- Spécifier schémas de réponse SEO Rank (exemples legacy).
- Préparer mocks HTTP (respx) + dataset test.

### Phase 1 — Service & client API (1 sprint)
- Créer `SeorankClient` (wrapper `httpx` réutilisable par API et Celery) avec retries + logs `[seorank]`.
- Implémenter `SeorankService` (sélection expressions via SQLAlchemy query, respect filtres).
- Ecrire tests unitaires (mocks HTTP) + snapshot payload.

### Phase 2 — Orchestration (0.5 sprint)
- Tâche Celery `seorank_task` + WebSocket progress.
- Endpoint REST v1/v2 (`lands`) + schéma request (`SeorankRequest`).
- Mise à jour `crud_job` pour gérer le type de job `seorank_enrichment`.

### Phase 3 — Exports & outils (0.5 sprint)
- Adapter `ExportService` pour intégrer `seo_rank` (CSV/GEXF).
- Script CLI `scripts/reprocess_seorank.py` avec options `--dry-run`, `--batch-size`, `--force`.
- Option reprocessing via API/tâche (force).

### Phase 4 — Documentation & QA (0.5 sprint)
- Ajouter `.claude/docs/SEORANK_GUIDE.md` (config, usage, monitoring).
- Tests d'intégration (CLI + API) et tests de non-régression sur les exports.
- Mise à jour `.claude/INDEX_DOCUMENTATION.md`, README.

## 7. Backlog détaillé
| ID | Catégorie | Description | Livrable | Owner |
|----|-----------|-------------|----------|-------|
| SR-01 | Analyse | Spécifier schéma payload SEO Rank + jeux de tests | Rapport + fixtures | QA |
| SR-02 | Core | Client HTTP (`SeorankClient`) avec retries & logs | Module | Dev A |
| SR-03 | Core | `SeorankService.run_batch_for_land` | Service + tests | Dev A |
| SR-04 | Infra | Tâche Celery `seorank_task` + WS progress | Task | DevOps |
| SR-05 | API | Endpoint `POST /lands/{id}/seorank` (v1/v2) | Routes + tests | Dev B |
| SR-06 | Data | Adapter `ExportService` (CSV/GEXF) pour `seo_rank` | Code + tests | Dev B |
| SR-07 | CLI | Script reprocessing (`reprocess_seorank.py`) avec options avancées | Script | DevOps |
| SR-08 | Observabilité | Logs, métriques Prometheus (`seorank_requests_total`) | Dashboard | DevOps |
| SR-09 | Docs | Guide `.claude/docs/SEORANK_GUIDE.md`, README, changelog | Documentation | Tech Writer |

## 8. Critères d’acceptation
- Endpoint `POST /lands/{id}/seorank` lance tâche Celery, retourne job_id, WS.
- Tâche traite filtres `limit/depth/http/minrel/force`, loggage `[seorank]`, met `Expression.seo_rank`.
- Export CSV/GEXF inclut colonnes dynamiques issues du JSON.
- Tests unitaires + intégration couvrant succès, erreur HTTP, JSON invalide.
- Docs à jour + monitoring actif.
- Le script de reprocessing est fonctionnel avec les options `dry-run` et `force`.

## 9. Risques & mitigations
- **Quota API SEO Rank** : throttle via `SEORANK_REQUEST_DELAY`, planifier cache/memoization.
- **JSON schema variable** : utiliser robustesse du parsing (clé optionnelle).
- **Moteur unique** : S'appuyer sur un client HTTP mutualisé pour éviter toute divergence entre API et worker.
- **Sécurité clé API** : stocker dans secrets/ENV, ne pas logger la clé.

## 10. Prochaines étapes immédiates
1. Valider accès API SEO Rank (clé, quota) avec Ops.
2. Lancer SR-01/SR-02 pour sécuriser le client + specs.
3. Mettre en place environnement de mocks HTTP pour tests automatiques.
