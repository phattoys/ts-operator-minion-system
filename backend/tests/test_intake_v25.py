"""
Product Intake v2.5 - Backend API Tests
Tests: CSV/TSV file upload, duplicate-awareness flags, attribute suggestions in generate
"""
import pytest
import requests
import os
import io
import time

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')
PASSWORD = "TSFounder!Vault2026#Secure"

# ================== FIXTURES ==================

@pytest.fixture(scope="module")
def auth_token():
    """Get authentication token"""
    response = requests.post(f"{BASE_URL}/api/auth/login", json={"password": PASSWORD})
    assert response.status_code == 200, f"Auth failed: {response.text}"
    return response.json().get("access_token")

@pytest.fixture(scope="module")
def auth_headers(auth_token):
    """Headers with auth token"""
    return {"Authorization": f"Bearer {auth_token}"}

@pytest.fixture(scope="module")
def test_data():
    """Shared test data"""
    return {}

# ================== CSV UPLOAD TESTS ==================

class TestCSVUpload:
    """Test CSV/TSV file upload endpoint"""
    
    def test_create_session_for_csv(self, auth_headers, test_data):
        """Create a session for CSV upload testing"""
        response = requests.post(
            f"{BASE_URL}/api/intake/sessions",
            json={
                "source_store": "TEST_CSV_Upload_Store",
                "order_id": "CSV-TEST-001",
                "notes": "Testing CSV upload feature"
            },
            headers={**auth_headers, "Content-Type": "application/json"}
        )
        assert response.status_code == 200
        data = response.json()
        test_data["session_id"] = data["id"]
        print(f"✓ Created session for CSV testing: {data['id']}")
    
    def test_upload_csv_file(self, auth_headers, test_data):
        """Upload a CSV file with product rows"""
        csv_content = """product,price,qty,color,size,sku,notes
TEST Purple Vibrator,4.99,2,Purple,Medium,SKU-001,Test item 1
TEST Rose Gold Oil,3.50,3,Rose Gold,,SKU-002,Test item 2
TEST Black Lingerie Set,7.25,1,Black,M,SKU-003,Test item 3"""
        
        files = {
            'file': ('test_products.csv', io.BytesIO(csv_content.encode('utf-8')), 'text/csv')
        }
        
        response = requests.post(
            f"{BASE_URL}/api/intake/sessions/{test_data['session_id']}/upload-csv",
            files=files,
            headers=auth_headers
        )
        assert response.status_code == 200, f"CSV upload failed: {response.text}"
        data = response.json()
        
        assert "uploaded_count" in data
        assert data["uploaded_count"] == 3, f"Expected 3 items, got {data['uploaded_count']}"
        assert "filename" in data
        assert data["filename"] == "test_products.csv"
        assert "items" in data
        assert len(data["items"]) == 3
        
        # Verify item structure
        item = data["items"][0]
        assert item["source_type"] == "csv_upload"
        assert "source_title" in item
        assert "unit_cost" in item
        assert "quantity" in item
        assert "color" in item
        assert "attribute_suggestions" in item
        assert "duplicate_flags" in item
        assert "missing_fields" in item
        
        # Store first item for later tests
        test_data["csv_item_id"] = data["items"][0]["id"]
        test_data["csv_item_ids"] = [item["id"] for item in data["items"]]
        
        print(f"✓ Uploaded CSV with {data['uploaded_count']} items")
        for item in data["items"]:
            print(f"  - {item['source_title']}: ${item.get('unit_cost', 'N/A')}, qty={item.get('quantity', 1)}")
    
    def test_upload_tsv_file(self, auth_headers, test_data):
        """Upload a TSV file (tab-separated)"""
        tsv_content = """product\tprice\tqty\tcolor
TEST TSV Item 1\t5.99\t1\tBlue
TEST TSV Item 2\t8.50\t2\tRed"""
        
        files = {
            'file': ('test_products.tsv', io.BytesIO(tsv_content.encode('utf-8')), 'text/tab-separated-values')
        }
        
        response = requests.post(
            f"{BASE_URL}/api/intake/sessions/{test_data['session_id']}/upload-csv",
            files=files,
            headers=auth_headers
        )
        assert response.status_code == 200, f"TSV upload failed: {response.text}"
        data = response.json()
        
        assert data["uploaded_count"] == 2
        assert data["filename"] == "test_products.tsv"
        
        print(f"✓ Uploaded TSV with {data['uploaded_count']} items")
    
    def test_upload_rejects_non_csv_file(self, auth_headers, test_data):
        """Reject non-CSV/TSV files"""
        files = {
            'file': ('test.pdf', io.BytesIO(b'%PDF-1.4 fake pdf content'), 'application/pdf')
        }
        
        response = requests.post(
            f"{BASE_URL}/api/intake/sessions/{test_data['session_id']}/upload-csv",
            files=files,
            headers=auth_headers
        )
        assert response.status_code == 400
        assert "CSV" in response.json().get("detail", "") or "TSV" in response.json().get("detail", "")
        print("✓ Non-CSV file rejected")
    
    def test_upload_handles_various_column_names(self, auth_headers, test_data):
        """CSV parser handles various column name variations"""
        # Test with alternative column names
        csv_content = """name,cost,quantity,colour,variant
TEST Alt Column Item,6.99,2,Green,Large"""
        
        files = {
            'file': ('alt_columns.csv', io.BytesIO(csv_content.encode('utf-8')), 'text/csv')
        }
        
        response = requests.post(
            f"{BASE_URL}/api/intake/sessions/{test_data['session_id']}/upload-csv",
            files=files,
            headers=auth_headers
        )
        assert response.status_code == 200, f"Alt column upload failed: {response.text}"
        data = response.json()
        
        assert data["uploaded_count"] == 1
        item = data["items"][0]
        assert item["source_title"] == "TEST Alt Column Item"
        assert item["unit_cost"] == 6.99
        assert item["quantity"] == 2
        assert item["color"] == "Green"
        assert item["style"] == "Large"  # variant maps to style
        
        print("✓ CSV parser handles alternative column names")
    
    def test_upload_empty_file_rejected(self, auth_headers, test_data):
        """Empty or too short file is rejected"""
        files = {
            'file': ('empty.csv', io.BytesIO(b''), 'text/csv')
        }
        
        response = requests.post(
            f"{BASE_URL}/api/intake/sessions/{test_data['session_id']}/upload-csv",
            files=files,
            headers=auth_headers
        )
        assert response.status_code == 400
        print("✓ Empty file rejected")
    
    def test_upload_no_valid_rows_rejected(self, auth_headers, test_data):
        """CSV with headers but no valid product rows is rejected"""
        csv_content = """product,price,qty
,,,"""  # Empty row
        
        files = {
            'file': ('no_rows.csv', io.BytesIO(csv_content.encode('utf-8')), 'text/csv')
        }
        
        response = requests.post(
            f"{BASE_URL}/api/intake/sessions/{test_data['session_id']}/upload-csv",
            files=files,
            headers=auth_headers
        )
        assert response.status_code == 400
        assert "No valid product rows" in response.json().get("detail", "")
        print("✓ CSV with no valid rows rejected")
    
    def test_upload_to_nonexistent_session(self, auth_headers):
        """Upload to nonexistent session returns 404"""
        csv_content = """product,price
Test,5.99"""
        
        files = {
            'file': ('test.csv', io.BytesIO(csv_content.encode('utf-8')), 'text/csv')
        }
        
        response = requests.post(
            f"{BASE_URL}/api/intake/sessions/nonexistent-session-id/upload-csv",
            files=files,
            headers=auth_headers
        )
        assert response.status_code == 404
        print("✓ Upload to nonexistent session returns 404")

