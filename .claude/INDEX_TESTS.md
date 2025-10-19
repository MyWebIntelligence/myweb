# 📋 Index des Scripts de Test

**Dernière mise à jour** : 19 octobre 2025

---

## 🎯 Scripts Disponibles

### 1. `test-crawl-async.sh` ✅ NOUVEAU

**Objectif** : Tester le crawler ASYNC et valider les corrections d'alignement sync/async

**Utilisation** :
```bash
cd MyWebIntelligenceAPI/tests
./test-crawl-async.sh
```

**Ce qui est testé** :
- ✅ Phase 1 : Headers HTTP (`last_modified`, `etag`)
- ✅ Phase 2 : Dictionnaire `metadata`
- ✅ Phase 3 : Parsing `published_at`
- ✅ Phase 4 : `update_data.update()` avec metadata
- ✅ Phase 5 : Fix NameError `metadata_lang` → `final_lang`

**Documentation** :
- [README_TEST_ASYNC.md](README_TEST_ASYNC.md) - Guide complet
- [QUICKSTART_TEST_ASYNC.md](QUICKSTART_TEST_ASYNC.md) - Démarrage rapide

**Durée** : ~30-45 secondes
**Exit code** : 0 = succès, 1 = échec

---

### 2. `test-crawl-simple.sh` (Existant)

**Objectif** : Tester le crawler SYNC (via Celery)

**Utilisation** :
```bash
cd MyWebIntelligenceAPI/tests
./test-crawl-simple.sh
```

**Ce qui est testé** :
- ✅ Crawl sync via Celery workers
- ✅ 5 URLs du fichier lecornu.txt
- ✅ Création land, ajout mots-clés, crawl, vérification stats

**Durée** : ~20-30 secondes

---

## 🔍 Comparaison Scripts

| Aspect | test-crawl-async.sh | test-crawl-simple.sh |
|--------|---------------------|---------------------|
| **Crawler testé** | Async (API directe) | Sync (Celery) |
| **Fichier testé** | `crawler_engine.py` | `crawler_engine_sync.py` |
| **URLs** | 3 URLs stables | 5 URLs lecornu.txt |
| **Vérifications** | 15+ champs en DB | Stats globales |
| **Validation** | Phases 1-5 spécifiques | Générale |
| **Rapport** | Très détaillé | Concis |

---

## 📚 Documentation

### Script Async (Nouveau)
- **[README_TEST_ASYNC.md](README_TEST_ASYNC.md)**
  - Guide complet (15+ sections)
  - Prérequis, utilisation, debugging
  - Interprétation résultats
  - Troubleshooting

- **[QUICKSTART_TEST_ASYNC.md](QUICKSTART_TEST_ASYNC.md)**
  - Démarrage rapide (TL;DR)
  - Usage en 1 commande
  - Cas d'usage

### Documentation Générale
- [.claude/align_sync_async.md](../.claude/align_sync_async.md) - Plan d'alignement
- [.claude/ERREUR_DOUBLE_CRAWLER.md](../.claude/ERREUR_DOUBLE_CRAWLER.md) - Problème sync/async

---

## 🚀 Workflow Recommandé

### Après Modification du Crawler Async

```bash
# 1. Modifier crawler_engine.py
vim MyWebIntelligenceAPI/app/core/crawler_engine.py

# 2. Redémarrer API
docker-compose restart api

# 3. Tester async
./test-crawl-async.sh

# 4. Si succès, tester sync pour vérifier parité
./test-crawl-simple.sh
```

### Avant Déploiement Production

```bash
# 1. Test async
./test-crawl-async.sh > /tmp/test-async.log

# 2. Test sync
./test-crawl-simple.sh > /tmp/test-sync.log

# 3. Vérifier que les deux passent
echo $? # Doit être 0 pour les deux
```

### Comparaison Sync vs Async

```bash
# Lancer les deux en parallèle
./test-crawl-async.sh > /tmp/async.log 2>&1 &
./test-crawl-simple.sh > /tmp/sync.log 2>&1 &

# Attendre
wait

# Comparer (ignorer Job IDs et timestamps)
diff /tmp/async.log /tmp/sync.log
```

---

## 🎯 Quand Utiliser Quel Script ?

### Utiliser `test-crawl-async.sh` quand :
- ✅ Vous avez modifié `crawler_engine.py` (async)
- ✅ Vous voulez vérifier l'alignement sync/async
- ✅ Vous testez une correction spécifique (metadata, headers, etc.)
- ✅ Vous voulez un rapport détaillé champ par champ

### Utiliser `test-crawl-simple.sh` quand :
- ✅ Vous avez modifié `crawler_engine_sync.py` (sync)
- ✅ Vous testez Celery workers
- ✅ Vous voulez un test rapide global
- ✅ Vous testez avec des URLs réelles (lecornu)

### Utiliser LES DEUX quand :
- ✅ Vous avez modifié la logique de crawl (TOUJOURS !)
- ✅ Avant un déploiement en production
- ✅ Pour valider la parité complète
- ✅ Après merge d'une PR importante

---

## ⚡ Commandes Rapides

### Test Async Seul
```bash
cd MyWebIntelligenceAPI/tests && ./test-crawl-async.sh
```

### Test Sync Seul
```bash
cd MyWebIntelligenceAPI/tests && ./test-crawl-simple.sh
```

### Les Deux en Séquence
```bash
cd MyWebIntelligenceAPI/tests
./test-crawl-async.sh && echo "✅ Async OK" && \
./test-crawl-simple.sh && echo "✅ Sync OK"
```

### Avec Personnalisation
```bash
# API custom
API_URL="http://localhost:8080" ./test-crawl-async.sh

# DB custom
DB_CONTAINER="custom-db" ./test-crawl-async.sh
```

---

## 🐛 Debugging

### Logs API
```bash
docker logs -f mywebclient-api-1 | grep -E "crawl|error"
```

### Logs Celery
```bash
docker logs -f mywebclient-celery_worker-1 | grep -E "crawl|error"
```

### Vérifier DB
```bash
docker exec mywebclient-db-1 psql -U mwi_user -d mwi_db -c \
  "SELECT COUNT(*) FROM expressions WHERE created_at > NOW() - INTERVAL '5 minutes';"
```

---

## 📊 Structure des Fichiers Tests

```
MyWebIntelligenceAPI/tests/
├── test-crawl-async.sh          ← Script test ASYNC ✅ NOUVEAU
├── test-crawl-simple.sh         ← Script test SYNC (existant)
├── README_TEST_ASYNC.md         ← Doc complète async ✅ NOUVEAU
├── QUICKSTART_TEST_ASYNC.md     ← Quick start async ✅ NOUVEAU
├── INDEX_TESTS.md               ← Vous êtes ici ✅ NOUVEAU
└── test_*.py                    ← Tests unitaires Python
```

---

## 🎓 Rappel Important

⚠️ **DOUBLE CRAWLER** : Toute modification de la logique de crawl doit être portée sur LES DEUX crawlers !

- `app/core/crawler_engine.py` (async)
- `app/core/crawler_engine_sync.py` (sync)

Voir : [.claude/ERREUR_DOUBLE_CRAWLER.md](../.claude/ERREUR_DOUBLE_CRAWLER.md)

---

**Version** : 1.0
**Maintenu par** : Équipe MyWebIntelligence
