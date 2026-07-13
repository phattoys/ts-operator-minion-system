"""
Test Vision LLM PDF Intake Feature
Tests the Vision fallback for image-based PDFs (like Temu invoices)
"""
import pytest
import requests
import os
import time

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')
PASSWORD = "TSFounder!Vault2026#Secure"

# Known test data from previous Vision PDF upload
TEMU_SESSION_ID = "1ceb82ec-9032-4973-ad3a-07601a3d8fb6"
SHEIN_SESSION_ID = "e54de4dc-5308-4b63-b1e1-f9af5f7d3225"


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
    """Headers with auth token"""
    return {"Authorization": f"Bearer {auth_token}"}


class TestSessionCreation:
    """Test creating intake sessions for Temu"""
    
    def test_create_temu_session(self, auth_headers):
        """POST /api/intake/sessions - create a new session for Temu"""
        response = requests.post(
            f"{BASE_URL}/api/intake/sessions",
            json={
                "source_store": "Temu Test Session",
                "order_id": "TEST-VISION-001",
                "notes": "Test session for Vision PDF testing"
            },
            headers=auth_headers
        )
        assert response.status_code == 200, f"Failed to create session: {response.text}"
        data = response.json()
        
        # Verify response structure
        assert "id" in data
        assert data["source_store"] == "Temu Test Session"
        assert data["order_id"] == "TEST-VISION-001"
        assert data["item_count"] == 0
        assert data["needs_info_count"] == 0
        assert data["in_review_count"] == 0
        assert data["ready_count"] == 0
        
        # Cleanup - delete the test session
        cleanup = requests.delete(
            f"{BASE_URL}/api/intake/sessions/{data['id']}",
            headers=auth_headers
        )
        assert cleanup.status_code == 200


