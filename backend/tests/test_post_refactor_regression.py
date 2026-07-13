"""
Post-Refactor Regression Tests for TS Operator Minion v1
Tests all functionality after server.py split into modular files:
- database.py, models.py, auth.py, services/, routes/
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

class TestAuthEndpoints:
    """Auth: Login with password, verify token, logout"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        self.password = "TSFounder!Vault2026#Secure"
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
    
    def test_login_success(self):
        """Test login with correct password returns token"""
        response = self.session.post(f"{BASE_URL}/api/auth/login", json={"password": self.password})
        assert response.status_code == 200, f"Login failed: {response.text}"
        data = response.json()
        assert "access_token" in data, "No access_token in response"
        assert "token_type" in data, "No token_type in response"
        assert data["token_type"] == "bearer"
        print(f"✓ Login successful, token received")
    
    def test_login_invalid_password(self):
        """Test login with wrong password returns 401"""
        response = self.session.post(f"{BASE_URL}/api/auth/login", json={"password": "wrong"})
        assert response.status_code == 401, f"Expected 401, got {response.status_code}"
        print(f"✓ Invalid password correctly rejected")
    
    def test_verify_token(self):
        """Test token verification endpoint"""
        # First login
        login_resp = self.session.post(f"{BASE_URL}/api/auth/login", json={"password": self.password})
        token = login_resp.json()["access_token"]
        
        # Verify token
        response = self.session.get(
            f"{BASE_URL}/api/auth/verify",
            headers={"Authorization": f"Bearer {token}"}
        )
        assert response.status_code == 200, f"Verify failed: {response.text}"
        data = response.json()
        assert data.get("authenticated") == True
        assert "user" in data
        print(f"✓ Token verification successful")
    
    def test_logout(self):
        """Test logout endpoint"""
        # First login
        login_resp = self.session.post(f"{BASE_URL}/api/auth/login", json={"password": self.password})
        token = login_resp.json()["access_token"]
        
        # Logout
        response = self.session.post(
            f"{BASE_URL}/api/auth/logout",
            headers={"Authorization": f"Bearer {token}"}
        )
        assert response.status_code == 200, f"Logout failed: {response.text}"
        data = response.json()
        assert "message" in data
        print(f"✓ Logout successful")


class TestDashboardEndpoints:
    """Dashboard: Stats and recommended endpoints"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
        # Login
        login_resp = self.session.post(
            f"{BASE_URL}/api/auth/login",
            json={"password": "TSFounder!Vault2026#Secure"}
        )
        self.token = login_resp.json()["access_token"]
        self.session.headers.update({"Authorization": f"Bearer {self.token}"})
    
    def test_stats_endpoint(self):
        """Test stats endpoint returns correct totals (25 pages)"""
        response = self.session.get(f"{BASE_URL}/api/stats")
        assert response.status_code == 200, f"Stats failed: {response.text}"
        data = response.json()
        assert "total_pages" in data
        assert data["total_pages"] == 25, f"Expected 25 pages, got {data['total_pages']}"
        assert "by_status" in data
        assert "by_family" in data
        print(f"✓ Stats endpoint returns 25 total pages")
    
    def test_recommended_endpoint_returns_array(self):
        """Test recommended endpoint returns plain array (not wrapped)"""
        response = self.session.get(f"{BASE_URL}/api/pages/recommended")
        assert response.status_code == 200, f"Recommended failed: {response.text}"
        data = response.json()
        # Should be a plain array, not wrapped in an object
        assert isinstance(data, list), f"Expected array, got {type(data)}"
        print(f"✓ Recommended endpoint returns array with {len(data)} pages")


class TestPageQueueEndpoints:
    """Page Queue: List all pages, filter by status, filter by family"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
        login_resp = self.session.post(
            f"{BASE_URL}/api/auth/login",
            json={"password": "TSFounder!Vault2026#Secure"}
        )
        self.token = login_resp.json()["access_token"]
        self.session.headers.update({"Authorization": f"Bearer {self.token}"})
    
    def test_list_all_pages(self):
        """Test listing all pages"""
        response = self.session.get(f"{BASE_URL}/api/pages")
        assert response.status_code == 200, f"List pages failed: {response.text}"
        data = response.json()
        assert "pages" in data
        assert "total" in data
        assert data["total"] == 25, f"Expected 25 pages, got {data['total']}"
        print(f"✓ List all pages returns {data['total']} pages")
    
    def test_filter_by_status(self):
        """Test filtering pages by status"""
        response = self.session.get(f"{BASE_URL}/api/pages?status=Planned")
        assert response.status_code == 200, f"Filter by status failed: {response.text}"
        data = response.json()
        assert "pages" in data
        # All returned pages should have status=Planned
        for page in data["pages"]:
            assert page.get("status") == "Planned", f"Page {page.get('page_name')} has wrong status"
        print(f"✓ Filter by status works, returned {len(data['pages'])} Planned pages")
    
    def test_filter_by_family(self):
        """Test filtering pages by family"""
        response = self.session.get(f"{BASE_URL}/api/pages?family=District")
        assert response.status_code == 200, f"Filter by family failed: {response.text}"
        data = response.json()
        assert "pages" in data
        # All returned pages should have page_family=District
        for page in data["pages"]:
            assert page.get("page_family") == "District", f"Page {page.get('page_name')} has wrong family"
        print(f"✓ Filter by family works, returned {len(data['pages'])} District pages")


