# MyWebIntelligence API - Guide Complet pour Agents

MyWebIntelligence est une API FastAPI encapsulant les fonctionnalités du crawler MyWebIntelligencePython. Elle permet l'intégration avec MyWebClient et ouvre la voie à un déploiement SaaS scalable.

## 📚 Documentation active

- [INDEX_DOCUMENTATION.md](INDEX_DOCUMENTATION.md) — plan de lecture consolidé & statuts
- [RÉSUMÉ_CORRECTIONS_17OCT2025.md](RÉSUMÉ_CORRECTIONS_17OCT2025.md) — synthèse décisionnelle
- [TRANSFERT_API_CRAWL.md](TRANSFERT_API_CRAWL.md) — audit Legacy → API
- [CORRECTIONS_PARITÉ_LEGACY.md](CORRECTIONS_PARITÉ_LEGACY.md) — détails techniques (métadonnées & HTML)
- [Transfert_readable.md](Transfert_readable.md) — suivi du pipeline readable
- [CHAÎNE_FALLBACKS.md](CHAÎNE_FALLBACKS.md) — schéma d'extraction
- [METADATA_FIXES.md](METADATA_FIXES.md) — journal détaillé des corrections métadonnées
- [CORRECTIONS_FINALES.md](CORRECTIONS_FINALES.md) — synthèse + checklist de validation
- [compare_addterms_analysis.md](compare_addterms_analysis.md) — analyse AddTerms & pertinence
- [AGENTS.md](AGENTS.md) — checklists incidents (double crawler, init DB, dictionnaire)

## 🎯 Concepts Clés

### Qu'est-ce qu'un "Land" ?
Un **Land** est un projet de crawling/recherche qui contient :
- **URLs de départ** (`start_urls`) : Points d'entrée du crawl
- **Mots-clés** (`words`) : Termes à rechercher avec leurs lemmes
- **Configuration** : Langues supportées, limites, etc.
- **Résultats** : Expressions (pages) et médias découverts

### Qu'est-ce qu'une "Expression" ?
Une **Expression** est une page web crawlée qui contient :
- **URL** et **contenu** de la page
- **Profondeur** (`depth`) : Distance depuis les URLs de départ (0 = URL initiale, 1 = lien direct, etc.)
- **Pertinence** (`relevance`) : Score de correspondance avec les mots-clés
- **Médias** associés (images, vidéos, audio)

### Workflow Typique
1. **Créer un Land** avec URLs de départ et mots-clés
2. **Lancer le crawl** → Découverte d'expressions et médias
3. **Pipeline Readable** → Extraction de contenu lisible (Mercury-like)
4. **Analyser les médias** → Extraction de métadonnées (couleurs, dimensions, EXIF)
5. **Exporter les données** → CSV, GEXF, JSON

## 🚀 Démarrage Rapide

### Authentification
```bash
# Option 1 : depuis l’hôte
TOKEN=$(curl -s -X POST "http://localhost:8000/api/v1/auth/login" -H "Content-Type: application/x-www-form-urlencoded" -d "username=admin@example.com&password=changeme" | jq -r .access_token)

# Option 2 : via Docker Compose (container « api »)
TOKEN=$(docker compose exec api curl -s -X POST "http://localhost:8000/api/v1/auth/login" -H "Content-Type: application/x-www-form-urlencoded" -d "username=${MYWI_USERNAME:-admin@example.com}&password=${MYWI_PASSWORD:-changeme}" | jq -r .access_token)

echo "Token JWT: $TOKEN"
```

### Serveur Docker
```bash
# (Re)déployer avec migrations fraîchement appliquées
docker compose down -v
docker compose up --build -d

# Vérifier les containers
docker ps | grep mywebintelligenceapi

# Redémarrer si nécessaire
docker restart mywebintelligenceapi

# Tester que le serveur répond
curl -s -w "%{http_code}" "http://localhost:8000/" -o /dev/null
```

## 🏗️ Architecture de l'API

### Structure des Endpoints

#### API v1 (Legacy)
- `/api/v1/auth/` - Authentification
- `/api/v1/export/` - Export de données (CSV, GEXF)

#### API v2 (Moderne)
- `/api/v2/lands/` - Gestion des projets (lands)
- `/api/v2/lands/{id}/crawl` - Lancement de crawls
- `/api/v2/lands/{id}/readable` - Pipeline readable (extraction contenu)
- `/api/v2/lands/{id}/media-analysis-async` - Analyse des médias (asynchrone)
- `/api/v2/lands/{id}/stats` - Statistiques

### Modèles de Données

#### Land (Projet)
```python
id: int                    # ID unique
name: str                  # Nom du projet
description: str           # Description
owner_id: int              # Propriétaire (FK users.id)
lang: List[str]            # Langues ["fr", "en"]
start_urls: List[str]      # URLs de départ
crawl_status: str          # "pending", "running", "completed"
total_expressions: int     # Nombre d'expressions
total_domains: int         # Nombre de domaines
words: List[dict]          # Mots-clés avec lemmes
```

#### Expression (Page crawlée)
```python
id: int                    # ID unique
land_id: int               # Projet parent
domain_id: int             # Domaine parent
url: str                   # URL de la page
title: str                 # Titre
content: str               # Contenu HTML
readable: str              # Contenu lisible (markdown)
depth: int                 # Profondeur de crawl
relevance: float           # Score de pertinence
language: str              # Langue détectée
word_count: int            # Nombre de mots
```

#### Media (Fichiers média)
```python
id: int                    # ID unique
expression_id: int         # Expression parent
url: str                   # URL du média
type: str                  # "img", "video", "audio"
is_processed: bool         # Analysé ou non
width: int                 # Largeur (images)
height: int                # Hauteur (images)
file_size: int             # Taille en bytes
metadata: dict             # Métadonnées EXIF, etc.
dominant_colors: List[str] # Couleurs dominantes
```

## 🆕 Mises à jour structurelles (juillet 2025)

