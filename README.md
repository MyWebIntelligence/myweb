# MyWebIntelligence Project

Ce projet contient deux applications principales :

- **MyWebClient** : Une application web (client et serveur) qui fournit l'interface utilisateur.
- **MyWebIntelligenceAPI** : Une API FastAPI pour le crawling et l'analyse de contenu.

L'ensemble de l'environnement est géré par Docker et orchestré avec `docker-compose`.

## 🚀 Démarrage Rapide

### Prérequis

- Docker et Docker Compose

### Installation

1.  **Cloner le projet**
    ```bash
    git clone <repository-url>
    cd MyWebIntelligenceProject
    ```

2.  **Configurer les variables d'environnement**

    Copiez le fichier d'exemple `.env.example` de `MyWebIntelligenceAPI` à la racine du projet :
    ```bash
    cp MyWebIntelligenceAPI/.env.example .env
    ```
    Modifiez le fichier `.env` si nécessaire.

3.  **Lancer les services**

    Depuis la racine du projet, exécutez la commande suivante pour construire les images et démarrer tous les conteneurs :
    ```bash
    docker-compose up -d
    ```

4.  **Appliquer les migrations de la base de données**

    Une fois les conteneurs démarrés, appliquez les migrations de la base de données pour l'API :
    ```bash
    docker-compose exec api alembic upgrade head
    ```

### Accès aux applications

- **MyWebClient** : [http://localhost:3002](http://localhost:3002)
- **MyWebIntelligenceAPI** : [http://localhost:8000](http://localhost:8000)
  - Documentation interactive (Swagger) : [http://localhost:8000/docs](http://localhost:8000/docs)
  - Documentation alternative (ReDoc) : [http://localhost:8000/redoc](http://localhost:8000/redoc)

## 🔧 Services

Le `docker-compose.yml` à la racine orchestre les services suivants :

- `postgres` : Base de données PostgreSQL.
- `redis` : Serveur Redis pour le caching et Celery.
- `api` : L'application `MyWebIntelligenceAPI`.
- `client` : L'application `MyWebClient`.
- `celery_worker` : Worker Celery pour les tâches asynchrones.
- `flower` : Interface de monitoring pour Celery.
- `prometheus` : Monitoring des métriques.
- `grafana` : Dashboards pour la visualisation des métriques.

## 🏗️ Structure du projet

```
.
├── MyWebClient/              # Application Web (React + Node.js)
│   ├── client/
│   ├── server/
│   └── Dockerfile
├── MyWebIntelligenceAPI/       # API FastAPI
│   ├── app/
│   └── Dockerfile
├── docker-compose.yml        # Orchestration des services
└── README.md                 # Ce fichier
```

## 🤝 Contribution

Pour contribuer, veuillez vous référer aux `README.md` spécifiques de chaque sous-projet.
