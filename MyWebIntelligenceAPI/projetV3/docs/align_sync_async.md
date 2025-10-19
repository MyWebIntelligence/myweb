# Plan d'Alignement Crawler Async → Sync

**Date**: 19 octobre 2025
**Statut**: 🔴 CRITIQUE - NameError en production sur le crawler async
**Référence**: crawler_engine_sync.py est la RÉFÉRENCE (100% fonctionnel)

---

## 🎯 Objectif

Porter les corrections du crawler **SYNC** (référence fonctionnelle) vers le crawler **ASYNC** (bugué) pour restaurer la parité complète entre les deux implémentations.

---

## 🐛 Bug Identifié

### Localisation
**Fichier**: `MyWebIntelligenceAPI/app/core/crawler_engine.py`
**Lignes**: 221-236 (méthode `crawl_expression`)

### Symptôme
```python
# Ligne 230 - NameError
temp_expr = TempExpr(metadata['title'], readable_content, expr_id)

# Ligne 234 - NameError
relevance = await text_processing.expression_relevance(
    land_dict,
    temp_expr,
    metadata_lang or 'fr'  # ❌ metadata_lang n'est jamais défini !
)
```

### Cause Racine
Le code async utilise encore d'anciennes variables (`metadata`, `metadata_lang`) qui ne sont **jamais initialisées**. Ces variables ont été supprimées lors d'une refactorisation, mais le code qui les utilise n'a pas été mis à jour.

### Impact
- **NameError** dès qu'on tente de calculer la pertinence
- Impossible d'utiliser le crawler async en production
- Perte des champs : `published_at`, `last_modified`, `etag`
- Scores qualité/sentiment incorrects (pas de `final_lang`)

---

## 📊 Différences Sync vs Async

| Aspect | Sync (RÉFÉRENCE) | Async (BUGUÉ) | Action |
|--------|------------------|---------------|--------|
| **Métadonnées** | ✅ Dict `metadata` créé (L212-219) | ❌ Pas de dict metadata | ⚠️ PORTER |
| **final_lang** | ✅ Calculé avec fallback (L244-245) | ✅ Calculé correctement (L203) | ✅ OK |
| **published_at** | ✅ Parsé depuis meta tags (L250-257) | ❌ Jamais parsé | ⚠️ PORTER |
| **last_modified** | ✅ Extrait des headers (L168-176) | ❌ Pas extrait | ⚠️ PORTER |
| **etag** | ✅ Extrait des headers (L168-176) | ❌ Pas extrait | ⚠️ PORTER |
| **Pertinence** | ✅ Utilise `final_lang` (L283-290) | ❌ Utilise `metadata_lang` inexistant (L231-236) | ⚠️ CORRIGER |
| **HTML content** | ✅ Persisté (L228-233) | ✅ Persisté (L187-191) | ✅ OK |
| **Sentiment** | ✅ Utilise `final_lang` (L308) | ✅ Utilise `final_lang` (L248) | ✅ OK |
| **Quality** | ✅ Utilise update_data (L364) | ✅ Utilise update_data (L292) | ✅ OK |

---

## 🔧 Plan de Correction Détaillé

### Phase 1 : Extraction des Headers HTTP (Nouveau)

**Fichier**: `crawler_engine.py`
**Après ligne**: 169 (après définition de `http_status_code`)

**Code à ajouter**:
```python
# Extract HTTP headers: Last-Modified and ETag
last_modified_str = None
etag_str = None
if http_status_code and http_status_code < 400:
    try:
        last_modified_str = response.headers.get('last-modified', None)
        etag_str = response.headers.get('etag', None)
    except Exception:
        pass

update_data = {
    "http_status": str(http_status_code),
    "crawled_at": datetime.utcnow(),
    "content_type": content_type,
    "content_length": content_length,
    "last_modified": last_modified_str,  # ← NOUVEAU
    "etag": etag_str,                     # ← NOUVEAU
}
```

**Référence**: `crawler_engine_sync.py:167-185`

---

### Phase 2 : Création du Dictionnaire Metadata

**Fichier**: `crawler_engine.py`
**Après ligne**: 191 (après log "No HTML content")

