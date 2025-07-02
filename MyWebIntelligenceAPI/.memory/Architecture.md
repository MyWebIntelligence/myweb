# Architecture de l’API MyWebIntelligence

L’architecture de MyWebIntelligence s’articule en deux parties principales : le client web (_MyWebClient_) et l’API (_MyWebIntelligenceAPI_). Le _client_ est une application React/Node.js (dossier `MyWebClient`) qui sert l’interface utilisateur, tandis que l’_API_ est réalisée en Python avec FastAPI (dossier `MyWebIntelligenceAPI`). L’environnement est orchestré par Docker Compose (voir _docker-compose.yml_[GitHub](docker-compose.yml)[GitHub](docker-compose.yml)) : on y trouve les services **postgres** (base de données PostgreSQL), **redis** (broker de tâches), **mywebintelligenceapi** (API FastAPI), **mywebclient** (client web), un **celery\_worker** (exécutant les tâches asynchrones), un **flower** (monitoring Celery), ainsi que **Prometheus/Grafana** pour la supervision.

Dans l’API, l’organisation suit le schéma classique **FastAPI + SQLAlchemy + Celery**. Le dossier `app/core` contient les configurations et la logique métier centrale (p. ex. `crawler_engine.py`, `content_extractor.py`, `media_processor.py`, `text_processing.py`). Les modèles SQLAlchemy sont dans `app/db/models` (ex. `models.Land`, `models.Expression`, etc.), accompagnés de schémas Pydantic dans `app/schemas`. Les opérations CRUD sur la base sont implémentées dans `app/crud/` (ex. `crud_land.py`, `crud_expression.py`, `crud_media.py`, `crud_job.py`). Les **endpoints REST** sont définis sous `app/api/v1/endpoints/` (par ex. `lands.py`, `expressions.py`, `jobs.py`), exposant la gestion des lands, expressions, utilisateurs, tâches, etc. (login/authentification, CRUD de Land, lancement de crawl, etc.).

Les **dépendances internes** incluent notamment l’accès à la BD via SQLAlchemy (avec PostgreSQL), l’envoi de requêtes HTTP asynchrones via `httpx` ou `aiohttp`, et les calculs via des bibliothèques NLP (NLTK), de traitement d’image (Pillow, scikit-learn) et de scraping (BeautifulSoup, Trafilatura, Newspaper, readability). Externes, on trouve la gestion de l’authentification (JWT via python-jose), la manipulation d’images (ImageHash, ColorThief), l’archivage (archive.org via `internetarchive`), etc. Un exemple de configuration Docker liste ces technologies clés dans _requirements.txt_[GitHub](MyWebIntelligenceAPI/requirements.txt).

Les **points d’entrée API** comprennent au moins les routes suivantes (extraits des endpoints) :

- **`/api/v1/lands`** : CRUD des « lands » (projets d’analyse), création et listing des lands pour l’utilisateur courant[GitHub](MyWebIntelligenceAPI/app/api/v1/endpoints/lands.py)[GitHub](MyWebIntelligenceAPI/app/api/v1/endpoints/lands.py).
    
- **`/api/v1/lands/{land_id}/crawl`** : lance en tâche asynchrone un crawl pour le land donné (via Celery)[GitHub](MyWebIntelligenceAPI/app/api/v1/endpoints/lands.py)[GitHub](MyWebIntelligenceAPI/app/tasks/crawling_task.py).
    
- **`/api/v1/lands/{land_id}/consolidate`** : lance la consolidation des données d’un land[GitHub](MyWebIntelligenceAPI/app/api/v1/endpoints/lands.py).
    
- **`/api/v1/expressions`** (probablement) : accès aux expressions collectées (CRUD, filtrage, pagination) – en cours d’implémentation.
    
- **`/api/v1/jobs`** : suivi des tâches de crawling/consolidation (status, annulation, historique).
    

La base de données interne contient des entités telles que _Land_ (projet thématique), _Expression_ (URL analysée), _ExpressionLink_ (arêtes entre pages), _Media_ (média/image extraits), _Word/LandDictionary_ (pour le scoring), ainsi qu’un modèle _CrawlJob_ pour tracer l’état des tâches (créé par `crud_job.create`)[GitHub](MyWebIntelligenceAPI/app/tasks/crawling_task.py)[GitHub](MyWebIntelligenceAPI/app/crud/crud_job.py).

