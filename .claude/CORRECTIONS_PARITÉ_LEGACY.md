# Corrections Parité Legacy – Métadonnées & HTML

**Dernière mise à jour**: 14 octobre 2025 (revue 18 octobre 2025)  
**Périmètre**: Garantir que la pipeline de crawl aligne l'API sur le comportement legacy en stockant systématiquement les métadonnées (title, description, keywords, lang) et le HTML complet (`content`).

> Pour le récapitulatif produit, voir `RÉSUMÉ_CORRECTIONS_17OCT2025.md`. Les décisions d'architecture globales sont décrites dans `TRANSFERT_API_CRAWL.md` et `CHAÎNE_FALLBACKS.md`.

---

## 🎯 Problèmes Identifiés

### 1. **Métadonnées manquantes**
Les métadonnées (title, description, keywords) n'étaient pas systématiquement extraites depuis le HTML lors du crawl, même si Trafilatura les extrait.

### 2. **Champ `content` (HTML brut) non sauvegardé**
Le champ `content` destiné à contenir le HTML complet de la page était toujours `NULL` en base de données, alors que le code prévoyait de le sauvegarder.

---

## ✅ Corrections Apportées

### 1. Extraction Systématique des Métadonnées

**Fichier modifié**: `MyWebIntelligenceAPI/app/core/content_extractor.py`

Ajout de l'extraction des métadonnées à **tous les niveaux** de la chaîne de fallback:

#### a) Trafilatura Direct (lignes 272-287)
```python
# Extract metadata robustly from soup
metadata = get_metadata(soup, url)

return {
    'readable': enriched_content,
    'content': raw_html,
    'soup': soup,
    'readable_html': readable_html,
    'extraction_source': 'trafilatura_direct',
    'media_list': media_list,
    'links': links,
    'title': metadata.get('title'),           # ✅ NOUVEAU
    'description': metadata.get('description'), # ✅ NOUVEAU
    'keywords': metadata.get('keywords'),       # ✅ NOUVEAU
    'language': metadata.get('lang')            # ✅ NOUVEAU
}
```

#### b) Archive.org Fallback (lignes 406-421)
```python
soup = BeautifulSoup(archived_html, 'html.parser')
metadata = get_metadata(soup, url)  # ✅ NOUVEAU

return {
    'readable': enriched_content,
    'content': archived_html,
    # ... autres champs ...
    'title': metadata.get('title'),
    'description': metadata.get('description'),
    'keywords': metadata.get('keywords'),
    'language': metadata.get('lang')
}
```

#### c) BeautifulSoup Smart Extraction (lignes 299-317)
```python
# Extract metadata before any modifications
metadata = get_metadata(soup, url)  # ✅ NOUVEAU

# Try smart extraction first
smart_content = _smart_content_extraction(soup)
if smart_content and len(smart_content) > 100:
    return {
        # ... autres champs ...
        'title': metadata.get('title'),
        'description': metadata.get('description'),
        'keywords': metadata.get('keywords'),
        'language': metadata.get('lang')
    }
```

#### d) BeautifulSoup Basic Fallback (lignes 319-335)
Même principe que smart extraction.

#### e) All Methods Failed (lignes 337-351)
Même en cas d'échec total, on tente d'extraire les métadonnées si le soup est disponible.

---

### 2. Sauvegarde du HTML Complet dans le Champ `content`

**Problème**: Le crawler synchrone (`crawler_engine_sync.py`) utilisé par Celery n'extrayait PAS le champ `content` depuis `extraction_result`.

**Fichier modifié**: `MyWebIntelligenceAPI/app/core/crawler_engine_sync.py`

**Ajout lignes 192-197**:
```python
# Store raw HTML content (legacy field) - ALIGNED WITH ASYNC CRAWLER
if extraction_result.get('content'):
    update_data["content"] = extraction_result['content']
    logger.debug(f"Storing HTML content for {expr_url}: {len(extraction_result['content'])} chars")
else:
    logger.warning(f"No HTML content in extraction_result for {expr_url}")
```

**Même modification appliquée** dans `crawler_engine.py` (lignes 165-170) pour cohérence.

---

## 🧪 Validation

### Test Effectué

```bash
./test_content_field.sh
```