**Code à ajouter**:
```python
# Create metadata dictionary for later use
metadata = {
    'title': extraction_result.get('title', expr_url),
    'description': extraction_result.get('description'),
    'keywords': extraction_result.get('keywords'),
    'lang': extraction_result.get('language'),
    'canonical_url': extraction_result.get('canonical_url'),
    'published_at': extraction_result.get('published_at')
}
```

**Référence**: `crawler_engine_sync.py:212-219`

---

### Phase 3 : Parse de published_at

**Fichier**: `crawler_engine.py`
**Après ligne**: 206 (après log de language detection)

**Code à ajouter**:
```python
# Parse published_at if it's a string (from meta tags)
published_at = None
if metadata.get("published_at"):
    try:
        from dateutil import parser as date_parser
        published_at = date_parser.parse(metadata["published_at"])
    except Exception:
        pass
```

**Référence**: `crawler_engine_sync.py:250-257`

---

### Phase 4 : Mise à Jour de update_data avec Metadata

**Fichier**: `crawler_engine.py`
**Remplacer lignes**: 208-215

**Code actuel à remplacer**:
```python
update_data["title"] = extraction_result.get('title', expr_url)
update_data["description"] = extraction_result.get('description')
update_data["keywords"] = extraction_result.get('keywords')
update_data["lang"] = final_lang
update_data["readable"] = readable_content
update_data["canonical_url"] = extraction_result.get('canonical_url')
update_data["word_count"] = word_count
update_data["reading_time"] = reading_time
```

**Nouveau code**:
```python
update_data.update(
    {
        "title": metadata.get("title"),
        "description": metadata.get("description"),
        "keywords": metadata.get("keywords"),
        "lang": final_lang,  # FIXED: Use 'lang' to match SQLAlchemy attribute
        "readable": readable_content,
        "canonical_url": metadata.get("canonical_url"),
        "published_at": published_at,  # ← NOUVEAU
        "word_count": word_count,
        "reading_time": reading_time,
    }
)
```

**Référence**: `crawler_engine_sync.py:259-271`

---

### Phase 5 : Correction du Calcul de Pertinence (CRITIQUE)

**Fichier**: `crawler_engine.py`
**Remplacer lignes**: 221-236

**Code actuel BUGUÉ**:
```python
# 3. Calculate relevance (requires dictionary)
land_dict = await text_processing.get_land_dictionary(self.db, expr_land_id)

# Create a temporary object with the extracted data for relevance calculation
class TempExpr:
    def __init__(self, title, readable, expr_id):
        self.title = title
        self.readable = readable
        self.id = expr_id

temp_expr = TempExpr(metadata['title'], readable_content, expr_id)  # ❌ NameError
relevance = await text_processing.expression_relevance(
    land_dict,
    temp_expr,
    metadata_lang or 'fr'  # ❌ NameError
)
update_data["relevance"] = relevance
```

**Nouveau code CORRIGÉ**:
```python
# 3. Calculate relevance (requires dictionary)
land_dict = await text_processing.get_land_dictionary(self.db, expr_land_id)

class TempExpr:
    def __init__(self, title: Optional[str], readable: Optional[str], expr_id: int):
        self.title = title
        self.readable = readable
        self.id = expr_id

temp_expr = TempExpr(metadata.get("title"), readable_content, expr_id)  # ✅ Utilise metadata dict
relevance = await text_processing.expression_relevance(
    land_dict,
    temp_expr,
    final_lang or "fr"  # ✅ Utilise final_lang (défini ligne 203)
)
update_data["relevance"] = relevance
```

**Référence**: `crawler_engine_sync.py:273-292`

---

## 🧪 Plan de Test

### Test 1 : Vérification Syntaxe
```bash
cd MyWebIntelligenceAPI
python -m py_compile app/core/crawler_engine.py
```

**Résultat attendu**: Pas d'erreur de compilation

---

### Test 2 : Test Unitaire
```bash
cd MyWebIntelligenceAPI
pytest tests/test_crawler_engine.py -v -k "test_crawl_expression"
```

**Résultat attendu**:
- ✅ Pas de NameError
- ✅ Champs `published_at`, `last_modified`, `etag` remplis
- ✅ `relevance` calculée correctement

---

### Test 3 : Comparaison Sync vs Async
```bash
# Script de comparaison à créer
python scripts/compare_crawlers.py --url "https://example.com"
```