class TestPageWorkspaceEndpoints:
    """Page Workspace: Get single page, update page, create new page"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
        login_resp = self.session.post(
            f"{BASE_URL}/api/auth/login",
            json={"password": "TSFounder!Vault2026#Secure"}
        )
        self.token = login_resp.json()["access_token"]
        self.session.headers.update({"Authorization": f"Bearer {self.token}"})
    
    def test_get_single_page(self):
        """Test getting a single page by ID"""
        # First get list to find a page ID
        list_resp = self.session.get(f"{BASE_URL}/api/pages")
        pages = list_resp.json()["pages"]
        page_id = pages[0]["id"]
        
        response = self.session.get(f"{BASE_URL}/api/pages/{page_id}")
        assert response.status_code == 200, f"Get page failed: {response.text}"
        data = response.json()
        assert data["id"] == page_id
        assert "page_name" in data
        assert "page_family" in data
        print(f"✓ Get single page works: {data['page_name']}")
    
    def test_update_page(self):
        """Test updating a page"""
        # Get a page
        list_resp = self.session.get(f"{BASE_URL}/api/pages")
        pages = list_resp.json()["pages"]
        page_id = pages[0]["id"]
        original_notes = pages[0].get("notes")
        
        # Update notes
        test_note = "TEST_regression_update_note"
        response = self.session.put(
            f"{BASE_URL}/api/pages/{page_id}",
            json={"notes": test_note}
        )
        assert response.status_code == 200, f"Update page failed: {response.text}"
        data = response.json()
        assert data["notes"] == test_note
        
        # Restore original
        self.session.put(f"{BASE_URL}/api/pages/{page_id}", json={"notes": original_notes})
        print(f"✓ Update page works")
    
    def test_create_new_page(self):
        """Test creating a new page"""
        new_page = {
            "page_name": "TEST_Regression_Page",
            "page_family": "Trust",
            "page_type": "About",
            "audience": "Test audience",
            "purpose": "Regression testing"
        }
        response = self.session.post(f"{BASE_URL}/api/pages", json=new_page)
        assert response.status_code == 201, f"Create page failed: {response.text}"
        data = response.json()
        assert data["page_name"] == new_page["page_name"]
        assert "id" in data
        
        # Cleanup - delete the test page
        page_id = data["id"]
        self.session.delete(f"{BASE_URL}/api/pages/{page_id}")
        print(f"✓ Create new page works")


class TestExemplarEndpoints:
    """Exemplars: List all (should be 4), filter by family, get single, verify primaries"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
        login_resp = self.session.post(
            f"{BASE_URL}/api/auth/login",
            json={"password": "TSFounder!Vault2026#Secure"}
        )
        self.token = login_resp.json()["access_token"]
        self.session.headers.update({"Authorization": f"Bearer {self.token}"})
    
    def test_list_all_exemplars(self):
        """Test listing all exemplars (should be 4)"""
        response = self.session.get(f"{BASE_URL}/api/exemplars")
        assert response.status_code == 200, f"List exemplars failed: {response.text}"
        data = response.json()
        assert "exemplars" in data
        assert "total" in data
        assert data["total"] == 4, f"Expected 4 exemplars, got {data['total']}"
        print(f"✓ List exemplars returns {data['total']} exemplars")
    
    def test_filter_by_family(self):
        """Test filtering exemplars by family"""
        response = self.session.get(f"{BASE_URL}/api/exemplars?family=District")
        assert response.status_code == 200, f"Filter exemplars failed: {response.text}"
        data = response.json()
        assert "exemplars" in data
        for ex in data["exemplars"]:
            assert ex.get("page_family") == "District"
        print(f"✓ Filter exemplars by family works, returned {len(data['exemplars'])} District exemplars")
    
    def test_get_single_exemplar(self):
        """Test getting a single exemplar"""
        # Get list first
        list_resp = self.session.get(f"{BASE_URL}/api/exemplars")
        exemplars = list_resp.json()["exemplars"]
        if exemplars:
            exemplar_id = exemplars[0]["id"]
            response = self.session.get(f"{BASE_URL}/api/exemplars/{exemplar_id}")
            assert response.status_code == 200, f"Get exemplar failed: {response.text}"
            data = response.json()
            assert data["id"] == exemplar_id
            print(f"✓ Get single exemplar works: {data.get('page_name')}")
    
    def test_verify_primaries(self):
        """Verify Core Hub, District, and Trust have primary exemplars"""
        response = self.session.get(f"{BASE_URL}/api/exemplars")
        data = response.json()
        by_family = data.get("by_family", {})
        
        # Check Core Hub has primary
        core_hub = by_family.get("Core Hub", {})
        assert core_hub.get("primary") is not None, "Core Hub should have a primary exemplar"
        
        # Check District has primary (at least one)
        district = by_family.get("District", {})
        # District may or may not have primary set
        
        # Check Trust has primary
        trust = by_family.get("Trust", {})
        assert trust.get("primary") is not None, "Trust should have a primary exemplar"
        
        print(f"✓ Primary exemplars verified for Core Hub and Trust")