En résumé, l’architecture technique est la suivante :

- **Front-end** : React + Bootstrap pour l’UI, packagé via Node.js (MyWebClient)[GitHub](MyWebClient/client/src/index.js).
    
- **Back-end API** : FastAPI (Python) exposant des endpoints REST, utilisant SQLAlchemy (PostgreSQL) pour la persistance. Les requêtes HTTP (crawling) sont gérées en async via `httpx`. Les données extraites sont stockées en BD et accessibles via l’API.
    
- **Workers asynchrones** : tâches Celery (broker Redis) pour exécuter les crawls et consolidations en arrière-plan[GitHub](MyWebIntelligenceAPI/app/core/celery_app.py)[GitHub](MyWebIntelligenceAPI/app/tasks/crawling_task.py). Chaque tâche crée un _job_ en base et met à jour le statut du land (RUNNING, COMPLETED, FAILED).
    
- **Base de données** : PostgreSQL. Les modèles incluent Land, Expression, Domain, Media, Word, LandDictionary, CrawlJob, etc. (Cf. README et code)[GitHub](.crawlerOLD_APP/model.py)[GitHub](MyWebIntelligenceAPI/app/crud/crud_job.py).
    
- **Monitoring** : Prometheus (via starlette-prometheus) et Grafana pour la collecte de métriques système/API.
    
- **Dépendances** : Voir _requirements.txt_[GitHub](MyWebIntelligenceAPI/requirements.txt), notamment FastAPI/Uvicorn, SQLAlchemy, Celery, Redis, httpx, Trafilatura, BeautifulSoup, Pillow, scikit-learn, etc.
    

En pratique, l’application se déploie via `docker-compose up`, qui démarre ces conteneurs interconnectés[GitHub](docker-compose.yml)[GitHub](docker-compose.yml). L’API écoute sur le port 8000, et le client sur le port 3002. Les services intérieurs collaborent ainsi pour fournir l’ensemble des fonctionnalités de crawling, traitement et restitution.

# Pipelines fonctionnels

Les pipelines de traitement implémentés suivent principalement les étapes de _crawling_ de pages Web, d’extraction de contenu, d’enrichissement (liens, médias, scoring) et de **restauration via l’API**. Les principaux sont :