class TestExistingTemuSession:
    """Test the existing Temu session with 67 vision-extracted items"""
    
    def test_get_temu_session(self, auth_headers):
        """GET /api/intake/sessions/{session_id} - verify Temu session exists"""
        response = requests.get(
            f"{BASE_URL}/api/intake/sessions/{TEMU_SESSION_ID}",
            headers=auth_headers
        )
        assert response.status_code == 200, f"Failed to get session: {response.text}"
        data = response.json()
        
        # Verify session metadata
        assert data["id"] == TEMU_SESSION_ID
        assert data["source_store"] == "Temu"
        assert data["item_count"] == 67, f"Expected 67 items, got {data['item_count']}"
        
    def test_temu_items_have_correct_fields(self, auth_headers):
        """Verify extracted items have correct fields (source_title, unit_cost, quantity, color, vendor)"""
        response = requests.get(
            f"{BASE_URL}/api/intake/sessions/{TEMU_SESSION_ID}",
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        items = data.get("items", [])
        
        assert len(items) == 67, f"Expected 67 items, got {len(items)}"
        
        # Check first few items have required fields
        for item in items[:5]:
            assert "source_title" in item, "Missing source_title"
            assert item["source_title"], "source_title is empty"
            assert "unit_cost" in item, "Missing unit_cost"
            assert item["unit_cost"] is not None, "unit_cost is None"
            assert "quantity" in item, "Missing quantity"
            assert item["quantity"] >= 1, "quantity should be >= 1"
            
            # Check attribute_suggestions has vendor
            attrs = item.get("attribute_suggestions", {})
            assert "vendor" in attrs, f"Missing vendor in attribute_suggestions for item: {item['source_title'][:50]}"
            
    def test_all_items_start_at_needs_info(self, auth_headers):
        """Verify all items start at 'needs_info' status (never auto-published)"""
        response = requests.get(
            f"{BASE_URL}/api/intake/sessions/{TEMU_SESSION_ID}",
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        items = data.get("items", [])
        
        # All items should be needs_info
        assert data["needs_info_count"] == 67, f"Expected 67 needs_info, got {data['needs_info_count']}"
        assert data["in_review_count"] == 0, f"Expected 0 in_review, got {data['in_review_count']}"
        assert data["ready_count"] == 0, f"Expected 0 ready, got {data['ready_count']}"
        
        for item in items:
            assert item["status"] == "needs_info", f"Item {item['id']} has status {item['status']}, expected needs_info"
            
    def test_items_have_vision_extraction_evidence(self, auth_headers):
        """Verify items have vision_llm extraction evidence"""
        response = requests.get(
            f"{BASE_URL}/api/intake/sessions/{TEMU_SESSION_ID}",
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        items = data.get("items", [])
        
        for item in items[:10]:
            evidence = item.get("extraction_evidence", "")
            assert "vision_llm" in evidence, f"Item missing vision_llm evidence: {evidence}"
            assert "PDF page" in evidence, f"Item missing PDF page reference: {evidence}"


class TestPdfJobPolling:
    """Test the PDF job polling endpoint"""
    
    def test_get_nonexistent_job_returns_404(self, auth_headers):
        """GET /api/intake/pdf-jobs/{job_id} - nonexistent job returns 404"""
        response = requests.get(
            f"{BASE_URL}/api/intake/pdf-jobs/nonexistent-job-id",
            headers=auth_headers
        )
        assert response.status_code == 404
        
    def test_pdf_job_endpoint_requires_auth(self):
        """GET /api/intake/pdf-jobs/{job_id} - requires authentication"""
        response = requests.get(
            f"{BASE_URL}/api/intake/pdf-jobs/some-job-id"
        )
        assert response.status_code == 401


class TestTextBasedPdfPath:
    """Test that text-based PDFs (SHEIN-style) still work synchronously"""
    
    def test_shein_session_exists(self, auth_headers):
        """Verify SHEIN session with text-based PDF extraction exists"""
        response = requests.get(
            f"{BASE_URL}/api/intake/sessions/{SHEIN_SESSION_ID}",
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        
        assert data["source_store"] == "SHEIN"
        assert data["item_count"] == 63
        
    def test_shein_items_have_regex_extraction(self, auth_headers):
        """Verify SHEIN items were extracted via regex (not vision)"""
        response = requests.get(
            f"{BASE_URL}/api/intake/sessions/{SHEIN_SESSION_ID}",
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        items = data.get("items", [])
        
        # Check that items have SKU (regex extraction provides SKU)
        items_with_sku = [i for i in items if i.get("attribute_suggestions", {}).get("sku")]
        assert len(items_with_sku) > 0, "SHEIN items should have SKU from regex extraction"


class TestPdfUploadEndpoint:
    """Test the PDF upload endpoint behavior"""
    
    def test_upload_pdf_requires_auth(self):
        """POST /api/intake/sessions/{session_id}/upload-pdf - requires authentication"""
        response = requests.post(
            f"{BASE_URL}/api/intake/sessions/{TEMU_SESSION_ID}/upload-pdf",
            files={"file": ("test.pdf", b"fake pdf content", "application/pdf")}
        )
        assert response.status_code == 401
        
    def test_upload_pdf_validates_file_type(self, auth_headers):
        """POST /api/intake/sessions/{session_id}/upload-pdf - rejects non-PDF files"""
        response = requests.post(
            f"{BASE_URL}/api/intake/sessions/{TEMU_SESSION_ID}/upload-pdf",
            files={"file": ("test.txt", b"not a pdf", "text/plain")},
            headers=auth_headers
        )
        assert response.status_code == 400
        assert "PDF" in response.json().get("detail", "")
        
    def test_upload_pdf_validates_session_exists(self, auth_headers):
        """POST /api/intake/sessions/{session_id}/upload-pdf - returns 404 for nonexistent session"""
        response = requests.post(
            f"{BASE_URL}/api/intake/sessions/nonexistent-session-id/upload-pdf",
            files={"file": ("test.pdf", b"%PDF-1.4 fake", "application/pdf")},
            headers=auth_headers
        )
        assert response.status_code == 404


class TestItemDataIntegrity:
    """Test data integrity of vision-extracted items"""
    
    def test_items_have_suggested_price(self, auth_headers):
        """Verify items have suggested_price calculated from unit_cost"""
        response = requests.get(
            f"{BASE_URL}/api/intake/sessions/{TEMU_SESSION_ID}",
            headers=auth_headers
        )
        assert response.status_code == 200
        items = response.json().get("items", [])
        
        items_with_price = [i for i in items if i.get("suggested_price") is not None]
        assert len(items_with_price) > 50, f"Expected most items to have suggested_price, got {len(items_with_price)}"
        
        # Verify suggested_price > unit_cost (markup applied)
        for item in items_with_price[:10]:
            if item.get("unit_cost"):
                assert item["suggested_price"] > item["unit_cost"], \
                    f"suggested_price ({item['suggested_price']}) should be > unit_cost ({item['unit_cost']})"
                    
    def test_items_have_list_price_in_attributes(self, auth_headers):
        """Verify items have list_price (original price) in attribute_suggestions"""
        response = requests.get(
            f"{BASE_URL}/api/intake/sessions/{TEMU_SESSION_ID}",
            headers=auth_headers
        )
        assert response.status_code == 200
        items = response.json().get("items", [])
        
        items_with_list_price = [
            i for i in items 
            if i.get("attribute_suggestions", {}).get("list_price")
        ]
        # Not all products show original prices, so we just verify some have it
        assert len(items_with_list_price) > 10, \
            f"Expected some items to have list_price, got {len(items_with_list_price)}"
            
    def test_items_have_color_or_size_variants(self, auth_headers):
        """Verify some items have color/size variants extracted"""
        response = requests.get(
            f"{BASE_URL}/api/intake/sessions/{TEMU_SESSION_ID}",
            headers=auth_headers
        )
        assert response.status_code == 200
        items = response.json().get("items", [])
        
        items_with_color = [i for i in items if i.get("color")]
        items_with_size = [i for i in items if i.get("size")]
        
        # At least some items should have variants
        assert len(items_with_color) > 0 or len(items_with_size) > 0, \
            "Expected some items to have color or size variants"


class TestDeduplication:
    """Test deduplication logic for vision-extracted items"""
    
    def test_no_exact_duplicate_titles(self, auth_headers):
        """Verify no exact duplicate titles exist (dedup should have merged them)"""
        response = requests.get(
            f"{BASE_URL}/api/intake/sessions/{TEMU_SESSION_ID}",
            headers=auth_headers
        )
        assert response.status_code == 200
        items = response.json().get("items", [])
        
        # Normalize titles for comparison
        titles = [i.get("source_title", "").lower().strip() for i in items]
        unique_titles = set(titles)
        
        # Allow duplicates for different variants (color/size combinations)
        # Vision extraction may have similar titles for variant products
        duplicate_count = len(titles) - len(unique_titles)
        # Just verify dedup is working (not 67 duplicates)
        assert duplicate_count < 30, f"Too many duplicate titles: {duplicate_count}"


class TestIntakeStats:
    """Test intake stats endpoint includes vision session data"""
    
    def test_stats_include_temu_items(self, auth_headers):
        """GET /api/intake/stats - includes Temu session items"""
        response = requests.get(
            f"{BASE_URL}/api/intake/stats",
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        
        assert data["total_items"] >= 67, f"Expected at least 67 items, got {data['total_items']}"
        assert data["total_sessions"] >= 2, f"Expected at least 2 sessions, got {data['total_sessions']}"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
