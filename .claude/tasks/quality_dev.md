# Développement — Score Qualité (V2 Sync)

## 1. Objectif
Calculer et stocker un score qualité pour chaque expression à partir des données récupérées par le crawler synchrone.

## 2. Architecture Fonctionnelle
1. `app/services/quality_service.py`
   - Calcule le score à partir des signaux : longueur, lisibilité, ratio médias, statut HTTP, fraîcheur.
   - Fournit un résultat normalisé (`score`, `label`, `confidence`, `details`).
2. `crawler_engine_sync.py`
   - Après enrichissement readable, appelle `QualityService` et persiste le résultat.
3. API & Reporting
   - Champs exposés : `quality_score`, `quality_label`, `quality_status`, `quality_details`.
   - Endpoint de filtrage : `GET /api/v2/lands/{id}/expressions?quality[min]=...`.
4. Scripts back-office
   - `scripts/recompute_quality.py` pour recalcul global.

## 3. Étapes projet
### 3.1 Service qualité
- Méthode principale `evaluate(expression)` retournant un `QualityResult` dataclass.
- Facteurs :
  - `readable_word_count`
  - `media_count`
  - `http_status`
  - `language`
  - détection spam (`quality_utils.detect_spam`).
- Paramètres dans `config.py` :
  ```python
  ENABLE_QUALITY_ANALYSIS: bool = True
  QUALITY_MIN_WORDS: int = 120
  QUALITY_MEDIA_RATIO_MIN: float = 0.1
  ```

### 3.2 Intégration crawler
```python
if settings.ENABLE_QUALITY_ANALYSIS:
    quality = quality_service.evaluate(expression)
    expression.quality_score = quality.score
    expression.quality_label = quality.label
    expression.quality_status = quality.status
    expression.quality_details = quality.details
```
- Ajouter logs `logger.debug("quality", extra=...)`.

### 3.3 API / DB
- Colonnes supplémentaires si nécessaire (`quality_score` Numeric, `quality_label` String, etc.).
- Mise à jour des schémas FastAPI (`ExpressionOut`, `QualityMetrics`).
- Migrations Alembic.

### 3.4 Tests
- Tests unitaires sur `QualityService` (cas content riche / pauvre / spam / erreurs HTTP).
- Tests d'intégration sur `SyncCrawlerEngine` pour vérifier la persistance.
- Script fumée `tests/test-crawl-quality.sh`.

## 4. Observabilité
- Métrique Prometheus `quality_enrichment_total` par statut (computed, skipped, error).
- Histogramme `quality_enrichment_duration_seconds`.
- Logs JSON : score final, seuils appliqués.

## 5. Checklist
- [ ] Service qualité testé et documenté.
- [ ] Intégration dans le moteur unique validée par tests d'intégration.
- [ ] API expose les nouveaux champs et la documentation est mise à jour.
- [ ] Script de recalcul global exécuté sur préproduction.

## 6. Points de vigilance
- Jamais de dépendance à un moteur parallèle : toute logique doit fonctionner dans la boucle synchrone.
- Ne pas recalculer la qualité si `quality_status="locked"` (cas de corrections manuelles).
- Prévoir un fallback neutre en cas d'erreur (score `None`, statut `failed`).
- Documenter les règles métiers dans `.claude/docs/QUALITY_SCORE_GUIDE.md`.

