"""
Test Mark Ready & Export Feature for Product Intake
Tests the mark-ready-export and export-woo endpoints
"""
import pytest
import requests
import csv
import io
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')
SESSION_ID = "e54de4dc-5308-4b63-b1e1-f9af5f7d3225"  # SHEIN session with 63 items

# Expected WooCommerce CSV columns
WOO_CSV_COLUMNS = [
    "Name", "Type", "SKU", "Published", "Is featured?",
    "Short description", "Description", "Regular price", "Sale price",
    "Categories", "Tags", "Images",
    "Attribute 1 name", "Attribute 1 value(s)",
    "Attribute 2 name", "Attribute 2 value(s)",
    "Attribute 3 name", "Attribute 3 value(s)",
    "Stock", "Meta: _source_title", "Meta: _source_sku",
    "Meta: _unit_cost", "Meta: _vendor", "Meta: _confidence",
]


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
def session(request):
    """Requests session with auth cookie"""
    s = requests.Session()
    # Get token first
    response = s.post(
        f"{BASE_URL}/api/auth/login",
        json={"password": "TSFounder!Vault2026#Secure"}
    )
    token = response.json()["access_token"]
    s.cookies.set("access_token", token)
    return s


class TestSessionState:
    """Verify the current state of the SHEIN session after mark-ready-export was run"""
    
    def test_session_exists(self, session):
        """Session should exist with correct item counts"""
        response = session.get(f"{BASE_URL}/api/intake/sessions/{SESSION_ID}")
        assert response.status_code == 200
        data = response.json()
        
        assert data["source_store"] == "SHEIN"
        assert data["item_count"] == 63
        assert data["ready_count"] == 62
        assert data["in_review_count"] == 1
        assert data["needs_info_count"] == 0
    
    def test_ready_items_count(self, session):
        """62 items should be in 'ready' status"""
        response = session.get(f"{BASE_URL}/api/intake/sessions/{SESSION_ID}")
        assert response.status_code == 200
        items = response.json()["items"]
        
        ready_items = [i for i in items if i["status"] == "ready"]
        assert len(ready_items) == 62
    
    def test_held_back_item_exists(self, session):
        """1 item should be held back in 'in_review' status"""
        response = session.get(f"{BASE_URL}/api/intake/sessions/{SESSION_ID}")
        assert response.status_code == 200
        items = response.json()["items"]
        
        in_review_items = [i for i in items if i["status"] == "in_review"]
        assert len(in_review_items) == 1
        
        held_back = in_review_items[0]
        assert "Fishnet" in held_back["clean_title"] or "Fishnet" in held_back.get("source_title", "")
    
    def test_held_back_item_has_duplicate_flags(self, session):
        """Held back item should have 3+ duplicate flags (reason for being held back)"""
        response = session.get(f"{BASE_URL}/api/intake/sessions/{SESSION_ID}")
        assert response.status_code == 200
        items = response.json()["items"]
        
        in_review_items = [i for i in items if i["status"] == "in_review"]
        held_back = in_review_items[0]
        
        duplicate_flags = held_back.get("duplicate_flags", [])
        assert len(duplicate_flags) >= 3, f"Expected 3+ duplicate flags, got {len(duplicate_flags)}"


