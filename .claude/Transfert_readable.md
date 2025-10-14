# Audit transfert du pipeline "readable" - MISE À JOUR

**Date de révision**: 17 octobre 2025
**Statut**: ✅ Écarts critiques corrigés (voir TRANSFERT_API_CRAWL.md)

---

## 🔄 Contexte

Ce document listait initialement les écarts entre le pipeline legacy et l'API. **Une partie importante de ces écarts a été corrigée** suite à l'audit détaillé du 17 octobre 2025.

**📚 Pour les corrections apportées**, consulter :
- [`.claude/TRANSFERT_API_CRAWL.md`](.claude/TRANSFERT_API_CRAWL.md) - Audit complet et corrections
- [`.claude/CORRECTIONS_PARITÉ_LEGACY.md`](.claude/CORRECTIONS_PARITÉ_LEGACY.md) - Détails techniques
- [`.claude/CHAÎNE_FALLBACKS.md`](.claude/CHAÎNE_FALLBACKS.md) - Pipeline d'extraction

---

## ✅ Écarts CORRIGÉS (17 octobre 2025)

### 1. ✅ Extraction de contenu et format
**Statut**: **RÉSOLU**

**Avant**:
- Trafilatura retournait du texte brut
- Pas de markdown structuré
- Métadonnées limitées

**Maintenant**:
- ✅ Trafilatura avec `output_format='markdown'`, `include_links=True`, `include_images=True`
- ✅ Markdown enrichi avec marqueurs `![IMAGE]`, `[VIDEO:]`, `[AUDIO:]`
- ✅ Extraction simultanée markdown + HTML pour analyse médias
- ✅ Métadonnées complètes (title, description, keywords, language)
- ✅ Champ `content` (HTML brut) persisté

**Référence**: `app/core/content_extractor.py` (lignes 14-63, 153-218)

---

### 2. ✅ Fallback Wayback / Archive.org
**Statut**: **RÉSOLU**

**Avant**:
- Archive.org utilisait httpx basique
- Compteur wayback_used erroné
- Pas de métadonnées Archive.org

**Maintenant**:
- ✅ Utilisation de `trafilatura.fetch_url()` (comportement legacy)
- ✅ Pipeline complète : fetch → extraction markdown+HTML → enrichissement médias → extraction liens
- ✅ Source tracée : `extraction_source = 'archive_org'`
- ✅ Ordre des fallbacks aligné : Trafilatura → Archive.org → BeautifulSoup

**Référence**: `app/core/content_extractor.py` (lignes 307-375)

---

### 3. ✅ Gestion des médias et des liens
**Statut**: **PARTIELLEMENT RÉSOLU**

**Corrigé**:
- ✅ Extraction médias depuis markdown enrichi (`enrich_markdown_with_media`)
- ✅ Extraction liens depuis markdown (`extract_md_links`)
- ✅ Création ExpressionLink depuis liens markdown (`_create_links_from_markdown`)
- ✅ Sauvegarde médias depuis liste enrichie (`_save_media_from_list`)
- ✅ Résolution URLs relatives avec `resolve_url()`

