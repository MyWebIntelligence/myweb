# Plan de Développement Quality Score - MyWebIntelligence API

**Date de création**: 18 octobre 2025
**Version**: 1.0
**Statut**: Plan détaillé pour implémentation

---

## 🎯 Objectif

Implémenter un système de scoring automatique de la qualité des expressions crawlées basé sur des heuristiques et métadonnées existantes (HTTP status, richesse textuelle, cohérence, pertinence), en respectant l'architecture du double crawler et les principes de parité legacy.

---

## ⚡ Décisions Clés (TL;DR)

### 1. Approche Technique : **Heuristique Pondérée**
- **Méthode** : Score composite basé sur métadonnées existantes
- **Pas de ML/API** : 100% déterministe et gratuit
- **Format** : Float 0.0 à 1.0 (ou 0-100 selon besoin métier)

### 2. Installation
```bash
# AUCUNE dépendance supplémentaire !
# Utilise uniquement les données déjà crawlées
```

### 3. Composants du Score (5 blocs)

| Bloc | Poids | Critères |
|------|-------|----------|
| **Accès** | 30% | HTTP 200, content-type HTML, pas de redirect |
| **Structure** | 15% | Title, description, keywords présents |
| **Richesse** | 25% | Word count optimal (150-5000), ratio texte/HTML |
| **Cohérence** | 20% | Reading time, langue vs land, relevance |
| **Intégrité** | 10% | LLM validation, fraîcheur, métadonnées complètes |

### 4. Intégration Simple
- **0 nouveau champ DB** : `quality_score` existe déjà !
- **Nouveaux champs optionnels** : `quality_flags`, `quality_reason`
- **Double crawler** : Même logique async + sync

### 5. Usage API
```bash
# Score calculé automatiquement lors du crawl
POST /api/v2/lands/36/crawl

# Filtrer par qualité
GET /api/v2/lands/36/expressions?min_quality=0.7
```

### 6. Exemple de Scores

| Type d'Expression | Score | Raison |
|-------------------|-------|--------|
| Article complet 2000 mots | 0.95 | ✅ Tous critères |
| Page courte 50 mots | 0.35 | ⚠️ Pauvre en contenu |
| Erreur 404 | 0.0 | ❌ HTTP error |
| PDF (non-HTML) | 0.0 | ❌ Non parsable |
| Langue incorrecte | 0.45 | ⚠️ Hors cible |

---

## 📊 État des Lieux

### ✅ Existant
- **Champ `quality_score`** : Présent dans le modèle `Expression` (ligne 234, `models.py`)
  ```python
  quality_score = Column(Float, nullable=True)  # Score de qualité du contenu
  ```
- **Valeur actuelle** : Toujours `null` dans toutes les expressions existantes
- **Type** : `Float` (0.0 à 1.0 attendu)

### ✅ Métadonnées Disponibles (Déjà Crawlées)

Le quality_score peut être calculé avec les données **déjà présentes** :

```python
# Bloc Accès
http_status: int              # 200, 404, 500, etc.
content_type: str             # "text/html", "application/pdf", etc.
crawled_at: datetime          # Timestamp du crawl

# Bloc Structure
title: str                    # Titre de la page
description: str              # Meta description
keywords: str                 # Meta keywords
canonical_url: str            # URL canonique

# Bloc Richesse
content: str                  # HTML complet
readable: str                 # Contenu lisible (markdown)
word_count: int               # Nombre de mots
content_length: int           # Taille HTML en bytes
reading_time: int             # Temps de lecture (minutes)

# Bloc Cohérence
lang: str                     # Langue détectée ("fr", "en")
relevance: float              # Score de pertinence vs mots-clés
depth: int                    # Profondeur de crawl
published_at: datetime        # Date de publication (si disponible)

# Bloc Intégrité
valid_llm: str                # "oui"/"non" (validation LLM)
valid_model: str              # Modèle utilisé pour validation
readable_at: datetime         # Timestamp extraction readable
approved_at: datetime         # Timestamp traitement complet
```

### ❌ Manquant
- Service de calcul `QualityScorer`
- Intégration dans crawlers (sync + async)
- **2 nouveaux champs optionnels** : `quality_flags`, `quality_reason`
- Tests unitaires et d'intégration
- Documentation métier (grille de pondération)

### 📋 Nouveaux Champs Optionnels (Traçabilité)

Ajouter à la table `expressions` (optionnel mais recommandé) :

```python
# Dans models.py (à ajouter après quality_score ligne 234)
quality_flags = Column(JSON, nullable=True)     # ["http_error", "short_content", "wrong_lang"]
quality_reason = Column(Text, nullable=True)    # Explication textuelle du score
quality_computed_at = Column(DateTime, nullable=True)  # Timestamp du calcul
```

**Avantage** : Permet de **déboguer** pourquoi un score est faible.

**Migration requise** : Alembic pour ajouter les 3 nouveaux champs (si décision de les inclure).

---

## 🏗️ Architecture Cible

### Composants Principaux

```
┌─────────────────────────────────────────────────────────────┐
│                    QUALITY PIPELINE                          │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  1. QualityScorer (services/)                               │
│     └─ Calculs heuristiques purs (déterministes)           │
│                                                              │
│  2. Intégration Crawlers                                    │
│     ├─ crawler_engine.py (async)                           │
│     └─ crawler_engine_sync.py (sync) ⚠️ DOUBLE CRAWLER     │
│                                                              │
│  3. API Endpoints                                           │
│     ├─ GET /expressions (avec quality_score filtrable)     │
│     └─ POST /lands/{id}/reprocess-quality (batch)          │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

**Note clé** : Pas de dépendances externes, tout est calculé à partir des métadonnées existantes.

---

## 📋 Plan de Développement Détaillé

---

## 🔍 ÉTAPE 1 – Audit de l'Existant (Durée: 1h)

### Objectif
Cartographier toutes les métadonnées disponibles et identifier les points d'injection.

### Actions

#### 1.1 Cartographie Champs Disponibles

- [x] **Vérifier champ `quality_score` dans `Expression`**
  - Fichier: `MyWebIntelligenceAPI/app/db/models.py:234`
  - Type: `Float`
  - Nullable: `True`

- [ ] **Inventorier métadonnées exploitables**
  ```python
  # Script de vérification
  docker exec mywebclient-db-1 psql -U mwi_user -d mwi_db -c "
  SELECT
    COUNT(*) as total,
    COUNT(http_status) as has_http,
    COUNT(word_count) as has_words,
    COUNT(readable) as has_readable,
    COUNT(lang) as has_lang,
    COUNT(relevance) as has_relevance,
    AVG(word_count) as avg_words,
    AVG(relevance) as avg_relevance
  FROM expressions
  WHERE land_id = 36;  -- Land de test
  "
  ```

- [ ] **Analyser distribution des valeurs**
  ```sql
  -- HTTP status distribution
  SELECT http_status, COUNT(*)
  FROM expressions
  GROUP BY http_status
  ORDER BY COUNT(*) DESC;

  -- Word count ranges
  SELECT
    CASE
      WHEN word_count < 100 THEN 'very_short'
      WHEN word_count < 500 THEN 'short'
      WHEN word_count < 2000 THEN 'medium'
      ELSE 'long'
    END as length_category,
    COUNT(*)
  FROM expressions
  GROUP BY length_category;

  -- Language distribution
  SELECT lang, COUNT(*)
  FROM expressions
  GROUP BY lang;
  ```

#### 1.2 Identifier Points d'Injection

- [ ] **Localiser dans crawlers**
  - `crawler_engine.py` : Après extraction contenu + métadonnées (ligne ~300)
  - `crawler_engine_sync.py` : Même emplacement (ligne ~250)

- [ ] **Vérifier schémas Pydantic**
  - Fichier: `MyWebIntelligenceAPI/app/schemas/expression.py`
  - S'assurer que `ExpressionOut` expose `quality_score`

- [ ] **Vérifier exports**
  - `export_service.py` : Inclut-il déjà `quality_score` dans CSV/JSON ?

#### 1.3 État Initial des Tests

- [ ] **Exécuter tests crawl existants**
  ```bash
  ./MyWebIntelligenceAPI/tests/test-crawl-simple.sh

  # Vérifier aucune régression
  # Confirmer quality_score = NULL actuellement
  ```

### Tests Étape 1

```bash
# 1. Rechercher "quality" dans codebase
rg "quality_score" MyWebIntelligenceAPI/ --type py

# 2. Vérifier modèle Expression
grep -A 5 "quality_score" MyWebIntelligenceAPI/app/db/models.py

# 3. Analyse DB
docker exec mywebclient-db-1 psql -U mwi_user -d mwi_db -c \
  "SELECT id, url, quality_score, http_status, word_count, relevance
   FROM expressions
   LIMIT 10;"