- **Schéma SQLAlchemy réaligné**  
  - `domains` conserve `http_status` et `fetched_at`.  
  - `expressions` stocke désormais `published_at`, `approved_at`, `validllm`, `validmodel`, `seorank`, et la langue détectée.  
  - `words` embarque `language` et `frequency`. Une migration Alembic `006_add_legacy_crawl_columns.py` doit être appliquée.

- **Dictionnaire de land**  
  - `DictionaryService.populate_land_dictionary` accepte les seeds (`words`) fournis à la création et crée automatiquement des entrées `Word` multilingues.  
  - Les variations générées via `get_lemma` remplissent la table `land_dictionaries` sans manipuler directement la relation ORM.

- **Service de crawl**  
  - `start_crawl_for_land` renvoie un `CrawlJobResponse` typé (avec `ws_channel`) et convertit les filtres `http_status` en entiers avant insertion.  
  - `CrawlerEngine` persiste la langue, approuve les expressions pertinentes et peuple les nouveaux champs de métadonnées.
- **Migrations automatiques**  
  - Les services `api` et `celery_worker` exécutent `alembic upgrade head` à chaque démarrage du conteneur. Reconstruis la stack (`docker compose down -v && docker compose up --build`) après un pull pour appliquer les derniers schémas.

- **Tests & environnement**  
  - Les tests de crawling nécessitent `pytest`, `sqlalchemy`, `aiosqlite` dans le venv.  
  - Sous Python 3.13, certaines wheels (`pydantic-core`, `asyncpg`, `pillow`) échouent à la compilation ; privilégier Python 3.11/3.12 ou installer Rust + toolchain compatible.

## 🔄 Pipelines de Traitement

### 1. Pipeline de Crawl
```
Start URLs → Crawler → Pages → Content Extraction → Expressions
                          ↓
                     Media Detection → Media Records
```

**Endpoint:** `POST /api/v2/lands/{id}/crawl`
```json
{
  "limit": 10,              // Nombre max de pages
  "depth": 2,               // Profondeur max
  "analyze_media": true     // Analyser les médias
}
```

### 2. Pipeline d'Analyse Media
```
Expressions → Media URLs → Download → Analysis → Metadata Storage
                               ↓
                         PIL/OpenCV → Colors, Dimensions, EXIF
```

**Endpoint:** `POST /api/v2/lands/{id}/media-analysis-async`
```json
{
  "depth": 1,               // Profondeur max des expressions à analyser (0=URLs initiales, 1=liens directs, etc.)
  "minrel": 0.5             // Score de pertinence minimum des expressions
}
```

**IMPORTANT:** `depth` ne limite PAS le nombre d'unités/médias à analyser, mais la profondeur des expressions source !
- `depth: 0` = Analyser uniquement les médias des URLs de départ
- `depth: 1` = Inclure aussi les médias des pages liées directement 
- `depth: 999` = Analyser tous les médias sans limite de profondeur

**STRATÉGIE de LIMITATION:** Pour limiter le nombre de médias analysés, utiliser `minrel` (pertinence) :
- `minrel: 0.0` = Toutes les expressions
- `minrel: 1.0` = Expressions moyennement pertinentes  
- `minrel: 3.0` = Expressions très pertinentes seulement (recommandé pour tests)
- `minrel: 5.0` = Expressions extrêmement pertinentes

### 3. Pipeline Readable (Nouveau)
```
Expressions → Content Extraction → Readable Content → Text Processing → Paragraphs
                     ↓
            Mercury/Trafilatura → Clean Text → LLM Validation → Storage
```

**Endpoint:** `POST /api/v2/lands/{id}/readable`
```json
{
  "limit": 50,              // Nombre max d'expressions à traiter
  "depth": 1,               // Profondeur max des expressions
  "merge_strategy": "smart_merge",  // "mercury_priority", "preserve_existing"
  "enable_llm": false,      // Validation LLM (optionnel)
  "batch_size": 10,         // Expressions par batch
  "max_concurrent": 5       // Batches concurrents
}
```

**IMPORTANT:** Le pipeline readable transforme le contenu HTML brut des expressions en contenu lisible et structuré :
- **Extraction intelligente** : Utilise Trafilatura puis Mercury fallback
- **Nettoyage** : Supprime le markup, garde le contenu principal
- **Validation LLM** : Optionnelle, améliore la qualité du contenu
- **Segmentation** : Découpe en paragraphes pour l'embedding

### 4. Pipeline LLM Validation (Intégré) ✅
```
Expressions → OpenRouter API → Relevance Check → Database Update
                     ↓
              "oui"/"non" → valid_llm, valid_model → Relevance=0 si non pertinent
```

**Intégration dans les pipelines existants :**
- **Crawl avec LLM** : `POST /api/v2/lands/{id}/crawl` avec `"enable_llm": true`
- **Readable avec LLM** : `POST /api/v2/lands/{id}/readable` avec `"enable_llm": true`

**Configuration OpenRouter requise :**
```bash
export OPENROUTER_ENABLED=True
export OPENROUTER_API_KEY=sk-or-v1-your-key-here
export OPENROUTER_MODEL=anthropic/claude-3.5-sonnet
```

**Exemples d'usage :**
```bash
# Crawl avec validation LLM
curl -X POST "http://localhost:8000/api/v2/lands/36/crawl" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"limit": 5, "enable_llm": true}'

# Readable avec validation LLM  
curl -X POST "http://localhost:8000/api/v2/lands/36/readable" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"limit": 3, "enable_llm": true}'
```

**Résultats stockés :**
- `valid_llm` : "oui" (pertinent) ou "non" (non pertinent)
- `valid_model` : Modèle utilisé (ex: "anthropic/claude-3.5-sonnet")
- `relevance` : Mis à 0 si expression jugée non pertinente

### 5. Pipeline d'Export
```
Data Selection → Format Conversion → Response
     ↓
CSV/GEXF/JSON → Compressed → Download
```

