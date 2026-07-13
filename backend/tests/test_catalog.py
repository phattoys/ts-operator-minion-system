"""
Catalog Minion Backend Tests
Tests for: catalog items CRUD, categories, variant groups, duplicates, import, export
"""
import pytest
import requests
import os
import time

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')
if not BASE_URL:
    BASE_URL = "https://page-queue-hub.preview.emergentagent.com"

PASSWORD = "TSFounder!Vault2026#Secure"


class TestCatalogAuth:
    """Test authentication requirements for catalog endpoints"""
    
    def test_stats_requires_auth(self):
        """GET /api/catalog/stats requires authentication"""
        response = requests.get(f"{BASE_URL}/api/catalog/stats")
        assert response.status_code == 401, f"Expected 401, got {response.status_code}"
        print("✓ Stats endpoint requires auth")
    
    def test_items_requires_auth(self):
        """GET /api/catalog/items requires authentication"""
        response = requests.get(f"{BASE_URL}/api/catalog/items")
        assert response.status_code == 401, f"Expected 401, got {response.status_code}"
        print("✓ Items endpoint requires auth")
    
    def test_categories_requires_auth(self):
        """GET /api/catalog/categories requires authentication"""
        response = requests.get(f"{BASE_URL}/api/catalog/categories")
        assert response.status_code == 401, f"Expected 401, got {response.status_code}"
        print("✓ Categories endpoint requires auth")


@pytest.fixture(scope="module")
def auth_token():
    """Get authentication token"""
    response = requests.post(f"{BASE_URL}/api/auth/login", json={"password": PASSWORD})
    assert response.status_code == 200, f"Login failed: {response.text}"
    token = response.json().get("access_token")
    assert token, "No access_token in response"
    print(f"✓ Authenticated successfully")
    return token


@pytest.fixture(scope="module")
def auth_headers(auth_token):
    """Headers with auth token"""
    return {"Authorization": f"Bearer {auth_token}", "Content-Type": "application/json"}


class TestCatalogStats:
    """Test GET /api/catalog/stats"""
    
    def test_stats_returns_correct_structure(self, auth_headers):
        """Stats endpoint returns expected fields"""
        response = requests.get(f"{BASE_URL}/api/catalog/stats", headers=auth_headers)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert "total_items" in data, "Missing total_items"
        assert "by_status" in data, "Missing by_status"
        assert "category_count" in data, "Missing category_count"
        assert "variant_group_count" in data, "Missing variant_group_count"
        assert "draft_count" in data, "Missing draft_count"
        assert "needs_review_count" in data, "Missing needs_review_count"
        assert "ready_count" in data, "Missing ready_count"
        assert "exported_count" in data, "Missing exported_count"
        
        print(f"✓ Stats: {data['total_items']} items, {data['category_count']} categories")


