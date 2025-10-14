# 🔴 ERREUR FRÉQUENTE : Double Crawler Sync/Async

**Date**: 14 octobre 2025
**Gravité**: 🔴 **CRITIQUE** - Cause de bugs silencieux en production
**Fréquence**: ⚠️ **TRÈS FRÉQUENTE**

---

## ❌ Le Problème

Le système MyWebIntelligence utilise **DEUX crawlers différents** pour des raisons techniques. Oublier de modifier l'un des deux cause des bugs qui passent inaperçus en développement mais apparaissent en production.

```
┌───────────────────────────────────────────────────────────────────────┐
│                                                                        │
│  ❌ ERREUR TYPIQUE                                                     │
│                                                                        │
│  1. Vous modifiez crawler_engine.py (async)                          │
│  2. Vous testez avec l'API directe → ✅ Ça marche !                  │
│  3. Vous commitez                                                     │
│  4. En production, Celery utilise crawler_engine_sync.py             │
│  5. 💥 Le bug n'apparaît qu'en production                            │
│                                                                        │
└───────────────────────────────────────────────────────────────────────┘
```

---

## 🏗️ Architecture : Pourquoi Deux Crawlers ?

```
┌─────────────────────────────────────────────────────────────────────┐
│                                                                      │
│  📱 FastAPI (API endpoints)                                         │
│      └─ AsyncCrawlerEngine (crawler_engine.py)                     │
│          └─ Utilisé pour : Tests, API directe                       │
│          └─ Format : async/await natif                              │
│                                                                      │
│  ⚙️  Celery Workers (tasks asynchrones)                            │
│      └─ SyncCrawlerEngine (crawler_engine_sync.py)                 │
│          └─ Utilisé pour : Crawls en production                     │
│          └─ Format : Synchrone avec asyncio.run()                   │
│                                                                      │
└─────────────────────────────────────────────────────────────────────┘
```

### Pourquoi pas un seul crawler ?

1. **FastAPI** : Nativement async, préfère `AsyncCrawlerEngine`
2. **Celery** : Workers synchrones, difficultés avec async/await
3. **Performances** : Les deux architectures sont optimisées différemment

---

## 📋 Checklist OBLIGATOIRE

**Avant CHAQUE modification de la logique de crawl :**

```bash
# ✅ CHECKLIST
[ ] 1. Modifier crawler_engine.py (async)
[ ] 2. Modifier crawler_engine_sync.py (sync)
[ ] 3. Vérifier que la logique est identique
[ ] 4. Tester avec l'API
[ ] 5. Tester avec Celery
[ ] 6. Vérifier en base de données
```

---

## 🐛 Exemples de Bugs Réels

### Bug #1 : Champ `content` (HTML) non sauvegardé (14 oct 2025)

**Symptômes** :
- Le champ `content` (HTML brut) est toujours NULL en DB
- Tests unitaires passent ✅
- Production échoue ❌

**Cause** :
```python
# ✅ Ajouté dans crawler_engine.py
if extraction_result.get('content'):
    update_data["content"] = extraction_result['content']

# ❌ OUBLIÉ dans crawler_engine_sync.py
# → Le HTML n'est jamais sauvegardé en production
```

**Solution** :
```python
# Ajouter AUSSI dans crawler_engine_sync.py (lignes 192-197)
if extraction_result.get('content'):
    update_data["content"] = extraction_result['content']
    logger.debug(f"Storing HTML content: {len(extraction_result['content'])} chars")
```

---

### Bug #2 : Métadonnées manquantes

**Symptômes** :
- `title`, `description`, `keywords` extraits en dev
- Vides en production

**Cause** :
- Logique d'extraction ajoutée dans `content_extractor.py`
- Crawler async l'utilise correctement
- Crawler sync ne récupère pas les nouveaux champs

**Solution** :
- Vérifier que les deux crawlers récupèrent les mêmes champs depuis `extraction_result`

---

### Bug #3 : Nouveau calcul de relevance

**Symptômes** :
- Nouveau scoring fonctionne en tests
- Ancien scoring utilisé en prod

**Cause** :
- Logique de relevance modifiée dans crawler async
- Crawler sync utilise toujours l'ancienne

---

## 🔍 Comment Détecter Ce Bug

### 1. Recherche dans le code

```bash
# Chercher votre modification dans LES DEUX fichiers
grep -n "votre_nouvelle_fonction" app/core/crawler_engine.py
grep -n "votre_nouvelle_fonction" app/core/crawler_engine_sync.py

# Si un seul résultat → 🚨 PROBLÈME !
```