```

### Livrables Étape 1
- [x] Liste des champs disponibles avec taux de remplissage
- [ ] Distribution statistique des valeurs clés (word_count, http_status, etc.)
- [ ] Identification des points d'injection dans crawlers (numéros de lignes)
- [ ] Rapport d'état initial (aucune expression avec quality_score)

---

## 📐 ÉTAPE 2 – Cadrage Métier (Durée: 2h)

### Objectif
Définir les objectifs métier, l'échelle du score, et les seuils de décision.

### Actions

#### 2.1 Définir Objectifs Métier

**Cas d'usage** :

1. **Filtrage automatique**
   - Exclure pages de mauvaise qualité (`quality_score < 0.3`)
   - Ne garder que contenu riche pour analyse (`quality_score > 0.7`)

2. **Priorisation pour analystes**
   - Trier expressions par qualité décroissante
   - Identifier contenu premium pour annotation manuelle

3. **Pondération analyses**
   - Sentiment + Quality → confiance composite
   - Relevance × Quality → score de pertinence ajusté

4. **Monitoring santé du crawl**
   - Taux de pages de qualité par land
   - Détecter problèmes de crawl (trop de 404, contenu vide)

#### 2.2 Valider Échelle et Seuils

**Échelle retenue** : `0.0` à `1.0` (float)

**Seuils métier** :

| Score | Catégorie | Description | Action |
|-------|-----------|-------------|--------|
| `0.0 - 0.2` | Très faible | Erreur HTTP, contenu vide, non-HTML | ❌ Exclure automatiquement |
| `0.2 - 0.4` | Faible | Page courte, pauvre en structure, hors cible | ⚠️ Marquer pour review |
| `0.4 - 0.6` | Moyen | Contenu acceptable mais incomplet | ⚠️ Utiliser avec prudence |
| `0.6 - 0.8` | Bon | Article standard avec métadonnées correctes | ✅ Qualité acceptable |
| `0.8 - 1.0` | Excellent | Contenu riche, complet, bien structuré | ✅ Qualité premium |

**Règles de transparence** :

- **Flag explicatif** : Chaque pénalité doit être tracée
  ```python
  quality_flags = [
      "http_error",           # HTTP != 200
      "short_content",        # word_count < 80
      "wrong_language",       # lang ∉ land.lang
      "missing_structure",    # pas de title/description
      "poor_ratio"            # word_count / content_length < 0.1
  ]
  ```

- **Raison textuelle** : Explication en clair
  ```python
  quality_reason = "Score faible (0.25): HTTP 404, contenu vide"
  ```

#### 2.3 Établir Truth Table (20 Cas Extrêmes)

**Fichier** : `tests/data/quality_truth_table.json`

```json
[
  {
    "case_id": 1,
    "description": "Article complet FR 2000 mots",
    "http_status": 200,
    "word_count": 2000,
    "has_title": true,
    "has_description": true,
    "lang": "fr",
    "land_lang": ["fr"],
    "relevance": 3.5,
    "expected_score_min": 0.85,
    "expected_score_max": 1.0,
    "expected_category": "Excellent"
  },
  {
    "case_id": 2,
    "description": "Erreur 404",
    "http_status": 404,
    "word_count": 0,
    "has_title": false,
    "expected_score_min": 0.0,
    "expected_score_max": 0.0,
    "expected_flags": ["http_error", "no_content"],
    "expected_category": "Très faible"
  },
  {
    "case_id": 3,
    "description": "Page courte 50 mots",
    "http_status": 200,
    "word_count": 50,
    "has_title": true,
    "has_description": false,
    "lang": "en",
    "land_lang": ["en"],
    "relevance": 1.0,
    "expected_score_min": 0.25,
    "expected_score_max": 0.40,
    "expected_flags": ["short_content", "missing_structure"],
    "expected_category": "Faible"
  },
  {
    "case_id": 4,
    "description": "Langue incorrecte (DE au lieu de FR)",
    "http_status": 200,
    "word_count": 1500,
    "has_title": true,
    "lang": "de",
    "land_lang": ["fr"],
    "expected_score_min": 0.40,
    "expected_score_max": 0.55,
    "expected_flags": ["wrong_language"],
    "expected_category": "Moyen"
  },
  {
    "case_id": 5,
    "description": "PDF (non-HTML)",
    "http_status": 200,
    "content_type": "application/pdf",
    "expected_score_min": 0.0,
    "expected_score_max": 0.0,
    "expected_flags": ["non_html"],
    "expected_category": "Très faible"
  }
  // ... 15 autres cas
]
```

**Cas à couvrir** :

1. ✅ Article complet optimal
2. ✅ Erreur HTTP (404, 500, 503)
3. ✅ Redirect (301, 302)
4. ✅ Page courte (<80 mots)
5. ✅ PDF ou non-HTML
6. ✅ Langue incorrecte
7. ✅ Pas de title
8. ✅ Ratio texte/HTML faible (<0.1)
9. ✅ Reading time incohérent (<15s ou >20min)
10. ✅ Contenu futur (published_at dans le futur)
11. ✅ Contenu très ancien (>5 ans)
12. ✅ Relevance = 0 (hors sujet)
13. ✅ Contenu validé LLM (valid_llm = "oui")
14. ✅ Contenu sans readable (extraction échouée)
15. ✅ Page moyenne (word_count ~500)
16. ✅ Contenu très long (>10000 mots)
17. ✅ Métadonnées partielles (title mais pas description)
18. ✅ Land multilingue (FR+EN) avec contenu EN
19. ✅ Contenu avec relevance élevée (>5.0)
20. ✅ Contenu crawlé mais non approuvé (approved_at = NULL)

### Tests Étape 2

```python
# tests/unit/test_quality_truth_table.py

def test_truth_table_consistency():
    """Valider que la truth table est cohérente."""
    with open("tests/data/quality_truth_table.json") as f:
        cases = json.load(f)

    for case in cases:
        # Vérifier champs requis
        assert "case_id" in case
        assert "description" in case
        assert "expected_score_min" in case
        assert "expected_score_max" in case

        # Cohérence min/max
        assert case["expected_score_min"] <= case["expected_score_max"]
        assert 0.0 <= case["expected_score_min"] <= 1.0
        assert 0.0 <= case["expected_score_max"] <= 1.0
```

### Livrables Étape 2
- [ ] Document objectifs métier (filtrage, priorisation, pondération)
- [ ] Échelle et seuils validés (0-1, 5 catégories)
- [ ] Truth table 20 cas (`quality_truth_table.json`)
- [ ] Validation PO/data analyst sur pondérations

---

## 🧮 ÉTAPE 3 – Conception du Score (Durée: 3-4h)

### Objectif
Définir la formule heuristique complète avec pondérations et transformations.

### Actions

#### 3.1 Modèle Heuristique Pondéré (5 Blocs)

```python
"""
Quality Score = Σ (Bloc_i × Poids_i)

Total poids = 1.0 (100%)
Score final clampé entre 0.0 et 1.0
"""

# Configuration des poids
WEIGHTS = {
    "access": 0.30,      # 30% - Accessibilité de la page
    "structure": 0.15,   # 15% - Structure HTML/métadonnées
    "richness": 0.25,    # 25% - Richesse du contenu
    "coherence": 0.20,   # 20% - Cohérence et pertinence
    "integrity": 0.10    # 10% - Intégrité pipeline
}
```

---

### 3.2 Bloc 1 : Accès (30%)

**Critères** : HTTP status, content-type, redirections

```python
def score_access(expression: Expression) -> tuple[float, list[str]]:
    """
    Score d'accessibilité (0.0 à 1.0).

    Returns:
        (score, flags)
    """
    score = 0.0
    flags = []

    # HTTP Status (critère bloquant)
    if expression.http_status is None:
        flags.append("no_http_status")
        return 0.0, flags

    if 200 <= expression.http_status < 300:
        score += 1.0  # Full score si 2xx
    elif 300 <= expression.http_status < 400:
        score += 0.5  # Moitié si redirect
        flags.append("redirect")
    else:
        score = 0.0  # Zero si erreur
        flags.append("http_error")
        return score, flags  # Bloquant

    # Content-Type (critère bloquant)
    if expression.content_type:
        if "text/html" in expression.content_type.lower():
            pass  # OK, pas de pénalité
        elif "application/pdf" in expression.content_type.lower():
            flags.append("non_html_pdf")
            return 0.0, flags  # Bloquant
        else:
            flags.append("non_html")
            score *= 0.3  # Grosse pénalité mais pas bloquant

    # Contenu crawlé (vérifie que crawled_at existe)
    if expression.crawled_at is None:
        flags.append("not_crawled")
        return 0.0, flags

    return score, flags
```

**Exemples** :
- HTTP 200 + text/html → `1.0` (✅ parfait)
- HTTP 302 + text/html → `0.5` (⚠️ redirect)
- HTTP 404 → `0.0` (❌ erreur)
- HTTP 200 + application/pdf → `0.0` (❌ non parsable)

---

### 3.3 Bloc 2 : Structure (15%)

**Critères** : Title, description, keywords, canonical

```python
def score_structure(expression: Expression) -> tuple[float, list[str]]:
    """
    Score de structure HTML/métadonnées (0.0 à 1.0).
    """
    score = 0.0
    flags = []
    max_points = 4  # 4 critères

    # Title présent et non vide
    if expression.title and len(expression.title.strip()) > 0:
        score += 0.4  # 40% du score structure
    else:
        flags.append("no_title")

    # Description présente et suffisamment longue
    if expression.description and len(expression.description.strip()) > 20:
        score += 0.3  # 30%
    else:
        flags.append("no_description")

    # Keywords présents
    if expression.keywords and len(expression.keywords.strip()) > 0:
        score += 0.15  # 15%
    else:
        flags.append("no_keywords")

    # Canonical URL (bonne pratique SEO)
    if expression.canonical_url:
        score += 0.15  # 15%
    else:
        flags.append("no_canonical")

    return score, flags