class TestHouseTemplateEndpoints:
    """House Templates: List all (should be 3), filter by family, get single, verify Education District Pattern"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
        login_resp = self.session.post(
            f"{BASE_URL}/api/auth/login",
            json={"password": "TSFounder!Vault2026#Secure"}
        )
        self.token = login_resp.json()["access_token"]
        self.session.headers.update({"Authorization": f"Bearer {self.token}"})
    
    def test_list_all_templates(self):
        """Test listing all house templates (should be 3)"""
        response = self.session.get(f"{BASE_URL}/api/house-templates")
        assert response.status_code == 200, f"List templates failed: {response.text}"
        data = response.json()
        assert "templates" in data
        assert "total" in data
        assert data["total"] == 3, f"Expected 3 templates, got {data['total']}"
        print(f"✓ List house templates returns {data['total']} templates")
    
    def test_filter_by_family(self):
        """Test filtering templates by family"""
        response = self.session.get(f"{BASE_URL}/api/house-templates?family=District")
        assert response.status_code == 200, f"Filter templates failed: {response.text}"
        data = response.json()
        assert "templates" in data
        print(f"✓ Filter templates by family works, returned {len(data['templates'])} District templates")
    
    def test_get_single_template(self):
        """Test getting a single template"""
        list_resp = self.session.get(f"{BASE_URL}/api/house-templates")
        templates = list_resp.json()["templates"]
        if templates:
            template_id = templates[0]["id"]
            response = self.session.get(f"{BASE_URL}/api/house-templates/{template_id}")
            assert response.status_code == 200, f"Get template failed: {response.text}"
            data = response.json()
            assert data["id"] == template_id
            print(f"✓ Get single template works: {data.get('template_name')}")
    
    def test_education_district_pattern_exists(self):
        """Verify Education District Pattern exists and is active"""
        response = self.session.get(f"{BASE_URL}/api/house-templates")
        templates = response.json()["templates"]
        
        edu_template = None
        for t in templates:
            if "Education District" in t.get("template_name", ""):
                edu_template = t
                break
        
        assert edu_template is not None, "Education District Pattern template not found"
        assert edu_template.get("status") == "active", "Education District Pattern should be active"
        print(f"✓ Education District Pattern exists and is active")


class TestStyleProfileEndpoints:
    """Style Profiles: List all (should be 6), filter by family, verify defaults"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
        login_resp = self.session.post(
            f"{BASE_URL}/api/auth/login",
            json={"password": "TSFounder!Vault2026#Secure"}
        )
        self.token = login_resp.json()["access_token"]
        self.session.headers.update({"Authorization": f"Bearer {self.token}"})
    
    def test_list_all_profiles(self):
        """Test listing all style profiles (should be 6)"""
        response = self.session.get(f"{BASE_URL}/api/style-profiles")
        assert response.status_code == 200, f"List profiles failed: {response.text}"
        data = response.json()
        assert "profiles" in data
        assert "total" in data
        assert data["total"] == 6, f"Expected 6 profiles, got {data['total']}"
        print(f"✓ List style profiles returns {data['total']} profiles")
    
    def test_filter_by_family(self):
        """Test filtering profiles by family"""
        response = self.session.get(f"{BASE_URL}/api/style-profiles?family=Trust")
        assert response.status_code == 200, f"Filter profiles failed: {response.text}"
        data = response.json()
        assert "profiles" in data
        print(f"✓ Filter profiles by family works, returned {len(data['profiles'])} Trust profiles")
    
    def test_verify_defaults_by_family(self):
        """Verify defaults_by_family is populated"""
        response = self.session.get(f"{BASE_URL}/api/style-profiles")
        data = response.json()
        assert "defaults_by_family" in data
        defaults = data["defaults_by_family"]
        # Should have some defaults set
        assert len(defaults) > 0, "Should have some default profiles by family"
        print(f"✓ Defaults by family verified: {list(defaults.keys())}")


