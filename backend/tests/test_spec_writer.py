"""
Spec Writer Minion - Backend API Tests
Tests CRUD operations, validation, status changes, and versions for specs.
Does NOT test LLM generation/scoring (those hit external APIs).
"""
import pytest
import requests
import os
import uuid

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')
PASSWORD = "TSFounder!Vault2026#Secure"

# Valid spec types and statuses from models.py
VALID_SPEC_TYPES = [
    "Software Feature",
    "Standalone App",
    "Plugin / Extension",
    "GPT / AI Agent",
    "Automation / Workflow",
    "Internal Tool",
]

VALID_STATUSES = [
    "Draft",
    "Scored",
    "Needs Refinement",
    "Ready",
    "Handed Off",
    "Archived",
]


@pytest.fixture(scope="module")
def auth_token():
    """Get authentication token for all tests"""
    response = requests.post(f"{BASE_URL}/api/auth/login", json={"password": PASSWORD})
    assert response.status_code == 200, f"Login failed: {response.text}"
    data = response.json()
    assert "access_token" in data
    return data["access_token"]


@pytest.fixture(scope="module")
def auth_headers(auth_token):
    """Headers with auth token"""
    return {
        "Authorization": f"Bearer {auth_token}",
        "Content-Type": "application/json"
    }


@pytest.fixture
def created_spec_id(auth_headers):
    """Create a test spec and return its ID, clean up after test"""
    spec_data = {
        "title": f"TEST_Spec_{uuid.uuid4().hex[:8]}",
        "spec_type": "Software Feature",
        "raw_idea": "A test spec for automated testing purposes",
        "target_audience": "QA Engineers",
        "priority": "P1",
        "constraints": "Must be testable",
    }
    response = requests.post(f"{BASE_URL}/api/specs", json=spec_data, headers=auth_headers)
    assert response.status_code == 201, f"Failed to create test spec: {response.text}"
    spec_id = response.json()["id"]
    yield spec_id
    # Cleanup
    requests.delete(f"{BASE_URL}/api/specs/{spec_id}", headers=auth_headers)


class TestSpecWriterAuth:
    """Test that spec endpoints require authentication"""
    
    def test_list_specs_requires_auth(self):
        response = requests.get(f"{BASE_URL}/api/specs")
        assert response.status_code == 401
    
    def test_create_spec_requires_auth(self):
        response = requests.post(f"{BASE_URL}/api/specs", json={
            "title": "Test", "spec_type": "Software Feature", "raw_idea": "Test"
        })
        assert response.status_code == 401


