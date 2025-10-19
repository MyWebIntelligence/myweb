# Plan de Développement Sentiment Score - MyWebIntelligence API

**Date de création**: 18 octobre 2025
**Version**: 1.1
**Statut**: Plan détaillé pour implémentation

---

## 🎯 Objectif

Implémenter un système complet de détection et d'analyse du sentiment des expressions crawlées dans l'API MyWebIntelligence, en respectant l'architecture du double crawler (sync/async) et les principes de parité legacy.

---

## ⚡ Décisions Clés (TL;DR)

### 1. Approche Technique : **Hybride TextBlob + OpenRouter**
- **Par défaut** : TextBlob (10 MB, 50ms, gratuit, FR/EN)
- **Haute qualité** : OpenRouter LLM (déjà intégré, $0.003/analyse)
- **Sélection** : Via flag `llm_validation` existant (pas de nouveau paramètre !)

### 2. Installation Minimale
```bash
pip install textblob textblob-fr  # +15 MB total
python -m textblob.download_corpora
# OpenRouter déjà disponible, rien à installer !
```

### 3. Intégration Simple
- **1 nouveau champ** en DB : `sentiment_model` (pour tracer TextBlob vs LLM)
- **Réutilise flag existant** : `llm_validation` contrôle aussi le sentiment
- **Double crawler** : Même logique dans async + sync (comme toujours)

### 4. Usage API
```bash
# Standard (TextBlob - gratuit)
POST /api/v2/lands/36/crawl {"llm_validation": false}

# Premium (LLM - haute qualité)
POST /api/v2/lands/36/crawl {"llm_validation": true}
```

### 5. Coût Estimé
- TextBlob : 0€
- OpenRouter (si 10% en LLM) : ~15€/mois pour 5000 analyses
- **Total** : <20€/mois

---

---

## 📊 État des Lieux

### ✅ Existant
- **Champ `sentiment_score`** : Présent dans le modèle `Expression` (ligne 233, `models.py`)
  ```python
  sentiment_score = Column(Float, nullable=True)  # Analyse de sentiment
  ```
- **Valeur actuelle** : Toujours `null` dans toutes les expressions existantes
- **Type** : `Float` (accepte valeurs négatives et positives)

### ❌ Manquant
- Service d'analyse de sentiment
- Intégration dans les crawlers (sync + async)
- Bibliothèque d'analyse (TextBlob à installer)
- **1 nouveau champ** : `sentiment_model` (pour tracer TextBlob vs LLM)
- Tests unitaires et d'intégration
- Documentation API

### 📋 Nouveaux Champs Nécessaires

Ajouter à la table `expressions` :

```python
# Dans models.py (à ajouter après sentiment_score ligne 233)
sentiment_label = Column(String(20), nullable=True)        # "positive", "neutral", "negative"
sentiment_confidence = Column(Float, nullable=True)         # 0.0 à 1.0
sentiment_status = Column(String(30), nullable=True)        # "computed", "failed", "unsupported_lang", etc.
sentiment_model = Column(String(100), nullable=True)        # "textblob" ou "llm/claude-3.5-sonnet"
sentiment_computed_at = Column(DateTime, nullable=True)     # Timestamp du calcul
```

**Migration requise** : Alembic pour ajouter les 5 nouveaux champs.

---

## 🏗️ Architecture Cible

### Composants Principaux

```
┌─────────────────────────────────────────────────────────────┐
│                    SENTIMENT PIPELINE                        │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  1. SentimentModelProvider (core/)                          │
│     └─ Chargement lazy des modèles multilingues            │
│                                                              │
│  2. SentimentService (services/)                            │
│     ├─ Détection langue (réutilise module existant)        │
│     ├─ Appel modèle approprié                              │
│     ├─ Calibration score                                    │
│     └─ Gestion fallbacks                                    │
│                                                              │
│  3. Intégration Crawlers                                    │
│     ├─ crawler_engine.py (async)                           │
│     └─ crawler_engine_sync.py (sync) ⚠️ DOUBLE CRAWLER     │
│                                                              │
│  4. API Endpoints                                           │
│     ├─ GET /expressions/{id} (avec sentiment)              │
│     └─ POST /lands/{id}/reprocess-sentiment (batch)        │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

---

## 📋 Plan de Développement Détaillé

---

## 🔍 ÉTAPE 1 – Cartographie Existant (Durée: 1-2h)

### Objectif
Auditer l'infrastructure existante pour identifier les points d'intégration et les dépendances disponibles.

### Actions

#### 1.1 Audit Modèle de Données
- [x] **Vérifier champ `sentiment_score` dans `Expression`**
  - Fichier: `MyWebIntelligenceAPI/app/db/models.py:233`
  - Type: `Float`
  - Nullable: `True`
  - Index: Non (à considérer si requêtes fréquentes)

- [ ] **Vérifier schémas Pydantic**
  - Fichier: `MyWebIntelligenceAPI/app/schemas/expression.py`
  - Action: S'assurer que `ExpressionOut` expose `sentiment_score`
  - Vérifier également `ExpressionCreate`, `ExpressionUpdate`

- [ ] **Évaluer besoin de nouveaux champs**
  ```python
  # Proposition d'ajout dans models.py
  sentiment_label = Column(String(20), nullable=True)      # "positive", "neutral", "negative"
  sentiment_confidence = Column(Float, nullable=True)       # 0.0 à 1.0
  sentiment_status = Column(String(20), nullable=True)      # "computed", "failed", "unsupported_lang"
  sentiment_model = Column(String(100), nullable=True)      # Modèle utilisé
  sentiment_computed_at = Column(DateTime, nullable=True)   # Timestamp
  ```

#### 1.2 Tracer Flux d'Enrichissement
- [ ] **Identifier points d'injection dans crawlers**
  - `crawler_engine.py` (async): Ligne ~250-300 (après extraction contenu)
  - `crawler_engine_sync.py` (sync): Ligne ~200-250 (après extraction contenu)
  - ⚠️ **CRITIQUE**: Modifier LES DEUX crawlers (voir `ERREUR_DOUBLE_CRAWLER.md`)

- [ ] **Examiner pipeline readable**
  - Services: `readable_service.py`, `readable_celery_service.py`
  - Opportunité: Ajouter sentiment lors du traitement readable
  - Fichiers: `MyWebIntelligenceAPI/app/services/readable_*.py`

- [ ] **Identifier workers Celery**
  - Tasks: `MyWebIntelligenceAPI/app/tasks/`
  - Vérifier si sentiment peut être calculé de manière asynchrone
  - Considérer task dédiée `sentiment_task.py`

#### 1.3 Inventaire Dépendances & Contraintes
- [ ] **Vérifier dépendances Python disponibles**
  ```bash
  # Vérifier requirements.txt
  grep -E "(transformers|torch|tensorflow|scikit-learn)" MyWebIntelligenceAPI/requirements.txt
  ```

- [ ] **Évaluer contraintes infrastructure**
  - CPU/RAM disponible dans containers Docker
  - Temps de réponse acceptable (< 2s par expression idéalement)
  - Espace disque pour modèles (~500MB par modèle)

- [ ] **Tester détection de langue existante**
  ```python
  # Dans text_processing.py ou utils
  from app.core.text_processing import detect_language
  # Vérifier si déjà implémenté et performant
  ```

### Tests Étape 1
```bash
# 1. Rechercher "sentiment" dans toute la codebase
rg "sentiment" MyWebIntelligenceAPI/ --type py

# 2. Vérifier modèle Expression
grep -A 5 "sentiment_score" MyWebIntelligenceAPI/app/db/models.py

# 3. Inspecter fixtures de test
docker exec mywebclient-db-1 psql -U mwi_user -d mwi_db -c \
  "SELECT id, url, sentiment_score FROM expressions LIMIT 5;"