- ## Pipeline de Crawling
    
    Cette pipeline parcourt les URL (« expressions ») d’un land et les analyse. L’ordre d’exécution est :
    
    1. **Sélection des expressions à crawler** : la tâche Celery appelle `CrawlingService.crawl_land_directly(land_id)`[GitHub](MyWebIntelligenceAPI/app/tasks/crawling_task.py). Celui-ci récupère les _expressions_ non encore traitées via `crud_expression.get_expressions_to_crawl` (filtrant par land, statut HTTP, profondeur, etc.)[GitHub](MyWebIntelligenceAPI/app/crud/crud_expression.py).
        
    2. **Traitement de chaque expression** : pour chaque URL, `CrawlerEngine.crawl_expression(expr, ...)` est exécuté[GitHub](MyWebIntelligenceAPI/app/core/crawler_engine.py). Cette méthode :
        
        - Effectue la requête HTTP asynchrone pour récupérer le HTML brut (via `http_client.get`) – en gérant le _User-Agent_ et timeout (cf. `crawler_engine.py`, section HTTP).
            
        - Si l’accès direct échoue, tente d’obtenir un snapshot sur Archive.org, ou en dernier recours une requête directe (cf. pipeline en commentaire dans le code _core.py_ historique). Le code actuel assure déjà une seule tentative avec httpx, mais la logique d’Archive.org peut être intégrée.
            
        - Appelle `get_readable_content(html)`[GitHub](MyWebIntelligenceAPI/app/core/content_extractor.py) pour extraire le texte lisible. Ce code utilise _Trafilatura_ en priorité (extraction propre de texte) et, si Trafilatura ne donne pas assez de contenu, retombe sur un nettoyage basique via BeautifulSoup.
            
        - Extrait les métadonnées du HTML (titre, description, mots-clés, langue) via `get_metadata(soup, url)`[GitHub](MyWebIntelligenceAPI/app/core/content_extractor.py).
            
        - Stocke ces informations dans l’objet `expr` (modèle SQLAlchemy) : champ `title`, `description`, `keywords`, `lang`, ainsi que `readable` pour le contenu. Le champ `readable_at` est mis à jour avec l’heure actuelle.
            
        - **Scoring** : calcule la pertinence de la page via `expression_relevance(dictionary, expr)`[GitHub](MyWebIntelligenceAPI/app/core/text_processing.py)[GitHub](MyWebIntelligenceAPI/app/core/text_processing.py). Cette fonction fait du tokenizing/stemming (NLTK) du titre et du contenu, puis compte les occurrences pondérées des lemmes du _dictionnaire du land_. Le score obtenu (int) est stocké dans `expr.relevance`.
            
        - Si le score est positif (>0), on considère la page « approuvée » et on met à jour `expr.approved_at`.
            
        - **Extraction de liens et médias** :
            
            - Pour les médias : `CrawlerEngine._extract_media(soup, expr)` collecte toutes les URLs d’images/vidéos dans la page (balises `<img>`, `<video>`, etc.), normalise les URLs, puis pour chaque URL appelle `MediaProcessor.analyze_image(url)`[GitHub](MyWebIntelligenceAPI/app/core/media_processor.py). Cette analyse asynchrone télécharge l’image (via `httpx`), calcule un hash (SHA256), lit ses dimensions et format (via Pillow), détecte la transparence, et (si activé) calcule les couleurs dominantes via _KMeans_ (sklearn) et les convertit en couleurs _web-safe_[GitHub](MyWebIntelligenceAPI/app/core/media_processor.py)[GitHub](MyWebIntelligenceAPI/app/core/media_processor.py)[GitHub](MyWebIntelligenceAPI/app/core/media_processor.py). Les métadonnées EXIF basiques sont également extraites. Le résultat (dict) est stocké en base via `crud_media.create_media(...)`.
                
            - Pour les liens : `CrawlerEngine._extract_links(soup, expr)` cherche tous les `<a>` dans la page. Pour chaque URL cible, on vérifie si elle est « crawlable » (commence par http/https et n’est pas un type de fichier exclu). Si oui, on obtient ou crée une `Expression` correspondante (`crud_expression.get_or_create_expression(db, land_id, url, depth)`) et on crée un lien `ExpressionLink(source=expr, target=new_expr)` pour maintenir le graphe[GitHub](MyWebIntelligenceAPI/app/core/crawler_engine.py).
                
        - Chaque expression est validée et `db.commit()` est fait pour sauvegarder tous ces changements (métadonnées, contenu, médias, liens).
            
        - Le résultat de `crawl_expression` est comptabilisé (succès ou erreur).
            
    
    Au final, la tâche Celery `crawl_land_task` renvoie le nombre de pages traitées et d’erreurs[GitHub](MyWebIntelligenceAPI/app/tasks/crawling_task.py). Elle met aussi à jour le statut du land en base (RUNNING, puis COMPLETED/FAILED) via `crud_land.update_land_status`[GitHub](MyWebIntelligenceAPI/app/tasks/crawling_task.py).
    
- ## Pipeline de Consolidation
    
    Ce pipeline réévalue les expressions déjà crawlées pour recalculer leur pertinence et re-extraire liens et médias à partir du contenu stocké. Déclenché par `consolidate_land_task` ou l’endpoint `POST /lands/{id}/consolidate`. Les étapes principales :
    
    1. Récupération du dictionnaire du land et des expressions déjà crawlées (non-null `fetched_at`) via `crud_expression.get_expressions_to_consolidate` (avec éventuellement filtre par profondeur/limite).
        
    2. Pour chaque `expr` extrait :
        
        - Recalcule le score de pertinence via `expression_relevance` (idéalement avec le même dictionnaire) et met à jour `expr.relevance` si besoin.
            
        - Parcourt `expr.readable` (le HTML « lisible » déjà stocké) avec BeautifulSoup. Puis ré-extrait **liens** (`_extract_and_save_links`) et **médias** (`_extract_and_save_media`) exactement comme dans le crawl initial[GitHub](MyWebIntelligenceAPI/app/core/crawler_engine.py). On supprime d’abord les anciennes entrées de liens/médias pour cette expression, puis on recrée depuis le contenu mis en cache.
            
        - Commit en base.
            
    
    Ce pipeline permet par exemple d’appliquer de nouveaux critères (mise à jour du dictionnaire, changement de profondeur) aux expressions existantes. Il maintient à jour le graphe de liens et les médias associés, et remplit les champs de pertinence qui peuvent avoir changé. Au retour, on obtient à nouveau un tuple (traités, erreurs)[GitHub](MyWebIntelligenceAPI/app/core/crawler_engine.py)[GitHub](MyWebIntelligenceAPI/app/core/crawler_engine.py).
    