**Endpoint:** `POST /api/v1/export/direct`
```json
{
  "land_id": 36,
  "export_type": "mediacsv", // "pagecsv", "nodecsv", etc.
  "limit": 100
}
```

## 🗄️ Base de Données

### Tables Principales
- `users` - Utilisateurs
- `lands` - Projets de crawl
- `domains` - Domaines web
- `expressions` - Pages crawlées
- `media` - Fichiers média
- `paragraphs` - Contenu segmenté
- `crawl_jobs` - Jobs Celery

### Relations Clés
```
users (1) → (n) lands
lands (1) → (n) domains
lands (1) → (n) expressions
expressions (1) → (n) media
expressions (1) → (n) paragraphs
```

## 🧪 Tests Rapides

### ⚠️ PROBLÈME DE PERSISTENCE DU TOKEN

Le token JWT ne persiste pas car `export TOKEN` dans un **sous-shell Docker** ne remonte pas au shell parent. Voici **3 solutions** :

---

### ✅ **Solution 1 : Script complet dans Docker** (recommandé pour les tests)

Exécuter tout le workflow dans un seul appel Docker pour que le token reste en mémoire :

```bash
docker compose exec mywebintelligenceapi bash -c '
  # 1. Authentification
  TOKEN=$(curl -s -X POST "http://localhost:8000/api/v1/auth/login" \
    -H "Content-Type: application/x-www-form-urlencoded" \
    -d "username=admin@example.com&password=changethispassword" \
    | jq -r ".access_token")

  echo "✅ Token obtenu : ${TOKEN:0:20}..."

  # 2. Créer le land
  LAND_ID=$(curl -s -X POST "http://localhost:8000/api/v2/lands/" \
    -H "Authorization: Bearer $TOKEN" \
    -H "Content-Type: application/json" \
    -d "{\"name\":\"Lecornu$(date +%s)\",\"description\":\"Test gilets jaunes\",\"words\":[\"lecornu\"]}" \
    | jq -r ".id // empty")

  if [ -z "$LAND_ID" ]; then
    echo "❌ Impossible de créer le land"
    exit 1
  fi

  echo "✅ Land créé : LAND_ID=${LAND_ID}"

  # 3. Ajouter les URLs
  curl -s -X POST "http://localhost:8000/api/v2/lands/${LAND_ID}/urls" \
    -H "Authorization: Bearer $TOKEN" \
    -H "Content-Type: application/json" \
    --data "$(jq -Rs "{urls: split(\"\n\") | map(select(length>0))}" /app/scripts/data/lecornu.txt)" \
    | jq "."

  echo "✅ URLs ajoutées au land ${LAND_ID}"
'
```

---

### ✅ **Solution 2 : Appels depuis l'hôte** (si API accessible sur localhost)

Stocker le token dans un fichier temporaire pour le réutiliser :

```bash
# 1. Authentification (sauvegarder le token dans un fichier)
curl -s -X POST "http://localhost:8000/api/v1/auth/login" \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=admin@example.com&password=changethispassword" \
  | jq -r '.access_token' > /tmp/mywebintel_token.txt

export TOKEN=$(cat /tmp/mywebintel_token.txt)
echo "✅ Token obtenu : ${TOKEN:0:20}..."

# 2. Créer le land
LAND_ID=$(curl -s -X POST "http://localhost:8000/api/v2/lands/" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"name":"Lecornu202535","description":"testprojet gilets jaunes","words":["lecornu"]}' \
  | jq -r '.id // empty')

if [ -z "$LAND_ID" ]; then
  echo "❌ Impossible de créer le land. Vérifiez les logs ou les permissions."
  exit 1
else
  echo "✅ Land créé : LAND_ID=${LAND_ID}"

  # 3. Ajouter la liste d'URLs
  curl -X POST "http://localhost:8000/api/v2/lands/${LAND_ID}/urls" \
    -H "Authorization: Bearer $TOKEN" \
    -H "Content-Type: application/json" \
    --data "$(jq -Rs '{urls: split("\n") | map(select(length>0))}' MyWebIntelligenceAPI/scripts/data/lecornu.txt)"
fi
```

---

### ✅ **Solution 3 : Session interactive dans le container** (pour tests manuels)

Entrer directement dans le container pour garder le token en mémoire :

```bash
# 1. Entrer dans le container
docker compose exec mywebintelligenceapi bash

# 2. Dans le container, authentification + export
TOKEN=$(curl -s -X POST "http://localhost:8000/api/v1/auth/login" -H "Content-Type: application/x-www-form-urlencoded" -d "username=admin@example.com&password=changethispassword" | jq -r '.access_token')

export TOKEN
echo "✅ Token : ${TOKEN:0:20}..."

# 3. Maintenant toutes vos commandes curl peuvent utiliser $TOKEN
# Créer le land
LAND_ID=$(curl -s -X POST "http://localhost:8000/api/v2/lands/" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"name":"Lecornu202540","description":"Test gilets jaunes","words":["lecornu"]}' \
  | jq -r '.id')

echo "✅ Land créé : $LAND_ID"

# Ajouter les URLs
curl -X POST "http://localhost:8000/api/v2/lands/${LAND_ID}/urls" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  --data "$(jq -Rs '{urls: split("\n") | map(select(length>0))}' /app/scripts/data/lecornu.txt)"

# Pour sortir du container :
# exit
```

### 1. Lister les Lands
```bash
curl -X GET "http://localhost:8000/api/v2/lands/?page=1&page_size=20" \
  -H "Authorization: Bearer $TOKEN"
```

### 2. Détails d'un Land
```bash
curl -X GET "http://localhost:8000/api/v2/lands/${LAND_ID}" \
  -H "Authorization: Bearer $TOKEN"
```

### 3. Statistiques d'un Land
```bash
curl -X GET "http://localhost:8000/api/v2/lands/${LAND_ID}/stats" \
  -H "Authorization: Bearer $TOKEN"
```

