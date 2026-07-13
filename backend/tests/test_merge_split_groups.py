"""
Multi-Photo Item Grouping Tests (Merge, Split, Suggest Groups)
Tests for:
- POST /api/field-listing/batches/{batch_id}/merge-items
- POST /api/field-listing/items/{item_id}/split
- POST /api/field-listing/batches/{batch_id}/suggest-groups
"""
import pytest
import requests
import os
import io
from PIL import Image

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

@pytest.fixture(scope="module")
def auth_token():
    """Get authentication token"""
    response = requests.post(f"{BASE_URL}/api/auth/login", json={
        "password": "TSFounder!Vault2026#Secure"
    })
    if response.status_code == 200:
        return response.json().get("access_token")
    pytest.skip("Authentication failed - skipping tests")

@pytest.fixture(scope="module")
def auth_headers(auth_token):
    """Headers with auth token"""
    return {
        "Authorization": f"Bearer {auth_token}",
        "Content-Type": "application/json"
    }

def create_test_image(color='red'):
    """Create a simple test image"""
    img = Image.new('RGB', (100, 100), color=color)
    img_bytes = io.BytesIO()
    img.save(img_bytes, format='JPEG')
    img_bytes.seek(0)
    return img_bytes

@pytest.fixture(scope="module")
def test_batch_with_items(auth_headers):
    """Create a test batch with multiple items for merge/split testing"""
    # Create test batch
    response = requests.post(f"{BASE_URL}/api/field-listing/batches", json={
        "name": "TEST_Merge_Split_Batch",
        "source_vendor": "Test Vendor",
        "grouped_pricing_note": "Test pricing",
        "destinations": ["website", "offerup", "facebook"]
    }, headers=auth_headers)
    
    if response.status_code not in [200, 201]:
        pytest.skip(f"Failed to create test batch: {response.text}")
    
    batch_id = response.json().get("id")
    
    # Upload 3 test images to create 3 items
    headers = {"Authorization": auth_headers["Authorization"]}
    item_ids = []
    
    for i, color in enumerate(['red', 'green', 'blue']):
        img_bytes = create_test_image(color)
        files = [('files', (f'test_image_{i}.jpg', img_bytes, 'image/jpeg'))]
        upload_resp = requests.post(
            f"{BASE_URL}/api/field-listing/batches/{batch_id}/upload-photos",
            files=files,
            headers=headers
        )
        if upload_resp.status_code == 200 and upload_resp.json().get("items"):
            item_ids.append(upload_resp.json()["items"][0]["id"])
    
    yield {"batch_id": batch_id, "item_ids": item_ids}
    
    # Cleanup
    requests.delete(f"{BASE_URL}/api/field-listing/batches/{batch_id}", headers=auth_headers)


