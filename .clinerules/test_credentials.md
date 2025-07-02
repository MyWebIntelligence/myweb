# Informations de Connexion pour les Tests `curl`

Ce document résume toutes les informations de connexion et les clés nécessaires pour tester l'API MyWebIntelligenceAPI avec `curl`.

---

## 1. Utilisateur Admin

-   **Nom d'utilisateur :** `admin@example.com`
-   **Mot de passe :** `changethispassword`

---

## 2. Token d'Authentification (JWT)

-   **Token d'accès (Bearer Token) :**
    ```
    eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJleHAiOjE3NTEzOTY1MTUsInN1YiI6ImFkbWluQGV4YW1wbGUuY29tIn0.7IbHIblOFaD-zKEZGXeyfmdCSqe1XAlRaNEm4P1hxM0
    ```

---

## 3. Endpoints de l'API

-   **URL de base :** `http://localhost:8000`
-   **Endpoint de connexion :** `/api/v1/v1/auth/login`
-   **Endpoint de création de land :** `/api/v1/v1/lands/`
-   **Endpoint de création de tag :** `/api/v1/tags/`

---

## 4. Exemples de Commandes `curl`

### **Authentification (Réussie)**

```bash
curl -X POST "http://localhost:8000/api/v1/v1/auth/login" \
     -H "Content-Type: application/x-www-form-urlencoded" \
     -d "username=admin@example.com&password=changethispassword"
```

### **Création d'un Land (Réussie)**

```bash
curl -X POST "http://localhost:8000/api/v1/v1/lands/" \
     -H "Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJleHAiOjE3NTEzOTY1MTUsInN1YiI6ImFkbWluQGV4YW1wbGUuY29tIn0.7IbHIblOFaD-zKEZGXeyfmdCSqe1XAlRaNEm4P1hxM0" \
     -H "Content-Type: application/json" \
     -d '{"name": "Test Land", "description": "Land de test", "start_urls": ["https://example.com"]}'
```

### **Ajout de termes à un Land (✅ TESTÉ ET FONCTIONNEL)**

*L'endpoint pour l'ajout de termes à un land a été testé avec succès.*

L'endpoint `/api/v1/v1/lands/{land_id}/terms` permet d'ajouter des mots de relevance à un land.

**Test réussi le 2025-07-02 :**
- Status Code: 200 
- Land ID testé: 2
- Termes ajoutés: ["intelligence", "artificielle", "web", "crawling", "test"]

```bash
curl -X POST "http://localhost:8000/api/v1/v1/lands/2/terms" \
     -H "Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJleHAiOjE3NTEzOTY1MTUsInN1YiI6ImFkbWluQGV4YW1wbGUuY29tIn0.7IbHIblOFaD-zKEZGXeyfmdCSqe1XAlRaNEm4P1hxM0" \
     -H "Content-Type: application/json" \
     -d '{"terms": ["intelligence", "artificielle", "web", "crawling", "test"]}'
```

**Corrections techniques apportées:**
- Relation many-to-many entre Land et Word via LandDictionary
- Fonction CRUD add_terms_to_land avec gestion des doublons
- Lemmatisation basique (conversion en lowercase)
- Tests automatisés avec `test_addterms_simple.py`

---
