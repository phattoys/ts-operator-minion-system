"""
WordPress Page Placement Minion - LIVE WordPress Connection Tests
Tests for: LIVE WP connection status, template inference, drafts (mock=false), stats, log
NOTE: Does NOT create new WP pages - only verifies existing live pages via GET endpoints
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')
PASSWORD = "TSFounder!Vault2026#Secure"


@pytest.fixture(scope="module")
def auth_token():
    """Get authentication token"""
    response = requests.post(f"{BASE_URL}/api/auth/login", json={"password": PASSWORD})
    if response.status_code == 200:
        return response.json().get("access_token")
    pytest.fail(f"Authentication failed: {response.status_code} - {response.text}")


@pytest.fixture(scope="module")
def auth_headers(auth_token):
    """Headers with auth token"""
    return {"Authorization": f"Bearer {auth_token}", "Content-Type": "application/json"}


# ================== LIVE WP CONNECTION TESTS ==================

class TestLiveWPConnection:
    """Verify WordPress is in LIVE mode (not mock)"""

    def test_templates_shows_wp_connected_true(self, auth_headers):
        """GET /api/wp-placement/templates returns wp_connected=true"""
        response = requests.get(f"{BASE_URL}/api/wp-placement/templates", headers=auth_headers)
        assert response.status_code == 200
        
        data = response.json()
        assert data["wp_connected"] == True, f"Expected wp_connected=true (LIVE mode), got {data['wp_connected']}"
        assert len(data["templates"]) == 3
        print(f"✓ WP CONNECTED: {data['wp_connected']} - LIVE mode confirmed")

    def test_stats_shows_wp_connected_true(self, auth_headers):
        """GET /api/wp-placement/stats returns wp_connected=true"""
        response = requests.get(f"{BASE_URL}/api/wp-placement/stats", headers=auth_headers)
        assert response.status_code == 200
        
        data = response.json()
        assert data["wp_connected"] == True
        assert "total_placements" in data
        assert "creates" in data
        assert "updates" in data
        assert "by_template" in data
        print(f"✓ Stats: {data['total_placements']} placements, wp_connected={data['wp_connected']}")

    def test_drafts_shows_wp_connected_true(self, auth_headers):
        """GET /api/wp-placement/drafts returns wp_connected=true"""
        response = requests.get(f"{BASE_URL}/api/wp-placement/drafts", headers=auth_headers)
        assert response.status_code == 200
        
        data = response.json()
        assert data["wp_connected"] == True
        print(f"✓ Drafts: {data['count']} pages, wp_connected={data['wp_connected']}")

    def test_drafts_have_mock_false(self, auth_headers):
        """GET /api/wp-placement/drafts returns pages with mock=false (real WP pages)"""
        response = requests.get(f"{BASE_URL}/api/wp-placement/drafts", headers=auth_headers)
        assert response.status_code == 200
        
        data = response.json()
        pages = data.get("pages", [])
        
        if len(pages) == 0:
            pytest.skip("No drafts to verify mock=false")
        
        # Check that at least some pages have mock=false (live WP pages)
        live_pages = [p for p in pages if p.get("mock") == False]
        assert len(live_pages) > 0, "Expected at least one live WP page with mock=false"
        
        # Verify live pages have numeric WP IDs
        for page in live_pages[:3]:
            assert page["id"].isdigit(), f"Expected numeric WP ID, got {page['id']}"
            assert "title" in page
            assert "slug" in page
            assert page["status"] == "draft"
            print(f"  ✓ Live WP page: ID={page['id']}, title={page['title'][:50]}...")
        
        print(f"✓ Found {len(live_pages)} live WP pages with mock=false")


# ================== TEMPLATE INFERENCE TESTS ==================

class TestTemplateInference:
    """Test auto-inference of templates based on page_type, title, content"""

    def test_infer_template_a_education_guide(self, auth_headers):
        """POST /api/wp-placement/infer-template correctly infers Template A for education/guide content"""
        response = requests.post(
            f"{BASE_URL}/api/wp-placement/infer-template",
            params={"page_type": "education", "title": "Beginner Guide to Wellness", "content": "learn how to get started with tips"},
            headers=auth_headers
        )
        assert response.status_code == 200
        
        data = response.json()
        assert data["template_id"] == "standard_content", f"Expected standard_content, got {data['template_id']}"
        assert data["template_name"] == "Template A — Standard Content Page"
        assert data["confidence"] in ["high", "medium"]
        assert len(data["matched_keywords"]) > 0
        print(f"✓ Template A inferred: {data['template_name']} ({data['confidence']} confidence)")
        print(f"  Matched keywords: {data['matched_keywords']}")

    def test_infer_template_b_shop_product(self, auth_headers):
        """POST /api/wp-placement/infer-template correctly infers Template B for shop/product content"""
        response = requests.post(
            f"{BASE_URL}/api/wp-placement/infer-template",
            params={"page_type": "category", "title": "Best Selling Vibrators", "content": "shop our collection of clit stimulators"},
            headers=auth_headers
        )
        assert response.status_code == 200
        
        data = response.json()
        assert data["template_id"] == "category_support", f"Expected category_support, got {data['template_id']}"
        assert data["template_name"] == "Template B — Shop Support Page"
        assert data["confidence"] in ["high", "medium"]
        print(f"✓ Template B inferred: {data['template_name']} ({data['confidence']} confidence)")
        print(f"  Matched keywords: {data['matched_keywords']}")

    def test_infer_template_c_local_location(self, auth_headers):
        """POST /api/wp-placement/infer-template correctly infers Template C for local/location content"""
        response = requests.post(
            f"{BASE_URL}/api/wp-placement/infer-template",
            params={"page_type": "local", "title": "Long Beach Sex Shop", "content": "visit our adult boutique near me"},
            headers=auth_headers
        )
        assert response.status_code == 200
        
        data = response.json()
        assert data["template_id"] == "local_seo_landing", f"Expected local_seo_landing, got {data['template_id']}"
        assert data["template_name"] == "Template C — Local / SEO Landing Page"
        assert data["confidence"] in ["high", "medium"]
        print(f"✓ Template C inferred: {data['template_name']} ({data['confidence']} confidence)")
        print(f"  Matched keywords: {data['matched_keywords']}")

    def test_infer_template_no_match_defaults_to_standard(self, auth_headers):
        """POST /api/wp-placement/infer-template defaults to standard_content when no keywords match"""
        response = requests.post(
            f"{BASE_URL}/api/wp-placement/infer-template",
            params={"page_type": "", "title": "Random Page", "content": "some random content"},
            headers=auth_headers
        )
        assert response.status_code == 200
        
        data = response.json()
        assert data["template_id"] == "standard_content"
        assert data["confidence"] == "low"
        assert data["needs_review"] == True
        print(f"✓ No match defaults to standard_content with needs_review=True")


# ================== PLACEMENT LOG TESTS ==================

class TestPlacementLog:
    """Test placement log endpoint"""

    def test_get_placement_log(self, auth_headers):
        """GET /api/wp-placement/log returns placement history"""
        response = requests.get(f"{BASE_URL}/api/wp-placement/log", headers=auth_headers)
        assert response.status_code == 200
        
        data = response.json()
        assert "placements" in data
        assert "count" in data
        assert isinstance(data["placements"], list)
        print(f"✓ Placement log: {data['count']} entries")

    def test_placement_log_has_live_entries(self, auth_headers):
        """GET /api/wp-placement/log contains entries with wp_connected=true"""
        response = requests.get(f"{BASE_URL}/api/wp-placement/log", headers=auth_headers)
        assert response.status_code == 200
        
        placements = response.json().get("placements", [])
        if len(placements) == 0:
            pytest.skip("No placements in log")
        
        # Check for live placements
        live_placements = [p for p in placements if p.get("wp_connected") == True]
        assert len(live_placements) > 0, "Expected at least one placement with wp_connected=true"
        
        for p in live_placements[:3]:
            assert "page_id" in p
            assert "page_title" in p
            assert "template_id" in p
            assert "mode" in p
            print(f"  ✓ Live placement: {p['page_title'][:40]}... (mode={p['mode']})")
        
        print(f"✓ Found {len(live_placements)} live placements with wp_connected=true")


# ================== TEMPLATES DETAIL TESTS ==================

class TestTemplatesDetail:
    """Test template detail endpoints"""

    def test_get_all_templates(self, auth_headers):
        """GET /api/wp-placement/templates returns all 3 templates"""
        response = requests.get(f"{BASE_URL}/api/wp-placement/templates", headers=auth_headers)
        assert response.status_code == 200
        
        data = response.json()
        templates = data["templates"]
        assert len(templates) == 3
        
        template_ids = [t["id"] for t in templates]
        assert "standard_content" in template_ids
        assert "category_support" in template_ids
        assert "local_seo_landing" in template_ids
        
        for t in templates:
            assert "name" in t
            assert "description" in t
            assert "use_for" in t
            assert "required_sections" in t
            print(f"  ✓ {t['name']}")
        
        print(f"✓ All 3 templates returned with wp_connected={data['wp_connected']}")

    def test_get_template_standard_content_detail(self, auth_headers):
        """GET /api/wp-placement/templates/standard_content returns template with sections"""
        response = requests.get(f"{BASE_URL}/api/wp-placement/templates/standard_content", headers=auth_headers)
        assert response.status_code == 200
        
        data = response.json()
        assert data["id"] == "standard_content"
        assert "sections" in data
        assert len(data["sections"]) > 0
        
        section_keys = [s["key"] for s in data["sections"]]
        assert "hero" in section_keys
        assert "intro" in section_keys
        assert "body" in section_keys
        assert "cta" in section_keys
        print(f"✓ Template A sections: {section_keys}")


# ================== SETTINGS TESTS ==================

class TestSettings:
    """Test settings endpoint"""

    def test_get_settings_shows_wp_connected(self, auth_headers):
        """GET /api/wp-placement/settings returns wp_connected=true"""
        response = requests.get(f"{BASE_URL}/api/wp-placement/settings", headers=auth_headers)
        assert response.status_code == 200
        
        data = response.json()
        assert data["wp_connected"] == True
        assert "default_status" in data
        assert "preserve_slug_on_update" in data
        assert "flag_missing_cta" in data
        assert "save_placement_log" in data
        print(f"✓ Settings: wp_connected={data['wp_connected']}, default_status={data['default_status']}")


# ================== AUTH TESTS ==================

class TestAuth:
    """Authentication requirement tests"""

    def test_templates_requires_auth(self):
        """GET /api/wp-placement/templates requires authentication"""
        response = requests.get(f"{BASE_URL}/api/wp-placement/templates")
        assert response.status_code == 401
        print("✓ Templates endpoint requires auth")

    def test_drafts_requires_auth(self):
        """GET /api/wp-placement/drafts requires authentication"""
        response = requests.get(f"{BASE_URL}/api/wp-placement/drafts")
        assert response.status_code == 401
        print("✓ Drafts endpoint requires auth")

    def test_stats_requires_auth(self):
        """GET /api/wp-placement/stats requires authentication"""
        response = requests.get(f"{BASE_URL}/api/wp-placement/stats")
        assert response.status_code == 401
        print("✓ Stats endpoint requires auth")

    def test_log_requires_auth(self):
        """GET /api/wp-placement/log requires authentication"""
        response = requests.get(f"{BASE_URL}/api/wp-placement/log")
        assert response.status_code == 401
        print("✓ Log endpoint requires auth")

    def test_infer_template_requires_auth(self):
        """POST /api/wp-placement/infer-template requires authentication"""
        response = requests.post(f"{BASE_URL}/api/wp-placement/infer-template")
        assert response.status_code == 401
        print("✓ Infer-template endpoint requires auth")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
