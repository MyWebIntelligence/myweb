# 📚 Index de la Documentation - Transfert Legacy → API

**Date**: 17 octobre 2025
**Projet**: MyWebIntelligence - Migration Pipeline Crawl & Readable

---

## 🗺️ Vue d'ensemble

Ce dossier `.claude/` contient toute la documentation relative au transfert et à l'alignement du système legacy vers l'API moderne. Suite à l'audit du 17 octobre 2025, **des corrections majeures** ont été apportées pour restaurer la parité avec le système legacy.

---

## 📑 Documents par Catégorie

### 🔴 ERREURS FRÉQUENTES (À lire IMMÉDIATEMENT)

#### 0. [ERREUR_DOUBLE_CRAWLER.md](ERREUR_DOUBLE_CRAWLER.md) 🚨 CRITIQUE

Bug le plus fréquent du projet:

- Explication du problème sync/async
- Checklist obligatoire avant chaque commit
- Exemples de bugs réels causés par cet oubli
- Guide de synchronisation des deux crawlers

**👉 LISEZ CE DOCUMENT AVANT TOUTE MODIFICATION DU CRAWLER !**

---

### 🎯 Documents Principaux (À lire en priorité)

#### 1. [RÉSUMÉ_CORRECTIONS_17OCT2025.md](RÉSUMÉ_CORRECTIONS_17OCT2025.md) ⭐ **START HERE**
**Résumé exécutif des corrections**
- Vue d'ensemble des 7 recommandations implémentées
- Liste des fichiers modifiés
- Instructions de test et validation
- Prochaines étapes

**👉 Lisez ce document en premier pour comprendre rapidement ce qui a été fait.**

---

#### 2. [TRANSFERT_API_CRAWL.md](TRANSFERT_API_CRAWL.md) 📋 **AUDIT COMPLET**
**Audit détaillé et statut des corrections**
- État des lieux initial (écarts identifiés)
- Cartographie Legacy → API
- Plan de développement avec statut ✅/⏳
- Récapitulatif des fichiers modifiés

**👉 Document de référence pour l'audit complet.**

---

#### 3. [CORRECTIONS_PARITÉ_LEGACY.md](CORRECTIONS_PARITÉ_LEGACY.md) 🔧 **DÉTAILS TECHNIQUES**
**Documentation technique complète des corrections**
- Problèmes identifiés et solutions détaillées
- Code source modifié avec numéros de lignes
- Impact métier et fonctionnel
- Checklist de déploiement

**👉 Pour comprendre les détails techniques de chaque correction.**

---

### 🔍 Documents Techniques

#### 4. [CHAÎNE_FALLBACKS.md](CHAÎNE_FALLBACKS.md) 📊 **SCHÉMA PIPELINE**
**Schéma visuel de la chaîne d'extraction**
- Diagramme complet de la pipeline
- Détails de chaque méthode (Trafilatura, Archive.org, BeautifulSoup)
- Sources d'extraction tracées
- Comportement attendu selon scénarios

**👉 Pour comprendre visuellement comment fonctionne l'extraction de contenu.**

---

#### 5. [Transfert_readable.md](Transfert_readable.md) 📝 **AUDIT READABLE**
**Audit du pipeline "readable" (mis à jour)**
- Écarts corrigés ✅
- Écarts restants à traiter ⏳
- Actions prioritaires
- Checklist de validation

**👉 Pour le suivi des écarts spécifiques au pipeline readable.**

---

## 🎯 Workflow de Lecture Recommandé

### Pour comprendre rapidement (15 min)
1. [RÉSUMÉ_CORRECTIONS_17OCT2025.md](RÉSUMÉ_CORRECTIONS_17OCT2025.md)
2. [CHAÎNE_FALLBACKS.md](CHAÎNE_FALLBACKS.md) (schéma visuel)

### Pour une compréhension complète (1h)
1. [RÉSUMÉ_CORRECTIONS_17OCT2025.md](RÉSUMÉ_CORRECTIONS_17OCT2025.md)
2. [TRANSFERT_API_CRAWL.md](TRANSFERT_API_CRAWL.md)
3. [CORRECTIONS_PARITÉ_LEGACY.md](CORRECTIONS_PARITÉ_LEGACY.md)
4. [CHAÎNE_FALLBACKS.md](CHAÎNE_FALLBACKS.md)

### Pour l'implémentation (développeur)
1. [CORRECTIONS_PARITÉ_LEGACY.md](CORRECTIONS_PARITÉ_LEGACY.md)
2. [CHAÎNE_FALLBACKS.md](CHAÎNE_FALLBACKS.md)
3. Code source dans `MyWebIntelligenceAPI/app/core/`
4. Tests dans `MyWebIntelligenceAPI/tests/test_legacy_parity.py`

### Pour la validation (QA/Tests)
1. [RÉSUMÉ_CORRECTIONS_17OCT2025.md](RÉSUMÉ_CORRECTIONS_17OCT2025.md) (section Tests)
2. [Transfert_readable.md](Transfert_readable.md) (checklist validation)
3. `MyWebIntelligenceAPI/tests/test_legacy_parity.py`