class TestSpecCRUD:
    """Test Spec CRUD operations"""
    
    def test_create_spec_success(self, auth_headers):
        """POST /api/specs - Create new spec with all required fields"""
        spec_data = {
            "title": f"TEST_Create_Spec_{uuid.uuid4().hex[:8]}",
            "spec_type": "Standalone App",
            "raw_idea": "Build a mobile app for tracking daily habits",
            "target_audience": "Health-conscious individuals",
            "priority": "P0",
            "constraints": "Must work offline",
            "reference_links": ["https://example.com/reference"],
        }
        response = requests.post(f"{BASE_URL}/api/specs", json=spec_data, headers=auth_headers)
        assert response.status_code == 201, f"Create failed: {response.text}"
        
        data = response.json()
        assert "id" in data
        assert data["title"] == spec_data["title"]
        assert data["spec_type"] == spec_data["spec_type"]
        assert data["raw_idea"] == spec_data["raw_idea"]
        assert data["target_audience"] == spec_data["target_audience"]
        assert data["priority"] == spec_data["priority"]
        assert data["constraints"] == spec_data["constraints"]
        assert data["status"] == "Draft"  # Default status
        assert data["generated_spec"] is None  # Not generated yet
        assert data["completeness_score"] is None
        
        # Cleanup
        requests.delete(f"{BASE_URL}/api/specs/{data['id']}", headers=auth_headers)
    
    def test_create_spec_with_input_answers(self, auth_headers):
        """POST /api/specs - Create spec with structured input answers"""
        spec_data = {
            "title": f"TEST_InputAnswers_{uuid.uuid4().hex[:8]}",
            "spec_type": "Internal Tool",
            "raw_idea": "Dashboard for monitoring server health",
            "input_answers": {
                "what_is_it": "A monitoring dashboard",
                "who_is_it_for": "DevOps team",
                "what_pain": "No visibility into server health",
            }
        }
        response = requests.post(f"{BASE_URL}/api/specs", json=spec_data, headers=auth_headers)
        assert response.status_code == 201
        
        data = response.json()
        assert data["input_answers"]["what_is_it"] == "A monitoring dashboard"
        
        # Cleanup
        requests.delete(f"{BASE_URL}/api/specs/{data['id']}", headers=auth_headers)
    
    def test_list_specs_returns_array(self, auth_headers):
        """GET /api/specs - Returns specs array"""
        response = requests.get(f"{BASE_URL}/api/specs", headers=auth_headers)
        assert response.status_code == 200
        
        data = response.json()
        assert "specs" in data
        assert "total" in data
        assert isinstance(data["specs"], list)
        assert isinstance(data["total"], int)
    
    def test_get_spec_stats(self, auth_headers):
        """GET /api/specs/stats - Returns stats object"""
        response = requests.get(f"{BASE_URL}/api/specs/stats", headers=auth_headers)
        assert response.status_code == 200
        
        data = response.json()
        assert "total" in data
        assert "by_status" in data
        assert "by_type" in data
        assert "by_priority" in data
        assert "ready_count" in data
        assert "needs_refinement_count" in data
        assert isinstance(data["by_status"], dict)
        assert isinstance(data["by_type"], dict)
    
    def test_get_single_spec(self, auth_headers, created_spec_id):
        """GET /api/specs/{id} - Get single spec by ID"""
        response = requests.get(f"{BASE_URL}/api/specs/{created_spec_id}", headers=auth_headers)
        assert response.status_code == 200
        
        data = response.json()
        assert data["id"] == created_spec_id
        assert "title" in data
        assert "spec_type" in data
        assert "raw_idea" in data
        assert "status" in data
    
    def test_get_nonexistent_spec_returns_404(self, auth_headers):
        """GET /api/specs/{id} - Returns 404 for non-existent spec"""
        fake_id = str(uuid.uuid4())
        response = requests.get(f"{BASE_URL}/api/specs/{fake_id}", headers=auth_headers)
        assert response.status_code == 404
    
    def test_update_spec_metadata(self, auth_headers, created_spec_id):
        """PUT /api/specs/{id} - Update spec metadata"""
        update_data = {
            "title": "Updated Test Title",
            "priority": "P0",
            "constraints": "Updated constraints",
        }
        response = requests.put(f"{BASE_URL}/api/specs/{created_spec_id}", json=update_data, headers=auth_headers)
        assert response.status_code == 200
        
        data = response.json()
        assert data["title"] == "Updated Test Title"
        assert data["priority"] == "P0"
        assert data["constraints"] == "Updated constraints"
        
        # Verify persistence with GET
        get_response = requests.get(f"{BASE_URL}/api/specs/{created_spec_id}", headers=auth_headers)
        assert get_response.status_code == 200
        assert get_response.json()["title"] == "Updated Test Title"
    
    def test_delete_spec(self, auth_headers):
        """DELETE /api/specs/{id} - Delete spec"""
        # Create a spec to delete
        spec_data = {
            "title": f"TEST_ToDelete_{uuid.uuid4().hex[:8]}",
            "spec_type": "Software Feature",
            "raw_idea": "This will be deleted",
        }
        create_response = requests.post(f"{BASE_URL}/api/specs", json=spec_data, headers=auth_headers)
        assert create_response.status_code == 201
        spec_id = create_response.json()["id"]
        
        # Delete it
        delete_response = requests.delete(f"{BASE_URL}/api/specs/{spec_id}", headers=auth_headers)
        assert delete_response.status_code == 200
        
        # Verify it's gone
        get_response = requests.get(f"{BASE_URL}/api/specs/{spec_id}", headers=auth_headers)
        assert get_response.status_code == 404
    
    def test_delete_nonexistent_spec_returns_404(self, auth_headers):
        """DELETE /api/specs/{id} - Returns 404 for non-existent spec"""
        fake_id = str(uuid.uuid4())
        response = requests.delete(f"{BASE_URL}/api/specs/{fake_id}", headers=auth_headers)
        assert response.status_code == 404


