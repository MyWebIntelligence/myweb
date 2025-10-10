# PRD — Migration MyWebClient vers Client de MyWebIntelligenceAPI

Version: 1.0  
Date: 2025-08-09  
Auteur: Cline (assisté par l’équipe MyWebIntelligence)  
Statut: Draft pour approbation

Résumé exécutif
- MyWebClient n’est plus autonome (SQLite locale + backend Node), mais devient un client complet de MyWebIntelligenceAPI (FastAPI + PostgreSQL + Celery/Redis).
- Objectifs: 
  - Déporter toute logique métier/données vers MyWebIntelligenceAPI.
  - Conserver et étendre les fonctionnalités UI existantes (exploration lands/expressions/tags, édition readable, tagging, navigation, médias, exports, suivi jobs).
  - Introduire la gestion des jobs (crawl, consolidation, export) avec suivi temps réel (WebSockets).
- Approche recommandée (step-by-step, faible risque): 
  - Phase 1: Conserver un BFF Node/Express minimal (proxy) pour faciliter l’intégration et éviter les CORS, en mappant les anciens endpoints vers l’API v1.
  - Phase 2: Migration progressive du client React vers des appels directs à l’API (si souhaité), ou maintien du BFF pour des raisons de sécurité/expérience (cookies httpOnly, centralisation auth, rate limiting).
- KPI (HEART): 
  - Task success: 95% des actions critiques réussies (login, list lands/expressions, save readable, tag, export).
  - Performance: TTI < 2s pour écrans principaux, p95 API < 500ms pour requêtes list/GET.
  - Engagement: ≥ 70% des sessions déclenchent au moins 1 action de navigation/exploration.
  - Reliability: Taux d’erreurs < 1% sur appels API non réseau.

Contexte
- État actuel MyWebClient:
  - React (UI) + Node/Express (API) accédant à une base SQLite “métier” (mwi.db) et une base SQLite “admin” (admin.db).
  - Endpoints REST internes pour lands, expressions, tags, taggedContent, médias, readable, etc.
- Cible:
  - Backend officiel: MyWebIntelligenceAPI (FastAPI) — Postgres, SQLAlchemy, Celery (broker Redis), endpoints REST /api/v1 (lands, jobs, export, expressions…), WebSocket de progression, monitoring (Prometheus).
  - Modèle de données: tables Postgres (lands, expressions, media, tags, tagged_content, domains, jobs, users…) — voir .clinerules/Schéma Postgres.

Prérequis & Environnement Docker (obligatoire)
- Tous les développements et tous les tests doivent être réalisés dans l’environnement Docker de référence du dépôt (docker-compose). Aucune validation ne doit être faite hors de cet environnement.
- La validation préalable de l’installation Docker locale est obligatoire avant de commencer à coder ET avant toute Pull Request.

Checklist de validation Docker (à exécuter avant dev/PR)
- Prérequis:
  - Docker Desktop ≥ 24, Docker Compose v2
- Préparation des variables d’environnement:
  - cp MyWebIntelligenceAPI/.env.example MyWebIntelligenceAPI/.env (adapter au besoin)
- Build & démarrage des services:
  - docker-compose up -d --build
