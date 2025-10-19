# Plan de Développement - Crawling Async Parallèle

**Date**: 19 octobre 2025
**Statut**: ⏸️ EN PAUSE - Fonctionnel mais désactivé temporairement
**Raison**: Erreurs `greenlet_spawn` dans l'extraction des liens (trop complexe à résoudre)
**Objectif**: Implémenter le crawling HTTP parallèle sans casser les opérations DB séquentielles

---

## ⏸️ DÉCISION: MISE EN PAUSE

**Date**: 19 octobre 2025

### Pourquoi la pause?

Le mode parallèle **fonctionne** pour le crawl principal (4/5 URLs crawlées avec succès, HTTP status sauvé, metadata extraits, relevance calculée), mais rencontre des **erreurs non-bloquantes** dans l'extraction des liens:

```
Error processing markdown link: greenlet_spawn has not been called;
can't call await_only() here. Was IO attempted in an unexpected place?
```

**Impact**:
- ✅ Crawl principal: **FONCTIONNE**
- ✅ Métadonnées: **SAUVÉES**
- ✅ Performance: **3x plus rapide** (10s vs 30s)
- ❌ Liens entre expressions: **NON CRÉÉS** (erreur greenlet_spawn)
- ❌ Graphe de navigation: **INCOMPLET**

**Décision**: Désactiver temporairement le mode parallèle (`parallel=False` par défaut) jusqu'à résolution complète du problème d'extraction des liens.

### Ce qui a été corrigé

Les 4 bugs critiques ont été résolus:
1. ✅ `http_status` en INTEGER (au lieu de STRING)
2. ✅ Headers HTTP en mode prefetched
3. ✅ Logging des échecs HTTP
4. ✅ Tests avec le nouveau code

### Ce qui reste à faire

- [ ] Refactoriser `_create_links_from_markdown()` pour éviter erreurs greenlet_spawn
- [ ] Refactoriser `_extract_and_save_links()` pour éviter erreurs greenlet_spawn
- [ ] Refactoriser `_save_media_from_list()` pour éviter erreurs greenlet_spawn
- [ ] Tester extraction liens en mode parallèle
- [ ] Valider graphe complet avec liens et media

**Complexité estimée**: 2-3 jours de développement supplémentaire

**Priorité**: BASSE (le crawl fonctionne sans parallélisme)

---

---

## 🎯 Architecture Parallèle

### Principe
L'implémentation parallèle divise le crawl en 2 phases:

**Phase 1 - HTTP PARALLÈLE** (I/O-bound, bénéficie de la concurrence)
```python
fetch_results = await asyncio.gather(
    *[fetch_with_semaphore(url) for url in urls],
    return_exceptions=True
)
```
- Toutes les requêtes HTTP sont lancées en parallèle
- Semaphore limite à `max_concurrent` (default: 10)
- Pas d'accès à la DB → Pas de conflit de session SQLAlchemy

**Phase 2 - TRAITEMENT SÉQUENTIEL** (DB-bound, évite les conflits)
```python
for fetch_result in fetch_results:
    status_code = await self.crawl_expression(expr, prefetched_content=fetch_result)
    await self.db.commit()  # Commit après CHAQUE expression
```
- Traitement un par un des résultats HTTP
- Extraction de contenu, calcul de pertinence, sentiment
- Commit après chaque expression → Session SQLAlchemy propre

### Avantages
- **Performance**: 5 URLs en ~10s au lieu de ~30s (3x plus rapide)
- **Fiabilité**: Pas d'erreurs `greenlet_spawn` ou `Session is already flushing`
- **Compatibilité**: Réutilise `crawl_expression()` existant avec `prefetched_content`

### Limitations
- Commits fréquents (1 par expression) → Overhead transactionnel
- Pas de rollback global si une expression échoue
- Nécessite plus de mémoire (tous les résultats HTTP en mémoire)

---

## 🐛 Bugs Identifiés

### BUG #1 CRITIQUE: `http_status` stocké en STRING au lieu d'INTEGER

**Symptôme**:
```
(sqlalchemy.dialects.postgresql.asyncpg.Error) <class 'asyncpg.exceptions.DataError'>:
invalid input for query argument $6: '200' ('str' object cannot be interpreted as an integer)
```

**Localisation**:
- `MyWebIntelligenceAPI/app/core/crawler_engine.py:322`
- `MyWebIntelligenceAPI/app/schemas/expression.py:33`

**Analyse**:
La DB PostgreSQL attend un INTEGER, mais le code convertit en STRING à cause d'une incohérence dans les schémas Pydantic.

**Schémas actuels**:
```python
# DB Model (models.py:207)
http_status = Column(Integer, nullable=True, index=True)  # ✅ INTEGER

# Schema UPDATE (schemas/expression.py:33)
http_status: Optional[str] = None  # ❌ STRING (INCORRECT)

# Schema GET (schemas/expression.py:62)
http_status: Optional[int] = None  # ✅ INTEGER

# Code (crawler_engine.py:322)
"http_status": str(http_status_code),  # ❌ Conversion en STRING (INCORRECT)
```