class TestSpecTypeValidation:
    """Test spec type validation"""
    
    @pytest.mark.parametrize("spec_type", VALID_SPEC_TYPES)
    def test_valid_spec_types_accepted(self, auth_headers, spec_type):
        """POST /api/specs - All 6 valid spec types are accepted"""
        spec_data = {
            "title": f"TEST_Type_{spec_type[:10]}_{uuid.uuid4().hex[:6]}",
            "spec_type": spec_type,
            "raw_idea": f"Testing {spec_type} type",
        }
        response = requests.post(f"{BASE_URL}/api/specs", json=spec_data, headers=auth_headers)
        assert response.status_code == 201, f"Type '{spec_type}' should be valid: {response.text}"
        
        # Cleanup
        requests.delete(f"{BASE_URL}/api/specs/{response.json()['id']}", headers=auth_headers)
    
    def test_invalid_spec_type_rejected(self, auth_headers):
        """POST /api/specs - Invalid spec type returns 400"""
        spec_data = {
            "title": "TEST_InvalidType",
            "spec_type": "Invalid Type That Does Not Exist",
            "raw_idea": "This should fail",
        }
        response = requests.post(f"{BASE_URL}/api/specs", json=spec_data, headers=auth_headers)
        assert response.status_code == 400
        assert "Invalid spec type" in response.json().get("detail", "")


class TestSpecStatusChange:
    """Test spec status changes"""
    
    def test_change_spec_status(self, auth_headers, created_spec_id):
        """POST /api/specs/{id}/status - Change spec status"""
        response = requests.post(
            f"{BASE_URL}/api/specs/{created_spec_id}/status",
            json={"status": "Ready"},
            headers=auth_headers
        )
        assert response.status_code == 200
        
        data = response.json()
        assert data["status"] == "Ready"
        
        # Verify persistence
        get_response = requests.get(f"{BASE_URL}/api/specs/{created_spec_id}", headers=auth_headers)
        assert get_response.json()["status"] == "Ready"
    
    @pytest.mark.parametrize("status", VALID_STATUSES)
    def test_all_valid_statuses_accepted(self, auth_headers, status):
        """POST /api/specs/{id}/status - All 6 valid statuses are accepted"""
        # Create a spec for this test
        spec_data = {
            "title": f"TEST_Status_{status[:8]}_{uuid.uuid4().hex[:6]}",
            "spec_type": "Software Feature",
            "raw_idea": f"Testing {status} status",
        }
        create_response = requests.post(f"{BASE_URL}/api/specs", json=spec_data, headers=auth_headers)
        assert create_response.status_code == 201
        spec_id = create_response.json()["id"]
        
        # Change status
        response = requests.post(
            f"{BASE_URL}/api/specs/{spec_id}/status",
            json={"status": status},
            headers=auth_headers
        )
        assert response.status_code == 200, f"Status '{status}' should be valid: {response.text}"
        assert response.json()["status"] == status
        
        # Cleanup
        requests.delete(f"{BASE_URL}/api/specs/{spec_id}", headers=auth_headers)
    
    def test_invalid_status_rejected(self, auth_headers, created_spec_id):
        """POST /api/specs/{id}/status - Invalid status returns 400"""
        response = requests.post(
            f"{BASE_URL}/api/specs/{created_spec_id}/status",
            json={"status": "InvalidStatus"},
            headers=auth_headers
        )
        assert response.status_code == 400
        assert "Invalid status" in response.json().get("detail", "")