**Références**:
- `app/core/content_extractor.py` (fonctions d'enrichissement)
- `app/core/crawler_engine.py` (méthodes `_create_links_from_markdown`, `_save_media_from_list`)

**Reste à faire**:
- ⏳ Vérifier que `ReadableSimpleService` et `ReadableCeleryService` utilisent bien ces nouvelles fonctions
- ⏳ S'assurer que la création automatique d'expressions pour les liens découverts fonctionne

---

## ⏳ Écarts RESTANTS (À traiter)

### 4. ⏳ Pertinence et validation LLM dans services parallèles

**Statut**: **À VÉRIFIER**

**Problème identifié**:
- `ReadableSimpleService` et `ReadableCeleryService` ne recalculent peut-être pas la pertinence ni n'appellent la validation LLM
- Pas de mise à jour d'`approved_at`, `relevance`, `valid_llm` pour ces chemins

**Action requise**:
1. Auditer `ReadableSimpleService` et `ReadableCeleryService`
2. S'assurer qu'ils utilisent le pipeline complet avec :
   - Extraction enrichie (markdown + médias + liens)
   - Recalcul de pertinence
   - Validation LLM si configurée
   - Mise à jour de `approved_at`

**Référence**: À vérifier dans :
- `app/services/readable_simple_service.py`
- `app/services/readable_celery_service.py`

---

### 5. ⏳ Stratégies de fusion et profondeur

**Statut**: **À VÉRIFIER**

**Problèmes identifiés**:
- Logique de fusion dupliquée dans trois services (risque d'incohérence)
- Filtrage par profondeur diffère du legacy (≤ depth vs == depth)

**Action requise**:
1. Vérifier si le filtrage `≤ depth` est intentionnel ou doit être `== depth`
2. Centraliser la logique de fusion dans un seul endroit
3. Supporter les champs additionnels (keywords, etc.)

**Référence**: À vérifier dans :
- `app/services/readable_service.py:330-370`
- `app/services/readable_simple_service.py:206-259`
- `app/services/readable_celery_service.py:170-231`

---

### 6. ⏳ Statistiques et instrumentation

**Statut**: **À AMÉLIORER**

**Problème identifié**:
- `ReadableProcessingResult` ne calcule pas de taux de succès
- Pas de trace distincte pour `skipped` ni erreurs Wayback

**Action requise**:
1. Ajouter calcul de `success_rate` dans les statistiques
2. Tracer distinctement : `success`, `failed`, `skipped`, `wayback_used`
3. Ajouter métriques pour monitoring

**Référence**: À améliorer dans :
- `app/services/readable_service.py:176-198`

---

## 📋 Checklist de Validation

### ✅ Corrections Appliquées (17 octobre 2025)
- [x] Format markdown avec enrichissement médias/liens
- [x] Fallback Archive.org avec trafilatura.fetch_url
- [x] Extraction et sauvegarde médias depuis markdown
- [x] Extraction et création liens depuis markdown
- [x] Persistance champs legacy (content, http_status)
- [x] Ordre des fallbacks aligné avec legacy
- [x] Smart extraction intégrée au fallback BeautifulSoup

### ⏳ Validations Requises
- [ ] Services parallèles utilisent pipeline enrichi
- [ ] Recalcul pertinence dans tous les services
- [ ] Validation LLM cohérente
- [ ] Stratégies de fusion harmonisées
- [ ] Statistiques complètes avec success_rate
- [ ] Tests de non-régression sur échantillon

---

## 🎯 Actions Prioritaires Restantes

### Priorité 1 (Critique)
1. **Auditer services parallèles** (`ReadableSimpleService`, `ReadableCeleryService`)
   - Vérifier qu'ils utilisent `content_extractor.get_readable_content_with_fallbacks()`
   - S'assurer du recalcul de pertinence
   - Vérifier appel validation LLM

### Priorité 2 (Important)
2. **Harmoniser logique de fusion**
   - Centraliser dans un service commun
   - Documenter stratégies (prefer_earlier, prefer_later, merge)

3. **Améliorer statistiques**
   - Ajouter `success_rate`
   - Tracer sources d'extraction distinctement

### Priorité 3 (Souhaitable)
4. **Tests de validation**
   - Tests comparatifs legacy vs API
   - Validation sur échantillon d'URLs réelles

---

## 📚 Références

### Documents Principaux
- **Audit et corrections** : [TRANSFERT_API_CRAWL.md](TRANSFERT_API_CRAWL.md)
- **Détails techniques** : [CORRECTIONS_PARITÉ_LEGACY.md](CORRECTIONS_PARITÉ_LEGACY.md)
- **Pipeline extraction** : [CHAÎNE_FALLBACKS.md](CHAÎNE_FALLBACKS.md)
- **Résumé exécutif** : [RÉSUMÉ_CORRECTIONS_17OCT2025.md](RÉSUMÉ_CORRECTIONS_17OCT2025.md)

### Fichiers Source Modifiés
- `MyWebIntelligenceAPI/app/core/content_extractor.py`
- `MyWebIntelligenceAPI/app/core/crawler_engine.py`
- `MyWebIntelligenceAPI/app/schemas/expression.py`

### Tests
- `MyWebIntelligenceAPI/tests/test_legacy_parity.py`

---

**Dernière mise à jour**: 17 octobre 2025
**Statut global**: ✅ **Écarts critiques corrigés** | ⏳ **Validation services parallèles requise**
