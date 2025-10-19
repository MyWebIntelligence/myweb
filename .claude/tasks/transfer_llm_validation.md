# Bilan & plan — Transfert LLM Validation (crawl + readable)

## 1. Contexte & objectifs
- Le legacy MyWebIntelligence déclenchait la **validation par LLM via OpenRouter** à deux moments :
  1. **Pendant le crawl** (`_legacy/core.py` lignes ~1860) pour filtrer les expressions non pertinentes (relevance = 0, tout en conservant la trace de traitement via `approved_at`).
  2. **Dans le pipeline readable** (`_legacy/readable_pipeline.py` lignes ~820) via l’option `--llm`, recalculant `relevance`, `validllm`, `validmodel`.
- Le portage API a introduit `LLMValidationService` mais son intégration est incomplète, voire absente, dans les flux de production.
- Objectif : dresser l’état des lieux et planifier les actions pour retrouver la parité fonctionnelle (et profiter de l’infrastructure moderne).

## 2. Comportement legacy à reproduire
- **Crawl** :
  - `is_relevant_via_openrouter(land, expression)` appelé après extraction, **avant** validation finale.
  - Si verdict `False`, alors `expression.relevance = 0` mais l’horodatage `approved_at` reste la marque du passage du pipeline (il ne doit pas être supprimé).
  - Champs mis à jour : `validllm` (`oui`/`non`), `validmodel`, `relevance` (éventuellement 0), et `approved_at` (date de traitement).
- **Pipeline Readable** :
  - Pipeline `run_readable_pipeline(..., llm_enabled)` recalcule pertinence via LLM si `readable` modifié.
  - Conservation de la pertinence locale mais remise à 0 en cas de verdict négatif, tout en laissant `approved_at` indiquer que le contenu a été récupéré.
  - `LandController.llm_validate` permet revalidation manuelle (batch).
- **Options CLI** : `--llm` pour `land readable`, commande `land llm validate`.

## 3. Implémentation actuelle (API)
### 3.1 Crawl
- `CrawlRequest.enable_llm` existe (schemas, endpoints), stocké dans `crawl_jobs.parameters`.
- **Mais** :
  - `tasks.crawl_land_task` ignore le paramètre `enable_llm`.
  - `CrawlerEngine` (async) et `SyncCrawlerEngine` (sync, pour Celery) n'appellent **jamais** `LLMValidationService`.
  - `LLMValidationService` ne dispose que d’une interface `async`, ce qui le rend inutilisable directement par le `SyncCrawlerEngine`.
  - **Conséquence** : `valid_llm`, `valid_model` et `relevance` ne sont jamais mis à jour par le LLM pendant le crawl.

### 3.2 Pipeline Readable
- `ReadableService` (async) :
  - Appelle `LLMValidationService` si `enable_llm=True`.
  - `update_expression_validation` met à jour `valid_llm`, `valid_model`, met `relevance=0` si non pertinent mais conserve `approved_at`. **Ceci est le comportement attendu.**
- `ReadableSimpleService` & `ReadableCeleryService` :
  - Commentaire explicite “skip media/links/LLM validation”.
  - Même avec `enable_llm=True`, aucune validation n’est faite.
  - Recalcul pertinence simplifié (`update_expression_readable_simple`) qui n’interagit pas avec LLM.
- Tâche Celery `process_readable_task` utilise `ReadableSimpleService`, donc **aucune** validation LLM en production.
- Tests d’intégration `test_readable_endpoints` vérifient seulement la sérialisation du flag, pas l’effet.

### 3.3 CLI / Services manquants
- Aucun équivalent API pour `land llm validate` (batch manuel).
- Pas de script de retraitement LLM (contrairement au legacy qui pouvait repasser sur les expressions).

## 4. Écarts & impacts
| Zone | Legacy | API actuelle | Impact |
|---|---|---|---|
| Crawl (async/sync) | LLM gate actif | Flag ignoré, pas de LLM | 🔴 **Critique**. Expressions non filtrées, `valid_llm` toujours `null`. |
| Readable (API directe) | LLM OK | ✅ Parité (service async seulement) | Fonctionnel mais rarement utilisé en pratique. |
| Readable (Celery) | LLM OK (legacy) | ❌ LLM ignoré | 🔴 **Critique**. Le pipeline de production ne valide jamais via LLM. |
| Commande `land llm validate` | Oui | ❌ Absent | Aucun reprocessing manuel possible. |
| Traçabilité | `validllm`, `validmodel` mis à jour | Partiel, dépend du service | Incohérences dans la base de données. |

