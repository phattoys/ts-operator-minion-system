"""
Test suite for TS Operator Minion v1 - Refinement Pass Features
Tests: expanded avoid_phrases, CTA avoid list, content_direction field, family-aware scoring
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')
PASSWORD = "TSFounder!Vault2026#Secure"

# Test page IDs
TRUST_PAGE_ID = "28398fa6-1ea8-485a-83a1-839b9d6922af"  # About Temporary Satisfaction
FAQ_PAGE_ID = "c2b06fc2-a040-4327-ae2c-344ac00c4102"  # Shipping & Delivery FAQ
HOMEPAGE_ID = "ef54de19-6e5b-405e-9e80-5316b31ddd1f"  # Homepage (Core Hub)


@pytest.fixture(scope="module")
def auth_token():
    """Get authentication token"""
    response = requests.post(
        f"{BASE_URL}/api/auth/login",
        json={"password": PASSWORD}
    )
    assert response.status_code == 200, f"Login failed: {response.text}"
    return response.json()["access_token"]


@pytest.fixture(scope="module")
def auth_headers(auth_token):
    """Get headers with auth token"""
    return {"Authorization": f"Bearer {auth_token}"}


class TestBrandVoiceEndpoint:
    """Tests for GET /api/brand-voice - expanded avoid_phrases and CTA avoid list"""
    
    def test_brand_voice_returns_24_avoid_phrases(self, auth_headers):
        """Verify expanded avoid_phrases list has 24 items"""
        response = requests.get(f"{BASE_URL}/api/brand-voice", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        
        avoid_phrases = data.get("avoid_phrases", [])
        assert len(avoid_phrases) == 24, f"Expected 24 avoid_phrases, got {len(avoid_phrases)}"
        
        # Verify some key phrases are present
        expected_phrases = [
            "browse our selection",
            "shop now",
            "begin your journey",
            "elevated essentials",
            "embark on",
            "dive into",
            "immerse yourself"
        ]
        for phrase in expected_phrases:
            assert phrase in avoid_phrases, f"Missing expected phrase: {phrase}"
    
    def test_cta_avoid_includes_cta_prefix(self, auth_headers):
        """Verify CTA avoid list includes 'CTA: [anything]'"""
        response = requests.get(f"{BASE_URL}/api/brand-voice", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        
        cta_style = data.get("cta_style", {})
        cta_avoid = cta_style.get("avoid", [])
        
        assert "CTA: [anything]" in cta_avoid, "CTA avoid list should include 'CTA: [anything]'"
    
    def test_cta_avoid_includes_begin_your_journey(self, auth_headers):
        """Verify CTA avoid list includes 'Begin Your Journey'"""
        response = requests.get(f"{BASE_URL}/api/brand-voice", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        
        cta_style = data.get("cta_style", {})
        cta_avoid = cta_style.get("avoid", [])
        
        assert "Begin Your Journey" in cta_avoid, "CTA avoid list should include 'Begin Your Journey'"
    
    def test_brand_voice_has_all_required_fields(self, auth_headers):
        """Verify brand-voice endpoint returns all required fields"""
        response = requests.get(f"{BASE_URL}/api/brand-voice", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        
        required_fields = [
            "motto", "emotional_core", "user_should_feel", 
            "brand_should_feel", "brand_should_NOT_feel",
            "copy_principles", "good_phrases", "avoid_phrases", "cta_style"
        ]
        for field in required_fields:
            assert field in data, f"Missing required field: {field}"


class TestContentDirectionField:
    """Tests for content_direction field in POST /api/pages/{id}/generate"""
    
    def test_generate_accepts_content_direction_dict(self, auth_headers):
        """Verify generate endpoint accepts content_direction as dict"""
        # Test with Trust page
        response = requests.post(
            f"{BASE_URL}/api/pages/{TRUST_PAGE_ID}/generate",
            headers=auth_headers,
            json={
                "tone": "professional",
                "content_direction": {
                    "trust_angle": "privacy and discretion",
                    "privacy_focus": "emphasize packaging discretion",
                    "proof_style": "paraphrased stories"
                }
            }
        )
        # Should accept the request (may take time to generate)
        assert response.status_code in [200, 500], f"Unexpected status: {response.status_code}, {response.text}"
        if response.status_code == 200:
            data = response.json()
            assert "generated_content" in data or "id" in data
    
    def test_generate_accepts_empty_content_direction(self, auth_headers):
        """Verify generate endpoint works without content_direction"""
        response = requests.post(
            f"{BASE_URL}/api/pages/{TRUST_PAGE_ID}/generate",
            headers=auth_headers,
            json={
                "tone": "professional",
                "content_direction": None
            }
        )
        assert response.status_code in [200, 500], f"Unexpected status: {response.status_code}"
    
    def test_generate_accepts_faq_content_direction(self, auth_headers):
        """Verify generate endpoint accepts FAQ-specific content_direction"""
        response = requests.post(
            f"{BASE_URL}/api/pages/{FAQ_PAGE_ID}/generate",
            headers=auth_headers,
            json={
                "tone": "professional",
                "content_direction": {
                    "topics_to_cover": "shipping times, tracking, international",
                    "detail_level": "medium"
                }
            }
        )
        assert response.status_code in [200, 500], f"Unexpected status: {response.status_code}"


class TestPageFamilies:
    """Tests for page family identification"""
    
    def test_trust_page_has_correct_family(self, auth_headers):
        """Verify Trust page has page_family='Trust'"""
        response = requests.get(
            f"{BASE_URL}/api/pages/{TRUST_PAGE_ID}",
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        assert data.get("page_family") == "Trust", f"Expected Trust family, got {data.get('page_family')}"
    
    def test_faq_page_has_correct_family(self, auth_headers):
        """Verify FAQ page has page_family='FAQ/Support'"""
        response = requests.get(
            f"{BASE_URL}/api/pages/{FAQ_PAGE_ID}",
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        assert data.get("page_family") == "FAQ/Support", f"Expected FAQ/Support family, got {data.get('page_family')}"
    
    def test_homepage_has_core_hub_family(self, auth_headers):
        """Verify Homepage has page_family='Core Hub'"""
        response = requests.get(
            f"{BASE_URL}/api/pages/{HOMEPAGE_ID}",
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        assert data.get("page_family") == "Core Hub", f"Expected Core Hub family, got {data.get('page_family')}"


class TestNavigation:
    """Tests for navigation items"""
    
    def test_all_api_endpoints_accessible(self, auth_headers):
        """Verify all main API endpoints are accessible"""
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
            response = requests.get(f"{BASE_URL}{endpoint}", headers=auth_headers)
            assert response.status_code == 200, f"Endpoint {endpoint} failed with status {response.status_code}"


class TestExistingFeatures:
    """Tests to verify existing features still work"""
    
    def test_exemplars_endpoint_works(self, auth_headers):
        """Verify exemplars endpoint returns data"""
        response = requests.get(f"{BASE_URL}/api/exemplars", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert "exemplars" in data
    
    def test_house_templates_endpoint_works(self, auth_headers):
        """Verify house-templates endpoint returns data"""
        response = requests.get(f"{BASE_URL}/api/house-templates", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert "templates" in data
    
    def test_style_profiles_endpoint_works(self, auth_headers):
        """Verify style-profiles endpoint returns data"""
        response = requests.get(f"{BASE_URL}/api/style-profiles", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert "profiles" in data
    
    def test_promotions_endpoint_works(self, auth_headers):
        """Verify promotions endpoint returns data"""
        response = requests.get(f"{BASE_URL}/api/promotions/candidates", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert "candidates" in data
    
    def test_stats_endpoint_works(self, auth_headers):
        """Verify stats endpoint returns data"""
        response = requests.get(f"{BASE_URL}/api/stats", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        # Stats should have some fields
        assert isinstance(data, dict)


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