### 4. Lancer un Crawl avec Analyse Media
```bash
curl -X POST "http://localhost:8000/api/v2/lands/7/crawl" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"analyze_media": false, "limit": 25, "llm_validation": false}'
```

### 5. Analyser les Médias (ASYNC)
```bash
# Analyser TOUS les médias (toutes profondeurs, toute pertinence)
curl -X POST "http://localhost:8000/api/v2/lands/${LAND_ID}/media-analysis-async" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"depth": 0, "minrel": 3.0}'

# Analyser uniquement les médias des URLs de départ (depth=0)
curl -X POST "http://localhost:8000/api/v2/lands/${LAND_ID}/media-analysis-async" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"depth": 0, "minrel": 0.0}'

# Analyser avec filtre de pertinence (expressions très pertinentes seulement)
curl -X POST "http://localhost:8000/api/v2/lands/${LAND_ID}/media-analysis-async" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"minrel": 3.0}'

# TEST RAPIDE - Analyser seulement les plus pertinents (recommandé)
curl -X POST "http://localhost:8000/api/v2/lands/${LAND_ID}/media-analysis-async" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"minrel": 3.0}'
```

### 6. Pipeline Readable - Extraction de Contenu (✅ FONCTIONNEL)
```bash
# 🎯 TEST DIRECT CELERY (recommandé pour vérifier que ça marche)
docker-compose exec celery_worker python -c "
from app.tasks.readable_working_task import readable_working_task
result = readable_working_task.delay(land_id=1, job_id=999, limit=2)
print(f'Task ID: {result.id}')
import time; time.sleep(15)
print(f'Result: {result.get()}')"

# 📋 PIPELINE COMPLET (via API - maintenant fonctionnel!)
curl -X POST "http://localhost:8000/api/v2/lands/${LAND_ID}/readable" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"limit": 10}' \
  --max-time 60

# 🔧 LOGS EN TEMPS RÉEL
docker-compose logs celery_worker --tail=20 -f

# ✅ RÉSULTATS ATTENDUS:
# - Content extraction avec Trafilatura + fallback Archive.org
# - Processing réussi avec logs détaillés
# - Extraction de 3000+ caractères de contenu readable
# - Durée: 15-20 secondes pour 2 URLs
# - Status: completed avec statistiques détaillées

# 📊 STATISTIQUES TYPIQUES:
# - processed: 2 URLs
# - successful: 1-2 selon le contenu disponible  
# - errors: 0-1 (example.com peut échouer)
# - readable_length: 3000+ caractères extraits
# - source: "archive_org" (fallback utilisé)
```

## 🐛 Débuggage Fréquent

### Erreurs SQL
- **Problème:** `should be explicitly declared as text()`
- **Solution:** Ajouter `from sqlalchemy import text` et wrapper les requêtes avec `text()`

### Erreurs de Modèle
- **Problème:** `'Land' object has no attribute 'user_id'`
- **Solution:** Utiliser `owner_id` au lieu de `user_id`

### Timeouts & Freeze
- **Problème:** L'analyse media timeout ou freeze (pas de réponse)
- **Cause:** Traitement lourd des images (PIL/sklearn) sur trop de médias
- **Solutions éprouvées:** 
  - **PRIORITÉ 1:** Utiliser `minrel: 3.0` ou plus pour réduire drastiquement le nombre d'expressions
  - Utiliser `depth: 0` pour analyser seulement les URLs initiales
  - Ajouter `--max-time 120` à curl pour éviter les timeouts infinis
  - Vérifier les logs Celery: `docker logs mywebintelligenceapi_celery_1`
  - Redémarrer le worker: `docker restart mywebintelligenceapi_celery_1`

### Résultats d'Analyse Typiques
- **Expressions totales:** ~1000+
- **Avec minrel=3.0:** ~2-5 expressions (filtrage très efficace)
- **Médias analysés:** 7-50 selon la pertinence
- **Échecs fréquents:** Images 404, SVG non supportés, URLs de tracking
- **Temps de traitement:** 60-120s avec filtrage, timeout sans filtrage

### 🚨 Problème URLs de Médias Incorrectes
- **Problème majeur:** URLs de médias générées incorrectement durant le crawl
- **Causes principales:**
  - Proxies WordPress (i0.wp.com, i1.wp.com) qui ne fonctionnent plus
  - URLs relatives mal résolues
  - Manque de validation d'URLs
  - Attributs alternatifs (srcset, data-src) ignorés
- **Solution:** Nouveau système de nettoyage d'URLs dans MediaProcessor
- **Impact:** Réduction drastique des erreurs 404 lors de l'analyse

### 🚨 PROBLÈME CRITIQUE : Dictionary Starvation - RÉSOLU ✅
- **Cause racine:** Lands créés sans dictionnaires de mots-clés peuplés
- **Symptômes:** 
  - Toutes les expressions ont pertinence = 0
  - Crawler suit tous les liens sans discrimination
  - Explosion du nombre d'expressions (1831 pour 10 URLs)
- **Impact:** Système de pertinence complètement cassé
- **Solution implémentée:** 
  - Auto-population des dictionnaires lors de la création des lands (`crud_land.py`)
  - Service `DictionaryService` pour gérer les dictionnaires
  - Endpoints `/populate-dictionary` et `/dictionary-stats` pour diagnostiquer
- **Code impacté:** `text_processing.expression_relevance()` retourne 0 si dictionnaire vide

### 🔧 Pipeline de Crawl - Logique des Timestamps ✅

**LOGIQUE STRICTE DES DATES (CRITIQUE) :**

1. **`created_at`** → Quand l'expression est **ajoutée en base** (découverte de l'URL)
   - Rempli automatiquement lors de l'INSERT
   - Permet de suivre l'ordre de découverte des URLs

2. **`crawled_at`** → Quand le **contenu HTTP a été récupéré** (fetch HTTP réussi)
   - Rempli après un GET HTTP réussi avec code HTTP valide
   - NULL si l'URL n'a jamais été fetchée