## 5. Plan d’alignement
### Phase 1 — Fondations (0.5 sprint)
1. **Wrapper Synchrone pour le Service LLM** :
   - Modifier `LLMValidationService` pour y ajouter une méthode `validate_expression_relevance_sync`.
   - Cette méthode sera un simple wrapper qui appellera la version `async` via `asyncio.run()`. Cela évite de dupliquer la logique.
   - Centraliser la gestion des timeouts, retries et du "circuit breaker" (désactivation temporaire si l'API OpenRouter échoue) dans ce service.

### Phase 2 — Intégration crawl (1 sprint)
1. **Propagation du flag `enable_llm`** :
   - `crawling_service.start_crawl_for_land` → stocker flag.
   - `tasks.crawling_task.crawl_land_task` → extraire le flag des paramètres et le passer au moteur.
2. **Modification des deux crawlers (Double Crawler)** :
   - Dans `crawler_engine.py` (async) : après le calcul de pertinence, si `enable_llm` est vrai, appeler `LLMValidationService.validate_expression_relevance`.
   - Dans `crawler_engine_sync.py` (sync) : faire de même en appelant la nouvelle méthode `LLMValidationService.validate_expression_relevance_sync`.
   - **Crucial** : Mettre à jour `valid_llm`, `valid_model`, et `relevance` (à 0 si non pertinent) tout en s'assurant que `approved_at` est bien horodaté pour marquer l'expression comme traitée.
3. **Tests de parité** :
   - Mettre à jour les scripts `test-crawl-async.sh` et `test-crawl-simple.sh` pour inclure un cas avec `enable_llm=true`.
   - Utiliser des mocks (ex: `respx`) pour simuler les réponses d'OpenRouter et éviter des appels réels coûteux.

### Phase 3 — Harmonisation readable (0.5 sprint)
1. **Refactoriser les services `readable`** :
   - Modifier `ReadableSimpleService` et `ReadableCeleryService` pour qu'ils appellent `LLMValidationService` (via son wrapper sync) si `enable_llm=True`.
   - Supprimer les commentaires "skip LLM validation" et implémenter la logique manquante.
2. **Mise à jour de la tâche Celery** :
   - S'assurer que la tâche `process_readable_task` propage bien le paramètre `enable_llm` au service qu'elle utilise.

### Phase 4 — Outils & reprocessing (0.5 sprint)
1. **Endpoint de revalidation** : Créer une route `POST /api/v2/lands/{id}/llm-validate` qui lance une tâche Celery `llm_validate_task`.
2. **Script de reprocessing** : Créer un script `scripts/reprocess_llm_validation.py` pour rejouer la validation sur des expressions existantes (par land, par date, etc.).
3. **Documentation** : Créer un guide `docs/LLM_VALIDATION_GUIDE.md` expliquant la configuration, l'utilisation, les coûts et le monitoring.

### Phase 5 — Observabilité & QA (0.5 sprint)
-1. **Logs Structurés** : Ajouter des logs clairs indiquant la source de l'appel LLM (`crawl`, `readable`, `manual`), le verdict, le modèle utilisé et la latence.
-2. **Métriques Prometheus** : Instrumenter les appels avec des compteurs : `llm_validation_requests_total{source="crawl|readable"}`, `llm_validation_failures_total`, et un histogramme `llm_validation_duration_seconds`.
-3. **Tests de non-régression** :
   - Crawl avec enable_llm true/false.
   - Pipeline readable (via Celery) avec `enable_llm: true`.
   - Exécution du script de reprocessing en `dry-run`.

## 6. Backlog priorisé
| ID | Catégorie | Description | Livrable |
|---|---|---|---|
| LLM-01 | Core | Ajouter un wrapper `_sync` à `LLMValidationService` pour le rendre compatible avec Celery. | Méthode `validate_..._sync` + tests unitaires. |
| LLM-02 | Crawl | Intégrer l'appel au service LLM dans `crawler_engine.py` (async). | Code + tests d'intégration (mock). |
| LLM-03 | Crawl | **[Double Crawler]** Intégrer l'appel dans `crawler_engine_sync.py` (sync). | Code + tests d'intégration (mock). |
| LLM-04 | Readable | Aligner `ReadableSimpleService` et `ReadableCeleryService` pour qu'ils utilisent le service LLM. | Refactoring des services + tests. |
| LLM-05 | API | Créer l'endpoint `POST /lands/{id}/llm-validate` et la tâche Celery associée. | Route API, tâche Celery, schéma Pydantic. |
| LLM-06 | Outils | Créer le script de reprocessing `scripts/reprocess_llm_validation.py`. | Script Python avec CLI (Typer/argparse). |
| LLM-07 | Observabilité | Ajouter les logs structurés et les métriques Prometheus. | Code d'instrumentation + exemples de logs/métriques. |
| LLM-08 | Tests | Créer un script de test de non-régression `test-llm-pipeline.sh`. | Script shell validant le workflow complet. |
| LLM-09 | Docs | Rédiger le guide `docs/LLM_VALIDATION_GUIDE.md`. | Fichier Markdown. |

## 7. Critères d’acceptation
- `enable_llm` influe réellement sur crawl (sync + async) et readable (toutes variantes).
- `valid_llm`, `valid_model`, `relevance` et `approved_at` mis à jour conformément au legacy (pas de remise à null d’`approved_at` lors d’un verdict négatif, seulement `relevance=0`).
- Commande/API de revalidation disponible.
- Tests automatisés (avec mocks) couvrant les cas de succès, échec et timeout de l'API OpenRouter.
- Documentation + monitoring opérationnels.

## 8. Risques & mitigations
- **Coût OpenRouter** : Implémenter un "circuit breaker" qui désactive temporairement les appels LLM si le taux d'erreur dépasse un seuil (ex: 5 échecs consécutifs). Logger un `WARNING` clair.
- **Temps de réponse** : Utiliser des timeouts stricts (`httpx.Timeout`) et exécuter la validation LLM en fin de traitement pour ne pas bloquer les autres extractions.
- **Double crawler** : Appliquer rigoureusement la checklist de `.claude/AGENTS.md` et exécuter les scripts de test `test-crawl-async.sh` et `test-crawl-simple.sh` après modification.
- **Propagation des erreurs** : En cas d’échec de l'API LLM, logger l'erreur, définir `valid_llm='error'`, et **ne jamais** bloquer le reste du pipeline de crawl/readable.

## 9. Prochaines étapes immédiates
1. **Valider le plan** avec l'équipe pour confirmer les priorités.
2. **Commencer par LLM-01** (Wrapper sync), car il débloque l'intégration dans le crawler sync et les services readable de production.
3. **Préparer l'environnement de test** avec des mocks pour l'API OpenRouter (`respx` est un bon candidat) afin de permettre des tests CI/CD rapides et sans coût.