```

### Livrables Étape 1
- [x] Liste des fichiers à modifier avec numéros de lignes précis
- [ ] Document des dépendances disponibles/manquantes
- [ ] Schéma du flux d'injection sentiment (diagramme)
- [ ] Rapport de contraintes (CPU, RAM, latence)

---

## 📚 ÉTAPE 2 – Jeu de Validation & Exigences Métier (Durée: 2-3h)

### Objectif
Constituer un corpus annoté pour validation et définir les critères de qualité.

### Actions

#### 2.1 Constituer Corpus Annoté
- [ ] **Sélectionner 50-60 expressions réelles**
  ```sql
  -- Échantillon équilibré FR/EN avec contenu varié
  SELECT id, url, title, readable, lang
  FROM expressions
  WHERE readable IS NOT NULL
    AND lang IN ('fr', 'en')
    AND word_count > 100
  ORDER BY RANDOM()
  LIMIT 30; -- 30 FR

  SELECT id, url, title, readable, lang
  FROM expressions
  WHERE readable IS NOT NULL
    AND lang = 'en'
    AND word_count > 100
  ORDER BY RANDOM()
  LIMIT 30; -- 30 EN
  ```

- [ ] **Annoter manuellement chaque texte**
  - Label: `positive`, `neutral`, `negative`
  - Score cible: `-1.0` (très négatif) à `+1.0` (très positif)
  - Confiance: Niveau de certitude de l'annotation (high/medium/low)
  - Format: CSV ou JSON
  ```json
  {
    "expression_id": 12345,
    "url": "https://example.com/article",
    "text_snippet": "Premières 200 chars...",
    "manual_label": "positive",
    "manual_score": 0.75,
    "annotator_confidence": "high",
    "language": "fr",
    "notes": "Commentaires optionnels"
  }
  ```

- [ ] **Sauvegarder corpus dans Git**
  - Emplacement: `MyWebIntelligenceAPI/tests/data/sentiment_corpus.json`
  - Version control pour traçabilité

#### 2.2 Définir Exigences Métier
- [ ] **Format de sortie**
  ```python
  # Dans Expression model
  sentiment_score: float      # -1.0 à +1.0 (ou 0-1 selon modèle)
  sentiment_label: str        # "positive", "neutral", "negative"
  sentiment_confidence: float # 0.0 à 1.0 (probabilité du modèle)
  sentiment_status: str       # "computed", "failed", "unsupported_lang", "no_content"
  ```

- [ ] **Seuils de décision**
  - **Positif**: score > 0.6 (configurable)
  - **Neutre**: score entre -0.6 et 0.6
  - **Négatif**: score < -0.6
  - **Confiance minimale**: 0.5 (sinon status = "low_confidence")

- [ ] **Seuils d'alertes (optionnel)**
  - Expressions très négatives (score < -0.8) → flag pour review
  - Expressions polarisées (|score| > 0.9) → potentiel contenu sensible

- [ ] **Tolérance latence**
  - **Crawl en temps réel**: < 500ms par expression (objectif stretch)
  - **Crawl batch/async**: < 2s par expression (acceptable)
  - **Reprocessing historique**: Pas de limite (job Celery)

#### 2.3 Cas Limites à Gérer
- [ ] **Langue non supportée** (ex: allemand, espagnol)
  - Comportement: `sentiment_score = null`, `sentiment_status = "unsupported_lang"`

- [ ] **Contenu vide ou trop court**
  - Comportement: `sentiment_score = null`, `sentiment_status = "no_content"`
  - Seuil: < 50 caractères de contenu lisible

- [ ] **Texte mixte multilingue**
  - Comportement: Utiliser langue dominante détectée
  - Fallback: Si langue dominante non FR/EN → unsupported

- [ ] **Erreur modèle**
  - Comportement: `sentiment_score = null`, `sentiment_status = "failed"`
  - Logging détaillé pour investigation

### Tests Étape 2
```bash
# Reviewer annotations manuelles
python MyWebIntelligenceAPI/tests/scripts/validate_corpus.py

# Vérifier distribution des labels
jq '.[] | .manual_label' tests/data/sentiment_corpus.json | sort | uniq -c

# Statistiques du corpus
jq '[.[] | .manual_score] | add/length' tests/data/sentiment_corpus.json
```

### Livrables Étape 2
- [ ] Corpus annoté (`sentiment_corpus.json`) avec 50-60 exemples
- [ ] Document spécifications sentiment (format, seuils, alertes)
- [ ] Checklist des cas limites et comportements attendus

---

## 🤖 ÉTAPE 3 – Choix et Encapsulation du Modèle (Durée: 3-4h)

### Objectif
Sélectionner et intégrer un modèle de sentiment multilingue optimisé.

### Actions

#### 3.1 Sélection du Modèle

##### Option A: TextBlob (RECOMMANDÉ - Ultra Léger) ⭐
**Bibliothèque**: `textblob` (dictionnaire + règles)
- ✅ **Avantages**:
  - **Ultra léger**: 10 MB total (vs 1.25 GB pour transformers)
  - **Très rapide**: <50ms par analyse
  - **RAM minimale**: ~50 MB (vs 1-2 GB pour torch)
  - Simple à intégrer
  - Support FR avec extension `textblob-fr`
- ❌ **Inconvénients**:
  - Précision modérée (basé sur dictionnaires)
  - Moins bon que deep learning sur textes complexes
- **Installation**:
  ```bash
  pip install textblob textblob-fr
  python -m textblob.download_corpora  # Une fois
  ```
- **Cas d'usage idéal**:
  - Textes courts/moyens
  - Besoin de performance
  - Contraintes RAM/disque

##### Option B: VADER (Textes Courts/Informels)
**Bibliothèque**: `vaderSentiment` (règles + lexique)
- ✅ **Avantages**:
  - **Minuscule**: 2 MB total
  - **Extrêmement rapide**: <10ms
  - Excellent pour réseaux sociaux (émojis, slang)
  - Gère ponctuation et casse
- ❌ **Inconvénients**:
  - **Anglais uniquement** (dealbreaker pour FR)
  - Moins bon sur textes formels/longs
- **Installation**:
  ```bash
  pip install vaderSentiment
  ```
- **Cas d'usage idéal**:
  - Contenu EN uniquement
  - Tweets, commentaires courts

##### Option C: API OpenRouter (Déjà Intégré!) 🎯
**Service**: Réutiliser `llm_validation_service.py` existant
- ✅ **Avantages**:
  - **Zéro dépendance supplémentaire** (déjà dans le projet)
  - **Très haute qualité** (Claude 3.5 Sonnet)
  - **Multilingue parfait** (FR/EN/ES/...)
  - Déjà configuré et testé
- ❌ **Inconvénients**:
  - **Coût**: ~$0.003 par analyse (15€ pour 5000 expressions)
  - **Latence**: 500ms-2s (réseau)
  - Requiert `OPENROUTER_ENABLED=true` et budget API
- **Installation**:
  ```bash
  # AUCUNE ! Déjà disponible
  ```
- **Cas d'usage idéal**:
  - Haute qualité requise
  - Volume modéré (<10k expressions/mois)
  - Budget API disponible

##### Option D: Transformers (Haute Précision) ⚠️ LOURD
**Modèle**: `cardiffnlp/twitter-xlm-roberta-base-sentiment-multilingual`
- ✅ **Avantages**:
  - Très haute précision (deep learning)
  - Support FR + EN + 6 autres langues
  - État de l'art pour sentiment
- ❌ **Inconvénients**:
  - **Très lourd**: ~1.25 GB (torch + transformers)
  - **RAM élevée**: 1-2 GB par worker
  - **Temps de chargement**: 30-60s au démarrage
  - Latence modérée (200-500ms)
- **Installation**:
  ```bash
  pip install transformers torch sentencepiece
  ```
- **Cas d'usage idéal**:
  - Infrastructure robuste (GPU, RAM abondante)
  - Précision maximale requise
  - Volume très élevé justifiant l'investissement

---

### 🎯 **DÉCISION RECOMMANDÉE: Approche Hybride**

**Stratégie Intelligente** (meilleur compromis):

1. **Par Défaut**: TextBlob (Option A) - Léger, rapide, gratuit
   - Utilisé quand `llm_validation: false` (défaut)
   - Stocke `sentiment_model: "textblob"`

2. **Haute Qualité**: OpenRouter (Option C) - Précision maximale
   - **Réutilise le flag existant** `llm_validation: true` du crawl
   - Utilisé pour contenus critiques ou validation
   - Stocke `sentiment_model: "llm/claude-3.5-sonnet"`

**Avantages Hybride**:
- ✅ Démarrage immédiat avec TextBlob (léger)
- ✅ **Pas de nouveau paramètre** - réutilise `llm_validation` existant
- ✅ Cohérence : même flag pour validation pertinence + sentiment
- ✅ Coût maîtrisé (LLM seulement si nécessaire)
- ✅ Flexibilité max

**Code de sélection** (réutilise flag existant):
```python
# Dans crawler_engine.py et crawler_engine_sync.py
if llm_validation and settings.OPENROUTER_ENABLED:
    # Haute qualité (payant) - validation + sentiment LLM
    result = await analyze_sentiment_llm(text, language)
else:
    # Standard (gratuit, rapide) - TextBlob
    result = analyze_sentiment_textblob(text, language)
```

**Exemple d'utilisation API**:
```bash
# Crawl standard avec TextBlob
curl -X POST "/api/v2/lands/36/crawl" \
  -d '{"limit": 10, "llm_validation": false}'
# → sentiment via TextBlob (gratuit, rapide)

# Crawl haute qualité avec LLM
curl -X POST "/api/v2/lands/36/crawl" \
  -d '{"limit": 10, "llm_validation": true}'
# → validation pertinence + sentiment via Claude (payant, précis)
```

#### 3.2 Implémenter `SentimentModelProvider` (Approche Hybride)

**Nouveau fichier**: `MyWebIntelligenceAPI/app/core/sentiment_provider.py`

```python
"""
Sentiment Analysis Provider for MyWebIntelligence API

Hybrid approach:
- TextBlob (default): Lightweight, fast, free
- OpenRouter (optional): High quality, LLM-based

Supports FR/EN with automatic fallback.
"""

import logging
from typing import Optional, Dict, Any, Literal

from app.config import settings

logger = logging.getLogger(__name__)

SentimentLabel = Literal["positive", "neutral", "negative"]