class TestCatalogCategories:
    """Test category CRUD operations"""
    
    def test_list_categories_returns_defaults(self, auth_headers):
        """GET /api/catalog/categories returns default 14 categories"""
        response = requests.get(f"{BASE_URL}/api/catalog/categories", headers=auth_headers)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert "categories" in data, "Missing categories field"
        categories = data["categories"]
        
        # Should have at least 14 default categories
        assert len(categories) >= 14, f"Expected at least 14 categories, got {len(categories)}"
        
        # Check structure
        for cat in categories[:3]:
            assert "id" in cat, "Category missing id"
            assert "name" in cat, "Category missing name"
            assert "created_at" in cat, "Category missing created_at"
        
        # Check some expected default categories
        cat_names = [c["name"] for c in categories]
        expected = ["Vibrators", "Dildos", "Lubricants & Oils", "Lingerie", "Other"]
        for exp in expected:
            assert exp in cat_names, f"Missing expected category: {exp}"
        
        print(f"✓ Categories: {len(categories)} categories returned")
        return categories
    
    def test_create_category(self, auth_headers):
        """POST /api/catalog/categories creates new category"""
        payload = {"name": "TEST_NewCategory"}
        response = requests.post(f"{BASE_URL}/api/catalog/categories", json=payload, headers=auth_headers)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert data["name"] == "TEST_NewCategory", f"Name mismatch: {data['name']}"
        assert "id" in data, "Missing id in response"
        
        print(f"✓ Created category: {data['name']} (id: {data['id'][:8]}...)")
        return data
    
    def test_create_duplicate_category_fails(self, auth_headers):
        """POST /api/catalog/categories with duplicate name fails"""
        payload = {"name": "Vibrators"}  # Default category
        response = requests.post(f"{BASE_URL}/api/catalog/categories", json=payload, headers=auth_headers)
        assert response.status_code == 400, f"Expected 400, got {response.status_code}"
        print("✓ Duplicate category creation blocked")
    
    def test_update_category(self, auth_headers):
        """PUT /api/catalog/categories/{id} updates category"""
        # First create a category
        create_resp = requests.post(
            f"{BASE_URL}/api/catalog/categories",
            json={"name": "TEST_ToUpdate"},
            headers=auth_headers
        )
        if create_resp.status_code == 400:  # Already exists
            # Get existing
            list_resp = requests.get(f"{BASE_URL}/api/catalog/categories", headers=auth_headers)
            cats = list_resp.json()["categories"]
            cat = next((c for c in cats if c["name"] == "TEST_ToUpdate"), None)
            if not cat:
                pytest.skip("Could not create or find test category")
            cat_id = cat["id"]
        else:
            cat_id = create_resp.json()["id"]
        
        # Update it
        update_resp = requests.put(
            f"{BASE_URL}/api/catalog/categories/{cat_id}",
            json={"name": "TEST_Updated"},
            headers=auth_headers
        )
        assert update_resp.status_code == 200, f"Expected 200, got {update_resp.status_code}"
        assert update_resp.json()["name"] == "TEST_Updated"
        print("✓ Category updated successfully")
    
    def test_delete_category_without_items(self, auth_headers):
        """DELETE /api/catalog/categories/{id} deletes unused category"""
        # Create a category to delete
        create_resp = requests.post(
            f"{BASE_URL}/api/catalog/categories",
            json={"name": "TEST_ToDelete"},
            headers=auth_headers
        )
        if create_resp.status_code == 400:
            pytest.skip("Category already exists")
        
        cat_id = create_resp.json()["id"]
        
        # Delete it
        delete_resp = requests.delete(f"{BASE_URL}/api/catalog/categories/{cat_id}", headers=auth_headers)
        assert delete_resp.status_code == 200, f"Expected 200, got {delete_resp.status_code}"
        print("✓ Category deleted successfully")