**Correction**:

1. **schemas/expression.py ligne 33**:
```python
# AVANT
http_status: Optional[str] = None  # Changed to string (legacy format)

# APRÈS
http_status: Optional[int] = None  # Must match DB type (INTEGER)
```

2. **crawler_engine.py ligne 322**:
```python
# AVANT
"http_status": str(http_status_code),  # Store as string (legacy format)

# APRÈS
"http_status": http_status_code,  # Store as int (DB expects INTEGER)
```

**Impact**: Sans ce fix, TOUTES les expressions échouent avec une erreur PostgreSQL.

---

### BUG #2 MAJEUR: Headers HTTP écrasés en mode `prefetched`

**Symptôme**:
Les champs `last_modified` et `etag` ne sont JAMAIS sauvés en mode parallèle.

**Localisation**:
`MyWebIntelligenceAPI/app/core/crawler_engine.py:279-280, 312-319`

**Analyse**:
En mode `prefetched_content`, le code:
1. **Ligne 279-280**: Extrait correctement les headers du `prefetched_content` ✅
```python
last_modified_str = prefetched_content.get('last_modified')
etag_str = prefetched_content.get('etag')
```

2. **Ligne 312-313**: Réinitialise les variables à `None` ❌
```python
last_modified_str = None
etag_str = None
```

3. **Ligne 316-317**: Tente d'utiliser `response` qui n'existe PAS en mode prefetched ❌
```python
last_modified_str = response.headers.get('last-modified', None)  # ❌ NameError!
etag_str = response.headers.get('etag', None)
```

**Code actuel problématique**:
```python
# Ligne 272-280: Mode prefetched (✅ extraction correcte)
if prefetched_content:
    html_content = prefetched_content['html_content']
    http_status_code = prefetched_content['status_code']
    content_type = prefetched_content.get('content_type')
    content_length = prefetched_content.get('content_length')
    last_modified_str = prefetched_content.get('last_modified')  # ✅
    etag_str = prefetched_content.get('etag')  # ✅
else:
    # Mode séquentiel...

# Ligne 312-319: PROBLÈME - écrase les valeurs prefetched
last_modified_str = None  # ❌ Écrase la valeur ligne 279!
etag_str = None  # ❌ Écrase la valeur ligne 280!
if http_status_code and http_status_code < 400:
    try:
        last_modified_str = response.headers.get('last-modified', None)  # ❌ response n'existe pas!
        etag_str = response.headers.get('etag', None)
    except Exception:
        pass
```

**Correction**:
Conditionner le bloc à `if not prefetched_content`:
```python
# Extract HTTP headers: Last-Modified and ETag
if not prefetched_content:  # ✅ Seulement en mode séquentiel
    last_modified_str = None
    etag_str = None
    if http_status_code and http_status_code < 400:
        try:
            last_modified_str = response.headers.get('last-modified', None)
            etag_str = response.headers.get('etag', None)
        except Exception:
            pass
# Sinon, on garde les valeurs extraites du prefetched_content (lignes 279-280)
```

**Impact**: Sans ce fix, les headers HTTP ne sont jamais sauvés en mode parallèle.

---

### BUG #3: Manque de logging pour les échecs HTTP

**Symptôme**:
Quand un fetch HTTP échoue (4xx, 5xx, timeout), aucun log n'indique le problème.

**Localisation**:
`MyWebIntelligenceAPI/app/core/crawler_engine.py:231-258`

**Analyse**:
Le code vérifie si `fetch_result` est une Exception, mais ne log pas si `fetch_result['success'] == False`.

**Code actuel**:
```python
for fetch_result in fetch_results:
    if isinstance(fetch_result, Exception):
        logger.error(f"HTTP fetch raised exception: {fetch_result}")
        error_count += 1
        http_stats['error'] += 1
        continue

    # ❌ Pas de vérification de fetch_result['success']
    url = fetch_result['url']
    expr = expr_map.get(url)
    if not expr:
        continue

    try:
        status_code = await self.crawl_expression(...)
```

**Correction**:
Ajouter un log après la vérification d'exception:
```python
for fetch_result in fetch_results:
    if isinstance(fetch_result, Exception):
        logger.error(f"HTTP fetch raised exception: {fetch_result}")
        error_count += 1
        http_stats['error'] += 1
        continue

    # ✅ Log si le fetch a échoué (mais pas levé d'exception)
    if not fetch_result.get('success', True):
        url = fetch_result.get('url', 'unknown')
        status_code = fetch_result.get('status_code', 0)
        error = fetch_result.get('error', 'Unknown error')
        logger.warning(
            f"HTTP fetch failed for {url}: "
            f"status={status_code}, error={error}"
        )

    url = fetch_result['url']
    # ...
```

**Note**: On continue quand même le traitement car on veut enregistrer le `http_status` même en cas d'erreur (4xx, 5xx).

