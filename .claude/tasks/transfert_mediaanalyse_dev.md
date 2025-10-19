# Plan de suivi — Pipeline MediaAnalyse (legacy → API)

## 1. Contexte & objectifs
- Le legacy fournit la commande `land medianalyse` qui traite toutes les entrées `media` d’un land via `core.medianalyse_land` (MediaAnalyzer, filtres dimension/poids, mise à jour DB).
- L’API moderne expose un endpoint `POST /lands/{id}/medianalyse` (v1/v2) qui déclenche la tâche Celery `analyze_land_media_task`.
- Le transfert est bien avancé : logique Celery, filtrage SQL, extraction via `MediaProcessor` sont déjà en place. **Objectif final** : assurer la parité totale, améliorer la robustesse et consolider le pipeline (observabilité, export, docs).

## 2. Héritage legacy assuré
- **Séléction médias** : jointure `Media`→`Expression`, filtres `depth`, `relevance`, `limit` (legacy). L’API reprend depth/minrel.
- **Analyse** : MediaAnalyzer (legacy) vs `MediaProcessor` (API) → extraction dimensions, format, EXIF, couleurs, perceptual hash.
- **Mise à jour DB** : champs media (width, height, dominant_colors, hash, is_processed, analyzed_at, etc.).
- **Workflow** : CLI -> boucle sync, API -> Celery async (batch + group tasks).
- **Journalisation** : logs `MEDIA ANALYSIS STARTED/COMPLETED`, stats (analysed/failed).
- **Tâche Celery** : `analyze_land_media_task` déjà implémentée.

## 3. État API actuel (2025-10)
- Endpoint v1/v2 : `land medianalyse` → create job (`media_analysis`), lance `analyze_land_media_task`.
- Service interne : `media_analysis_task.py` gère:
  - Sélection expressions (SQL brut).
  - Sélection médias non traités (`type='IMAGE'`, `is_processed` false/null).
  - Traitement direct < batch_size, sinon sous-tâches Celery groupées.
  - Mise à jour job + logs + result data.
- `MediaProcessor` (`app/core/media_processor.py`) gère téléchargement via httpx, validations, extraction PIL/sklearn.
- Observabilité partielle : logs, résultat job. Pas de métriques Prometheus ni WebSocket de progression (à vérifier).
- Exports : `ExportService` prend en compte `media` (à confirmer pour champs analytiques).
- Documentation : README/API mentionne le pipeline, mais pas de guide dédié.

## 4. Parité vs legacy
| Aspect | Legacy | API | Statut |
|--------|--------|-----|--------|
| Commande déclenchement | CLI sync | Endpoint + Celery | ✅ (amélioré) |
| Filtres | depth, minrel | depth, minrel | ✅ |
| Type média | Tous (legacy) | Filtre `type='IMAGE'` | 🟡 (à confirmer) |
| Re-analyses | Toujours (legacy) | `is_processed` False | ✅ (respect DB flag) |
| Analyse | MediaAnalyzer (aiohttp) | MediaProcessor (httpx) | 🟡 (assurer feature parity) |
| Stats retour | processed_count | result dict (analyzed, failed) | ✅ |
| Logs | stdout | logging + job result | ✅ |
| CLI feedback | Console | API JSON / Celery job | ✅ |
| Tests | manuels | partiels (à compléter) | 🟡 |

## 5. Travaux restants
1. **Parité extraction** :
   - **Critique** : Vérifier que MediaProcessor couvre toutes les features legacy (EXIF, dominant colors, perceptual hash : pHash, dHash, cHash).
   - Confirmer que les filtres min_width/min_height/max_file_size sont appliqués (config).
   - Ajouter support pour autres types (`VIDEO`, `AUDIO`) si legacy le faisait (legacy mentionne images surtout).
2. **Observabilité / UX** :
   - **Critique** : Ajouter WebSocket progress (via `websocket_manager`) pour le suivi en temps réel.
   - Exposer métriques Prometheus (`media_analysis_processed_total`, `media_analysis_failures_total`).
   - Inclure success_rate dans job.result.