3. **`approved_at`** → Quand le crawler a **traité la réponse** (même si erreur)
   - ⚠️ **CRITÈRE DE SÉLECTION PRINCIPAL** : `approved_at IS NULL` = candidats au crawl
   - Rempli systématiquement après traitement (succès ou échec)
   - Marque l'expression comme "traitée par le crawler"

4. **`readable_at`** → Quand le **contenu readable** a été extrait et enregistré
   - Rempli après extraction réussie (Trafilatura/Mercury)
   - NULL si pas encore de contenu lisible

5. **`updated_at`** → Quand le contenu **readable a été modifié**
   - Mis à jour automatiquement à chaque modification de `readable`
   - Permet de tracker les re-extractions

**HTTP_STATUS - RÈGLE STRICTE :**

- **TOUJOURS** un code HTTP valide (200, 404, 500, etc.)
- **OU** `000` pour erreur inconnue non-HTTP (timeout, DNS, etc.)
- **JAMAIS** NULL après traitement

**WORKFLOW TYPIQUE :**

```text
1. Découverte URL     → created_at = NOW, approved_at = NULL, http_status = NULL
2. Fetch HTTP         → crawled_at = NOW, http_status = 200 (ou 404, etc.)
3. Traitement réponse → approved_at = NOW
4. Extraction readable → readable_at = NOW, updated_at = NOW
5. Modification readable → updated_at = NOW (updated_at > readable_at)
```

**REQUÊTE DE SÉLECTION DES CANDIDATS AU CRAWL :**

```sql
SELECT * FROM expressions
WHERE land_id = ?
  AND approved_at IS NULL  -- ⚠️ Clé principale !
  AND depth <= ?           -- Filtre optionnel de profondeur
ORDER BY depth ASC, created_at ASC
LIMIT ?
```

**Endpoints de diagnostic du pipeline:**
- `GET /api/v2/lands/{id}/pipeline-stats` - Statistiques complètes du pipeline
- `POST /api/v2/lands/{id}/fix-pipeline` - Répare les incohérences de dates

### Container Docker
- **Problème:** Changements de code non pris en compte
- **Solution:** `docker restart mywebintelligenceapi`

### Logs d'Analyse Média
- **IMPORTANT:** L'analyse média est **ASYNCHRONE** (avec Celery)
- **Logs à surveiller:** `docker logs mywebclient-celery_worker-1 -f`
- **Signaux d'activité:** 
  - `sklearn.base.py:1152: ConvergenceWarning` = Clustering couleurs dominantes
  - `PIL/Image.py:975: UserWarning` = Traitement d'images avec transparence
  - Task terminé avec succès dans les logs Celery

## 📊 Données de Test

### Land 36 "giletsjaunes"
- **ID:** 36
- **URLs:** Blogs gilets jaunes (over-blog.com, etc.)
- **Contenu:** Articles sur le mouvement
- **Médias:** ~850 images selon les stats mockées

### Autres Lands
- **37, 38, 39:** Lands de test avec URLs example.com
- **40:** Land basique avec example.org
- **41:** Autre land gilets jaunes

## 🔧 Technologies

### Backend
- **FastAPI** - Framework web moderne avec validation automatique
- **SQLAlchemy 2.0** - ORM async avec modèles déclaratifs
- **PostgreSQL 15+** - Base de données relationnelle
- **Celery** - Tâches asynchrones distribuées 
- **Redis** - Broker Celery et cache

### Analyse Media
- **PIL/Pillow** - Traitement d'images (dimensions, format, EXIF)
- **OpenCV** - Vision par ordinateur avancée
- **scikit-learn** - Machine learning (clustering couleurs dominantes)
- **httpx** - Client HTTP asynchrone pour téléchargement

### Architecture Async
- **AsyncSession** - Connexions DB non-bloquantes
- **async/await** - Gestion asynchrone des tâches lourdes
- **WebSocket** - Suivi temps réel des jobs

### Containerisation
- **Docker Compose** - Orchestration multi-services
- **Services:** API, Celery Worker, PostgreSQL, Redis, Flower (monitoring)
- **Volumes persistants** - Données et logs
- **Network isolation** - Sécurité inter-services

### Installation & Configuration
```bash
# Installation complète avec Docker
git clone <repository-url>
cd MyWebIntelligenceAPI
cp .env.example .env           # Configurer DATABASE_URL, REDIS_URL, SECRET_KEY
docker-compose up -d           # Lancer tous les services
docker-compose exec api alembic upgrade head    # Migrations DB

# Accès services
# API: http://localhost:8000
# Docs: http://localhost:8000/docs  
# Flower: http://localhost:5555
# Prometheus: http://localhost:9090
# Grafana: http://localhost:3001
```

### Variables d'Environnement Critiques
```bash
# Base de données
DATABASE_URL=postgresql://user:pass@postgres:5432/mywebintelligence

# Cache/Queue  
REDIS_URL=redis://redis:6379

# Sécurité
SECRET_KEY=<générer-clé-aléatoire-64-chars>
FIRST_SUPERUSER_EMAIL=admin@example.com
FIRST_SUPERUSER_PASSWORD=changethispassword

# API Externe (optionnel)
OPENROUTER_API_KEY=<pour-analyse-sémantique>
```

---

## 🚀 TEST RAPIDE COMPLET - SCRIPT AUTOMATISÉ

### 🔥 Script de Test Robuste Anti-Erreurs (2 minutes)

