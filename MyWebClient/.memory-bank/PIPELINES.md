# PIPELINES.md — MyWebClient (vue opérationnelle détaillée)

But du document
- Cartographier les pipelines fonctionnels de MyWebClient, de l’UI au backend/DB, avec prérequis, paramètres, erreurs et états.
- Servir de référence de comportement lors des évolutions: quoi appeler, dans quel ordre, avec quelles attentes.

Rappel critique (précondition globale)
- L’API Data (lands/expressions/tags/…) nécessite une connexion préalable à la base SQLite “métier”.
- Tant que GET /api/connect n’a pas été fait avec un chemin valide vers mwi.db, toutes les routes Data renverront 503 “Database not connected”.
- Schéma attendu = celui de la base historique MyWebIntelligencePython (ne pas confondre avec la nouvelle API/Postgres).

Contenu
1) Modèle d’état global (client)
2) Connexion à la base (init) — /api/connect
3) Authentification (Login, /me, Logout)
4) Récupération/Mise en page des lands & expressions (filtre, tri, pagination)
5) Détail d’une expression, Readable (get/save), navigation Prev/Next, suppression
6) Tags: lecture/arbre, écriture/transactions, mise à jour
7) Contenu taggé: CRUD sur segments (tagContent/update/delete)
8) Domaines: consultation
9) Médias: suppression
10) Mot de passe oublié / réinitialisation (recover/reset via Resend)
11) Initialisation admin (au démarrage backend)
12) Erreurs, statuts et logs
13) Performances, limites, anti‑patterns et futurs travaux

---

## 1) Modèle d’état global (client)

Contexte (src/app/Context.js, components):
- auth:
  - token (JWT) stocké dans localStorage après /auth/login
  - user (id, username, role, last_session) obtenu via /auth/me
- db:
  - dbPath (chemin absolu vers mwi.db)
  - isConnected (bool, réponse de /api/connect)
- lands & filters:
  - currentLandId
  - filters: minRelevance (float), maxDepth (int)
  - sorting: sortColumn (e.id|e.title|e.relevance|e.depth|d.name), sortOrder (1 ASC | -1 DESC)
  - pagination: offset (int), limit (int)
- expression focus:
  - currentExpressionId
  - currentReadable (markdown dans l’état d’édition)
  - currentTaggedContent (liste)
- tags:
  - tagTree (arbre hiérarchique)
  - pendingTree (édition en cours)
- domain:
  - currentDomainId, currentDomainDetails

Règle d’or
- Toute action Data (lands/expressions/tags/…) est conditionnée par isConnected = true.

---

## 2) Pipeline “Connexion DB (init)”

Déclencheur (UI): DatabaseLocator.js (ou flux d’initialisation).

Séquence:
1) Utilisateur choisit un chemin local de DB (mwi.db). 
2) Client -> GET /api/connect?db=/chemin/absolu/vers/mwi.db
   - Sur Windows, le backend normalise les “\” en “/”.
3) Backend:
   - sqlite.open(READWRITE), PRAGMA foreign_keys=ON
   - OK => res.json(true), KO => res.json(false) (pas d’erreur HTTP ici)
4) Client:
   - Si true: isConnected=true; déclenche chargement initial (lands, tags, etc.)
   - Si false: afficher aide (chemin invalide, permissions, fichier manquant)

Erreurs/retours:
- 400 si paramètre db absent
- 200 + false si échec d’ouverture DB (géré par UI)
- 503 “Database not connected” renvoyé par les autres routes si cette étape n’a pas été faite

---

## 3) Pipeline “Auth” (login, me, logout)

3.1 Login
- Déclencheur: Login.js (handleSubmit)
- Client -> POST /api/auth/login { identifier, password }
- Backend (authRoutes.js):
  - AdminDB.findUser(identifier)
  - bcrypt.compare(password, user.password_hash)
  - En cas d’échec: incrementFailedAttempts (seuil de blocage paramétré), log accès (failure)
  - Succès:
    - resetFailedAttempts
    - jwt.sign(payload, JWT_SECRET, expiresIn=7d)
    - updateLastSession, log accès (success)
    - res { success:true, token, user:{ id, username, role, last_session } }
