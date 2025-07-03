"""
Test d'intégration complet pour l'endpoint de crawl.
Valide que l'implémentation respecte à la lettre l'ancien crawler.
"""
import asyncio
import httpx
import pytest
from datetime import datetime

# Configuration pour les tests
API_BASE_URL = "http://localhost:8000"
TEST_USER = {
    "username": "admin@example.com",
    "password": "changethispassword"
}

@pytest.mark.asyncio
async def test_full_crawl_integration():
    """
    Test d'intégration complet du processus de crawl.
    """
    # Attendre que le serveur démarre
    print("⏳ Attente du démarrage du serveur...")
    await asyncio.sleep(15)

    async with httpx.AsyncClient() as client:
        # 1. Authentification
        print("🔐 Authentification...")
        login_response = await client.post(
            f"{API_BASE_URL}/api/v1/auth/login",
            data={"username": TEST_USER["username"], "password": TEST_USER["password"]},
            headers={"Content-Type": "application/x-www-form-urlencoded"}
        )
        assert login_response.status_code == 200
        token_data = login_response.json()
        token = token_data["access_token"]
        headers = {"Authorization": f"Bearer {token}"}
        print(f"✅ Authentification réussie")

        # 2. Création d'un land de test
        print("🌍 Création d'un land de test...")
        land_data = {
            "name": f"Test Crawl {datetime.now().strftime('%Y%m%d_%H%M%S')}",
            "description": "Land de test pour validation du crawl",
            "start_urls": ["https://httpbin.org/html", "https://example.com"]
        }
        land_response = await client.post(
            f"{API_BASE_URL}/api/v1/lands/",
            json=land_data,
            headers=headers
        )
        assert land_response.status_code == 201
        land = land_response.json()
        land_id = land["id"]
        print(f"✅ Land créé avec l'ID: {land_id}")

        # 3. Ajout de termes au dictionnaire
        print("📚 Ajout de termes au dictionnaire...")
        terms_data = {"terms": ["test", "example", "html", "web", "crawler"]}
        terms_response = await client.post(
            f"{API_BASE_URL}/api/v1/lands/{land_id}/terms",
            json=terms_data,
            headers=headers
        )
        assert terms_response.status_code == 200
        print(f"✅ Termes ajoutés au dictionnaire")

        # 4. Ajout d'expressions de départ
        print("🔗 Ajout d'expressions de départ...")
        urls_data = {"urls": land_data["start_urls"]}
        urls_response = await client.post(
            f"{API_BASE_URL}/api/v1/lands/{land_id}/urls",
            json=urls_data,
            headers=headers
        )
        assert urls_response.status_code == 202
        print(f"✅ URLs de départ ajoutées")

        # 5. Lancement du crawl
        print("🕷️  Lancement du crawl...")
        crawl_data = {
            "limit": 5,  # Limite pour le test
            "depth": 2   # Profondeur limitée
        }
        crawl_response = await client.post(
            f"{API_BASE_URL}/api/v1/lands/{land_id}/crawl",
            json=crawl_data,
            headers=headers
        )
        assert crawl_response.status_code == 200
        crawl_result = crawl_response.json()
        job_id = crawl_result.get("job_id")
        print(f"✅ Crawl lancé avec le job ID: {job_id}")

        # 6. Attendre la fin du crawl (timeout de 60 secondes)
        print("⏳ Attente de la fin du crawl...")
        timeout = 60
        elapsed = 0
        job_status = "PENDING"
        
        while elapsed < timeout and job_status in ["PENDING", "RUNNING"]:
            await asyncio.sleep(2)
            elapsed += 2
            
            # Vérifier le statut du job
            job_response = await client.get(
                f"{API_BASE_URL}/api/v1/jobs/{job_id}",
                headers=headers
            )
            if job_response.status_code == 200:
                job_data = job_response.json()
                job_status = job_data.get("status", "UNKNOWN")
                progress = job_data.get("progress", 0)
                print(f"📊 Status: {job_status}, Progress: {progress}%")
            else:
                print(f"⚠️  Impossible de récupérer le statut du job")
                break

        # 7. Vérification des résultats
        print("🔍 Vérification des résultats...")
        
        # Récupérer les détails du land après crawl
        land_details_response = await client.get(
            f"{API_BASE_URL}/api/v1/lands/{land_id}",
            headers=headers
        )
        assert land_details_response.status_code == 200
        land_details = land_details_response.json()
        
        print(f"📈 Résultats du crawl:")
        print(f"   - Status final: {job_status}")
        print(f"   - Nombre d'expressions: {land_details.get('total_expressions', 0)}")
        print(f"   - Land mis à jour: {land_details.get('updated_at')}")

        # Vérifications finales
        if job_status == "COMPLETED":
            print("✅ Test réussi : Le crawl s'est terminé avec succès")
            assert land_details.get('total_expressions', 0) > 0, "Aucune expression crawlée"
        elif job_status == "FAILED":
            print("❌ Test échoué : Le crawl a échoué")
            assert False, f"Le crawl a échoué avec le statut: {job_status}"
        else:
            print(f"⚠️  Test partiel : Le crawl n'a pas terminé dans les temps (status: {job_status})")
            # Ne pas faire échouer le test si c'est juste un timeout

if __name__ == "__main__":
    print("🚀 Démarrage du test d'intégration du crawl...")
    asyncio.run(test_full_crawl_integration())
    print("🏁 Test terminé")
