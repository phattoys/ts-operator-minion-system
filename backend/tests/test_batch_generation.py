"""
Batch Listing Generation Tests for Product Intake Minion
Tests: generate-all endpoint, single-item generate, confidence scoring, attribute preservation
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')
SHEIN_SESSION_ID = "e54de4dc-5308-4b63-b1e1-f9af5f7d3225"
PASSWORD = "TSFounder!Vault2026#Secure"


@pytest.fixture(scope="module")
def auth_token():
    """Get authentication token"""
    response = requests.post(
        f"{BASE_URL}/api/auth/login",
        json={"password": PASSWORD}
    )
    if response.status_code == 200:
        return response.json().get("access_token")
    pytest.skip("Authentication failed - skipping tests")


@pytest.fixture(scope="module")
def auth_headers(auth_token):
    """Headers with auth token"""
    return {"Authorization": f"Bearer {auth_token}"}


class TestBatchGenerateEndpoint:
    """Tests for POST /api/intake/sessions/{session_id}/generate-all"""
    
    def test_generate_all_returns_correct_structure(self, auth_headers):
        """generate-all returns generated/failed/flagged/total counts plus results array"""
        response = requests.post(
            f"{BASE_URL}/api/intake/sessions/{SHEIN_SESSION_ID}/generate-all",
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        
        # Required fields in response
        assert "generated" in data
        assert "failed" in data
        assert "flagged" in data
        assert "total" in data
        assert "results" in data
        assert "message" in data
        
        # Types
        assert isinstance(data["generated"], int)
        assert isinstance(data["failed"], int)
        assert isinstance(data["flagged"], int)
        assert isinstance(data["total"], int)
        assert isinstance(data["results"], list)
    
    def test_generate_all_skips_items_with_descriptions(self, auth_headers):
        """Items with short_description are skipped (returns 0 generated)"""
        response = requests.post(
            f"{BASE_URL}/api/intake/sessions/{SHEIN_SESSION_ID}/generate-all",
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        
        # All SHEIN items already have descriptions, so should return 0
        assert data["generated"] == 0
        assert data["total"] == 0
        assert data["message"] == "No items need generation"
    
    def test_generate_all_requires_auth(self):
        """generate-all endpoint requires authentication"""
        response = requests.post(
            f"{BASE_URL}/api/intake/sessions/{SHEIN_SESSION_ID}/generate-all"
        )
        assert response.status_code == 401
    
    def test_generate_all_nonexistent_session(self, auth_headers):
        """generate-all returns 404 for nonexistent session"""
        response = requests.post(
            f"{BASE_URL}/api/intake/sessions/nonexistent-session-id/generate-all",
            headers=auth_headers
        )
        assert response.status_code == 404


class TestSingleItemGenerate:
    """Tests for POST /api/intake/items/{item_id}/generate"""
    
    def test_generate_includes_confidence_in_response(self, auth_headers):
        """Single item generate includes generation_confidence in response"""
        # Get first item from SHEIN session
        session_resp = requests.get(
            f"{BASE_URL}/api/intake/sessions/{SHEIN_SESSION_ID}",
            headers=auth_headers
        )
        assert session_resp.status_code == 200
        items = session_resp.json().get("items", [])
        assert len(items) > 0
        
        item_id = items[0]["id"]
        
        # Generate (regenerate) for this item
        response = requests.post(
            f"{BASE_URL}/api/intake/items/{item_id}/generate",
            headers=auth_headers,
            timeout=120
        )
        assert response.status_code == 200
        data = response.json()
        
        # Must have generation_confidence
        assert "generation_confidence" in data
        conf = data["generation_confidence"]
        
        # Confidence structure
        assert "score" in conf
        assert isinstance(conf["score"], (int, float))
        assert 0 <= conf["score"] <= 1
    
    def test_generate_confidence_has_breakdown_fields(self, auth_headers):
        """generation_confidence has title_confidence, category_confidence, description_confidence"""
        session_resp = requests.get(
            f"{BASE_URL}/api/intake/sessions/{SHEIN_SESSION_ID}",
            headers=auth_headers
        )
        items = session_resp.json().get("items", [])
        item_id = items[1]["id"]  # Use second item
        
        response = requests.post(
            f"{BASE_URL}/api/intake/items/{item_id}/generate",
            headers=auth_headers,
            timeout=120
        )
        assert response.status_code == 200
        conf = response.json().get("generation_confidence", {})
        
        # Breakdown fields
        assert "title_confidence" in conf
        assert "category_confidence" in conf
        assert "description_confidence" in conf
        
        # Values should be high/medium/low
        valid_levels = ["high", "medium", "low"]
        assert conf["title_confidence"] in valid_levels
        assert conf["category_confidence"] in valid_levels
        assert conf["description_confidence"] in valid_levels
    
    def test_generate_requires_auth(self):
        """Single item generate requires authentication"""
        response = requests.post(
            f"{BASE_URL}/api/intake/items/some-item-id/generate"
        )
        assert response.status_code == 401
    
    def test_generate_nonexistent_item(self, auth_headers):
        """Generate returns 404 for nonexistent item"""
        response = requests.post(
            f"{BASE_URL}/api/intake/items/nonexistent-item-id/generate",
            headers=auth_headers
        )
        assert response.status_code == 404


class TestItemStatusTransition:
    """Tests for status transitions after generation"""
    
    def test_all_shein_items_in_review_status(self, auth_headers):
        """All 63 SHEIN items are in 'in_review' status after batch generation"""
        response = requests.get(
            f"{BASE_URL}/api/intake/sessions/{SHEIN_SESSION_ID}",
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        
        # Session counts
        assert data["in_review_count"] == 63
        assert data["needs_info_count"] == 0
        assert data["ready_count"] == 0
        
        # All items should be in_review
        items = data.get("items", [])
        assert len(items) == 63
        for item in items:
            assert item["status"] == "in_review", f"Item {item['id']} has status {item['status']}, expected in_review"
    
    def test_items_not_auto_published_to_ready(self, auth_headers):
        """Items move to 'in_review' not 'ready' after generation"""
        response = requests.get(
            f"{BASE_URL}/api/intake/sessions/{SHEIN_SESSION_ID}",
            headers=auth_headers
        )
        data = response.json()
        
        # No items should be in 'ready' status
        assert data["ready_count"] == 0
        
        items = data.get("items", [])
        ready_items = [i for i in items if i["status"] == "ready"]
        assert len(ready_items) == 0, "Items should not auto-publish to 'ready' status"


class TestAttributePreservation:
    """Tests for attribute_suggestions preservation"""
    
    def test_preserved_fields_in_attribute_suggestions(self, auth_headers):
        """attribute_suggestions preserves sku, vendor, list_price alongside LLM-generated attrs"""
        response = requests.get(
            f"{BASE_URL}/api/intake/sessions/{SHEIN_SESSION_ID}",
            headers=auth_headers
        )
        items = response.json().get("items", [])
        
        for item in items[:10]:  # Check first 10 items
            attrs = item.get("attribute_suggestions", {})
            
            # Preserved fields from PDF extraction
            assert "sku" in attrs, f"Item {item['id']} missing sku in attribute_suggestions"
            assert "vendor" in attrs, f"Item {item['id']} missing vendor in attribute_suggestions"
            assert "list_price" in attrs, f"Item {item['id']} missing list_price in attribute_suggestions"
            
            # Vendor should be SHEIN
            assert attrs["vendor"] == "SHEIN"
            
            # SKU should be SHEIN format (2 letters + digits)
            assert len(attrs["sku"]) > 5
    
    def test_llm_generated_attributes_present(self, auth_headers):
        """LLM-generated attributes (material, color, size, style, type) present"""
        response = requests.get(
            f"{BASE_URL}/api/intake/sessions/{SHEIN_SESSION_ID}",
            headers=auth_headers
        )
        items = response.json().get("items", [])
        
        # Check that at least some items have LLM-generated attributes
        items_with_material = [i for i in items if i.get("attribute_suggestions", {}).get("material")]
        items_with_type = [i for i in items if i.get("attribute_suggestions", {}).get("type")]
        
        assert len(items_with_material) > 30, "Most items should have material attribute"
        assert len(items_with_type) > 30, "Most items should have type attribute"


class TestDuplicateFlagsPreservation:
    """Tests for duplicate_flags not being overwritten"""
    
    def test_duplicate_flags_preserved_after_generation(self, auth_headers):
        """duplicate_flags are NOT overwritten by generation"""
        response = requests.get(
            f"{BASE_URL}/api/intake/sessions/{SHEIN_SESSION_ID}",
            headers=auth_headers
        )
        items = response.json().get("items", [])
        
        # Find items with duplicate_flags
        items_with_flags = [i for i in items if i.get("duplicate_flags") and len(i["duplicate_flags"]) > 0]
        
        # There should be some items with duplicate flags (from previous duplicate check)
        assert len(items_with_flags) > 0, "Expected some items to have duplicate_flags"
        
        # Verify flag structure
        for item in items_with_flags[:5]:
            for flag in item["duplicate_flags"]:
                assert "type" in flag
                assert "match_title" in flag
                assert "match_id" in flag


class TestGenerationConfidenceField:
    """Tests for generation_confidence field structure"""
    
    def test_all_items_have_generation_confidence(self, auth_headers):
        """All generated items have generation_confidence field"""
        response = requests.get(
            f"{BASE_URL}/api/intake/sessions/{SHEIN_SESSION_ID}",
            headers=auth_headers
        )
        items = response.json().get("items", [])
        
        for item in items:
            assert "generation_confidence" in item, f"Item {item['id']} missing generation_confidence"
            conf = item["generation_confidence"]
            assert "score" in conf, f"Item {item['id']} missing score in generation_confidence"
    
    def test_confidence_score_range(self, auth_headers):
        """Confidence scores are between 0 and 1"""
        response = requests.get(
            f"{BASE_URL}/api/intake/sessions/{SHEIN_SESSION_ID}",
            headers=auth_headers
        )
        items = response.json().get("items", [])
        
        for item in items:
            score = item.get("generation_confidence", {}).get("score", 0)
            assert 0 <= score <= 1, f"Item {item['id']} has invalid confidence score: {score}"
    
    def test_confidence_breakdown_fields(self, auth_headers):
        """generation_confidence has title_confidence, category_confidence, description_confidence"""
        response = requests.get(
            f"{BASE_URL}/api/intake/sessions/{SHEIN_SESSION_ID}",
            headers=auth_headers
        )
        items = response.json().get("items", [])
        
        for item in items[:10]:
            conf = item.get("generation_confidence", {})
            assert "title_confidence" in conf
            assert "category_confidence" in conf
            assert "description_confidence" in conf


class TestSourceDataPreservation:
    """Tests for source data preservation"""
    
    def test_source_title_preserved(self, auth_headers):
        """Source title (raw) is preserved alongside clean title"""
        response = requests.get(
            f"{BASE_URL}/api/intake/sessions/{SHEIN_SESSION_ID}",
            headers=auth_headers
        )
        items = response.json().get("items", [])
        
        for item in items[:10]:
            # Both source_title and clean_title should exist
            assert "source_title" in item
            assert "clean_title" in item
            
            # Source title should be the raw SHEIN title
            assert len(item["source_title"]) > 10, f"Item {item['id']} has empty source_title"
            
            # Clean title should be different (cleaned up)
            assert item["clean_title"] != item["source_title"], f"Item {item['id']} clean_title same as source_title"
    
    def test_all_items_have_clean_title_and_description(self, auth_headers):
        """All 63 items have clean_title and short_description after batch generation"""
        response = requests.get(
            f"{BASE_URL}/api/intake/sessions/{SHEIN_SESSION_ID}",
            headers=auth_headers
        )
        items = response.json().get("items", [])
        
        assert len(items) == 63
        
        for item in items:
            assert item.get("clean_title"), f"Item {item['id']} missing clean_title"
            assert item.get("short_description"), f"Item {item['id']} missing short_description"


class TestSessionEndpointWithConfidence:
    """Tests for GET /api/intake/sessions/{session_id} returning confidence"""
    
    def test_session_items_include_generation_confidence(self, auth_headers):
        """GET session returns items with generation_confidence field"""
        response = requests.get(
            f"{BASE_URL}/api/intake/sessions/{SHEIN_SESSION_ID}",
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        
        items = data.get("items", [])
        assert len(items) > 0
        
        # All items should have generation_confidence
        for item in items:
            assert "generation_confidence" in item


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