- ## Extraction et Enrichissement
    
    - **Extraction de contenu (« readable »)** : pour chaque page crawlée, le pipeline utilise _Trafilatura_ pour obtenir le texte principal, ou en tombe-backs sur BeautifulSoup si nécessaire (cf. `get_readable_content`[GitHub](MyWebIntelligenceAPI/app/core/content_extractor.py)). Les métadonnées HTML (titre, description, keywords, langue) sont extraites par `get_metadata`[GitHub](MyWebIntelligenceAPI/app/core/content_extractor.py). Ces opérations constituent le cœur de l’« extraction readable ».
        
    - **Analyse média** : déjà décrite ci-dessus dans le crawling. Pour chaque image, `MediaProcessor` génère un rapport complet (dimensions, format, hash, couleurs dominantes, EXIF)[GitHub](MyWebIntelligenceAPI/app/core/media_processor.py). Tous ces attributs sont persistés en BD (modèle `Media`) pour chaque URL d’image.
        
    - **Scoring / Pertinence** : la fonction `expression_relevance` (dans `text_processing.py`) réalise le tokenizing/stemming avec NLTK pour français puis compte les occurrences des lemmes du dictionnaire du land (poids 10 pour le titre, 1 pour le contenu)[GitHub](MyWebIntelligenceAPI/app/core/text_processing.py). Elle retourne un score entier stocké dans l’expression, influençant l’autorisation de la page (« approved\_at »).
        
- ## Restitution via l’API
    
    Après traitement, les résultats peuvent être interrogés par l’API. Les endpoints exposent les données ainsi traitées – par exemple, un GET sur `/lands/{id}` renvoie les métadonnées du land avec ses expressions associées, incluant pour chaque page son titre, url, score, date de crawl, etc. D’autres endpoints permettront d’accéder aux liens (relations entre expressions) et médias, ou de déclencher l’export de données. L’API ne comprend pas de front-end de rendu : la restitution s’effectue via JSON (par ex. listes d’expressions) que le _client_ React affichera.
    
    Le lancement de chaque pipeline se fait généralement par un appel à l’API qui démarre une tâche Celery (par exemple `POST /lands/{id}/crawl` crée un _CrawlJob_ en base et renvoie un job\_id[GitHub](MyWebIntelligenceAPI/app/tasks/crawling_task.py)). Le suivi s’effectue via l’endpoint jobs (à implémenter) ou via WebSocket (prévu).
    

# Écarts entre ancienne et nouvelle version

Le répertoire `.crawlerOLD_APP` contient l’ancienne implémentation CLI. Plusieurs fonctionnalités existantes dans l’ancienne version n’ont pas (encore) été réimplémentées dans la version actuelle :

- **Gestion des domaines** : l’ancien code possédait un modèle _Domain_ et un contrôleur `DomainController` qui permettaient de crawler séparément les homepages des domaines référencés (avec statuts HTTP, métadonnées de domaine)[GitHub](.crawlerOLD_APP/core.py). La version actuelle n’a pas d’équivalent : il n’existe pas d’endpoint ni de modèle _Domain_ géré (le modèle existe en BD, mais aucun endpoint public ni tâche n’y fait référence). Il manquerait la logique de `crawl_domains()` qui alimentait la table Domain ainsi que la mise à jour heuristique (`update_heuristic()`) qui synchronisait les noms de domaines des expressions. Cela a pour impact qu’aucune information sur les domaines (http\_status, titre du site, etc.) n’est collectée actuellement.
    