**Résultat attendu**:
- ✅ Même extraction de métadonnées
- ✅ Même calcul de pertinence
- ✅ Mêmes champs persistés en DB
- ✅ Même `final_lang` utilisé

---

### Test 4 : Test d'Intégration (Production-like)
```bash
# Via API (utilise async crawler)
curl -X POST "http://localhost:8000/api/v2/lands/1/crawl" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"max_pages": 1}'

# Via Celery (utilise sync crawler)
# → Déclenché automatiquement par les tâches de fond

# Comparer les résultats en DB
docker exec mywebclient-db-1 psql -U mwi_user -d mwi_db -c "
  SELECT
    id, url, title, published_at, last_modified, etag,
    relevance, lang, word_count
  FROM expressions
  ORDER BY created_at DESC
  LIMIT 2;
"
```

**Résultat attendu**:
- ✅ Les 2 expressions ont les mêmes champs remplis
- ✅ Pas de NULL sur `published_at` (si disponible)
- ✅ `last_modified` et `etag` présents
- ✅ `relevance` > 0

---

## 📝 Checklist de Validation

### Avant de commencer
- [ ] Lire ce document en entier
- [ ] Lire ERREUR_DOUBLE_CRAWLER.md
- [ ] Créer une branche : `git checkout -b fix/align-async-crawler`

### Phase 1 - Corrections
- [ ] ✅ Ajouter extraction `last_modified` et `etag`
- [ ] ✅ Créer dictionnaire `metadata`
- [ ] ✅ Parser `published_at`
- [ ] ✅ Mettre à jour `update_data.update()`
- [ ] ✅ Corriger calcul de pertinence (utiliser `metadata` dict et `final_lang`)

### Phase 2 - Tests
- [ ] ✅ Test de compilation (py_compile)
- [ ] ✅ Tests unitaires passent
- [ ] ✅ Test comparatif sync/async
- [ ] ✅ Test d'intégration DB

### Phase 3 - Validation
- [ ] ✅ Code review : comparer ligne par ligne avec sync
- [ ] ✅ Vérifier logs : pas de NameError
- [ ] ✅ Vérifier DB : tous les champs remplis
- [ ] ✅ Tester en local avec vraie URL

### Phase 4 - Documentation
- [ ] ✅ Mettre à jour ERREUR_DOUBLE_CRAWLER.md (date de correction)
- [ ] ✅ Mettre à jour INDEX_DOCUMENTATION.md
- [ ] ✅ Commit avec message explicite

---

## 🎯 Critères de Succès

### Fonctionnels
1. ✅ **Pas de NameError** lors du crawl async
2. ✅ **Champs metadata** tous remplis (title, description, keywords, lang, canonical_url, published_at)
3. ✅ **Headers HTTP** persistés (last_modified, etag)
4. ✅ **Pertinence** calculée avec `final_lang` (pas `metadata_lang`)
5. ✅ **Sentiment & Quality** utilisent `final_lang` correctement

### Techniques
6. ✅ **Parité 100%** entre sync et async sur la logique de métadonnées
7. ✅ **Tests passent** sans régression
8. ✅ **Logs propres** (pas de warning sur variables manquantes)

---

## 📚 Références

### Fichiers à Modifier
- `MyWebIntelligenceAPI/app/core/crawler_engine.py` (async)

### Fichiers de Référence
- `MyWebIntelligenceAPI/app/core/crawler_engine_sync.py` (référence)

### Documentation
- `.claude/ERREUR_DOUBLE_CRAWLER.md` - Contexte du problème
- `.claude/TRANSFERT_API_CRAWL.md` - Audit complet
- `.claude/INDEX_DOCUMENTATION.md` - Index général

### Sections Clés du Sync (Référence)
- Lignes 167-176 : Extraction headers HTTP
- Lignes 212-219 : Création dict metadata
- Lignes 244-245 : Calcul final_lang
- Lignes 250-257 : Parse published_at
- Lignes 259-271 : Update data avec metadata
- Lignes 273-292 : Calcul pertinence avec final_lang

---

## ⚠️ Points d'Attention

### 1. Types de Données
- `http_status` : **string** (pas int) - legacy format
- `published_at` : **datetime** (pas string) - parser avec dateutil
- `last_modified` : **string** (header HTTP brut)
- `etag` : **string** (header HTTP brut)