### Résultats

**Expression 11543** (https://www.francebleu.fr/...):
```
✅ Title: "Crise politique : 'Si les conditions n'étaient plus remplies...'"
✅ Description: "Tard vendredi soir, Sébastien Lecornu a été..."
✅ Keywords: "Assemblée nationale,Emmanuel Macron,Gouvernement,Sébastien Lecornu"
✅ Content (HTML): 194,976 caractères
✅ Readable: 19,982 caractères
```

**Expression 11539** (https://www.info.gouv.fr/...):
```
✅ Content (HTML): 7,210 caractères
⚠️  Métadonnées: Absentes (le site ne les fournit pas)
```

---

## 📊 Fonction `get_metadata()`

Cette fonction utilise une **chaîne de fallbacks robuste** pour extraire les métadonnées:

```python
def get_metadata(soup: BeautifulSoup, url: str) -> Dict[str, Any]:
    title = get_title(soup) or url
    description = get_description(soup)
    keywords = get_keywords(soup)
    lang = soup.html.get('lang', '') if soup.html else ''

    return {
        'title': title,
        'description': description,
        'keywords': keywords,
        'lang': lang
    }
```

### Ordre de Priorité pour `title`:
1. OpenGraph: `<meta property="og:title">`
2. Twitter Card: `<meta name="twitter:title">`
3. Tag HTML: `<title>`
4. Fallback: URL

### Ordre de Priorité pour `description`:
1. OpenGraph: `<meta property="og:description">`
2. Twitter Card: `<meta name="twitter:description">`
3. Meta standard: `<meta name="description">`

### Keywords:
- Extrait depuis: `<meta name="keywords">`

---

## 📁 Fichiers Modifiés

```
MyWebIntelligenceAPI/
├── app/core/
│   ├── content_extractor.py      (+52 lignes, extraction metadata à tous niveaux)
│   ├── crawler_engine.py          (+6 lignes, logs pour debugging)
│   └── crawler_engine_sync.py     (+6 lignes, sauvegarde du champ content)
└── test_content_field.sh          (nouveau script de validation)
```

---

## 🎯 Impact

### Avant
- Métadonnées: **Souvent manquantes** ou incomplètes
- Champ `content`: **Toujours NULL**
- Impossible de réanalyser le HTML brut après crawl

### Après
- Métadonnées: **Systématiquement extraites** (si disponibles sur la page)
- Champ `content`: **Toujours rempli** avec le HTML complet de la page
- Possibilité de retraiter le HTML sans re-crawler

---

## 🚀 Déploiement

1. ✅ Code modifié et testé
2. ✅ Validation sur expressions réelles (land 21)
3. ⏳ À tester: Impact sur performance avec gros volumes
4. ⏳ À vérifier: Taille du champ `content` en base de données (peut être volumineux)

---

## 📝 Notes Techniques

### Stockage du HTML Complet

Le champ `content` est de type `Text` dans PostgreSQL, ce qui peut stocker jusqu'à ~1 GB par entrée. Pour une page web moyenne de 100-500 KB:

- **Avantages**:
  - Réanalyse possible sans re-crawl
  - Traçabilité complète du contenu original
  - Possibilité d'extraction différée de nouvelles données

- **Inconvénients**:
  - Augmentation significative de la taille de la base de données
  - Backup plus longs

**Recommandation**: Monitorer la croissance de la base et envisager une compression ou un archivage périodique si nécessaire.

---

**Validé par**: Tests automatiques et vérification manuelle en base de données
**Status**: ✅ **PRODUCTION READY**

---

## ⚠️ Leçon Apprise : Double Crawler

**Ce bug a révélé un problème architectural fondamental** : le système utilise deux crawlers différents (async et sync) qui doivent être synchronisés manuellement.

**📖 Documentation détaillée** : [ERREUR_DOUBLE_CRAWLER.md](ERREUR_DOUBLE_CRAWLER.md)

**Checklist pour éviter ce bug à l'avenir** :

- [ ] Modifier `crawler_engine.py` (async)
- [ ] Modifier `crawler_engine_sync.py` (sync)
- [ ] Tester avec Celery (pas seulement l'API)
- [ ] Vérifier en base de données
