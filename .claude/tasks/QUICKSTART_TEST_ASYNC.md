# 🚀 Quick Start - Test Crawler Async

**TL;DR** : Script de test pour valider les corrections du crawler async (fix NameError)

---

## ⚡ Démarrage Rapide (30 secondes)

```bash
cd MyWebIntelligenceAPI/tests
./test-crawl-async.sh
```

**C'est tout !** Le script gère automatiquement :
- ✅ Vérification environnement
- ✅ Authentification
- ✅ Création land de test
- ✅ Crawl de 3 URLs
- ✅ Validation des 5 phases de corrections
- ✅ Rapport détaillé

---

## 📊 Ce que Vous Verrez

### Pendant l'Exécution

```
═══════════════════════════════════════════════════════════
   TEST CRAWLER ASYNC - Vérification Alignement Sync/Async
═══════════════════════════════════════════════════════════

🔧 1/7 - Vérification serveur API...
✅ Serveur API opérationnel

🗄️  2/7 - Vérification base de données...
✅ Base de données accessible

🔑 3/7 - Authentification...
✅ Token obtenu: eyJhbGciOiJIUzI1NiI...

🏗️  4/7 - Création land de test...
✅ Land créé: LAND_ID=42

📝 5/7 - Ajout mots-clés...
✅ Mots-clés ajoutés

🕷️  6/7 - Lancement crawl ASYNC...
✅ Crawl lancé: JOB_ID=123

⏳ Attente fin du crawl (30s)...

📊 7/7 - Vérification résultats ASYNC...
```

### Résultat Final (Succès)

```
═══════════════════════════════════════════════════════════
                    RAPPORT FINAL
═══════════════════════════════════════════════════════════

✅ Vérification Corrections Async:

  Phase 1 - Headers HTTP (last_modified, etag):
    ✅ PHASE 1 OK - Headers extraits

  Phase 2 - Dictionnaire metadata (title, lang, description):
    ✅ PHASE 2 OK - Metadata dict créé et utilisé

  Phase 3 - Parsing published_at:
    ✅ PHASE 3 OK - published_at parsé

  Phase 4 - Update data avec metadata:
    ✅ PHASE 4 OK - update_data.update() utilisé

  Phase 5 - Calcul pertinence (FIX NameError CRITIQUE):
    ✅ PHASE 5 OK - Pas de NameError! final_lang utilisé
    ✅ Bug metadata_lang RÉSOLU

🎯 Validation Globale:
  ✅ SUCCÈS COMPLET - Crawler async 100% fonctionnel
  ✅ Alignement sync/async confirmé
  ✅ Toutes les phases validées

✅ Test terminé avec succès!
```

---

## 🎯 Ce qui est Vérifié

| Phase | Correction | Validation |
|-------|-----------|------------|
| **1** | Headers HTTP | `last_modified`, `etag` en DB |
| **2** | Dict metadata | `title`, `lang` remplis |
| **3** | Parsing dates | `published_at` parsé |
| **4** | Update data | Metadata utilisé |
| **5** | **Fix NameError** | `relevance` calculée ✅ |

---

## ❌ En Cas d'Erreur

### Serveur API non accessible

```bash
# Vérifier les containers
docker ps

# Démarrer l'API si nécessaire
docker-compose up -d api
```

### Base de données non accessible

```bash
# Vérifier la DB
docker exec mywebclient-db-1 psql -U mwi_user -d mwi_db -c "SELECT 1"

# Redémarrer si besoin
docker-compose restart db
```

### NameError dans les logs

```bash
# Vérifier que les corrections sont appliquées
grep -n "final_lang or" MyWebIntelligenceAPI/app/core/crawler_engine.py

# Doit afficher ligne 269:
# 269:                final_lang or "fr"
```

---

## 🔍 Options Avancées

### Personnaliser l'API URL

```bash
API_URL="http://localhost:8000" ./test-crawl-async.sh
```

### Voir Plus de Détails

Le script affiche déjà **tous les détails** par défaut. Pour encore plus :

```bash
# Activer le mode verbeux bash
bash -x ./test-crawl-async.sh
```

### Sauvegarder le Rapport

```bash
./test-crawl-async.sh | tee /tmp/test-async-$(date +%Y%m%d_%H%M%S).log
```

---

## 📚 Documentation Complète

Pour plus de détails, voir :
- **Guide complet** : [README_TEST_ASYNC.md](README_TEST_ASYNC.md)
- **Plan d'alignement** : [.claude/align_sync_async.md](../../.claude/align_sync_async.md)

---

## ✅ Prérequis Minimum

- Docker en cours d'exécution
- API accessible sur `http://localhost:8000`
- DB PostgreSQL accessible
- Commande `jq` installée

---

## 🎉 Cas d'Usage

### Après Modifications du Crawler

```bash
# 1. Modifier crawler_engine.py
vim MyWebIntelligenceAPI/app/core/crawler_engine.py

# 2. Redémarrer l'API
docker-compose restart api

# 3. Lancer le test
./test-crawl-async.sh
```

### Test de Non-Régression

```bash
# Lancer avant déploiement
./test-crawl-async.sh > /tmp/before.log

# Faire les modifs...

# Lancer après
./test-crawl-async.sh > /tmp/after.log

# Comparer
diff /tmp/before.log /tmp/after.log
```

---

**Temps d'exécution** : ~30-45 secondes
**URLs testées** : 3 URLs stables
**Exit code** : 0 = succès, 1 = échec

---

**Version** : 1.0
**Date** : 19 octobre 2025