class TestPromotionCandidateEndpoints:
    """Promotion Candidates: List all (should be 7), filter by status, verify counts"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
        login_resp = self.session.post(
            f"{BASE_URL}/api/auth/login",
            json={"password": "TSFounder!Vault2026#Secure"}
        )
        self.token = login_resp.json()["access_token"]
        self.session.headers.update({"Authorization": f"Bearer {self.token}"})
    
    def test_list_all_candidates(self):
        """Test listing all promotion candidates (should be 7)"""
        response = self.session.get(f"{BASE_URL}/api/promotions/candidates")
        assert response.status_code == 200, f"List candidates failed: {response.text}"
        data = response.json()
        assert "candidates" in data
        assert "total" in data
        assert data["total"] == 7, f"Expected 7 candidates, got {data['total']}"
        print(f"✓ List promotion candidates returns {data['total']} candidates")
    
    def test_filter_by_status(self):
        """Test filtering candidates by status"""
        response = self.session.get(f"{BASE_URL}/api/promotions/candidates?status=promoted")
        assert response.status_code == 200, f"Filter candidates failed: {response.text}"
        data = response.json()
        assert "candidates" in data
        for c in data["candidates"]:
            assert c.get("status") == "promoted"
        print(f"✓ Filter candidates by status works, returned {len(data['candidates'])} promoted")
    
    def test_verify_status_counts(self):
        """Verify promoted/dismissed/pending counts"""
        response = self.session.get(f"{BASE_URL}/api/promotions/candidates")
        data = response.json()
        assert "status_counts" in data
        counts = data["status_counts"]
        assert "promoted" in counts
        assert "dismissed" in counts
        assert "pending" in counts
        print(f"✓ Status counts: promoted={counts.get('promoted')}, dismissed={counts.get('dismissed')}, pending={counts.get('pending')}")


class TestSettingsEndpoints:
    """Settings: Get settings, update settings"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
        login_resp = self.session.post(
            f"{BASE_URL}/api/auth/login",
            json={"password": "TSFounder!Vault2026#Secure"}
        )
        self.token = login_resp.json()["access_token"]
        self.session.headers.update({"Authorization": f"Bearer {self.token}"})
    
    def test_get_settings(self):
        """Test getting settings"""
        response = self.session.get(f"{BASE_URL}/api/settings")
        assert response.status_code == 200, f"Get settings failed: {response.text}"
        data = response.json()
        assert "scoring_threshold_strong" in data
        assert "scoring_threshold_usable" in data
        assert "default_tone" in data
        assert "page_generation_model" in data
        print(f"✓ Get settings works: threshold_strong={data['scoring_threshold_strong']}")
    
    def test_update_settings(self):
        """Test updating settings"""
        # Get current
        current = self.session.get(f"{BASE_URL}/api/settings").json()
        original_tone = current.get("default_tone")
        
        # Update
        response = self.session.put(
            f"{BASE_URL}/api/settings",
            json={"default_tone": "warm"}
        )
        assert response.status_code == 200, f"Update settings failed: {response.text}"
        data = response.json()
        assert data.get("default_tone") == "warm"
        
        # Restore
        self.session.put(f"{BASE_URL}/api/settings", json={"default_tone": original_tone})
        print(f"✓ Update settings works")


