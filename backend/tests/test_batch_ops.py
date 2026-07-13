"""
Batch Operations API Tests
Tests for POST /api/batch-jobs, GET /api/batch-jobs, GET /api/batch-jobs/{id},
POST /api/batch-jobs/{id}/cancel, GET /api/batch-jobs/{id}/download
"""
import pytest
import requests
import os
import time

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# ================== FIXTURES ==================

@pytest.fixture(scope="module")
def auth_token():
    """Get authentication token"""
    response = requests.post(f"{BASE_URL}/api/auth/login", json={
        "password": "TSFounder!Vault2026#Secure"
    })
    if response.status_code == 200:
        return response.json().get("access_token")
    pytest.skip("Authentication failed - skipping authenticated tests")

@pytest.fixture(scope="module")
def auth_headers(auth_token):
    """Headers with auth token"""
    return {
        "Authorization": f"Bearer {auth_token}",
        "Content-Type": "application/json"
    }

@pytest.fixture(scope="module")
def sample_page_ids(auth_headers):
    """Get some page IDs for testing"""
    response = requests.get(f"{BASE_URL}/api/pages", headers=auth_headers)
    assert response.status_code == 200
    pages = response.json().get("pages", [])
    # Get first 3 pages for testing
    return [p["id"] for p in pages[:3]]


# ================== AUTH TESTS ==================

class TestBatchAuth:
    """Batch endpoints require authentication"""
    
    def test_list_batch_jobs_requires_auth(self):
        """GET /api/batch-jobs without auth returns 401"""
        response = requests.get(f"{BASE_URL}/api/batch-jobs")
        assert response.status_code == 401
        print("✓ List batch jobs requires auth")
    
    def test_create_batch_job_requires_auth(self):
        """POST /api/batch-jobs without auth returns 401"""
        response = requests.post(f"{BASE_URL}/api/batch-jobs", json={
            "type": "generate",
            "page_ids": ["test-id"]
        })
        assert response.status_code == 401
        print("✓ Create batch job requires auth")


# ================== VALIDATION TESTS ==================

class TestBatchValidation:
    """Batch job validation tests"""
    
    def test_invalid_batch_type_returns_400(self, auth_headers):
        """Invalid batch type returns 400 error"""
        response = requests.post(f"{BASE_URL}/api/batch-jobs", headers=auth_headers, json={
            "type": "invalid_type",
            "page_ids": ["test-id"]
        })
        assert response.status_code == 400
        data = response.json()
        assert "detail" in data
        assert "Invalid type" in data["detail"] or "invalid" in data["detail"].lower()
        print("✓ Invalid batch type returns 400")
    
    def test_empty_page_ids_returns_400(self, auth_headers):
        """Empty page_ids returns 400 error"""
        response = requests.post(f"{BASE_URL}/api/batch-jobs", headers=auth_headers, json={
            "type": "generate",
            "page_ids": []
        })
        assert response.status_code == 400
        data = response.json()
        assert "detail" in data
        assert "No pages" in data["detail"] or "page" in data["detail"].lower()
        print("✓ Empty page_ids returns 400")
    
    def test_valid_batch_types(self, auth_headers, sample_page_ids):
        """All valid batch types are accepted"""
        valid_types = ["generate", "score", "tighten", "status_change", "export"]
        for batch_type in valid_types:
            params = {}
            if batch_type == "status_change":
                params = {"target_status": "Deferred"}
            
            response = requests.post(f"{BASE_URL}/api/batch-jobs", headers=auth_headers, json={
                "type": batch_type,
                "page_ids": [sample_page_ids[0]],  # Use just one page
                "params": params
            })
            # Should be 201 (created) not 400 (validation error)
            assert response.status_code == 201, f"Type '{batch_type}' failed: {response.text}"
            print(f"✓ Batch type '{batch_type}' accepted")


# ================== CRUD TESTS ==================

