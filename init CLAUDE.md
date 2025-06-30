# Initialisation Claude/Cline pour MyWebClient

Ce document sert de guide rapide pour Claude/Cline afin de comprendre et d'interagir avec le projet MyWebClient.

## 1. Résumé exécutif du projet

**MyWebClient** est une application web développée avec React (frontend) et Node.js (backend API) qui interagit avec une base de données SQLite générée par le projet MyWebIntelligencePython. Son objectif principal est de fournir une interface graphique intuitive pour le nettoyage, l'organisation et l'analyse des informations.

## 2. Points d'entrée techniques clés

### Frontend (client/src)
- **`client/src/index.js`** : Point d'entrée principal de l'application React.
- **`client/src/app/Context.js`** : Gère le contexte global de configuration et les fonctions utilitaires partagées.
- **`client/src/components/App/App.js`** : Composant racine gérant l'état global et l'authentification.
- **`client/src/components/ExpressionExplorer/`** : Contient les composants pour l'affichage et l'édition des expressions.
- **`client/src/components/TagExplorer/`** : Contient les composants pour la gestion et l'exploration des tags.
- **`client/src/components/LandExplorer/`** : Contient les composants pour l'exploration des "lands" et leurs filtres.

### Backend (server/src)
- **`server/src/start.js`** : Point d'entrée du serveur Node.js.
- **`server/src/authRoutes.js`** : Définit les routes d'authentification (login, reset password).
- **`server/src/AdminDB.js`** : Gère les opérations sur la base de données d'administration (utilisateurs, logs, tokens).
- **`server/src/DataQueries.js`** : Contient les fonctions SQL pour interagir avec la base de données métier (expressions, tags, etc.).
- **`server/src/initAdmin.js`** : Script d'initialisation du compte administrateur.

## 3. Contexte de développement

- **Technologies** : ReactJS, Node.js (Express), SQLite.
- **Gestionnaire de paquets** : Yarn.
- **Conteneurisation** : Docker.
- **Conventions de code** : Suivre les standards React/JavaScript et Node.js.
- **Patterns architecturaux** : Séparation claire entre frontend et backend (API RESTful). Utilisation du contexte React pour la gestion de l'état global.

## 4. Actions courantes

- **Ajouter une nouvelle fonctionnalité** :
    - Identifier si la fonctionnalité est côté client, côté serveur, ou les deux.
    - Pour le client : créer de nouveaux composants React, mettre à jour le contexte si nécessaire, définir de nouvelles routes API si besoin.
    - Pour le serveur : ajouter de nouvelles routes dans `authRoutes.js` ou des fonctions de requête dans `DataQueries.js`, mettre à jour `AdminDB.js` si cela concerne l'administration.
- **Débugger** :
    - Côté client : utiliser les outils de développement du navigateur.
    - Côté serveur : consulter les logs du terminal où le serveur est lancé (`docker logs mwiclient` si Docker est utilisé).
    - Vérifier les appels API et les réponses.
- **Logs** : Les logs du serveur sont affichés dans la console. Les logs d'accès sont gérés par `AdminDB.js`.

## 5. Références rapides

- **Documentation complète du projet** : `README.md` (à la racine du projet).
- **Cartographie de l'application** : `memory-bank/AGENT.md`.
- **Pipelines fonctionnels** : `memory-bank/PIPELINES.md`.
- **Commandes Docker utiles** :
    - `docker ps` : Lister les conteneurs en cours.
    - `docker stop mwiclient` : Arrêter le conteneur.
    - `docker start mwiclient` : Redémarrer le conteneur.
    - `docker logs mwiclient` : Afficher les logs du conteneur.
    - `docker exec mwiclient cat /app/admin_password.txt` : Récupérer le mot de passe admin Docker.
- **Structure des données** : La base de données `mwi.db` est attendue dans le volume monté `/data` à l'intérieur du conteneur Docker.

Ce fichier devrait vous aider à démarrer rapidement sur le projet MyWebClient.