class SentimentModelProvider:
    """
    Hybrid sentiment analysis provider.

    Methods:
    - TextBlob: Fast, lightweight (default)
    - OpenRouter: High quality (optional, requires API key)
    """

    # Configuration
    SUPPORTED_LANGUAGES = ["fr", "en"]  # TextBlob supports these well
    TEXTBLOB_AVAILABLE = False
    OPENROUTER_AVAILABLE = False

    def __init__(self):
        """Initialize provider and check available methods."""
        # Check TextBlob availability
        try:
            from textblob import TextBlob
            self.TEXTBLOB_AVAILABLE = True
            logger.info("✅ TextBlob sentiment provider available")
        except ImportError:
            logger.warning("❌ TextBlob not installed (pip install textblob textblob-fr)")

        # Check OpenRouter availability
        if settings.OPENROUTER_ENABLED and settings.OPENROUTER_API_KEY:
            self.OPENROUTER_AVAILABLE = True
            logger.info("✅ OpenRouter sentiment provider available")

        if not self.TEXTBLOB_AVAILABLE and not self.OPENROUTER_AVAILABLE:
            logger.error("❌ No sentiment provider available!")

    def is_language_supported(self, lang: str) -> bool:
        """Check if language is supported."""
        return lang.lower() in self.SUPPORTED_LANGUAGES

    def _analyze_textblob(self, text: str, language: str) -> Dict[str, Any]:
        """
        Analyze sentiment using TextBlob.

        Fast, lightweight, rule-based approach.
        """
        try:
            from textblob import TextBlob

            # Use French-specific TextBlob if needed
            if language == "fr":
                try:
                    from textblob_fr import PatternTagger, PatternAnalyzer
                    blob = TextBlob(text, pos_tagger=PatternTagger(), analyzer=PatternAnalyzer())
                except ImportError:
                    logger.warning("textblob-fr not available, using English analyzer")
                    blob = TextBlob(text)
            else:
                blob = TextBlob(text)

            # Get polarity (-1.0 to +1.0)
            polarity = blob.sentiment.polarity

            # Determine label with thresholds
            if polarity > 0.1:
                label = "positive"
            elif polarity < -0.1:
                label = "negative"
            else:
                label = "neutral"

            return {
                "score": round(polarity, 3),
                "label": label,
                "confidence": round(abs(polarity), 3),  # Use absolute polarity as confidence
                "status": "computed",
                "model": "textblob"
            }

        except Exception as e:
            logger.error(f"TextBlob analysis failed: {e}")
            return {
                "score": None,
                "label": None,
                "confidence": None,
                "status": "failed",
                "model": None
            }

    async def _analyze_openrouter(self, text: str, language: str) -> Dict[str, Any]:
        """
        Analyze sentiment using OpenRouter LLM.

        High quality, but slower and costs money.
        """
        try:
            from app.services.llm_validation_service import LLMValidationService
            import json

            # Prepare prompt
            prompt = f"""Analyze the sentiment of the following text in {language.upper()}.

Text: {text[:1000]}

Respond with ONLY a valid JSON object (no markdown, no extra text):
{{"sentiment": "positive" or "neutral" or "negative", "score": -1.0 to 1.0, "confidence": 0.0 to 1.0}}

Example response:
{{"sentiment": "positive", "score": 0.75, "confidence": 0.9}}"""

            # Call LLM service
            llm_service = LLMValidationService()
            response_text = await llm_service._call_openrouter(
                prompt=prompt,
                temperature=0.0  # Deterministic for sentiment
            )

            # Parse JSON response
            # Remove markdown code blocks if present
            response_clean = response_text.strip()
            if response_clean.startswith("```"):
                # Extract JSON from markdown
                lines = response_clean.split("\n")
                response_clean = "\n".join(lines[1:-1])

            result = json.loads(response_clean)

            return {
                "score": round(float(result["score"]), 3),
                "label": result["sentiment"],
                "confidence": round(float(result["confidence"]), 3),
                "status": "computed",
                "model": f"llm/{settings.OPENROUTER_MODEL}"
            }

        except Exception as e:
            logger.error(f"OpenRouter analysis failed: {e}", exc_info=True)
            return {
                "score": None,
                "label": None,
                "confidence": None,
                "status": "failed",
                "model": None
            }

    async def analyze_sentiment(
        self,
        text: str,
        language: str = "en",
        use_llm: bool = False
    ) -> Dict[str, Any]:
        """
        Analyze sentiment of text.

        Args:
            text: Text to analyze (cleaned, readable content preferred)
            language: ISO 639-1 language code

        Returns:
            Dict with:
                - score: float (-1.0 to +1.0)
                - label: str ("positive", "neutral", "negative")
                - confidence: float (0.0 to 1.0)
                - status: str ("computed", "unsupported_lang", "no_content", "failed")
                - model: str (model name used)

        Example:
            >>> provider = SentimentModelProvider()
            >>> result = provider.analyze_sentiment("This is great!", "en")
            >>> print(result)
            {
                'score': 0.95,
                'label': 'positive',
                'confidence': 0.95,
                'status': 'computed',
                'model': 'cardiffnlp/twitter-xlm-roberta...'
            }
        """
        # Validation
        if not text or len(text.strip()) < 10:
            return {
                "score": None,
                "label": None,
                "confidence": None,
                "status": "no_content",
                "model": None
            }

        if not self.is_language_supported(language):
            logger.warning(f"Unsupported language: {language}")
            return {
                "score": None,
                "label": None,
                "confidence": None,
                "status": "unsupported_lang",
                "model": None
            }

        try:
            # Load model (cached)
            model = self._load_model()

            # Truncate very long texts (keep first 512 tokens worth ~2000 chars)
            text_truncated = text[:2000] if len(text) > 2000 else text

            # Analyze
            result = model(text_truncated)[0]

            # Extract and normalize
            raw_label = result["label"]
            confidence = result["score"]

            normalized_label = self._normalize_label(raw_label)
            sentiment_score = self._score_to_range(normalized_label, confidence)

            logger.debug(
                f"Sentiment analyzed: {normalized_label} "
                f"(score={sentiment_score:.2f}, conf={confidence:.2f})"
            )

            return {
                "score": round(sentiment_score, 3),
                "label": normalized_label,
                "confidence": round(confidence, 3),
                "status": "computed",
                "model": self.DEFAULT_MODEL
            }

        except Exception as e:
            logger.error(f"Sentiment analysis failed: {e}", exc_info=True)
            return {
                "score": None,
                "label": None,
                "confidence": None,
                "status": "failed",
                "model": None
            }
```

#### 3.3 Intégration Pipeline de Normalisation

**Modifier**: `MyWebIntelligenceAPI/app/utils/text_utils.py`

```python
def prepare_text_for_sentiment(content: str, max_length: int = 2000) -> str:
    """
    Prepare text for sentiment analysis.

    - Strip HTML tags (if any remain)
    - Remove excessive whitespace
    - Truncate to max_length
    - Preserve paragraph structure

    Args:
        content: Raw or readable content
        max_length: Maximum characters to keep

    Returns:
        Cleaned text ready for sentiment analysis
    """
    import re
    from bs4 import BeautifulSoup

    # Remove HTML tags if present
    soup = BeautifulSoup(content, 'html.parser')
    text = soup.get_text(separator=' ', strip=True)

    # Normalize whitespace
    text = re.sub(r'\s+', ' ', text).strip()

    # Truncate intelligently (try to break at sentence)
    if len(text) > max_length:
        text = text[:max_length]
        last_period = text.rfind('.')
        if last_period > max_length * 0.8:  # If period found in last 20%
            text = text[:last_period + 1]

    return text
```

### Tests Étape 3
```python
# MyWebIntelligenceAPI/tests/unit/test_sentiment_provider.py

import pytest
from app.core.sentiment_provider import SentimentModelProvider

@pytest.fixture
def provider():
    return SentimentModelProvider()

def test_positive_sentiment_en(provider):
    result = provider.analyze_sentiment(
        "This movie is absolutely fantastic! I loved every moment.",
        language="en"
    )
    assert result["status"] == "computed"
    assert result["label"] == "positive"
    assert result["score"] > 0.5
    assert result["confidence"] > 0.7

def test_negative_sentiment_fr(provider):
    result = provider.analyze_sentiment(
        "Ce film est vraiment nul. Une perte de temps totale.",
        language="fr"
    )
    assert result["status"] == "computed"
    assert result["label"] == "negative"
    assert result["score"] < -0.5

def test_neutral_sentiment(provider):
    result = provider.analyze_sentiment(
        "The weather today is cloudy with some sun.",
        language="en"
    )
    assert result["status"] == "computed"
    # Note: neutral detection is harder, accept any label
    assert result["label"] in ["positive", "neutral", "negative"]

def test_unsupported_language(provider):
    result = provider.analyze_sentiment(
        "日本語のテキスト",
        language="ja"
    )
    assert result["status"] == "unsupported_lang"
    assert result["score"] is None

def test_empty_content(provider):
    result = provider.analyze_sentiment("", language="en")
    assert result["status"] == "no_content"
    assert result["score"] is None

def test_very_short_content(provider):
    result = provider.analyze_sentiment("OK", language="en")
    assert result["status"] == "no_content"

def test_model_caching(provider):
    """Verify model is loaded once and cached."""
    result1 = provider.analyze_sentiment("Test 1", "en")
    result2 = provider.analyze_sentiment("Test 2", "en")

    # Both should succeed
    assert result1["status"] == "computed"
    assert result2["status"] == "computed"

    # Check cache
    assert len(provider._models) == 1

