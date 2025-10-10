# Memory Bank — MyWebClient (Contexte de démarrage pour développement)

Objectif de ce fichier
- Fournir à l’agent (Cline) un contexte minimal mais complet pour intervenir sans se tromper dans l’application MyWebClient.
- Remplacer l’ancien “banque mémoire” générique: ici, pas de dossier memory-bank/ séparé, ce fichier tient lieu de mémoire initiale.

TL;DR
- MyWebClient = client React + backend Node/Express + 2 bases SQLite:
  1) Base “métier” (SQLite) issue de MyWebIntelligencePython (lands, expressions, domaines, tags…).
  2) Base “admin” (SQLite) interne pour utilisateurs/auth (admin.db).
- Le backend Express expose des endpoints REST simples qui lisent/écrivent dans la base SQLite “métier”.
- Authentification avec JWT (pas de session côté serveur).
- Extraction “readable” possible via Mercury Parser, stockable en base.
- Ports: server écoute par défaut sur 3000 (voir .env). En mode “standalone” (yarn), prévoir ajustement pour éviter conflit avec le dev-server React.

Sommaire
1) Architecture et périmètre
2) Démarrage & environnements
3) Variables d’environnement
4) API backend — endpoints & contrats
5) Schéma et attentes sur la base SQLite “métier”
6) Authentification & sécurité
7) Frontend (React) — composants clés
8) Dépendances & versions
9) Pièges connus & bonnes pratiques
10) Checklist de démarrage (dev & prod)
11) Éléments à ne PAS confondre (SQLite vs API FastAPI)
12) Backlog / idées d’amélioration (non bloquant)

----------------------------------------
1) Architecture et périmètre
----------------------------------------
- Dossier: MyWebClient/
  - server/ (Node.js + Express)
    - src/start.js (point d’entrée serveur)
    - src/authRoutes.js (routes d’auth, JWT)
    - src/DataQueries.js (accès à la base SQLite “métier”)
    - src/AdminDB.js (accès DB auth — non détaillé ici mais conceptuellement: utilisateurs, tokens reset, logs d’accès)
  - client/ (React — create-react-app)
    - src/components/... (LandExplorer, ExpressionExplorer, TagExplorer, Domain, Auth)
- Rôle: interface d’exploration/édition sur base SQLite générée par “MyWebIntelligencePython”. 
- Hors scope: la nouvelle API FastAPI (MyWebIntelligenceAPI) en Postgres; MyWebClient ne parle pas à cette API.

----------------------------------------
2) Démarrage & environnements
----------------------------------------
- Option 1: Source (dev)
  - Pré-requis: Node 20 (Dockerfile: node:20-alpine), Yarn 1.x (classic).
  - À la racine MyWebClient: 
    - yarn install (installe aussi client via postinstall)
    - yarn standalone (lance “server” et “client” en parallèle)
  - Conflit de port possible: par défaut, server et client utilisent 3000.
    - Recommandation dev: mettre PORT=5001 dans MyWebClient/.env pour le backend; laisser le dev-server React en 3000.
    - Sinon, ajuster le port du dev-server React via variable d’env PORT avant yarn start (client), mais c’est moins courant.
- Option 2: Docker (prod simplifiée)
  - Dockerfile construit client (build) puis CMD ["yarn","server"] (le backend sert les fichiers statiques build).
  - Montée de volume pour base “métier”: -v /chemin/vers/MyWebIntelligencePython/Data:/data 
    - L’app doit pouvoir trouver /data/mwi.db (chemin passé via /api/connect côté UI).
  - Ports typiques:
    - -p 80:3000 (UI/Express)
    - -p 5001:5001 (exposition optionnelle si vous forcez un port différent côté serveur)
  - ADMIN_PASSWORD peut être passé en -e.

----------------------------------------
3) Variables d’environnement
----------------------------------------
- PORT: port d’écoute du backend Express. 
  - .env actuel: PORT=3000. En dev “standalone”, préférer PORT=5001 pour éviter conflit avec React (3000).
- ADMIN_PASSWORD: (optionnel) pour définir le mot de passe initial du compte admin. Sinon, généré et écrit dans admin_password.txt.
- JWT_SECRET: secret JWT (défaut: "jwt_super_secret_key"). À surcharger en prod.
- RESEND_API_KEY: (optionnel) active l’envoi d’e-mails pour /api/auth/recover. Sans cette clé, l’endpoint répond 501 (non bloquant).

----------------------------------------
4) API backend — endpoints & contrats
----------------------------------------
Base path: /api (sauf auth: /api/auth)
- Connexion DB “métier” (SQLite — fichier mwi.db)
  - GET /api/connect?db=/chemin/absolu/vers/mwi.db
    - Retour: true si ok; false si échec. 
    - À appeler au lancement via l’UI (DatabaseLocator).

