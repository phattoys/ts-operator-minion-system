"""
WordPress Page Placement Minion - Backend API Tests
Tests for: templates, placement (create/update), log, drafts, stats, settings
MOCKED WordPress layer - stores in MongoDB wp_mock_pages collection
"""
import pytest
import requests
import os
import time

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


# ================== TEMPLATES TESTS ==================

class TestTemplates:
    """Template endpoint tests"""

    def test_get_templates_list(self, auth_headers):
        """GET /api/wp-placement/templates returns 3 templates with wp_connected=false"""
        response = requests.get(f"{BASE_URL}/api/wp-placement/templates", headers=auth_headers)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert "templates" in data
        assert "wp_connected" in data
        assert data["wp_connected"] == False, "Expected wp_connected=false (mock mode)"
        assert len(data["templates"]) == 3, f"Expected 3 templates, got {len(data['templates'])}"
        
        template_ids = [t["id"] for t in data["templates"]]
        assert "standard_content" in template_ids
        assert "category_support" in template_ids
        assert "local_seo_landing" in template_ids
        print(f"✓ Templates list: {template_ids}")

    def test_get_template_standard_content(self, auth_headers):
        """GET /api/wp-placement/templates/standard_content returns template detail with sections"""
        response = requests.get(f"{BASE_URL}/api/wp-placement/templates/standard_content", headers=auth_headers)
        assert response.status_code == 200
        
        data = response.json()
        assert data["id"] == "standard_content"
        assert "name" in data
        assert "description" in data
        assert "sections" in data
        assert len(data["sections"]) > 0
        
        section_keys = [s["key"] for s in data["sections"]]
        assert "hero" in section_keys
        assert "intro" in section_keys
        assert "body" in section_keys
        print(f"✓ Standard Content template has sections: {section_keys}")

    def test_get_template_category_support(self, auth_headers):
        """GET /api/wp-placement/templates/category_support returns template detail"""
        response = requests.get(f"{BASE_URL}/api/wp-placement/templates/category_support", headers=auth_headers)
        assert response.status_code == 200
        
        data = response.json()
        assert data["id"] == "category_support"
        assert "sections" in data
        print(f"✓ Category Support template: {data['name']}")

    def test_get_template_local_seo_landing(self, auth_headers):
        """GET /api/wp-placement/templates/local_seo_landing returns template detail"""
        response = requests.get(f"{BASE_URL}/api/wp-placement/templates/local_seo_landing", headers=auth_headers)
        assert response.status_code == 200
        
        data = response.json()
        assert data["id"] == "local_seo_landing"
        assert "sections" in data
        print(f"✓ Local SEO Landing template: {data['name']}")

    def test_get_template_not_found(self, auth_headers):
        """GET /api/wp-placement/templates/invalid returns 404"""
        response = requests.get(f"{BASE_URL}/api/wp-placement/templates/invalid_template", headers=auth_headers)
        assert response.status_code == 404
        print("✓ Invalid template returns 404")


# ================== PLACEMENT TESTS ==================