def test_label_normalization(provider):
    """Test internal label mapping."""
    assert provider._normalize_label("LABEL_2") == "positive"
    assert provider._normalize_label("LABEL_0") == "negative"
    assert provider._normalize_label("Positive") == "positive"

def test_score_conversion(provider):
    """Test score range conversion."""
    assert provider._score_to_range("positive", 0.9) == 0.9
    assert provider._score_to_range("negative", 0.8) == -0.8
    assert provider._score_to_range("neutral", 0.5) == 0.0

# Performance test
def test_latency_budget(provider):
    """Ensure sentiment analysis completes in < 2s."""
    import time
    text = "This is a test text for performance measurement. " * 20

    start = time.time()
    result = provider.analyze_sentiment(text, "en")
    duration = time.time() - start

    assert result["status"] == "computed"
    assert duration < 2.0  # Budget: 2 seconds max
```

**Exécution**:
```bash
cd MyWebIntelligenceAPI
pytest tests/unit/test_sentiment_provider.py -v
```

### Livrables Étape 3
- [ ] Fichier `sentiment_provider.py` avec classe complète
- [ ] Tests unitaires (`test_sentiment_provider.py`) avec 10+ cas
- [ ] Documentation docstrings (Google style)
- [ ] Mesure de latence sur échantillon (moyenne < 500ms)

---

## 🔧 ÉTAPE 4 – Service d'Enrichissement (Durée: 2-3h)

### Objectif
Créer un service orchestrant détection de langue + analyse sentiment + calibration.

### Actions

#### 4.1 Créer `SentimentService`

**Nouveau fichier**: `MyWebIntelligenceAPI/app/services/sentiment_service.py`

```python
"""
Sentiment Enrichment Service for MyWebIntelligence API

Orchestrates language detection + sentiment analysis for expressions.
Integrates with existing text_processing module.
"""

import logging
from typing import Optional, Dict, Any

from app.core.sentiment_provider import SentimentModelProvider
from app.core.text_processing import detect_language  # Assuming exists
from app.utils.text_utils import prepare_text_for_sentiment

logger = logging.getLogger(__name__)