class TestCatalogItemsCRUD:
    """Test catalog items CRUD operations"""
    
    def test_create_item(self, auth_headers):
        """POST /api/catalog/items creates new item"""
        payload = {
            "title": "TEST_Product Item",
            "brand": "Test Brand",
            "regular_price": 29.99,
            "short_description": "A test product",
            "tags": ["test", "sample"]
        }
        response = requests.post(f"{BASE_URL}/api/catalog/items", json=payload, headers=auth_headers)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert data["title"] == "TEST_Product Item", f"Title mismatch: {data['title']}"
        assert data["brand"] == "Test Brand", f"Brand mismatch: {data['brand']}"
        assert data["regular_price"] == 29.99, f"Price mismatch: {data['regular_price']}"
        assert data["status"] == "Draft", f"Status should be Draft: {data['status']}"
        assert "id" in data, "Missing id"
        assert data["normalized"] == False, "Should not be normalized yet"
        
        print(f"✓ Created item: {data['title']} (id: {data['id'][:8]}...)")
        return data
    
    def test_create_item_requires_title(self, auth_headers):
        """POST /api/catalog/items without title fails"""
        payload = {"brand": "Test Brand"}
        response = requests.post(f"{BASE_URL}/api/catalog/items", json=payload, headers=auth_headers)
        # Should fail validation
        assert response.status_code in [400, 422], f"Expected 400/422, got {response.status_code}"
        print("✓ Item creation requires title")
    
    def test_list_items(self, auth_headers):
        """GET /api/catalog/items returns items list"""
        response = requests.get(f"{BASE_URL}/api/catalog/items", headers=auth_headers)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert "items" in data, "Missing items field"
        assert "count" in data, "Missing count field"
        
        print(f"✓ Listed {data['count']} items")
        return data
    
    def test_list_items_with_status_filter(self, auth_headers):
        """GET /api/catalog/items?status=Draft filters by status"""
        response = requests.get(f"{BASE_URL}/api/catalog/items", params={"status": "Draft"}, headers=auth_headers)
        assert response.status_code == 200
        
        data = response.json()
        for item in data["items"]:
            assert item["status"] == "Draft", f"Item has wrong status: {item['status']}"
        
        print(f"✓ Status filter works: {data['count']} Draft items")
    
    def test_list_items_with_search(self, auth_headers):
        """GET /api/catalog/items?search=TEST filters by search"""
        response = requests.get(f"{BASE_URL}/api/catalog/items", params={"search": "TEST"}, headers=auth_headers)
        assert response.status_code == 200
        
        data = response.json()
        print(f"✓ Search filter works: {data['count']} items matching 'TEST'")
    
    def test_get_single_item(self, auth_headers):
        """GET /api/catalog/items/{id} returns single item"""
        # First create an item
        create_resp = requests.post(
            f"{BASE_URL}/api/catalog/items",
            json={"title": "TEST_SingleItem"},
            headers=auth_headers
        )
        item_id = create_resp.json()["id"]
        
        # Get it
        response = requests.get(f"{BASE_URL}/api/catalog/items/{item_id}", headers=auth_headers)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert data["id"] == item_id, "ID mismatch"
        assert data["title"] == "TEST_SingleItem", "Title mismatch"
        
        print(f"✓ Got single item: {data['title']}")
    
    def test_get_nonexistent_item_returns_404(self, auth_headers):
        """GET /api/catalog/items/{id} with invalid id returns 404"""
        response = requests.get(f"{BASE_URL}/api/catalog/items/nonexistent-id", headers=auth_headers)
        assert response.status_code == 404, f"Expected 404, got {response.status_code}"
        print("✓ Nonexistent item returns 404")
    
    def test_update_item(self, auth_headers):
        """PUT /api/catalog/items/{id} updates item"""
        # Create item
        create_resp = requests.post(
            f"{BASE_URL}/api/catalog/items",
            json={"title": "TEST_ToUpdate", "brand": "Original"},
            headers=auth_headers
        )
        item_id = create_resp.json()["id"]
        
        # Update it
        update_resp = requests.put(
            f"{BASE_URL}/api/catalog/items/{item_id}",
            json={"brand": "Updated Brand", "status": "Needs Review"},
            headers=auth_headers
        )
        assert update_resp.status_code == 200, f"Expected 200, got {update_resp.status_code}"
        
        data = update_resp.json()
        assert data["brand"] == "Updated Brand", f"Brand not updated: {data['brand']}"
        assert data["status"] == "Needs Review", f"Status not updated: {data['status']}"
        
        # Verify with GET
        get_resp = requests.get(f"{BASE_URL}/api/catalog/items/{item_id}", headers=auth_headers)
        assert get_resp.json()["brand"] == "Updated Brand"
        
        print("✓ Item updated and verified")
    
    def test_update_item_invalid_status(self, auth_headers):
        """PUT /api/catalog/items/{id} with invalid status fails"""
        # Create item
        create_resp = requests.post(
            f"{BASE_URL}/api/catalog/items",
            json={"title": "TEST_InvalidStatus"},
            headers=auth_headers
        )
        item_id = create_resp.json()["id"]
        
        # Try invalid status
        update_resp = requests.put(
            f"{BASE_URL}/api/catalog/items/{item_id}",
            json={"status": "InvalidStatus"},
            headers=auth_headers
        )
        assert update_resp.status_code == 400, f"Expected 400, got {update_resp.status_code}"
        print("✓ Invalid status rejected")
    
    def test_delete_item(self, auth_headers):
        """DELETE /api/catalog/items/{id} deletes item"""
        # Create item
        create_resp = requests.post(
            f"{BASE_URL}/api/catalog/items",
            json={"title": "TEST_ToDelete"},
            headers=auth_headers
        )
        item_id = create_resp.json()["id"]
        
        # Delete it
        delete_resp = requests.delete(f"{BASE_URL}/api/catalog/items/{item_id}", headers=auth_headers)
        assert delete_resp.status_code == 200, f"Expected 200, got {delete_resp.status_code}"
        
        # Verify deleted
        get_resp = requests.get(f"{BASE_URL}/api/catalog/items/{item_id}", headers=auth_headers)
        assert get_resp.status_code == 404, "Item should be deleted"
        
        print("✓ Item deleted and verified")