class TestPlacement:
    """Placement endpoint tests - create and update modes"""

    def test_placement_create_full_content(self, auth_headers):
        """POST /api/wp-placement/place - create mode with full content"""
        payload = {
            "mode": "create",
            "template_id": "standard_content",
            "page_title": "TEST Full Content Page",
            "slug": "test-full-content",
            "hero_headline": "Welcome to Our Store",
            "subheadline": "Quality products for everyone",
            "intro": "This is the introduction paragraph with important information.",
            "body_section_1": "First body section with detailed content.",
            "body_section_2": "Second body section with more details.",
            "body_section_3": "Third body section wrapping up.",
            "cta_text": "Shop Now",
            "cta_url": "/shop",
            "related_links": [
                {"title": "About Us", "url": "/about"},
                {"title": "Contact", "url": "/contact"}
            ],
            "seo_title": "Test Page SEO Title",
            "meta_description": "Test page meta description for SEO"
        }
        
        response = requests.post(f"{BASE_URL}/api/wp-placement/place", json=payload, headers=auth_headers)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert "placement" in data
        assert "page" in data
        assert "html_preview" in data
        
        placement = data["placement"]
        assert placement["mode"] == "create"
        assert placement["page_title"] == "TEST Full Content Page"
        assert placement["template_id"] == "standard_content"
        assert "page_id" in placement
        assert placement["page_id"].startswith("wp-")
        assert "sections_placed" in placement
        assert "sections_skipped" in placement
        assert "warnings" in placement
        
        # Verify page was created
        page = data["page"]
        assert page["title"] == "TEST Full Content Page"
        assert page["slug"] == "test-full-content"
        assert page["mock"] == True
        
        # Verify HTML preview contains shortcodes
        assert "[section" in data["html_preview"]
        print(f"✓ Full content placement created: {placement['page_id']}")
        
        return placement["page_id"]

    def test_placement_create_minimal_content(self, auth_headers):
        """POST /api/wp-placement/place - create with minimal content (just title)"""
        payload = {
            "mode": "create",
            "template_id": "standard_content",
            "page_title": "TEST Minimal Page"
        }
        
        response = requests.post(f"{BASE_URL}/api/wp-placement/place", json=payload, headers=auth_headers)
        assert response.status_code == 200
        
        data = response.json()
        placement = data["placement"]
        
        # Should have warnings for missing required sections
        assert len(placement["warnings"]) > 0, "Expected warnings for missing sections"
        assert len(placement["sections_skipped"]) > 0, "Expected skipped sections"
        
        # Check for CTA warning
        has_cta_warning = any("CTA" in w for w in placement["warnings"])
        assert has_cta_warning, "Expected warning about missing CTA"
        
        print(f"✓ Minimal content placement with warnings: {placement['warnings']}")

    def test_placement_create_with_category_support_template(self, auth_headers):
        """POST /api/wp-placement/place - create with category_support template"""
        payload = {
            "mode": "create",
            "template_id": "category_support",
            "page_title": "TEST Category Page",
            "hero_headline": "Shop Our Collection",
            "intro": "Browse our curated selection."
        }
        
        response = requests.post(f"{BASE_URL}/api/wp-placement/place", json=payload, headers=auth_headers)
        assert response.status_code == 200
        
        data = response.json()
        assert data["placement"]["template_id"] == "category_support"
        print(f"✓ Category support template placement: {data['placement']['page_id']}")

    def test_placement_create_with_local_seo_template(self, auth_headers):
        """POST /api/wp-placement/place - create with local_seo_landing template"""
        payload = {
            "mode": "create",
            "template_id": "local_seo_landing",
            "page_title": "TEST Long Beach Store",
            "hero_headline": "Visit Our Long Beach Location",
            "intro": "Your local destination for quality products."
        }
        
        response = requests.post(f"{BASE_URL}/api/wp-placement/place", json=payload, headers=auth_headers)
        assert response.status_code == 200
        
        data = response.json()
        assert data["placement"]["template_id"] == "local_seo_landing"
        print(f"✓ Local SEO template placement: {data['placement']['page_id']}")

    def test_placement_update_requires_target_page_id(self, auth_headers):
        """POST /api/wp-placement/place - update mode requires target_page_id"""
        payload = {
            "mode": "update",
            "template_id": "standard_content",
            "page_title": "TEST Update Without Target"
        }
        
        response = requests.post(f"{BASE_URL}/api/wp-placement/place", json=payload, headers=auth_headers)
        assert response.status_code == 400
        assert "target_page_id" in response.json().get("detail", "").lower()
        print("✓ Update mode without target_page_id returns 400")

    def test_placement_update_with_valid_target(self, auth_headers):
        """POST /api/wp-placement/place - update mode with valid target_page_id"""
        # First create a page
        create_payload = {
            "mode": "create",
            "template_id": "standard_content",
            "page_title": "TEST Page For Update",
            "hero_headline": "Original Headline"
        }
        create_response = requests.post(f"{BASE_URL}/api/wp-placement/place", json=create_payload, headers=auth_headers)
        assert create_response.status_code == 200
        page_id = create_response.json()["placement"]["page_id"]
        
        # Now update it
        update_payload = {
            "mode": "update",
            "template_id": "standard_content",
            "target_page_id": page_id,
            "page_title": "TEST Page Updated",
            "hero_headline": "Updated Headline",
            "intro": "New intro content added"
        }
        
        response = requests.post(f"{BASE_URL}/api/wp-placement/place", json=update_payload, headers=auth_headers)
        assert response.status_code == 200
        
        data = response.json()
        assert data["placement"]["mode"] == "update"
        assert data["placement"]["page_id"] == page_id
        assert data["page"]["title"] == "TEST Page Updated"
        print(f"✓ Update mode successful for page: {page_id}")

    def test_placement_update_invalid_target(self, auth_headers):
        """POST /api/wp-placement/place - update with invalid target_page_id returns 404"""
        payload = {
            "mode": "update",
            "template_id": "standard_content",
            "target_page_id": "wp-nonexistent",
            "page_title": "TEST Update Invalid"
        }
        
        response = requests.post(f"{BASE_URL}/api/wp-placement/place", json=payload, headers=auth_headers)
        assert response.status_code == 404
        print("✓ Update with invalid target returns 404")

    def test_placement_missing_cta_url_warning(self, auth_headers):
        """POST /api/wp-placement/place - missing CTA URL generates warning"""
        payload = {
            "mode": "create",
            "template_id": "standard_content",
            "page_title": "TEST CTA Warning Page",
            "hero_headline": "Test",
            "cta_text": "Click Here"
            # cta_url intentionally missing
        }
        
        response = requests.post(f"{BASE_URL}/api/wp-placement/place", json=payload, headers=auth_headers)
        assert response.status_code == 200
        
        warnings = response.json()["placement"]["warnings"]
        has_cta_url_warning = any("URL" in w and "missing" in w.lower() for w in warnings)
        assert has_cta_url_warning, f"Expected CTA URL warning, got: {warnings}"
        print(f"✓ Missing CTA URL warning: {warnings}")

    def test_placement_no_cta_warning(self, auth_headers):
        """POST /api/wp-placement/place - no CTA generates 'No CTA provided' warning"""
        payload = {
            "mode": "create",
            "template_id": "standard_content",
            "page_title": "TEST No CTA Page",
            "hero_headline": "Test"
            # No cta_text or cta_url
        }
        
        response = requests.post(f"{BASE_URL}/api/wp-placement/place", json=payload, headers=auth_headers)
        assert response.status_code == 200
        
        warnings = response.json()["placement"]["warnings"]
        has_no_cta_warning = any("No CTA" in w for w in warnings)
        assert has_no_cta_warning, f"Expected 'No CTA provided' warning, got: {warnings}"
        print(f"✓ No CTA warning: {warnings}")

    def test_placement_requires_title(self, auth_headers):
        """POST /api/wp-placement/place - page_title is required"""
        payload = {
            "mode": "create",
            "template_id": "standard_content",
            "page_title": ""  # Empty title
        }
        
        response = requests.post(f"{BASE_URL}/api/wp-placement/place", json=payload, headers=auth_headers)
        assert response.status_code == 400
        print("✓ Empty title returns 400")