```bash
#!/bin/bash
# Test complet crawl + analyse média ASYNC Celery - AGENTS.md
# Version robuste qui évite les pièges courants

# Fonction pour renouveler le token (expire rapidement)
get_fresh_token() {
    TOKEN=$(curl -s -X POST "http://localhost:8000/api/v1/auth/login" \
      -H "Content-Type: application/x-www-form-urlencoded" \
      -d "username=admin@example.com&password=changeme" | jq -r .access_token)
    if [ "$TOKEN" = "null" ] || [ -z "$TOKEN" ]; then
        echo "❌ Échec authentification"
        exit 1
    fi
}

echo "🔧 1/7 - Vérification serveur..."
if ! curl -s -w "%{http_code}" "http://localhost:8000/" -o /dev/null | grep -q "200"; then
    echo "❌ Serveur API non accessible. Lancez: docker compose up -d"
    exit 1
fi

echo "🔑 2/7 - Authentification..."
get_fresh_token
echo "✅ Token obtenu: ${TOKEN:0:20}..."

echo "🏗️ 3/7 - Création land avec URLs intégrées..."
# ASTUCE: URLs directement dans start_urls (l'endpoint /urls est bugué)
LAND_ID=$(curl -s -X POST "http://localhost:8000/api/v2/lands/" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"name":"test_complet_media","description":"Test crawl + analyse média","start_urls":["https://www.lemonde.fr/politique/article/2025/10/11/emmanuel-macron-maintient-sebastien-lecornu-a-matignon-malgre-l-hostilite-de-l-ensemble-de-la-classe-politique_6645724_823448.html"]}' | jq -r '.id')

if [ "$LAND_ID" = "null" ] || [ -z "$LAND_ID" ]; then
    echo "❌ Échec création land"
    exit 1
fi
echo "✅ Land créé: LAND_ID=$LAND_ID"

echo "📝 4/7 - Ajout mots-clés (OBLIGATOIRE pour pertinence)..."
get_fresh_token  # Token peut expirer
curl -s -X POST "http://localhost:8000/api/v2/lands/${LAND_ID}/terms" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"terms": ["lecornu", "sebastien", "macron", "matignon"]}' > /dev/null

echo "🕷️ 5/7 - Lancement crawl..."
get_fresh_token  # Renouveler avant chaque action importante
CRAWL_RESULT=$(curl -s -X POST "http://localhost:8000/api/v2/lands/${LAND_ID}/crawl" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"limit": 3}' --max-time 60)

JOB_ID=$(echo "$CRAWL_RESULT" | jq -r '.job_id')
if [ "$JOB_ID" = "null" ] || [ -z "$JOB_ID" ]; then
    echo "❌ Échec crawl: $CRAWL_RESULT"
    exit 1
fi
echo "✅ Crawl lancé: JOB_ID=$JOB_ID"

echo "⏳ 6/7 - Attente crawl (45s)..."
sleep 45

echo "🎨 7/8 - Test analyse média ASYNC avec Celery..."
get_fresh_token  # Token frais pour dernière étape
ASYNC_RESULT=$(curl -s -X POST "http://localhost:8000/api/v2/lands/${LAND_ID}/media-analysis-async" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"depth": 0, "minrel": 0.0}')

ASYNC_JOB_ID=$(echo "$ASYNC_RESULT" | jq -r '.job_id')
CELERY_TASK_ID=$(echo "$ASYNC_RESULT" | jq -r '.celery_task_id')

if [ "$ASYNC_JOB_ID" = "null" ]; then
    echo "❌ Échec analyse async: $ASYNC_RESULT"
    exit 1
fi

echo "✅ Analyse média ASYNC lancée:"
echo "  - Job ID: $ASYNC_JOB_ID"
echo "  - Celery Task: $CELERY_TASK_ID"

echo "📖 8/8 - Test pipeline Readable (NOUVEAU)..."
get_fresh_token  # Token frais pour dernière étape
READABLE_RESULT=$(curl -s -X POST "http://localhost:8000/api/v2/lands/${LAND_ID}/readable" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"limit": 5, "depth": 1, "merge_strategy": "smart_merge"}' \
  --max-time 120)

READABLE_JOB_ID=$(echo "$READABLE_RESULT" | jq -r '.job_id')
READABLE_TASK_ID=$(echo "$READABLE_RESULT" | jq -r '.celery_task_id')

if [ "$READABLE_JOB_ID" = "null" ]; then
    echo "❌ Échec pipeline readable: $READABLE_RESULT"
    # Ne pas exit ici, c'est un test de la nouvelle fonctionnalité
else
    echo "✅ Pipeline Readable lancé:"
    echo "  - Job ID: $READABLE_JOB_ID"
    echo "  - Celery Task: $READABLE_TASK_ID"
fi

echo ""
echo "📋 SUIVI LOGS CELERY (20s):"
echo "docker logs mywebclient-celery_worker-1 --tail=10 -f"
echo ""
docker logs mywebclient-celery_worker-1 --tail=10 -f &
TAIL_PID=$!
sleep 20
kill $TAIL_PID 2>/dev/null

echo ""
echo "🎯 RÉSUMÉ FINAL:"
echo "- Land ID: $LAND_ID"
echo "- Crawl Job: $JOB_ID"
echo "- Media Analysis Job: $ASYNC_JOB_ID" 
echo "- Readable Processing Job: $READABLE_JOB_ID"
echo "- Celery Tasks: $CELERY_TASK_ID, $READABLE_TASK_ID"
echo ""
echo "🔍 Commandes utiles:"
echo "# Statut job: curl -H \"Authorization: Bearer \$TOKEN\" \"http://localhost:8000/api/v2/jobs/${ASYNC_JOB_ID}\""
echo "# Statut readable: curl -H \"Authorization: Bearer \$TOKEN\" \"http://localhost:8000/api/v2/jobs/${READABLE_JOB_ID}\""
echo "# Stats land: curl -H \"Authorization: Bearer \$TOKEN\" \"http://localhost:8000/api/v2/lands/${LAND_ID}/stats\""
echo "# Logs Celery: docker logs mywebclient-celery_worker-1 --tail=20 -f"
```

### Utilisation Rapide
```bash
# Copier-coller et exécuter :
curl -s https://raw.githubusercontent.com/MyWebIntelligence/scripts/test-complet.sh | bash

# OU créer le fichier localement :
# 1. Copier le script ci-dessus dans test-crawl.sh
# 2. chmod +x test-crawl.sh && ./test-crawl.sh
```

