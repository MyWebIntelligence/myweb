# Plan de mise à niveau — Pipeline “Readable” (v2)

## 1. Contexte & objectifs
- Garantir la parité fonctionnelle entre le pipeline readable du legacy (`_legacy/core.py`) et la nouvelle API tout en conservant les améliorations validées (markdown enrichi, smart extraction).
- S’assurer que **toutes** les variantes de service (async principal, simple, Celery) exploitent le même pipeline d’extraction (`ContentExtractor.get_readable_content_with_fallbacks`) et respectent les invariants ORM (`approved_at`, `readable_at`, `relevance`, `valid_llm`, etc.).
- Étendre l’observabilité et la traçabilité (statistiques, logs, métriques) afin d’éviter les régressions déjà rencontrées (voir `.claude/AGENTS.md`, section Recommandations Dev 2025-10).

## 2. Héritage legacy à préserver
- **Chaîne de fallbacks** : Trafilatura → Archive.org → BeautifulSoup (smart → basic) [réf. `.claude/docs/CHAÎNE_FALLBACKS.md`].
- **Format markdown enrichi** : marqueurs `[IMAGE]`, `[VIDEO]`, `[AUDIO]`, liens normalisés (`resolve_url`).
- **Propagation metadata** : title, description, keywords, canonical, published_at, language.
- **Persistance HTML** : champ `Expression.content` toujours rempli pour réutilisation (SEO, LLM).
- **Gestion des liens/médias découverts** : réinjection dans la base (ExpressionLink, Media) via `_create_links_from_markdown` et `_save_media_from_list`.

## 3. État actuel (2025-10)
- `ContentExtractor` déjà réaligné (markdown + fallbacks + enrichissement) cf. `_TRANSFERT_API_CRAWL.md`.
- `ReadableService` (async, DB AsyncSession) : applique extraction enrichie, calcule stats, gère merge strategies, mais logique dupliquée dans `ReadableSimpleService` & `ReadableCeleryService`.
- Services alternatifs n’appellent pas forcément les mêmes utilitaires (ex. `update_expression_readable_simple` vs TextProcessorService).
- Observabilité perfectible : success_rate absent, `wayback_used` peu exploité, statistiques par source non exposées.
- Pas de tests de non-régression legacy vs API sur un set d’URLs de référence (infrastructure en place mais non utilisée).

## 4. Périmètre de la mise à niveau
- **Inclus** : harmonisation services (async/simple/celery), recalcul pertinence/validation LLM, instrumentation, tests, documentation.
- **Exclus** : refonte complète du scheduler, nouvelles heuristiques, support robots.txt.
- **Prérequis** : connaissance des fichiers `app/core/content_extractor.py`, `app/services/readable_service.py`, `app/services/readable_simple_service.py`, `app/services/readable_celery_service.py`, + docs `.claude/_*.md`.

## 5. Architecture cible
1. **Content extraction unique** : `ContentExtractor.get_readable_content_with_fallbacks()` (Trafilatura markdown + HTML, fallbacks, enrichissement, métadonnées).
2. **Services alignés** :
   - `ReadableService` (async) : pipeline complet (extraction, merge, text processing, media, links, LLM).
   - `ReadableSimpleService` : doit déléguer au même extractor et appliquer au minimum les mêmes merges + recalcul pertinence.
   - `ReadableCeleryService` : idem simple, mais via pool sync (readable_db_pool) pour Celery.
3. **Utilitaires partagés** : centraliser merge strategies + recalculs pertinence/LMM dans helpers pour éviter divergences.
4. **Observabilité** : stats par source (trafilatura_direct, archive_org…), success_rate, skipped, erreurs par type, métriques Prometheus.
5. **Tests** : suite de non-régression comparant legacy vs API sur échantillon d’URLs réelles.

## 6. Plan d’implémentation (révisé)

### Phase 0 — Analyse & cadrage (0.5 sprint)
- Lire carthographie existante (`_TRANSFERT_API_CRAWL.md`, `CHAÎNE_FALLBACKS.md`, `quality_dev.md` pour exigences de pertinence).
- Inventorier divergence services (async vs simple vs celery) : usage extractor, recalcul pertinence, LLM, stats.
- Préparer dataset d’URLs de test (succès, archive, fallback basic, erreurs).

### Phase 1 — Harmonisation extraction (1 sprint)
- Garantie que `ReadableSimpleService` et `ReadableCeleryService` appellent `ContentExtractor.get_readable_content_with_fallbacks`.
- Mutualiser la logique d’interprétation du retour (`ExtractionResult`) via un processeur commun.
- Vérifier persistance `readable`, `content`, `title`, `description`, `language`, `published_at`, `extraction_source` (normaliser les valeurs: `trafilatura_direct|archive_org|beautifulsoup_smart|beautifulsoup_basic`).