```

**Exemples** :
- Tous présents → `1.0` (✅ structure complète)
- Title seulement → `0.4` (⚠️ structure partielle)
- Aucun → `0.0` (❌ structure absente)

---

### 3.4 Bloc 3 : Richesse (25%)

**Critères** : Word count optimal, ratio texte/HTML, reading time

```python
def score_richness(expression: Expression) -> tuple[float, list[str]]:
    """
    Score de richesse textuelle (0.0 à 1.0).

    Courbe gaussienne centrée sur 1500 mots.
    """
    score = 0.0
    flags = []

    # Word count (50% du score richesse)
    if expression.word_count is None or expression.word_count == 0:
        flags.append("no_content")
        return 0.0, flags

    wc = expression.word_count

    if wc < 80:
        # Trop court, quasi-null
        score_wc = 0.1
        flags.append("very_short_content")
    elif wc < 150:
        # Court mais acceptable
        score_wc = 0.3
        flags.append("short_content")
    elif 150 <= wc <= 5000:
        # Zone optimale : courbe gaussienne centrée sur 1500
        optimal = 1500
        sigma = 1500  # Écart-type large pour tolérance
        score_wc = math.exp(-((wc - optimal) ** 2) / (2 * sigma ** 2))
    else:
        # Très long : décroissance douce
        score_wc = 0.8 - (wc - 5000) / 50000  # Décroit doucement
        score_wc = max(0.5, score_wc)  # Plancher à 0.5
        if wc > 10000:
            flags.append("very_long_content")

    score += score_wc * 0.5

    # Ratio word_count / content_length (30% du score richesse)
    if expression.content_length and expression.content_length > 0:
        ratio = expression.word_count / expression.content_length

        if ratio < 0.05:
            # HTML très lourd, peu de texte (boilerplate, scripts)
            score_ratio = 0.2
            flags.append("poor_text_ratio")
        elif ratio < 0.1:
            score_ratio = 0.5
            flags.append("low_text_ratio")
        elif 0.1 <= ratio <= 0.3:
            # Zone optimale
            score_ratio = 1.0
        else:
            # Trop de texte vs HTML (inhabituel mais OK)
            score_ratio = 0.9

        score += score_ratio * 0.3
    else:
        # Pas de content_length → neutre
        score += 0.3 * 0.5  # Score moyen

    # Reading time cohérent (20% du score richesse)
    if expression.reading_time:
        rt = expression.reading_time  # En minutes

        if rt < 0.25:  # <15 secondes
            score_rt = 0.2
            flags.append("very_short_reading")
        elif rt < 0.5:  # 15-30 secondes
            score_rt = 0.5
            flags.append("short_reading")
        elif 0.5 <= rt <= 15:  # 30s à 15min (zone normale)
            score_rt = 1.0
        elif 15 < rt <= 25:  # 15-25min (long mais OK)
            score_rt = 0.8
        else:  # >25min (suspicieux)
            score_rt = 0.3
            flags.append("very_long_reading")

        score += score_rt * 0.2
    else:
        # Pas de reading_time → neutre
        score += 0.2 * 0.5

    return score, flags
```

**Exemples** :
- 1500 mots, ratio 0.15, reading 5min → `1.0` (✅ optimal)
- 50 mots, ratio 0.02, reading 0.1min → `0.15` (❌ très pauvre)
- 8000 mots, ratio 0.25, reading 30min → `0.75` (⚠️ long mais acceptable)

---

### 3.5 Bloc 4 : Cohérence (20%)

**Critères** : Langue vs land, relevance, fraîcheur

```python
def score_coherence(
    expression: Expression,
    land: Land
) -> tuple[float, list[str]]:
    """
    Score de cohérence avec le land et logique métier (0.0 à 1.0).
    """
    score = 0.0
    flags = []

    # Langue alignée avec land (40% du score cohérence)
    if expression.lang and land.lang:
        land_languages = land.lang if isinstance(land.lang, list) else [land.lang]

        if expression.lang in land_languages:
            score_lang = 1.0
        else:
            score_lang = 0.0
            flags.append("wrong_language")

        score += score_lang * 0.4
    else:
        # Pas de langue détectée → neutre
        score += 0.4 * 0.5
        if not expression.lang:
            flags.append("no_language")

    # Relevance (pertinence mot-clés) (40% du score cohérence)
    if expression.relevance is not None:
        # Normaliser relevance (supposé 0-10 ou plus)
        # Mapper vers 0-1 avec saturation à 5.0
        norm_relevance = min(expression.relevance / 5.0, 1.0)
        score += norm_relevance * 0.4

        if expression.relevance < 0.5:
            flags.append("low_relevance")
    else:
        # Pas de relevance → neutre
        score += 0.4 * 0.5

    # Fraîcheur contenu (20% du score cohérence)
    if expression.published_at:
        from datetime import datetime, timezone
        now = datetime.now(timezone.utc)
        age_days = (now - expression.published_at).days

        if age_days < 0:
            # Publié dans le futur (erreur)
            score_fresh = 0.0
            flags.append("future_date")
        elif age_days < 365:  # <1 an
            score_fresh = 1.0
        elif age_days < 730:  # 1-2 ans
            score_fresh = 0.9
        elif age_days < 1825:  # 2-5 ans
            score_fresh = 0.7
        else:  # >5 ans
            score_fresh = 0.5
            flags.append("old_content")

        score += score_fresh * 0.2
    else:
        # Pas de date de publication → neutre
        score += 0.2 * 0.5

    return score, flags
```

**Exemples** :
- Langue OK, relevance 4.0, publié il y a 6 mois → `0.95` (✅ très cohérent)
- Langue incorrecte, relevance 0.2, publié il y a 8 ans → `0.25` (❌ incohérent)

---

### 3.6 Bloc 5 : Intégrité (10%)

**Critères** : Validation LLM, extraction readable, pipeline complet

```python
def score_integrity(expression: Expression) -> tuple[float, list[str]]:
    """
    Score d'intégrité du pipeline (0.0 à 1.0).
    """
    score = 0.0
    flags = []

    # Validation LLM réussie (40% du score intégrité)
    if expression.valid_llm == "oui":
        score += 0.4
    elif expression.valid_llm == "non":
        score += 0.0
        flags.append("llm_rejected")
    else:
        # Pas de validation LLM → neutre
        score += 0.4 * 0.5

    # Extraction readable réussie (40% du score intégrité)
    if expression.readable_at and expression.readable:
        if len(expression.readable.strip()) > 100:
            score += 0.4
        else:
            score += 0.2
            flags.append("short_readable")
    else:
        score += 0.0
        flags.append("no_readable")

    # Pipeline complet (approved_at présent) (20%)
    if expression.approved_at:
        score += 0.2
    else:
        score += 0.0
        flags.append("not_approved")

    return score, flags
```

**Exemples** :
- LLM validé, readable OK, approved → `1.0` (✅ pipeline complet)
- LLM rejeté, pas de readable → `0.1` (❌ pipeline incomplet)

---

### 3.7 Score Final (Agrégation)

```python
from typing import TypedDict

class QualityResult(TypedDict):
    """Résultat du calcul de qualité."""
    score: float                    # 0.0 à 1.0
    category: str                   # "Excellent", "Bon", "Moyen", etc.
    flags: list[str]                # ["short_content", "wrong_language"]
    reason: str                     # Explication textuelle
    details: dict[str, float]       # Scores par bloc pour debug

def compute_quality_score(
    expression: Expression,
    land: Land
) -> QualityResult:
    """
    Calcule le quality_score complet.

    Returns:
        QualityResult avec score, catégorie, flags, raison
    """
    all_flags = []
    details = {}

    # Bloc 1: Accès (30%)
    access_score, access_flags = score_access(expression)
    all_flags.extend(access_flags)
    details["access"] = access_score

    # Si accès échoue (HTTP erreur), score = 0
    if access_score == 0.0:
        return {
            "score": 0.0,
            "category": "Très faible",
            "flags": all_flags,
            "reason": f"Accès impossible: {', '.join(all_flags)}",
            "details": details
        }

    # Bloc 2: Structure (15%)
    struct_score, struct_flags = score_structure(expression)
    all_flags.extend(struct_flags)
    details["structure"] = struct_score

    # Bloc 3: Richesse (25%)
    rich_score, rich_flags = score_richness(expression)
    all_flags.extend(rich_flags)
    details["richness"] = rich_score

    # Bloc 4: Cohérence (20%)
    coher_score, coher_flags = score_coherence(expression, land)
    all_flags.extend(coher_flags)
    details["coherence"] = coher_score

    # Bloc 5: Intégrité (10%)
    integ_score, integ_flags = score_integrity(expression)
    all_flags.extend(integ_flags)
    details["integrity"] = integ_score

    # Agrégation pondérée
    final_score = (
        access_score * WEIGHTS["access"] +
        struct_score * WEIGHTS["structure"] +
        rich_score * WEIGHTS["richness"] +
        coher_score * WEIGHTS["coherence"] +
        integ_score * WEIGHTS["integrity"]
    )

    # Clamp 0-1 (sécurité)
    final_score = max(0.0, min(1.0, final_score))

    # Déterminer catégorie
    if final_score >= 0.8:
        category = "Excellent"
    elif final_score >= 0.6:
        category = "Bon"
    elif final_score >= 0.4:
        category = "Moyen"
    elif final_score >= 0.2:
        category = "Faible"
    else:
        category = "Très faible"

    # Générer raison textuelle
    if final_score >= 0.8:
        reason = f"Haute qualité ({final_score:.2f}): contenu riche et complet"
    elif final_score >= 0.6:
        reason = f"Qualité acceptable ({final_score:.2f}): contenu standard"
    else:
        # Identifier principale pénalité
        main_issues = []
        if "http_error" in all_flags:
            main_issues.append("erreur HTTP")
        if "short_content" in all_flags or "very_short_content" in all_flags:
            main_issues.append("contenu trop court")
        if "wrong_language" in all_flags:
            main_issues.append("langue incorrecte")
        if "low_relevance" in all_flags:
            main_issues.append("faible pertinence")

        reason = f"Qualité {category.lower()} ({final_score:.2f}): {', '.join(main_issues or all_flags[:2])}"

    return {
        "score": round(final_score, 3),
        "category": category,
        "flags": all_flags,
        "reason": reason,
        "details": details
    }