## 🐛 CORRECTIONS CRITIQUES AGENTS - Leçons Apprises

### ❌ **Erreurs Fréquentes à Éviter**

#### 1. **Bug job_id** (RÉSOLU)
- **Problème** : `job_id should be a valid integer [input_value=None]`
- **Cause** : `/app/api/v2/endpoints/lands_v2.py:582` cherchait `"id"` au lieu de `"job_id"`
- **Fix** : `job_payload.get("id")` → `job_payload.get("job_id")`

#### 2. **Tokens JWT Expirent Rapidement** ⚠️
- **Problème** : `Could not validate credentials` après quelques minutes
- **Solution** : Fonction `get_fresh_token()` avant chaque appel critique
- **Astuce** : Renouveler systématiquement avant crawl/analyse

#### 3. **Endpoint `/urls` Bugué** ⚠️
- **Problème** : Impossible d'ajouter URLs après création land
- **Solution** : URLs directement dans `start_urls` lors de création
- **Éviter** : `POST /api/v2/lands/{id}/urls`

#### 4. **Analyse Média : Utiliser UNIQUEMENT l'Endpoint ASYNC** ⚠️
- **UTILISER** : `/media-analysis-async` (asynchrone, recommandé, logs Celery visibles)
- **NE PAS UTILISER** : `/media-analysis` (synchrone, déprécié, peut timeout)
- **Logs Celery** : `docker logs mywebclient-celery_worker-1 --tail=20 -f`

#### 5. **Mots-clés Obligatoires** ⚠️
- **Problème** : Sans mots-clés, `relevance=0` pour toutes expressions
- **Solution** : Toujours ajouter termes via `/terms` après création land
- **Impact** : Détermine filtrage pertinence dans analyse média

#### 6. **DEPTH = Niveau de Crawl** 🔥 **CRITIQUE**
- **`depth: 0`** = Analyser médias des **start_urls** seulement
- **`depth: 1`** = Analyser médias des **liens directs** depuis start_urls
- **`depth: 2`** = Analyser médias des **liens de liens** (2e niveau)
- **`depth: 999`** = Analyser **TOUS** les médias sans limite de profondeur
- **⚠️ BUG ENDPOINT** : L'endpoint `/media-analysis-async` ignore le paramètre `depth` et force toujours `depth: 999`

### 🎯 **Workflow Anti-Erreurs**

```bash
1. ✅ Créer land avec start_urls intégrées (pas d'endpoint /urls)
2. ✅ Ajouter termes OBLIGATOIREMENT  
3. ✅ Renouveler token avant chaque action
4. ✅ Utiliser /media-analysis-async (pas /media-analysis)
5. ✅ Suivre logs Celery pour vérifier traitement
6. ✅ Attendre suffisamment (45s crawl, 20s+ analyse)
```

---

## 🧪 Tests Manuels Détaillés

### Test 1 : Authentification
```bash
TOKEN=$(curl -s -X POST "http://localhost:8000/api/v1/auth/login" \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=admin@example.com&password=changeme" | jq -r .access_token)
echo "Token: $TOKEN"
```

### Test 2 : Création Land Complète
```bash
# Land avec URLs intégrées (évite l'endpoint /urls bugué)
LAND_ID=$(curl -s -X POST "http://localhost:8000/api/v2/lands/" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "test_fonctionnel", 
    "description": "Test crawl fonctionnel",
    "start_urls": ["https://httpbin.org/html", "https://example.com"],
    "words": ["test", "example"]
  }' | jq -r '.id')
echo "Land créé: $LAND_ID"
```

### Test 3 : Ajout Mots-clés (Obligatoire pour pertinence)
```bash
curl -X POST "http://localhost:8000/api/v2/lands/${LAND_ID}/terms" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"terms": ["html", "test", "example", "title"]}'
```

### Test 4 : Crawl Simple
```bash
curl -X POST "http://localhost:8000/api/v2/lands/${LAND_ID}/crawl" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"limit": 3}' --max-time 120
```

### Test 5 : Analyse Média (ASYNC)
```bash
# Analyse rapide (expressions très pertinentes seulement)
curl -X POST "http://localhost:8000/api/v2/lands/${LAND_ID}/media-analysis-async" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"depth": 0, "minrel": 3.0}'

# Analyse complète (toutes expressions)  
curl -X POST "http://localhost:8000/api/v2/lands/${LAND_ID}/media-analysis-async" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"minrel": 0.0}'
```

## 🧭 Scénario d'Usage Complet

### Script de Test Automatisé
Le script `scripts/land_scenario.py` reproduit l'ancien workflow CLI :

```bash
python scripts/land_scenario.py \
  --land-name "MyResearchTopic" \
  --terms "keyword1,keyword2" \
  --urls "https://example.org,https://example.com" \
  --crawl-limit 25
```

**Variables d'environnement:**
- `MYWI_BASE_URL` (défaut: `http://localhost:8000`)  
- `MYWI_USERNAME` / `MYWI_PASSWORD` (défaut: `admin@example.com` / `changeme`)

### Migration depuis SQLite
```bash
# Migration d'une base SQLite existante
python scripts/migrate_sqlite_to_postgres.py --source /path/to/mwi.db
```

# MyWebIntelligenceAPI Architecture

This document outlines the architecture of the MyWebIntelligenceAPI codebase and the runtime responsibilities of each module.

## 1. Repository Layout
- `app/` FastAPI application package (described in section 2).
- `scripts/` Operational tooling split into `manual/` CLI flows for API smoke tests, `admin/` bootstrap helpers such as `create_admin.py`, `config/` for ops configuration (`prometheus.yml`), `data/` fixture URL lists, and single-file utilities (`delete_all_lands.py`, `land_scenario.py`, `verify_legacy_parity.py`, `get_crawl_status.py`, `medianalyse.py`).
- `tests/` Automated suites grouped by scope (`unit/`, `integration/`, `legacy/`, `api/`, `performance/`, `robustness/`), plus `manual/` smoke scripts and `data/test.db` fixtures.
- `alembic/` Alembic environment and migration scripts; `migrations/` stores legacy artefacts.
- `_legacy/` Historical experiments and deprecated tooling kept for reference.
- `exports/` and `exports_demo/` Example export outputs generated by jobs.
- `.claude/` Team documentation snapshots and per-environment settings; `.memory/` long-form design notes and ADR-style records.
- Project tooling lives at the root: `Dockerfile`, `README.md`, `.env.example`, `pytest.ini`, and `requirements.txt`.