### Phase 2 — Mise à jour des métriques dérivées (0.5 sprint)
- Introduire un processeur commun `BaseReadableProcessor` qui :
  - exécute l’extraction (via `ContentExtractor`) et prépare les mises à jour (merge).
  - recalcul la pertinence via `TextProcessorService`.
  - recalcul le `quality_score` via `QualityScorer` (bloc Richness impacté par le nouveau readable).
  - appelle la validation LLM si `enable_llm=True` (puis met `valid_llm`, `valid_model`, ajuste `relevance` si négatif, sans remettre `approved_at` à null).
- Assurer que tous services marquent `readable_at`, conservent `approved_at` comme trace de traitement, et renseignent `wayback_used` selon `extraction_source`.

### Phase 3 — Gestion médias/liens (0.5 sprint)
- Vérifier que simple/celery reconstituent `media_created` & `links_created` via `MediaLinkExtractor` (ou version sync).
- Ajouter support minimal ou expliciter dans docs pourquoi non géré.
- S’assurer que `expression.medias` / `expression.links` mis à jour en base.

### Phase 4 — Observabilité & stats (0.5 sprint)
- Étendre `ReadableProcessingResult` :
  - `success_rate = updated/processed`.
  - Comptes par `extraction_source`.
  - `errors_by_type`, `skipped_reason`.
- Instrumenter métriques Prometheus avec labels explicites:
  - `readable_processed_total{land_id,source="trafilatura|archive_org|beautifulsoup_smart|beautifulsoup_basic"}`
  - `readable_errors_total{land_id,reason="fetch_error|extraction_failed|merge_conflict"}`
  - `readable_duration_seconds` (histogram)
  - `readable_wayback_total{land_id}`
- Ajouter logs JSON avec `extraction_source`, `expr_id`, `land_id`, `updated`.

### Phase 5 — Tests & validation (1 sprint)
- Tests unitaires services (async/simple/celery) avec mocks (respx/VCR).
- Tests d’intégration : pipeline complet sur dataset (legacy vs API) → assert contenu, metadata, sources, quality_score, relevance, timestamps.
- Script shell de non‑régression `tests/manual/test-readable-pipeline.sh` inspiré des scripts crawl (création land, crawl, readable, vérifications SQL).
- Tests de charge (batch 100 expressions) pour vérifier absence de memory leak/io loop issues.
- Documentation `.claude/docs` + README mise à jour.

## 7. Backlog détaillé (révisé)
| ID | Catégorie | Description | Livrable | Owner |
|----|-----------|-------------|----------|-------|
| RD-01 | Analyse | Cartographie divergences services | Rapport | Tech Lead |
| RD-02 | Tests | Dataset URLs + mocks (Trafilatura/Archive/HTML) | Fixtures | QA |
| RD-03 | Core | ✨ `BaseReadableProcessor` (extraction, merge, relevance, quality, LLM) | Module `core/readable_processor.py` | Dev A |
| RD-04 | Core | ✨ Refactor services pour utiliser `BaseReadableProcessor` (async/simple/celery) | Services simplifiés | Dev A/B |
| RD-05 | Core | Normaliser `extraction_source` + `wayback_used` | Constantes + mapping | Dev B |
| RD-06 | Core | Gestion liens/médias alignée | Impl + tests | Dev B |
| RD-07 | Observabilité | ✨ Métriques Prometheus avec labels + logs JSON | Logs + metrics | DevOps |
| RD-08 | Tests | ✨ Script `test-readable-pipeline.sh` + E2E (legacy vs API) | Tests E2E | QA |
| RD-09 | Docs | MAJ `.claude/docs`, README, changelog | Documentation | Tech Writer |

## 8. Critères d’acceptation (complétés)
- 100% des services readable déposent les mêmes champs (title, description, readable, content, language, published_at, extraction_source, approved_at, readable_at).
- Parité sur dataset test : contenu, métadonnées, sources identiques (ou écarts documentés).
- `quality_score` recalculé après mise à jour du readable (et cohérent entre services).
- success_rate & stats disponibles (`/lands/{id}/readable/stats` & API v2).
- Tests unitaires + intégration verts.
- Documentation opérateur à jour (procédure run, monitoring).

## 9. Risques & mitigations
- **Divergence double crawler** : suivre checklist `.claude/AGENTS.md` (tests `test-crawl-async.sh`/`simple.sh`).
- **Charge Trafilatura/Archive** : limiter concurrency, caches, retries.
- **Maintien compatibilité clients** : versionner API si modification réponse.
- **Temps de développement** : prioriser harmonisation + tests avant stats avancées.
 - **Incohérence `extraction_source`** : définir des constantes communes et valider via tests.

## 10. Suivi & communication
- Stand-up hebdo “Readable” (10 min) + point dédié QA pour dataset.
- Kanban spécifique (Swimlanes Core/Infra/QA/Docs).
- Rapport d’avancement hebdo : nb expressions traitées, taux succès, anomalies.
- Mise à jour `.claude/INDEX_DOCUMENTATION.md` à chaque jalon.

## 11. Prochaines étapes immédiates
1. Lancer RD-01/RD-02 : audit complet des services + préparation dataset/mocks.
2. Valider plan avec Product/QA pour priorisation (phase 1→4).
3. Préparer pipeline tests CI pour suite non-régression readable.
