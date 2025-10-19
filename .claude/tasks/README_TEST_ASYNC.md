# Test Crawler Async - Guide d'Utilisation

**Date**: 19 octobre 2025
**Objectif**: Valider les corrections du crawler async (alignement avec sync)

---

## 🎯 Objectif du Test

Ce script teste **spécifiquement le crawler ASYNC** ([crawler_engine.py](../app/core/crawler_engine.py)) pour valider les **5 phases de corrections** appliquées suite à l'alignement avec le crawler sync.

### Corrections Vérifiées

| Phase | Correction | Vérification |
|-------|-----------|--------------|
| **1** | Extraction headers HTTP (`last_modified`, `etag`) | Présence champs en DB |
| **2** | Création dict `metadata` | `title`, `lang`, `description` remplis |
| **3** | Parsing `published_at` | Date parsée et persistée |
| **4** | `update_data.update()` avec metadata | Utilisation dict metadata |
| **5** | **Fix NameError** `metadata_lang` → `final_lang` | Calcul `relevance` réussi |

---

## 📋 Prérequis

### 1. Environnement Docker

```bash
# Services requis en cours d'exécution
docker ps | grep -E "api|db|celery"
```

Vous devez avoir :
- ✅ `mywebclient-api-1` (API FastAPI)
- ✅ `mywebclient-db-1` (PostgreSQL)
- ✅ `mywebclient-celery_worker-1` (Celery worker - optionnel)

### 2. Base de Données Initialisée

```bash
# Vérifier la connexion DB
docker exec mywebclient-db-1 psql -U mwi_user -d mwi_db -c "SELECT 1"
```

### 3. Utilisateur Admin

Par défaut, le script utilise :
- **Email**: `admin@example.com`
- **Password**: `changethispassword`

Si vous avez d'autres credentials, modifiez le script ligne 6-8.

### 4. Dépendances

```bash
# Le script nécessite:
- curl
- jq (parser JSON)
- docker
```

Installation si manquant :

```bash
# macOS
brew install jq

# Ubuntu/Debian
sudo apt-get install jq

# Arch
sudo pacman -S jq
```

---

## 🚀 Utilisation

### Lancement Simple

```bash
cd MyWebIntelligenceAPI/tests
./test-crawl-async.sh
```

### Avec Configuration Personnalisée

```bash
# Personnaliser l'URL de l'API
API_URL="http://localhost:8000" ./test-crawl-async.sh

# Personnaliser le container DB
DB_CONTAINER="mon-db-custom" ./test-crawl-async.sh

# Combinaison
API_URL="http://api.local:8080" \
DB_CONTAINER="custom-db" \
./test-crawl-async.sh
```

---

## 📊 Ce que Fait le Script

### Phase 1 : Initialisation (étapes 1-3)
1. ✅ Vérifie que l'API est accessible
2. ✅ Vérifie que la DB est accessible
3. ✅ S'authentifie et obtient un token JWT

### Phase 2 : Préparation (étapes 4-5)
4. ✅ Crée un land de test avec 3 URLs stables
5. ✅ Ajoute des mots-clés pour le calcul de pertinence

### Phase 3 : Crawl (étape 6)
6. ✅ Lance le crawl via l'API (utilise **crawler ASYNC**)

### Phase 4 : Validation (étape 7)

Le script vérifie **tous les champs critiques** en DB :

```sql
SELECT
    id, url, title, description, lang,
    published_at,           -- Phase 3 ✅
    last_modified, etag,    -- Phase 1 ✅
    relevance,              -- Phase 5 ✅ (fix NameError)
    content, readable,
    word_count, approved_at
FROM expressions
WHERE land_id = <TEST_LAND_ID>;
```

### Phase 5 : Rapport
- 📊 Statistiques de crawl
- ✅ Validation de chaque phase
- 🎯 Verdict final (succès/échec)

---

## 📈 Interprétation des Résultats

### ✅ Succès Complet

```
✅ SUCCÈS COMPLET - Crawler async 100% fonctionnel
✅ Alignement sync/async confirmé
✅ Toutes les phases validées
```

**Signification** :
- Tous les champs métadonnées sont remplis
- Pas de NameError sur `metadata_lang`
- Le crawler async est aligné avec le sync

### ✅ Succès Partiel

```
✅ SUCCÈS PARTIEL - Pas de NameError
⚠️  Quelques champs optionnels manquants (normal)
```

**Signification** :
- Le bug critique (NameError) est résolu
- Quelques champs optionnels manquent (ex: `published_at`, `etag`)
- C'est **NORMAL** si les pages crawlées ne fournissent pas ces métadonnées

### ❌ Échec

```
❌ ÉCHEC - NameError probable ou métadonnées manquantes
❌ Vérifier les logs du crawler async
```

**Actions** :
1. Vérifier les logs de l'API :
   ```bash
   docker logs mywebclient-api-1 --tail 100 | grep -i "error\|nameerror"
   ```

2. Vérifier la DB manuellement :
   ```bash
   docker exec mywebclient-db-1 psql -U mwi_user -d mwi_db -c \
     "SELECT url, lang, relevance FROM expressions ORDER BY created_at DESC LIMIT 5;"
   ```

---

## 🔍 Debugging

### Voir les Logs de l'API