# ================== LOG TESTS ==================

class TestPlacementLog:
    """Placement log endpoint tests"""

    def test_get_placement_log(self, auth_headers):
        """GET /api/wp-placement/log returns placement history"""
        response = requests.get(f"{BASE_URL}/api/wp-placement/log", headers=auth_headers)
        assert response.status_code == 200
        
        data = response.json()
        assert "placements" in data
        assert "count" in data
        assert isinstance(data["placements"], list)
        
        if len(data["placements"]) > 0:
            log = data["placements"][0]
            assert "id" in log
            assert "mode" in log
            assert "page_title" in log
            assert "template_id" in log
            assert "created_at" in log
        
        print(f"✓ Placement log: {data['count']} entries")

    def test_get_placement_detail(self, auth_headers):
        """GET /api/wp-placement/log/{placement_id} returns single placement detail"""
        # First get the log to find a placement ID
        log_response = requests.get(f"{BASE_URL}/api/wp-placement/log", headers=auth_headers)
        placements = log_response.json().get("placements", [])
        
        if len(placements) == 0:
            pytest.skip("No placements in log to test detail endpoint")
        
        placement_id = placements[0]["id"]
        response = requests.get(f"{BASE_URL}/api/wp-placement/log/{placement_id}", headers=auth_headers)
        assert response.status_code == 200
        
        data = response.json()
        assert data["id"] == placement_id
        assert "page_title" in data
        assert "template_id" in data
        print(f"✓ Placement detail for: {placement_id}")

    def test_get_placement_detail_not_found(self, auth_headers):
        """GET /api/wp-placement/log/{invalid_id} returns 404"""
        response = requests.get(f"{BASE_URL}/api/wp-placement/log/nonexistent-id", headers=auth_headers)
        assert response.status_code == 404
        print("✓ Invalid placement ID returns 404")


# ================== DRAFTS TESTS ==================

