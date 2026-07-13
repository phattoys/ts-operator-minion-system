"""
Field-to-Listing Module Tests
Tests for batch CRUD, photo upload, pricing parser, item updates, and bulk actions.
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

@pytest.fixture(scope="module")
def test_batch_id(auth_headers):
    """Create a test batch and return its ID, cleanup after tests"""
    # Create test batch
    response = requests.post(f"{BASE_URL}/api/field-listing/batches", json={
        "name": "TEST_Pytest_Batch",
        "source_vendor": "Test Vendor",
        "grouped_pricing_note": "These were $25 each, sell at $55",
        "grouped_category_note": "Test items",
        "condition_note": "New with tags",
        "pickup_shipping_note": "Local pickup only",
        "destinations": ["website", "offerup", "facebook"]
    }, headers=auth_headers)
    
    if response.status_code in [200, 201]:
        batch_id = response.json().get("id")
        yield batch_id
        # Cleanup
        requests.delete(f"{BASE_URL}/api/field-listing/batches/{batch_id}", headers=auth_headers)
    else:
        pytest.skip(f"Failed to create test batch: {response.text}")


class TestFieldListingStats:
    """Test GET /api/field-listing/stats endpoint"""
    
    def test_stats_returns_counts(self, auth_headers):
        """Stats endpoint returns batch and item counts"""
        response = requests.get(f"{BASE_URL}/api/field-listing/stats", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert "total_batches" in data
        assert "total_items" in data
        assert "approved_items" in data
        assert "draft_items" in data
        assert isinstance(data["total_batches"], int)
        assert isinstance(data["total_items"], int)
        print(f"Stats: {data}")
    
    def test_stats_requires_auth(self):
        """Stats endpoint requires authentication"""
        response = requests.get(f"{BASE_URL}/api/field-listing/stats")
        assert response.status_code == 401


class TestFieldListingBatchCRUD:
    """Test batch CRUD operations"""
    
    def test_create_batch_success(self, auth_headers):
        """Create batch with all fields"""
        response = requests.post(f"{BASE_URL}/api/field-listing/batches", json={
            "name": "TEST_Create_Batch",
            "source_vendor": "Downtown LA",
            "grouped_pricing_note": "price at $12.99",
            "grouped_category_note": "Jewelry",
            "condition_note": "Like new",
            "pickup_shipping_note": "Ships nationwide",
            "destinations": ["website", "offerup"]
        }, headers=auth_headers)
        
        assert response.status_code in [200, 201]
        data = response.json()
        assert data["name"] == "TEST_Create_Batch"
        assert data["source_vendor"] == "Downtown LA"
        assert data["grouped_pricing_note"] == "price at $12.99"
        assert data["status"] == "intake"
        assert "id" in data
        assert "website" in data["destinations"]
        assert "offerup" in data["destinations"]
        print(f"Created batch: {data['id']}")
        
        # Cleanup
        requests.delete(f"{BASE_URL}/api/field-listing/batches/{data['id']}", headers=auth_headers)
    
    def test_create_batch_requires_name(self, auth_headers):
        """Create batch fails without name"""
        response = requests.post(f"{BASE_URL}/api/field-listing/batches", json={
            "name": "",
            "source_vendor": "Test"
        }, headers=auth_headers)
        assert response.status_code == 400
        assert "name" in response.json().get("detail", "").lower()
    
    def test_create_batch_invalid_destination(self, auth_headers):
        """Create batch fails with invalid destination"""
        response = requests.post(f"{BASE_URL}/api/field-listing/batches", json={
            "name": "TEST_Invalid_Dest",
            "destinations": ["website", "invalid_dest"]
        }, headers=auth_headers)
        assert response.status_code == 400
        assert "invalid destination" in response.json().get("detail", "").lower()
    
    def test_list_batches(self, auth_headers):
        """List all batches"""
        response = requests.get(f"{BASE_URL}/api/field-listing/batches", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert "batches" in data
        assert isinstance(data["batches"], list)
        print(f"Found {len(data['batches'])} batches")
    
    def test_get_single_batch(self, auth_headers, test_batch_id):
        """Get single batch with items"""
        response = requests.get(f"{BASE_URL}/api/field-listing/batches/{test_batch_id}", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == test_batch_id
        assert "items" in data
        assert isinstance(data["items"], list)
        print(f"Batch {test_batch_id} has {len(data['items'])} items")
    
    def test_get_nonexistent_batch(self, auth_headers):
        """Get nonexistent batch returns 404"""
        response = requests.get(f"{BASE_URL}/api/field-listing/batches/nonexistent-id", headers=auth_headers)
        assert response.status_code == 404
    
    def test_update_batch(self, auth_headers, test_batch_id):
        """Update batch notes"""
        response = requests.put(f"{BASE_URL}/api/field-listing/batches/{test_batch_id}", json={
            "grouped_pricing_note": "Updated: sell at $99",
            "condition_note": "Updated condition"
        }, headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert data["grouped_pricing_note"] == "Updated: sell at $99"
        assert data["condition_note"] == "Updated condition"
        print(f"Updated batch: {data}")
    
    def test_delete_batch(self, auth_headers):
        """Delete batch and all items"""
        # Create a batch to delete
        create_resp = requests.post(f"{BASE_URL}/api/field-listing/batches", json={
            "name": "TEST_Delete_Batch"
        }, headers=auth_headers)
        batch_id = create_resp.json()["id"]
        
        # Delete it
        response = requests.delete(f"{BASE_URL}/api/field-listing/batches/{batch_id}", headers=auth_headers)
        assert response.status_code == 200
        assert "deleted" in response.json().get("message", "").lower()
        
        # Verify it's gone
        get_resp = requests.get(f"{BASE_URL}/api/field-listing/batches/{batch_id}", headers=auth_headers)
        assert get_resp.status_code == 404


class TestPhotoUpload:
    """Test photo upload and image serving"""
    
    def test_upload_photo_creates_item(self, auth_headers, test_batch_id):
        """Upload photo creates item record"""
        # Create a simple test image
        img = Image.new('RGB', (100, 100), color='red')
        img_bytes = io.BytesIO()
        img.save(img_bytes, format='JPEG')
        img_bytes.seek(0)
        
        files = [('files', ('test_image.jpg', img_bytes, 'image/jpeg'))]
        headers = {"Authorization": auth_headers["Authorization"]}
        
        response = requests.post(
            f"{BASE_URL}/api/field-listing/batches/{test_batch_id}/upload-photos",
            files=files,
            headers=headers
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["uploaded"] >= 1
        assert "items" in data
        assert len(data["items"]) >= 1
        
        item = data["items"][0]
        assert "id" in item
        assert item["batch_id"] == test_batch_id
        assert item["status"] == "draft"
        assert len(item["images"]) >= 1
        print(f"Uploaded {data['uploaded']} photos, total items: {data['total_items']}")
        
        # Return item for use in other tests
        return item
    
    def test_upload_photo_to_nonexistent_batch(self, auth_headers):
        """Upload to nonexistent batch returns 404"""
        img = Image.new('RGB', (100, 100), color='blue')
        img_bytes = io.BytesIO()
        img.save(img_bytes, format='JPEG')
        img_bytes.seek(0)
        
        files = [('files', ('test.jpg', img_bytes, 'image/jpeg'))]
        headers = {"Authorization": auth_headers["Authorization"]}
        
        response = requests.post(
            f"{BASE_URL}/api/field-listing/batches/nonexistent-id/upload-photos",
            files=files,
            headers=headers
        )
        assert response.status_code == 404
    
    def test_serve_uploaded_image(self, auth_headers, test_batch_id):
        """Serve uploaded image via GET endpoint"""
        # First upload an image
        img = Image.new('RGB', (100, 100), color='green')
        img_bytes = io.BytesIO()
        img.save(img_bytes, format='JPEG')
        img_bytes.seek(0)
        
        files = [('files', ('serve_test.jpg', img_bytes, 'image/jpeg'))]
        headers = {"Authorization": auth_headers["Authorization"]}
        
        upload_resp = requests.post(
            f"{BASE_URL}/api/field-listing/batches/{test_batch_id}/upload-photos",
            files=files,
            headers=headers
        )
        
        if upload_resp.status_code == 200 and upload_resp.json().get("items"):
            item = upload_resp.json()["items"][0]
            filename = item["images"][0]["filename"]
            
            # Now try to serve it (no auth required for image serving)
            serve_resp = requests.get(f"{BASE_URL}/api/field-listing/images/{test_batch_id}/{filename}")
            assert serve_resp.status_code == 200
            assert "image" in serve_resp.headers.get("content-type", "")
            print(f"Successfully served image: {filename}")
    
    def test_serve_nonexistent_image(self):
        """Serve nonexistent image returns 404"""
        response = requests.get(f"{BASE_URL}/api/field-listing/images/fake-batch/fake-image.jpg")
        assert response.status_code == 404


class TestPricingParser:
    """Test pricing note parsing and apply-pricing endpoint"""
    
    def test_apply_pricing_with_note(self, auth_headers, test_batch_id):
        """Apply pricing from note parses correctly"""
        # First upload an image to have items
        img = Image.new('RGB', (100, 100), color='yellow')
        img_bytes = io.BytesIO()
        img.save(img_bytes, format='JPEG')
        img_bytes.seek(0)
        
        files = [('files', ('pricing_test.jpg', img_bytes, 'image/jpeg'))]
        headers = {"Authorization": auth_headers["Authorization"]}
        
        requests.post(
            f"{BASE_URL}/api/field-listing/batches/{test_batch_id}/upload-photos",
            files=files,
            headers=headers
        )
        
        # Apply pricing with note
        response = requests.post(
            f"{BASE_URL}/api/field-listing/batches/{test_batch_id}/apply-pricing",
            json={"pricing_note": "These were $25 each, sell at $55"},
            headers=auth_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["unit_cost"] == 25.0
        assert data["retail_price"] == 55.0
        assert data["updated"] >= 1
        print(f"Applied pricing: unit_cost={data['unit_cost']}, retail_price={data['retail_price']}, updated={data['updated']} items")
    
    def test_apply_pricing_retail_only(self, auth_headers, test_batch_id):
        """Apply pricing with retail-only note"""
        response = requests.post(
            f"{BASE_URL}/api/field-listing/batches/{test_batch_id}/apply-pricing",
            json={"pricing_note": "price at $12.99"},
            headers=auth_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["retail_price"] == 12.99
        print(f"Applied retail-only pricing: {data['retail_price']}")
    
    def test_apply_pricing_explicit_values(self, auth_headers, test_batch_id):
        """Apply pricing with explicit values"""
        response = requests.post(
            f"{BASE_URL}/api/field-listing/batches/{test_batch_id}/apply-pricing",
            json={"unit_cost": 10.0, "retail_price": 29.99},
            headers=auth_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["unit_cost"] == 10.0
        assert data["retail_price"] == 29.99
    
    def test_apply_pricing_no_values(self, auth_headers, test_batch_id):
        """Apply pricing with no parseable values fails"""
        response = requests.post(
            f"{BASE_URL}/api/field-listing/batches/{test_batch_id}/apply-pricing",
            json={"pricing_note": "no numbers here"},
            headers=auth_headers
        )
        assert response.status_code == 400
        assert "pricing" in response.json().get("detail", "").lower()


class TestItemUpdate:
    """Test individual item update endpoint"""
    
    def test_update_item_fields(self, auth_headers, test_batch_id):
        """Update item title, price, category, status"""
        # Get items in batch
        batch_resp = requests.get(f"{BASE_URL}/api/field-listing/batches/{test_batch_id}", headers=auth_headers)
        items = batch_resp.json().get("items", [])
        
        if not items:
            # Upload an image first
            img = Image.new('RGB', (100, 100), color='purple')
            img_bytes = io.BytesIO()
            img.save(img_bytes, format='JPEG')
            img_bytes.seek(0)
            
            files = [('files', ('update_test.jpg', img_bytes, 'image/jpeg'))]
            headers = {"Authorization": auth_headers["Authorization"]}
            
            upload_resp = requests.post(
                f"{BASE_URL}/api/field-listing/batches/{test_batch_id}/upload-photos",
                files=files,
                headers=headers
            )
            items = upload_resp.json().get("items", [])
        
        if items:
            item_id = items[0]["id"]
            
            # Update item
            response = requests.put(f"{BASE_URL}/api/field-listing/items/{item_id}", json={
                "draft_title": "Updated Test Title",
                "retail_price": 49.99,
                "category_suggestion": "Test Category",
                "status": "review"
            }, headers=auth_headers)
            
            assert response.status_code == 200
            data = response.json()
            assert data["draft_title"] == "Updated Test Title"
            assert data["retail_price"] == 49.99
            assert data["category_suggestion"] == "Test Category"
            assert data["status"] == "review"
            print(f"Updated item: {data['id']}")
    
    def test_update_item_invalid_status(self, auth_headers, test_batch_id):
        """Update item with invalid status fails"""
        batch_resp = requests.get(f"{BASE_URL}/api/field-listing/batches/{test_batch_id}", headers=auth_headers)
        items = batch_resp.json().get("items", [])
        
        if items:
            item_id = items[0]["id"]
            response = requests.put(f"{BASE_URL}/api/field-listing/items/{item_id}", json={
                "status": "invalid_status"
            }, headers=auth_headers)
            assert response.status_code == 400
    
    def test_update_nonexistent_item(self, auth_headers):
        """Update nonexistent item returns 404"""
        response = requests.put(f"{BASE_URL}/api/field-listing/items/nonexistent-id", json={
            "draft_title": "Test"
        }, headers=auth_headers)
        assert response.status_code == 404


class TestBulkActions:
    """Test bulk approve/skip actions"""
    
    def test_bulk_approve(self, auth_headers, test_batch_id):
        """Bulk approve items"""
        # Get items
        batch_resp = requests.get(f"{BASE_URL}/api/field-listing/batches/{test_batch_id}", headers=auth_headers)
        items = batch_resp.json().get("items", [])
        
        if items:
            item_ids = [items[0]["id"]]
            
            response = requests.post(
                f"{BASE_URL}/api/field-listing/batches/{test_batch_id}/bulk-action",
                json={"item_ids": item_ids, "action": "approve"},
                headers=auth_headers
            )
            
            assert response.status_code == 200
            data = response.json()
            assert data["action"] == "approve"
            assert data["updated"] >= 1
            print(f"Bulk approved {data['updated']} items")
    
    def test_bulk_skip(self, auth_headers, test_batch_id):
        """Bulk skip items"""
        # Upload another image for skip test
        img = Image.new('RGB', (100, 100), color='orange')
        img_bytes = io.BytesIO()
        img.save(img_bytes, format='JPEG')
        img_bytes.seek(0)
        
        files = [('files', ('skip_test.jpg', img_bytes, 'image/jpeg'))]
        headers = {"Authorization": auth_headers["Authorization"]}
        
        upload_resp = requests.post(
            f"{BASE_URL}/api/field-listing/batches/{test_batch_id}/upload-photos",
            files=files,
            headers=headers
        )
        
        if upload_resp.status_code == 200 and upload_resp.json().get("items"):
            item_id = upload_resp.json()["items"][0]["id"]
            
            response = requests.post(
                f"{BASE_URL}/api/field-listing/batches/{test_batch_id}/bulk-action",
                json={"item_ids": [item_id], "action": "skip"},
                headers=auth_headers
            )
            
            assert response.status_code == 200
            data = response.json()
            assert data["action"] == "skip"
            print(f"Bulk skipped {data['updated']} items")
    
    def test_bulk_set_price(self, auth_headers, test_batch_id):
        """Bulk set price"""
        batch_resp = requests.get(f"{BASE_URL}/api/field-listing/batches/{test_batch_id}", headers=auth_headers)
        items = batch_resp.json().get("items", [])
        
        if items:
            item_ids = [items[0]["id"]]
            
            response = requests.post(
                f"{BASE_URL}/api/field-listing/batches/{test_batch_id}/bulk-action",
                json={"item_ids": item_ids, "action": "set_price", "value": "39.99"},
                headers=auth_headers
            )
            
            assert response.status_code == 200
            data = response.json()
            assert data["action"] == "set_price"


class TestAnalyzeAndGenerateEndpoints:
    """Test analyze and generate-listings endpoints exist (don't run actual LLM calls)"""
    
    def test_analyze_endpoint_exists(self, auth_headers, test_batch_id):
        """Analyze endpoint exists and returns proper response"""
        response = requests.post(
            f"{BASE_URL}/api/field-listing/batches/{test_batch_id}/analyze",
            json={},
            headers=auth_headers
        )
        # Should return 200 with either job_id or "no photos pending" message
        assert response.status_code == 200
        data = response.json()
        assert "message" in data or "job_id" in data
        print(f"Analyze response: {data}")
    
    def test_generate_listings_endpoint_exists(self, auth_headers, test_batch_id):
        """Generate listings endpoint exists"""
        response = requests.post(
            f"{BASE_URL}/api/field-listing/batches/{test_batch_id}/generate-listings",
            json={},
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        assert "message" in data or "job_id" in data
        print(f"Generate listings response: {data}")
    
    def test_generate_packs_endpoint_exists(self, auth_headers, test_batch_id):
        """Generate packs endpoint exists"""
        response = requests.post(
            f"{BASE_URL}/api/field-listing/batches/{test_batch_id}/generate-packs",
            json={},
            headers=auth_headers
        )
        # May return 400 if no items in review/approved status, or 200 if successful
        assert response.status_code in [200, 400]
        print(f"Generate packs response: {response.json()}")
    
    def test_get_packs_endpoint_exists(self, auth_headers, test_batch_id):
        """Get packs endpoint exists"""
        response = requests.get(
            f"{BASE_URL}/api/field-listing/batches/{test_batch_id}/packs",
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        assert "batch_name" in data
        assert "items" in data
        print(f"Get packs response: {data}")


class TestJobPolling:
    """Test job polling endpoint"""
    
    def test_job_not_found(self, auth_headers):
        """Nonexistent job returns 404"""
        response = requests.get(
            f"{BASE_URL}/api/field-listing/jobs/nonexistent-job-id",
            headers=auth_headers
        )
        assert response.status_code == 404


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