class TestBatchCRUD:
    """Batch job CRUD operations"""
    
    def test_create_batch_job(self, auth_headers, sample_page_ids):
        """POST /api/batch-jobs creates a batch job"""
        response = requests.post(f"{BASE_URL}/api/batch-jobs", headers=auth_headers, json={
            "type": "export",
            "page_ids": sample_page_ids[:2],
            "params": {}
        })
        assert response.status_code == 201
        data = response.json()
        
        # Verify response structure
        assert "job" in data
        job = data["job"]
        assert "id" in job
        assert job["type"] == "export"
        assert job["state"] in ["queued", "running", "completed"]
        assert job["total_items"] == 2
        assert "created_at" in job
        assert "updated_at" in job
        print(f"✓ Created batch job: {job['id']}")
        return job["id"]
    
    def test_list_batch_jobs(self, auth_headers):
        """GET /api/batch-jobs returns list of all batch jobs"""
        response = requests.get(f"{BASE_URL}/api/batch-jobs", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        
        # Verify response structure
        assert "jobs" in data
        assert "total" in data
        assert isinstance(data["jobs"], list)
        assert data["total"] >= 0
        
        if data["jobs"]:
            job = data["jobs"][0]
            assert "id" in job
            assert "type" in job
            assert "state" in job
            assert "total_items" in job
        print(f"✓ Listed {data['total']} batch jobs")
    
    def test_get_batch_job_by_id(self, auth_headers, sample_page_ids):
        """GET /api/batch-jobs/{id} returns job with enriched items"""
        # First create a job
        create_response = requests.post(f"{BASE_URL}/api/batch-jobs", headers=auth_headers, json={
            "type": "export",
            "page_ids": sample_page_ids[:1],
            "params": {}
        })
        assert create_response.status_code == 201
        job_id = create_response.json()["job"]["id"]
        
        # Wait a moment for processing
        time.sleep(1)
        
        # Get the job
        response = requests.get(f"{BASE_URL}/api/batch-jobs/{job_id}", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        
        # Verify response structure
        assert "job" in data
        assert "items" in data
        assert data["job"]["id"] == job_id
        
        # Verify items are enriched with page_name
        if data["items"]:
            item = data["items"][0]
            assert "page_id" in item
            assert "page_name" in item  # Enriched field
            assert "state" in item
        print(f"✓ Got batch job {job_id} with enriched items")
    
    def test_get_nonexistent_batch_job_returns_404(self, auth_headers):
        """GET /api/batch-jobs/{id} with invalid ID returns 404"""
        response = requests.get(f"{BASE_URL}/api/batch-jobs/nonexistent-id-12345", headers=auth_headers)
        assert response.status_code == 404
        print("✓ Nonexistent batch job returns 404")


# ================== CANCEL TESTS ==================

class TestBatchCancel:
    """Batch job cancellation tests"""
    
    def test_cancel_nonexistent_job_returns_404(self, auth_headers):
        """POST /api/batch-jobs/{id}/cancel with invalid ID returns 404"""
        response = requests.post(f"{BASE_URL}/api/batch-jobs/nonexistent-id-12345/cancel", 
                                headers=auth_headers, json={})
        assert response.status_code == 404
        print("✓ Cancel nonexistent job returns 404")
    
    def test_cancel_completed_job_returns_400(self, auth_headers, sample_page_ids):
        """Cannot cancel a completed job"""
        # Create an export job (completes quickly)
        create_response = requests.post(f"{BASE_URL}/api/batch-jobs", headers=auth_headers, json={
            "type": "export",
            "page_ids": sample_page_ids[:1],
            "params": {}
        })
        assert create_response.status_code == 201
        job_id = create_response.json()["job"]["id"]
        
        # Wait for completion
        time.sleep(2)
        
        # Try to cancel
        response = requests.post(f"{BASE_URL}/api/batch-jobs/{job_id}/cancel", 
                                headers=auth_headers, json={})
        # Should be 400 because job is already completed
        assert response.status_code == 400
        print("✓ Cannot cancel completed job (returns 400)")


# ================== STATUS CHANGE TESTS ==================

class TestBatchStatusChange:
    """Batch status_change type tests"""
    
    def test_status_change_to_approved(self, auth_headers, sample_page_ids):
        """status_change batch with target_status='Approved' changes page status"""
        # Get a page to test with
        page_id = sample_page_ids[0]
        
        # Get original status
        page_response = requests.get(f"{BASE_URL}/api/pages/{page_id}", headers=auth_headers)
        assert page_response.status_code == 200
        original_status = page_response.json().get("status")
        
        # Create status_change batch
        response = requests.post(f"{BASE_URL}/api/batch-jobs", headers=auth_headers, json={
            "type": "status_change",
            "page_ids": [page_id],
            "params": {"target_status": "Approved"}
        })
        assert response.status_code == 201
        job_id = response.json()["job"]["id"]
        
        # Wait for processing
        time.sleep(2)
        
        # Verify page status changed
        page_response = requests.get(f"{BASE_URL}/api/pages/{page_id}", headers=auth_headers)
        assert page_response.status_code == 200
        new_status = page_response.json().get("status")
        assert new_status == "Approved", f"Expected 'Approved', got '{new_status}'"
        print(f"✓ Status changed from '{original_status}' to 'Approved'")
        
        # Restore original status if different
        if original_status and original_status != "Approved":
            requests.put(f"{BASE_URL}/api/pages/{page_id}", headers=auth_headers, json={
                "status": original_status
            })
    
    def test_status_change_to_deferred(self, auth_headers, sample_page_ids):
        """status_change batch with target_status='Deferred' works"""
        page_id = sample_page_ids[1] if len(sample_page_ids) > 1 else sample_page_ids[0]
        
        # Get original status
        page_response = requests.get(f"{BASE_URL}/api/pages/{page_id}", headers=auth_headers)
        original_status = page_response.json().get("status")
        
        # Create status_change batch
        response = requests.post(f"{BASE_URL}/api/batch-jobs", headers=auth_headers, json={
            "type": "status_change",
            "page_ids": [page_id],
            "params": {"target_status": "Deferred"}
        })
        assert response.status_code == 201
        
        # Wait for processing
        time.sleep(2)
        
        # Verify page status changed
        page_response = requests.get(f"{BASE_URL}/api/pages/{page_id}", headers=auth_headers)
        new_status = page_response.json().get("status")
        assert new_status == "Deferred", f"Expected 'Deferred', got '{new_status}'"
        print(f"✓ Status changed to 'Deferred'")
        
        # Restore original status
        if original_status and original_status != "Deferred":
            requests.put(f"{BASE_URL}/api/pages/{page_id}", headers=auth_headers, json={
                "status": original_status
            })


# ================== EXPORT TESTS ==================

class TestBatchExport:
    """Batch export type tests"""
    
    def test_export_creates_downloadable_zip(self, auth_headers, sample_page_ids):
        """export type creates a job that can be downloaded as ZIP"""
        # Create export job
        response = requests.post(f"{BASE_URL}/api/batch-jobs", headers=auth_headers, json={
            "type": "export",
            "page_ids": sample_page_ids[:2],
            "params": {}
        })
        assert response.status_code == 201
        job_id = response.json()["job"]["id"]
        
        # Wait for completion
        time.sleep(2)
        
        # Download the ZIP
        download_response = requests.get(f"{BASE_URL}/api/batch-jobs/{job_id}/download", 
                                        headers=auth_headers)
        assert download_response.status_code == 200
        assert download_response.headers.get("content-type") == "application/zip"
        assert "attachment" in download_response.headers.get("content-disposition", "")
        assert len(download_response.content) > 0
        print(f"✓ Export job {job_id} downloaded as ZIP ({len(download_response.content)} bytes)")
    
    def test_download_non_export_job_returns_400(self, auth_headers, sample_page_ids):
        """Cannot download a non-export job"""
        # Create a status_change job (not export)
        response = requests.post(f"{BASE_URL}/api/batch-jobs", headers=auth_headers, json={
            "type": "status_change",
            "page_ids": sample_page_ids[:1],
            "params": {"target_status": "Deferred"}
        })
        assert response.status_code == 201
        job_id = response.json()["job"]["id"]
        
        # Try to download
        download_response = requests.get(f"{BASE_URL}/api/batch-jobs/{job_id}/download", 
                                        headers=auth_headers)
        assert download_response.status_code == 400
        print("✓ Cannot download non-export job (returns 400)")


# ================== REGRESSION TESTS ==================

class TestRegression:
    """Regression tests for existing modules"""
    
    def test_dashboard_stats(self, auth_headers):
        """Dashboard stats endpoint still works"""
        response = requests.get(f"{BASE_URL}/api/stats", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert "total_pages" in data
        assert data["total_pages"] == 25
        print(f"✓ Dashboard stats: {data['total_pages']} total pages")
    
    def test_spec_library(self, auth_headers):
        """Spec library endpoint still works"""
        response = requests.get(f"{BASE_URL}/api/specs", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert "specs" in data
        assert "total" in data
        print(f"✓ Spec library: {data['total']} specs")
    
    def test_exemplars(self, auth_headers):
        """Exemplars endpoint still works"""
        response = requests.get(f"{BASE_URL}/api/exemplars", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert "exemplars" in data
        exemplar_count = len(data["exemplars"])
        assert exemplar_count == 4, f"Expected 4 exemplars, got {exemplar_count}"
        print(f"✓ Exemplars: {exemplar_count} exemplars")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