### 2. Vérifier les logs Celery

```bash
# Les logs Celery montrent quel crawler est utilisé
docker logs mywebclient-celery_worker-1 --tail 100 | grep "Crawling"

# Chercher des erreurs silencieuses
docker logs mywebclient-celery_worker-1 --tail 100 | grep -E "(ERROR|WARNING)"
```

### 3. Vérifier en base de données

```bash
# Après un crawl, vérifier que TOUTES les données sont sauvegardées
docker exec mywebclient-db-1 psql -U mwi_user -d mwi_db -c "
  SELECT
    url,
    title IS NOT NULL as has_title,
    description IS NOT NULL as has_desc,
    content IS NOT NULL as has_html,
    readable IS NOT NULL as has_readable
  FROM expressions
  WHERE created_at > NOW() - INTERVAL '5 minutes'
  LIMIT 3;
"
```

---

## 🛠️ Guide de Synchronisation

### Quand modifier les deux crawlers ?

**TOUJOURS** quand vous changez :

✅ Extraction de données depuis les pages
✅ Calcul de relevance
✅ Sauvegarde de nouveaux champs en DB
✅ Logique de filtrage des URLs
✅ Traitement des erreurs HTTP
✅ Gestion des médias
✅ Pipeline readable

❌ **PAS NÉCESSAIRE** pour :
- Routes API (endpoints FastAPI)
- Schémas Pydantic
- Services externes (non liés au crawl)
- Configuration Docker

---

### Template de modification

```python
# ===== TOUJOURS SYNCHRONISER CES DEUX BLOCS =====

# 📁 crawler_engine.py (ASYNC)
# Lignes ~165-170
if extraction_result.get('nouveau_champ'):
    update_data["nouveau_champ"] = extraction_result['nouveau_champ']
    logger.debug(f"Nouveau champ extrait")

# 📁 crawler_engine_sync.py (SYNC)
# Lignes ~192-197
if extraction_result.get('nouveau_champ'):
    update_data["nouveau_champ"] = extraction_result['nouveau_champ']
    logger.debug(f"Nouveau champ extrait")
```

---

## 📊 Différences entre les Deux Crawlers

| Aspect | AsyncCrawlerEngine | SyncCrawlerEngine |
|--------|-------------------|-------------------|
| **Fichier** | `crawler_engine.py` | `crawler_engine_sync.py` |
| **Utilisé par** | FastAPI endpoints | Celery tasks |
| **Appels async** | `await func()` | `asyncio.run(func())` |
| **HTTP Client** | `httpx.AsyncClient` | `httpx.Client` |
| **DB Session** | `AsyncSession` | `Session` (sync) |
| **Logs** | Dans API logs | Dans Celery logs |

---

## 🧪 Tests de Non-Régression

### Test après modification

```bash
# 1. Lancer un crawl via API (teste async)
curl -X POST "http://localhost:8000/api/v2/lands/1/crawl" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"max_pages": 1}'

# 2. Lancer un crawl via Celery (teste sync)
# (Le crawl normal utilise automatiquement Celery)

# 3. Comparer les résultats
docker exec mywebclient-db-1 psql -U mwi_user -d mwi_db -c "
  SELECT
    id, url, title,
    LENGTH(content) as html_len,
    LENGTH(readable) as readable_len
  FROM expressions
  ORDER BY created_at DESC
  LIMIT 2;
"
```

### Résultat attendu

Les **deux dernières expressions** doivent avoir :
- ✅ Title rempli
- ✅ HTML (`content`) présent
- ✅ Readable présent
- ✅ Même structure de données

---

## 📚 Ressources

- **Code source** :
  - `app/core/crawler_engine.py`
  - `app/core/crawler_engine_sync.py`

- **Tasks Celery** :
  - `app/tasks/crawling_task.py` (utilise SyncCrawlerEngine)

- **Documentation** :
  - `.claude/AGENTS.md` (section "Double Crawler")
  - `.claude/CORRECTIONS_EXTRACTION_METADATA.md`

---

## ✅ Résumé en 3 Points

1. **Deux crawlers existent** : async (API) et sync (Celery)
2. **Toujours modifier les deux** quand vous touchez à la logique de crawl
3. **Tester avec Celery** avant de considérer le bug résolu

---

**Dernière mise à jour** : 14 octobre 2025
**Prochain audit** : À chaque modification du pipeline de crawl