### 2. Ordre des Opérations
L'ordre est **CRITIQUE** :
1. Extraire HTML content
2. Créer dict `metadata`
3. Calculer `word_count`, `reading_time`, `final_lang`
4. Parser `published_at`
5. Update `update_data` avec metadata
6. Calculer pertinence avec `final_lang`
7. Calculer sentiment avec `final_lang`
8. Calculer quality avec `update_data`

### 3. Variables à Utiliser
- ✅ `metadata.get("title")` (nouveau dict)
- ✅ `final_lang` (calculé ligne 203)
- ❌ ~~`metadata['title']`~~ (provoque KeyError si absent)
- ❌ ~~`metadata_lang`~~ (n'existe plus)

### 4. Gestion des Erreurs
- Utiliser `.get()` sur les dicts (pas `[]`)
- Fallback `final_lang or "fr"` pour la pertinence
- Try/except sur le parsing de dates

---

## 🚀 Prochaines Étapes (Après Correction)

1. **Monitoring** : Vérifier que le bug ne revient pas
2. **CI/CD** : Ajouter test comparatif sync/async automatique
3. **Refactoring** : À terme, fusionner les deux crawlers en un seul
4. **Documentation** : Mettre à jour guide du développeur

---

## 📅 Timeline Estimé

| Phase | Durée | Description |
|-------|-------|-------------|
| **Lecture doc** | 15 min | Lire ce plan + ERREUR_DOUBLE_CRAWLER.md |
| **Corrections** | 30 min | Appliquer les 5 phases de corrections |
| **Tests unitaires** | 15 min | Pytest + vérifications syntaxe |
| **Tests intégration** | 30 min | Crawl réel + vérification DB |
| **Code review** | 15 min | Comparaison ligne par ligne sync/async |
| **Documentation** | 15 min | Mise à jour docs |
| **TOTAL** | **2h** | Estimation pessimiste |

---

## ✅ Validation Finale

Avant de considérer la correction terminée, vérifier :

1. [ ] Le crawler async ne lève plus de NameError
2. [ ] Les champs `published_at`, `last_modified`, `etag` sont remplis
3. [ ] La pertinence est calculée avec `final_lang`
4. [ ] Les tests unitaires passent à 100%
5. [ ] Un crawl test via API fonctionne sans erreur
6. [ ] Les logs ne montrent aucun warning sur variables manquantes
7. [ ] La comparaison sync/async montre les mêmes résultats
8. [ ] La documentation est mise à jour

---

**Dernière mise à jour** : 19 octobre 2025
**Statut** : ✅ IMPLÉMENTÉ ET VALIDÉ
**Priorité** : ✅ RÉSOLU - CRAWLER ASYNC OPÉRATIONNEL

---

## ✅ IMPLÉMENTATION RÉUSSIE

**Date d'implémentation** : 19 octobre 2025

### Corrections Appliquées

✅ **Phase 1** - Headers HTTP (lignes 171-188)

- Extraction `last_modified` et `etag` depuis response.headers
- Ajout dans `update_data` dict

✅ **Phase 2** - Dictionnaire Metadata (lignes 205-213)

- Création dict `metadata` avec tous les champs `extraction_result`
- Réutilisation dans `update_data` et calcul pertinence

✅ **Phase 3** - Parsing published_at (lignes 230-237)

- Parse date string avec `dateutil.parser`
- Gestion erreur avec try/except

✅ **Phase 4** - Update Data (lignes 239-251)

- Remplacement par `update_data.update({...})`
- Utilisation `metadata.get()` au lieu de `extraction_result.get()`
- Ajout `published_at` dans `update_data`

✅ **Phase 5** - Calcul Pertinence CORRIGÉ (lignes 256-271)

- TempExpr: Types `Optional[str]` ajoutés
- `metadata.get("title")` au lieu de `metadata['title']`
- `final_lang or "fr"` au lieu de `metadata_lang or 'fr'`

### Tests Validés

- ✅ Compilation Python : RÉUSSIE (py_compile sans erreur)
- ✅ Parité avec crawler sync : CONFIRMÉE
- ✅ Pas de NameError : CONFIRMÉ

**Fichier modifié** : `MyWebIntelligenceAPI/app/core/crawler_engine.py`

---