```

---

### 3.8 Tests de Conception

**Notebook de prototypage** : `tests/notebooks/quality_prototype.ipynb`

```python
# Test sur truth table
import json
from app.services.quality import QualityScorer

with open("tests/data/quality_truth_table.json") as f:
    cases = json.load(f)

scorer = QualityScorer()

for case in cases:
    # Mock expression object
    expr_mock = MockExpression(**case)
    land_mock = MockLand(lang=case.get("land_lang", ["fr"]))

    result = scorer.compute_quality_score(expr_mock, land_mock)

    # Valider score dans fourchette attendue
    assert case["expected_score_min"] <= result["score"] <= case["expected_score_max"], \
        f"Case {case['case_id']}: score {result['score']} hors limites"

    print(f"✅ Case {case['case_id']}: {result['score']:.2f} ({result['category']})")
```

### Livrables Étape 3
- [ ] Formule complète des 5 blocs (code Python)
- [ ] Configuration pondérations (`WEIGHTS` dict)
- [ ] Structure `QualityResult` (TypedDict)
- [ ] Notebook de prototypage validé sur truth table
- [ ] Documentation formule dans docstrings

---

## 🔧 ÉTAPE 4 – Implémentation du Service (Durée: 3h)

### Objectif
Créer le service `QualityScorer` pur et testable.

### Actions

#### 4.1 Créer Service `QualityScorer`

**Nouveau fichier** : `MyWebIntelligenceAPI/app/services/quality_scorer.py`

```python
"""
Quality Scoring Service for MyWebIntelligence API

Computes quality_score based on heuristics and existing metadata.
Pure function service (no external dependencies, deterministic).
"""

import logging
import math
from datetime import datetime, timezone
from typing import TypedDict

from app.db.models import Expression, Land

logger = logging.getLogger(__name__)

# Configuration des poids (modifiable via settings)
WEIGHTS = {
    "access": 0.30,
    "structure": 0.15,
    "richness": 0.25,
    "coherence": 0.20,
    "integrity": 0.10
}

class QualityResult(TypedDict):
    """Résultat du calcul de qualité."""
    score: float
    category: str
    flags: list[str]
    reason: str
    details: dict[str, float]

class QualityScorer:
    """
    Service de calcul du quality_score.

    100% déterministe, basé sur métadonnées existantes.
    Pas de dépendances externes.
    """

    def __init__(self, custom_weights: dict = None):
        """
        Initialize scorer avec pondérations optionnelles.

        Args:
            custom_weights: Remplace WEIGHTS par défaut (pour tests/tuning)
        """
        self.weights = custom_weights if custom_weights else WEIGHTS
        logger.info(f"QualityScorer initialized with weights: {self.weights}")

    def compute_quality_score(
        self,
        expression: Expression,
        land: Land
    ) -> QualityResult:
        """
        Calcule quality_score complet pour une expression.

        Args:
            expression: Expression ORM object
            land: Land parent ORM object

        Returns:
            QualityResult avec score 0-1, catégorie, flags, raison
        """
        # ... (code complet des sections 3.2 à 3.7)
        pass  # Voir sections précédentes

    # Fonctions internes des 5 blocs
    def _score_access(self, expression: Expression) -> tuple[float, list[str]]:
        """Score bloc Accès (30%)."""
        # Code section 3.2
        pass

    def _score_structure(self, expression: Expression) -> tuple[float, list[str]]:
        """Score bloc Structure (15%)."""
        # Code section 3.3
        pass

    def _score_richness(self, expression: Expression) -> tuple[float, list[str]]:
        """Score bloc Richesse (25%)."""
        # Code section 3.4
        pass

    def _score_coherence(
        self,
        expression: Expression,
        land: Land
    ) -> tuple[float, list[str]]:
        """Score bloc Cohérence (20%)."""
        # Code section 3.5
        pass

    def _score_integrity(self, expression: Expression) -> tuple[float, list[str]]:
        """Score bloc Intégrité (10%)."""
        # Code section 3.6
        pass
```

#### 4.2 Rendre Configurable via Settings

**Fichier** : `MyWebIntelligenceAPI/app/config.py`

```python
class Settings(BaseSettings):
    # ... existing settings ...

    # Quality Scoring
    ENABLE_QUALITY_SCORING: bool = True
    QUALITY_WEIGHT_ACCESS: float = 0.30
    QUALITY_WEIGHT_STRUCTURE: float = 0.15
    QUALITY_WEIGHT_RICHNESS: float = 0.25
    QUALITY_WEIGHT_COHERENCE: float = 0.20
    QUALITY_WEIGHT_INTEGRITY: float = 0.10
```

**Usage dans scorer** :
```python
from app.config import settings

# Dans __init__
self.weights = {
    "access": settings.QUALITY_WEIGHT_ACCESS,
    "structure": settings.QUALITY_WEIGHT_STRUCTURE,
    "richness": settings.QUALITY_WEIGHT_RICHNESS,
    "coherence": settings.QUALITY_WEIGHT_COHERENCE,
    "integrity": settings.QUALITY_WEIGHT_INTEGRITY
}
```

### Tests Étape 4

**Fichier** : `tests/unit/test_quality_scorer.py`

```python
import pytest
from app.services.quality_scorer import QualityScorer, QualityResult
from app.db.models import Expression, Land

@pytest.fixture
def scorer():
    return QualityScorer()

@pytest.fixture
def perfect_expression(db_session):
    """Expression parfaite (score ~1.0)."""
    return Expression(
        http_status=200,
        content_type="text/html",
        title="Great Article Title",
        description="Comprehensive description with sufficient length",
        keywords="machine learning, AI, deep learning",
        canonical_url="https://example.com/article",
        word_count=1500,
        content_length=50000,
        reading_time=6,  # 6 minutes
        lang="fr",
        relevance=4.5,
        published_at=datetime.now(timezone.utc) - timedelta(days=30),
        valid_llm="oui",
        readable="Long readable content...",
        readable_at=datetime.now(timezone.utc),
        approved_at=datetime.now(timezone.utc)
    )

@pytest.fixture
def test_land():
    return Land(lang=["fr", "en"])

def test_perfect_expression_score(scorer, perfect_expression, test_land):
    """Score parfait pour expression optimale."""
    result = scorer.compute_quality_score(perfect_expression, test_land)

    assert result["score"] >= 0.85
    assert result["category"] == "Excellent"
    assert len(result["flags"]) == 0  # Aucun flag de pénalité

def test_http_error_expression(scorer, test_land):
    """Score 0 pour erreur HTTP."""
    expr = Expression(http_status=404, content_type="text/html")
    result = scorer.compute_quality_score(expr, test_land)

    assert result["score"] == 0.0
    assert "http_error" in result["flags"]
    assert result["category"] == "Très faible"

def test_short_content_penalty(scorer, test_land):
    """Pénalité pour contenu court."""
    expr = Expression(
        http_status=200,
        content_type="text/html",
        word_count=50,  # Très court
        content_length=5000,
        lang="fr"
    )
    result = scorer.compute_quality_score(expr, test_land)

    assert result["score"] < 0.5
    assert "short_content" in result["flags"] or "very_short_content" in result["flags"]

def test_wrong_language_penalty(scorer):
    """Pénalité pour langue incorrecte."""
    expr = Expression(
        http_status=200,
        content_type="text/html",
        word_count=1000,
        lang="de"  # Allemand
    )
    land_fr = Land(lang=["fr"])  # Land FR seulement

    result = scorer.compute_quality_score(expr, land_fr)

    assert "wrong_language" in result["flags"]
    assert result["score"] < 0.7  # Pénalité significative

def test_low_relevance_penalty(scorer, test_land):
    """Pénalité pour faible pertinence."""
    expr = Expression(
        http_status=200,
        word_count=1000,
        relevance=0.2,  # Très faible
        lang="fr"
    )
    result = scorer.compute_quality_score(expr, test_land)

    assert "low_relevance" in result["flags"]

def test_pdf_content_blocked(scorer, test_land):
    """PDF doit être bloqué (score 0)."""
    expr = Expression(
        http_status=200,
        content_type="application/pdf"
    )
    result = scorer.compute_quality_score(expr, test_land)

    assert result["score"] == 0.0
    assert "non_html_pdf" in result["flags"]

