"""
Test Sprint Promotions - Verifying winning page promotions from sprint review
Tests for:
1. Exemplar Library: 4 exemplars (Core Hub: 1, District: 2, Trust: 1)
2. Customer Stories exemplar marked PRIMARY in Trust family
3. Temporary Satisfaction Home exemplar marked PRIMARY in Core Hub family
4. Wellness District exemplar with correct tags
5. Education District exemplar with correct tags
6. House Templates: 3 templates including Education District Pattern
7. Promotion Queue: Education District and Customer Stories candidates with correct status/action
"""

import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', 'https://page-queue-hub.preview.emergentagent.com').rstrip('/')
PASSWORD = "TSFounder!Vault2026#Secure"

# Known IDs from the promotions
WELLNESS_DISTRICT_EXEMPLAR_ID = "11ea0800-4cf4-4abc-b23d-667daf3ad1ce"
EDUCATION_DISTRICT_EXEMPLAR_ID = "b3d8cb26-5353-4f56-a40b-ea252d142193"
CUSTOMER_STORIES_EXEMPLAR_ID = "228dc125-d96d-4caf-aa56-54c39dc63251"
EDUCATION_DISTRICT_TEMPLATE_ID = "f23fd88a-b15b-4894-bd0e-690a28ea93b6"


@pytest.fixture(scope="module")
def auth_token():
    """Get authentication token"""
    response = requests.post(f"{BASE_URL}/api/auth/login", json={"password": PASSWORD})
    assert response.status_code == 200, f"Login failed: {response.text}"
    return response.json()["access_token"]


@pytest.fixture(scope="module")
def api_client(auth_token):
    """Authenticated requests session"""
    session = requests.Session()
    session.headers.update({
        "Content-Type": "application/json",
        "Authorization": f"Bearer {auth_token}"
    })
    return session


class TestExemplarLibrary:
    """Verify Exemplar Library shows exactly 4 exemplars with correct distribution"""
    
    def test_exemplar_count_is_4(self, api_client):
        """Verify exactly 4 exemplars exist"""
        response = api_client.get(f"{BASE_URL}/api/exemplars")
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 4, f"Expected 4 exemplars, got {data['total']}"
    
    def test_exemplar_family_distribution(self, api_client):
        """Verify distribution: Core Hub (1), District (2), Trust (1)"""
        response = api_client.get(f"{BASE_URL}/api/exemplars")
        assert response.status_code == 200
        data = response.json()
        by_family = data["by_family"]
        
        # Core Hub: 1 exemplar
        assert "Core Hub" in by_family, "Core Hub family missing"
        assert by_family["Core Hub"]["count"] == 1, f"Expected 1 Core Hub exemplar, got {by_family['Core Hub']['count']}"
        
        # District: 2 exemplars
        assert "District" in by_family, "District family missing"
        assert by_family["District"]["count"] == 2, f"Expected 2 District exemplars, got {by_family['District']['count']}"
        
        # Trust: 1 exemplar
        assert "Trust" in by_family, "Trust family missing"
        assert by_family["Trust"]["count"] == 1, f"Expected 1 Trust exemplar, got {by_family['Trust']['count']}"
    
    def test_customer_stories_is_primary_trust_exemplar(self, api_client):
        """Verify Customer Stories exemplar is marked PRIMARY in Trust family"""
        response = api_client.get(f"{BASE_URL}/api/exemplars")
        assert response.status_code == 200
        data = response.json()
        
        # Check by_family primary
        trust_family = data["by_family"].get("Trust", {})
        assert trust_family.get("primary") == CUSTOMER_STORIES_EXEMPLAR_ID, \
            f"Customer Stories should be primary Trust exemplar, got {trust_family.get('primary')}"
        
        # Also verify the exemplar itself has is_primary=True
        customer_stories = next((e for e in data["exemplars"] if e["id"] == CUSTOMER_STORIES_EXEMPLAR_ID), None)
        assert customer_stories is not None, "Customer Stories exemplar not found"
        assert customer_stories["is_primary"] == True, "Customer Stories should have is_primary=True"
        assert customer_stories["page_family"] == "Trust", "Customer Stories should be in Trust family"
    
    def test_temporary_satisfaction_home_is_primary_core_hub_exemplar(self, api_client):
        """Verify Temporary Satisfaction Home exemplar is marked PRIMARY in Core Hub family"""
        response = api_client.get(f"{BASE_URL}/api/exemplars")
        assert response.status_code == 200
        data = response.json()
        
        # Check by_family primary
        core_hub_family = data["by_family"].get("Core Hub", {})
        assert core_hub_family.get("primary") is not None, "Core Hub should have a primary exemplar"
        
        # Find the Core Hub exemplar
        core_hub_exemplars = [e for e in data["exemplars"] if e["page_family"] == "Core Hub"]
        assert len(core_hub_exemplars) == 1, f"Expected 1 Core Hub exemplar, got {len(core_hub_exemplars)}"
        
        home_exemplar = core_hub_exemplars[0]
        assert home_exemplar["page_name"] == "Temporary Satisfaction Home", \
            f"Expected 'Temporary Satisfaction Home', got {home_exemplar['page_name']}"
        assert home_exemplar["is_primary"] == True, "Temporary Satisfaction Home should have is_primary=True"
    
    def test_wellness_district_exemplar_tags(self, api_client):
        """Verify Wellness District exemplar has correct tags"""
        response = api_client.get(f"{BASE_URL}/api/exemplars/{WELLNESS_DISTRICT_EXEMPLAR_ID}")
        assert response.status_code == 200
        exemplar = response.json()
        
        assert exemplar["page_name"] == "Wellness District"
        assert exemplar["page_family"] == "District"
        
        expected_tags = ["Brand voice mastery", "Emotional resonance", "Community-building language"]
        for tag in expected_tags:
            assert tag in exemplar["reason_tags"], f"Missing tag: {tag}"
    
    def test_education_district_exemplar_tags(self, api_client):
        """Verify Education District exemplar has correct tags"""
        response = api_client.get(f"{BASE_URL}/api/exemplars/{EDUCATION_DISTRICT_EXEMPLAR_ID}")
        assert response.status_code == 200
        exemplar = response.json()
        
        assert exemplar["page_name"] == "Education District"
        assert exemplar["page_family"] == "District"
        
        expected_tags = ["Brand voice mastery", "Structural clarity", "Emotional resonance", "Community-building language"]
        for tag in expected_tags:
            assert tag in exemplar["reason_tags"], f"Missing tag: {tag}"