- Lands / Expressions / Domain / Readable
  - GET /api/lands
    - Retour: [{id, name}]
  - GET /api/land?id=LAND_ID&minRelevance=0&maxDepth=3
    - Retour: {id, name, description, expressionCount} (selon filtres)
  - GET /api/expressions?landId=ID&minRelevance=0&maxDepth=3&offset=0&limit=50&sortColumn=e.id|e.title|e.relevance|e.depth|d.name&sortOrder=1|-1
    - Retour: liste d’expressions résumées avec domaine et tagCount
  - GET /api/expression?id=EXPR_ID
    - Retour: {id, landId, url, title, description, keywords, readable, relevance, depth, domainId, domainName, images}
    - Note: images construit via GROUP_CONCAT(media.url) WHERE media.type='img'
  - GET /api/readable?id=EXPR_ID
    - Utilise Mercury.parse(URL, {contentType:'markdown'}) et renvoie markdown
  - POST /api/readable { id, content }
    - Met à jour expression.readable + readable_at (ISO string)

- Navigation séquentielle (liste filtrée triée)
  - GET /api/prev?id=EXPR_ID&landId=LAND_ID&minRelevance=&maxDepth=&sortColumn=&sortOrder=
  - GET /api/next?... (mêmes params)
    - Détails: LEAD(...) est utilisé; pour “prev”, l’ordre est inversé en interne. Dépend des filtres et tri fournis.

- Suppression / médias
  - GET /api/deleteExpression?id=ID ou id=ID1&id=ID2...
    - Supprime dans expression, media, expressionlink pour ces IDs
  - POST /api/deleteMedia { url, expressionId }
    - Supprime une entrée media

- Tags / Contenu taggé
  - GET /api/tags?landId=LAND_ID
    - Retourne un arbre (root expanded=true) construit via CTE récursif
  - POST /api/tags { landId, tags: [ { id?, name, color, children: [...] } ] }
    - Upsert/tri (sorting index par ordre d’apparition), supprime les tags non présents
  - POST /api/updateTag { id, name, color }
  - GET /api/taggedContent?expressionId=... ou ?landId=... [&tagId=...]
  - GET /api/deleteTaggedContent?id=...
  - POST /api/tagContent { tagId, expressionId, text, start, end }
  - POST /api/updateTagContent { contentId, tagId, text }

Auth (JWT)
- POST /api/auth/login { identifier, password }
  - identifier = username ou email; Retour: { success:true, token, user:{id,username,role,last_session} }
- GET /api/auth/me (Authorization: Bearer <jwt>)
  - Retour: { id, username, role, last_session }
- POST /api/auth/recover { email }
  - Crée token reset (1h). Envoie e-mail via Resend si RESEND_API_KEY; sinon 501 explicite.
- POST /api/auth/reset { token, newPassword }
  - Valide complexité puis remplace le hash.
- POST /api/auth/logout
  - Héritage “session”; inoffensif si pas de middleware session actif.

Codes d’erreur usuels
- 400: paramètres manquants/invalides
- 404: ressource non trouvée
- 500: erreur SQL/serveur
- 501: fonctionnalité non disponible (recover sans RESEND_API_KEY)

----------------------------------------
5) Schéma et attentes sur la base SQLite “métier”
----------------------------------------
Importante: cette base provient de MyWebIntelligencePython (ancienne version). Noms de tables/colonnes attendus par DataQueries.js:
- land: id, name, description
- expression: id, land_id, domain_id, url, title, description, keywords, http_status, relevance, depth, readable, readable_at
- domain: id, name, title, description, keywords
- media: expression_id, url, type (ex: 'img') — pour deleteMedia et getExpression
- tag: id, land_id, parent_id, name, sorting, color
- taggedContent: id, tag_id, expression_id, text, from_char, to_char
- expressionlink: source_id, target_id

Remarques
- Certains noms diffèrent de la nouvelle API (FastAPI/Postgres): ici, “expression”, “domain”, “media.type” (et non “media_type”), “taggedContent” (camel-case). Ne pas renommer.
- Les requêtes utilisent http_status=200, relevance >= min, depth <= max.
- Le CTE pour tags reconstruit les paths; tri = “sorting” alimenté par l’ordre des enfants.

----------------------------------------
6) Authentification & sécurité
----------------------------------------
- Modèle: JWT (jsonwebtoken), SECRET configurable via JWT_SECRET. Expiration: 7d (en dur).
- Admin initial:
  - initAdmin.js garantit un compte “admin”.
  - Mot de passe: ADMIN_PASSWORD si fourni, sinon généré et logué + stocké dans admin_password.txt (racine MyWebClient).
- AdminDB (SQLite admin.db):
  - findUser / findUserById / incrementFailedAttempts / resetFailedAttempts / updateLastSession / setResetToken / resetPassword / addAccessLog.
  - Blocage temporaire si tentatives échouées (parametré dans AdminDB).
- Récupération mot de passe:
  - /recover retourne 501 si RESEND_API_KEY absent; le backend NE plante pas.
- Sécurité SQL:
  - Tri sécurisé: validateSortColumn whiteliste 'e.id','e.title','e.relevance','e.depth','d.name'.
  - Placeholders “?” systématiques. Éviter toute interpolation non whiteliste.
- Sessions:
  - Supprimées (commentaires). /logout conserve un destroy() hérité: inoffensif.