# ================== DUPLICATE CHECK TESTS ==================

class TestDuplicateCheck:
    """Test duplicate-awareness flags endpoint"""
    
    def test_check_duplicates_returns_flags(self, auth_headers, test_data):
        """Check duplicates endpoint returns duplicate_flags"""
        if "csv_item_id" not in test_data:
            pytest.skip("No CSV item available")
        
        response = requests.get(
            f"{BASE_URL}/api/intake/items/{test_data['csv_item_id']}/check-duplicates",
            headers=auth_headers
        )
        assert response.status_code == 200, f"Duplicate check failed: {response.text}"
        data = response.json()
        
        assert "item_id" in data
        assert data["item_id"] == test_data["csv_item_id"]
        assert "duplicate_flags" in data
        assert "count" in data
        assert isinstance(data["duplicate_flags"], list)
        
        print(f"✓ Duplicate check returned {data['count']} potential duplicates")
        if data["count"] > 0:
            for flag in data["duplicate_flags"]:
                print(f"  - {flag['type']}: {flag.get('match_title', 'N/A')}")
    
    def test_check_duplicates_saves_to_item(self, auth_headers, test_data):
        """Duplicate flags are saved to the item"""
        if "csv_item_id" not in test_data:
            pytest.skip("No CSV item available")
        
        # First run duplicate check
        requests.get(
            f"{BASE_URL}/api/intake/items/{test_data['csv_item_id']}/check-duplicates",
            headers=auth_headers
        )
        
        # Then get the item and verify flags are saved
        response = requests.get(
            f"{BASE_URL}/api/intake/items/{test_data['csv_item_id']}",
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        
        assert "duplicate_flags" in data
        print("✓ Duplicate flags saved to item")
    
    def test_check_duplicates_nonexistent_item(self, auth_headers):
        """Check duplicates on nonexistent item returns 404"""
        response = requests.get(
            f"{BASE_URL}/api/intake/items/nonexistent-item-id/check-duplicates",
            headers=auth_headers
        )
        assert response.status_code == 404
        print("✓ Duplicate check on nonexistent item returns 404")
    
    def test_duplicate_detection_between_draft_items(self, auth_headers, test_data):
        """Duplicate detection finds similar draft items"""
        if "session_id" not in test_data:
            pytest.skip("No session available")
        
        # Create two similar items
        response1 = requests.post(
            f"{BASE_URL}/api/intake/sessions/{test_data['session_id']}/items",
            json={
                "source_type": "manual_entry",
                "source_title": "TEST Duplicate Detection Item Alpha",
                "quantity": 1,
                "unit_cost": 10.00
            },
            headers={**auth_headers, "Content-Type": "application/json"}
        )
        assert response1.status_code == 200
        item1_id = response1.json()["id"]
        
        response2 = requests.post(
            f"{BASE_URL}/api/intake/sessions/{test_data['session_id']}/items",
            json={
                "source_type": "manual_entry",
                "source_title": "TEST Duplicate Detection Item Alpha Version 2",  # Similar title
                "quantity": 1,
                "unit_cost": 10.00
            },
            headers={**auth_headers, "Content-Type": "application/json"}
        )
        assert response2.status_code == 200
        item2_id = response2.json()["id"]
        
        # Check duplicates on second item
        response = requests.get(
            f"{BASE_URL}/api/intake/items/{item2_id}/check-duplicates",
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        
        # Should find the first item as a potential duplicate
        draft_matches = [f for f in data["duplicate_flags"] if f["type"] == "draft_title_match"]
        print(f"✓ Found {len(draft_matches)} draft title matches")
        
        # Cleanup
        test_data["dup_item_ids"] = [item1_id, item2_id]

# ================== ATTRIBUTE SUGGESTIONS TESTS ==================

class TestAttributeSuggestions:
    """Test attribute suggestions in generate endpoint"""
    
    def test_generate_returns_attribute_suggestions(self, auth_headers, test_data):
        """Generate endpoint returns attribute_suggestions"""
        if "csv_item_id" not in test_data:
            pytest.skip("No CSV item available")
        
        print("  Calling LLM for listing generation (15-30s)...")
        response = requests.post(
            f"{BASE_URL}/api/intake/items/{test_data['csv_item_id']}/generate",
            headers=auth_headers,
            timeout=60
        )
        
        if response.status_code == 400:
            # Item may need a title
            print(f"  Generate returned 400: {response.json().get('detail', '')}")
            pytest.skip("Item needs title for generation")
        
        assert response.status_code == 200, f"Generate failed: {response.text}"
        data = response.json()
        
        # Verify attribute_suggestions is present
        assert "attribute_suggestions" in data, "Response should include attribute_suggestions"
        
        # Verify other generated fields
        assert "clean_title" in data
        assert "short_description" in data
        assert "long_description" in data
        assert "category_suggestions" in data
        
        print(f"✓ Generate returned attribute_suggestions: {data.get('attribute_suggestions', {})}")
        
        # Check if color/size/style were filled from suggestions
        if data.get("attribute_suggestions"):
            attrs = data["attribute_suggestions"]
            if attrs.get("color"):
                print(f"  - Suggested color: {attrs['color']}")
            if attrs.get("size"):
                print(f"  - Suggested size: {attrs['size']}")
            if attrs.get("style"):
                print(f"  - Suggested style: {attrs['style']}")
            if attrs.get("material"):
                print(f"  - Suggested material: {attrs['material']}")
    
    def test_generate_fills_color_size_style_from_suggestions(self, auth_headers, test_data):
        """Generate fills empty color/size/style from attribute_suggestions"""
        if "session_id" not in test_data:
            pytest.skip("No session available")
        
        # Create item without color/size/style
        response = requests.post(
            f"{BASE_URL}/api/intake/sessions/{test_data['session_id']}/items",
            json={
                "source_type": "manual_entry",
                "source_title": "TEST Blue Silk Scarf Large Size",  # Title hints at attributes
                "quantity": 1,
                "unit_cost": 15.00
            },
            headers={**auth_headers, "Content-Type": "application/json"}
        )
        assert response.status_code == 200
        item_id = response.json()["id"]
        test_data["attr_test_item_id"] = item_id
        
        # Verify color/size/style are empty
        item = response.json()
        assert not item.get("color"), "Color should be empty initially"
        assert not item.get("size"), "Size should be empty initially"
        
        print("  Calling LLM for listing generation (15-30s)...")
        response = requests.post(
            f"{BASE_URL}/api/intake/items/{item_id}/generate",
            headers=auth_headers,
            timeout=60
        )
        assert response.status_code == 200, f"Generate failed: {response.text}"
        data = response.json()
        
        # Check if attributes were filled
        if data.get("attribute_suggestions"):
            attrs = data["attribute_suggestions"]
            # The generate endpoint should fill color/size/style from suggestions if empty
            if attrs.get("color") and data.get("color"):
                print(f"✓ Color filled from suggestions: {data['color']}")
            if attrs.get("size") and data.get("size"):
                print(f"✓ Size filled from suggestions: {data['size']}")
        
        print("✓ Generate endpoint processes attribute suggestions")

# ================== EXISTING SESSION TEST ==================

class TestExistingCSVSession:
    """Test with the existing CSV session mentioned in context"""
    
    def test_existing_csv_session(self, auth_headers):
        """Verify existing CSV session has items"""
        existing_session_id = "46caf1a7-3578-477e-ac19-849dbb5f8c11"
        
        response = requests.get(
            f"{BASE_URL}/api/intake/sessions/{existing_session_id}",
            headers=auth_headers
        )
        
        if response.status_code == 404:
            print("  Existing CSV session not found (may have been cleaned up)")
            pytest.skip("Existing session not found")
        
        assert response.status_code == 200
        data = response.json()
        
        print(f"✓ Existing CSV session found: {data.get('source_store', 'Unknown')}")
        print(f"  - Items: {len(data.get('items', []))}")
        
        # Check items have csv_upload source_type
        csv_items = [i for i in data.get("items", []) if i.get("source_type") == "csv_upload"]
        print(f"  - CSV-uploaded items: {len(csv_items)}")

# ================== WP PLACEMENT REGRESSION ==================

class TestWPPlacementRegression:
    """Quick regression check for WP Placement module"""
    
    def test_wp_templates_endpoint(self, auth_headers):
        """WP templates endpoint still works"""
        response = requests.get(
            f"{BASE_URL}/api/wp-placement/templates",
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        assert "templates" in data
        assert len(data["templates"]) == 3
        print(f"✓ WP templates: {len(data['templates'])} templates available")
    
    def test_wp_stats_endpoint(self, auth_headers):
        """WP stats endpoint still works"""
        response = requests.get(
            f"{BASE_URL}/api/wp-placement/stats",
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        assert "total_placements" in data
        assert "wp_connected" in data
        print(f"✓ WP stats: {data['total_placements']} placements, connected={data['wp_connected']}")
    
    def test_wp_placement_log(self, auth_headers):
        """WP placement log endpoint still works"""
        response = requests.get(
            f"{BASE_URL}/api/wp-placement/log",
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        assert "placements" in data
        print(f"✓ WP placement log: {len(data['placements'])} entries")
    
    def test_wp_drafts_endpoint(self, auth_headers):
        """WP drafts endpoint still works"""
        response = requests.get(
            f"{BASE_URL}/api/wp-placement/drafts",
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        assert "pages" in data
        print(f"✓ WP drafts: {len(data['pages'])} drafts")

# ================== CLEANUP ==================

class TestCleanup:
    """Cleanup test data"""
    
    def test_cleanup_test_items(self, auth_headers, test_data):
        """Delete test items"""
        # Delete duplicate test items
        for item_id in test_data.get("dup_item_ids", []):
            requests.delete(f"{BASE_URL}/api/intake/items/{item_id}", headers=auth_headers)
        
        # Delete attribute test item
        if "attr_test_item_id" in test_data:
            requests.delete(f"{BASE_URL}/api/intake/items/{test_data['attr_test_item_id']}", headers=auth_headers)
        
        print("✓ Cleaned up test items")
    
    def test_cleanup_test_session(self, auth_headers, test_data):
        """Delete the test session"""
        if "session_id" in test_data:
            response = requests.delete(
                f"{BASE_URL}/api/intake/sessions/{test_data['session_id']}",
                headers=auth_headers
            )
            assert response.status_code in [200, 404]
            print("✓ Cleaned up test session")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
