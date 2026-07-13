"""
Test suite for Exemplar Library endpoints - Phase 1: Gold Standard / Exemplar Pages v1
Tests CRUD operations for exemplars, reason tags, primary exemplar management
"""
import pytest
import requests
import os
import time

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')
PASSWORD = "TSFounder!Vault2026#Secure"
HOMEPAGE_PAGE_ID = "ef54de19-6e5b-405e-9e80-5316b31ddd1f"

class TestExemplarEndpoints:
    """Test Exemplar Library API endpoints"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup session with authentication"""
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
        # Login
        login_res = self.session.post(f"{BASE_URL}/api/auth/login", json={"password": PASSWORD})
        assert login_res.status_code == 200, f"Login failed: {login_res.text}"
        self.token = login_res.json().get("access_token")
        self.session.headers.update({"Authorization": f"Bearer {self.token}"})
        yield
    
    # ==================== GET /api/exemplars ====================
    def test_get_all_exemplars(self):
        """GET /api/exemplars - returns all exemplars with by_family grouping"""
        res = self.session.get(f"{BASE_URL}/api/exemplars")
        assert res.status_code == 200, f"Failed: {res.text}"
        data = res.json()
        
        # Validate response structure
        assert "exemplars" in data, "Missing 'exemplars' key"
        assert "total" in data, "Missing 'total' key"
        assert "by_family" in data, "Missing 'by_family' key"
        assert "available_reason_tags" in data, "Missing 'available_reason_tags' key"
        
        # Validate reason tags are present
        assert len(data["available_reason_tags"]) > 0, "No reason tags available"
        print(f"✓ GET /api/exemplars - Found {data['total']} exemplars, {len(data['available_reason_tags'])} reason tags")
    
    def test_get_exemplars_with_family_filter(self):
        """GET /api/exemplars?family=Core Hub - filters by family"""
        res = self.session.get(f"{BASE_URL}/api/exemplars?family=Core%20Hub")
        assert res.status_code == 200, f"Failed: {res.text}"
        data = res.json()
        
        # All returned exemplars should be Core Hub family
        for ex in data.get("exemplars", []):
            assert ex.get("page_family") == "Core Hub", f"Wrong family: {ex.get('page_family')}"
        print(f"✓ GET /api/exemplars?family=Core Hub - Found {data['total']} Core Hub exemplars")
    
    # ==================== GET /api/exemplars/family/{family} ====================
    def test_get_exemplars_by_family(self):
        """GET /api/exemplars/family/{family} - returns exemplars for specific family"""
        res = self.session.get(f"{BASE_URL}/api/exemplars/family/Core%20Hub")
        assert res.status_code == 200, f"Failed: {res.text}"
        data = res.json()
        
        assert "family" in data, "Missing 'family' key"
        assert "exemplars" in data, "Missing 'exemplars' key"
        assert "total" in data, "Missing 'total' key"
        assert "primary_exemplar" in data, "Missing 'primary_exemplar' key"
        assert data["family"] == "Core Hub", f"Wrong family: {data['family']}"
        print(f"✓ GET /api/exemplars/family/Core Hub - Found {data['total']} exemplars, primary: {data['primary_exemplar'] is not None}")
    
    # ==================== GET /api/exemplars/reason-tags/options ====================
    def test_get_reason_tags_options(self):
        """GET /api/exemplars/reason-tags/options - returns available reason tags"""
        res = self.session.get(f"{BASE_URL}/api/exemplars/reason-tags/options")
        assert res.status_code == 200, f"Failed: {res.text}"
        data = res.json()
        
        assert "tags" in data, "Missing 'tags' key"
        assert len(data["tags"]) > 0, "No tags returned"
        
        # Check for expected tags
        expected_tags = ["Strong brand voice", "Perfect structure", "Emotional resonance"]
        for tag in expected_tags:
            assert tag in data["tags"], f"Missing expected tag: {tag}"
        print(f"✓ GET /api/exemplars/reason-tags/options - Found {len(data['tags'])} tags")
    
    # ==================== GET /api/exemplars/{id} ====================
    def test_get_single_exemplar(self):
        """GET /api/exemplars/{id} - returns single exemplar"""
        # First get all exemplars to find one
        all_res = self.session.get(f"{BASE_URL}/api/exemplars")
        assert all_res.status_code == 200
        exemplars = all_res.json().get("exemplars", [])
        
        if len(exemplars) == 0:
            pytest.skip("No exemplars exist to test single get")
        
        exemplar_id = exemplars[0]["id"]
        res = self.session.get(f"{BASE_URL}/api/exemplars/{exemplar_id}")
        assert res.status_code == 200, f"Failed: {res.text}"
        data = res.json()
        
        assert data["id"] == exemplar_id, "ID mismatch"
        assert "page_name" in data, "Missing page_name"
        assert "page_family" in data, "Missing page_family"
        assert "version_number" in data, "Missing version_number"
        assert "generated_content" in data, "Missing generated_content"
        print(f"✓ GET /api/exemplars/{exemplar_id} - Found: {data['page_name']}")
    
    def test_get_nonexistent_exemplar(self):
        """GET /api/exemplars/{id} - returns 404 for nonexistent"""
        res = self.session.get(f"{BASE_URL}/api/exemplars/nonexistent-id-12345")
        assert res.status_code == 404, f"Expected 404, got {res.status_code}"
        print("✓ GET /api/exemplars/nonexistent - Returns 404")
    
    # ==================== POST /api/exemplars ====================
    def test_create_exemplar_full_cycle(self):
        """POST /api/exemplars - creates formal exemplar with reason_tags, notes, is_primary"""
        # First, get page versions to find a valid version
        versions_res = self.session.get(f"{BASE_URL}/api/pages/{HOMEPAGE_PAGE_ID}/versions")
        if versions_res.status_code != 200:
            pytest.skip(f"Could not get versions for page: {versions_res.text}")
        
        versions = versions_res.json().get("versions", [])
        if len(versions) == 0:
            pytest.skip("No versions exist for homepage")
        
        # Find a version that's not already an exemplar
        test_version = None
        for v in versions:
            if not v.get("is_exemplar"):
                test_version = v
                break
        
        if not test_version:
            pytest.skip("All versions are already exemplars")
        
        # Create exemplar
        create_payload = {
            "page_id": HOMEPAGE_PAGE_ID,
            "version_id": test_version["id"],
            "reason_tags": ["Strong brand voice", "Perfect structure"],
            "exemplar_notes": "TEST_exemplar - Created by automated test",
            "is_primary": False
        }
        
        res = self.session.post(f"{BASE_URL}/api/exemplars", json=create_payload)
        assert res.status_code == 201, f"Failed to create: {res.text}"
        data = res.json()
        
        # Validate response
        assert "id" in data, "Missing id"
        assert data["page_id"] == HOMEPAGE_PAGE_ID, "Wrong page_id"
        assert data["version_id"] == test_version["id"], "Wrong version_id"
        assert data["reason_tags"] == create_payload["reason_tags"], "Wrong reason_tags"
        assert data["exemplar_notes"] == create_payload["exemplar_notes"], "Wrong notes"
        
        created_id = data["id"]
        print(f"✓ POST /api/exemplars - Created exemplar {created_id}")
        
        # Verify it was persisted
        get_res = self.session.get(f"{BASE_URL}/api/exemplars/{created_id}")
        assert get_res.status_code == 200, "Failed to get created exemplar"
        
        # Cleanup - delete the test exemplar
        del_res = self.session.delete(f"{BASE_URL}/api/exemplars/{created_id}")
        assert del_res.status_code == 200, f"Failed to cleanup: {del_res.text}"
        print(f"✓ Cleanup - Deleted test exemplar {created_id}")
    
    def test_create_duplicate_exemplar_fails(self):
        """POST /api/exemplars - returns 409 for duplicate version"""
        # Get existing exemplar
        all_res = self.session.get(f"{BASE_URL}/api/exemplars")
        exemplars = all_res.json().get("exemplars", [])
        
        if len(exemplars) == 0:
            pytest.skip("No exemplars exist to test duplicate")
        
        existing = exemplars[0]
        
        # Try to create duplicate
        create_payload = {
            "page_id": existing["page_id"],
            "version_id": existing["version_id"],
            "reason_tags": ["Test tag"],
            "exemplar_notes": "Duplicate test",
            "is_primary": False
        }
        
        res = self.session.post(f"{BASE_URL}/api/exemplars", json=create_payload)
        assert res.status_code == 409, f"Expected 409 for duplicate, got {res.status_code}"
        print("✓ POST /api/exemplars - Returns 409 for duplicate version")
    
    # ==================== PUT /api/exemplars/{id} ====================
    def test_update_exemplar(self):
        """PUT /api/exemplars/{id} - updates exemplar reason_tags/notes"""
        # Get existing exemplar
        all_res = self.session.get(f"{BASE_URL}/api/exemplars")
        exemplars = all_res.json().get("exemplars", [])
        
        if len(exemplars) == 0:
            pytest.skip("No exemplars exist to test update")
        
        exemplar = exemplars[0]
        exemplar_id = exemplar["id"]
        original_notes = exemplar.get("exemplar_notes")
        
        # Update
        update_payload = {
            "reason_tags": ["Emotional resonance", "Trust-building excellence"],
            "exemplar_notes": "TEST_updated notes - " + str(time.time())
        }
        
        res = self.session.put(f"{BASE_URL}/api/exemplars/{exemplar_id}", json=update_payload)
        assert res.status_code == 200, f"Failed to update: {res.text}"
        data = res.json()
        
        assert data["reason_tags"] == update_payload["reason_tags"], "Tags not updated"
        assert data["exemplar_notes"] == update_payload["exemplar_notes"], "Notes not updated"
        print(f"✓ PUT /api/exemplars/{exemplar_id} - Updated successfully")
        
        # Verify persistence
        get_res = self.session.get(f"{BASE_URL}/api/exemplars/{exemplar_id}")
        assert get_res.status_code == 200
        fetched = get_res.json()
        assert fetched["exemplar_notes"] == update_payload["exemplar_notes"], "Update not persisted"
        
        # Restore original notes if any
        if original_notes:
            self.session.put(f"{BASE_URL}/api/exemplars/{exemplar_id}", json={"exemplar_notes": original_notes})
    
    # ==================== POST /api/exemplars/{id}/set-primary ====================
    def test_set_primary_exemplar(self):
        """POST /api/exemplars/{id}/set-primary - sets exemplar as primary for its family"""
        # Get exemplars for Core Hub family
        family_res = self.session.get(f"{BASE_URL}/api/exemplars/family/Core%20Hub")
        assert family_res.status_code == 200
        data = family_res.json()
        exemplars = data.get("exemplars", [])
        
        if len(exemplars) == 0:
            pytest.skip("No Core Hub exemplars to test set-primary")
        
        # Find a non-primary exemplar
        non_primary = None
        for ex in exemplars:
            if not ex.get("is_primary"):
                non_primary = ex
                break
        
        if not non_primary:
            # All are primary or only one exists - use the first one
            non_primary = exemplars[0]
        
        exemplar_id = non_primary["id"]
        
        # Set as primary
        res = self.session.post(f"{BASE_URL}/api/exemplars/{exemplar_id}/set-primary")
        assert res.status_code == 200, f"Failed: {res.text}"
        data = res.json()
        
        assert data.get("is_primary") == True, "Not set as primary"
        print(f"✓ POST /api/exemplars/{exemplar_id}/set-primary - Set as primary")
        
        # Verify only one primary in family
        family_res2 = self.session.get(f"{BASE_URL}/api/exemplars/family/Core%20Hub")
        exemplars2 = family_res2.json().get("exemplars", [])
        primary_count = sum(1 for e in exemplars2 if e.get("is_primary"))
        assert primary_count == 1, f"Expected 1 primary, found {primary_count}"
        print("✓ Verified only one primary exemplar in family")
    
    # ==================== DELETE /api/exemplars/{id} ====================
    def test_delete_exemplar_and_verify_removal(self):
        """DELETE /api/exemplars/{id} - removes exemplar and unflags version"""
        # First create an exemplar to delete
        versions_res = self.session.get(f"{BASE_URL}/api/pages/{HOMEPAGE_PAGE_ID}/versions")
        if versions_res.status_code != 200:
            pytest.skip("Could not get versions")
        
        versions = versions_res.json().get("versions", [])
        
        # Find a non-exemplar version
        test_version = None
        for v in versions:
            if not v.get("is_exemplar"):
                test_version = v
                break
        
        if not test_version:
            pytest.skip("No non-exemplar versions available")
        
        # Create exemplar
        create_payload = {
            "page_id": HOMEPAGE_PAGE_ID,
            "version_id": test_version["id"],
            "reason_tags": ["Test tag"],
            "exemplar_notes": "TEST_to_delete",
            "is_primary": False
        }
        
        create_res = self.session.post(f"{BASE_URL}/api/exemplars", json=create_payload)
        if create_res.status_code != 201:
            pytest.skip(f"Could not create test exemplar: {create_res.text}")
        
        created_id = create_res.json()["id"]
        
        # Delete
        del_res = self.session.delete(f"{BASE_URL}/api/exemplars/{created_id}")
        assert del_res.status_code == 200, f"Delete failed: {del_res.text}"
        print(f"✓ DELETE /api/exemplars/{created_id} - Deleted successfully")
        
        # Verify removal
        get_res = self.session.get(f"{BASE_URL}/api/exemplars/{created_id}")
        assert get_res.status_code == 404, "Exemplar still exists after delete"
        print("✓ Verified exemplar no longer exists")