----------------------------------------
7) Frontend (React) — composants clés
----------------------------------------
- App: src/components/App/App.js (layout général)
- Authentication: Login.js, ForgotPassword.js, ResetPassword.js (consomme /api/auth/*)
- DatabaseLocator/DatabaseLocator.js: UI de connexion à la DB via /api/connect
- LandExplorer/*: filtres (minRelevance, maxDepth), affichage nombre d’expressions, navigation
- ExpressionExplorer/*: liste, détail, édition readable (Markdown), navigation prev/next
- Domain/*: vue domaine
- TagExplorer/*: arbre de tags (TreeRenderer, TagRenderer), contenus taggés

----------------------------------------
8) Dépendances & versions
----------------------------------------
- Node: 20 (cf. Dockerfile). 
- Yarn: classic (1.22.x)
- Backend: express, body-parser, dotenv, sqlite3, bcrypt, jsonwebtoken, @postlight/mercury-parser, resend (optionnel), nodemon, @babel/core/node/preset-env.
- Client: create-react-app + assets FontAwesome. 
- OpenSSL legacy provider: nécessaire en build (déjà géré via env NODE_OPTIONS côté client et scripts).

----------------------------------------
9) Pièges connus & bonnes pratiques
----------------------------------------
- Conflit de ports en “standalone”:
  - React dev-server utilise 3000; backend Express par défaut sur 3000 aussi.
  - Fix: mettre PORT=5001 dans .env pour backend en local dev.
- Schéma DB: ne pas “aligner” sur MyWebIntelligenceAPI/Postgres (noms différents). DataQueries.js attend les noms SQLite historiques (media.type, taggedContent, expressionlink, etc.).
- Mercury Parser:
  - getReadable fait un fetch live sur l’URL. Échecs possibles (réseau, CORS, anti-bot). Gérer retours 500 proprement.
  - saveReadable stocke du texte potentiellement volumineux: vérifier taille (OK en SQLite).
- Tri/Prev/Next:
  - Fournir les mêmes filtres/tri que la liste; prev/next se base sur les mêmes critères (LEAD + ordre inversé pour “prev”).
- Sécurité:
  - Toujours vérifier Authorization sur /auth/me côté client.
  - JWT_SECRET non trivial en prod.
- Docker:
  - Monter le volume vers /data avec le bon chemin contenant mwi.db. L’UI appellera /api/connect avec /data/mwi.db.

----------------------------------------
10) Checklist de démarrage (dev & prod)
----------------------------------------
Dev (sources):
- [ ] MyWebClient/.env: PORT=5001
- [ ] yarn install
- [ ] ADMIN_PASSWORD=MonSecret (optionnel) yarn standalone
- [ ] Dans l’UI (DatabaseLocator): connecter /chemin/absolu/vers/mwi.db (ou /data/mwi.db si conteneur)
- [ ] Login avec “admin” + mot de passe (voir admin_password.txt si nécessaire)

Docker (prod simple):
- [ ] docker build -t mwiclient:1.0 .
- [ ] docker run -p 80:3000 --name mwiclient -v /chemin/MyWebIntelligencePython/Data:/data -e ADMIN_PASSWORD=... mwiclient:1.0
- [ ] Ouvrir http://localhost (backend sert client/build)
- [ ] /api/connect vers /data/mwi.db via l’UI
- [ ] Optionnel: RESEND_API_KEY pour activer /auth/recover

----------------------------------------
11) Éléments à ne PAS confondre
----------------------------------------
- MyWebClient (ce projet) utilise SQLite “métier” historique (tables: land, expression, domain, media, taggedContent, expressionlink, tag).
- MyWebIntelligenceAPI (projet FastAPI / Postgres) est un autre backend moderne — non utilisé par MyWebClient.
- Ne pas renommer colonnes/ tables dans SQLite pour “coller” à Postgres: casserait DataQueries.js.

----------------------------------------
12) Backlog / idées d’amélioration (non bloquant)
----------------------------------------
- Harmoniser les ports par défaut:
  - Mettre PORT=5001 dans .env par défaut pour éviter conflit en dev (ou ajuster scripts).
- Nettoyage “sessions”:
  - Supprimer l’appel req.session.destroy() de /logout si plus jamais utilisé.
- Robustesse Mercury:
  - Timeout, retry, message d’erreur utilisateur plus clair si parsing échoue.
- Validation côté serveur:
  - Étendre la whitelist validateSortColumn si de nouvelles colonnes de tri sont ajoutées.
- Sécurité JWT:
  - Rendre JWT_EXPIRES_IN configurable via env.
- Tests:
  - Ajouter quelques tests d’intégration (supertest) pour endpoints critiques.

Annexes — commandes utiles
- Dev:
  - yarn server (init admin + nodemon babel-node)
  - yarn client (CRA dev server)
  - yarn standalone (les deux)
- Docker:
  - docker logs mwiclient (mot de passe admin affiché lors du premier run)
  - docker exec mwiclient cat /app/admin_password.txt

Fin — règle d’or
- Avant tout dev: 
  1) Assure la connexion DB via /api/connect
  2) Vérifie les ports (éviter 3000 vs 3000)
  3) Souviens-toi: schéma SQLite historique, pas la nouvelle API Postgres.