- Client:
  - stocke token localStorage
  - bascule vers l’UI principale

Erreurs usuelles:
- 401 Utilisateur non trouvé / mot de passe incorrect
- 403 Compte bloqué temporairement
- 500 Erreur interne AdminDB

3.2 /me
- Client -> GET /api/auth/me (Authorization: Bearer <jwt>)
- Backend: jwt.verify(JWT_SECRET), AdminDB.findUserById
- Retour { id, username, role, last_session } sinon 401/404

3.3 Logout
- Client -> POST /api/auth/logout (héritage de sessions; inoffensif sans middleware de session)
- UI: effacer token du localStorage côté client

Remarques:
- DataQueries (routes /api/* hors /auth) n’imposent pas de middleware d’auth: l’UI restreint mais côté API il n’y a pas d’autorisation fine.

---

## 4) Pipeline “Lands & Expressions” (filtre, tri, pagination)

Déclencheur:
- Sélection d’un land, ajustement sliders, changement tri/pagination.

Séquence:
1) Client -> GET /api/land?id=LAND_ID&minRelevance=&maxDepth=
   - Retour: { id, name, description, expressionCount (selon filtres) }
2) Client -> GET /api/expressions?landId=LAND_ID&minRelevance=&maxDepth=&offset=&limit=&sortColumn=&sortOrder=
   - Retour: liste d’objets:
     - id, title, url, httpStatus, relevance
     - domainId, domainName
     - tagCount

Paramètres et valeurs:
- minRelevance (float; défaut 0)
- maxDepth (int; défaut 3)
- sortColumn whitelist: e.id, e.title, e.relevance, e.depth, d.name
- sortOrder: 1 (ASC) ou -1 (DESC)
- offset/limit: pagination (défaut 0/50)

Erreurs:
- 400 paramètres manquants/invalides
- 500 erreur SQL
- 503 pas connecté

---

## 5) Pipeline “Expression” (détail, readable, navigation, suppression)

5.1 Détail
- Client -> GET /api/expression?id=EXPR_ID
- Backend: joint expression + domain + media (GROUP_CONCAT) avec m.type='img'
- Retour: 
  - id, landId, url, title, description, keywords, readable, relevance, depth
  - domainId, domainName
  - images (string concatennée d’URLs)

5.2 Readable — lecture
- Client -> GET /api/readable?id=EXPR_ID
- Backend:
  - SELECT url
  - Mercury.parse(url, { contentType: 'markdown' })
  - Retour: markdown (string) ou 500 si échec parse/fetch
  - Si id inconnu => null

5.3 Readable — sauvegarde
- Client -> POST /api/readable { id:EXPR_ID, content:MARKDOWN }
- Backend: UPDATE expression SET readable=?, readable_at=now() WHERE id=?
- Retour: true si OK, 404 si aucune ligne modifiée, 500 si erreur SQL

5.4 Navigation Prev/Next
- Client -> GET /api/prev|/api/next avec les MÊMES paramètres de contexte:
  - id (courant), landId, minRelevance, maxDepth, sortColumn, sortOrder
- Backend:
  - Fenêtre analytique LEAD(...) et inversion d’ordre pour “prev”
  - Retour: EXPR_ID voisin ou null
- Attention: si les filtres/tri ne matchent pas ceux de la liste, la navigation sera incohérente.

5.5 Suppression d’expression
- Client -> GET /api/deleteExpression?id=ID ou id=ID1&id=ID2...
- Backend:
  - DELETE expression IN (...)
  - DELETE media WHERE expression_id IN (...)
  - DELETE expressionlink WHERE source_id IN (...) OR target_id IN (...)
- Retour: true (idempotent), logs des counts supprimés en console

Erreurs communes:
- 400 id manquant/invalide
- 500 SQL error
- 503 pas connecté

---

## 6) Pipeline “Tags” (arbre, transactions, mise à jour)

6.1 Lire l’arbre de tags
- Client -> GET /api/tags?landId=LAND_ID
- Backend:
  - CTE récursif tagPath pour reconstruire path/ordre
  - Construction arbre en mémoire (expanded=true par défaut)
- Retour: tableau de racines { id, name, color, sorting, parent_id, children[], path }

6.2 Écrire l’arbre (persist)
- Client -> POST /api/tags { landId, tags: [ { id?, name, color, children: [...] } ] }
- Backend (transaction):
  - BEGIN
  - SELECT ids existants (prevIndex)
  - traverse récursive de la structure:
    - si tag.id présent dans prevIndex => UPDATE parent_id, name, sorting, color
    - sinon => INSERT (land_id, parent_id, name, sorting, color) et propager lastID aux enfants
  - Supprimer les ids existants non référencés dans la structure envoyée (DELETE)
  - COMMIT (ou ROLLBACK si erreur)
- Retour: true

Remarques:
- Le champ sorting est dérivé de l’ordre dans le tableau children (index).
- Les chemins path sont reconstruits à la lecture (CTE), pas stockés.

6.3 Mise à jour d’un tag (édition unitaire)
- Client -> POST /api/updateTag { id, name, color }
- Retour true, 404 si non trouvé

Erreurs:
- 400 paramètres manquants/invalides
- 500 SQL
- 503 pas connecté

---

## 7) Pipeline “Contenu taggé” (segments)

7.1 Créer un segment taggé
- Client -> POST /api/tagContent { tagId, expressionId, text, start, end }
- Backend: INSERT taggedContent(tag_id, expression_id, text, from_char, to_char)
- Retour: { id, message }

7.2 Lire le contenu taggé
- Par expression: GET /api/taggedContent?expressionId=ID
- Par land: GET /api/taggedContent?landId=ID
- Optionnel: filtrer par tagId: +&tagId=ID
- Retour: rows []

7.3 Mettre à jour un segment
- Client -> POST /api/updateTagContent { contentId, tagId, text }
- Backend: UPDATE taggedContent SET tag_id=?, text=? WHERE id=?
- Retour: true, 404 si non trouvé

7.4 Supprimer un segment
- Client -> GET /api/deleteTaggedContent?id=ID
- Backend: DELETE taggedContent WHERE id=?
- Retour: true, 404 si non trouvé

Erreurs:
- 400 invalide/manquant
- 500 SQL
- 503 pas connecté

---

## 8) Pipeline “Domaines”

- Déclencheur: sélection dans Domain.js
- Client -> GET /api/domain?id=DOMAIN_ID
- Backend:
  - SELECT d.*, COUNT(e.id) AS expressionCount JOIN expression e ON e.domain_id=d.id
- Retour: { id, name, title, description, keywords, expressionCount }

Erreurs: 400/500/503

---

## 9) Pipeline “Médias” (suppression)

- Déclencheur: suppression d’un média dans Expression.js
- Client -> POST /api/deleteMedia { url, expressionId }
- Backend: DELETE media WHERE url=? AND expression_id=?
- Retour: true | 404 si non trouvé

Erreurs: 400/500/503

---

## 10) Pipeline “Mot de passe oublié / Réinitialisation”

10.1 Demande (recover)
- Déclencheur: ForgotPassword.js
- Client -> POST /api/auth/recover { email }
- Backend:
  - Génère token hex 32o + expires (now+1h)
  - AdminDB.setResetToken(email, token, expires)
  - resetUrl = http://localhost:3000/reset-password?token=...
  - Si RESEND_API_KEY présent:
    - resend.emails.send({ to:email, subject, html })
    - res { success:true }
  - Sinon: res.status(501).json({ error: "Service d'envoi d'e-mail non configuré..." })

10.2 Réinitialisation (reset)
- Déclencheur: ResetPassword.js
- Client -> POST /api/auth/reset { token, newPassword }
- Backend:
  - Politique regex: min 8, a-z, A-Z, chiffre, spécial
  - AdminDB.findUserByResetToken(token)
  - bcrypt.hash(newPassword)
  - AdminDB.resetPassword(user.id, hash) (invalide le token)
  - res { success:true }

Erreurs:
- 400 token/mot de passe manquant ou faible
- 400 token invalide/expiré
- 501 (recover) si RESEND_API_KEY manquant
- 500 AdminDB errors

---

## 11) Pipeline “Initialisation admin” (démarrage backend)

- Déclencheur: script “server” (package.json) exécute node server/src/initAdmin.js avant nodemon
- Si aucun compte admin:
  - Crée username=admin
  - Mot de passe:
    - si ADMIN_PASSWORD fourni: utilise la valeur
    - sinon: génère un aléatoire robuste
  - Écrit dans admin_password.txt à la racine (et log console)
- À la première connexion, l’utilisateur peut utiliser admin + mot de passe.

---

## 12) Erreurs, statuts et logs

Côté DataQueries:
- 400 paramètres manquants/invalides
- 404 ressource non trouvée (updateTag, updateTagContent, saveReadable sans ligne)
- 500 erreur SQL/interne
- 503 “Database not connected” si /api/connect non effectué (dbCheck)

Côté Auth:
- 401 non authentifié / mauvais identifiants / token invalide
- 403 compte bloqué
- 404 utilisateur non trouvé (/me)
- 501 recover sans service mail
- 500 erreurs AdminDB/Resend

Logs:
- Console backend: requêtes Data (verboses), erreurs SQL, détails Prev/Next, insert/update counts, logs d’accès auth.
- À prévoir: centralisation/log levels (futur).

---

## 13) Performances, limites, anti‑patterns et futurs travaux

Performances/limites:
- SQLite locale: accès en lecture/écriture série; éviter de lancer des requêtes massives côté UI (paginées par défaut).
- getReadable (Mercury): appels réseau vers les URLs sources; latence et échecs possibles (rate-limit, bot protection).
  - Bonne pratique: si l’édition est manuelle, privilégier saveReadable (persistance côté DB).
- /api/tags (transaction):
  - Sur gros arbres, la sérialisation d’un large payload provoquera des INSERT/UPDATE/DELETE nombreux; éviter de sauvegarder à chaque micro-changement côté UI (batcher).

Anti‑patterns:
- Oublier d’aligner les filtres/tri entre liste d’expressions et navigation Prev/Next => incohérence.
- Tenter d’utiliser le schéma Postgres (nouvelle API) avec MyWebClient: incompatibilité (noms de tables/colonnes).
- Partir sans /api/connect: l’UI doit explicitement connecter la DB métier.

Futurs travaux (non bloquants):
- Sécurisation DataQueries par middleware JWT (aligner avec UI).
- Paramétrer JWT_EXPIRES_IN via env.
- Améliorer messages d’erreurs utilisateur pour Mercury (timeouts/retry).
- Nettoyer reliquat session (/logout) si définitivement inutile.
- Tests d’intégration (supertest) pour endpoints principaux (land/expressions/readable/tags).
- Optimisations SQL: index ciblés si la DB grossit (sur land_id, http_status, relevance, depth, expression_id/tag_id, etc.).

---

Annexes — Raccourcis de debug
- Vérifier connexion DB:
  - GET /api/connect?db=/…/mwi.db => true attendu
  - Toute route /api/* ensuite => ne doit plus renvoyer 503
- Requêtes types:
  - GET /api/lands
  - GET /api/land?id=1&minRelevance=0&maxDepth=3
  - GET /api/expressions?landId=1&offset=0&limit=50&sortColumn=e.relevance&sortOrder=-1
  - GET /api/expression?id=123
  - GET /api/readable?id=123
  - POST /api/readable { id:123, content:"# Titre\n…" }
  - GET /api/tags?landId=1
  - POST /api/tags { landId:1, tags:[...] }
  - POST /api/tagContent { tagId:10, expressionId:123, text:"extrait", start:0, end:7 }
  - GET /api/taggedContent?expressionId=123
  - POST /api/deleteMedia { url:"http://…/img.jpg", expressionId:123 }

Fin — Principe de sécurité mentale
- Toujours: /api/connect d’abord, puis auth UI, puis Data.
- Toujours: garder en phase filtres/tri entre liste et navigation.
- Toujours: se rappeler que MyWebClient parle à SQLite historique, pas à l’API FastAPI/Postgres.