---

## 📊 Statut Global

### ✅ Corrections Implémentées (100% des recommandations)
- ✅ Format markdown Trafilatura avec enrichissement
- ✅ Ordre des fallbacks aligné (Trafilatura → Archive.org → BeautifulSoup + smart)
- ✅ Enrichissement markdown avec marqueurs médias
- ✅ Extraction et création de liens depuis markdown
- ✅ Persistance champs legacy (content, http_status)
- ✅ Fallback Archive.org avec trafilatura.fetch_url
- ✅ Smart extraction optimisée dans BeautifulSoup

### ⏳ Validations Requises
- ⏳ Services parallèles (ReadableSimpleService, ReadableCeleryService)
- ⏳ Tests de non-régression sur échantillon URLs
- ⏳ Validation avec downstream consumers

---

## 🗂️ Structure des Fichiers

```
.claude/
├── INDEX_DOCUMENTATION.md          ← Vous êtes ici
├── RÉSUMÉ_CORRECTIONS_17OCT2025.md ⭐ Start here
├── TRANSFERT_API_CRAWL.md          📋 Audit complet
├── CORRECTIONS_PARITÉ_LEGACY.md    🔧 Détails techniques
├── CHAÎNE_FALLBACKS.md             📊 Schéma pipeline
└── Transfert_readable.md           📝 Audit readable (mis à jour)
```

---

## 📁 Code Source Modifié

### Fichiers Principaux
```
MyWebIntelligenceAPI/
├── app/core/
│   ├── content_extractor.py    (+150 lignes, 4 nouvelles fonctions)
│   └── crawler_engine.py       (+130 lignes, 2 nouvelles méthodes)
├── app/schemas/
│   └── expression.py            (+3 champs)
└── tests/
    └── test_legacy_parity.py   (suite complète de tests)
```

### Scripts Utilitaires
```
MyWebIntelligenceAPI/scripts/
├── verify_legacy_parity.py     (vérification Python)
└── check_files.sh              (vérification bash) ✅ Testé
```

---

## 🧪 Tests et Validation

### Tests Unitaires
```bash
cd MyWebIntelligenceAPI
pytest tests/test_legacy_parity.py -v
```

### Vérification Rapide
```bash
cd MyWebIntelligenceAPI
./scripts/check_files.sh
```

### Test Manuel
```bash
# API doit être lancée
curl -X POST http://localhost:8000/api/lands/{land_id}/crawl
```

---

## 📈 Métriques

### Taux de Complétion
- **Recommandations implémentées**: 7/7 (100%)
- **Fichiers modifiés**: 3 fichiers core + 1 schéma + 1 tests
- **Lignes de code ajoutées**: ~280 lignes
- **Nouvelles fonctions**: 6 fonctions + 2 méthodes
- **Tests créés**: 1 suite complète (10+ test cases)

### Couverture Fonctionnelle
- **Format markdown**: 100% ✅
- **Fallbacks**: 100% ✅
- **Enrichissement médias**: 100% ✅
- **Extraction liens**: 100% ✅
- **Champs legacy**: 100% ✅
- **Archive.org**: 100% ✅
- **Smart extraction**: 100% ✅

---

## 🚀 Prochaines Étapes

### Phase 1 - Tests (Priorité Haute)
1. Exécuter tests unitaires
2. Tests d'intégration sur URLs réelles
3. Validation comparative legacy vs API

### Phase 2 - Validation Services (Priorité Haute)
1. Auditer ReadableSimpleService
2. Auditer ReadableCeleryService
3. S'assurer de la cohérence du recalcul de pertinence

### Phase 3 - Déploiement (Priorité Moyenne)
1. Tests en staging
2. Migration base de données (si nécessaire)
3. Déploiement production
4. Monitoring

---

## 📞 Support

### Questions sur les Corrections
- Consulter [CORRECTIONS_PARITÉ_LEGACY.md](CORRECTIONS_PARITÉ_LEGACY.md)
- Section "Points d'attention" et "Impacts métier"

### Questions sur la Pipeline
- Consulter [CHAÎNE_FALLBACKS.md](CHAÎNE_FALLBACKS.md)
- Schéma visuel et détails des méthodes

### Questions sur l'Audit
- Consulter [TRANSFERT_API_CRAWL.md](TRANSFERT_API_CRAWL.md)
- Section "Écarts identifiés" et "Plan de remise à niveau"

---

## 🏷️ Tags et Mots-clés

**Concepts**: Legacy, API, Migration, Parité, Crawl, Readable, Trafilatura, Archive.org, BeautifulSoup

**Technos**: Python, FastAPI, SQLAlchemy, Trafilatura, BeautifulSoup, Celery, WebSocket

**Statuts**: ✅ Corrigé, ⏳ En cours, ❌ Non fait

---

**Dernière mise à jour**: 17 octobre 2025
**Version**: 1.0
**Mainteneur**: Équipe MyWebIntelligence
