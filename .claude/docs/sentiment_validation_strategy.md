# Stratégie de Validation - Sentiment Analysis

**Date**: 18 octobre 2025
**Projet**: MyWebIntelligence API - Sentiment Score
**Statut**: Plan de validation détaillé

---

## 🎯 Objectif

Définir une stratégie complète de validation du sentiment analysis à plusieurs niveaux : technique, qualité, et métier.

---

## 📊 Les 5 Niveaux de Validation

```
┌─────────────────────────────────────────────────────────────┐
│                   VALIDATION PYRAMID                         │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  5. Validation Métier (Humain)                             │
│     └─ Annotation manuelle corpus                           │
│                                                              │
│  4. Validation A/B Testing                                  │
│     └─ Comparaison TextBlob vs LLM                          │
│                                                              │
│  3. Validation End-to-End                                   │
│     └─ Tests intégration crawlers                           │
│                                                              │
│  2. Validation Service                                      │
│     └─ Tests unitaires SentimentService                     │
│                                                              │
│  1. Validation Provider                                     │
│     └─ Tests unitaires SentimentModelProvider               │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

---

## 1️⃣ Validation Provider (Technique)

### 1.1 Tests Unitaires TextBlob

**Fichier**: `tests/unit/test_sentiment_provider.py`

```python
def test_textblob_positive_sentiment_en():
    """Valider détection sentiment positif EN."""
    provider = SentimentModelProvider()
    result = provider._analyze_textblob(
        "This is absolutely amazing! I love it.",
        language="en"
    )

    assert result["status"] == "computed"
    assert result["label"] == "positive"
    assert result["score"] > 0.3
    assert result["model"] == "textblob"

def test_textblob_negative_sentiment_fr():
    """Valider détection sentiment négatif FR."""
    result = provider._analyze_textblob(
        "C'est vraiment horrible et décevant.",
        language="fr"
    )

    assert result["label"] == "negative"
    assert result["score"] < -0.3

def test_textblob_neutral_sentiment():
    """Valider détection sentiment neutre."""
    result = provider._analyze_textblob(
        "The meeting is scheduled for 3pm.",
        language="en"
    )

    # Neutre = score proche de 0
    assert abs(result["score"]) < 0.2
```

### 1.2 Tests Unitaires OpenRouter (LLM)

```python
@pytest.mark.asyncio
async def test_llm_sentiment_high_quality():
    """Valider sentiment LLM haute qualité."""
    provider = SentimentModelProvider()

    # Skip si pas de clé API
    if not settings.OPENROUTER_API_KEY:
        pytest.skip("No OpenRouter API key")

    result = await provider._analyze_openrouter(
        "I'm extremely disappointed with this product.",
        language="en"
    )

    assert result["status"] == "computed"
    assert result["label"] == "negative"
    assert result["confidence"] > 0.7  # LLM = haute confiance
    assert "llm/" in result["model"]
```

### 1.3 Tests Cas Limites

```python
def test_empty_text():
    """Valider gestion texte vide."""
    result = provider._analyze_textblob("", "en")
    assert result["status"] == "failed"

def test_very_short_text():
    """Valider texte trop court."""
    result = provider._analyze_textblob("OK", "en")
    # Doit fonctionner mais avec confiance faible
    assert result["status"] == "computed"

def test_unsupported_language():
    """Valider langue non supportée."""
    result = await provider.analyze_sentiment(
        "日本語のテキスト",
        language="ja"
    )
    assert result["status"] == "unsupported_lang"

def test_mixed_language():
    """Valider texte multilingue."""
    result = provider._analyze_textblob(
        "This is great! C'est génial!",
        language="en"  # Langue dominante
    )
    assert result["status"] == "computed"
```

**Résultat attendu** : 15+ tests unitaires, couverture >90%

---

## 2️⃣ Validation Service (Orchestration)

### 2.1 Tests Orchestration Langue + Sentiment

**Fichier**: `tests/unit/test_sentiment_service.py`

```python
def test_service_auto_detect_language():
    """Valider détection automatique de langue."""
    service = SentimentService()

    result = service.enrich_expression_sentiment(
        readable="Ceci est un texte en français très positif.",
        language=None  # Pas de langue fournie
    )

    # Doit détecter FR et analyser
    assert result["sentiment_status"] == "computed"
    assert result["sentiment_label"] == "positive"

def test_service_prefers_readable_over_content():
    """Valider priorité readable vs content."""
    service = SentimentService()

    result = service.enrich_expression_sentiment(
        content="<html><body>Neutral HTML</body></html>",
        readable="This is a very positive article!",  # Priorité
        language="en"
    )

    # Doit analyser le readable, pas le HTML
    assert result["sentiment_label"] == "positive"