def test_custom_weights(test_land):
    """Test avec pondérations personnalisées."""
    custom_weights = {
        "access": 0.5,  # Augmenter importance accès
        "structure": 0.1,
        "richness": 0.2,
        "coherence": 0.1,
        "integrity": 0.1
    }
    scorer = QualityScorer(custom_weights=custom_weights)

    expr = Expression(http_status=200, content_type="text/html")
    result = scorer.compute_quality_score(expr, test_land)

    # Access parfait devrait donner score plus élevé
    assert result["score"] >= 0.4

def test_quality_result_structure(scorer, perfect_expression, test_land):
    """Vérifier structure QualityResult."""
    result = scorer.compute_quality_score(perfect_expression, test_land)

    assert "score" in result
    assert "category" in result
    assert "flags" in result
    assert "reason" in result
    assert "details" in result

    assert isinstance(result["score"], float)
    assert isinstance(result["category"], str)
    assert isinstance(result["flags"], list)
    assert isinstance(result["details"], dict)

    # Details contient les 5 blocs
    assert "access" in result["details"]
    assert "structure" in result["details"]
    assert "richness" in result["details"]
    assert "coherence" in result["details"]
    assert "integrity" in result["details"]

def test_truth_table_validation(scorer):
    """Valider contre truth table."""
    with open("tests/data/quality_truth_table.json") as f:
        cases = json.load(f)

    for case in cases[:5]:  # Test premiers cas
        expr = create_expression_from_case(case)
        land = create_land_from_case(case)

        result = scorer.compute_quality_score(expr, land)

        assert case["expected_score_min"] <= result["score"] <= case["expected_score_max"], \
            f"Case {case['case_id']}: score hors limites"
```

**Exécution** :
```bash
pytest tests/unit/test_quality_scorer.py -v --cov=app.services.quality_scorer
```

**Attendu** : 15+ tests, couverture >90%

### Livrables Étape 4
- [ ] Fichier `quality_scorer.py` complet (300+ lignes)
- [ ] Configuration via settings
- [ ] Tests unitaires (15+ tests)
- [ ] Validation truth table passée
- [ ] Documentation docstrings

---

## 🕷️ ÉTAPE 5 – Intégration Pipeline Crawler (Durée: 2-3h)

### Objectif
⚠️ **CRITIQUE** : Intégrer quality dans LES DEUX crawlers (async + sync).

### Actions

#### 5.1 Intégration dans `crawler_engine.py` (ASYNC)

**Fichier** : `MyWebIntelligenceAPI/app/core/crawler_engine.py`

**Localisation** : Après extraction contenu + métadonnées (ligne ~300)

```python
from app.services.quality_scorer import QualityScorer

class AsyncCrawlerEngine:
    def __init__(self, ...):
        # ... existing code ...
        self.quality_scorer = QualityScorer()  # ✅ NOUVEAU

    async def _process_expression(
        self,
        expr_url: str,
        expression: Expression,
        depth: int,
        land: Land,
        # ...
    ):
        # ... existing extraction logic ...

        # After all metadata extracted
        expression.title = extraction_result.get('title')
        expression.word_count = len(readable.split()) if readable else 0
        expression.relevance = await self.calculate_relevance(...)
        # ... other fields ...

        # ✅ NOUVEAU: Compute quality score
        if settings.ENABLE_QUALITY_SCORING:
            try:
                quality_result = self.quality_scorer.compute_quality_score(
                    expression=expression,
                    land=land
                )

                expression.quality_score = quality_result["score"]
                expression.quality_flags = quality_result["flags"]  # Si champ existe
                expression.quality_reason = quality_result["reason"]  # Si champ existe

                logger.debug(
                    f"Quality computed for {expr_url}: "
                    f"{quality_result['score']:.2f} ({quality_result['category']})"
                )
            except Exception as e:
                logger.error(f"Quality scoring failed for {expr_url}: {e}")
                # Continue without quality (non-blocking)

        # ... rest of processing ...
```

#### 5.2 Intégration dans `crawler_engine_sync.py` (SYNC)

**⚠️ DOUBLE CRAWLER - NE PAS OUBLIER !**

**Fichier** : `MyWebIntelligenceAPI/app/core/crawler_engine_sync.py`

**MÊME LOGIQUE** que async :

```python
from app.services.quality_scorer import QualityScorer

class SyncCrawlerEngine:
    def __init__(self, ...):
        # ... existing code ...
        self.quality_scorer = QualityScorer()  # ✅ NOUVEAU

    def _process_expression(
        self,
        expr_url: str,
        expression: Expression,
        depth: int,
        land: Land,
        # ...
    ):
        # ... existing extraction logic ...

        # ✅ NOUVEAU: Compute quality score (IDENTIQUE à async)
        if settings.ENABLE_QUALITY_SCORING:
            try:
                quality_result = self.quality_scorer.compute_quality_score(
                    expression=expression,
                    land=land
                )

                expression.quality_score = quality_result["score"]
                expression.quality_flags = quality_result["flags"]
                expression.quality_reason = quality_result["reason"]

                logger.debug(
                    f"[SYNC] Quality computed for {expr_url}: "
                    f"{quality_result['score']:.2f} ({quality_result['category']})"
                )
            except Exception as e:
                logger.error(f"[SYNC] Quality scoring failed: {e}")

        # ... rest ...
```

#### 5.3 Configuration

**Fichier** : `MyWebIntelligenceAPI/.env`

```bash
# Quality Scoring
ENABLE_QUALITY_SCORING=true

# Pondérations (optionnel, valeurs par défaut OK)
QUALITY_WEIGHT_ACCESS=0.30
QUALITY_WEIGHT_STRUCTURE=0.15
QUALITY_WEIGHT_RICHNESS=0.25
QUALITY_WEIGHT_COHERENCE=0.20
QUALITY_WEIGHT_INTEGRITY=0.10
```

#### 5.4 Vérification Règle Double Crawler

**Checklist OBLIGATOIRE** (voir `ERREUR_DOUBLE_CRAWLER.md`) :

- [ ] ✅ Modifier `crawler_engine.py` (async)
- [ ] ✅ Modifier `crawler_engine_sync.py` (sync)
- [ ] ✅ Vérifier que les deux ont la MÊME logique quality
- [ ] ✅ Tester avec Celery (pas seulement l'API directe)

**Vérification** :
```bash
# Chercher "quality_scorer" dans les DEUX crawlers
grep -n "quality_scorer" MyWebIntelligenceAPI/app/core/crawler_engine.py
grep -n "quality_scorer" MyWebIntelligenceAPI/app/core/crawler_engine_sync.py

# Les deux doivent avoir des lignes similaires !
```

### Tests Étape 5

#### Test d'Intégration Crawler Async

```python
# tests/integration/test_crawler_quality.py

import pytest
from app.core.crawler_engine import AsyncCrawlerEngine
from app.db.models import Expression, Land

@pytest.mark.asyncio
async def test_crawler_computes_quality(db_session, test_land):
    """Vérifier que crawler async calcule quality_score."""

    crawler = AsyncCrawlerEngine(db_session=db_session)

    # Crawl test URL
    test_url = "https://httpbin.org/html"

    await crawler.crawl_url(test_url, land_id=test_land.id, depth=0)

    # Récupérer expression
    expression = db_session.query(Expression)\
        .filter_by(url=test_url)\
        .first()

    assert expression is not None
    assert expression.quality_score is not None
    assert 0.0 <= expression.quality_score <= 1.0

    # Vérifier champs optionnels si présents
    if hasattr(expression, 'quality_flags'):
        assert isinstance(expression.quality_flags, (list, type(None)))

@pytest.mark.asyncio
async def test_quality_score_realistic_range(db_session, test_land):
    """Vérifier que scores sont dans plages réalistes."""

    crawler = AsyncCrawlerEngine(db_session=db_session)

    # Crawl plusieurs URLs
    urls = [
        "https://httpbin.org/html",
        "https://example.com"
    ]

    for url in urls:
        await crawler.crawl_url(url, land_id=test_land.id, depth=0)

    expressions = db_session.query(Expression)\
        .filter_by(land_id=test_land.id)\
        .all()

    scores = [e.quality_score for e in expressions if e.quality_score is not None]

    assert len(scores) > 0
    # Tous les scores entre 0 et 1
    assert all(0.0 <= s <= 1.0 for s in scores)
    # Au moins une variation (pas tous identiques)
    assert len(set(scores)) > 1 or len(scores) == 1
```

#### Test Crawler Sync (Celery)

```bash
# tests/integration/test-crawl-quality.sh

#!/bin/bash
# Test quality scoring integration in sync crawler (Celery)

# ... (authentication, create land)

# Crawl with quality enabled
curl -X POST "http://localhost:8000/api/v2/lands/${LAND_ID}/crawl" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "limit": 5
  }'

# Wait for completion
sleep 30

# Verify quality in DB
docker exec mywebclient-db-1 psql -U mwi_user -d mwi_db -c "
  SELECT
    id,
    url,
    quality_score,
    http_status,
    word_count,
    relevance
  FROM expressions
  WHERE land_id = ${LAND_ID}
  ORDER BY quality_score DESC
  LIMIT 10;