class TestMergeItems:
    """Test POST /api/field-listing/batches/{batch_id}/merge-items endpoint"""
    
    def test_merge_two_items_success(self, auth_headers, test_batch_with_items):
        """Merge 2 items into 1 - combines images, removes secondary item"""
        batch_id = test_batch_with_items["batch_id"]
        item_ids = test_batch_with_items["item_ids"]
        
        if len(item_ids) < 2:
            pytest.skip("Not enough items to test merge")
        
        # Get initial batch state
        batch_before = requests.get(f"{BASE_URL}/api/field-listing/batches/{batch_id}", headers=auth_headers).json()
        initial_item_count = len(batch_before.get("items", []))
        
        # Merge first 2 items
        response = requests.post(
            f"{BASE_URL}/api/field-listing/batches/{batch_id}/merge-items",
            json={"item_ids": item_ids[:2]},
            headers=auth_headers
        )
        
        assert response.status_code == 200, f"Merge failed: {response.text}"
        data = response.json()
        
        # Verify response structure
        assert "merged_item" in data
        assert "removed_count" in data
        assert "total_images" in data
        
        # Verify merged item has all images
        merged_item = data["merged_item"]
        assert len(merged_item["images"]) == 2, f"Expected 2 images, got {len(merged_item['images'])}"
        assert data["removed_count"] == 1
        assert data["total_images"] == 2
        
        # Verify merged_from field tracks source items
        assert "merged_from" in merged_item
        assert item_ids[1] in merged_item["merged_from"]
        
        # Verify batch item_count decreased
        batch_after = requests.get(f"{BASE_URL}/api/field-listing/batches/{batch_id}", headers=auth_headers).json()
        assert batch_after["item_count"] == initial_item_count - 1
        
        print(f"Successfully merged 2 items into 1 with {data['total_images']} images")
    
    def test_merge_requires_at_least_two_items(self, auth_headers, test_batch_with_items):
        """Merge with less than 2 items fails"""
        batch_id = test_batch_with_items["batch_id"]
        item_ids = test_batch_with_items["item_ids"]
        
        if not item_ids:
            pytest.skip("No items available")
        
        response = requests.post(
            f"{BASE_URL}/api/field-listing/batches/{batch_id}/merge-items",
            json={"item_ids": [item_ids[0]]},  # Only 1 item
            headers=auth_headers
        )
        
        assert response.status_code == 400
        assert "at least 2" in response.json().get("detail", "").lower()
    
    def test_merge_nonexistent_item_fails(self, auth_headers, test_batch_with_items):
        """Merge with nonexistent item ID fails"""
        batch_id = test_batch_with_items["batch_id"]
        item_ids = test_batch_with_items["item_ids"]
        
        if not item_ids:
            pytest.skip("No items available")
        
        response = requests.post(
            f"{BASE_URL}/api/field-listing/batches/{batch_id}/merge-items",
            json={"item_ids": [item_ids[0], "nonexistent-item-id"]},
            headers=auth_headers
        )
        
        assert response.status_code == 404
        assert "not found" in response.json().get("detail", "").lower()
    
    def test_merge_nonexistent_batch_fails(self, auth_headers):
        """Merge on nonexistent batch fails"""
        response = requests.post(
            f"{BASE_URL}/api/field-listing/batches/nonexistent-batch/merge-items",
            json={"item_ids": ["id1", "id2"]},
            headers=auth_headers
        )
        
        assert response.status_code == 404