class SentimentService:
    """
    Service for enriching expressions with sentiment scores.

    Workflow:
    1. Detect language (reuse existing module)
    2. Prepare text (clean, truncate)
    3. Call sentiment model
    4. Calibrate score if needed
    5. Return structured result
    """

    def __init__(self):
        """Initialize service with model provider."""
        self.provider = SentimentModelProvider()
        logger.info("SentimentService initialized")

    def enrich_expression_sentiment(
        self,
        content: Optional[str],
        readable: Optional[str] = None,
        language: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Enrich an expression with sentiment analysis.

        Args:
            content: Raw HTML content (fallback)
            readable: Readable markdown content (preferred)
            language: Detected language (ISO 639-1), auto-detect if None

        Returns:
            Dict ready for Expression update:
                - sentiment_score: float or None
                - sentiment_label: str or None
                - sentiment_confidence: float or None
                - sentiment_status: str
                - sentiment_model: str or None
                - sentiment_computed_at: datetime or None

        Example:
            >>> service = SentimentService()
            >>> result = service.enrich_expression_sentiment(
            ...     readable="This article is very positive!",
            ...     language="en"
            ... )
            >>> print(result["sentiment_score"])
            0.87
        """
        from datetime import datetime, timezone

        # Choose best text source
        text = readable if readable else content

        if not text or len(text.strip()) < 10:
            logger.debug("No usable content for sentiment analysis")
            return {
                "sentiment_score": None,
                "sentiment_label": None,
                "sentiment_confidence": None,
                "sentiment_status": "no_content",
                "sentiment_model": None,
                "sentiment_computed_at": None
            }

        # Detect language if not provided
        if not language:
            try:
                language = detect_language(text)
                logger.debug(f"Detected language: {language}")
            except Exception as e:
                logger.warning(f"Language detection failed: {e}")
                language = "en"  # Fallback to English

        # Prepare text
        clean_text = prepare_text_for_sentiment(text, max_length=2000)

        # Analyze sentiment
        result = self.provider.analyze_sentiment(clean_text, language)

        # Add timestamp if computed
        timestamp = None
        if result["status"] == "computed":
            timestamp = datetime.now(timezone.utc)

        return {
            "sentiment_score": result["score"],
            "sentiment_label": result["label"],
            "sentiment_confidence": result["confidence"],
            "sentiment_status": result["status"],
            "sentiment_model": result["model"],
            "sentiment_computed_at": timestamp
        }

    def should_compute_sentiment(
        self,
        existing_score: Optional[float],
        force_recompute: bool = False
    ) -> bool:
        """
        Determine if sentiment should be computed.

        Args:
            existing_score: Current sentiment_score in DB
            force_recompute: Override check

        Returns:
            True if should compute/recompute
        """
        if force_recompute:
            return True

        # Compute if never computed
        if existing_score is None:
            return True

        # Already computed and not forcing
        return False
```

#### 4.2 Définir Seuil de Confiance

**Dans `sentiment_service.py`**, ajouter:

```python
# Configuration thresholds
MIN_CONFIDENCE_THRESHOLD = 0.5  # Below this, set status = "low_confidence"

def enrich_expression_sentiment(...) -> Dict[str, Any]:
    # ... (code précédent)

    result = self.provider.analyze_sentiment(clean_text, language)

    # Apply confidence threshold
    if result["status"] == "computed" and result["confidence"] < MIN_CONFIDENCE_THRESHOLD:
        logger.info(
            f"Low confidence sentiment: {result['confidence']:.2f} < {MIN_CONFIDENCE_THRESHOLD}"
        )
        result["status"] = "low_confidence"
        # Keep score but flag as uncertain

    # ... (return)
```

#### 4.3 Instrumentation (Métriques)

**Optionnel mais recommandé**: Ajouter métriques Prometheus/StatsD

```python
# Dans sentiment_service.py
import time
from app.utils.metrics import metrics_client  # Assuming exists

def enrich_expression_sentiment(...) -> Dict[str, Any]:
    start_time = time.time()

    # ... (processing)

    result = self.provider.analyze_sentiment(clean_text, language)

    # Track metrics
    duration_ms = (time.time() - start_time) * 1000

    # Log processing time
    metrics_client.timing('sentiment.analysis.duration', duration_ms)
    metrics_client.increment(f'sentiment.status.{result["status"]}')

    if result["status"] == "computed":
        metrics_client.histogram('sentiment.score', result["score"])

    logger.info(f"Sentiment computed in {duration_ms:.0f}ms: {result['label']}")

    # ... (return)
```

### Tests Étape 4

```python
# MyWebIntelligenceAPI/tests/unit/test_sentiment_service.py

import pytest
from app.services.sentiment_service import SentimentService

@pytest.fixture
def service():
    return SentimentService()

def test_enrich_with_readable_content(service):
    result = service.enrich_expression_sentiment(
        content=None,
        readable="This is a wonderful day with great weather!",
        language="en"
    )

    assert result["sentiment_status"] == "computed"
    assert result["sentiment_score"] > 0.3
    assert result["sentiment_label"] == "positive"
    assert result["sentiment_computed_at"] is not None

def test_enrich_with_fallback_to_content(service):
    """Should use content if readable is None."""
    result = service.enrich_expression_sentiment(
        content="<p>Amazing experience!</p>",
        readable=None,
        language="en"
    )

    assert result["sentiment_status"] == "computed"
    assert result["sentiment_label"] == "positive"

def test_enrich_with_language_autodetection(service):
    """Should auto-detect language if not provided."""
    result = service.enrich_expression_sentiment(
        readable="Ceci est un texte en français."
    )

    # Should work even without explicit language
    assert result["sentiment_status"] in ["computed", "unsupported_lang"]

def test_enrich_no_content(service):
    result = service.enrich_expression_sentiment(
        content=None,
        readable=None
    )

    assert result["sentiment_status"] == "no_content"
    assert result["sentiment_score"] is None

def test_should_compute_new_expression(service):
    """Should compute for expressions without sentiment."""
    assert service.should_compute_sentiment(existing_score=None) is True

def test_should_not_recompute_existing(service):
    """Should not recompute unless forced."""
    assert service.should_compute_sentiment(existing_score=0.5) is False

def test_should_force_recompute(service):
    """Should recompute when forced."""
    assert service.should_compute_sentiment(
        existing_score=0.5,
        force_recompute=True
    ) is True

def test_low_confidence_handling(service, monkeypatch):
    """Should flag low confidence results."""
    # Mock provider to return low confidence
    def mock_analyze(text, lang):
        return {
            "score": 0.3,
            "label": "neutral",
            "confidence": 0.45,  # Below 0.5 threshold
            "status": "computed",
            "model": "mock"
        }

    monkeypatch.setattr(service.provider, "analyze_sentiment", mock_analyze)

    result = service.enrich_expression_sentiment(
        readable="Some text",
        language="en"
    )

    assert result["sentiment_status"] == "low_confidence"
    assert result["sentiment_score"] == 0.3  # Score kept but flagged
```

**Exécution**:
```bash
pytest tests/unit/test_sentiment_service.py -v
```

### Livrables Étape 4
- [ ] Fichier `sentiment_service.py` avec orchestration complète
- [ ] Tests unitaires service (8+ cas de test)
- [ ] Documentation workflow dans docstrings
- [ ] Métriques instrumentées (optionnel)

---

## 🕷️ ÉTAPE 5 – Intégration Pipeline Crawler (Durée: 3-4h)

### Objectif
⚠️ **CRITIQUE**: Intégrer sentiment dans LES DEUX crawlers (async + sync).

### Actions

#### 5.1 Intégration dans `crawler_engine.py` (ASYNC)

**Fichier**: `MyWebIntelligenceAPI/app/core/crawler_engine.py`

**Localisation**: Après extraction de contenu (ligne ~250-300)

```python
# Dans la méthode AsyncCrawlerEngine._process_expression ou équivalent

from app.services.sentiment_service import SentimentService

class AsyncCrawlerEngine:
    def __init__(self, ...):
        # ... existing code ...
        self.sentiment_service = SentimentService()  # ✅ NOUVEAU

    async def _process_expression(
        self,
        expr_url: str,
        expression: Expression,
        depth: int,
        # ...
    ):
        # ... existing extraction logic ...

        # After content extraction and metadata extraction
        extraction_result = await self.content_extractor.extract_content(
            html=response_html,
            url=expr_url
        )

        # Update expression with extracted data
        expression.content = extraction_result.get('content')
        expression.readable = extraction_result.get('readable')
        expression.title = extraction_result.get('title')
        # ... other fields ...

        # ✅ NOUVEAU: Enrich with sentiment
        if settings.ENABLE_SENTIMENT_ANALYSIS:  # Master switch
            try:
                # Determine method: TextBlob (default) or LLM (if llm_validation=true)
                use_llm = llm_validation and settings.OPENROUTER_ENABLED

                sentiment_data = await self.sentiment_service.enrich_expression_sentiment(
                    content=expression.content,
                    readable=expression.readable,
                    language=expression.lang,  # Use detected language
                    use_llm=use_llm  # ✅ Réutilise le flag llm_validation
                )

                # Update expression with sentiment data
                expression.sentiment_score = sentiment_data["sentiment_score"]
                expression.sentiment_label = sentiment_data["sentiment_label"]
                expression.sentiment_confidence = sentiment_data["sentiment_confidence"]
                expression.sentiment_status = sentiment_data["sentiment_status"]
                expression.sentiment_model = sentiment_data["sentiment_model"]
                expression.sentiment_computed_at = sentiment_data["sentiment_computed_at"]

                logger.debug(
                    f"Sentiment enriched for {expr_url}: "
                    f"{sentiment_data['sentiment_label']} ({sentiment_data['sentiment_score']}) "
                    f"via {sentiment_data['sentiment_model']}"
                )
            except Exception as e:
                logger.error(f"Sentiment enrichment failed for {expr_url}: {e}")
                # Continue without sentiment (non-blocking)

        # ... rest of processing ...
```

#### 5.2 Intégration dans `crawler_engine_sync.py` (SYNC)

**⚠️ DOUBLE CRAWLER - NE PAS OUBLIER !**

**Fichier**: `MyWebIntelligenceAPI/app/core/crawler_engine_sync.py`

**MÊME LOGIQUE** que async, ajuster pour code synchrone:

```python
from app.services.sentiment_service import SentimentService

class SyncCrawlerEngine:
    def __init__(self, ...):
        # ... existing code ...
        self.sentiment_service = SentimentService()  # ✅ NOUVEAU

    def _process_expression(
        self,
        expr_url: str,
        expression: Expression,
        depth: int,
        # ...
    ):
        # ... existing extraction logic ...

        extraction_result = self.content_extractor.extract_content_sync(
            html=response_html,
            url=expr_url
        )

        # ... update expression fields ...

        # ✅ NOUVEAU: Enrich with sentiment (IDENTIQUE à async)
        if settings.ENABLE_SENTIMENT_ANALYSIS:  # Master switch
            try:
                # Determine method: TextBlob (default) or LLM (if llm_validation=true)
                use_llm = llm_validation and settings.OPENROUTER_ENABLED

                # Note: sentiment_service methods are sync-compatible
                sentiment_data = self.sentiment_service.enrich_expression_sentiment(
                    content=expression.content,
                    readable=expression.readable,
                    language=expression.lang,
                    use_llm=use_llm  # ✅ Réutilise le flag llm_validation
                )

                expression.sentiment_score = sentiment_data["sentiment_score"]
                expression.sentiment_label = sentiment_data["sentiment_label"]
                expression.sentiment_confidence = sentiment_data["sentiment_confidence"]
                expression.sentiment_status = sentiment_data["sentiment_status"]
                expression.sentiment_model = sentiment_data["sentiment_model"]
                expression.sentiment_computed_at = sentiment_data["sentiment_computed_at"]

                logger.debug(
                    f"[SYNC] Sentiment enriched for {expr_url}: "
                    f"{sentiment_data['sentiment_label']} via {sentiment_data['sentiment_model']}"
                )
            except Exception as e:
                logger.error(f"[SYNC] Sentiment enrichment failed: {e}")

        # ... rest ...
```

#### 5.3 Configuration (Réutilise Settings Existants)

**Fichier**: `MyWebIntelligenceAPI/app/config.py`

```python
class Settings(BaseSettings):
    # ... existing settings ...

    # Sentiment Analysis (✅ Réutilise OPENROUTER settings existants)
    ENABLE_SENTIMENT_ANALYSIS: bool = True  # ✅ NOUVEAU - Master switch
    SENTIMENT_MIN_CONFIDENCE: float = 0.5
    SENTIMENT_SUPPORTED_LANGUAGES: str = "fr,en"  # Comma-separated

    # OpenRouter (✅ DÉJÀ EXISTANT - utilisé pour LLM validation + sentiment)
    OPENROUTER_ENABLED: bool = False
    OPENROUTER_API_KEY: str = ""
    OPENROUTER_MODEL: str = "anthropic/claude-3.5-sonnet"

    class Config:
        env_file = ".env"
```

**Fichier**: `MyWebIntelligenceAPI/.env`

```bash
# Sentiment Analysis Configuration
ENABLE_SENTIMENT_ANALYSIS=true  # ✅ NOUVEAU - Active/désactive sentiment globalement
SENTIMENT_MIN_CONFIDENCE=0.5
SENTIMENT_SUPPORTED_LANGUAGES=fr,en

# OpenRouter (✅ DÉJÀ EXISTANT - pas de changement)
OPENROUTER_ENABLED=true
OPENROUTER_API_KEY=sk-or-v1-your-key
OPENROUTER_MODEL=anthropic/claude-3.5-sonnet
```

**Note importante** :
- `ENABLE_SENTIMENT_ANALYSIS` : Active/désactive le sentiment globalement
- `llm_validation` (paramètre crawl) : Choix TextBlob vs LLM
- Pas besoin de nouveau flag `enable_llm_sentiment` !

#### 5.4 Vérification Règle Double Crawler

**Checklist OBLIGATOIRE** (voir `ERREUR_DOUBLE_CRAWLER.md`):

- [ ] ✅ Modifier `crawler_engine.py` (async)
- [ ] ✅ Modifier `crawler_engine_sync.py` (sync)
- [ ] ✅ Vérifier que les deux ont la MÊME logique sentiment
- [ ] ✅ Tester avec Celery (pas seulement l'API directe)

**Vérification**:
```bash
# Chercher "sentiment" dans les DEUX crawlers
grep -n "sentiment_service" MyWebIntelligenceAPI/app/core/crawler_engine.py
grep -n "sentiment_service" MyWebIntelligenceAPI/app/core/crawler_engine_sync.py

# Les deux doivent avoir des lignes similaires !
```

### Tests Étape 5

#### Test d'Intégration Crawler Async

```python
# MyWebIntelligenceAPI/tests/integration/test_crawler_sentiment.py

import pytest
from app.core.crawler_engine import AsyncCrawlerEngine
from app.db.models import Expression, Land

@pytest.mark.asyncio
async def test_crawler_enriches_sentiment(db_session, test_land):
    """Verify async crawler adds sentiment to expressions."""

    # Create crawler
    crawler = AsyncCrawlerEngine(db_session=db_session)

    # Crawl a test URL with clear sentiment
    test_url = "https://httpbin.org/html"  # Neutral content

    # ... (setup expression in DB)

    # Crawl
    await crawler.crawl_url(test_url, land_id=test_land.id, depth=0)

    # Retrieve expression
    expression = db_session.query(Expression).filter_by(url=test_url).first()

    # Assertions
    assert expression is not None
    assert expression.sentiment_status in ["computed", "unsupported_lang", "no_content"]

    if expression.sentiment_status == "computed":
        assert expression.sentiment_score is not None
        assert expression.sentiment_label in ["positive", "neutral", "negative"]
        assert expression.sentiment_confidence is not None
        assert expression.sentiment_model is not None
        assert expression.sentiment_computed_at is not None
```

#### Test Crawler Sync (Celery)

```bash
# MyWebIntelligenceAPI/tests/test-crawl-sentiment.sh

#!/bin/bash
# Test sentiment integration in sync crawler (Celery)

# ... (authentication, create land)

# Crawl with sentiment enabled
curl -X POST "http://localhost:8000/api/v2/lands/${LAND_ID}/crawl" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "limit": 3,
    "enable_sentiment": true
  }'

# Wait for completion
sleep 30

# Verify sentiment in DB
docker exec mywebclient-db-1 psql -U mwi_user -d mwi_db -c "
  SELECT
    id,
    url,
    sentiment_score,
    sentiment_label,
    sentiment_status
  FROM expressions
  WHERE land_id = ${LAND_ID}
  LIMIT 5;
"
```

### Livrables Étape 5
- [ ] `crawler_engine.py` modifié avec sentiment
- [ ] `crawler_engine_sync.py` modifié (IDENTIQUE)
- [ ] Feature flag dans `config.py`
- [ ] Tests intégration (1 async + 1 sync)
- [ ] Documentation dans `AGENTS.md` (nouvelle section sentiment)

---

## 📡 ÉTAPE 6 – Persistance & API (Durée: 2h)

### Objectif
Exposer les champs sentiment dans les schémas Pydantic et endpoints API.

### Actions

#### 6.1 Mettre à Jour Schémas Pydantic

**Fichier**: `MyWebIntelligenceAPI/app/schemas/expression.py`

```python
from typing import Optional
from datetime import datetime
from pydantic import BaseModel, Field

class ExpressionBase(BaseModel):
    # ... existing fields ...

    # Sentiment Analysis (✅ NOUVEAU)
    sentiment_score: Optional[float] = Field(
        None,
        description="Sentiment score from -1.0 (negative) to +1.0 (positive)"
    )
    sentiment_label: Optional[str] = Field(
        None,
        description="Sentiment label: positive, neutral, or negative"
    )
    sentiment_confidence: Optional[float] = Field(
        None,
        description="Model confidence score (0.0 to 1.0)"
    )
    sentiment_status: Optional[str] = Field(
        None,
        description="Status: computed, failed, unsupported_lang, no_content, low_confidence"
    )
    sentiment_model: Optional[str] = Field(
        None,
        description="Model used for sentiment analysis"
    )
    sentiment_computed_at: Optional[datetime] = Field(
        None,
        description="Timestamp when sentiment was computed"
    )

class ExpressionOut(ExpressionBase):
    """Schema for Expression API output."""
    id: int
    url: str
    # ... other output fields ...

    # Sentiment fields inherited from Base

    class Config:
        from_attributes = True

class ExpressionCreate(BaseModel):
    """Schema for creating Expression."""
    # Sentiment fields NOT in create (computed post-creation)
    pass

class ExpressionUpdate(BaseModel):
    """Schema for updating Expression."""
    # ... existing updateable fields ...

    # Allow manual sentiment override (optional)
    sentiment_score: Optional[float] = None
    sentiment_label: Optional[str] = None
```

#### 6.2 Vérifier Endpoints Exposent Sentiment

**Fichier**: `MyWebIntelligenceAPI/app/api/v2/endpoints/lands_v2.py`

```python
@router.get("/{land_id}/expressions", response_model=List[ExpressionOut])
async def get_land_expressions(
    land_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    # ... filters ...
):
    """
    Get expressions for a land.

    Returns expressions with all fields including sentiment analysis.
    """
    # ... existing query ...

    # ExpressionOut schema will automatically include sentiment fields
    return expressions
```

**Vérifier aussi**:
- `GET /api/v2/lands/{id}/expressions/{expr_id}`
- `POST /api/v1/export/direct` (CSV exports)

#### 6.3 Documenter dans OpenAPI

Pydantic génère automatiquement la doc OpenAPI, mais vérifier:

```bash
# Accéder à la doc
open http://localhost:8000/docs

# Vérifier schéma ExpressionOut inclut:
# - sentiment_score
# - sentiment_label
# - sentiment_confidence
# - sentiment_status
# - sentiment_model
# - sentiment_computed_at
```

#### 6.4 Mettre à Jour Exports CSV/JSON

**Fichier**: `MyWebIntelligenceAPI/app/services/export_service.py`

```python
def export_expressions_csv(self, land_id: int, ...) -> str:
    """
    Export expressions to CSV.

    Includes sentiment fields in output.
    """
    # ... existing query ...

    # CSV headers
    headers = [
        'id', 'url', 'title', 'relevance', 'depth',
        'language', 'word_count',
        # ✅ NOUVEAU
        'sentiment_score', 'sentiment_label',
        'sentiment_confidence', 'sentiment_status'
    ]

    # ... write CSV ...
```

### Tests Étape 6

```python
# MyWebIntelligenceAPI/tests/api/test_expression_api_sentiment.py

import pytest
from httpx import AsyncClient

@pytest.mark.asyncio
async def test_get_expression_includes_sentiment(
    client: AsyncClient,
    test_expression_with_sentiment
):
    """Verify GET /expressions/{id} returns sentiment fields."""

    response = await client.get(
        f"/api/v2/expressions/{test_expression_with_sentiment.id}"
    )

    assert response.status_code == 200
    data = response.json()

    # Check sentiment fields present
    assert "sentiment_score" in data
    assert "sentiment_label" in data
    assert "sentiment_confidence" in data
    assert "sentiment_status" in data

    # Verify values
    assert data["sentiment_score"] == pytest.approx(0.85, abs=0.01)
    assert data["sentiment_label"] == "positive"

@pytest.mark.asyncio
async def test_export_csv_includes_sentiment(client: AsyncClient, test_land):
    """Verify CSV export contains sentiment columns."""

    response = await client.post(
        "/api/v1/export/direct",
        json={
            "land_id": test_land.id,
            "export_type": "pagecsv"
        }
    )

    assert response.status_code == 200
    csv_content = response.text

    # Check CSV headers
    assert "sentiment_score" in csv_content
    assert "sentiment_label" in csv_content
    assert "sentiment_confidence" in csv_content

@pytest.mark.asyncio
async def test_expression_without_sentiment_returns_null(
    client: AsyncClient,
    test_expression_no_sentiment
):
    """Expressions without sentiment should return null values."""

    response = await client.get(
        f"/api/v2/expressions/{test_expression_no_sentiment.id}"
    )

    data = response.json()
    assert data["sentiment_score"] is None
    assert data["sentiment_label"] is None
    assert data["sentiment_status"] is None
```

### Livrables Étape 6
- [ ] `expression.py` schémas mis à jour
- [ ] Endpoints API vérifiés (retournent sentiment)
- [ ] Export CSV/JSON inclut sentiment
- [ ] Documentation OpenAPI à jour
- [ ] Tests API (3+ cas de test)

---

## 🔄 ÉTAPE 7 – Reprocessing Historique (Durée: 3-4h)

### Objectif
Permettre le recalcul du sentiment sur expressions existantes (batch job).

### Actions

#### 7.1 Créer Task Celery pour Batch

**Nouveau fichier**: `MyWebIntelligenceAPI/app/tasks/sentiment_task.py`

```python
"""
Celery tasks for sentiment analysis batch processing.
"""

import logging
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.core.celery_app import celery_app
from app.db.models import Expression
from app.db.session import AsyncSessionLocal
from app.services.sentiment_service import SentimentService

logger = logging.getLogger(__name__)

@celery_app.task(bind=True, name="sentiment.batch_reprocess")
def batch_reprocess_sentiment(
    self,
    land_id: Optional[int] = None,
    limit: int = 100,
    force_recompute: bool = False
):
    """
    Batch reprocess sentiment for expressions.

    Args:
        land_id: If provided, process only this land
        limit: Max expressions to process per batch
        force_recompute: Recompute even if sentiment exists

    Returns:
        Dict with stats: processed, successful, errors
    """
    import asyncio

    async def _process():
        async with AsyncSessionLocal() as db:
            service = SentimentService()

            # Build query
            query = select(Expression)

            if land_id:
                query = query.filter(Expression.land_id == land_id)

            if not force_recompute:
                # Only expressions without sentiment
                query = query.filter(Expression.sentiment_score.is_(None))

            # Limit and order
            query = query.order_by(Expression.id).limit(limit)

            result = await db.execute(query)
            expressions = result.scalars().all()

            logger.info(
                f"Batch processing {len(expressions)} expressions for sentiment"
            )

            stats = {"processed": 0, "successful": 0, "errors": 0}

            for expr in expressions:
                try:
                    # Compute sentiment
                    sentiment_data = service.enrich_expression_sentiment(
                        content=expr.content,
                        readable=expr.readable,
                        language=expr.lang
                    )

                    # Update expression
                    expr.sentiment_score = sentiment_data["sentiment_score"]
                    expr.sentiment_label = sentiment_data["sentiment_label"]
                    expr.sentiment_confidence = sentiment_data["sentiment_confidence"]
                    expr.sentiment_status = sentiment_data["sentiment_status"]
                    expr.sentiment_model = sentiment_data["sentiment_model"]
                    expr.sentiment_computed_at = sentiment_data["sentiment_computed_at"]

                    stats["processed"] += 1
                    if sentiment_data["sentiment_status"] == "computed":
                        stats["successful"] += 1

                    # Update task progress
                    self.update_state(
                        state='PROGRESS',
                        meta={
                            'current': stats["processed"],
                            'total': len(expressions),
                            'status': f"Processing expression {expr.id}"
                        }
                    )

                except Exception as e:
                    logger.error(f"Error processing expression {expr.id}: {e}")
                    stats["errors"] += 1
                    continue

            # Commit all updates
            await db.commit()

            logger.info(f"Batch completed: {stats}")
            return stats

    # Run async code in Celery (sync context)
    return asyncio.run(_process())

@celery_app.task(name="sentiment.reprocess_expression")
def reprocess_single_expression(expression_id: int):
    """
    Reprocess sentiment for a single expression.

    Args:
        expression_id: Expression ID to process
    """
    import asyncio

    async def _process():
        async with AsyncSessionLocal() as db:
            service = SentimentService()

            # Get expression
            result = await db.execute(
                select(Expression).filter(Expression.id == expression_id)
            )
            expr = result.scalar_one_or_none()

            if not expr:
                raise ValueError(f"Expression {expression_id} not found")

            # Compute sentiment
            sentiment_data = service.enrich_expression_sentiment(
                content=expr.content,
                readable=expr.readable,
                language=expr.lang
            )

            # Update
            expr.sentiment_score = sentiment_data["sentiment_score"]
            expr.sentiment_label = sentiment_data["sentiment_label"]
            expr.sentiment_confidence = sentiment_data["sentiment_confidence"]
            expr.sentiment_status = sentiment_data["sentiment_status"]
            expr.sentiment_model = sentiment_data["sentiment_model"]
            expr.sentiment_computed_at = sentiment_data["sentiment_computed_at"]

            await db.commit()

            logger.info(
                f"Expression {expression_id} sentiment updated: "
                f"{sentiment_data['sentiment_label']}"
            )

            return sentiment_data

    return asyncio.run(_process())
```

#### 7.2 Créer Endpoint API pour Lancement Batch

**Fichier**: `MyWebIntelligenceAPI/app/api/v2/endpoints/lands_v2.py`

```python
from app.tasks.sentiment_task import batch_reprocess_sentiment

@router.post("/{land_id}/reprocess-sentiment")
async def reprocess_land_sentiment(
    land_id: int,
    limit: int = 100,
    force_recompute: bool = False,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Reprocess sentiment for expressions in a land.

    Launches a Celery task to batch process expressions.

    Args:
        land_id: Land ID to process
        limit: Max expressions per batch (default 100)
        force_recompute: Recompute even if sentiment exists

    Returns:
        Task ID for monitoring progress
    """
    # Verify land exists and user has access
    land = await db.get(Land, land_id)
    if not land:
        raise HTTPException(status_code=404, detail="Land not found")

    if land.owner_id != current_user.id and not current_user.is_admin:
        raise HTTPException(status_code=403, detail="Access denied")

    # Launch task
    task = batch_reprocess_sentiment.delay(
        land_id=land_id,
        limit=limit,
        force_recompute=force_recompute
    )

    logger.info(
        f"Sentiment reprocessing task launched for land {land_id}: {task.id}"
    )

    return {
        "task_id": task.id,
        "status": "processing",
        "land_id": land_id,
        "limit": limit,
        "force_recompute": force_recompute
    }
```

#### 7.3 Script CLI pour Administration

**Nouveau fichier**: `MyWebIntelligenceAPI/scripts/admin/reprocess_sentiment.py`

```bash
#!/usr/bin/env python3
"""
CLI tool to reprocess sentiment for expressions.

Usage:
    python scripts/admin/reprocess_sentiment.py --land-id 36 --limit 50
    python scripts/admin/reprocess_sentiment.py --all --force
"""

import argparse
import asyncio
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.db.session import AsyncSessionLocal
from app.db.models import Expression
from app.services.sentiment_service import SentimentService

async def reprocess_sentiment(
    land_id: int = None,
    limit: int = 100,
    force: bool = False
):
    """Reprocess sentiment for expressions."""

    async with AsyncSessionLocal() as db:
        service = SentimentService()

        # Build query
        query = select(Expression)

        if land_id:
            query = query.filter(Expression.land_id == land_id)

        if not force:
            query = query.filter(Expression.sentiment_score.is_(None))

        query = query.order_by(Expression.id).limit(limit)

        result = await db.execute(query)
        expressions = result.scalars().all()

        print(f"Processing {len(expressions)} expressions...")

        for i, expr in enumerate(expressions, 1):
            sentiment_data = service.enrich_expression_sentiment(
                content=expr.content,
                readable=expr.readable,
                language=expr.lang
            )

            expr.sentiment_score = sentiment_data["sentiment_score"]
            expr.sentiment_label = sentiment_data["sentiment_label"]
            expr.sentiment_confidence = sentiment_data["sentiment_confidence"]
            expr.sentiment_status = sentiment_data["sentiment_status"]

            if i % 10 == 0:
                print(f"  Processed {i}/{len(expressions)}...")

        await db.commit()
        print(f"✅ Completed: {len(expressions)} expressions updated")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--land-id", type=int, help="Land ID to process")
    parser.add_argument("--limit", type=int, default=100, help="Max expressions")
    parser.add_argument("--force", action="store_true", help="Force recompute")

    args = parser.parse_args()

    asyncio.run(reprocess_sentiment(
        land_id=args.land_id,
        limit=args.limit,
        force=args.force
    ))
```

#### 7.4 Throttling & Gestion d'Erreurs

Dans `sentiment_task.py`, ajouter:

```python
@celery_app.task(
    bind=True,
    name="sentiment.batch_reprocess",
    max_retries=3,
    default_retry_delay=60  # 1 minute
)
def batch_reprocess_sentiment(self, ...):
    # ... code ...

    # Add delay between expressions to avoid overload
    import time

    for expr in expressions:
        try:
            # ... processing ...

            # Throttle: 100ms between expressions
            time.sleep(0.1)

        except Exception as e:
            logger.error(f"Error: {e}")
            stats["errors"] += 1

            # Retry task if too many errors
            if stats["errors"] > len(expressions) * 0.5:  # 50% error rate
                raise self.retry(exc=e)
```

### Tests Étape 7

```python
# MyWebIntelligenceAPI/tests/integration/test_sentiment_batch.py

import pytest
from app.tasks.sentiment_task import batch_reprocess_sentiment

def test_batch_reprocess_dry_run(db_session, test_land):
    """Test batch reprocessing on small dataset."""

    # Create test expressions without sentiment
    # ... (setup)

    # Run batch (synchronously for test)
    result = batch_reprocess_sentiment(
        land_id=test_land.id,
        limit=5,
        force_recompute=False
    )

    assert result["processed"] == 5
    assert result["successful"] >= 4  # Allow 1 failure
    assert result["errors"] <= 1

def test_batch_reprocess_force(db_session, test_land):
    """Test force recompute on expressions with existing sentiment."""

    # ... (setup with existing sentiment)

    result = batch_reprocess_sentiment(
        land_id=test_land.id,
        limit=5,
        force_recompute=True
    )

    assert result["processed"] == 5
```

### Livrables Étape 7
- [ ] Task Celery `sentiment_task.py` avec batch + single
- [ ] Endpoint API `/lands/{id}/reprocess-sentiment`
- [ ] Script CLI `reprocess_sentiment.py`
- [ ] Throttling + retry logic
- [ ] Tests batch (2+ cas)

---

## 📊 ÉTAPE 8 – Monitoring & Déploiement (Durée: 2-3h)

### Objectif
Instrumenter le système, déployer progressivement, surveiller.

### Actions

#### 8.1 Ajouter Métriques (Prometheus/StatsD)

**Fichier**: `MyWebIntelligenceAPI/app/services/sentiment_service.py`

```python
from app.utils.metrics import metrics  # Assuming prometheus_client

class SentimentService:
    # Metrics
    sentiment_counter = metrics.Counter(
        'sentiment_analysis_total',
        'Total sentiment analyses',
        ['status', 'language']
    )

    sentiment_duration = metrics.Histogram(
        'sentiment_analysis_duration_seconds',
        'Sentiment analysis duration'
    )

    sentiment_score_gauge = metrics.Gauge(
        'sentiment_score_distribution',
        'Distribution of sentiment scores',
        ['label']
    )

    def enrich_expression_sentiment(...) -> Dict[str, Any]:
        with self.sentiment_duration.time():
            # ... processing ...

            result = self.provider.analyze_sentiment(...)

            # Increment counter
            self.sentiment_counter.labels(
                status=result["status"],
                language=language
            ).inc()

            # Record score distribution
            if result["status"] == "computed":
                self.sentiment_score_gauge.labels(
                    label=result["label"]
                ).set(result["score"])

            return {...}
```

#### 8.2 Dashboard Monitoring

**Grafana Dashboard** (optionnel, requiert Prometheus):

```yaml
# dashboard.json (exemple simplifié)
{
  "panels": [
    {
      "title": "Sentiment Analysis Rate",
      "targets": [
        {
          "expr": "rate(sentiment_analysis_total[5m])"
        }
      ]
    },
    {
      "title": "Sentiment Score Distribution",
      "targets": [
        {
          "expr": "sentiment_score_distribution"
        }
      ]
    },
    {
      "title": "Analysis Duration (p95)",
      "targets": [
        {
          "expr": "histogram_quantile(0.95, sentiment_analysis_duration_seconds)"
        }
      ]
    }
  ]
}
```

#### 8.3 Logging Détaillé

Assurer logs structurés pour debug:

```python
# Dans sentiment_service.py
logger.info(
    "Sentiment computed",
    extra={
        "expression_id": expr_id,
        "sentiment_label": result["label"],
        "sentiment_score": result["score"],
        "confidence": result["confidence"],
        "language": language,
        "duration_ms": duration * 1000
    }
)
```

#### 8.4 Guide Exploitation

**Nouveau fichier**: `MyWebIntelligenceAPI/docs/SENTIMENT_OPERATIONS.md`

```markdown
# Sentiment Analysis - Guide d'Exploitation

## Activation/Désactivation

### Désactiver temporairement
```bash
# Dans .env
ENABLE_SENTIMENT_ANALYSIS=false

# Redémarrer services
docker compose restart api celery_worker
```

### Réactiver
```bash
ENABLE_SENTIMENT_ANALYSIS=true
docker compose restart api celery_worker
```

## Monitoring

### Métriques clés
- `sentiment_analysis_total`: Nombre d'analyses
- `sentiment_analysis_duration_seconds`: Latence
- Distribution `null` vs `computed`: Taux de succès

### Logs à surveiller
```bash
# Logs sentiment
docker logs mywebclient-api-1 | grep "Sentiment"

# Erreurs
docker logs mywebclient-api-1 | grep "sentiment.*ERROR"
```

## Troubleshooting

### Symptôme: Beaucoup de `unsupported_lang`
**Cause**: Expressions dans langues non supportées (DE, ES, etc.)
**Action**: Ajouter langues dans `SENTIMENT_SUPPORTED_LANGUAGES`

### Symptôme: Latence > 2s
**Cause**: Modèle lourd ou CPU surchargé
**Actions**:
1. Vérifier charge CPU: `docker stats`
2. Passer à GPU si disponible
3. Réduire `max_length` du modèle (512 → 256 tokens)

### Symptôme: `sentiment_score` toujours NULL
**Cause**: Feature flag désactivé ou erreur modèle
**Actions**:
1. Vérifier `ENABLE_SENTIMENT_ANALYSIS=true`
2. Vérifier logs chargement modèle
3. Test manuel: `python -c "from app.services.sentiment_service import SentimentService; print(SentimentService().enrich_expression_sentiment('test'))"`

## Rollback

### Procédure d'urgence
```bash
# 1. Désactiver sentiment
ENABLE_SENTIMENT_ANALYSIS=false

# 2. Redémarrer
docker compose restart api celery_worker

# 3. Vérifier crawl fonctionne sans sentiment
curl -X POST http://localhost:8000/api/v2/lands/TEST/crawl
```
```

#### 8.5 Déploiement Progressif

**Plan de déploiement**:

1. **Phase 1: Staging (1 semaine)**
   ```bash
   # Déployer sur environnement staging
   ENABLE_SENTIMENT_ANALYSIS=true

   # Tester sur petit échantillon (10 lands)
   # Surveiller métriques, logs, latence
   ```

2. **Phase 2: Production Canary (1 semaine)**
   ```bash
   # Activer seulement pour 10% des lands
   # Modifier code pour sampling:

   if land_id % 10 == 0:  # 10% canary
       enable_sentiment = True
   ```

3. **Phase 3: Production Complète**
   ```bash
   # Activer pour tous après validation
   ENABLE_SENTIMENT_ANALYSIS=true
   ```

### Tests Étape 8

#### Smoke Test Post-Déploiement

```bash
# MyWebIntelligenceAPI/tests/smoke/test_sentiment_smoke.sh

#!/bin/bash
# Smoke test for sentiment feature after deployment

echo "🧪 Sentiment Feature Smoke Test"

# 1. Verify API is up
HTTP_CODE=$(curl -s -w "%{http_code}" "http://localhost:8000/health" -o /dev/null)
if [ "$HTTP_CODE" != "200" ]; then
    echo "❌ API not responding"
    exit 1
fi
echo "✅ API responding"

# 2. Crawl test URL
# ... (create land, crawl)

# 3. Verify sentiment in DB
SENTIMENT_COUNT=$(docker exec mywebclient-db-1 psql -U mwi_user -d mwi_db -t -c \
  "SELECT COUNT(*) FROM expressions WHERE sentiment_score IS NOT NULL;")

echo "Expressions with sentiment: $SENTIMENT_COUNT"

if [ "$SENTIMENT_COUNT" -gt 0 ]; then
    echo "✅ Sentiment feature working"
else
    echo "⚠️ No sentiment computed (check feature flag)"
fi

# 4. Check metrics endpoint
curl -s http://localhost:8000/metrics | grep sentiment_analysis_total

echo "✅ Smoke test completed"
```

### Livrables Étape 8
- [ ] Métriques Prometheus instrumentées
- [ ] Guide exploitation (`SENTIMENT_OPERATIONS.md`)
- [ ] Plan de déploiement progressif
- [ ] Smoke test post-déploiement
- [ ] Dashboard monitoring (optionnel)

---

## 📝 Documentation Finale

### Fichiers à Créer/Mettre à Jour

1. **`.claude/docs/sentiment_dev.md`** (ce fichier)
   - Plan détaillé complet

2. **`.claude/docs/sentiment_validation_strategy.md`** ✅ CRÉÉ
   - 5 niveaux de validation (Provider → Métier)
   - Corpus annoté (60 expressions FR/EN)
   - Comparaison TextBlob vs LLM
   - Critères de succès et métriques

3. **`.claude/AGENTS.md`**
   - Ajouter section "Sentiment Analysis"
   - Checklist intégration double crawler

4. **`MyWebIntelligenceAPI/README.md`**
   - Ajouter feature sentiment dans liste
   - Variables d'environnement sentiment

5. **`MyWebIntelligenceAPI/docs/API.md`**
   - Documenter nouveaux champs API
   - Endpoint `/reprocess-sentiment`

6. **`MyWebIntelligenceAPI/docs/SENTIMENT_OPERATIONS.md`**
   - Guide opérationnel (créé Étape 8)

---

## ✅ Checklist Globale

### Étape 1 - Cartographie ✅
- [x] Vérifier modèle Expression
- [ ] Tracer flux crawlers
- [ ] Inventaire dépendances
- [ ] Tests audit complets

### Étape 2 - Corpus & Exigences
- [ ] Constituer corpus 50-60 textes
- [ ] Annoter manuellement
- [ ] Définir seuils & format
- [ ] Documenter cas limites

### Étape 3 - Modèle
- [ ] Choisir modèle (Option A recommandée)
- [ ] Implémenter `SentimentModelProvider`
- [ ] Pipeline normalisation texte
- [ ] Tests unitaires provider (10+ cas)

### Étape 4 - Service
- [ ] Créer `SentimentService`
- [ ] Orchestration langue + sentiment
- [ ] Seuils confiance
- [ ] Tests service (8+ cas)

### Étape 5 - Intégration Crawlers ⚠️ CRITIQUE
- [ ] Modifier `crawler_engine.py` (async)
- [ ] Modifier `crawler_engine_sync.py` (sync)
- [ ] Vérifier PARITÉ entre les deux
- [ ] Feature flag configuration
- [ ] Tests intégration (async + sync)

### Étape 6 - API
- [ ] Schémas Pydantic mis à jour
- [ ] Endpoints exposent sentiment
- [ ] Exports CSV/JSON
- [ ] Tests API (3+ cas)

### Étape 7 - Batch Reprocessing
- [ ] Task Celery batch
- [ ] Endpoint API reprocess
- [ ] Script CLI admin
- [ ] Tests batch (2+ cas)

### Étape 8 - Monitoring & Déploiement
- [ ] Métriques instrumentées
- [ ] Guide exploitation
- [ ] Smoke tests
- [ ] Déploiement progressif

---

## 🚀 Prochaines Actions Immédiates

### Pour Démarrer (aujourd'hui)
1. Valider plan avec équipe/product owner
2. Confirmer ressources hardware (CPU/RAM/GPU)
3. Installer dépendances de test:
   ```bash
   pip install transformers torch sentencepiece
   ```
4. Constituer corpus annoté (Étape 2)

### Sprint 1 (Semaine 1)
- Étapes 1-3: Infrastructure modèle
- Tests unitaires provider

### Sprint 2 (Semaine 2)
- Étapes 4-5: Service + intégration crawlers
- Tests intégration

### Sprint 3 (Semaine 3)
- Étapes 6-7: API + batch
- Tests end-to-end

### Sprint 4 (Semaine 4)
- Étape 8: Monitoring + déploiement staging
- Validation métier

---

## 📞 Support & Questions

### Points de Blocage Potentiels

1. **Performance modèle trop lente**
   - Solution: GPU, modèle plus léger (DistilBERT), ou API cloud

2. **Mémoire insuffisante**
   - Solution: Augmenter RAM container, ou modèle quantized

3. **Langues non supportées majoritaires**
   - Solution: Ajouter modèles, ou accepter % null élevé

4. **Double crawler oublié**
   - Solution: Checklist stricte, revue code obligatoire

### Contacts
- Architecture: Voir `AGENTS.md`, `Architecture.md`
- Opérations: Voir `GEMINI.md`
- Bugs crawlers: Voir `ERREUR_DOUBLE_CRAWLER.md`

---

**Dernière mise à jour**: 18 octobre 2025
**Version**: 1.0
**Auteur**: Assistant AI (Claude)
**Statut**: Plan détaillé prêt pour implémentation
