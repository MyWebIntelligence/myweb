# Plan de remise à niveau — Validation LLM (crawler sync + readable)

## 1. Objectif
Réactiver la validation des expressions via LLM (OpenRouter) dans la V2 qui tourne exclusivement avec le moteur synchrone `SyncCrawlerEngine`.

## 2. État actuel
- Le flag `enable_llm` est stocké dans les jobs de crawl mais ignoré par le moteur.
- `LLMValidationService` existe mais ne propose qu'une interface orientée coroutine.
- Le pipeline readable côté Celery appelle encore une version simplifiée sans contrôle LLM.
- Aucun script de retraitement n'est disponible pour relancer la validation.

## 3. Actions à mener
### 3.1 Service LLM
- Ajouter `validate_expression_relevance_sync(expression, land, settings)` qui encapsule l'appel OpenRouter via l'exécution de la coroutine dans un thread pool.
- Centraliser timeouts, retries, circuit breaker, et instrumentation Prometheus (`llm_validation_total`).

### 3.2 Intégration crawler
- Propager le flag `enable_llm` depuis `crawl_land_task` jusqu'à `SyncCrawlerEngine._process_expression`.
- Après calcul pertinence :
  ```python
  if enable_llm and settings.OPENROUTER_ENABLED:
      verdict = llm_service.validate_expression_relevance_sync(expression, land)
      expression.valid_llm = verdict.is_valid
      expression.valid_model = verdict.model
      if not verdict.is_valid:
          expression.relevance = 0
  ```
- Conserver `approved_at` pour tracer le passage du pipeline.

### 3.3 Pipeline readable
- Unifier le traitement dans `ReadableService` et supprimer les variantes héritées.
- Lorsque `llm_enabled=True`, réutiliser la même méthode synchrone du service.
- Garantir la mise à jour de `valid_llm`, `valid_model`, `relevance` et `llm_validated_at`.

### 3.4 Outils & API
- Créer `scripts/reprocess_llm_validation.py --land <id> --force` pour relancer la validation.
- Ajouter endpoint `POST /api/v2/lands/{id}/llm-validate` qui crée un job Celery.
- Mettre à jour la documentation utilisateur (`SENTIMENT_ANALYSIS_FEATURE.md` si besoin) pour rappeler l'activation du flag.

## 4. Tests
- Tests unitaires `test_llm_validation_service.py` couvrant succès, échec HTTP, timeout, réponse invalide.
- Tests d'intégration :
  - Crawl avec `enable_llm=true` → vérifier `valid_llm`, `relevance`.
  - Pipeline readable via Celery → vérifier que le job met à jour les champs.
- Script fumée `tests/test-llm-validation.sh` (création land, crawl, readable, vérifications SQL).

## 5. Observabilité
- Logs JSON avec `land_id`, `expression_id`, `valid_llm`, `model`, `duration_ms`.
- Métriques Prometheus :
  - `llm_validation_total{status}`
  - `llm_validation_duration_seconds`
- Alerting sur le ratio d'échecs.

## 6. Checklist livraison
- [ ] Service LLM expose l'API synchrone.
- [ ] `SyncCrawlerEngine` déclenche le contrôle lorsque `enable_llm=true`.
- [ ] Pipeline readable Celery utilise la même logique.
- [ ] Endpoint/job/CLI de reprocessing disponibles.
- [ ] Tests et documentation mis à jour.

## 7. Risques & mitigation
- **Quota OpenRouter** : ajouter une file d'attente dédiée + backoff.
- **Temps de réponse** : prévoir un timeout < 6s et retenter 1 fois.
- **Défaillance provider** : circuit breaker désactive temporairement la fonctionnalité et loggue un warning.
- **Coût** : exposer un tableau de bord pour suivre la consommation.