```bash
# Logs temps réel
docker logs -f mywebclient-api-1

# Dernières erreurs
docker logs mywebclient-api-1 --tail 100 | grep -E "ERROR|NameError|metadata_lang"

# Logs de crawl
docker logs mywebclient-api-1 --tail 200 | grep -i "crawl"
```

### Requêtes DB Manuelles

```bash
# Se connecter à la DB
docker exec -it mywebclient-db-1 psql -U mwi_user -d mwi_db

# Vérifier les dernières expressions
SELECT id, url, title, lang, relevance, published_at
FROM expressions
ORDER BY created_at DESC
LIMIT 10;

# Vérifier les champs NULL
SELECT
    COUNT(*) as total,
    COUNT(lang) as with_lang,
    COUNT(relevance) as with_relevance,
    COUNT(published_at) as with_published
FROM expressions
WHERE created_at > NOW() - INTERVAL '5 minutes';
```

### Tester Manuellement l'API

```bash
# 1. Login
TOKEN=$(curl -s -X POST "http://localhost:8000/api/v1/auth/login" \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=admin@example.com&password=changethispassword" | jq -r .access_token)

# 2. Créer un land
curl -X POST "http://localhost:8000/api/v2/lands/" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "test_manual",
    "start_urls": ["https://www.example.com"]
  }' | jq '.'

# 3. Lancer crawl (remplacer LAND_ID)
curl -X POST "http://localhost:8000/api/v2/lands/{LAND_ID}/crawl" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"limit": 1}' | jq '.'
```

---

## 🧪 Tests Complémentaires

### Comparaison Sync vs Async

Pour vérifier la parité complète :

```bash
# 1. Lancer test ASYNC
./test-crawl-async.sh > /tmp/result_async.txt

# 2. Lancer test SYNC
./test-crawl-simple.sh > /tmp/result_sync.txt

# 3. Comparer les résultats
diff /tmp/result_async.txt /tmp/result_sync.txt
```

Les différences attendues :
- ✅ Durée de crawl (async peut être plus rapide)
- ✅ Job IDs différents
- ❌ Les champs `lang`, `relevance`, `title` doivent être **identiques**

### Test de Charge

```bash
# Test avec plus d'URLs
# Modifier TEST_URLS dans le script pour ajouter:
TEST_URLS=(
    "https://www.example.com"
    "https://en.wikipedia.org/wiki/Web_crawler"
    "https://www.ietf.org/rfc/rfc2616.txt"
    "https://developer.mozilla.org/en-US/"
    "https://www.w3.org/standards/"
    # ... jusqu'à 20 URLs
)
```

---

## 📝 Personnalisation

### Modifier les URLs de Test

Éditez le script, ligne 26-30 :

```bash
TEST_URLS=(
    "https://votre-url-1.com"
    "https://votre-url-2.com"
    "https://votre-url-3.com"
)
```

**Recommandations** :
- Utilisez des URLs **stables** (qui ne changent pas)
- Privilégiez des sites **bien structurés** (metadata complètes)
- Évitez les sites avec **anti-scraping** agressif

### Modifier les Mots-Clés

Ligne 96 :

```bash
-d '{"terms": ["web", "crawler", "http", "metadata"]}'
```

Adaptez selon votre domaine de test.

---

## 🎯 Critères de Réussite

Pour que le test soit validé, **au minimum** :

1. ✅ `relevance` calculée (pas de NameError)
2. ✅ `lang` détectée
3. ✅ `title` extrait
4. ✅ `approved_at` rempli (expression validée)

**Optionnels mais bons signes** :
- ✅ `published_at` parsé
- ✅ `last_modified` ou `etag` présents
- ✅ `description` et `keywords` remplis

---

## 🐛 Problèmes Connus

### "NameError: name 'metadata_lang' is not defined"

**Cause** : Les corrections n'ont pas été appliquées
**Solution** : Vérifier que [crawler_engine.py](../app/core/crawler_engine.py) ligne 269 utilise bien `final_lang or "fr"` et **pas** `metadata_lang or 'fr'`

### "KeyError: 'title'" sur metadata['title']

**Cause** : Utilisation de `metadata['title']` au lieu de `metadata.get('title')`
**Solution** : Vérifier ligne 265 du crawler_engine.py

### Tous les champs sont NULL

**Cause** : Le crawler a échoué silencieusement
**Solution** :
1. Vérifier les logs API
2. Tester avec une URL simple (https://www.example.com)
3. Vérifier que l'API utilise bien le crawler async et pas sync

---

## 📚 Références

- **Plan d'alignement** : [.claude/align_sync_async.md](../../.claude/align_sync_async.md)
- **Erreur double crawler** : [.claude/ERREUR_DOUBLE_CRAWLER.md](../../.claude/ERREUR_DOUBLE_CRAWLER.md)
- **Fichier corrigé** : [app/core/crawler_engine.py](../app/core/crawler_engine.py)
- **Référence sync** : [app/core/crawler_engine_sync.py](../app/core/crawler_engine_sync.py)

---

## ✅ Checklist Avant de Lancer

- [ ] Services Docker en cours d'exécution
- [ ] DB accessible et initialisée
- [ ] User admin créé
- [ ] `jq` installé
- [ ] Script exécutable (`chmod +x test-crawl-async.sh`)

---

**Dernière mise à jour** : 19 octobre 2025
**Version script** : 1.0
**Auteur** : Équipe MyWebIntelligence
