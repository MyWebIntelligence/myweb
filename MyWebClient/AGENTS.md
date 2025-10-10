# AGENTS — MyWebClient Knowledge Base

## 1. Mission & Snapshot
- MyWebClient est une application full-stack (React + Node/Express) offrant une interface d'exploration, d'édition et d'annotation de données issues de MyWebIntelligencePython.
- Deux bases SQLite locales sont utilisées: `mwi.db` (données métier: lands, expressions, tags, domaines, médias) et `admin.db` (authentification, logs d'accès, tokens de reset).
- L'API Express expose des endpoints REST sous `/api` pour la data métier et `/api/auth` pour l'auth JWT. Aucune dépendance active vers la nouvelle API FastAPI/Postgres.
- Extraction "readable" (Markdown) via `@postlight/mercury-parser`. Authentification par JWT stocké côté client.

## 2. Architecture & Arborescence clef
- `client/` : frontend React (create-react-app)
  - `src/index.js` point d'entrée, `src/app/Context.js` contexte global, `src/app/Util.js` utilitaires.
  - `src/components/App/App.js` composant racine (état global + auth) avec `MainApp` pour la logique principale.
  - Modules majeurs: `DatabaseLocator/` (connexion DB), `LandExplorer/`, `ExpressionExplorer/`, `Domain/`, `TagExplorer/`, `Auth/` (Login/Forgot/Reset).
- `server/` : backend Node/Express
  - `src/start.js` (bootstrap serveur + static build), `src/authRoutes.js`, `src/DataQueries.js`, `src/AdminDB.js`, `src/initAdmin.js`, `src/migrations_auth.sql`.
- Racine: `package.json` (monorepo scripts yarn), `Dockerfile`, `README.md`, fichiers .env éventuels.

## 3. Pile technique & dépendances
- Node 20 (cf. Dockerfile `node:20-alpine`), Yarn 1.x (classic).
- Backend: express, body-parser, dotenv, sqlite3, bcrypt, jsonwebtoken, @postlight/mercury-parser, resend (optionnel), nodemon, @babel/core + preset-env.
- Frontend: React (CRA), FontAwesome, tests via `react-scripts test`, service worker optionnel.
- Conteneurisation: Docker (build client puis `yarn server`).

## 4. Données & variables d'environnement
- `mwi.db` : schéma historique attendu (`land`, `expression`, `domain`, `media`, `tag`, `taggedContent`, `expressionlink`). Ne pas renommer les colonnes (ex: `taggedContent` camelCase, `media.type`).
- `admin.db` : géré par `AdminDB.js` (utilisateurs, tentatives échouées, tokens de reset, logs d'accès, statut bloqué).
- Variables supportées :
  - `PORT` (par défaut 3000, recommander 5001 en dev pour éviter conflit CRA).
  - `ADMIN_PASSWORD` (optionnel, mot de passe initial admin; sinon généré, logué et écrit dans `admin_password.txt`).
  - `JWT_SECRET` (défaut `jwt_super_secret_key`, à surcharger en prod).
  - `RESEND_API_KEY` (optionnel, active l'envoi d'e-mails pour `/api/auth/recover`, sinon 501 explicite).

## 5. Mise en route & exécution
### 5.1 Développement local (sources)
1. Créer/modifier `.env` à la racine avec `PORT=5001` (évite conflit avec le dev-server React).
2. `yarn install` (installe aussi `client/` via postinstall).
3. `yarn standalone` (lance backend + frontend). Sinon `yarn server` ou `yarn client` séparément.
4. Dans l'UI, via `DatabaseLocator`, appeler `/api/connect` avec le chemin absolu de `mwi.db` (ex: `/path/.../Data/mwi.db`).
5. Se connecter avec `admin` + mot de passe (voir `admin_password.txt` si généré).

### 5.2 Docker (prod simplifiée ou démo)
1. `docker build -t mwiclient:1.0 .`
2. `docker run -p 80:3000 --name mwiclient -v /chemin/MyWebIntelligencePython/Data:/data -e ADMIN_PASSWORD=MonSecret mwiclient:1.0`
3. Accéder à `http://localhost`, connecter `/data/mwi.db` via l'UI.
4. Optionnel: exposer un port backend distinct (`-p 5001:5001`) si `PORT` différent.
5. `RESEND_API_KEY` peut être fourni pour activer la récupération de mot de passe.

### 5.3 Commandes utiles
- `yarn server` (init admin puis `nodemon babel-node`).
- `yarn client` (CRA dev server sur 3000).
- `yarn standalone` (les deux simultanément).
- Docker: `docker logs mwiclient`, `docker exec mwiclient cat /app/admin_password.txt`.

## 6. Backend API — panorama
> Les routes métier renvoient 503 tant que `/api/connect` n'a pas été appelé avec succès.

### 6.1 Connexion base
- `GET /api/connect?db=/chemin/vers/mwi.db` → `true`/`false`. Normalise les chemins Windows, active `PRAGMA foreign_keys=ON`.

### 6.2 Lands & expressions
- `GET /api/lands` → liste `{id, name}`.
- `GET /api/land?id=LAND_ID&minRelevance=0&maxDepth=3` → métadonnées land + `expressionCount` filtré.
- `GET /api/expressions?landId=ID&minRelevance=&maxDepth=&offset=0&limit=50&sortColumn=e.id|e.title|e.relevance|e.depth|d.name&sortOrder=1|-1` → liste paginée (id, title, url, httpStatus, relevance, domain*, tagCount).
- `GET /api/expression?id=EXPR_ID` → détail complet (domain, images via `media.type='img'`, readable, relevance, depth...).
- `GET /api/prev` / `GET /api/next` avec les mêmes filtres/tri que la liste pour naviguer séquentiellement.
- `GET /api/deleteExpression?id=ID` (support multi-ID) → suppression expression + media + expressionlink.

### 6.3 Readable & médias
- `GET /api/readable?id=EXPR_ID` → récupère et convertit avec Mercury (peut renvoyer 500 si fetch/parse échoue).
- `POST /api/readable { id, content }` → `expression.readable` + `readable_at` mis à jour.
- `POST /api/deleteMedia { url, expressionId }` → supprime une entrée média.

### 6.4 Tags & contenu taggé
- `GET /api/tags?landId=LAND_ID` → arbre complet (CTE récursif, `expanded=true`).
- `POST /api/tags { landId, tags:[...] }` → transaction: upsert tags existants, insertion nouveaux, suppression manquants; `sorting` basé sur l'ordre fourni.
- `POST /api/updateTag { id, name, color }` → mise à jour unitaire.
- `POST /api/tagContent { tagId, expressionId, text, start, end }` → création segment.
- `POST /api/updateTagContent { contentId, tagId, text }` → mise à jour.
- `GET /api/taggedContent?expressionId=...` ou `?landId=...` [`&tagId=...`] → lecture.
- `GET /api/deleteTaggedContent?id=ID` → suppression segment.

### 6.5 Domaines
- `GET /api/domain?id=DOMAIN_ID` → métadonnées + `expressionCount` associé.

### 6.6 Authentification
- `POST /api/auth/login { identifier, password }` → `{ success, token, user:{ id, username, role, last_session } }`.
- `GET /api/auth/me` (JWT Bearer) → infos utilisateur.
- `POST /api/auth/logout` → hérité (détruit session si middleware présent, inoffensif sinon).
- `POST /api/auth/recover { email }` → génère token reset (501 si `RESEND_API_KEY` manquant).
- `POST /api/auth/reset { token, newPassword }` → vérifie regex (>=8, a-z, A-Z, chiffre, spécial) puis met à jour le hash.

### 6.7 Codes d'erreur typiques
- 400 paramètres invalides/manquants, 404 ressource absente, 500 erreur SQL/serveur, 501 fonctionnalité non configurée, 503 base non connectée, 401/403 côté auth.

## 7. Frontend — carte des composants & état global
- `Context.js` centralise `auth`, `db`, `lands`, `filters`, `sorting`, `pagination`, `currentExpression`, `currentReadable`, `tagTree`, `pendingTree`, `currentDomain`.
- `App/App.js` gère l'auth (token en localStorage), route vers `MainApp` après login.
- `DatabaseLocator` pilote `/api/connect` et stocke `dbPath` / `isConnected`.
- `LandExplorer` (avec `FilterSlider`, `LandFilters`) règle `minRelevance`, `maxDepth`, offset/limit, tri.
- `ExpressionExplorer` + `Expression` couvrent la liste, l'édition du readable, la navigation Prev/Next, la suppression, les médias.
- `TagExplorer` (TreeRenderer, TagRenderer, TaggedContent) gère l'arbre, la transaction de sauvegarde, et les segments taggés.
- `Domain/Domain.js` affiche les détails domaine.
- Modules Auth (`Login`, `ForgotPassword`, `ResetPassword`) consomment `/api/auth/*`.

## 8. Pipelines opérationnels clés (voir `.memory-bank/PIPELINES.md` pour le détail)
1. **Connexion DB** : `DatabaseLocator` → `GET /api/connect` → maj `isConnected`. Retour `false` n'est pas une erreur HTTP.
2. **Authentification** : `Login` → `POST /api/auth/login` → stockage token, `GET /api/auth/me` sur chargement, `/auth/logout` pour nettoyer côté client.
3. **Lands & expressions** : enchaînement `GET /api/land` puis `GET /api/expressions`. Paramètres obligatoires alignés avec l'état Context (relevance/depth/sort/pagination).
4. **Expression detail** : `GET /api/expression`, `GET /api/readable`, `POST /api/readable`, navigation `/api/prev|next`, suppression `/api/deleteExpression`.
5. **Tags** : `GET /api/tags`, `POST /api/tags` (transaction), `POST /api/updateTag`.
6. **Tagged content** : création (`POST /api/tagContent`), lecture (`GET /api/taggedContent`), mise à jour, suppression.
7. **Domaines** : `GET /api/domain` par sélection d'expression.
8. **Médias** : `POST /api/deleteMedia` depuis `Expression.js`.
9. **Mot de passe oublié** : `POST /api/auth/recover` (dépend de `RESEND_API_KEY`), `POST /api/auth/reset`.
10. **Initialisation admin** : `yarn server` exécute `initAdmin.js` avant le serveur; crée `admin` si absent, écrit le mot de passe généré.
11. **Gestion erreurs & logs** : DataQueries journalise requêtes, counts supprimés, prev/next; AdminDB trace les logs d'accès.

## 9. Auth & sécurité
- JWT signé avec `JWT_SECRET`, expiration 7 jours (dur dans le code). Prévoir durcissement en prod (secret fort, rotation éventuelle).
- `AdminDB` gère le blocage temporaire après tentatives échouées (`incrementFailedAttempts` vs `maxAttempts`).
- Tokens de reset stockés avec expiration (1h) via `setResetToken` / `findUserByResetToken`.
- `RESEND_API_KEY` absent → `/auth/recover` retourne 501 (comportement attendu, l'app ne plante pas).
- SQL sécurisé via placeholders `?` et whitelist sur `sortColumn` (`validateSortColumn`).
- Relique session (`req.session.destroy`) dans `/logout` inoffensif car middleware session absent.

## 10. Pièges connus & bonnes pratiques
- Toujours appeler `/api/connect` avant toute action data, sinon 503.
- Eviter le conflit de port 3000/3000 : configurer `PORT=5001` pour le backend en dev.
- Conserver les filtres/tri synchronisés entre la liste et la navigation Prev/Next (sinon résultats incohérents).
- Ne pas tenter d'utiliser le schéma Postgres de la nouvelle API : MyWebClient attend la nomenclature SQLite historique.
- `getReadable` dépend d'un fetch externe (Mercury) : prévoir des erreurs réseau/anti-bot; afficher des retours utilisateur clairs.
- Sauvegarde de l'arbre de tags : opter pour des batchs raisonnables, l'endpoint réalise INSERT/UPDATE/DELETE nombreux.
- JWT & secrets : définir des valeurs robustes en prod; envisager de rendre `JWT_EXPIRES_IN` configurable (backlog).

## 11. Checklists opératoires
### Dev (sources)
- [ ] `.env` avec `PORT=5001` (ou port libre).
- [ ] `yarn install`.
- [ ] (Optionnel) `ADMIN_PASSWORD` défini avant `yarn standalone`.
- [ ] `/api/connect` vers le bon chemin `mwi.db` via l'UI.
- [ ] Connexion `admin` + mot de passe (fichier `admin_password.txt` si besoin).

### Docker (prod simple)
- [ ] `docker build -t mwiclient:1.0 .`
- [ ] `docker run -p 80:3000 -v /chemin/Data:/data -e ADMIN_PASSWORD=... mwiclient:1.0`.
- [ ] UI accessible sur `http://localhost`, connexion `/data/mwi.db`.
- [ ] (Optionnel) `RESEND_API_KEY` pour mails reset.

## 12. Feuille de route — Migration vers MyWebIntelligenceAPI (PRD Draft)
- Objectif cible : MyWebClient devient client de MyWebIntelligenceAPI (FastAPI + Postgres + jobs Celery/Redis) en conservant les features UI.
- Approche recommandée :
  - **Phase 0** : aligner les contrats API, décider BFF vs SPA directe.
  - **Phase 1** : introduire un BFF Node/Express proxy `/api/client/*` → `/api/v1/*`, gérer auth (cookie httpOnly), mapper les endpoints existants, retirer `DatabaseLocator`, ajouter panneau Jobs/Exports.
  - **Phase 2** : durcir sécurité (cookies Secure/SameSite), améliorer gestion erreurs, ajouter tests intégration/E2E, gérer téléchargements d'exports.
  - **Phase 3** : optionnel, migration SPA directe si CORS et sécurité le permettent.
- Nouveaux besoins : suivi des jobs (crawl/consolidate/export) en temps réel via WS, configuration `API_BASE_URL` / `WS_URL`, gestion des gaps API (readable update, delete media, arbre de tags complet, etc.).
- Exigence process : tout dev/test devra passer par l'environnement Docker commun (`docker-compose` multi-services) avant PR.

## 13. Références complémentaires
- `README.md` : documentation générale et commandes.
- `.clinerules/memory-bank.md` : contexte détaillé (architecture, bonnes pratiques, backlog).
- `.memory-bank/PIPELINES.md` : séquences complètes UI → API (paramètres, erreurs, futur travaux).
- `.memory-bank/CLAUDE.md` & `init CLAUDE.md` : guides de démarrage rapide pour les agents.
- `.memory-bank/PRD-Upgrade-MyWebClient-to-MyWebIntelligenceAPI.md` : vision long terme, exigences Docker-first.
- Dockerfile & scripts Yarn : point de vérité pour versions Node/Yarn et démarrage automatisé.