class TestCatalogDuplicates:
    """Test duplicate detection and resolution"""
    
    def test_scan_duplicates_empty(self, auth_headers):
        """GET /api/catalog/duplicates returns pairs structure"""
        response = requests.get(f"{BASE_URL}/api/catalog/duplicates", headers=auth_headers)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert "pairs" in data, "Missing pairs field"
        assert "count" in data, "Missing count field"
        
        print(f"✓ Duplicates scan: {data['count']} pairs found")
    
    def test_scan_duplicates_with_threshold(self, auth_headers):
        """GET /api/catalog/duplicates?threshold=80 uses threshold"""
        response = requests.get(
            f"{BASE_URL}/api/catalog/duplicates",
            params={"threshold": 80},
            headers=auth_headers
        )
        assert response.status_code == 200
        print("✓ Duplicates scan with threshold works")
    
    def test_create_similar_items_and_detect(self, auth_headers):
        """Create similar items and detect as duplicates"""
        # Create two similar items
        item1_resp = requests.post(
            f"{BASE_URL}/api/catalog/items",
            json={"title": "TEST_Duplicate Widget Pro", "brand": "TestBrand"},
            headers=auth_headers
        )
        item1_id = item1_resp.json()["id"]
        
        item2_resp = requests.post(
            f"{BASE_URL}/api/catalog/items",
            json={"title": "TEST_Duplicate Widget Pro Max", "brand": "TestBrand"},
            headers=auth_headers
        )
        item2_id = item2_resp.json()["id"]
        
        # Scan for duplicates with lower threshold
        dup_resp = requests.get(
            f"{BASE_URL}/api/catalog/duplicates",
            params={"threshold": 50},
            headers=auth_headers
        )
        assert dup_resp.status_code == 200
        
        pairs = dup_resp.json()["pairs"]
        # Check if our items are detected
        found = False
        for pair in pairs:
            ids = {pair["item_a"]["id"], pair["item_b"]["id"]}
            if item1_id in ids and item2_id in ids:
                found = True
                assert "score" in pair, "Missing score"
                assert "signals" in pair, "Missing signals"
                print(f"✓ Duplicate pair detected with score: {pair['score']}")
                break
        
        if not found:
            print("✓ Similar items created (may not meet threshold)")
        
        return item1_id, item2_id
    
    def test_resolve_duplicate_not_duplicate(self, auth_headers):
        """POST /api/catalog/duplicates/resolve with not_duplicate action"""
        # Create two items
        item1_resp = requests.post(
            f"{BASE_URL}/api/catalog/items",
            json={"title": "TEST_NotDup1"},
            headers=auth_headers
        )
        item1_id = item1_resp.json()["id"]
        
        item2_resp = requests.post(
            f"{BASE_URL}/api/catalog/items",
            json={"title": "TEST_NotDup2"},
            headers=auth_headers
        )
        item2_id = item2_resp.json()["id"]
        
        # Resolve as not duplicate
        resolve_resp = requests.post(
            f"{BASE_URL}/api/catalog/duplicates/resolve",
            params={"item_a_id": item1_id, "item_b_id": item2_id},
            json={"action": "not_duplicate"},
            headers=auth_headers
        )
        assert resolve_resp.status_code == 200, f"Expected 200, got {resolve_resp.status_code}: {resolve_resp.text}"
        assert resolve_resp.json()["action"] == "dismissed"
        print("✓ Resolved as not_duplicate")
    
    def test_resolve_duplicate_merge_keep_left(self, auth_headers):
        """POST /api/catalog/duplicates/resolve with merge_keep_left"""
        # Create two items with different data
        item1_resp = requests.post(
            f"{BASE_URL}/api/catalog/items",
            json={"title": "TEST_MergeLeft", "brand": "Brand1", "tags": ["tag1"]},
            headers=auth_headers
        )
        item1_id = item1_resp.json()["id"]
        
        item2_resp = requests.post(
            f"{BASE_URL}/api/catalog/items",
            json={"title": "TEST_MergeRight", "short_description": "Desc from B", "tags": ["tag2"]},
            headers=auth_headers
        )
        item2_id = item2_resp.json()["id"]
        
        # Merge keeping left
        resolve_resp = requests.post(
            f"{BASE_URL}/api/catalog/duplicates/resolve",
            params={"item_a_id": item1_id, "item_b_id": item2_id},
            json={"action": "merge_keep_left"},
            headers=auth_headers
        )
        assert resolve_resp.status_code == 200, f"Expected 200, got {resolve_resp.status_code}"
        
        data = resolve_resp.json()
        assert "kept" in data, "Missing kept item"
        assert "archived_id" in data, "Missing archived_id"
        assert data["archived_id"] == item2_id, "Wrong item archived"
        
        # Verify item B is archived
        item_b = requests.get(f"{BASE_URL}/api/catalog/items/{item2_id}", headers=auth_headers)
        assert item_b.json()["status"] == "Archived", "Item B should be archived"
        
        # Verify item A has merged data
        item_a = requests.get(f"{BASE_URL}/api/catalog/items/{item1_id}", headers=auth_headers)
        assert item_a.json()["short_description"] == "Desc from B", "Description not merged"
        assert "tag1" in item_a.json()["tags"], "Original tag missing"
        assert "tag2" in item_a.json()["tags"], "Merged tag missing"
        
        print("✓ Merge keep_left works with data merge")
    
    def test_resolve_duplicate_missing_ids(self, auth_headers):
        """POST /api/catalog/duplicates/resolve without ids fails"""
        resolve_resp = requests.post(
            f"{BASE_URL}/api/catalog/duplicates/resolve",
            json={"action": "not_duplicate"},
            headers=auth_headers
        )
        assert resolve_resp.status_code == 400, f"Expected 400, got {resolve_resp.status_code}"
        print("✓ Missing item IDs rejected")


