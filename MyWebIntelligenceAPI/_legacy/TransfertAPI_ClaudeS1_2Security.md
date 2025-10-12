# TransfertAPI Sprint 1-2 — Bilan & Sécurité

## État des livrables

- **Couche base de données**
  - ✅ Modèles `Paragraph` et `Similarity` complets avec index, contraintes et helpers `has_embedding`/`preview_text` (`MyWebIntelligenceAPI/app/db/models.py:290`).
  - ✅ Migration `001_add_paragraphs_and_similarities.py` crée tables, index et contraintes de cohérence prévues pour le sprint (`MyWebIntelligenceAPI/alembic/versions/001_add_paragraphs_and_similarities.py:1`).
  - ✅ Révision `002_add_embedding_indexes.py` ajoute les indexes partiels/GIN dédiés aux embeddings et active `pg_trgm` (`MyWebIntelligenceAPI/alembic/versions/002_add_embedding_indexes.py:1`).

- **Couche API**
  - ✅ Schémas Pydantic `Paragraph`/`Embedding` couvrent création, mise à jour, stats et traitements batch (`MyWebIntelligenceAPI/app/schemas/paragraph.py:1`, `MyWebIntelligenceAPI/app/schemas/embedding.py:1`).
  - ✅ Endpoints CRUD v1 disponibles avec contrôles d’accès (`MyWebIntelligenceAPI/app/api/v1/endpoints/paragraphs.py:1`, `MyWebIntelligenceAPI/app/api/v1/router.py:12`) en parallèle des routes avancées v2 (`MyWebIntelligenceAPI/app/api/v2/endpoints/paragraphs.py:25`).

- **Business logic**
  - ✅ CRUD paragraphe livré avec déduplication, création/bulk update et statistiques (`MyWebIntelligenceAPI/app/crud/crud_paragraph.py:1`).
  - ✅ `EmbeddingService` instancie le registre provider et force son initialisation avant chaque traitement (`MyWebIntelligenceAPI/app/services/embedding_service.py:26-110`).
  - ✅ `TextProcessorService` compose les champs `readable/content/summary/...` sans dépendre d’un attribut inexistant (`MyWebIntelligenceAPI/app/services/text_processor_service.py:196`).
  - ✅ Utilitaires NLP exposés dans `MyWebIntelligenceAPI/app/utils/text_utils.py:1`.

- **Architecture des providers**
  - ✅ Base abstraite et providers OpenAI/Mistral opérationnels (`MyWebIntelligenceAPI/app/core/embedding_providers/base_provider.py:1`, `.../openai_provider.py:1`, `.../mistral_provider.py:1`).
  - ✅ Registre centralisé avec auto-config via `_ensure_registry_initialized` (`MyWebIntelligenceAPI/app/core/embedding_providers/registry.py:19`, `MyWebIntelligenceAPI/app/services/embedding_service.py:29-34`).

- **Configuration**
  - ✅ `app/config.py` expose désormais les flags embeddings (provider par défaut, confirmation, overrides JSON) (`MyWebIntelligenceAPI/app/config.py:38`).
  - ✅ Module typed `app/core/settings.py` gère la validation/chargement des providers et résout les clés API (`MyWebIntelligenceAPI/app/core/settings.py:1`).

- **Tâches asynchrones**
  - ✅ `embedding_tasks.py` utilise `SessionLocal` du module sync (`MyWebIntelligenceAPI/app/tasks/embedding_tasks.py:1`, `MyWebIntelligenceAPI/app/db/session.py:23`) et orchestre extraction + génération.
  - ✅ `text_processing_tasks.py` ajouté pour couvrir extraction par expression et analyse de texte (`MyWebIntelligenceAPI/app/tasks/text_processing_tasks.py:1`, `MyWebIntelligenceAPI/app/tasks/__init__.py:1`).

- **Tests**
  - ⚠️ Premiers tests unitaires couvrent modèle `Paragraph` et configuration embeddings (`MyWebIntelligenceAPI/tests/unit/test_paragraph_model.py:1`, `MyWebIntelligenceAPI/tests/unit/test_embeddings_settings.py:1`) mais la couverture fonctionnelle reste minimale.

## Risques sécurité identifiés

- **Critique – Accès non authentifié aux paragraphes & embeddings**  
  Tous les endpoints v2 exposent la donnée brute et les actions Celery sans dépendance auth (`MyWebIntelligenceAPI/app/api/v2/endpoints/paragraphs.py:40-435`). Un appel anonyme peut lister/exporter des paragraphes et déclencher des traitements lourds.  
  ✅ _Action_ : ajouter `Depends(get_current_user)` + contrôle d’appartenance aux lands/expressions avant publication.

- **Critique – Exfiltration potentielle vers providers externes**  
  `generate_embeddings_for_land` et `generate_embeddings_batch` permettent à n’importe quel appelant de pousser l’intégralité du corpus vers OpenAI/Mistral (`MyWebIntelligenceAPI/app/api/v2/endpoints/paragraphs.py:278-356` couplé à `MyWebIntelligenceAPI/app/services/embedding_service.py:55-125`). Sans garde d’accès ni consentement, cela viole confidentialité et peut générer des coûts API.  
  ✅ _Action_ : exiger authentification, vérifier droits data owner, journaliser les consentements et prévoir un mode “stay on-prem”.

- **Élevé – Fuite d’informations internes via statut de tâche**  
  L’endpoint `/task/{task_id}/status` renvoie `str(result.info)` directement au client (`MyWebIntelligenceAPI/app/api/v2/endpoints/paragraphs.py:216-248`). En cas de crash, cela divulgue traces d’erreur, chemins locaux, voire messages des providers contenant des détails sensibles.  
  ✅ _Action_ : normaliser les erreurs retournées, filtrer les messages pour n’exposer qu’un code et une description générique.

- **Moyen – Déni de service par analyse de texte libre**  
  `analyze_text_content` accepte du texte non authentifié et effectue des calculs coûteux (`MyWebIntelligenceAPI/app/api/v2/endpoints/paragraphs.py:438-456`). Un attaquant peut envoyer des payloads volumineux pour épuiser CPU.  
  ⚠️ _Action_ : imposer authentification, réduire `max_length`, ajouter quotas/rate limiting. (Auth + limite renforcée implémentées, rate limiting restant à traiter.)

- **Moyen – Sessions Celery invalides**  
  `SessionLocal` est importée depuis un module inexistant et fermée avant retour (`MyWebIntelligenceAPI/app/tasks/embedding_tasks.py:11-24`). Les tâches plantent => perte de résilience, risque d’accumulation de jobs échoués.  
  ✅ _Action_ : créer un `SessionLocal` synchrone dédié ou réutiliser `AsyncSessionLocal` via context manager correct.

## Recommandations prioritaires

1. **Sécuriser immédiatement les endpoints v2** (auth + RBAC, limitation de périmètre, validation propriétaires).  
2. **Encadrer l’envoi de données vers OpenAI/Mistral** : règles de conformité, nettoyage étendu et possibilité d’opt-out.  
3. **Durcir la surface d’erreur** : wrapper les réponses Celery et normaliser les logs/retours client.  
4. **Corriger les intégrations bloquantes** (initialisation providers, sessions Celery, champ `expression.text`) avant d’ouvrir le sprint en production.  
5. **Compléter migrations/tests & documenter configuration** pour garantir reproductibilité et contrôle qualité.