def test_service_fallback_to_content():
    """Valider fallback sur content si pas de readable."""
    result = service.enrich_expression_sentiment(
        content="This is great content!",
        readable=None,
        language="en"
    )

    assert result["sentiment_status"] == "computed"
    assert result["sentiment_label"] == "positive"
```

### 2.2 Tests Seuils de Confiance

```python
def test_low_confidence_flagging(monkeypatch):
    """Valider flag low_confidence si score faible."""
    service = SentimentService()

    # Mock provider pour retourner confiance < 0.5
    def mock_analyze(text, lang):
        return {
            "score": 0.1,
            "label": "neutral",
            "confidence": 0.4,  # < seuil 0.5
            "status": "computed",
            "model": "textblob"
        }

    monkeypatch.setattr(
        service.provider,
        "_analyze_textblob",
        mock_analyze
    )

    result = service.enrich_expression_sentiment(
        readable="Some text",
        language="en"
    )

    assert result["sentiment_status"] == "low_confidence"
    assert result["sentiment_score"] == 0.1  # Score gardé
```

**Résultat attendu** : 10+ tests service, logique orchestration validée

---

## 3️⃣ Validation End-to-End (Intégration)

### 3.1 Tests Crawlers avec Sentiment

**Fichier**: `tests/integration/test_crawler_sentiment.py`

```python
@pytest.mark.asyncio
async def test_async_crawler_adds_sentiment(db_session, test_land):
    """Valider crawler async enrichit sentiment."""
    crawler = AsyncCrawlerEngine(db_session=db_session)

    # Crawl URL avec contenu positif connu
    test_url = "https://httpbin.org/html"  # Contenu neutre

    await crawler.crawl_url(
        test_url,
        land_id=test_land.id,
        llm_validation=False  # TextBlob
    )

    # Vérifier expression en DB
    expr = db_session.query(Expression)\
        .filter_by(url=test_url)\
        .first()

    assert expr is not None
    assert expr.sentiment_score is not None
    assert expr.sentiment_label in ["positive", "neutral", "negative"]
    assert expr.sentiment_model == "textblob"
    assert expr.sentiment_computed_at is not None

@pytest.mark.asyncio
async def test_async_crawler_llm_sentiment(db_session, test_land):
    """Valider crawler async avec LLM sentiment."""
    if not settings.OPENROUTER_API_KEY:
        pytest.skip("No API key")

    crawler = AsyncCrawlerEngine(db_session=db_session)

    await crawler.crawl_url(
        "https://example.com",
        land_id=test_land.id,
        llm_validation=True  # LLM
    )

    expr = db_session.query(Expression).first()
    assert "llm/" in expr.sentiment_model
```

### 3.2 Tests Double Crawler (Sync vs Async)

```python
def test_sync_async_parity(db_session, test_land):
    """Valider parité sentiment sync vs async."""
    test_url = "https://httpbin.org/html"

    # Crawl sync
    sync_crawler = SyncCrawlerEngine(db_session=db_session)
    sync_crawler.crawl_url(test_url, test_land.id, llm_validation=False)
    sync_expr = db_session.query(Expression)\
        .filter_by(url=test_url)\
        .first()

    # Nettoyage
    db_session.delete(sync_expr)
    db_session.commit()

    # Crawl async
    async_crawler = AsyncCrawlerEngine(db_session=db_session)
    asyncio.run(async_crawler.crawl_url(
        test_url, test_land.id, llm_validation=False
    ))
    async_expr = db_session.query(Expression)\
        .filter_by(url=test_url)\
        .first()

    # Comparer résultats (doivent être très proches)
    assert sync_expr.sentiment_label == async_expr.sentiment_label
    assert abs(sync_expr.sentiment_score - async_expr.sentiment_score) < 0.1
    assert sync_expr.sentiment_model == async_expr.sentiment_model
```

**Résultat attendu** : 5+ tests intégration, parité crawlers validée

---

## 4️⃣ Validation A/B Testing (Comparaison Méthodes)

### 4.1 Comparaison TextBlob vs LLM sur Corpus

**Script**: `tests/validation/compare_sentiment_methods.py`

```python
import json
from app.core.sentiment_provider import SentimentModelProvider