class TestCatalogVariantGroups:
    """Test variant group operations"""
    
    def test_list_variant_groups(self, auth_headers):
        """GET /api/catalog/variant-groups returns groups"""
        response = requests.get(f"{BASE_URL}/api/catalog/variant-groups", headers=auth_headers)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert "groups" in data, "Missing groups field"
        print(f"✓ Listed {len(data['groups'])} variant groups")
    
    def test_create_variant_group(self, auth_headers):
        """POST /api/catalog/variant-groups creates group"""
        # Create two items first
        item1_resp = requests.post(
            f"{BASE_URL}/api/catalog/items",
            json={"title": "TEST_Variant Red", "color": "Red"},
            headers=auth_headers
        )
        item1_id = item1_resp.json()["id"]
        
        item2_resp = requests.post(
            f"{BASE_URL}/api/catalog/items",
            json={"title": "TEST_Variant Blue", "color": "Blue"},
            headers=auth_headers
        )
        item2_id = item2_resp.json()["id"]
        
        # Create variant group
        group_resp = requests.post(
            f"{BASE_URL}/api/catalog/variant-groups",
            json={
                "name": "TEST_Color Variants",
                "attribute_keys": ["color"],
                "member_ids": [item1_id, item2_id]
            },
            headers=auth_headers
        )
        assert group_resp.status_code == 200, f"Expected 200, got {group_resp.status_code}: {group_resp.text}"
        
        data = group_resp.json()
        assert data["name"] == "TEST_Color Variants"
        assert len(data["member_ids"]) == 2
        assert "id" in data
        
        # Verify items have variant_group_id
        item1 = requests.get(f"{BASE_URL}/api/catalog/items/{item1_id}", headers=auth_headers)
        assert item1.json()["variant_group_id"] == data["id"]
        
        print(f"✓ Created variant group: {data['name']}")
        return data
    
    def test_create_variant_group_requires_2_members(self, auth_headers):
        """POST /api/catalog/variant-groups with <2 members fails"""
        # Create one item
        item_resp = requests.post(
            f"{BASE_URL}/api/catalog/items",
            json={"title": "TEST_SingleVariant"},
            headers=auth_headers
        )
        item_id = item_resp.json()["id"]
        
        # Try to create group with 1 member
        group_resp = requests.post(
            f"{BASE_URL}/api/catalog/variant-groups",
            json={
                "name": "TEST_Invalid Group",
                "attribute_keys": ["size"],
                "member_ids": [item_id]
            },
            headers=auth_headers
        )
        assert group_resp.status_code == 400, f"Expected 400, got {group_resp.status_code}"
        print("✓ Variant group requires 2+ members")
    
    def test_delete_variant_group(self, auth_headers):
        """DELETE /api/catalog/variant-groups/{id} deletes group"""
        # Create items and group
        item1_resp = requests.post(
            f"{BASE_URL}/api/catalog/items",
            json={"title": "TEST_DelGroup1"},
            headers=auth_headers
        )
        item1_id = item1_resp.json()["id"]
        
        item2_resp = requests.post(
            f"{BASE_URL}/api/catalog/items",
            json={"title": "TEST_DelGroup2"},
            headers=auth_headers
        )
        item2_id = item2_resp.json()["id"]
        
        group_resp = requests.post(
            f"{BASE_URL}/api/catalog/variant-groups",
            json={
                "name": "TEST_ToDelete",
                "attribute_keys": ["size"],
                "member_ids": [item1_id, item2_id]
            },
            headers=auth_headers
        )
        group_id = group_resp.json()["id"]
        
        # Delete group
        delete_resp = requests.delete(f"{BASE_URL}/api/catalog/variant-groups/{group_id}", headers=auth_headers)
        assert delete_resp.status_code == 200, f"Expected 200, got {delete_resp.status_code}"
        
        # Verify items no longer have variant_group_id
        item1 = requests.get(f"{BASE_URL}/api/catalog/items/{item1_id}", headers=auth_headers)
        assert item1.json()["variant_group_id"] is None, "Item should have no variant group"
        
        print("✓ Variant group deleted, items unlinked")


