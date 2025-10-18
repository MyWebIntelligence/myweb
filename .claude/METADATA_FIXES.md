# Corrections des métadonnées manquantes - 2025-10-17

## Problèmes corrigés

### 1. ✅ `published_at` (date de publication)

**Avant** : Toujours `null`

**Cause** : 
- Aucune extraction depuis Trafilatura (`meta_obj.date`)
- Aucune extraction depuis les meta tags HTML (`article:published_time`, `datePublished`, etc.)

**Solution** :
- Ajout fonction `get_published_date()` dans `content_extractor.py` avec cascade de fallbacks :
  1. `article:published_time` (Open Graph)
  2. `datePublished` (Schema.org)
  3. `dc.date` (Dublin Core)
  4. `date` (generic)
  5. `published_time` (generic)
- Extraction depuis `trafilatura.extract_metadata().date`
- Parsing avec `python-dateutil` dans `crawler_engine_sync.py`

**Fichiers modifiés** :
- `app/core/content_extractor.py` : Ajout `get_published_date()` et intégration dans le pipeline
- `app/core/crawler_engine_sync.py` : Parsing et stockage de `published_at`
- `requirements.txt` : Ajout de `python-dateutil==2.8.2`

---

### 2. ✅ `language` (langue du contenu)

**Avant** : Souvent `null` malgré le code de détection

**Cause** :
- `langdetect` pouvait échouer silencieusement
- Pas de gestion robuste des exceptions
- Fallback non systématique

**Solution** :
- Amélioration du gestionnaire d'exceptions dans `detect_language()` :
  - `LangDetectException` → fallback
  - `ImportError` → fallback avec warning
  - Exception générique → fallback avec warning
- Meilleur logging pour le debugging
- Fallback systématique en cas d'échec

**Fichiers modifiés** :
- `app/utils/text_utils.py` : Refactoring complet de `detect_language()`

---

### 3. ✅ `canonical_url` (URL canonique)

**Avant** : `null`

**Cause** : Code d'extraction existant mais **jamais persisté** dans la base de données

**Solution** :
- Ajout de `canonical_url` dans `update_data` du crawler
- Déjà extrait correctement via `get_canonical_url()`

**Fichiers modifiés** :
- `app/core/crawler_engine_sync.py` : Ajout à `update_data`

---

### 4. ✅ `last_modified` et `etag` (headers HTTP)

**Avant** : Toujours `null`

**Cause** : Headers HTTP extraits mais **jamais persistés** dans la base de données

**Solution** :
- Extraction de `Last-Modified` et `ETag` depuis `response.headers`
- Ajout dans `update_data` du crawler

**Fichiers modifiés** :
- `app/core/crawler_engine_sync.py` : Extraction et stockage des headers

---

### 5. ⚠️ `content_length` (taille du contenu)

**Statut** : Comportement normal (pas un bug)

**Explication** :
- Dépend du header HTTP `Content-Length` envoyé par le serveur
- Si le serveur utilise la compression dynamique ou le transfert par chunks, ce header peut être absent
- Le code extrait correctement ce header quand disponible

**Aucune modification nécessaire**

---

### 6. ✅ Warning NLTK punkt

**Avant** : 
```
NLTK 'punkt'/'punkt_tab' not available; using simple tokenizer fallback
```

**Cause** : `punkt_tab` pas téléchargé dans le Dockerfile

**Solution** :
- Ajout de `punkt_tab` dans le téléchargement NLTK
- Fallback en cas d'échec du téléchargement

**Fichiers modifiés** :
- `Dockerfile` : `RUN python -m nltk.downloader punkt punkt_tab || python -m nltk.downloader punkt`

---

## Résumé des fichiers modifiés

1. **app/core/content_extractor.py**
   - Ajout `get_published_date()` avec 5 fallbacks
   - Intégration `published_at` dans `get_metadata()`
   - Extraction depuis Trafilatura `meta_obj.date`

2. **app/core/crawler_engine_sync.py**
   - Ajout extraction `Last-Modified` et `ETag`
   - Parsing `published_at` avec `python-dateutil`
   - Stockage de `canonical_url`, `published_at`, `last_modified`, `etag`

3. **app/utils/text_utils.py**
   - Refactoring complet `detect_language()`
   - Gestion robuste des exceptions
   - Meilleur logging

4. **requirements.txt**
   - Ajout `python-dateutil==2.8.2`

5. **Dockerfile**
   - Téléchargement `punkt_tab` pour NLTK

6. **tests/test_metadata_extraction.py** (nouveau)
   - Tests unitaires pour vérifier les extractions

---

## Tests recommandés

### 1. Rebuild Docker
```bash
docker-compose build --no-cache mywebintelligenceapi
docker-compose up -d
```

### 2. Vérifier les logs
```bash
docker-compose logs -f mywebintelligenceapi | grep -E "punkt|language|published"
```

### 3. Lancer un crawl de test
```bash
./MyWebIntelligenceAPI/tests/test-crawl-simple.sh
```

### 4. Vérifier les métadonnées dans la base
```sql
SELECT 
    url,
    published_at,
    language,
    canonical_url,
    last_modified,
    etag,
    content_length
FROM expressions
WHERE crawled_at > NOW() - INTERVAL '1 hour'
LIMIT 10;
```

### 5. Tests unitaires (optionnel)
```bash
docker-compose exec mywebintelligenceapi pytest tests/test_metadata_extraction.py -v
```

---

## Résultats attendus

Après rebuild et nouveau crawl :
- ✅ `published_at` : Date ISO 8601 (ex: `2025-10-11T09:05:23+02:00`)
- ✅ `language` : Code ISO 639-1 (ex: `fr`, `en`)
- ✅ `canonical_url` : URL canonique si présente
- ✅ `last_modified` : Date HTTP si présente
- ✅ `etag` : ETag HTTP si présent
- ⚠️ `content_length` : Présent si le serveur l'envoie
- ✅ Plus de warning NLTK punkt

---

## Notes importantes

1. **python-dateutil** : Ajouté pour parser les dates ISO 8601 robustement
2. **Trafilatura priority** : Les métadonnées Trafilatura ont priorité sur BeautifulSoup
3. **Fallbacks** : Chaque extraction a plusieurs fallbacks pour maximiser la couverture
4. **Logging** : Amélioration des logs pour faciliter le debugging

---

## Prochaines étapes recommandées

1. Tester sur un échantillon d'URLs
2. Vérifier les logs pour d'éventuelles erreurs
3. Comparer avec l'ancien système pour validation
4. Monitorer les performances (extraction + parsing)