class TestExemplarDataIntegrity:
    """Test data integrity and edge cases"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup session with authentication"""
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
        login_res = self.session.post(f"{BASE_URL}/api/auth/login", json={"password": PASSWORD})
        assert login_res.status_code == 200
        self.token = login_res.json().get("access_token")
        self.session.headers.update({"Authorization": f"Bearer {self.token}"})
        yield
    
    def test_exemplar_contains_page_details(self):
        """Verify exemplar response includes page details"""
        all_res = self.session.get(f"{BASE_URL}/api/exemplars")
        exemplars = all_res.json().get("exemplars", [])
        
        if len(exemplars) == 0:
            pytest.skip("No exemplars to verify")
        
        ex = exemplars[0]
        required_fields = ["id", "page_id", "version_id", "page_name", "page_family", 
                          "page_type", "version_number", "generated_content", "reason_tags",
                          "is_primary", "created_at", "updated_at"]
        
        for field in required_fields:
            assert field in ex, f"Missing required field: {field}"
        
        print(f"✓ Exemplar contains all required fields: {len(required_fields)} fields verified")
    
    def test_by_family_grouping_correct(self):
        """Verify by_family grouping is accurate"""
        all_res = self.session.get(f"{BASE_URL}/api/exemplars")
        data = all_res.json()
        
        by_family = data.get("by_family", {})
        exemplars = data.get("exemplars", [])
        
        # Count exemplars per family manually
        manual_count = {}
        for ex in exemplars:
            fam = ex.get("page_family", "Unknown")
            manual_count[fam] = manual_count.get(fam, 0) + 1
        
        # Verify counts match
        for fam, count in manual_count.items():
            assert fam in by_family, f"Family {fam} missing from by_family"
            assert by_family[fam]["count"] == count, f"Count mismatch for {fam}"
        
        print(f"✓ by_family grouping verified for {len(by_family)} families")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
