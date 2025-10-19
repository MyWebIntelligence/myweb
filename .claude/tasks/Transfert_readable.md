# Plan de mise à niveau — Pipeline "Readable" (V2 sync)

## 1. Objectifs
- Aligner `ReadableService` et ses variantes sur un **pipeline unique synchrone**.
- Conserver les améliorations validées : markdown enrichi, fallbacks Archive.org, conservation HTML.
- Étendre l'observabilité (statistiques, métriques, logs) pour éviter toute régression future.

## 2. Architecture cible
1. `app/core/content_extractor.py`
   - Renvoie un `ExtractionResult` complet (markdown, HTML, métadonnées, source).
2. `app/services/readable_service.py`
   - Orchestration unique : extraction → merge → pertinence → qualité → LLM.
3. `app/services/readable_worker.py`
   - Adaptateur Celery qui délègue intégralement à `ReadableService`.
4. `app/api/v2/readable.py`
   - Endpoints REST pour lancer le pipeline et consulter les statistiques.

## 3. Étapes clés
- [ ] Supprimer les anciennes implémentations parallèles (`ReadableSimpleService`, `ReadableCeleryService`) et rediriger vers `ReadableService`.
- [ ] Mutualiser la logique d'enrichissement dans un `ReadableProcessor` partagé (merge, pertinence, qualité, LLM).
- [ ] Normaliser `extraction_source` (`trafilatura_direct`, `archive_org`, `bs_smart`, `bs_basic`).
- [ ] Garantir la persistance de `readable`, `content`, `title`, `description`, `language`, `published_at`, `approved_at`, `readable_at`, `wayback_used`.
- [ ] Centraliser la gestion médias/liens dans `MediaLinkExtractor`.

## 4. Observabilité
- Métriques Prometheus :
  - `readable_processed_total{source=..., land_id=...}`
  - `readable_errors_total{reason=...}`
  - `readable_duration_seconds`
- Logs structurés : land, expression, source, durée, statut.
- Endpoint `/api/v2/lands/{id}/readable/stats` regroupant success_rate, erreurs, utilisation Archive.org.

## 5. Tests
- Tests unitaires sur `ReadableService` avec fixtures Trafilatura/Archive/HTML.
- Tests d'intégration comparant résultats legacy vs V2 sur un échantillon d'URL.
- Script fumée `tests/test-readable-pipeline.sh` (API → Celery → DB → vérifications SQL).

## 6. Checklist livraison
- [ ] Code back-end : `ReadableService` = source unique 
- [ ] Migration supprimant les anciennes classes/entrées obsolètes
- [ ] Documentation `.claude/docs/` mise à jour (workflow, monitoring, procédures).
- [ ] CI : tests unitaires + intégration verts, script fumée documenté.
- [ ] Rétro-documentation : mentionner suppression complète de l'ancien pipeline parallèle.

## 7. Risques
- Divergences de merge : prévoir tests de non-régression.
- Charge Trafilatura : configurer timeouts + caches.
- Dépendances clients : vérifier que les réponses API restent compatibles (versionner en cas de changement majeur).

## 8. Suivi
- Kanban dédié (colonnes Analyse / Implémentation / Revue / Tests / Docs).
- Point hebdomadaire avec QA pour valider le dataset de comparaison.
- Mise à jour de `INDEX_DOCUMENTATION.md` à chaque jalon livré.