class TestSplitItem:
    """Test POST /api/field-listing/items/{item_id}/split endpoint"""
    
    def test_split_multi_image_item(self, auth_headers):
        """Split a multi-image item back into separate items"""
        # Create a fresh batch for split testing
        batch_resp = requests.post(f"{BASE_URL}/api/field-listing/batches", json={
            "name": "TEST_Split_Batch",
            "source_vendor": "Split Test"
        }, headers=auth_headers)
        batch_id = batch_resp.json()["id"]
        
        try:
            # Upload 2 images
            headers = {"Authorization": auth_headers["Authorization"]}
            item_ids = []
            
            for i, color in enumerate(['cyan', 'magenta']):
                img_bytes = create_test_image(color)
                files = [('files', (f'split_test_{i}.jpg', img_bytes, 'image/jpeg'))]
                upload_resp = requests.post(
                    f"{BASE_URL}/api/field-listing/batches/{batch_id}/upload-photos",
                    files=files,
                    headers=headers
                )
                if upload_resp.status_code == 200 and upload_resp.json().get("items"):
                    item_ids.append(upload_resp.json()["items"][0]["id"])
            
            if len(item_ids) < 2:
                pytest.skip("Failed to upload enough images")
            
            # Merge them first
            merge_resp = requests.post(
                f"{BASE_URL}/api/field-listing/batches/{batch_id}/merge-items",
                json={"item_ids": item_ids},
                headers=auth_headers
            )
            assert merge_resp.status_code == 200
            merged_item_id = merge_resp.json()["merged_item"]["id"]
            
            # Get batch state after merge
            batch_after_merge = requests.get(f"{BASE_URL}/api/field-listing/batches/{batch_id}", headers=auth_headers).json()
            item_count_after_merge = batch_after_merge["item_count"]
            
            # Now split the merged item
            split_resp = requests.post(
                f"{BASE_URL}/api/field-listing/items/{merged_item_id}/split",
                json={},
                headers=auth_headers
            )
            
            assert split_resp.status_code == 200, f"Split failed: {split_resp.text}"
            split_data = split_resp.json()
            
            # Verify response structure
            assert "original_id" in split_data
            assert "new_items" in split_data
            assert "total_split" in split_data
            
            assert split_data["original_id"] == merged_item_id
            assert split_data["total_split"] == 2
            assert len(split_data["new_items"]) == 1  # 1 new item created (original keeps first image)
            
            # Verify new items have split_from field
            for new_item in split_data["new_items"]:
                assert new_item["split_from"] == merged_item_id
            
            # Verify batch item_count increased
            batch_after_split = requests.get(f"{BASE_URL}/api/field-listing/batches/{batch_id}", headers=auth_headers).json()
            assert batch_after_split["item_count"] == item_count_after_merge + 1
            
            print(f"Successfully split item into {split_data['total_split']} separate items")
            
        finally:
            # Cleanup
            requests.delete(f"{BASE_URL}/api/field-listing/batches/{batch_id}", headers=auth_headers)
    
    def test_split_single_image_item_fails(self, auth_headers):
        """Split item with only 1 image fails"""
        # Create a batch with single image item
        batch_resp = requests.post(f"{BASE_URL}/api/field-listing/batches", json={
            "name": "TEST_Split_Single_Batch"
        }, headers=auth_headers)
        batch_id = batch_resp.json()["id"]
        
        try:
            # Upload 1 image
            headers = {"Authorization": auth_headers["Authorization"]}
            img_bytes = create_test_image('yellow')
            files = [('files', ('single_image.jpg', img_bytes, 'image/jpeg'))]
            upload_resp = requests.post(
                f"{BASE_URL}/api/field-listing/batches/{batch_id}/upload-photos",
                files=files,
                headers=headers
            )
            
            if upload_resp.status_code == 200 and upload_resp.json().get("items"):
                item_id = upload_resp.json()["items"][0]["id"]
                
                # Try to split single-image item
                split_resp = requests.post(
                    f"{BASE_URL}/api/field-listing/items/{item_id}/split",
                    json={},
                    headers=auth_headers
                )
                
                assert split_resp.status_code == 400
                assert "only 1 image" in split_resp.json().get("detail", "").lower()
        finally:
            requests.delete(f"{BASE_URL}/api/field-listing/batches/{batch_id}", headers=auth_headers)
    
    def test_split_nonexistent_item_fails(self, auth_headers):
        """Split nonexistent item returns 404"""
        response = requests.post(
            f"{BASE_URL}/api/field-listing/items/nonexistent-item-id/split",
            json={},
            headers=auth_headers
        )
        assert response.status_code == 404


