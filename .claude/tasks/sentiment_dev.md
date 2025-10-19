# Développement — Pipeline Sentiment (V2 Sync)

## 1. Objectif
Intégrer l'analyse de sentiment dans MyWebIntelligence en s'appuyant sur **un seul moteur de crawl synchrone**. Le service doit enrichir les expressions avec :

- `sentiment_score` (float)
- `sentiment_label` (positive/neutral/negative)
- `sentiment_confidence`
- `sentiment_status`
- `sentiment_model`
- `sentiment_computed_at`

## 2. Architecture retenue
1. `app/services/sentiment_service.py`
   - Récupère le contenu brut/readable.
   - Détecte la langue via `text_utils.detect_language`.
   - Choisit le moteur : TextBlob ou LLM (OpenRouter) selon configuration.
   - Retourne un dictionnaire normalisé.
2. `crawler_engine_sync.py`
   - Après extraction contenu + métadonnées, invoque `SentimentService`.
   - Persiste le résultat sur l'objet `Expression`.
3. `app/api/v2/expressions.py`
   - Expose les champs sentiment dans les schémas réponse.
4. Jobs de retraitement : `scripts/reprocess_sentiment.py` pour rejouer l'enrichissement.

## 3. Étapes projet
### 3.1 Service sentiment
- Implémenter la classe `SentimentService` avec méthodes :
  - `enrich_expression_sentiment(content, readable, language, use_llm=False)`
  - `_analyze_textblob(text, language)`
  - `_analyze_openrouter(text, language)`
- Gestion des erreurs : retourner `sentiment_status="failed"` et logger l'exception.
- Paramètres dans `app/config.py` :
  ```python
  ENABLE_SENTIMENT_ANALYSIS: bool = True
  SENTIMENT_MIN_CONFIDENCE: float = 0.5
  SENTIMENT_SUPPORTED_LANGUAGES: str = "fr,en"
  ```

### 3.2 Intégration moteur de crawl
- Dans `SyncCrawlerEngine._process_expression` :
  ```python
  if settings.ENABLE_SENTIMENT_ANALYSIS:
      sentiment = sentiment_service.enrich_expression_sentiment(
          content=expression.content,
          readable=expression.readable,
          language=expression.lang,
          use_llm=llm_validation and settings.OPENROUTER_ENABLED,
      )
      expression.sentiment_score = sentiment["sentiment_score"]
      expression.sentiment_label = sentiment["sentiment_label"]
      expression.sentiment_confidence = sentiment["sentiment_confidence"]
      expression.sentiment_status = sentiment["sentiment_status"]
      expression.sentiment_model = sentiment["sentiment_model"]
      expression.sentiment_computed_at = sentiment["sentiment_computed_at"]
  ```
- Journaliser le statut final (`logger.debug`).

### 3.3 API & modèles
- Étendre `ExpressionOut` (schéma réponse) pour inclure les champs sentiment.
- Mettre à jour `app/db/models.py` si colonnes manquantes (type `Numeric`, `String`, `DateTime`).
- Ajouter migrations Alembic correspondantes.

### 3.4 Tests
- Tests unitaires `tests/unit/test_sentiment_service.py` couvrant :
  - texte en français / anglais / langage non supporté.
  - absence de contenu.
  - erreur provider (retour statut failed).
- Tests d'intégration `tests/integration/test_crawler_sentiment.py` :
  - lancer `SyncCrawlerEngine` sur une expression de démonstration et vérifier la persistance des champs.
- Script CLI : `tests/test-crawl-sentiment.sh` pour fumée manuelle.

## 4. Monitoring
- Logs niveau INFO pendant le traitement sentiment (langue détectée, moteur utilisé, statut).
- Métriques Prometheus :
  - `sentiment_enrichment_total{status=...}`
  - `sentiment_enrichment_duration_seconds`
- Table `sentiment_events` (optionnel) pour tracer les erreurs critiques.

## 5. Checklists
### Avant merge
- [ ] `SentimentService` couvert par tests unitaires.
- [ ] `SyncCrawlerEngine` enrichit correctement les champs.
- [ ] Migration Alembic exécutée localement (`alembic upgrade head`).
- [ ] API v2 retourne les champs sentiment.

### Après déploiement
- [ ] Rejouer `scripts/reprocess_sentiment.py --land <id>` sur un lot représentatif.
- [ ] Vérifier la distribution des labels via SQL :
  ```sql
  SELECT sentiment_label, COUNT(*) FROM expressions
  WHERE sentiment_status = 'computed'
  GROUP BY sentiment_label;
  ```
- [ ] Surveiller les logs d'erreur pendant 48h.

## 6. Points d'attention
- Ne jamais re-introduire de moteur parallèle : tout tourne dans la boucle synchrone.
- Le flag `llm_validation` déclenche seulement l'utilisation du LLM dans le moteur unique.
- Prévoir un fallback francophone lorsque la détection de langue échoue (`sentiment_status="unsupported_lang"`).
- Documenter tout nouveau script ou endpoint dans `.claude/docs/SENTIMENT_IMPLEMENTATION_SUMMARY.md`.