- **Tagging et catégories de contenu** : l’ancienne version comportait un modèle `Tag` et `TaggedContent`, ainsi qu’un `TagController` pour exporter des tags (types « matrix » ou « content »)[GitHub](.crawlerOLD_APP/controller.py). Rien de semblable n’existe dans la nouvelle API. Or l’ancien pipeline Média pré-calculait également des « content\_tags » et un « nsfw\_score » pour chaque image (colonnes `Media.content_tags` et `Media.nsfw_score`[GitHub](.crawlerOLD_APP/model.py)[GitHub](.crawlerOLD_APP/model.py)). Ces champs ne sont pas pris en charge dans le code Python actuel. Pour reproduire entièrement l’ancienne application, il faudrait implémenter l’analyse de contenu des images (reconnaissance de labels ou détection NSFW) et les stocker, ainsi qu’un mécanisme de génération de tags à partir des textes/pages.
    
- **Pipeline Mercury (readable pipeline)** : l’ancienne version offrait un pipeline `MercuryReadablePipeline` (fichier _readable\_pipeline.py_) qui utilisait l’outil Mercury Parser pour extraire de manière enrichie et fusionner les contenus (« smart merge », etc.)[GitHub](.crawlerOLD_APP/readable_pipeline.py)[GitHub](.crawlerOLD_APP/readable_pipeline.py). Cette logique avancée de lecture de pages, incluant fusion intelligente et traitement batch, n’est pas présente dans la nouvelle API. À la place, seul Trafilatura/BS est utilisé via `content_extractor.py`. Reprendre le pipeline Mercury (avec ses stratégies de fusion de champs) pourrait améliorer la qualité de l’extraction de contenu si nécessaire.
    
- **Export de données** : l’ancienne application proposait des exports complets via la classe `Export` (formats CSV, GEXF, etc.) – par exemple les commandes `land export` ou `tag export` appelaient `core.export_land()` et `core.export_tags()` pour créer des fichiers dans `settings.data_location`[GitHub](.crawlerOLD_APP/core.py)[GitHub](.crawlerOLD_APP/core.py). La nouvelle API ne contient pas ces fonctionnalités d’export (les endpoints correspondants ne sont pas encore implémentés). Il manque donc l’équivalent de ces exports, que l’on retrouverait dans un futur `export_task` ou endpoint `/export`.
    
- **Analyse des médias (hors visuels)** : dans l’ancien code, `MediaAnalyzer` permettait d’analyser séquentiellement tous les médias existants d’un land[GitHub](.crawlerOLD_APP/controller.py). Il gérait notamment le téléchargement des images et stockait la date d’analyse, les erreurs, etc. Aujourd’hui, l’analyse d’image est exécutée _dans_ le pipeline de crawling (MediaProcessor) et les métadonnées sont directement écrites. Cependant, les fonctionnalités facultatives (filtrage par taille minimale, nombre de couleurs, etc.) sont reproduites en partie. Il reste à vérifier des options comme les retries ou timeouts du downloader, ainsi que les critères de taille (les settings YAML ne sont pas exposés pour le moment).
    
- **Mise à jour heuristique** : l’ancien script inclut `core.update_heuristic()`, qui parcourait toutes les expressions et recalculait leur domaine (via `get_domain_name`), afin de migrer une expression vers un nouvel enregistrement `Domain` si le nom différait[GitHub](.crawlerOLD_APP/core.py). Cet utilitaire n’existe pas dans la nouvelle codebase. Son absence implique que si un URL a été rattaché initialement au mauvais domaine, cela n’est pas corrigé automatiquement.
    
- **Contrôleur Land avancé** : des commandes CLI comme `land addterm` et `land addurl` permettaient d’ajouter manuellement des termes au dictionnaire du land ou des URL en lot[GitHub](.crawlerOLD_APP/controller.py)[GitHub](.crawlerOLD_APP/controller.py). Dans l’API actuelle, l’ajout de termes au dictionnaire n’est pas encore exposé (pas d’endpoint `/lands/{id}/addterm` par défaut), et l’ajout d’expressions se fait implicitement via crawl et lien(s). Pour une fonctionnalité équivalente, on pourrait prévoir un endpoint pour injecter des termes ou URL manuellement.
    