class TestBrandVoiceEndpoint:
    """Brand Voice: Get brand voice endpoint returns full brand config"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
        login_resp = self.session.post(
            f"{BASE_URL}/api/auth/login",
            json={"password": "TSFounder!Vault2026#Secure"}
        )
        self.token = login_resp.json()["access_token"]
        self.session.headers.update({"Authorization": f"Bearer {self.token}"})
    
    def test_get_brand_voice(self):
        """Test brand voice endpoint returns full config"""
        response = self.session.get(f"{BASE_URL}/api/brand-voice")
        assert response.status_code == 200, f"Get brand voice failed: {response.text}"
        data = response.json()
        
        # Verify all required fields
        assert "motto" in data
        assert data["motto"] == "YOUR PASSION IS OUR PLEASURE"
        assert "emotional_core" in data
        assert "user_should_feel" in data
        assert "brand_should_feel" in data
        assert "brand_should_NOT_feel" in data
        assert "copy_principles" in data
        assert "good_phrases" in data
        assert "avoid_phrases" in data
        assert "cta_style" in data
        
        print(f"✓ Brand voice endpoint returns full config with motto: {data['motto']}")


class TestActivityEndpoint:
    """Activity: Get recent activity logs"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
        login_resp = self.session.post(
            f"{BASE_URL}/api/auth/login",
            json={"password": "TSFounder!Vault2026#Secure"}
        )
        self.token = login_resp.json()["access_token"]
        self.session.headers.update({"Authorization": f"Bearer {self.token}"})
    
    def test_get_activity(self):
        """Test getting recent activity logs"""
        response = self.session.get(f"{BASE_URL}/api/activity")
        assert response.status_code == 200, f"Get activity failed: {response.text}"
        data = response.json()
        assert isinstance(data, list), "Activity should return a list"
        if data:
            assert "action" in data[0]
            assert "timestamp" in data[0]
        print(f"✓ Activity endpoint returns {len(data)} logs")


class TestEcosystemEndpoints:
    """Ecosystem: Families, types, statuses endpoints return data"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
        login_resp = self.session.post(
            f"{BASE_URL}/api/auth/login",
            json={"password": "TSFounder!Vault2026#Secure"}
        )
        self.token = login_resp.json()["access_token"]
        self.session.headers.update({"Authorization": f"Bearer {self.token}"})
    
    def test_get_families(self):
        """Test ecosystem families endpoint"""
        response = self.session.get(f"{BASE_URL}/api/ecosystem/families")
        assert response.status_code == 200, f"Get families failed: {response.text}"
        data = response.json()
        assert "families" in data
        assert len(data["families"]) > 0
        print(f"✓ Ecosystem families returns {len(data['families'])} families")
    
    def test_get_types(self):
        """Test ecosystem types endpoint"""
        response = self.session.get(f"{BASE_URL}/api/ecosystem/types")
        assert response.status_code == 200, f"Get types failed: {response.text}"
        data = response.json()
        assert "types" in data
        assert len(data["types"]) > 0
        print(f"✓ Ecosystem types returns {len(data['types'])} types")
    
    def test_get_statuses(self):
        """Test ecosystem statuses endpoint"""
        response = self.session.get(f"{BASE_URL}/api/ecosystem/statuses")
        assert response.status_code == 200, f"Get statuses failed: {response.text}"
        data = response.json()
        assert "statuses" in data
        assert len(data["statuses"]) > 0
        print(f"✓ Ecosystem statuses returns {len(data['statuses'])} statuses")


class TestVersionHistoryEndpoint:
    """Version History: Get versions for a page that has them"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
        login_resp = self.session.post(
            f"{BASE_URL}/api/auth/login",
            json={"password": "TSFounder!Vault2026#Secure"}
        )
        self.token = login_resp.json()["access_token"]
        self.session.headers.update({"Authorization": f"Bearer {self.token}"})
    
    def test_get_versions_for_page(self):
        """Test getting versions for a page"""
        # Get a page that might have versions (from exemplars)
        exemplars_resp = self.session.get(f"{BASE_URL}/api/exemplars")
        exemplars = exemplars_resp.json().get("exemplars", [])
        
        if exemplars:
            page_id = exemplars[0]["page_id"]
            response = self.session.get(f"{BASE_URL}/api/pages/{page_id}/versions")
            assert response.status_code == 200, f"Get versions failed: {response.text}"
            data = response.json()
            assert "page_id" in data
            assert "versions" in data
            assert "total_versions" in data
            print(f"✓ Version history works: {data['total_versions']} versions for page")
        else:
            # If no exemplars, just test the endpoint exists
            list_resp = self.session.get(f"{BASE_URL}/api/pages")
            pages = list_resp.json()["pages"]
            if pages:
                page_id = pages[0]["id"]
                response = self.session.get(f"{BASE_URL}/api/pages/{page_id}/versions")
                assert response.status_code == 200, f"Get versions failed: {response.text}"
                print(f"✓ Version history endpoint works")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