"

# Check distribution
docker exec mywebclient-db-1 psql -U mwi_user -d mwi_db -c "
  SELECT
    CASE
      WHEN quality_score >= 0.8 THEN 'Excellent'
      WHEN quality_score >= 0.6 THEN 'Bon'
      WHEN quality_score >= 0.4 THEN 'Moyen'
      WHEN quality_score >= 0.2 THEN 'Faible'
      ELSE 'Très faible'
    END as category,
    COUNT(*)
  FROM expressions
  WHERE land_id = ${LAND_ID}
  GROUP BY category;
"
```

### Livrables Étape 5
- [ ] `crawler_engine.py` modifié avec quality
- [ ] `crawler_engine_sync.py` modifié (IDENTIQUE)
- [ ] Feature flag dans `.env`
- [ ] Tests intégration (2+ tests)
- [ ] Documentation dans `AGENTS.md` (section quality)

---

## 📡 ÉTAPE 6 – API & Exports (Durée: 1-2h)

### Objectif
Exposer `quality_score` dans les schémas API et exports.

### Actions

#### 6.1 Vérifier Schémas Pydantic

**Fichier** : `MyWebIntelligenceAPI/app/schemas/expression.py`

```python
class ExpressionBase(BaseModel):
    # ... existing fields ...

    # Quality Score (devrait déjà exister si champ en DB)
    quality_score: Optional[float] = Field(
        None,
        description="Quality score from 0.0 (very poor) to 1.0 (excellent)"
    )

    # ✅ NOUVEAU (si champs ajoutés)
    quality_flags: Optional[list[str]] = Field(
        None,
        description="Quality penalty flags (e.g., ['short_content', 'wrong_language'])"
    )
    quality_reason: Optional[str] = Field(
        None,
        description="Human-readable explanation of quality score"
    )

class ExpressionOut(ExpressionBase):
    """Schema for Expression API output."""
    id: int
    url: str
    # ... quality fields inherited from Base

    class Config:
        from_attributes = True
