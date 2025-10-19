# Plan de développement — Domain Crawl V2 (mode synchrone)

## 1. Contexte & objectifs
- Reprendre le crawl des domaines en s'appuyant sur un moteur unique `crawler_engine_sync.py`.
- Enrichir la table `domains` avec les métadonnées nécessaires : titre, description, mots-clés, statut HTTP, dates de collecte.
- Garantir la cohérence avec le pipeline expressions (readable, sentiment, qualité) sans réintroduire d'exécution parallèle.

## 2. Architecture cible
1. `app/core/domain_crawler.py`
   - Implémentation unique basée sur `requests` + `trafilatura`.
   - Gestion séquentielle des stratégies : cache local → archive.org → HTTP direct.
   - Normalisation des résultats et mapping strict vers les attributs ORM (`domain.title`, `domain.language`, ...).
2. `app/services/domain_crawl_service.py`
   - Sélection des domaines à traiter (batch, limites, filtrage par land).
   - Persistance des champs, recalcul de `last_crawled`, `first_crawled`, `total_expressions`.
   - Emission d'évènements de suivi (logs structurés, métriques Prometheus).
3. `app/tasks/domain_crawl_task.py`
   - Tâche Celery `crawl_domains_task` qui orchestre le service synchrone.
   - Support du suivi de progression (mise à jour régulière via `update_state`).
4. API / CLI
   - Endpoint `POST /api/v2/lands/{id}/crawl-domains`.
   - Commande Typer `python -m app.scripts.domain_crawl --land <id>` pour exécuter depuis la ligne de commande.

## 3. Backlog technique
- [ ] Créer `DomainCrawler` (classe synchrone) avec méthodes `fetch`, `parse`, `persist`.
- [ ] Traduire l'ancien code `_legacy/core.py:crawl_domains` vers la nouvelle structure.
- [ ] Intégrer les stratégies archive.org et HTTP direct avec timeouts configurables.
- [ ] Ajouter les métriques `domain_crawl_duration_seconds` et `domain_crawl_failures_total`.
- [ ] Documenter le workflow dans `docs/domain_crawl.md`.

## 4. Tests à prévoir
- Tests unitaires sur `DomainCrawler` (réponses HTTP contrôlées via `responses`).
- Tests d'intégration via Pytest + base Postgres en mémoire ou dockerisée.
- Script shell `tests/test-domain-crawl.sh` pour fumée end-to-end (API → Celery → DB).
- Vérification SQL :
  ```bash
  docker exec mywebclient-db-1 psql -U mwi_user -d mwi_db -c \
  "SELECT url, http_status, fetched_at FROM domains ORDER BY fetched_at DESC LIMIT 10;"
  ```

## 5. Observabilité & exploitation
- Logs structurés côté worker (`logger.info` avec payload JSON : domaine, stratégie utilisée, durée, statut).
- Métriques Prometheus exposées par l'API : durée moyenne, nombre d'échecs, files d'attente.
- Table `domain_crawl_events` pour tracer les erreurs bloquantes.

## 6. Points de vigilance
- Interdiction de réintroduire des dépendances non bloquantes (`aiohttp`, boucles d'évènement, etc.).
- Respect des noms d'attributs pour SQLAlchemy (cf. `LANGUAGE_DETECTION_FIX.md`).
- Gérer proprement les timeouts réseau : retry limité, fallback archive puis abandon.
- Vérifier que les scripts de remise en file `scripts/requeue_domains.py` exploitent bien le moteur unique.

## 7. Livraison
- PR unique accompagnée d'un plan de test précisant les environnements touchés.
- Mise à jour de la documentation produit (`.claude/docs`) pour refléter l'architecture synchrone.
- Rétro-documentation : mentionner dans les CR l'abandon définitif du moteur parallèle et pointer vers `ERREUR_DOUBLE_CRAWLER.md`.

