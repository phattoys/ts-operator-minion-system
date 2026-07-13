"""
Test Bulk Status Actions for Product Intake
Tests: set_status, set_category, add_tags bulk actions
Validation: items with missing fields or 3+ duplicate flags are skipped when marking ready
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')
SESSION_ID = "e54de4dc-5308-4b63-b1e1-f9af5f7d3225"  # SHEIN session with 63 items


@pytest.fixture(scope="module")
def auth_token():
    """Get authentication token"""
    response = requests.post(
        f"{BASE_URL}/api/auth/login",
        json={"password": "TSFounder!Vault2026#Secure"}
    )
    assert response.status_code == 200, f"Login failed: {response.text}"
    return response.json()["access_token"]


@pytest.fixture(scope="module")
def auth_headers(auth_token):
    """Headers with auth token"""
    return {"Authorization": f"Bearer {auth_token}", "Content-Type": "application/json"}


@pytest.fixture(scope="module")
def session_items(auth_headers):
    """Get all items from the SHEIN session"""
    response = requests.get(f"{BASE_URL}/api/intake/sessions/{SESSION_ID}", headers=auth_headers)
    assert response.status_code == 200, f"Failed to get session: {response.text}"
    return response.json().get("items", [])


class TestBulkActionEndpoint:
    """Test POST /api/intake/sessions/{session_id}/bulk-action endpoint"""
    
    def test_bulk_action_requires_auth(self):
        """Bulk action requires authentication"""
        response = requests.post(
            f"{BASE_URL}/api/intake/sessions/{SESSION_ID}/bulk-action",
            json={"item_ids": ["test"], "action": "set_status", "value": "in_review"}
        )
        assert response.status_code == 401, f"Expected 401, got {response.status_code}"
    
    def test_bulk_action_404_for_nonexistent_session(self, auth_headers):
        """Bulk action returns 404 for nonexistent session"""
        response = requests.post(
            f"{BASE_URL}/api/intake/sessions/nonexistent-session-id/bulk-action",
            headers=auth_headers,
            json={"item_ids": ["test"], "action": "set_status", "value": "in_review"}
        )
        assert response.status_code == 404
    
    def test_bulk_action_rejects_empty_item_ids(self, auth_headers):
        """Bulk action rejects empty item_ids list"""
        response = requests.post(
            f"{BASE_URL}/api/intake/sessions/{SESSION_ID}/bulk-action",
            headers=auth_headers,
            json={"item_ids": [], "action": "set_status", "value": "in_review"}
        )
        assert response.status_code == 400
        assert "No items selected" in response.json().get("detail", "")
    
    def test_bulk_action_rejects_invalid_action(self, auth_headers, session_items):
        """Bulk action rejects invalid action type"""
        item_ids = [session_items[0]["id"]] if session_items else ["test"]
        response = requests.post(
            f"{BASE_URL}/api/intake/sessions/{SESSION_ID}/bulk-action",
            headers=auth_headers,
            json={"item_ids": item_ids, "action": "invalid_action", "value": "test"}
        )
        assert response.status_code == 400
        assert "Invalid action" in response.json().get("detail", "")


class TestBulkSetStatus:
    """Test bulk set_status action"""
    
    def test_bulk_set_status_in_review(self, auth_headers, session_items):
        """Bulk set_status to in_review updates selected items"""
        # Get 3 ready items to test
        ready_items = [i for i in session_items if i["status"] == "ready"][:3]
        if len(ready_items) < 3:
            pytest.skip("Not enough ready items to test")
        
        item_ids = [i["id"] for i in ready_items]
        response = requests.post(
            f"{BASE_URL}/api/intake/sessions/{SESSION_ID}/bulk-action",
            headers=auth_headers,
            json={"item_ids": item_ids, "action": "set_status", "value": "in_review"}
        )
        assert response.status_code == 200
        data = response.json()
        
        # Verify response structure
        assert "action" in data
        assert "value" in data
        assert "updated" in data
        assert "skipped" in data
        assert "skipped_items" in data
        assert "total_selected" in data
        
        assert data["action"] == "set_status"
        assert data["value"] == "in_review"
        assert data["updated"] == 3
        assert data["skipped"] == 0
        assert data["total_selected"] == 3
        
        # Verify items were actually updated
        for item_id in item_ids:
            item_resp = requests.get(f"{BASE_URL}/api/intake/items/{item_id}", headers=auth_headers)
            assert item_resp.status_code == 200
            assert item_resp.json()["status"] == "in_review"
        
        # Restore items to ready status
        for item_id in item_ids:
            requests.put(
                f"{BASE_URL}/api/intake/items/{item_id}",
                headers=auth_headers,
                json={"status": "ready"}
            )
    
    def test_bulk_set_status_needs_info(self, auth_headers, session_items):
        """Bulk set_status to needs_info updates selected items"""
        ready_items = [i for i in session_items if i["status"] == "ready"][:2]
        if len(ready_items) < 2:
            pytest.skip("Not enough ready items to test")
        
        item_ids = [i["id"] for i in ready_items]
        response = requests.post(
            f"{BASE_URL}/api/intake/sessions/{SESSION_ID}/bulk-action",
            headers=auth_headers,
            json={"item_ids": item_ids, "action": "set_status", "value": "needs_info"}
        )
        assert response.status_code == 200
        data = response.json()
        assert data["updated"] == 2
        assert data["skipped"] == 0
        
        # Restore items to ready status
        for item_id in item_ids:
            requests.put(
                f"{BASE_URL}/api/intake/items/{item_id}",
                headers=auth_headers,
                json={"status": "ready"}
            )
    
    def test_bulk_set_status_ready_validates_items(self, auth_headers, session_items):
        """Bulk set_status to ready validates items - skips items with missing fields or 3+ dupes"""
        # Find the White Fishnet item with 3+ duplicate flags
        fishnet_item = None
        for item in session_items:
            if "fishnet" in (item.get("clean_title") or item.get("source_title") or "").lower():
                if len(item.get("duplicate_flags", [])) >= 3:
                    fishnet_item = item
                    break
        
        if not fishnet_item:
            pytest.skip("White Fishnet item with 3+ duplicate flags not found")
        
        # Get a valid ready item to include in the test
        valid_items = [i for i in session_items if i["status"] == "ready"][:1]
        if not valid_items:
            pytest.skip("No valid ready items to test")
        
        # First set both to in_review
        test_ids = [fishnet_item["id"], valid_items[0]["id"]]
        for item_id in test_ids:
            requests.put(
                f"{BASE_URL}/api/intake/items/{item_id}",
                headers=auth_headers,
                json={"status": "in_review"}
            )
        
        # Now try to bulk mark as ready
        response = requests.post(
            f"{BASE_URL}/api/intake/sessions/{SESSION_ID}/bulk-action",
            headers=auth_headers,
            json={"item_ids": test_ids, "action": "set_status", "value": "ready"}
        )
        assert response.status_code == 200
        data = response.json()
        
        # One should be updated (valid item), one should be skipped (fishnet with 3+ dupes)
        assert data["updated"] == 1, f"Expected 1 updated, got {data['updated']}"
        assert data["skipped"] == 1, f"Expected 1 skipped, got {data['skipped']}"
        
        # Verify skipped_items contains the fishnet item with reason
        assert len(data["skipped_items"]) == 1
        skipped = data["skipped_items"][0]
        assert skipped["id"] == fishnet_item["id"]
        assert "unresolved_duplicates" in skipped["reason"]
        
        # Verify the valid item is now ready
        valid_resp = requests.get(f"{BASE_URL}/api/intake/items/{valid_items[0]['id']}", headers=auth_headers)
        assert valid_resp.json()["status"] == "ready"
        
        # Verify the fishnet item is still in_review
        fishnet_resp = requests.get(f"{BASE_URL}/api/intake/items/{fishnet_item['id']}", headers=auth_headers)
        assert fishnet_resp.json()["status"] == "in_review"
    
    def test_bulk_ready_skips_items_without_required_fields(self, auth_headers, session_items):
        """Items without clean_title/short_description/category are skipped when bulk-marking as ready"""
        # Find an item and clear its category to test validation
        test_item = [i for i in session_items if i["status"] == "ready" and i.get("category")][:1]
        if not test_item:
            pytest.skip("No suitable item to test")
        
        test_item = test_item[0]
        original_category = test_item["category"]
        
        # Clear the category
        requests.put(
            f"{BASE_URL}/api/intake/items/{test_item['id']}",
            headers=auth_headers,
            json={"category": "", "status": "in_review"}
        )
        
        # Try to bulk mark as ready
        response = requests.post(
            f"{BASE_URL}/api/intake/sessions/{SESSION_ID}/bulk-action",
            headers=auth_headers,
            json={"item_ids": [test_item["id"]], "action": "set_status", "value": "ready"}
        )
        assert response.status_code == 200
        data = response.json()
        
        # Should be skipped due to missing category
        assert data["updated"] == 0
        assert data["skipped"] == 1
        assert len(data["skipped_items"]) == 1
        assert "missing_fields" in data["skipped_items"][0]["reason"]
        assert "category" in data["skipped_items"][0]["reason"]
        
        # Restore the item
        requests.put(
            f"{BASE_URL}/api/intake/items/{test_item['id']}",
            headers=auth_headers,
            json={"category": original_category, "status": "ready"}
        )


class TestBulkSetCategory:
    """Test bulk set_category action"""
    
    def test_bulk_set_category_updates_items(self, auth_headers, session_items):
        """Bulk set_category updates category on selected items"""
        test_items = session_items[:3]
        if len(test_items) < 3:
            pytest.skip("Not enough items to test")
        
        item_ids = [i["id"] for i in test_items]
        original_categories = {i["id"]: i.get("category", "") for i in test_items}
        
        new_category = "TEST_BULK_CATEGORY"
        response = requests.post(
            f"{BASE_URL}/api/intake/sessions/{SESSION_ID}/bulk-action",
            headers=auth_headers,
            json={"item_ids": item_ids, "action": "set_category", "value": new_category}
        )
        assert response.status_code == 200
        data = response.json()
        
        assert data["action"] == "set_category"
        assert data["value"] == new_category
        assert data["updated"] == 3
        assert data["skipped"] == 0
        
        # Verify items were updated
        for item_id in item_ids:
            item_resp = requests.get(f"{BASE_URL}/api/intake/items/{item_id}", headers=auth_headers)
            assert item_resp.json()["category"] == new_category
        
        # Restore original categories
        for item_id, orig_cat in original_categories.items():
            requests.put(
                f"{BASE_URL}/api/intake/items/{item_id}",
                headers=auth_headers,
                json={"category": orig_cat}
            )
    
    def test_bulk_set_category_rejects_empty_value(self, auth_headers, session_items):
        """Bulk set_category rejects empty category value"""
        item_ids = [session_items[0]["id"]] if session_items else ["test"]
        response = requests.post(
            f"{BASE_URL}/api/intake/sessions/{SESSION_ID}/bulk-action",
            headers=auth_headers,
            json={"item_ids": item_ids, "action": "set_category", "value": ""}
        )
        assert response.status_code == 200
        data = response.json()
        # All items should be skipped with empty_category reason
        assert data["skipped"] == len(item_ids)
        assert data["updated"] == 0


class TestBulkAddTags:
    """Test bulk add_tags action"""
    
    def test_bulk_add_tags_updates_items(self, auth_headers, session_items):
        """Bulk add_tags adds tags to selected items"""
        test_items = session_items[:3]
        if len(test_items) < 3:
            pytest.skip("Not enough items to test")
        
        item_ids = [i["id"] for i in test_items]
        original_tags = {i["id"]: i.get("tags", []) for i in test_items}
        
        new_tags = "test_tag1, test_tag2"
        response = requests.post(
            f"{BASE_URL}/api/intake/sessions/{SESSION_ID}/bulk-action",
            headers=auth_headers,
            json={"item_ids": item_ids, "action": "add_tags", "value": new_tags}
        )
        assert response.status_code == 200
        data = response.json()
        
        assert data["action"] == "add_tags"
        assert data["value"] == new_tags
        assert data["updated"] == 3
        assert data["skipped"] == 0
        
        # Verify items have the new tags
        for item_id in item_ids:
            item_resp = requests.get(f"{BASE_URL}/api/intake/items/{item_id}", headers=auth_headers)
            item_tags = item_resp.json()["tags"]
            assert "test_tag1" in item_tags
            assert "test_tag2" in item_tags
        
        # Restore original tags
        for item_id, orig_tags in original_tags.items():
            requests.put(
                f"{BASE_URL}/api/intake/items/{item_id}",
                headers=auth_headers,
                json={"tags": orig_tags}
            )
    
    def test_bulk_add_tags_deduplicates(self, auth_headers, session_items):
        """Bulk add_tags deduplicates with existing tags"""
        test_item = session_items[0] if session_items else None
        if not test_item:
            pytest.skip("No items to test")
        
        item_id = test_item["id"]
        original_tags = test_item.get("tags", [])
        
        # First add some tags
        requests.put(
            f"{BASE_URL}/api/intake/items/{item_id}",
            headers=auth_headers,
            json={"tags": ["existing_tag", "another_tag"]}
        )
        
        # Now bulk add tags including one that already exists
        response = requests.post(
            f"{BASE_URL}/api/intake/sessions/{SESSION_ID}/bulk-action",
            headers=auth_headers,
            json={"item_ids": [item_id], "action": "add_tags", "value": "existing_tag, new_tag"}
        )
        assert response.status_code == 200
        
        # Verify deduplication - existing_tag should appear only once
        item_resp = requests.get(f"{BASE_URL}/api/intake/items/{item_id}", headers=auth_headers)
        item_tags = item_resp.json()["tags"]
        assert item_tags.count("existing_tag") == 1
        assert "another_tag" in item_tags
        assert "new_tag" in item_tags
        
        # Verify order: existing tags first, then new
        assert item_tags.index("existing_tag") < item_tags.index("new_tag")
        
        # Restore original tags
        requests.put(
            f"{BASE_URL}/api/intake/items/{item_id}",
            headers=auth_headers,
            json={"tags": original_tags}
        )
    
    def test_bulk_add_tags_rejects_empty_value(self, auth_headers, session_items):
        """Bulk add_tags rejects empty tags value"""
        item_ids = [session_items[0]["id"]] if session_items else ["test"]
        response = requests.post(
            f"{BASE_URL}/api/intake/sessions/{SESSION_ID}/bulk-action",
            headers=auth_headers,
            json={"item_ids": item_ids, "action": "add_tags", "value": ""}
        )
        assert response.status_code == 200
        data = response.json()
        # All items should be skipped with empty_tags reason
        assert data["skipped"] == len(item_ids)
        assert data["updated"] == 0


class TestBulkActionResponseStructure:
    """Test bulk action response structure"""
    
    def test_response_has_all_required_fields(self, auth_headers, session_items):
        """Bulk action response has all required fields"""
        item_ids = [session_items[0]["id"]] if session_items else ["test"]
        response = requests.post(
            f"{BASE_URL}/api/intake/sessions/{SESSION_ID}/bulk-action",
            headers=auth_headers,
            json={"item_ids": item_ids, "action": "set_status", "value": "in_review"}
        )
        assert response.status_code == 200
        data = response.json()
        
        required_fields = ["action", "value", "updated", "skipped", "skipped_items", "total_selected"]
        for field in required_fields:
            assert field in data, f"Missing field: {field}"
        
        # Restore
        requests.put(
            f"{BASE_URL}/api/intake/items/{item_ids[0]}",
            headers=auth_headers,
            json={"status": "ready"}
        )
    
    def test_skipped_items_have_id_and_reason(self, auth_headers, session_items):
        """Skipped items have id and reason fields"""
        # Find item with 3+ duplicate flags
        fishnet_item = None
        for item in session_items:
            if len(item.get("duplicate_flags", [])) >= 3:
                fishnet_item = item
                break
        
        if not fishnet_item:
            pytest.skip("No item with 3+ duplicate flags found")
        
        # Set to in_review first
        requests.put(
            f"{BASE_URL}/api/intake/items/{fishnet_item['id']}",
            headers=auth_headers,
            json={"status": "in_review"}
        )
        
        response = requests.post(
            f"{BASE_URL}/api/intake/sessions/{SESSION_ID}/bulk-action",
            headers=auth_headers,
            json={"item_ids": [fishnet_item["id"]], "action": "set_status", "value": "ready"}
        )
        assert response.status_code == 200
        data = response.json()
        
        assert data["skipped"] == 1
        assert len(data["skipped_items"]) == 1
        skipped = data["skipped_items"][0]
        assert "id" in skipped
        assert "reason" in skipped
        assert skipped["id"] == fishnet_item["id"]


class TestBulkActionValidation:
    """Test validation guards for bulk actions"""
    
    def test_items_with_3plus_dupes_skipped_for_ready(self, auth_headers, session_items):
        """Items with 3+ unresolved duplicate_flags are skipped when bulk-marking as ready"""
        # Find item with 3+ duplicate flags
        dupe_items = [i for i in session_items if len(i.get("duplicate_flags", [])) >= 3]
        if not dupe_items:
            pytest.skip("No items with 3+ duplicate flags found")
        
        dupe_item = dupe_items[0]
        
        # Set to in_review
        requests.put(
            f"{BASE_URL}/api/intake/items/{dupe_item['id']}",
            headers=auth_headers,
            json={"status": "in_review"}
        )
        
        response = requests.post(
            f"{BASE_URL}/api/intake/sessions/{SESSION_ID}/bulk-action",
            headers=auth_headers,
            json={"item_ids": [dupe_item["id"]], "action": "set_status", "value": "ready"}
        )
        assert response.status_code == 200
        data = response.json()
        
        assert data["updated"] == 0
        assert data["skipped"] == 1
        assert "unresolved_duplicates" in data["skipped_items"][0]["reason"]
    
    def test_nonexistent_items_skipped(self, auth_headers):
        """Nonexistent item IDs are skipped with not_found reason"""
        response = requests.post(
            f"{BASE_URL}/api/intake/sessions/{SESSION_ID}/bulk-action",
            headers=auth_headers,
            json={"item_ids": ["nonexistent-item-id"], "action": "set_status", "value": "in_review"}
        )
        assert response.status_code == 200
        data = response.json()
        
        assert data["updated"] == 0
        assert data["skipped"] == 1
        assert data["skipped_items"][0]["reason"] == "not_found"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