- Vérifications de santé (tous doivent être OK):
  - API FastAPI accessible: http://localhost:8000 (documentation Swagger disponible sur /docs)
  - Base Postgres up; migrations appliquées (logs du conteneur API/alembic OK)
  - Redis up
  - Celery worker enregistré (logs OK)
  - Client Web accessible (port exposé par docker-compose, typiquement http://localhost:3002)
- Outils de diagnostic utiles:
  - docker-compose ps
  - docker-compose logs -f
- Arrêt/nettoyage si nécessaire:
  - docker-compose down -v

Règle de blocage (gating)
- Aucune PR ne peut être mergée si la checklist de validation Docker n’est pas verte.
- Les scénarios de test fonctionnels (smoke tests) doivent être exécutés via l’environnement Docker.
- Portée: cette exigence s’applique au Client (MyWebClient) et à l’API (MyWebIntelligenceAPI).

Commandes de référence
- Lancement complet: docker-compose -f docker-compose.yml up --build
- Arrêt complet: docker-compose -f docker-compose.yml down -v

Objectifs & Non-objectifs
- Objectifs:
  - MyWebClient consomme exclusivement MyWebIntelligenceAPI pour toute donnée/persistance.
  - Support des nouveaux workflows: 
    - Lancer crawl/consolidation/export via API.
    - Suivre l’avancement (jobs, status RUNNING/COMPLETED/FAILED, % progression).
    - Télécharger exports (CSV, GEXF, corpus ZIP).
  - Conserver les features historiques de l’UI (filtrage, tri, pagination, prev/next, tagging, édition readable).
  - Auth alignée avec l’API (JWT), session sécurisée (httpOnly si BFF).
- Non-objectifs:
  - Réimplémenter de la logique métier côté client.
  - Accéder directement à la base Postgres hors API.
  - supprimer la compat SQLite “métier” locale.

Parties prenantes & utilisateurs
- Utilisateurs finaux: analystes, chercheurs, responsables éditoriaux.
- Stakeholders: 
  - Équipe API (propriétaires de MyWebIntelligenceAPI),
  - Équipe Front (MyWebClient),
  - DevOps (déploiement, sécurité, observabilité).

Hypothèses & Contraintes
- API accessible sur base URL configurable (ex: http://localhost:8000/api/v1).
- Auth JWT disponible (login, refresh si existant; sinon re-login).
- Endpoints requis: lands, expressions, domains, media, tags, tagged_content, jobs (crawl/consolidate/export), export downloads, user/auth.
- WebSocket disponible pour jobs: canal/endpoint fourni par l’API (ex: /ws/jobs/{job_id}).
- CORS/Proxy (précisions d’intégration réseau, choisir 1 modèle) :
  - Option A — CORS côté API (FastAPI) :
    - Origins autorisés (configurable via env API_CORS_ORIGINS, valeurs séparées par des virgules) :
      - Exemple dev: ["http://localhost:3000"]
      - Exemple prod: ["https://app.mywi.example"]
    - allow_credentials=True
    - allow_methods=["GET","POST","PUT","PATCH","DELETE","OPTIONS"]
    - allow_headers=["Authorization","Content-Type","X-Request-ID"]
    - expose_headers=["Content-Disposition"] (nécessaire pour downloads d’exports)
    - Exemple FastAPI :
      ```python
      from fastapi.middleware.cors import CORSMiddleware
      import os

      origins = [o.strip() for o in os.getenv("API_CORS_ORIGINS", "http://localhost:3000").split(",")]

      app.add_middleware(
          CORSMiddleware,
          allow_origins=origins,
          allow_credentials=True,
          allow_methods=["GET","POST","PUT","PATCH","DELETE","OPTIONS"],
          allow_headers=["Authorization","Content-Type","X-Request-ID"],
          expose_headers=["Content-Disposition"],
      )
      ```
    - WebSocket (si consommé directement par le client) :
      - Configurer le reverse proxy (nginx/caddy) pour l’upgrade (Connection: Upgrade, Upgrade: websocket).
      - S’assurer que l’origin autorisée inclut l’UI (ex: http://localhost:3000).
      - Sinon, préférer l’option BFF ci-dessous pour éviter la gestion CORS WS.
  - Option B — BFF proxy “même origine” (recommandé) :
    - Proxy HTTP :
      - /api/client/* → {API_BASE_URL}/api/v1/*
      - Path rewrite: "^/api/client" → "/api/v1"
      - changeOrigin=true, timeout/réessais configurés
    - Proxy WebSocket :
      - /ws/* → {WS_BASE_URL} (upgrade géré côté Node/http-server ou reverse proxy frontal)
    - Auth & cookies :
      - Cookie httpOnly “session” (JWT API chiffré côté BFF ou jeton signé BFF), SameSite=Lax (dev) / Strict (prod), Secure=true en prod.
      - En-têtes vers l’API : Authorization: Bearer <jwt> (injecté par le BFF).
    - CSRF (mutation uniquement) :
      - Générer un token CSRF (cryptographiquement fort) stocké en cookie non httpOnly (SameSite=Lax/Strict).
      - Exiger l’en-tête X-CSRF-Token correspondant sur POST/PUT/PATCH/DELETE.
      - Vérifier côté BFF avant de proxifier la requête vers l’API.
    - Exemple Express (extrait) :
      ```js
      import { createProxyMiddleware } from 'http-proxy-middleware';

      const API_BASE_URL = process.env.API_BASE_URL || 'http://localhost:8000';

      app.use('/api/client', createProxyMiddleware({
        target: API_BASE_URL,
        changeOrigin: true,
        pathRewrite: { '^/api/client': '/api/v1' },
        onProxyReq(proxyReq, req, res) {
          // Injecter Authorization à partir du cookie httpOnly “session”
          const jwt = extractJwtFromSessionCookie(req); // impl à fournir
          if (jwt) proxyReq.setHeader('Authorization', `Bearer ${jwt}`);
          // CSRF pour mutations
          if (['POST','PUT','PATCH','DELETE'].includes(req.method)) {
            assertValidCsrf(req); // impl à fournir
          }
        },
      }));

      // WS via http server upgrade (ou laisser au reverse proxy frontal)
      // server.on('upgrade', (req, socket, head) => { /* proxy ws vers {WS_BASE_URL} */ });
      ```
    - Avantages :
      - Pas de CORS côté client (même origine), auth plus sûre via cookie httpOnly, point unique pour rate limiting/observabilité.
      - Simplifie aussi les téléchargements (Content-Disposition) et le proxy WebSocket.
- Internationalisation fr (prioritaire) et conformité RGPD (pas de données personnelles superflues côté client).

Portée (Scope)
- Dans le périmètre:
  - Refactor complet du data layer client (Context.js) pour consommer l’API.
  - Ajout écran “Jobs”/panneau de suivi des tâches avec live updates.
  - Adaptation des composants: LandExplorer, ExpressionExplorer, TagExplorer, Domain.
  - Auth: intégration avec API (login/me/logout), stockage token sécurisé (via BFF cookie httpOnly recommandé).
  - Exports: déclenchement, liste, téléchargement.
  - Configuration: API_BASE_URL, gestion environnements (dev/staging/prod).
- Hors périmètre:
  - Changement du design system complet.
  - Implémentation de nouvelles fonctionnalités API côté serveur (sauf signalement gap — voir “Dépendances & gaps API”).

Architecture cible (haut niveau)
Option recommandée (Phase 1): BFF Node/Express (Backend For Frontend)
- MyWebClient/server (Node/Express) devient un proxy:
  - /client (static) — sert l’app React en prod.
  - /api/* (BFF) — routes qui forward vers MyWebIntelligenceAPI /api/v1/* (avec mapping, normalisation, auth).
  - Avantages: pas de CORS côté client, auth en httpOnly cookie, possibilité de fallback, rate limiting, observabilité.
- MyWebClient/client (React):
  - Consomme /api/* (BFF) au lieu d’appeler directement l’API.
  - Migration progressive des services vers contrats de l’API.

Option (Phase 2): SPA direct vers API
- Si CORS et sécurité ok: client appelle directement API_BASE_URL.
- Auth en token Bearer stocké en mémoire + refresh token si fourni par API (sinon re-login).
- Requiert configuration CORS et gestion des headers côté API.

Cartographie de features (ancien → nouveau)
- Lands:
  - Old: GET /api/lands; New: GET MyWebIntelligenceAPI /api/v1/lands
  - Old: GET /api/land?id=…; New: GET /api/v1/lands/{id}
- Expressions:
  - Old: GET /api/expressions?landId=…; New: GET /api/v1/lands/{id}/expressions (params: relevance_min, depth_max, sort, order, limit, offset)
  - Old: GET /api/expression?id=…; New: GET /api/v1/expressions/{id}
  - Readable:
    - Old: GET/POST /api/readable?id or body {id, content}
    - New: likely fields provided by API: GET /api/v1/expressions/{id} (includes readable?) and PATCH /api/v1/expressions/{id} to update readable (à confirmer). Si non existant, PR API à prévoir: endpoint update readable.
  - Prev/Next:
    - Old: /api/prev, /api/next (LEAD…)
    - New: réaliser côté client via liste + index, ou endpoint API de navigation (si disponible). Recommandé: calculer client-side à partir de la même liste filtrée.
- Tags / Tagged content:
  - Old: /api/tags, /api/tagContent, /api/taggedContent, /api/updateTag, /api/deleteTaggedContent
  - New: 
    - GET /api/v1/lands/{id}/tags (arbre, path, tri) 
    - POST/PUT/PATCH /api/v1/tags (CRUD)
    - GET /api/v1/tagged-content?expression_id=… ou ?land_id=… 
    - POST /api/v1/tagged-content, PATCH /api/v1/tagged-content/{id}, DELETE idem
    - Si endpoints manquants, liste des gaps plus bas.
- Domain:
  - Old: GET /api/domain?id=… 
  - New: GET /api/v1/domains/{id}
- Media:
  - Old: POST /api/deleteMedia 
  - New: DELETE /api/v1/media/{id} ou param (si suppression par url/expression). Sinon endpoint à définir (gap).
- Jobs (NOUVEAU dans client):
  - Lancer crawl: POST /api/v1/lands/{id}/crawl (retour job_id)
  - Lancer consolidation: POST /api/v1/lands/{id}/consolidate (retour job_id)
  - Statut job: GET /api/v1/jobs/{job_id}, WS /ws/jobs/{job_id}
- Exports:
  - Générer: POST /api/v1/export (body: land_id, type, params)
  - Lister: GET /api/v1/exports?land_id=…
  - Télécharger: GET /api/v1/exports/{id}/download

User stories & Critères d’acceptation (BDD)

Authentification
- En tant qu’utilisateur, je peux me connecter avec mes identifiants API pour accéder à l’interface.
  - Given API up and user exists
  - When I submit valid credentials
  - Then I receive a valid session (token/cookie) and I can access protected features
- En tant qu’utilisateur, je peux voir mon identité (me) et me déconnecter.
  - Given I am authenticated
  - When I open the app
  - Then my session is validated via /auth/me and my name/role is displayed

Lands & Expressions
- En tant qu’analyste, je peux lister les lands depuis l’API.
  - When I open the home
  - Then GET /lands returns my projects and they are displayed
- En tant qu’analyste, je peux explorer les expressions d’un land avec filtres/tri/pagination.
  - Given a land with many expressions
  - When I set minRelevance and maxDepth and pick sorting
  - Then GET /lands/{id}/expressions returns a page matching filters and I can paginate
- En tant qu’analyste, je peux ouvrir une expression et voir ses métadonnées, domaine, médias, readable.
  - When I click an expression
  - Then GET /expressions/{id} returns details and they render in the UI

Readable (édition)
- En tant qu’analyste, je peux sauvegarder du readable sur une expression.
  - Given GET /expressions/{id} returns readable
  - When I edit and click save
  - Then PATCH /expressions/{id} persists readable and I see a success toast

Navigation Prev/Next
- En tant qu’analyste, je peux naviguer à l’expression précédente/suivante selon mon tri/filtre actuel.
  - Given a list context
  - When I click Next
  - Then the next item in my filtered/sorted list is opened

Tags & Tagged content
- En tant qu’analyste, je peux gérer l’arbre de tags d’un land (ajout, renommage, réorganisation couleur).
  - When I adjust tree and save
  - Then POST/PUT API returns success and GET reflects the new tree
- En tant qu’analyste, je peux annoter des segments de texte (tagged content).
  - When I select text and apply a tag
  - Then POST /tagged-content creates a record and I can see it in the list

Jobs (crawl, consolidation, export)
- En tant qu’analyste, je peux lancer un crawl sur un land et suivre sa progression en temps réel.
  - When I click “Start Crawl”
  - Then POST /lands/{id}/crawl returns a job_id and the UI subscribes to WS for live status until completion
- En tant qu’analyste, je peux lancer une consolidation et suivre son état (idem).
- En tant qu’analyste, je peux générer un export et le télécharger quand prêt.
  - When I request an export
  - Then I see it in “Exports” list and can click “Download” when status=COMPLETED

Domaines & Médias
- En tant qu’analyste, je peux consulter un domaine et supprimer un média d’une expression.
  - GET /domains/{id} shows metadata
  - DELETE /media/{id} removes an image and UI updates

Non-fonctionnels (ISO/IEC 25010)
- Performance:
  - p95 GET lists < 500ms (backend), UI TTI < 2s, pagination par 50 items par défaut.
- Fiabilité:
  - Gestion robuste des erreurs réseau/API, toasts explicites, retry pour lectures idempotentes.
- Sécurité:
  - Auth JWT; stockage token via cookie httpOnly (BFF) ou mémoire volatile (SPA) — pas de localStorage en prod si possible.
  - CORS strict si SPA; rate limiting sur BFF; pas de secrets client-side.
  - Conformité ASVS de base: authn, authz (à minima côté API), logs d’accès.
- Maintenabilité:
  - Découpler services API du state (ex: React Query/RTK-Query), typage de réponses (TS si migration possible).
  - Config centralisée (API_BASE_URL, WS_URL).
- Compatibilité:
  - Navigateurs modernes; fallback minimal pour features non critiques.
- Portabilité:
  - Docker compose pour dev; env var pour base URLs.
- Observabilité:
  - Logs normalisés au BFF; métriques (Prometheus côté API).

Conformité & RGPD
- Données personnelles: user credentials, identifiants; pas de PII superflue en stockage client.
- Base légale: intérêt légitime/opérationnel interne.
- Minimisation: uniquement token session; pas de miroirs de données.
- Droits: déléguer à l’API (export/effacement si nécessaire).
- DPIA: non applicable/à confirmer — faible volumétrie PII.
- Accessibilité: WCAG 2.2 AA (focus visible, navigation clavier, contrastes).

Design UX (changements)
- Retirer/masquer DatabaseLocator (sélecteur de fichier mwi.db). Remplacé par Settings/API Endpoint (lecture seule) et sélecteur de “Land” à partir de l’API.
- Ajouter “Jobs/Tasks” panel:
  - Liste des jobs (status, progression, timestamps).
  - Vue détail d’un job (logs, current_step).
  - Actions: lancer crawl/consolidation; annuler (si API supporte).
- État global:
  - Auth (connecté/déconnecté).
  - Sélecteurs filtrage/tri persistants par land (URL query params).
- Notifications:
  - Succès/erreur API; statut export prêt (toast avec lien).

Plan de livraison (Phases)

Phase 0 — Préparation
- Aligner contrats API: 
  - Confirmer endpoints exacts pour tags, tagged_content, readable update, médias delete, domains.
  - WS endpoints pour jobs.
- Décider Option BFF vs SPA direct: recommandé BFF en Phase 1.

Phase 1 — BFF Proxy + Remap Client
- Créer layer proxy Node/Express:
  - /api/client/* → API_BASE_URL/api/v1/*
  - Auth: login → obtention JWT; set cookie httpOnly; /auth/me via BFF; proxy Authorization vers API.
  - Normaliser réponses pour minimiser changements UI initialement.
- Adapter Context.js:
  - Remplacer appels DataQueries internes par fetch vers /api/client/...
  - Implémenter nouveaux endpoints (lands, expressions, tags, tagged_content, jobs, exports).
  - Readable: utiliser PATCH/PUT sur /expressions/{id} (ou endpoint spécifique).
  - Prev/Next: calcul client-side via liste en mémoire.
- UI:
  - Retirer DatabaseLocator.
  - Ajouter panneau Jobs; boutons Crawl, Consolidate, Export.
  - Abonnement WS: BFF peut proxy les WS (ou client direct sur WS_URL si CORS ok).

Phase 2 — Durcissement & NFR
- Sécuriser stockage (cookie httpOnly, SameSite=Lax/Strict, Secure en prod).
- Améliorer gestion erreurs et retries.
- Téléchargement exports: liens signés/endpoint BFF download (option).
- Tests E2E/UI (sélectionnés) + tests d’intégration (supertest côté BFF).

Phase 3 — Option SPA Direct (si décidé)
- Retirer BFF ou le réduire au strict minimum (static + proxy léger).
- Activer CORS côté API; tokens gérés côté SPA (risque XSS → à évaluer).

API — Détails d’intégration (proposés)
- Base URL: API_BASE_URL (ex: http://localhost:8000)
- Routes (exemples, à confirmer selon code API):
  - Auth:
    - POST /api/v1/auth/login → {access_token, token_type} ou similaire
    - GET /api/v1/auth/me
    - POST /api/v1/auth/logout (si fourni) — sinon client-side clear
  - Lands:
    - GET /api/v1/lands
    - GET /api/v1/lands/{id}
    - POST /api/v1/lands/{id}/crawl
    - POST /api/v1/lands/{id}/consolidate
  - Expressions:
    - GET /api/v1/lands/{id}/expressions?relevance_min=&depth_max=&sort=&order=&limit=&offset=
    - GET /api/v1/expressions/{id}
    - PATCH /api/v1/expressions/{id} {readable: "..."} (si disponible)
  - Tags:
    - GET /api/v1/lands/{id}/tags (arbre)
    - POST /api/v1/tags (create), PATCH /api/v1/tags/{id}, DELETE /api/v1/tags/{id}
  - TaggedContent:
    - GET /api/v1/tagged-content?expression_id=…|land_id=…[&tag_id=…]
    - POST /api/v1/tagged-content
    - PATCH /api/v1/tagged-content/{id}
    - DELETE /api/v1/tagged-content/{id}
  - Domains:
    - GET /api/v1/domains/{id}
  - Media:
    - DELETE /api/v1/media/{id} (ou body url/expression_id) — à préciser
  - Jobs:
    - GET /api/v1/jobs/{id}
    - WS /ws/jobs/{id}
  - Exports:
    - POST /api/v1/exports { land_id, type, params }
    - GET /api/v1/exports?land_id=…
    - GET /api/v1/exports/{id}/download

Gaps API pressentis (à confirmer / plan B)
- Update readable sur expression (champ readable + readable_at).
- Arbre de tags en un seul call (path, sorting).
- Delete media par url/expression_id (sinon ID de média exposé).
- Endpoints domains (si non exposés).
- Search (global) si nécessaire (hors scope initial).

Sécurité & AuthN/AuthZ
- Client → BFF:
  - Cookie httpOnly “session” (contenant JWT de l’API ou un token BFF signé référentiel).
  - CSRF mitigé via SameSite + header custom/timestamp (si POST multi-origin exposé).
- BFF → API:
  - Authorization: Bearer <jwt> (stocké chiffré côté BFF).
- Logs d’accès auth (succès/échecs) — côté API; côté BFF: audit minimal.
- NIST 800-63B: mots de passe gérés par API; “reset password” via API (si exposé); sinon lien vers portail API.

Observabilité & SRE
- Dashboards: requêtes par endpoint (BFF), taux d’erreurs, latences p50/p95, taille payload.
- Alertes: p95 latence > 1s, taux 5xx > 1%, échecs WS > X/min.
- Tracing: correlation-id (header) propagé BFF → API.

Analytique & Mesure
- Événements (anonymisés): app_open, land_view, expressions_list, expression_view, readable_save, tag_tree_save, tagged_content_create, job_start, job_complete, export_download.
- Stockage: côté serveur (si BFF) ou service analytics (configurable).

Dev & Déploiement — Docker-first (exigences obligatoires)
- Politique: tout développement doit prioriser un déploiement Docker et être testé dans Docker en continu (pas seulement en fin de sprint).
- Cibles Docker:
  - MyWebIntelligenceAPI (FastAPI) + PostgreSQL + Redis + Celery worker + (optionnel) Flower + Prometheus/Grafana (si activés).
  - MyWebClient (BFF Node/Express + client React).
- Composition:
  - Utiliser docker-compose pour le dev local (fichier docker-compose.yml à fournir/mettre à jour) avec réseaux internes dédiés.
  - Variables d’environnement pilotées par .env/.env.production (API_BASE_URL, WS_URL, JWT, CORS, etc.).
- Build images:
