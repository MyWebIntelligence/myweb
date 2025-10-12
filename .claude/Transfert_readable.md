# Audit transfert du pipeline "readable"

## Portée
- Legacy : `MyWebIntelligenceAPI/_legacy/readable_pipeline.py`
- Nouvelle API : `MyWebIntelligenceAPI/app/services/readable_service.py`, `readable_simple_service.py`, `readable_celery_service.py`, `app/core/content_extractor.py`, `app/services/media_link_extractor.py`

## Synthèse
- La version API remplace Mercury Parser par un extracteur maison basé sur Trafilatura, ce qui supprime plusieurs métadonnées et formats indispensables (markdown lisible, médias structurés, retries, paramètres CLI).
- Les services « simple » et Celery ne répliquent pas les étapes critiques du legacy (recalcul de pertinence, liens/médias, validation LLM), créant des régressions fonctionnelles selon le chemin d’exécution.
- L’intégration Wayback et la génération de statistiques sont incomplètes (fallback moins robuste, compteur erroné, absence de success rate, pas de création automatique de nouvelles expressions depuis les liens).

## Écarts détaillés

### 1. Extraction de contenu et format
- **Perte du moteur Mercury** : le legacy exécute Mercury CLI avec retries exponentiels et récupération du JSON complet (`_run_mercury`, lignes 418‑518) tandis que la nouvelle version s’appuie sur `ContentExtractor.get_readable_content_with_fallbacks` (`app/core/content_extractor.py:137-187`) sans retries ni CLI configurable (`mercury_path`, `max_retries` disparaissent).
- **Markdown vs texte brut** : Mercury produisait un markdown propre stocké dans `expression.readable` (`_prepare_expression_update`, lignes 555‑643). Le nouvel extracteur retourne du texte brut Trafilatura (`ExtractionResult.readable`, `readable_service.py:301-307`), ce qui empêche la détection des images/liens markdown par `MediaLinkExtractor`.
- **Métadonnées manquantes** : les champs Mercury (`lead_image_url`, `excerpt`, `direction`, `media`, `links`, `raw_response`) ne sont plus exposés. L’API n’écrit plus de metadonnées supplémentaires (et ne stocke pas l’HTML d’origine `expression.content`).
- **Pas de différentiation d’auteur/word_count** : la nouvelle extraction ne renseigne jamais `author`, `word_count`, `keywords`, etc., qui demeurent possibles dans Mercury.

### 2. Fallback Wayback / Archive
- Legacy : `_extract_with_mercury` appelle `_fetch_wayback_first_snapshot` (lignes 320‑412) qui interroge le CDX API avec filtre `statuscode:200`, choisit la première capture disponible et relance Mercury.
- Nouvelle version : `ContentExtractor._extract_from_archive_org` (`content_extractor.py:189-214`) utilise `archive.org/wayback/available` et la capture « closest » sans vérifier le statut HTTP ni garantir la plus ancienne snapshot.
- **Compteur Wayback erroné** : `ReadableService._process_single_expression` marque `wayback_used = 1 if extraction_result.extraction_source == 'archive' else 0` (`readable_service.py:247-260`), alors que l’extracteur renvoie `archive_org`. Le compteur reste 0.
- Pas de propagation d’informations Wayback (timestamp, URL d’archive) vers la base, contrairement à `wayback_result.raw_response` dans le legacy.

### 3. Gestion des médias et des liens
- Legacy : 
  - Extraction structurée via `_extract_media_and_links` (lignes 522‑567) puis enrichissement des médias/links à partir du markdown final (`_extract_media_from_markdown`, `_extract_links_from_markdown`).
  - Création d’expressions cibles via `_get_or_create_expression` et `core.add_expression` (lignes 858‑908) pour tout lien nouveau après vérification `is_crawlable`.
- Nouvelle API :
  - `MediaLinkExtractor.process_expression_media_and_links` (`media_link_extractor.py:254-312`) ne traite que du markdown ; avec un `readable` en texte brut, très peu de médias/liens sont détectés.
  - Les vidéos/medias fournis par Mercury (`data['videos']`) ne sont plus disponibles.
  - Aucun mécanisme pour créer automatiquement une nouvelle `Expression` lorsque la cible n’existe pas ; on se contente de logguer puis d’ignorer (`media_link_extractor.py:282-305`).
  - `ReadableSimpleService` et `ReadableCeleryService` sautent totalement l’étape médias/liens (retours forcés à 0, cf. `readable_simple_service.py:142-151`, `readable_celery_service.py:132-141`).

### 4. Pertinence et validation LLM
- Legacy : recalcul de la pertinence via `_calculate_relevance` + garde-fou LLM (`_apply_updates`, lignes 788‑845) sur chaque mise à jour.
- `ReadableService` (chemin « complet ») recalcule bien via `TextProcessorService` et déclenche `LLMValidationService` (`readable_service.py:243-251 & 398-454`).
- **Régression sur services parallèles** :
  - `ReadableSimpleService` et `ReadableCeleryService` n’appellent ni recalcul de pertinence ni validation LLM : `update_expression_readable_simple` se contente de patcher les champs (`readable_simple_service.py:120-160`), et `readable_celery_service.py` applique le même raccourci (`readable_celery_service.py:111-150`).
  - Pas de mise à jour d’`approved_at`, `relevance`, `valid_llm` pour ces chemins, contrairement au legacy.

### 5. Stratégies de fusion et profondeur
- Legacy applique `prefer_earlier_datetime` pour gérer les dates et supporte les trois stratégies (`_apply_merge_strategy`, lignes 643‑728).
- L’API reprend la logique, mais uniquement pour les champs gérés ; aucun support pour des champs additionnels (ex. `keywords`), et la fusion est dupliquée dans trois services, ce qui augmente le risque d’incohérence (cf. `readable_service.py:330-370`, `readable_simple_service.py:206-259`, `readable_celery_service.py:170-231`).
- Filtrage par profondeur : le legacy ne traite que la profondeur exacte demandée (`depth == n`, lignes 184‑214), la nouvelle version traite toutes les expressions ≤ `depth` (`readable_service.py:64-83`), modifiant le périmètre de traitement.

### 6. Statistiques et instrumentation
- Legacy maintient `self.stats` avec `success_rate` renvoyé par `_get_pipeline_stats` (lignes 914‑948).
- API : `ReadableProcessingResult` ne calcule pas de taux de succès et mélange les compteurs en fin de batch (`readable_service.py:176-198`). Aucun équivalent pour suivre `skipped` distinctement ni trace des erreurs Wayback.

## Recommandations prioritaires
1. Réintroduire un extracteur fournissant Markdown structuré + métadonnées Mercury (ou équivalent) et restaurer la logique de retries/CLI configurable.
2. Aligner le fallback Wayback sur le legacy (CDX API, statut 200, comptage correct, métadonnées stockées).
3. Porter l’extraction médias/liens complète (détection Markdown/HTML, création d’expressions cibles, vidéos) et l’activer dans tous les services.
4. Harmoniser les chemins `ReadableService`, `ReadableSimpleService`, `ReadableCeleryService` pour garantir recalcul de pertinence, `approved_at`, et validation LLM cohérente.
5. Compléter les statistiques retournées (success rate, erreurs, usage Wayback) pour faciliter le monitoring comme dans le pipeline historique.

le reste doit etre développé par la suite