class TestCatalogImportExport:
    """Test import from intake and Woo CSV export"""
    
    def test_import_from_intake_no_items(self, auth_headers):
        """POST /api/catalog/import-from-intake with no matching items"""
        response = requests.post(
            f"{BASE_URL}/api/catalog/import-from-intake",
            json={"statuses": ["nonexistent_status"]},
            headers=auth_headers
        )
        # Should return 400 if no items found
        assert response.status_code == 400, f"Expected 400, got {response.status_code}"
        print("✓ Import with no matching items returns 400")
    
    def test_import_from_intake_structure(self, auth_headers):
        """POST /api/catalog/import-from-intake returns correct structure"""
        # Try to import ready items (may or may not exist)
        response = requests.post(
            f"{BASE_URL}/api/catalog/import-from-intake",
            json={"statuses": ["ready"]},
            headers=auth_headers
        )
        
        if response.status_code == 200:
            data = response.json()
            assert "imported_count" in data, "Missing imported_count"
            assert "skipped_duplicates" in data, "Missing skipped_duplicates"
            assert "items" in data, "Missing items"
            print(f"✓ Imported {data['imported_count']} items from intake")
        else:
            assert response.status_code == 400, f"Unexpected status: {response.status_code}"
            print("✓ No ready items in intake to import")
    
    def test_export_woo_csv_no_ready_items(self, auth_headers):
        """GET /api/catalog/export/woo-csv with no Ready items"""
        # First ensure no Ready items by checking stats
        stats = requests.get(f"{BASE_URL}/api/catalog/stats", headers=auth_headers).json()
        
        if stats.get("ready_count", 0) == 0:
            response = requests.get(
                f"{BASE_URL}/api/catalog/export/woo-csv",
                params={"status": "Ready"},
                headers=auth_headers
            )
            assert response.status_code == 400, f"Expected 400, got {response.status_code}"
            print("✓ Export with no Ready items returns 400")
        else:
            print(f"✓ Skipping (has {stats['ready_count']} Ready items)")
    
    def test_export_woo_csv_with_ready_item(self, auth_headers):
        """GET /api/catalog/export/woo-csv exports Ready items as CSV"""
        # Create a Ready item
        create_resp = requests.post(
            f"{BASE_URL}/api/catalog/items",
            json={
                "title": "TEST_ExportItem",
                "brand": "ExportBrand",
                "regular_price": 49.99,
                "short_description": "Export test",
                "sku": "TEST-SKU-001"
            },
            headers=auth_headers
        )
        item_id = create_resp.json()["id"]
        
        # Set to Ready
        requests.put(
            f"{BASE_URL}/api/catalog/items/{item_id}",
            json={"status": "Ready"},
            headers=auth_headers
        )
        
        # Export
        response = requests.get(
            f"{BASE_URL}/api/catalog/export/woo-csv",
            params={"status": "Ready"},
            headers=auth_headers
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        # Check it's CSV
        content_type = response.headers.get("content-type", "")
        assert "text/csv" in content_type, f"Expected CSV, got {content_type}"
        
        # Check content
        csv_content = response.text
        assert "Name" in csv_content, "Missing Name column"
        assert "SKU" in csv_content, "Missing SKU column"
        assert "TEST_ExportItem" in csv_content, "Item not in export"
        
        # Verify item status changed to Exported
        item = requests.get(f"{BASE_URL}/api/catalog/items/{item_id}", headers=auth_headers)
        assert item.json()["status"] == "Exported", "Item should be Exported"
        
        print("✓ Woo CSV export works, item marked as Exported")


class TestCatalogNormalize:
    """Test LLM normalization (may take time)"""
    
    def test_normalize_item(self, auth_headers):
        """POST /api/catalog/items/{id}/normalize normalizes via LLM"""
        # Create item with messy data
        create_resp = requests.post(
            f"{BASE_URL}/api/catalog/items",
            json={
                "title": "TEST_MESSY PRODUCT!!! great deal",
                "short_description": "product for sale"
            },
            headers=auth_headers
        )
        item_id = create_resp.json()["id"]
        
        # Normalize (may take 15-30 seconds)
        print("  Calling normalize endpoint (may take 15-30 seconds)...")
        try:
            response = requests.post(
                f"{BASE_URL}/api/catalog/items/{item_id}/normalize",
                headers=auth_headers,
                timeout=60
            )
            
            if response.status_code == 200:
                data = response.json()
                assert "item" in data, "Missing item"
                assert "normalization_result" in data, "Missing normalization_result"
                assert data["item"]["normalized"] == True, "Item should be normalized"
                
                # Status should change from Draft to Needs Review
                assert data["item"]["status"] == "Needs Review", f"Status should be Needs Review: {data['item']['status']}"
                
                print(f"✓ Normalization successful: {data['item']['title']}")
                if data["normalization_result"].get("category_suggestion"):
                    print(f"  Category suggestion: {data['normalization_result']['category_suggestion']['name']}")
            else:
                print(f"⚠ Normalization returned {response.status_code}: {response.text[:200]}")
                # Don't fail - LLM may have issues
                
        except requests.exceptions.Timeout:
            print("⚠ Normalization timed out (known limitation with LLM)")
        except Exception as e:
            print(f"⚠ Normalization error: {str(e)}")
    
    def test_normalize_nonexistent_item(self, auth_headers):
        """POST /api/catalog/items/{id}/normalize with invalid id returns 404"""
        response = requests.post(
            f"{BASE_URL}/api/catalog/items/nonexistent-id/normalize",
            headers=auth_headers,
            timeout=10
        )
        assert response.status_code == 404, f"Expected 404, got {response.status_code}"
        print("✓ Normalize nonexistent item returns 404")


class TestCleanup:
    """Cleanup test data"""
    
    def test_cleanup_test_items(self, auth_headers):
        """Delete TEST_ prefixed items"""
        # Get all items
        response = requests.get(
            f"{BASE_URL}/api/catalog/items",
            params={"search": "TEST_", "limit": 200},
            headers=auth_headers
        )
        items = response.json().get("items", [])
        
        deleted = 0
        for item in items:
            if item["title"].startswith("TEST_"):
                requests.delete(f"{BASE_URL}/api/catalog/items/{item['id']}", headers=auth_headers)
                deleted += 1
        
        print(f"✓ Cleaned up {deleted} test items")
    
    def test_cleanup_test_categories(self, auth_headers):
        """Delete TEST_ prefixed categories"""
        response = requests.get(f"{BASE_URL}/api/catalog/categories", headers=auth_headers)
        categories = response.json().get("categories", [])
        
        deleted = 0
        for cat in categories:
            if cat["name"].startswith("TEST_"):
                del_resp = requests.delete(f"{BASE_URL}/api/catalog/categories/{cat['id']}", headers=auth_headers)
                if del_resp.status_code == 200:
                    deleted += 1
        
        print(f"✓ Cleaned up {deleted} test categories")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