class TestSpecVersions:
    """Test spec version history"""
    
    def test_list_versions_empty_for_new_spec(self, auth_headers, created_spec_id):
        """GET /api/specs/{id}/versions - Returns empty for new spec (no generation yet)"""
        response = requests.get(f"{BASE_URL}/api/specs/{created_spec_id}/versions", headers=auth_headers)
        assert response.status_code == 200
        
        data = response.json()
        assert "spec_id" in data
        assert "versions" in data
        assert "total_versions" in data
        assert data["spec_id"] == created_spec_id
        assert isinstance(data["versions"], list)
        assert data["total_versions"] == 0  # No generation yet
    
    def test_versions_for_nonexistent_spec_returns_404(self, auth_headers):
        """GET /api/specs/{id}/versions - Returns 404 for non-existent spec"""
        fake_id = str(uuid.uuid4())
        response = requests.get(f"{BASE_URL}/api/specs/{fake_id}/versions", headers=auth_headers)
        assert response.status_code == 404


class TestSpecFiltering:
    """Test spec list filtering"""
    
    def test_filter_by_spec_type(self, auth_headers):
        """GET /api/specs?spec_type=X - Filter by spec type"""
        # Create a spec with specific type
        spec_data = {
            "title": f"TEST_FilterType_{uuid.uuid4().hex[:8]}",
            "spec_type": "GPT / AI Agent",
            "raw_idea": "An AI agent for testing",
        }
        create_response = requests.post(f"{BASE_URL}/api/specs", json=spec_data, headers=auth_headers)
        assert create_response.status_code == 201
        spec_id = create_response.json()["id"]
        
        # Filter by type
        response = requests.get(f"{BASE_URL}/api/specs", params={"spec_type": "GPT / AI Agent"}, headers=auth_headers)
        assert response.status_code == 200
        
        data = response.json()
        # All returned specs should have the filtered type
        for spec in data["specs"]:
            assert spec["spec_type"] == "GPT / AI Agent"
        
        # Cleanup
        requests.delete(f"{BASE_URL}/api/specs/{spec_id}", headers=auth_headers)
    
    def test_filter_by_status(self, auth_headers):
        """GET /api/specs?status=X - Filter by status"""
        response = requests.get(f"{BASE_URL}/api/specs", params={"status": "Draft"}, headers=auth_headers)
        assert response.status_code == 200
        
        data = response.json()
        for spec in data["specs"]:
            assert spec["status"] == "Draft"
    
    def test_filter_by_priority(self, auth_headers):
        """GET /api/specs?priority=X - Filter by priority"""
        response = requests.get(f"{BASE_URL}/api/specs", params={"priority": "P1"}, headers=auth_headers)
        assert response.status_code == 200
        
        data = response.json()
        for spec in data["specs"]:
            assert spec["priority"] == "P1"


class TestRegressionPageOps:
    """Regression tests for Page Ops (existing functionality)"""
    
    def test_dashboard_stats(self, auth_headers):
        """GET /api/stats - Dashboard stats still work"""
        response = requests.get(f"{BASE_URL}/api/stats", headers=auth_headers)
        assert response.status_code == 200
        
        data = response.json()
        assert "total_pages" in data
        assert data["total_pages"] == 25  # From iteration_9
    
    def test_exemplars_endpoint(self, auth_headers):
        """GET /api/exemplars - Returns 4 exemplars"""
        response = requests.get(f"{BASE_URL}/api/exemplars", headers=auth_headers)
        assert response.status_code == 200
        
        data = response.json()
        assert len(data) == 4
    
    def test_house_templates_endpoint(self, auth_headers):
        """GET /api/house-templates - Returns 3 templates"""
        response = requests.get(f"{BASE_URL}/api/house-templates", headers=auth_headers)
        assert response.status_code == 200
        
        data = response.json()
        assert len(data) == 3
    
    def test_pages_list(self, auth_headers):
        """GET /api/pages - Returns pages list"""
        response = requests.get(f"{BASE_URL}/api/pages", headers=auth_headers)
        assert response.status_code == 200
        
        data = response.json()
        assert "pages" in data
        assert "total" in data


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