## 2. Application Package (`app/`)

### 2.1 Entry Points
- `main.py` Composes the FastAPI app, wires middleware, and mounts the versioned routers.
- `config.py` Centralises runtime configuration sourced from environment variables.
- `core/celery_app.py` Exposes the Celery instance used by asynchronous workers.

### 2.2 API Layer (`app/api`)
- `router.py` Registers the versioned routers and shared middleware.
- `dependencies.py` Provides FastAPI dependencies (database session, current user, pagination helpers).
- `versioning.py` Implements header-based API negotiation; `deprecation.py` surfaces sunset headers for clients.
- `v1/` Stable endpoints inside `endpoints/` grouped by resource (`lands.py`, `jobs.py`, `auth.py`, `export.py`, `paragraphs.py`, `tags.py`, `websocket.py`).
- `v2/` Iterative endpoints with revised contracts (`lands_v2.py`, `export_v2.py`, `paragraphs.py`) exposed through a dedicated router.

### 2.3 Core Modules (`app/core`)
- Crawling and extraction: `crawler_engine.py` (async), `crawler_engine_sync.py`, `content_extractor.py`, `http_client.py`.
- Media analysis: `media_processor.py`, `media_processor_sync.py` handle metadata enrichment and media-specific heuristics.
- Readable content: `readable_db.py`, `readable_simple.py`, and `websocket.py` support the readable pipeline and live updates.
- Security and configuration: `security.py` for auth helpers, `settings.py` for strongly-typed settings.
- Text analytics: `text_processing.py` streamlines scoring, dictionary operations, and paragraph generation.
- Embeddings: `embedding_providers/` defines `base_provider.py`, `registry.py`, `openai_provider.py`, and `mistral_provider.py` for pluggable vector generators.

### 2.4 Persistence Layer
- `db/` SQLAlchemy models (`models.py`), metadata (`base.py`), async session plumbing (`session.py`), and DB-level helpers (`schemas.py`).
- `crud/` Repository-style helpers aligned with each model (`crud_land.py`, `crud_expression.py`, `crud_media.py`, etc.) plus `base.py` for shared patterns.
- `schemas/` Pydantic models that validate and serialise API payloads for lands, jobs, users, paragraphs, tags, media, and authentication.

### 2.5 Domain Services (`app/services`)
- Orchestration modules encapsulating business logic: `crawling_service.py`, `dictionary_service.py`, `embedding_service.py`, `export_service.py`, `export_service_sync.py`, `llm_validation_service.py`, `media_link_extractor.py`, `readable_service.py`, `readable_celery_service.py`, `readable_simple_service.py`, and `text_processor_service.py`.
- Services coordinate between API handlers, CRUD helpers, core utilities, and background workers.

### 2.6 Task Queue (`app/tasks`)
- Crawl and readable orchestration: `crawling_task.py`, `media_analysis_task.py`, `readable_task.py`, `readable_working_task.py`, `readable_test_task.py`.
- NLP and embeddings: `embedding_tasks.py`, `text_processing_tasks.py`.
- Exports and consolidation: `export_task.py`, `export_tasks.py`, `consolidation_task.py`.

### 2.7 Utilities
- `utils/` Shared helpers such as structured logging (`logging.py`) and text helpers (`text_utils.py`).

## 3. API Versioning and Lifecycles
- `api/versioning.py` inspects `Accept` headers to route requests to `v1` or `v2`, falling back to the stable version when unspecified.
- `api/deprecation.py` emits warning headers for sunsetted routes and guides clients toward replacements.
- Version 1 remains the stable contract; version 2 introduces refined land and export endpoints while new features bed in.

## 4. Background Execution Model
- Celery workers import `core/celery_app.py`, registering all modules under `app/tasks`.
- Long-running jobs persist state in the `Job` model via CRUD helpers and stream status updates through websocket broadcasts (`core/websocket.py`) and polling endpoints (`api/v1/endpoints/jobs.py`).
- Services enqueue work with contextual metadata, ensuring traceability across pipelines and simplifying job orchestration.

## 5. Functional Pipelines
- **Crawling** `services/crawling_service.py` prepares targets, `tasks/crawling_task.py` feeds URLs into `core/crawler_engine.py`, and results persist through CRUD modules with live status updates.
- **Readable Content** `services/readable_service.py` and `readable_celery_service.py` trigger `tasks/readable_task.py` and `readable_working_task.py`, relying on `core/content_extractor.py`, Trafilatura fallbacks, and `core/readable_db.py`.
- **Media Analysis** `tasks/media_analysis_task.py` delegates to `core/media_processor.py` to enrich expressions with media metadata.
- **Embeddings** `services/embedding_service.py` dispatches `tasks/embedding_tasks.py`, which invoke providers in `core/embedding_providers/` and persist vectors via paragraph CRUD helpers.
- **Exports** `tasks/export_task.py` and `export_tasks.py` call into `services/export_service.py` to build archive artefacts under `exports/` or `exports_demo/`.

## 6. Testing and Diagnostics
- Automated tests live in `tests/` with dedicated directories for unit, integration, API regression, robustness, and performance suites; `tests/legacy/` preserves earlier workflows for parity checks.
- Python smoke scripts (`tests/manual/`) and Bash-based validation flows (`scripts/manual/`) provide reproducible end-to-end diagnostics for developers.
- Shared fixtures (`tests/data/test.db`) and helpers (`tests/utils.py`) consolidate setup logic, keeping suites consistent with production behaviours.