class TestDrafts:
    """Drafts (WP mock pages) endpoint tests"""

    def test_get_drafts_list(self, auth_headers):
        """GET /api/wp-placement/drafts returns list of mock WP pages"""
        response = requests.get(f"{BASE_URL}/api/wp-placement/drafts", headers=auth_headers)
        assert response.status_code == 200
        
        data = response.json()
        assert "pages" in data
        assert "count" in data
        assert "wp_connected" in data
        assert data["wp_connected"] == False
        
        if len(data["pages"]) > 0:
            page = data["pages"][0]
            assert "id" in page
            assert "title" in page
            assert "slug" in page
            assert "status" in page
        
        print(f"✓ Drafts list: {data['count']} pages")

    def test_get_draft_detail(self, auth_headers):
        """GET /api/wp-placement/drafts/{page_id} returns single draft detail"""
        # First get drafts list
        drafts_response = requests.get(f"{BASE_URL}/api/wp-placement/drafts", headers=auth_headers)
        pages = drafts_response.json().get("pages", [])
        
        if len(pages) == 0:
            pytest.skip("No drafts to test detail endpoint")
        
        page_id = pages[0]["id"]
        response = requests.get(f"{BASE_URL}/api/wp-placement/drafts/{page_id}", headers=auth_headers)
        assert response.status_code == 200
        
        data = response.json()
        assert data["id"] == page_id
        assert "title" in data
        assert "content" in data
        print(f"✓ Draft detail for: {page_id}")

    def test_get_draft_not_found(self, auth_headers):
        """GET /api/wp-placement/drafts/{invalid_id} returns 404"""
        response = requests.get(f"{BASE_URL}/api/wp-placement/drafts/wp-nonexistent", headers=auth_headers)
        assert response.status_code == 404
        print("✓ Invalid draft ID returns 404")


# ================== STATS TESTS ==================

class TestStats:
    """Stats endpoint tests"""

    def test_get_stats(self, auth_headers):
        """GET /api/wp-placement/stats returns placement statistics"""
        response = requests.get(f"{BASE_URL}/api/wp-placement/stats", headers=auth_headers)
        assert response.status_code == 200
        
        data = response.json()
        assert "total_placements" in data
        assert "creates" in data
        assert "updates" in data
        assert "by_template" in data
        assert "wp_connected" in data
        
        assert isinstance(data["total_placements"], int)
        assert isinstance(data["creates"], int)
        assert isinstance(data["updates"], int)
        assert isinstance(data["by_template"], dict)
        
        print(f"✓ Stats: {data['total_placements']} total, {data['creates']} creates, {data['updates']} updates")


# ================== SETTINGS TESTS ==================

class TestSettings:
    """Settings endpoint tests"""

    def test_get_settings(self, auth_headers):
        """GET /api/wp-placement/settings returns default settings"""
        response = requests.get(f"{BASE_URL}/api/wp-placement/settings", headers=auth_headers)
        assert response.status_code == 200
        
        data = response.json()
        assert "default_status" in data
        assert "preserve_slug_on_update" in data
        assert "preserve_unmapped_on_update" in data
        assert "flag_missing_cta" in data
        assert "save_placement_log" in data
        assert "wp_connected" in data
        
        print(f"✓ Settings: default_status={data['default_status']}, flag_missing_cta={data['flag_missing_cta']}")

    def test_update_settings(self, auth_headers):
        """PUT /api/wp-placement/settings updates settings"""
        # Get current settings
        current = requests.get(f"{BASE_URL}/api/wp-placement/settings", headers=auth_headers).json()
        original_flag = current.get("flag_missing_cta", True)
        
        # Toggle the flag
        new_value = not original_flag
        response = requests.put(
            f"{BASE_URL}/api/wp-placement/settings",
            json={"flag_missing_cta": new_value},
            headers=auth_headers
        )
        assert response.status_code == 200
        
        data = response.json()
        assert data["flag_missing_cta"] == new_value
        
        # Restore original value
        requests.put(
            f"{BASE_URL}/api/wp-placement/settings",
            json={"flag_missing_cta": original_flag},
            headers=auth_headers
        )
        
        print(f"✓ Settings updated: flag_missing_cta toggled to {new_value} and restored")


# ================== AUTH TESTS ==================

class TestAuth:
    """Authentication requirement tests"""

    def test_templates_requires_auth(self):
        """GET /api/wp-placement/templates requires authentication"""
        response = requests.get(f"{BASE_URL}/api/wp-placement/templates")
        assert response.status_code == 401
        print("✓ Templates endpoint requires auth")

    def test_place_requires_auth(self):
        """POST /api/wp-placement/place requires authentication"""
        response = requests.post(f"{BASE_URL}/api/wp-placement/place", json={"page_title": "Test"})
        assert response.status_code == 401
        print("✓ Place endpoint requires auth")

    def test_stats_requires_auth(self):
        """GET /api/wp-placement/stats requires authentication"""
        response = requests.get(f"{BASE_URL}/api/wp-placement/stats")
        assert response.status_code == 401
        print("✓ Stats endpoint requires auth")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