**Impact**: Améliore le debugging, pas critique pour le fonctionnement.

---

### BUG #4: Tests exécutés AVANT redémarrage API

**Symptôme**:
Les logs des tests montrent des erreurs déjà corrigées:
- `'CRUDLand' object has no attribute 'get_land_dict'` (corrigé ligne 397)
- `'SentimentService' object has no attribute 'analyze_sentiment'` (méthode dupliquée supprimée)
- `greenlet_spawn has not been called` (corrigé par l'architecture parallèle)

**Analyse**:
Les tests ont été lancés AVANT le redémarrage de l'API, donc l'ancien code était toujours en mémoire.

**Correction**:
1. Redémarrer l'API: `docker compose restart mywebintelligenceapi`
2. Attendre 5-10 secondes
3. Relancer les tests: `./MyWebIntelligenceAPI/tests/test-crawl-async.sh`

**Impact**: Les résultats des tests ne reflètent pas le nouveau code.

---

## 📋 Plan de Correction

### Phase 1: Corrections critiques

- [ ] **1.1** Corriger `schemas/expression.py` ligne 33
  - `http_status: Optional[str]` → `http_status: Optional[int]`

- [ ] **1.2** Corriger `crawler_engine.py` ligne 322
  - `"http_status": str(http_status_code)` → `"http_status": http_status_code`

- [ ] **1.3** Corriger `crawler_engine.py` lignes 312-319
  - Entourer avec `if not prefetched_content:`

### Phase 2: Améliorations

- [ ] **2.1** Ajouter logging dans `crawl_expressions_parallel` (ligne ~238)
  - Log si `fetch_result['success'] == False`

### Phase 3: Tests

- [ ] **3.1** Redémarrer API
  - `docker compose restart mywebintelligenceapi`
  - Attendre 10 secondes

- [ ] **3.2** Lancer test-crawl-async.sh
  - Vérifier: Pas d'erreur PostgreSQL
  - Vérifier: Headers HTTP sauvés
  - Vérifier: Metadata présents (title, lang, relevance)
  - Vérifier: Content sauvé (HTML, readable)

- [ ] **3.3** Vérifier logs API
  - Chercher: "Starting PARALLEL HTTP fetch"
  - Vérifier: "Parallel crawl completed: 5 processed, 0 errors"
  - Confirmer: Pas d'erreurs SQLAlchemy

---

## 🔍 Validation du Succès

### Critères de succès
- ✅ Aucune erreur PostgreSQL dans les logs
- ✅ Test passe: 5/5 expressions crawlées
- ✅ Headers HTTP: `last_modified` et `etag` présents (si serveur les envoie)
- ✅ Metadata: `title`, `lang`, `description` présents
- ✅ Relevance: > 0 pour au moins 3/5 expressions
- ✅ Content: `content` (HTML) et `readable` non vides
- ✅ Performance: Crawl < 15 secondes (vs ~30s en séquentiel)

### Requête DB de validation
```sql
SELECT
    id,
    url,
    http_status,
    last_modified,
    etag,
    lang,
    relevance,
    LENGTH(content) as html_size,
    LENGTH(readable) as readable_size
FROM expressions
WHERE land_id = <LAND_ID>
ORDER BY id;
```

---

## 📊 Comparaison Séquentiel vs Parallèle

| Aspect | Séquentiel | Parallèle |
|--------|-----------|-----------|
| **Durée (5 URLs)** | ~30 secondes | ~10 secondes |
| **Concurrence HTTP** | 1 requête à la fois | 10 requêtes simultanées |
| **Commits DB** | 1 commit global | 1 commit par expression |
| **Risque session DB** | Faible | Nul (séquentiel) |
| **Utilisation mémoire** | Faible | Moyenne |
| **Rollback** | Possible (global) | Impossible (commits fréquents) |
| **Code** | Simple | Modéré |

---

## 🚀 Prochaines Étapes

Une fois les bugs corrigés:

1. **Performance tuning**
   - Mesurer temps réel de crawl
   - Ajuster `max_concurrent` (actuellement 10)
   - Profiler pour identifier autres goulots

2. **Robustesse**
   - Ajouter retry logic pour échecs HTTP
   - Implémenter timeout par URL
   - Gérer rate limiting

3. **Monitoring**
   - Ajouter métriques Prometheus
   - Logger temps par phase (HTTP vs DB)
   - Tracker taux de succès/échec

4. **Documentation utilisateur**
   - Mettre à jour API docs
   - Ajouter paramètre `parallel=True/False` dans l'endpoint
   - Documenter différences de comportement

---

## 📚 Références

- **Architecture**: Voir [align_sync_async.md](.claude/tasks/align_sync_async.md) pour alignement sync/async
- **Tests**: Voir [README_TEST_ASYNC.md](.claude/tasks/README_TEST_ASYNC.md) pour procédure de test
- **Code source**: `MyWebIntelligenceAPI/app/core/crawler_engine.py` lignes 191-261 (parallel) et 263-532 (crawl_expression)
