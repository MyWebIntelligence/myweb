# Plan de développement — Domain Crawl indépendant (v2)

## 1. Contexte & objectifs
- Restaurer la parité avec `_legacy/core.py:crawl_domains` en enrichissant la table `domains` (title, description, keywords, http_status, fetched_at, first/last_crawled, language).
- Aligner la nouvelle implémentation avec l’architecture actuelle FastAPI + Celery en respectant **le principe double crawler** (`crawler_engine.py` async / `crawler_engine_sync.py` sync) souligné dans `.claude/AGENTS.md`.
- Décorréler le cycle de vie du crawl domaines de celui des expressions pour pouvoir planifier, monitorer et relancer ces flux indépendamment, sans perturber les pipelines existants (readable, media, quality, sentiment).

## 2. Leçons du legacy à intégrer
- **Chaîne de récupération** inchangée : Trafilatura → Archive.org → requêtes HTTP directes (exactement comme décrit dans `_TRANSFERT_API_CRAWL.md`).
- **Propagation complète des métadonnées** : title/description/keywords/http_status/content source, logs d’erreur (`ERR_TRAFI`, `ERR_ARCHIVE_*`…).
- **Respect des noms ORM** (`domain.title`, `domain.language`…) pour éviter les ratés déjà rencontrés (`LANGUAGE_DETECTION_FIX.md`).
- **Tests croisés sync/async** obligatoires (`tests/test-crawl-async.sh`, `tests/test-crawl-simple.sh`) pour garantir la parité.
- **Documentation & monitoring** dès la PR (section Recommandations Dev 2025-10 dans `.claude/AGENTS.md`).

## 3. Périmètre
- **Inclus** : crawl domaines multi-stratégies, mise à jour modèles/CRUD, orchestration via API et Celery, observabilité (WS/logs/métriques), tests auto, scripts de retraitement.
- **Exclus** : heuristiques sociales, détection robots.txt, scoring qualité des domaines, gestion DNS/IP avancée.
- **Prérequis** : accès PostgreSQL/Redis, Trafilatura + aiohttp installés, workers Celery opérationnels, `settings.domain_*` disponibles.

## 4. Architecture cible
1. `app/core/domain_crawler_async.py`  
   - Implémentation principale (aiohttp + `asyncio.to_thread(trafilatura.fetch_url)`).
   - Extraction métadonnées (BeautifulSoup fallback) + normalisation (source, status_code, html).
2. `app/core/domain_crawler_sync.py`  
   - Wrapper sync (requests + `asyncio.run` sur l’async pour partage de logique) utilisé par Celery/CLI.
3. `app/services/domain_crawl_service.py`  
   - Sélection des domaines (fetched_at NULL, filtre http, limite, land optionnel).
   - Persistance des champs + recompute `total_expressions`, `last_crawled`.
   - Publication d’évènements (logs, progress, stats).
4. `app/tasks/domain_crawl_task.py`  
   - Tâche Celery dédiée (`tasks.crawl_domains_task`) avec suivi WebSocket `domain_crawl_progress_{job}`.
5. API & CLI  
   - Endpoint REST `POST /api/v2/lands/{id}/crawl-domains` (+ route admin pour full crawl).
   - Commande Typer `python -m app.scripts.domain_crawl`.
6. Observabilité  
   - Logs structurés (`logger.info` + payload JSON), métriques Prometheus (`domain_crawl_duration_seconds`, `domain_crawl_failures_total`), traces OpenTelemetry (optionnel).

## 5. Flux de données
```
Domain sélectionné → Tentative Trafilatura (HTTPS→HTTP)
                     → Si échec : Archive.org (Wayback)
                     → Si échec : requêtes directes (HTTPS→HTTP)
                     → Extraction metadata (Trafilatura / BS4)
                     → Mise à jour Domain (title, desc, keywords, http_status, fetched_at, last_crawled, source_method, language)
                     → Journalisation + stats
```

## 6. Plan d’implémentation

### Phase 0 — Cadrage & préparation (0.5 sprint)
- Audit `Domain` : colonnes présentes, contraintes, index (ajouter index `(land_id, fetched_at)` si besoin).
- Définir settings (`domain_crawl_timeout`, `domain_crawl_retry`, `domain_crawl_user_agent`, `domain_crawl_concurrency`).
- Mettre en place environnement de test HTTP mocké (respx/VCR.py) + fixtures Wayback.
- Décision OPS : quotas Trafilatura/Archive.org, limites simultanées.

### Phase 1 — Portage logique & contrat (1 sprint)
- Cartographier legacy (`crawl_domains`) → définir DTO (`DomainFetchResult`).
- Rédiger tests “oracles” : 3 snapshots (succès, archive, http fallback).
- Spécifier codes d’erreur / logs (alignement `_TRANSFERT_API_CRAWL.md`).