3. **Exports & consumers** :
   - Confirmer que `ExportService` fait remonter les champs (dimensions, couleurs).
   - Doc pour data analysts (colonne `media` dans CSV/GEXF).
4. **Tests** :
   - Tests unitaires MediaProcessor avec fixtures (images valides, corrompues, trop lourdes).
   - Tests d’intégration : pipeline complet, assertions sur base (`is_processed`, `analyzed_at`).
   - Tests Celery group (multi batch).
5. **Documentation** :
   - Ajouter `.claude/docs/MEDIA_ANALYSIS_GUIDE.md` (déjà existant ? à vérifier).
   - Mettre à jour `.claude/INDEX_DOCUMENTATION.md`, README (workflow, params depth/minrel/batch).
6. **Robustesse & Configuration** :
   - **Nouveau** : Centraliser la configuration (`MEDIA_ANALYSIS_TIMEOUT`, `MEDIA_ANALYSIS_MAX_FILE_SIZE`, etc.) dans `app/config.py`.
   - **Nouveau** : Implémenter une logique de retries avec backoff exponentiel dans `MediaProcessor` pour les erreurs réseau (429, 503).
7. **Outils Développeur** :
   - **Nouveau** : Créer un script de reprocessing `scripts/reprocess_media.py` avec options `--land-id`, `--force`, `--dry-run`.

## 6. Backlog résiduel
| ID | Catégorie | Description | Livrable | Owner |
|----|-----------|-------------|----------|-------|
| MA-01 | Vérif | Audit parité MediaProcessor vs MediaAnalyzer legacy | Rapport | Tech Lead |
| MA-02 | Core | Implémenter les filtres de configuration (taille, dimensions) et la logique de retries. | `MediaProcessor` mis à jour | Dev A |
| MA-03 | Core | Ajouter le support multi-type (VIDEO, AUDIO) si pertinent. | Implémentation | Dev A |
| MA-04 | Observabilité | Intégrer WebSocket progress et métriques Prometheus. | Code + Dashboard | DevOps |
| MA-05 | Exports | Confirmer l'export des champs média (dimensions, couleurs, hash) dans les CSV/GEXF. | Tests + code | Dev B |
| MA-06 | Tests | Créer une suite de tests unitaires et d'intégration complète pour `MediaProcessor` et la tâche Celery. | Fichiers de test | QA |
| MA-07 | Outils | Créer le script de reprocessing `scripts/reprocess_media.py`. | Script Python | Dev B |
| MA-08 | Docs | Rédiger le guide `MEDIA_ANALYSIS_GUIDE.md` et mettre à jour la documentation existante. | Documentation | Tech Writer |

## 7. Critères d’acceptation finaux
- `POST /lands/{id}/medianalyse` → job Celery, logs, result complet (analyzed, failed, success_rate).
- MediaProcessor supporte dimensions, format, EXIF, couleurs, perceptual hash comme legacy.
- **Les filtres de configuration (taille, dimensions) sont fonctionnels.**
- Exports contiennent champs analytiques.
- Tests (unitaires + intégration) validés.
- Docs + monitoring à jour.

## 8. Risques & mitigations
- **Volume média important** : batch + group tasks déjà en place; surveiller limites concurrency httpx.
- **Type non supporté** : fallback/skip loggés; config pour activer/désactiver.
- **Resources CPU** : analyser usage PIL/sklearn (option de downscale).
- **Double crawler** : Non concerné directement pour l'analyse, mais **critique pour la création des entrées `Media`**. S'assurer que `crawler_engine.py` et `crawler_engine_sync.py` créent les enregistrements `Media` de manière identique.

## 9. Prochaines étapes
1. Conduire l’audit parité (MA-01) et lister gaps.
2. Prioriser MA-02, MA-04, MA-06 (robustesse, observabilité, tests).
3. Documenter le pipeline final (MA-08) avant la release.