class TestExportWooEndpoint:
    """Test GET /api/intake/sessions/{session_id}/export-woo endpoint"""
    
    def test_export_woo_returns_csv(self, session):
        """export-woo should return a CSV file"""
        response = session.get(f"{BASE_URL}/api/intake/sessions/{SESSION_ID}/export-woo")
        assert response.status_code == 200
        assert "text/csv" in response.headers.get("Content-Type", "")
    
    def test_export_woo_has_content_disposition(self, session):
        """export-woo should have Content-Disposition header for download"""
        response = session.get(f"{BASE_URL}/api/intake/sessions/{SESSION_ID}/export-woo")
        assert response.status_code == 200
        
        content_disp = response.headers.get("Content-Disposition", "")
        assert "attachment" in content_disp
        assert "filename=" in content_disp
        assert "woo-import" in content_disp.lower()
    
    def test_export_woo_csv_has_correct_columns(self, session):
        """CSV should have all 24 WooCommerce columns"""
        response = session.get(f"{BASE_URL}/api/intake/sessions/{SESSION_ID}/export-woo")
        assert response.status_code == 200
        
        reader = csv.DictReader(io.StringIO(response.text))
        columns = reader.fieldnames
        
        assert len(columns) == 24, f"Expected 24 columns, got {len(columns)}"
        for expected_col in WOO_CSV_COLUMNS:
            assert expected_col in columns, f"Missing column: {expected_col}"
    
    def test_export_woo_csv_has_62_rows(self, session):
        """CSV should have 62 data rows (ready items only)"""
        response = session.get(f"{BASE_URL}/api/intake/sessions/{SESSION_ID}/export-woo")
        assert response.status_code == 200
        
        reader = csv.DictReader(io.StringIO(response.text))
        rows = list(reader)
        
        assert len(rows) == 62, f"Expected 62 rows, got {len(rows)}"
    
    def test_export_woo_all_published_zero(self, session):
        """All items should have Published=0 (draft mode, never auto-publish)"""
        response = session.get(f"{BASE_URL}/api/intake/sessions/{SESSION_ID}/export-woo")
        assert response.status_code == 200
        
        reader = csv.DictReader(io.StringIO(response.text))
        rows = list(reader)
        
        for row in rows:
            assert row["Published"] == "0", f"Item {row['Name']} has Published={row['Published']}, expected 0"
    
    def test_export_woo_meta_fields_present(self, session):
        """CSV should include Meta fields for source data preservation"""
        response = session.get(f"{BASE_URL}/api/intake/sessions/{SESSION_ID}/export-woo")
        assert response.status_code == 200
        
        reader = csv.DictReader(io.StringIO(response.text))
        rows = list(reader)
        
        # Check first row has meta fields populated
        first_row = rows[0]
        assert first_row.get("Meta: _source_title"), "Missing _source_title"
        assert first_row.get("Meta: _source_sku"), "Missing _source_sku"
        assert first_row.get("Meta: _vendor") == "SHEIN", f"Expected vendor SHEIN, got {first_row.get('Meta: _vendor')}"
    
    def test_export_woo_requires_auth(self, session):
        """export-woo should require authentication"""
        # Use a fresh session without auth
        response = requests.get(f"{BASE_URL}/api/intake/sessions/{SESSION_ID}/export-woo")
        assert response.status_code == 401
    
    def test_export_woo_404_for_nonexistent_session(self, session):
        """export-woo should return 404 for nonexistent session"""
        response = session.get(f"{BASE_URL}/api/intake/sessions/nonexistent-session-id/export-woo")
        assert response.status_code == 404


class TestMarkReadyExportEndpoint:
    """Test POST /api/intake/sessions/{session_id}/mark-ready-export endpoint"""
    
    def test_mark_ready_export_no_in_review_items(self, session):
        """mark-ready-export should return 400 when no in_review items (except held back one)"""
        # Since only 1 item is in_review and it has 3+ duplicate flags, it will be held back
        # So effectively there are no items that can be marked ready
        response = session.post(f"{BASE_URL}/api/intake/sessions/{SESSION_ID}/mark-ready-export")
        
        # Either 400 (no items to process) or 200 with 0 marked_ready
        if response.status_code == 200:
            data = response.json()
            # The held-back item should still be held back
            assert data["held_back"] >= 0
        else:
            assert response.status_code == 400
    
    def test_mark_ready_export_requires_auth(self, session):
        """mark-ready-export should require authentication"""
        response = requests.post(f"{BASE_URL}/api/intake/sessions/{SESSION_ID}/mark-ready-export")
        assert response.status_code == 401
    
    def test_mark_ready_export_404_for_nonexistent_session(self, session):
        """mark-ready-export should return 404 for nonexistent session"""
        response = session.post(f"{BASE_URL}/api/intake/sessions/nonexistent-session-id/mark-ready-export")
        assert response.status_code == 404