async def compare_methods_on_corpus():
    """Compare TextBlob vs LLM sur corpus annoté."""

    # Charger corpus
    with open("tests/data/sentiment_corpus.json") as f:
        corpus = json.load(f)

    provider = SentimentModelProvider()
    results = {
        "textblob": {"correct": 0, "total": 0},
        "llm": {"correct": 0, "total": 0}
    }

    for item in corpus:
        text = item["text_snippet"]
        expected_label = item["manual_label"]

        # TextBlob
        tb_result = provider._analyze_textblob(text, "en")
        if tb_result["label"] == expected_label:
            results["textblob"]["correct"] += 1
        results["textblob"]["total"] += 1

        # LLM
        llm_result = await provider._analyze_openrouter(text, "en")
        if llm_result["label"] == expected_label:
            results["llm"]["correct"] += 1
        results["llm"]["total"] += 1

    # Calculer précision
    tb_accuracy = results["textblob"]["correct"] / results["textblob"]["total"]
    llm_accuracy = results["llm"]["correct"] / results["llm"]["total"]

    print(f"TextBlob Accuracy: {tb_accuracy:.2%}")
    print(f"LLM Accuracy: {llm_accuracy:.2%}")

    # Assertions
    assert tb_accuracy > 0.65  # TextBlob doit être >65%
    assert llm_accuracy > 0.85  # LLM doit être >85%
    assert llm_accuracy > tb_accuracy  # LLM meilleur que TextBlob
```

### 4.2 Analyse des Désaccords

```python
def analyze_disagreements():
    """Analyser cas où TextBlob et LLM divergent."""

    disagreements = []

    for item in corpus:
        tb_result = provider._analyze_textblob(item["text_snippet"], "en")
        llm_result = await provider._analyze_openrouter(item["text_snippet"], "en")

        if tb_result["label"] != llm_result["label"]:
            disagreements.append({
                "text": item["text_snippet"][:100],
                "textblob": tb_result["label"],
                "llm": llm_result["label"],
                "manual": item["manual_label"]
            })

    # Afficher désaccords pour analyse humaine
    print(f"\n{len(disagreements)} désaccords trouvés:")
    for d in disagreements[:10]:  # Top 10
        print(f"\nText: {d['text']}")
        print(f"  TextBlob: {d['textblob']} | LLM: {d['llm']} | Human: {d['manual']}")
```

**Résultat attendu** :
- TextBlob précision : 65-75%
- LLM précision : 85-95%
- Désaccords < 20% du corpus

---

## 5️⃣ Validation Métier (Annotation Humaine)

### 5.1 Constitution du Corpus Annoté

**Processus** :

1. **Sélectionner 60 expressions** (30 FR + 30 EN)
   ```sql
   -- Échantillon stratifié
   SELECT id, url, title, readable, lang
   FROM expressions
   WHERE readable IS NOT NULL
     AND word_count BETWEEN 100 AND 500
     AND lang IN ('fr', 'en')
   ORDER BY RANDOM()
   LIMIT 60;
   ```

2. **Annoter manuellement**
   - 2 annotateurs indépendants
   - Étiquettes : positive / neutral / negative
   - Score cible : -1.0 à +1.0
   - Niveau confiance : high / medium / low

3. **Format du corpus** (`sentiment_corpus.json`) :
   ```json
   [
     {
       "expression_id": 12345,
       "url": "https://example.com/article",
       "text_snippet": "First 200 chars of readable content...",
       "full_text_hash": "sha256...",
       "manual_label": "positive",
       "manual_score": 0.75,
       "annotator_1": "positive",
       "annotator_2": "positive",
       "agreement": true,
       "annotator_confidence": "high",
       "language": "fr",
       "word_count": 250,
       "notes": "Article élogieux sur politique climat"
     }
   ]
   ```

### 5.2 Métriques de Qualité

**Inter-annotator Agreement** :
```python
def calculate_agreement(corpus):
    """Calculer accord inter-annotateurs (Cohen's Kappa)."""
    from sklearn.metrics import cohen_kappa_score

    labels_1 = [item["annotator_1"] for item in corpus]
    labels_2 = [item["annotator_2"] for item in corpus]

    kappa = cohen_kappa_score(labels_1, labels_2)

    # Kappa > 0.6 = accord substantiel
    assert kappa > 0.6, f"Faible accord: {kappa:.2f}"

    return kappa
```

**Validation contre Corpus** :
```python
def validate_against_gold_standard():
    """Valider système contre gold standard."""
    from sklearn.metrics import classification_report, confusion_matrix

    # Prédictions système
    y_true = [item["manual_label"] for item in corpus]
    y_pred_tb = [textblob_analyze(item["full_text"])["label"] for item in corpus]
    y_pred_llm = [await llm_analyze(item["full_text"])["label"] for item in corpus]

    # Rapports détaillés
    print("TextBlob Performance:")
    print(classification_report(y_true, y_pred_tb))

    print("\nLLM Performance:")
    print(classification_report(y_true, y_pred_llm))

    # Confusion matrix
    print("\nTextBlob Confusion Matrix:")
    print(confusion_matrix(y_true, y_pred_tb))