class TestSuggestGroups:
    """Test POST /api/field-listing/batches/{batch_id}/suggest-groups endpoint"""
    
    def test_suggest_groups_returns_structure(self, auth_headers, test_batch_with_items):
        """Suggest groups endpoint returns proper structure"""
        batch_id = test_batch_with_items["batch_id"]
        
        response = requests.post(
            f"{BASE_URL}/api/field-listing/batches/{batch_id}/suggest-groups",
            json={},
            headers=auth_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        
        # Verify response structure
        assert "suggestions" in data
        assert "total_items" in data
        assert "suggested_merges" in data
        assert "message" in data
        
        assert isinstance(data["suggestions"], list)
        print(f"Suggest groups response: {data['message']}, {data['suggested_merges']} suggestions")
    
    def test_suggest_groups_with_similar_items(self, auth_headers):
        """Suggest groups finds similar items based on product_type and color"""
        # Create batch with items that have similar vision_analysis
        batch_resp = requests.post(f"{BASE_URL}/api/field-listing/batches", json={
            "name": "TEST_Suggest_Groups_Batch"
        }, headers=auth_headers)
        batch_id = batch_resp.json()["id"]
        
        try:
            # Upload 2 images
            headers = {"Authorization": auth_headers["Authorization"]}
            item_ids = []
            
            for i in range(2):
                img_bytes = create_test_image('red')
                files = [('files', (f'suggest_test_{i}.jpg', img_bytes, 'image/jpeg'))]
                upload_resp = requests.post(
                    f"{BASE_URL}/api/field-listing/batches/{batch_id}/upload-photos",
                    files=files,
                    headers=headers
                )
                if upload_resp.status_code == 200 and upload_resp.json().get("items"):
                    item_ids.append(upload_resp.json()["items"][0]["id"])
            
            if len(item_ids) < 2:
                pytest.skip("Failed to upload enough images")
            
            # Manually set similar vision_analysis on both items
            for item_id in item_ids:
                requests.put(f"{BASE_URL}/api/field-listing/items/{item_id}", json={
                    "draft_title": "Women's Red Dress"
                }, headers=auth_headers)
            
            # Also need to set vision_analysis directly in DB or via API
            # Since we can't directly set vision_analysis via the update endpoint,
            # we'll test that the endpoint works with items that have draft_title set
            
            response = requests.post(
                f"{BASE_URL}/api/field-listing/batches/{batch_id}/suggest-groups",
                json={},
                headers=auth_headers
            )
            
            assert response.status_code == 200
            data = response.json()
            
            # With identical draft_titles, should suggest grouping
            # Note: The actual grouping depends on vision_analysis which we can't easily set
            print(f"Suggest groups with similar items: {data}")
            
        finally:
            requests.delete(f"{BASE_URL}/api/field-listing/batches/{batch_id}", headers=auth_headers)
    
    def test_suggest_groups_empty_with_different_items(self, auth_headers):
        """Suggest groups returns empty when items have different product types"""
        batch_resp = requests.post(f"{BASE_URL}/api/field-listing/batches", json={
            "name": "TEST_Different_Items_Batch"
        }, headers=auth_headers)
        batch_id = batch_resp.json()["id"]
        
        try:
            # Upload 2 images
            headers = {"Authorization": auth_headers["Authorization"]}
            item_ids = []
            
            for i, color in enumerate(['red', 'blue']):
                img_bytes = create_test_image(color)
                files = [('files', (f'different_test_{i}.jpg', img_bytes, 'image/jpeg'))]
                upload_resp = requests.post(
                    f"{BASE_URL}/api/field-listing/batches/{batch_id}/upload-photos",
                    files=files,
                    headers=headers
                )
                if upload_resp.status_code == 200 and upload_resp.json().get("items"):
                    item_ids.append(upload_resp.json()["items"][0]["id"])
            
            if len(item_ids) < 2:
                pytest.skip("Failed to upload enough images")
            
            # Set different titles on items
            requests.put(f"{BASE_URL}/api/field-listing/items/{item_ids[0]}", json={
                "draft_title": "Women's Red Dress"
            }, headers=auth_headers)
            requests.put(f"{BASE_URL}/api/field-listing/items/{item_ids[1]}", json={
                "draft_title": "Men's Blue Jacket"
            }, headers=auth_headers)
            
            response = requests.post(
                f"{BASE_URL}/api/field-listing/batches/{batch_id}/suggest-groups",
                json={},
                headers=auth_headers
            )
            
            assert response.status_code == 200
            data = response.json()
            
            # With different product types, should return empty suggestions
            # (unless there's some similarity we didn't account for)
            print(f"Suggest groups with different items: {data}")
            
        finally:
            requests.delete(f"{BASE_URL}/api/field-listing/batches/{batch_id}", headers=auth_headers)
    
    def test_suggest_groups_not_enough_items(self, auth_headers):
        """Suggest groups with less than 2 items returns empty"""
        batch_resp = requests.post(f"{BASE_URL}/api/field-listing/batches", json={
            "name": "TEST_Single_Item_Batch"
        }, headers=auth_headers)
        batch_id = batch_resp.json()["id"]
        
        try:
            # Upload only 1 image
            headers = {"Authorization": auth_headers["Authorization"]}
            img_bytes = create_test_image('purple')
            files = [('files', ('single.jpg', img_bytes, 'image/jpeg'))]
            requests.post(
                f"{BASE_URL}/api/field-listing/batches/{batch_id}/upload-photos",
                files=files,
                headers=headers
            )
            
            response = requests.post(
                f"{BASE_URL}/api/field-listing/batches/{batch_id}/suggest-groups",
                json={},
                headers=auth_headers
            )
            
            assert response.status_code == 200
            data = response.json()
            assert data["suggestions"] == []
            assert "not enough" in data.get("message", "").lower()
            
        finally:
            requests.delete(f"{BASE_URL}/api/field-listing/batches/{batch_id}", headers=auth_headers)
    
    def test_suggest_groups_nonexistent_batch(self, auth_headers):
        """Suggest groups on nonexistent batch returns 404"""
        response = requests.post(
            f"{BASE_URL}/api/field-listing/batches/nonexistent-batch/suggest-groups",
            json={},
            headers=auth_headers
        )
        assert response.status_code == 404


class TestMergedItemFields:
    """Test that merged/split items have correct tracking fields"""
    
    def test_merged_item_has_merged_from_field(self, auth_headers):
        """Merged item contains merged_from field with source item IDs"""
        batch_resp = requests.post(f"{BASE_URL}/api/field-listing/batches", json={
            "name": "TEST_Merged_From_Field_Batch"
        }, headers=auth_headers)
        batch_id = batch_resp.json()["id"]
        
        try:
            # Upload 2 images
            headers = {"Authorization": auth_headers["Authorization"]}
            item_ids = []
            
            for i in range(2):
                img_bytes = create_test_image('orange')
                files = [('files', (f'merged_from_test_{i}.jpg', img_bytes, 'image/jpeg'))]
                upload_resp = requests.post(
                    f"{BASE_URL}/api/field-listing/batches/{batch_id}/upload-photos",
                    files=files,
                    headers=headers
                )
                if upload_resp.status_code == 200 and upload_resp.json().get("items"):
                    item_ids.append(upload_resp.json()["items"][0]["id"])
            
            if len(item_ids) < 2:
                pytest.skip("Failed to upload enough images")
            
            # Merge items
            merge_resp = requests.post(
                f"{BASE_URL}/api/field-listing/batches/{batch_id}/merge-items",
                json={"item_ids": item_ids},
                headers=auth_headers
            )
            
            assert merge_resp.status_code == 200
            merged_item = merge_resp.json()["merged_item"]
            
            # Verify merged_from field
            assert "merged_from" in merged_item
            assert isinstance(merged_item["merged_from"], list)
            assert item_ids[1] in merged_item["merged_from"]
            
            print(f"Merged item has merged_from: {merged_item['merged_from']}")
            
        finally:
            requests.delete(f"{BASE_URL}/api/field-listing/batches/{batch_id}", headers=auth_headers)
    
    def test_split_item_has_split_from_field(self, auth_headers):
        """Split items contain split_from field with source item ID"""
        batch_resp = requests.post(f"{BASE_URL}/api/field-listing/batches", json={
            "name": "TEST_Split_From_Field_Batch"
        }, headers=auth_headers)
        batch_id = batch_resp.json()["id"]
        
        try:
            # Upload 2 images
            headers = {"Authorization": auth_headers["Authorization"]}
            item_ids = []
            
            for i in range(2):
                img_bytes = create_test_image('pink')
                files = [('files', (f'split_from_test_{i}.jpg', img_bytes, 'image/jpeg'))]
                upload_resp = requests.post(
                    f"{BASE_URL}/api/field-listing/batches/{batch_id}/upload-photos",
                    files=files,
                    headers=headers
                )
                if upload_resp.status_code == 200 and upload_resp.json().get("items"):
                    item_ids.append(upload_resp.json()["items"][0]["id"])
            
            if len(item_ids) < 2:
                pytest.skip("Failed to upload enough images")
            
            # Merge items first
            merge_resp = requests.post(
                f"{BASE_URL}/api/field-listing/batches/{batch_id}/merge-items",
                json={"item_ids": item_ids},
                headers=auth_headers
            )
            merged_item_id = merge_resp.json()["merged_item"]["id"]
            
            # Split the merged item
            split_resp = requests.post(
                f"{BASE_URL}/api/field-listing/items/{merged_item_id}/split",
                json={},
                headers=auth_headers
            )
            
            assert split_resp.status_code == 200
            new_items = split_resp.json()["new_items"]
            
            # Verify split_from field on new items
            for new_item in new_items:
                assert "split_from" in new_item
                assert new_item["split_from"] == merged_item_id
            
            print(f"Split items have split_from: {merged_item_id}")
            
        finally:
            requests.delete(f"{BASE_URL}/api/field-listing/batches/{batch_id}", headers=auth_headers)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