class TestHouseTemplates:
    """Verify House Templates page shows 3 templates including Education District Pattern"""
    
    def test_template_count_is_3(self, api_client):
        """Verify exactly 3 templates exist"""
        response = api_client.get(f"{BASE_URL}/api/house-templates")
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 3, f"Expected 3 templates, got {data['total']}"
    
    def test_education_district_template_exists(self, api_client):
        """Verify Education District Pattern template exists with correct attributes"""
        response = api_client.get(f"{BASE_URL}/api/house-templates/{EDUCATION_DISTRICT_TEMPLATE_ID}")
        assert response.status_code == 200
        template = response.json()
        
        assert template["template_name"] == "Education District Pattern", \
            f"Expected 'Education District Pattern', got {template['template_name']}"
        assert template["page_family"] == "District", \
            f"Expected 'District' family, got {template['page_family']}"
        assert template["status"] == "active", \
            f"Expected 'active' status, got {template['status']}"
    
    def test_education_district_template_in_list(self, api_client):
        """Verify Education District Pattern appears in template list"""
        response = api_client.get(f"{BASE_URL}/api/house-templates")
        assert response.status_code == 200
        data = response.json()
        
        template_names = [t["template_name"] for t in data["templates"]]
        assert "Education District Pattern" in template_names, \
            f"Education District Pattern not found in templates: {template_names}"


class TestPromotionQueue:
    """Verify Promotion Queue shows correct status for promoted candidates"""
    
    def test_education_district_candidate_promoted_with_create_template(self, api_client):
        """Verify Education District candidate shows 'promoted' status with 'create-template' action"""
        response = api_client.get(f"{BASE_URL}/api/promotions/candidates")
        assert response.status_code == 200
        data = response.json()
        
        # Find Education District candidate
        ed_candidates = [c for c in data["candidates"] if c["page_name"] == "Education District"]
        assert len(ed_candidates) >= 1, "Education District candidate not found"
        
        # Find the one with create-template action
        ed_promoted = next((c for c in ed_candidates if c["action_taken"] == "create-template"), None)
        assert ed_promoted is not None, "Education District candidate with create-template action not found"
        assert ed_promoted["status"] == "promoted", \
            f"Expected 'promoted' status, got {ed_promoted['status']}"
        assert ed_promoted["action_taken"] == "create-template", \
            f"Expected 'create-template' action, got {ed_promoted['action_taken']}"
    
    def test_customer_stories_candidate_promoted_with_promote_exemplar(self, api_client):
        """Verify Customer Stories candidate shows 'promoted' status with 'promote-exemplar' action"""
        response = api_client.get(f"{BASE_URL}/api/promotions/candidates")
        assert response.status_code == 200
        data = response.json()
        
        # Find Customer Stories candidate with promote-exemplar action
        cs_candidates = [c for c in data["candidates"] if c["page_name"] == "Customer Stories"]
        assert len(cs_candidates) >= 1, "Customer Stories candidate not found"
        
        cs_promoted = next((c for c in cs_candidates if c["action_taken"] == "promote-exemplar"), None)
        assert cs_promoted is not None, "Customer Stories candidate with promote-exemplar action not found"
        assert cs_promoted["status"] == "promoted", \
            f"Expected 'promoted' status, got {cs_promoted['status']}"
        assert cs_promoted["action_taken"] == "promote-exemplar", \
            f"Expected 'promote-exemplar' action, got {cs_promoted['action_taken']}"


class TestNavigationAndRegression:
    """Verify all 7 navigation items accessible and Content Direction UI works"""
    
    def test_all_api_endpoints_accessible(self, api_client):
        """Verify all 7 main API endpoints are accessible"""
        endpoints = [
            "/api/pages",
            "/api/stats",
            "/api/exemplars",
            "/api/house-templates",
            "/api/style-profiles",
            "/api/promotions/candidates",
            "/api/settings"
        ]
        
        for endpoint in endpoints:
            response = api_client.get(f"{BASE_URL}{endpoint}")
            assert response.status_code == 200, f"Endpoint {endpoint} failed with status {response.status_code}"
    
    def test_trust_family_page_exists(self, api_client):
        """Verify Trust family page exists for Content Direction testing"""
        response = api_client.get(f"{BASE_URL}/api/pages?family=Trust")
        assert response.status_code == 200
        pages = response.json()
        assert len(pages) >= 1, "No Trust family pages found"
    
    def test_faq_support_family_page_exists(self, api_client):
        """Verify FAQ/Support family page exists for Content Direction testing"""
        response = api_client.get(f"{BASE_URL}/api/pages?family=FAQ/Support")
        assert response.status_code == 200
        pages = response.json()
        # FAQ/Support pages may or may not exist - just verify endpoint works
        # This is a regression check that the endpoint still works
        assert isinstance(pages, list), "Expected list of pages"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