### Phase 2 — Implémentation async (1 sprint)
- Créer `domain_crawler_async` (Trafilatura → Archive.org → HTTP, extraction metadata via BS4).
- Gestion des erreurs : retries exponentiels, codes `ERR_*`, logs contextuels.
- Tests unitaires avec mocks (aiohttp, respx) + couverture >85%.

### Phase 3 — Wrapper sync & double crawler (0.5 sprint)
- Implémenter `domain_crawler_sync` en réutilisant la logique async (pas de divergence).
- Tests smoke Celery + script CLI, validations `tests/test-crawl-async.sh` & `test-crawl-simple.sh`.

### Phase 4 — Service & orchestration (1 sprint)
- `DomainCrawlService.run_batch()` : sélection, exécution, persistance safe (transactions, verrous).
- Mise à jour `crawling_service` + enums `CrawlJob` (`job_type="domain_crawl"`).
- Tâche Celery + canal WebSocket, payload progress (processed/total/erreurs).
- Endpoint REST (v1/v2) + CLI (Typer) + schémas Pydantic.

### Phase 5 — Observabilité & UX (0.5 sprint)
- Ajout métriques Prometheus, logs JSON, dashboard Grafana (tableau succès/échecs).
- Mise à jour docs : `.claude/docs`, README général, changelog.
- Dashboard/CLI listant statut des domaines (fetched_at, last_crawled, http_status).

### Phase 6 — Validation & déploiement (0.5 sprint)
- Campagne QA staging (domaines en ligne, 301, 404, offline).
- Tests charge : N domaines/min, ressources Trafilatura.
- Checklist sécurité (respect robots.txt si activé, user-agent, retries).
- Go/No-Go + plan rollback.

## 7. Backlog détaillé
| ID | Catégorie | Description | Livrable | Owner |
|----|-----------|-------------|----------|-------|
| DC-01 | Analyse | Audit modèle Domain + index | Rapport | Tech Lead |
| DC-02 | Tests | Fixtures Trafilatura/Archive/HTTP + mocks | Tests pytest | QA |
| DC-03 | Core | `DomainCrawlerAsync.fetch(domain)` | Module + tests | Dev A |
| DC-04 | Core | Extraction metadata + normalisation | Utilitaires | Dev A |
| DC-05 | Core | Gestion erreurs + codes `ERR_*` | Logger + enums | Dev A |
| DC-06 | Core | Wrapper sync & tests | Module | Dev B |
| DC-07 | Service | `DomainCrawlService.run_batch` | Service + tests | Dev B |
| DC-08 | Infra | Tâche Celery + WebSocket progress | Task + tests e2e | DevOps |
| DC-09 | API | Endpoints REST + schémas | Routes + tests | Dev B |
| DC-10 | CLI | Commande Typer + doc | Script | DevOps |
| DC-11 | Observabilité | Métriques & logs JSON | Dashboard | DevOps |
| DC-12 | Docs | Guides `.claude/docs`, README | Docs | Tech Writer |
| DC-13 | QA | Campagne staging + rapport | Rapport QA | QA |

## 8. Qualité & critères d’acceptation
- 100% des domaines traités remplissent `fetched_at`, `http_status`, `source_method`.
- <5% d’échecs réseau sur un lot de 200 domaines (hors blocages externes).
- Temps moyen de traitement configurable (`settings.domain_crawl_timeout`) respecté.
- Parité sync/async vérifiée (scripts de tests existants + nouveaux tests).
- Observabilité : métriques + logs disponibles, docs à jour.

## 9. Risques & mitigations
- **Instabilité Trafilatura** : retries + fallback HTTP + logs `ERR_TRAFI`.
- **Blocage Archive.org** : circuit breaker + cache résultats.
- **Charge réseau** : limite `aiohttp.TCPConnector(limit=N)`, pacing global.
- **Désynchronisation double crawler** : revue croisée + exécution `test-crawl-*`.
- **Compatibilité exports** : garder codes d’erreurs legacy pour ne pas casser les scripts downstream.

## 10. Suivi & communication
- Stand-up dédié Domain Crawl (15 min / sprint) + demo fin de phase.
- Kanban spécifique avec swimlanes (Core / API / Infra / Docs / QA).
- Weekly report : domaines traités, erreurs par source, actions correctives.
- Diffuser chaque jalon via changelog interne + mise à jour `.claude/INDEX_DOCUMENTATION.md`.

## 11. Prochaines étapes immédiates
1. Valider le plan (tech/product/ops) + verrouiller les ressources.
2. Lancer DC-01/DC-02 (audit + fixtures) pour sécuriser l’implémentation.
3. Préparer environnement de mock HTTP (respx/VCR) et pipeline de tests CI dédiés.