- **Stratégies avancées de crawling** : l’ancienne version gérait des filtres supplémentaires (statut HTTP, limites de pertinence, _robots.txt_, profondeur, recrawl selon status) mentionnés dans le README et les controllers CLI[GitHub](.crawlerOLD_APP/cli.py). Le nouveau code prévoit des paramètres (`limit`, `http`, `depth` dans les endpoints et services), mais certains aspects comme le respect de robots.txt ou un filtrage sur la pertinence minimale ne semblent pas implémentés. Reprendre ces fonctionnalités améliore le contrôle du crawl.
    

En résumé, pour que la nouvelle application soit une réplique complète de l’ancienne, il faudrait réimplémenter notamment **la gestion des domaines**, **la génération et export de tags**, **l’export de données** et **le pipeline de fusion de contenu (Mercury)**. Chacune de ces fonctionnalités manque à l’appel :

- _Export de Land/Tags_ : rôle = permettre d’exporter les données en CSV/GEXF/ZIP, logique = utiliser la classe `Export` de l’ancien code pour formater les graphes et pages (impact : ajout de jobs d’export et endpoints associés).
    
- _Tagging_ : rôle = créer des catégories à partir du contenu crawlé (p. ex. extraire des mots-clés ou labels d’images), logique = importer le schéma `Tag`/`TaggedContent` et les routines de `export_tags()`[GitHub](.crawlerOLD_APP/controller.py)[GitHub](.crawlerOLD_APP/core.py) (impact : enrichissement des médias/expressions avec des tags, nouvelle table en base).
    
- _Update des domaines_ : rôle = corriger les noms de domaines des expressions, logique = reprendre `update_heuristic()`[GitHub](.crawlerOLD_APP/core.py) (impact : cohérence du modèle Domain).
    
- _Pipeline Mercury_ : rôle = extraire plus intelligemment le contenu des pages, logique = intégrer `readable_pipeline.py` dans `core/content_extractor.py`[GitHub](MyWebIntelligenceAPI/.memory/DEVELOPMENT_STATUS.md) (impact : qualité d’extraction potentiellement meilleure).
    
- _Export média complet_ : dans l’ancien, `mediacsv` était un type d’export (pages d’images). Non présent dans le nouveau.
    

Chaque item ci-dessus nécessiterait l’ajout de méthodes/contrôleurs dédiés dans l’API (ou des scripts CLI), ainsi que l’enrichissement des modèles de données si nécessaire. Par exemple, réintroduire la table _Tag_ avec ses champs, ou étendre _Media_ pour les scores de contenu NSFW. Cela impliquera de mettre à jour l’architecture (nouveaux endpoints, nouveaux jobs Celery pour l’export, etc.).

En conclusion, la structure de base (FastAPI + SQLAlchemy + Celery) est en place et correspond bien au système historique, mais certains traitements avancés (tags, exports, heuristiques) restent à implémenter pour atteindre une parité fonctionnelle complète avec l’ancienne version.

**Sources internes** : description de l’architecture et des pipelines basée sur le code du dépôt (notamment _crawler\_engine.py_[GitHub](MyWebIntelligenceAPI/app/core/crawler_engine.py)[GitHub](MyWebIntelligenceAPI/app/core/crawler_engine.py), _text\_processing.py_[GitHub](MyWebIntelligenceAPI/app/core/text_processing.py), _content\_extractor.py_[GitHub](MyWebIntelligenceAPI/app/core/content_extractor.py), _media\_processor.py_[GitHub](MyWebIntelligenceAPI/app/core/media_processor.py)[GitHub](MyWebIntelligenceAPI/app/core/media_processor.py), _crawling\_task.py_[GitHub](MyWebIntelligenceAPI/app/tasks/crawling_task.py), endpoints _lands.py_[GitHub](MyWebIntelligenceAPI/app/api/v1/endpoints/lands.py), et modèles/contrôleurs anciens[GitHub](.crawlerOLD_APP/model.py)[GitHub](.crawlerOLD_APP/controller.py)). Ces extraits illustrent les fonctions clés des pipelines et les différences structurelles entre les versions.