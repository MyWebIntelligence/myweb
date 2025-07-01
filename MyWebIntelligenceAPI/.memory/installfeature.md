# Bug Report: Échec du démarrage de l'API dans Docker

**Date :** 01/07/2025

## Description du problème

Le service `MyWebIntelligenceAPI` ne parvient pas à démarrer correctement lors de l'exécution de `docker-compose up`. Le conteneur entre dans une boucle de redémarrage, ce qui empêche l'API de devenir accessible. Ce problème a été découvert en tentant de tester l'endpoint d'authentification `/api/v1/auth/login`.

## Analyse de la cause racine

Le problème principal semble être une `ImportError` persistante au sein de l'application FastAPI. Les journaux montrent de manière constante que les modules ne peuvent pas être résolus, l'erreur la plus récente étant liée à l'importation de `JobStatus`.

Cela indique un problème fondamental avec la manière dont la résolution des importations Python fonctionne à l'intérieur du conteneur Docker, probablement lié à un `PYTHONPATH` incorrect ou à une mauvaise interprétation de la structure du projet.

## Étapes de débogage effectuées

1.  **Configuration initiale :** Tentative de lancement des services avec `docker-compose up -d`.
2.  **Conflits de dépendances :**
    - Résolution d'un conflit de dépendances `pip` entre `prometheus-client` et `starlette-prometheus` en modifiant la version de `prometheus-client` dans `requirements.txt`.
    - Ajout de la dépendance manquante `email-validator` à `requirements.txt`.
3.  **Restructuration du projet :**
    - Déplacement des composants `client` et `server` dans un répertoire `MyWebClient` dédié pour clarifier la structure.
    - Mise à jour du fichier `docker-compose.yml` pour refléter les nouveaux chemins.
4.  **Correction des Dockerfile et des importations :**
    - Correction des chemins des `Dockerfile` dans `docker-compose.yml`.
    - Tentatives de correction des erreurs d'importation en passant d'importations relatives à absolues.
    - Ajout de `ENV PYTHONPATH=/app` au `Dockerfile` de `MyWebIntelligenceAPI`.
5.  **Résolution des importations :**
    - Correction de plusieurs importations incorrectes liées à `JobStatus` et `CrawlStatus` dans les modules `schemas`, `crud` et `tasks`.

## État actuel

Malgré ces corrections, le service API reste instable et ne parvient pas à démarrer, ce qui empêche le traitement des requêtes. La commande `curl` vers l'endpoint de connexion reste bloquée.

## Prochaines étapes pour la reprise

1.  **Vérifier le `PYTHONPATH` :** Examiner à nouveau comment le `PYTHONPATH` est défini et utilisé dans le conteneur `api`.
2.  **Standardiser les importations :** S'assurer que toutes les importations au sein de l'application sont cohérentes (probablement absolues à partir de `app`).
3.  **Reconstruire les images :** Supprimer toutes les images Docker (`docker-compose down --rmi all`) et les reconstruire pour éviter tout problème de cache.
4.  **Démarrage incrémentiel :** Essayer de démarrer uniquement le service `api` et ses dépendances directes pour mieux isoler le problème.