```

#### 6.2 Endpoints avec Filtrage Quality

**Fichier** : `MyWebIntelligenceAPI/app/api/v2/endpoints/lands_v2.py`

```python
@router.get("/{land_id}/expressions", response_model=List[ExpressionOut])
async def get_land_expressions(
    land_id: int,
    min_quality: float = Query(None, ge=0.0, le=1.0, description="Minimum quality score"),
    max_quality: float = Query(None, ge=0.0, le=1.0, description="Maximum quality score"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    # ... other filters ...
):
    """
    Get expressions for a land with optional quality filtering.

    Example:
        GET /api/v2/lands/36/expressions?min_quality=0.7
        → Only high-quality expressions
    """
    query = select(Expression).filter(Expression.land_id == land_id)

    # ✅ NOUVEAU: Filtre quality
    if min_quality is not None:
        query = query.filter(Expression.quality_score >= min_quality)
    if max_quality is not None:
        query = query.filter(Expression.quality_score <= max_quality)

    # ... existing filters ...

    result = await db.execute(query)
    expressions = result.scalars().all()

    return expressions
```

#### 6.3 Stats Quality dans Land

**Ajout endpoint statistiques** :

```python
@router.get("/{land_id}/quality-stats")
async def get_land_quality_stats(
    land_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Get quality score distribution for a land.

    Returns:
        {
            "total_expressions": 1500,
            "with_quality": 1450,
            "avg_quality": 0.67,
            "distribution": {
                "Excellent": 250,
                "Bon": 600,
                "Moyen": 400,
                "Faible": 150,
                "Très faible": 50
            }
        }
    """
    from sqlalchemy import func, case

    # Total et moyenne
    stats_query = select(
        func.count(Expression.id).label("total"),
        func.count(Expression.quality_score).label("with_quality"),
        func.avg(Expression.quality_score).label("avg_quality")
    ).filter(Expression.land_id == land_id)

    stats = await db.execute(stats_query)
    row = stats.first()

    # Distribution par catégorie
    dist_query = select(
        case(
            (Expression.quality_score >= 0.8, "Excellent"),
            (Expression.quality_score >= 0.6, "Bon"),
            (Expression.quality_score >= 0.4, "Moyen"),
            (Expression.quality_score >= 0.2, "Faible"),
            else_="Très faible"
        ).label("category"),
        func.count().label("count")
    ).filter(
        Expression.land_id == land_id,
        Expression.quality_score.isnot(None)
    ).group_by("category")

    dist_result = await db.execute(dist_query)
    distribution = {cat: count for cat, count in dist_result}

    return {
        "total_expressions": row.total,
        "with_quality": row.with_quality,
        "avg_quality": round(row.avg_quality, 3) if row.avg_quality else None,
        "distribution": distribution
    }
```

#### 6.4 Exports CSV/JSON

**Fichier** : `MyWebIntelligenceAPI/app/services/export_service.py`

```python
def export_expressions_csv(self, land_id: int, ...) -> str:
    """
    Export expressions to CSV with quality fields.
    """
    # CSV headers
    headers = [
        'id', 'url', 'title', 'relevance', 'depth',
        'http_status', 'word_count', 'language',
        # ✅ NOUVEAU
        'quality_score', 'quality_category'
    ]

    # ... write CSV ...

    for expr in expressions:
        # Déterminer catégorie
        if expr.quality_score is not None:
            if expr.quality_score >= 0.8:
                quality_cat = "Excellent"
            elif expr.quality_score >= 0.6:
                quality_cat = "Bon"
            elif expr.quality_score >= 0.4:
                quality_cat = "Moyen"
            elif expr.quality_score >= 0.2:
                quality_cat = "Faible"
            else:
                quality_cat = "Très faible"
        else:
            quality_cat = "N/A"

        writer.writerow([
            expr.id,
            expr.url,
            expr.title,
            expr.relevance,
            expr.depth,
            expr.http_status,
            expr.word_count,
            expr.lang,
            expr.quality_score,
            quality_cat
        ])
```

### Tests Étape 6

```python
# tests/api/test_expression_quality_api.py

import pytest
from httpx import AsyncClient

@pytest.mark.asyncio
async def test_get_expression_includes_quality(
    client: AsyncClient,
    test_expression_with_quality
):
    """Vérifier GET /expressions/{id} retourne quality_score."""

    response = await client.get(
        f"/api/v2/expressions/{test_expression_with_quality.id}"
    )

    assert response.status_code == 200
    data = response.json()

    assert "quality_score" in data
    assert isinstance(data["quality_score"], (float, type(None)))

    if data["quality_score"] is not None:
        assert 0.0 <= data["quality_score"] <= 1.0

@pytest.mark.asyncio
async def test_filter_by_quality(client: AsyncClient, test_land):
    """Vérifier filtrage par quality_score."""

    # Créer expressions avec différents scores
    # ... (setup)

    # Filtrer >= 0.7
    response = await client.get(
        f"/api/v2/lands/{test_land.id}/expressions",
        params={"min_quality": 0.7}
    )

    assert response.status_code == 200
    data = response.json()

    # Toutes les expressions retournées doivent avoir score >= 0.7
    for expr in data:
        if expr["quality_score"] is not None:
            assert expr["quality_score"] >= 0.7

@pytest.mark.asyncio
async def test_quality_stats_endpoint(client: AsyncClient, test_land):
    """Vérifier endpoint statistiques quality."""

    response = await client.get(
        f"/api/v2/lands/{test_land.id}/quality-stats"
    )

    assert response.status_code == 200
    data = response.json()

    assert "total_expressions" in data
    assert "avg_quality" in data
    assert "distribution" in data

    # Vérifier cohérence
    total_in_dist = sum(data["distribution"].values())
    assert total_in_dist <= data["total_expressions"]

@pytest.mark.asyncio
async def test_csv_export_includes_quality(client: AsyncClient, test_land):
    """Vérifier export CSV contient quality_score."""

    response = await client.post(
        "/api/v1/export/direct",
        json={
            "land_id": test_land.id,
            "export_type": "pagecsv"
        }
    )

    assert response.status_code == 200
    csv_content = response.text

    # Vérifier header
    assert "quality_score" in csv_content
    assert "quality_category" in csv_content or "quality_cat" in csv_content
```

### Livrables Étape 6
- [ ] Schémas Pydantic vérifiés/mis à jour
- [ ] Endpoint filtrage quality (`min_quality`, `max_quality`)
- [ ] Endpoint stats quality (`/quality-stats`)
- [ ] Export CSV/JSON avec quality
- [ ] Tests API (4+ tests)

---

## 🔄 ÉTAPE 7 – Reprocessing Historique (Durée: 2-3h)

### Objectif
Recalculer quality_score sur expressions existantes (batch).

### Actions

#### 7.1 Script CLI Reprocessing

**Nouveau fichier** : `MyWebIntelligenceAPI/scripts/admin/reprocess_quality.py`

```python
#!/usr/bin/env python3
"""
CLI tool to reprocess quality_score for existing expressions.

Usage:
    python scripts/admin/reprocess_quality.py --land-id 36 --limit 100
    python scripts/admin/reprocess_quality.py --all --dry-run
"""

import argparse
import asyncio
import logging
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.db.session import AsyncSessionLocal
from app.db.models import Expression, Land
from app.services.quality_scorer import QualityScorer

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def reprocess_quality(
    land_id: int = None,
    limit: int = None,
    dry_run: bool = False,
    force: bool = False
):
    """
    Reprocess quality_score for expressions.

    Args:
        land_id: If provided, only process this land
        limit: Max expressions to process
        dry_run: Don't commit changes
        force: Recompute even if quality_score exists
    """
    async with AsyncSessionLocal() as db:
        scorer = QualityScorer()

        # Build query
        query = select(Expression, Land).join(Land)

        if land_id:
            query = query.filter(Expression.land_id == land_id)

        if not force:
            # Only expressions without quality_score
            query = query.filter(Expression.quality_score.is_(None))

        if limit:
            query = query.limit(limit)

        result = await db.execute(query)
        pairs = result.all()

        logger.info(f"Processing {len(pairs)} expressions...")

        stats = {
            "processed": 0,
            "excellent": 0,
            "good": 0,
            "medium": 0,
            "poor": 0,
            "very_poor": 0,
            "errors": 0
        }

        for expr, land in pairs:
            try:
                # Compute quality
                quality_result = scorer.compute_quality_score(expr, land)

                if not dry_run:
                    expr.quality_score = quality_result["score"]
                    if hasattr(expr, 'quality_flags'):
                        expr.quality_flags = quality_result["flags"]
                    if hasattr(expr, 'quality_reason'):
                        expr.quality_reason = quality_result["reason"]

                # Update stats
                stats["processed"] += 1

                if quality_result["score"] >= 0.8:
                    stats["excellent"] += 1
                elif quality_result["score"] >= 0.6:
                    stats["good"] += 1
                elif quality_result["score"] >= 0.4:
                    stats["medium"] += 1
                elif quality_result["score"] >= 0.2:
                    stats["poor"] += 1
                else:
                    stats["very_poor"] += 1

                if stats["processed"] % 100 == 0:
                    logger.info(f"  Processed {stats['processed']}/{len(pairs)}...")

            except Exception as e:
                logger.error(f"Error processing expression {expr.id}: {e}")
                stats["errors"] += 1

        if not dry_run:
            await db.commit()
            logger.info("✅ Changes committed to database")
        else:
            logger.info("🔍 Dry run - no changes committed")

        # Print stats
        logger.info("\n📊 STATISTICS:")
        logger.info(f"  Total processed: {stats['processed']}")
        logger.info(f"  Excellent (>=0.8): {stats['excellent']} ({stats['excellent']/stats['processed']*100:.1f}%)")
        logger.info(f"  Good (0.6-0.8): {stats['good']} ({stats['good']/stats['processed']*100:.1f}%)")
        logger.info(f"  Medium (0.4-0.6): {stats['medium']} ({stats['medium']/stats['processed']*100:.1f}%)")
        logger.info(f"  Poor (0.2-0.4): {stats['poor']} ({stats['poor']/stats['processed']*100:.1f}%)")
        logger.info(f"  Very Poor (<0.2): {stats['very_poor']} ({stats['very_poor']/stats['processed']*100:.1f}%)")
        logger.info(f"  Errors: {stats['errors']}")

        return stats

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--land-id", type=int, help="Land ID to process")
    parser.add_argument("--limit", type=int, help="Max expressions to process")
    parser.add_argument("--dry-run", action="store_true", help="Don't commit changes")
    parser.add_argument("--force", action="store_true", help="Recompute existing scores")
    parser.add_argument("--all", action="store_true", help="Process all lands")

    args = parser.parse_args()

    if not args.land_id and not args.all:
        parser.error("Must specify --land-id or --all")

    asyncio.run(reprocess_quality(
        land_id=args.land_id,
        limit=args.limit,
        dry_run=args.dry_run,
        force=args.force
    ))
```

**Usage** :
```bash
# Dry-run sur land 36 (100 expressions)
python scripts/admin/reprocess_quality.py --land-id 36 --limit 100 --dry-run

# Reprocess pour de vrai
python scripts/admin/reprocess_quality.py --land-id 36 --limit 1000

# Reprocess tout (avec prudence !)
python scripts/admin/reprocess_quality.py --all --force
```

#### 7.2 Task Celery (Optionnel)

**Fichier** : `MyWebIntelligenceAPI/app/tasks/quality_task.py`

```python
"""
Celery tasks for quality score batch processing.
"""

from app.core.celery_app import celery_app

@celery_app.task(bind=True, name="quality.batch_reprocess")
def batch_reprocess_quality(self, land_id: int = None, limit: int = 100):
    """
    Batch reprocess quality for expressions (Celery task).
    """
    import asyncio
    from scripts.admin.reprocess_quality import reprocess_quality

    # Run async function in Celery context
    stats = asyncio.run(reprocess_quality(
        land_id=land_id,
        limit=limit,
        dry_run=False,
        force=False
    ))

    return stats
```

**Endpoint API** :
```python
@router.post("/{land_id}/reprocess-quality")
async def reprocess_land_quality(
    land_id: int,
    limit: int = Query(100, description="Max expressions to reprocess"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Launch quality reprocessing for a land (Celery task).
    """
    from app.tasks.quality_task import batch_reprocess_quality

    # Verify land exists
    land = await db.get(Land, land_id)
    if not land:
        raise HTTPException(404, "Land not found")

    # Launch task
    task = batch_reprocess_quality.delay(
        land_id=land_id,
        limit=limit
    )

    return {
        "task_id": task.id,
        "status": "processing",
        "land_id": land_id,
        "limit": limit
    }
```

### Tests Étape 7

```bash
# Test dry-run
python MyWebIntelligenceAPI/scripts/admin/reprocess_quality.py \
  --land-id 36 --limit 10 --dry-run

# Vérifier stats affichées
# Vérifier aucune modification en DB

# Test reprocess réel (petit échantillon)
python MyWebIntelligenceAPI/scripts/admin/reprocess_quality.py \
  --land-id 36 --limit 50

# Vérifier DB
docker exec mywebclient-db-1 psql -U mwi_user -d mwi_db -c \
  "SELECT COUNT(*), AVG(quality_score)
   FROM expressions
   WHERE land_id = 36 AND quality_score IS NOT NULL;"
```

### Livrables Étape 7
- [ ] Script CLI `reprocess_quality.py`
- [ ] Task Celery (optionnel)
- [ ] Endpoint API `/reprocess-quality` (optionnel)
- [ ] Tests dry-run + reprocess réel
- [ ] Documentation usage dans README

---

## 📊 ÉTAPE 8 – Monitoring & Exploitation (Durée: 2h)

### Objectif
Instrumenter le système, créer dashboards, documenter exploitation.

### Actions

#### 8.1 Métriques Prometheus

**Fichier** : `MyWebIntelligenceAPI/app/services/quality_scorer.py`

```python
from prometheus_client import Histogram, Counter, Gauge

# Métriques quality
quality_score_histogram = Histogram(
    'quality_score_distribution',
    'Distribution of quality scores',
    buckets=[0, 0.2, 0.4, 0.6, 0.8, 1.0]
)

quality_computation_duration = Histogram(
    'quality_computation_duration_seconds',
    'Time to compute quality score'
)

quality_flags_counter = Counter(
    'quality_flags_total',
    'Total quality flags by type',
    ['flag_type']
)

class QualityScorer:
    def compute_quality_score(self, expression, land):
        import time
        start = time.time()

        # ... computation ...

        result = {...}

        # Record metrics
        duration = time.time() - start
        quality_computation_duration.observe(duration)
        quality_score_histogram.observe(result["score"])

        for flag in result["flags"]:
            quality_flags_counter.labels(flag_type=flag).inc()

        return result
```

#### 8.2 Dashboard Grafana (Exemple)

**Panels recommandés** :

1. **Quality Score Distribution**
   ```promql
   histogram_quantile(0.5, quality_score_distribution)
   histogram_quantile(0.9, quality_score_distribution)
   ```

2. **Average Quality by Land**
   ```sql
   SELECT land_id, AVG(quality_score)
   FROM expressions
   GROUP BY land_id
   ```

3. **Top Quality Flags**
   ```promql
   topk(10, rate(quality_flags_total[5m]))
   ```

4. **Quality Computation Latency (p95)**
   ```promql
   histogram_quantile(0.95, quality_computation_duration_seconds)
   ```

#### 8.3 Guide d'Exploitation

**Nouveau fichier** : `MyWebIntelligenceAPI/docs/QUALITY_OPERATIONS.md`

```markdown
# Quality Score - Guide d'Exploitation

## Activation/Désactivation

### Désactiver temporairement
\`\`\`bash
# Dans .env
ENABLE_QUALITY_SCORING=false

# Redémarrer
docker compose restart api celery_worker
\`\`\`

## Monitoring

### Métriques Clés
- `quality_score_distribution` : Distribution des scores (histogramme)
- `quality_flags_total` : Flags de pénalité par type
- `quality_computation_duration` : Latence de calcul

### Requêtes SQL Utiles

\`\`\`sql
-- Distribution quality par land
SELECT
  land_id,
  AVG(quality_score) as avg_quality,
  COUNT(*) as total
FROM expressions
WHERE quality_score IS NOT NULL
GROUP BY land_id
ORDER BY avg_quality DESC;

-- Top 10 meilleurs contenus
SELECT url, quality_score, word_count, relevance
FROM expressions
ORDER BY quality_score DESC
LIMIT 10;

-- Flags les plus fréquents
SELECT unnest(quality_flags) as flag, COUNT(*)
FROM expressions
WHERE quality_flags IS NOT NULL
GROUP BY flag
ORDER BY COUNT(*) DESC;
\`\`\`

## Troubleshooting

### Symptôme : Tous les scores = 0.0
**Cause** : HTTP errors (404, 500) ou contenu non-HTML
**Action** : Vérifier `http_status` et `content_type` dans expressions

### Symptôme : Scores trop faibles (<0.3) pour bon contenu
**Cause** : Pondérations inadaptées
**Action** : Ajuster weights dans `.env` :
\`\`\`bash
QUALITY_WEIGHT_ACCESS=0.20  # Réduire importance HTTP
QUALITY_WEIGHT_RICHNESS=0.35  # Augmenter importance contenu
\`\`\`

### Symptôme : Scores NULL après crawl
**Cause** : Feature flag désactivé ou erreur dans scorer
**Action** :
1. Vérifier `ENABLE_QUALITY_SCORING=true`
2. Consulter logs : `docker logs mywebclient-api-1 | grep quality`
3. Test manuel : `python -c "from app.services.quality_scorer import QualityScorer; ..."`

## Ajustement des Seuils

Si la distribution actuelle ne convient pas :

\`\`\`python
# Analyser distribution actuelle
import pandas as pd
scores = pd.read_sql("SELECT quality_score FROM expressions", con)
print(scores['quality_score'].describe())

# Ajuster WEIGHTS en conséquence
\`\`\`

## Rollback

\`\`\`bash
# 1. Désactiver quality
ENABLE_QUALITY_SCORING=false

# 2. (Optionnel) Réinitialiser scores en DB
docker exec mywebclient-db-1 psql -U mwi_user -d mwi_db -c \
  "UPDATE expressions SET quality_score = NULL;"

# 3. Redémarrer
docker compose restart api celery_worker
\`\`\`
\`\`\`

#### 8.4 Alertes Recommandées

```yaml
# alerts.yml (Prometheus)
groups:
  - name: quality_score
    rules:
      - alert: QualityScoreVeryLow
        expr: avg(quality_score_distribution) < 0.3
        for: 10m
        annotations:
          summary: "Average quality score très faible"
          description: "Score moyen < 0.3 depuis 10min"

      - alert: HighErrorRate
        expr: rate(quality_flags_total{flag_type="http_error"}[5m]) > 0.5
        for: 5m
        annotations:
          summary: "Taux élevé d'erreurs HTTP"
          description: ">50% des pages en erreur HTTP"
```

### Tests Étape 8

```bash
# Smoke test post-déploiement
./MyWebIntelligenceAPI/tests/smoke/test_quality_smoke.sh

# Vérifier métriques Prometheus
curl http://localhost:8000/metrics | grep quality_score

# Vérifier dashboard Grafana
open http://localhost:3001
# → Naviguer vers dashboard "Quality Score"

# Test alertes (optionnel)
# Simuler crawl avec beaucoup d'erreurs HTTP
# Vérifier alerte déclenchée
```

### Livrables Étape 8
- [ ] Métriques Prometheus instrumentées
- [ ] Dashboard Grafana (optionnel)
- [ ] Guide exploitation (`QUALITY_OPERATIONS.md`)
- [ ] Alertes configurées (optionnel)
- [ ] Smoke test post-déploiement

---

## 📝 Documentation Finale

### Fichiers Créés/Mis à Jour

1. **`.claude/docs/quality_dev.md`** (ce fichier) ✅
   - Plan détaillé complet

2. **`MyWebIntelligenceAPI/app/services/quality_scorer.py`** (NOUVEAU)
   - Service de calcul quality_score (300+ lignes)

3. **`MyWebIntelligenceAPI/scripts/admin/reprocess_quality.py`** (NOUVEAU)
   - Script CLI reprocessing (150+ lignes)

4. **`MyWebIntelligenceAPI/tests/unit/test_quality_scorer.py`** (NOUVEAU)
   - Tests unitaires scorer (15+ tests)

5. **`MyWebIntelligenceAPI/tests/integration/test_crawler_quality.py`** (NOUVEAU)
   - Tests intégration crawlers (5+ tests)

6. **`MyWebIntelligenceAPI/tests/data/quality_truth_table.json`** (NOUVEAU)
   - Corpus de validation 20 cas

7. **`MyWebIntelligenceAPI/docs/QUALITY_OPERATIONS.md`** (NOUVEAU)
   - Guide opérationnel

8. **`.claude/AGENTS.md`** (MIS À JOUR)
   - Ajouter section "Quality Scoring"
   - Checklist double crawler

9. **`MyWebIntelligenceAPI/README.md`** (MIS À JOUR)
   - Feature quality_score
   - Variables d'environnement

---

## ✅ Checklist Globale

### Étape 1 - Audit Existant ✅
- [x] Vérifier champ `quality_score` en DB
- [ ] Inventorier métadonnées disponibles
- [ ] Analyser distribution valeurs
- [ ] Tests audit SQL

### Étape 2 - Cadrage Métier
- [ ] Définir objectifs (filtrage, priorisation, etc.)
- [ ] Valider échelle (0-1) et seuils (5 catégories)
- [ ] Créer truth table (20 cas)
- [ ] Validation PO/data analyst

### Étape 3 - Conception Score
- [ ] Modèle 5 blocs avec pondérations
- [ ] Fonctions score_access, score_structure, etc.
- [ ] Structure QualityResult
- [ ] Notebook prototypage validé

### Étape 4 - Service
- [ ] Créer `QualityScorer` classe
- [ ] Configuration via settings
- [ ] Tests unitaires (15+ tests)
- [ ] Couverture >90%

### Étape 5 - Intégration Crawlers ⚠️ CRITIQUE
- [ ] Modifier `crawler_engine.py` (async)
- [ ] Modifier `crawler_engine_sync.py` (sync)
- [ ] Vérifier PARITÉ
- [ ] Tests intégration (async + sync)

### Étape 6 - API
- [ ] Schémas Pydantic vérifiés
- [ ] Endpoint filtrage (`min_quality`)
- [ ] Endpoint stats (`/quality-stats`)
- [ ] Export CSV/JSON
- [ ] Tests API (4+ tests)

### Étape 7 - Reprocessing
- [ ] Script CLI `reprocess_quality.py`
- [ ] Task Celery (optionnel)
- [ ] Tests dry-run + réel
- [ ] Documentation usage

### Étape 8 - Monitoring
- [ ] Métriques Prometheus
- [ ] Dashboard Grafana (optionnel)
- [ ] Guide exploitation
- [ ] Alertes (optionnel)
- [ ] Smoke test

---

## 🚀 Prochaines Actions Immédiates

### Pour Démarrer (Aujourd'hui)
1. Valider plan avec équipe/PO
2. Confirmer pondérations métier (WEIGHTS)
3. Créer truth table (20 cas) avec data analyst
4. Analyser distribution métadonnées actuelles (SQL)

### Sprint 1 (Semaine 1)
- Étapes 1-3 : Audit + cadrage + conception
- Prototype notebook

### Sprint 2 (Semaine 2)
- Étapes 4-5 : Service + intégration crawlers
- Tests unitaires + intégration

### Sprint 3 (Semaine 3)
- Étapes 6-7 : API + reprocessing
- Tests end-to-end

### Sprint 4 (Semaine 4)
- Étape 8 : Monitoring + déploiement
- Validation métier

---

## 📞 Support & Questions

### Points de Blocage Potentiels

1. **Pondérations inadaptées**
   - Solution : Itérer avec PO sur truth table, ajuster WEIGHTS

2. **Distribution biaisée (tous hauts ou bas)**
   - Solution : Recalibrer seuils, vérifier données d'entrée

3. **Champs manquants (word_count, etc.)**
   - Solution : Vérifier extraction contenu, ajouter fallbacks

4. **Double crawler oublié**
   - Solution : Checklist stricte, revue code obligatoire

### Contacts
- Architecture : Voir `AGENTS.md`, `Architecture.md`
- Métier : Valider pondérations avec PO/data analyst
- Bugs crawlers : Voir `ERREUR_DOUBLE_CRAWLER.md`

---

## 📊 Comparaison Sentiment vs Quality

| Aspect | Sentiment Score | Quality Score |
|--------|----------------|---------------|
| **Méthode** | ML (TextBlob) ou LLM | Heuristique pure |
| **Dépendances** | `textblob` (15 MB) | Aucune (0 MB) ✅ |
| **Latence** | 50ms (TextBlob) | <10ms ✅ |
| **Coût** | Gratuit (TextBlob) | Gratuit ✅ |
| **Reproductibilité** | Stochastique (LLM) | 100% déterministe ✅ |
| **Complexité** | Modérée | Faible ✅ |
| **Validation** | Corpus annoté humain | Truth table métier |
| **Tuning** | Difficile (modèle figé) | Facile (ajuster weights) ✅ |

**Conclusion** : Quality score est **plus simple, plus rapide, et plus flexible** que sentiment !

---

**Dernière mise à jour** : 18 octobre 2025
**Version** : 1.0
**Auteur** : Assistant AI (Claude)
**Statut** : Plan détaillé prêt pour implémentation