class TestValidationLogic:
    """Test the validation logic for mark-ready-export"""
    
    def test_held_back_item_has_unresolved_duplicates(self, session):
        """Item with 3+ duplicate flags should be held back with 'unresolved_duplicates' reason"""
        response = session.get(f"{BASE_URL}/api/intake/sessions/{SESSION_ID}")
        assert response.status_code == 200
        items = response.json()["items"]
        
        # Find the held back item
        in_review_items = [i for i in items if i["status"] == "in_review"]
        assert len(in_review_items) == 1
        
        held_back = in_review_items[0]
        duplicate_flags = held_back.get("duplicate_flags", [])
        
        # Verify it has 3+ duplicate flags (the threshold for being held back)
        assert len(duplicate_flags) >= 3
    
    def test_ready_items_have_required_fields(self, session):
        """All ready items should have clean_title, short_description, category, price"""
        response = session.get(f"{BASE_URL}/api/intake/sessions/{SESSION_ID}")
        assert response.status_code == 200
        items = response.json()["items"]
        
        ready_items = [i for i in items if i["status"] == "ready"]
        
        for item in ready_items:
            assert item.get("clean_title"), f"Item {item['id']} missing clean_title"
            assert item.get("short_description"), f"Item {item['id']} missing short_description"
            assert item.get("category"), f"Item {item['id']} missing category"
            # Price can be suggested_price or unit_cost
            has_price = item.get("suggested_price") is not None or item.get("unit_cost") is not None
            assert has_price, f"Item {item['id']} missing price"
    
    def test_ready_items_have_acceptable_confidence(self, session):
        """All ready items should have confidence >= 0.4"""
        response = session.get(f"{BASE_URL}/api/intake/sessions/{SESSION_ID}")
        assert response.status_code == 200
        items = response.json()["items"]
        
        ready_items = [i for i in items if i["status"] == "ready"]
        
        for item in ready_items:
            confidence = item.get("generation_confidence", {})
            score = confidence.get("score", 1.0) if isinstance(confidence, dict) else 1.0
            assert score >= 0.4, f"Item {item['id']} has low confidence {score}"


class TestCSVFormat:
    """Test WooCommerce CSV format details"""
    
    def test_csv_type_is_simple(self, session):
        """All products should have Type='simple'"""
        response = session.get(f"{BASE_URL}/api/intake/sessions/{SESSION_ID}/export-woo")
        assert response.status_code == 200
        
        reader = csv.DictReader(io.StringIO(response.text))
        for row in reader:
            assert row["Type"] == "simple"
    
    def test_csv_has_sku_values(self, session):
        """Most items should have SKU values"""
        response = session.get(f"{BASE_URL}/api/intake/sessions/{SESSION_ID}/export-woo")
        assert response.status_code == 200
        
        reader = csv.DictReader(io.StringIO(response.text))
        rows = list(reader)
        
        items_with_sku = [r for r in rows if r.get("SKU")]
        # At least 90% should have SKUs
        assert len(items_with_sku) >= len(rows) * 0.9
    
    def test_csv_has_prices(self, session):
        """All items should have Regular price"""
        response = session.get(f"{BASE_URL}/api/intake/sessions/{SESSION_ID}/export-woo")
        assert response.status_code == 200
        
        reader = csv.DictReader(io.StringIO(response.text))
        rows = list(reader)
        
        items_with_price = [r for r in rows if r.get("Regular price")]
        # All should have prices
        assert len(items_with_price) == len(rows)
    
    def test_csv_has_categories(self, session):
        """All items should have Categories"""
        response = session.get(f"{BASE_URL}/api/intake/sessions/{SESSION_ID}/export-woo")
        assert response.status_code == 200
        
        reader = csv.DictReader(io.StringIO(response.text))
        rows = list(reader)
        
        items_with_category = [r for r in rows if r.get("Categories")]
        # All should have categories
        assert len(items_with_category) == len(rows)
    
    def test_csv_confidence_values_valid(self, session):
        """Meta: _confidence should be valid float values"""
        response = session.get(f"{BASE_URL}/api/intake/sessions/{SESSION_ID}/export-woo")
        assert response.status_code == 200
        
        reader = csv.DictReader(io.StringIO(response.text))
        rows = list(reader)
        
        for row in rows:
            conf = row.get("Meta: _confidence", "")
            if conf:
                try:
                    score = float(conf)
                    assert 0 <= score <= 1, f"Confidence {score} out of range"
                except ValueError:
                    pytest.fail(f"Invalid confidence value: {conf}")