```

**Métriques attendues** :
- **Precision** (positive) : >70% (TextBlob), >90% (LLM)
- **Recall** (positive) : >65% (TextBlob), >85% (LLM)
- **F1-score** : >68% (TextBlob), >87% (LLM)

---

## 📋 Checklist Validation Complète

### Phase 1 : Tests Automatisés ✅

- [ ] Tests unitaires `SentimentModelProvider` (15+ tests)
- [ ] Tests unitaires `SentimentService` (10+ tests)
- [ ] Tests intégration crawler async (3+ tests)
- [ ] Tests intégration crawler sync (3+ tests)
- [ ] Tests parité sync/async (1 test)
- [ ] Couverture code >85%

**Commande** :
```bash
pytest tests/unit/test_sentiment_*.py -v --cov=app.core.sentiment_provider --cov=app.services.sentiment_service
```

### Phase 2 : Corpus Annoté 📝

- [ ] Sélectionner 60 expressions (30 FR + 30 EN)
- [ ] Annotation annotateur 1
- [ ] Annotation annotateur 2
- [ ] Calcul inter-rater agreement (Kappa >0.6)
- [ ] Résolution désaccords
- [ ] Export `sentiment_corpus.json`

### Phase 3 : Validation Métier 🎯

- [ ] A/B test TextBlob vs LLM sur corpus
- [ ] Analyse désaccords (manuel)
- [ ] Validation métriques (precision, recall, F1)
- [ ] Rapport comparatif TextBlob vs LLM
- [ ] Décision finale : TextBlob acceptable ? (si >65% précision)

### Phase 4 : Tests Production 🚀

- [ ] Crawl test sur 10 lands échantillon
- [ ] Vérification sentiment en DB (non-null)
- [ ] Vérification distribution (30% pos, 50% neut, 20% neg attendu)
- [ ] Vérification latence (<100ms TextBlob, <2s LLM)
- [ ] Smoke test post-déploiement

---

## 🎯 Critères de Succès

### Critères Techniques

| Critère | TextBlob | LLM |
|---------|----------|-----|
| **Latence moyenne** | <100ms | <2s |
| **Taux erreur** | <5% | <2% |
| **Taux null** | <10% | <5% |
| **Couverture tests** | >85% | >85% |

### Critères Qualité

| Métrique | TextBlob (Min) | LLM (Min) |
|----------|----------------|-----------|
| **Précision globale** | 65% | 85% |
| **Précision positive** | 70% | 90% |
| **Précision négative** | 70% | 90% |
| **Recall positive** | 65% | 85% |
| **F1-score** | 68% | 87% |

### Critères Métier

- **Cohérence** : Sentiment similaire pour contenus similaires
- **Stabilité** : Même texte → même sentiment (reproductibilité)
- **Explicabilité** : Pouvoir expliquer pourquoi un sentiment a été attribué
- **Utilité** : Les utilisateurs trouvent le sentiment pertinent

---

## 📊 Rapports de Validation

### Template Rapport Final

```markdown
# Rapport de Validation Sentiment Analysis

## Résumé Exécutif
- Date validation : [DATE]
- Corpus : 60 expressions (30 FR, 30 EN)
- Méthodes testées : TextBlob, OpenRouter LLM

## Résultats TextBlob
- Précision : XX%
- Recall : XX%
- F1-score : XX%
- Latence moyenne : XXms

## Résultats LLM
- Précision : XX%
- Recall : XX%
- F1-score : XX%
- Latence moyenne : XXms

## Comparaison
- Gain qualité LLM vs TextBlob : +XX%
- Surcoût latence : +XXms
- Coût supplémentaire : XX€/1000 analyses

## Recommandation
[TextBlob acceptable / LLM requis / Hybride optimal]

## Annexes
- Corpus annoté
- Matrice de confusion
- Exemples désaccords
```

---

## 🔄 Processus de Validation Continue

### Monitoring Post-Déploiement

```python
# Métriques à tracker (Prometheus)
sentiment_distribution = Histogram(
    'sentiment_score_distribution',
    'Distribution des scores sentiment'
)

sentiment_null_rate = Gauge(
    'sentiment_null_rate',
    'Taux de sentiment NULL'
)

sentiment_method_usage = Counter(
    'sentiment_method_total',
    'Usage TextBlob vs LLM',
    ['method']  # textblob ou llm
)
```

### Validation Hebdomadaire

1. **Échantillonner 10 expressions au hasard**
2. **Review manuelle** : sentiment correct ?
3. **Tracer dérive** : précision baisse ?
4. **Ajuster seuils** si nécessaire

---

**Dernière mise à jour** : 18 octobre 2025
**Version** : 1.0
**Auteur** : Assistant AI (Claude)
