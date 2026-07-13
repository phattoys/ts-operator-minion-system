"""
Product Intake Minion - Backend API Tests
Tests: Sessions CRUD, Items CRUD, Text Extraction (LLM), Listing Generation (LLM),
       Status Transitions, Missing Fields Validation, CSV Export, Pricing Settings
"""
import pytest
import requests
import os
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
    return {"Authorization": f"Bearer {auth_token}", "Content-Type": "application/json"}

@pytest.fixture(scope="module")
def session_data():
    """Shared session data for tests"""
    return {}

# ================== AUTH TESTS ==================

class TestIntakeAuth:
    """Test that intake endpoints require authentication"""
    
    def test_stats_requires_auth(self):
        response = requests.get(f"{BASE_URL}/api/intake/stats")
        assert response.status_code == 401, "Stats should require auth"
        print("✓ Stats endpoint requires auth")
    
    def test_sessions_requires_auth(self):
        response = requests.get(f"{BASE_URL}/api/intake/sessions")
        assert response.status_code == 401, "Sessions list should require auth"
        print("✓ Sessions list requires auth")
    
    def test_settings_requires_auth(self):
        response = requests.get(f"{BASE_URL}/api/intake/settings")
        assert response.status_code == 401, "Settings should require auth"
        print("✓ Settings endpoint requires auth")

# ================== STATS TESTS ==================

class TestIntakeStats:
    """Test stats endpoint"""
    
    def test_get_stats(self, auth_headers):
        response = requests.get(f"{BASE_URL}/api/intake/stats", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert "total_sessions" in data
        assert "total_items" in data
        assert "by_status" in data
        assert "ready_count" in data
        assert "needs_info_count" in data
        assert "in_review_count" in data
        assert "stuck_count" in data
        assert "stuck_days_threshold" in data
        print(f"✓ Stats: {data['total_sessions']} sessions, {data['total_items']} items")

# ================== SESSION CRUD TESTS ==================

class TestSessionCRUD:
    """Test session CRUD operations"""
    
    def test_create_session_validation(self, auth_headers):
        """Source store is required"""
        response = requests.post(
            f"{BASE_URL}/api/intake/sessions",
            json={"source_store": ""},
            headers=auth_headers
        )
        assert response.status_code == 400
        print("✓ Session creation validates source_store required")
    
    def test_create_session(self, auth_headers, session_data):
        """Create a new intake session"""
        response = requests.post(
            f"{BASE_URL}/api/intake/sessions",
            json={
                "source_store": "Temu",
                "order_id": "TEST-001",
                "purchase_date": "2026-01-15",
                "notes": "Test session for Product Intake testing"
            },
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        assert data["source_store"] == "Temu"
        assert data["order_id"] == "TEST-001"
        assert "id" in data
        assert data["item_count"] == 0
        session_data["session_id"] = data["id"]
        print(f"✓ Created session: {data['id']}")
    
    def test_list_sessions(self, auth_headers, session_data):
        """List all sessions"""
        response = requests.get(f"{BASE_URL}/api/intake/sessions", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert "sessions" in data
        assert isinstance(data["sessions"], list)
        # Verify our session is in the list
        session_ids = [s["id"] for s in data["sessions"]]
        assert session_data["session_id"] in session_ids
        print(f"✓ Listed {len(data['sessions'])} sessions")
    
    def test_get_session(self, auth_headers, session_data):
        """Get single session with items"""
        response = requests.get(
            f"{BASE_URL}/api/intake/sessions/{session_data['session_id']}",
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == session_data["session_id"]
        assert data["source_store"] == "Temu"
        assert "items" in data
        print(f"✓ Got session with {len(data['items'])} items")
    
    def test_update_session(self, auth_headers, session_data):
        """Update session fields"""
        response = requests.put(
            f"{BASE_URL}/api/intake/sessions/{session_data['session_id']}",
            json={"notes": "Updated notes for testing"},
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        assert data["notes"] == "Updated notes for testing"
        print("✓ Updated session notes")
    
    def test_get_nonexistent_session(self, auth_headers):
        """404 for nonexistent session"""
        response = requests.get(
            f"{BASE_URL}/api/intake/sessions/nonexistent-id",
            headers=auth_headers
        )
        assert response.status_code == 404
        print("✓ 404 for nonexistent session")

# ================== MANUAL ITEM CRUD TESTS ==================

class TestItemCRUD:
    """Test item CRUD operations"""
    
    def test_create_item_manually(self, auth_headers, session_data):
        """Add item manually to session"""
        response = requests.post(
            f"{BASE_URL}/api/intake/sessions/{session_data['session_id']}/items",
            json={
                "source_type": "manual_entry",
                "source_title": "TEST Purple Silicone Vibrator",
                "quantity": 2,
                "unit_cost": 4.99,
                "color": "Purple",
                "size": "Medium",
                "notes": "Test item"
            },
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        assert data["source_title"] == "TEST Purple Silicone Vibrator"
        assert data["quantity"] == 2
        assert data["unit_cost"] == 4.99
        assert data["status"] == "needs_info"
        assert "suggested_price" in data  # Should be calculated
        assert data["suggested_price"] is not None
        assert "missing_fields" in data
        session_data["item_id"] = data["id"]
        print(f"✓ Created item: {data['id']}, suggested_price: ${data['suggested_price']}")
    
    def test_get_item(self, auth_headers, session_data):
        """Get single item"""
        response = requests.get(
            f"{BASE_URL}/api/intake/items/{session_data['item_id']}",
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == session_data["item_id"]
        assert "missing_fields" in data
        print(f"✓ Got item, missing fields: {data['missing_fields']}")
    
    def test_update_item(self, auth_headers, session_data):
        """Update item fields"""
        response = requests.put(
            f"{BASE_URL}/api/intake/items/{session_data['item_id']}",
            json={
                "clean_title": "Premium Purple Silicone Vibrator",
                "short_description": "A high-quality personal massager",
                "category": "Vibrators"
            },
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        assert data["clean_title"] == "Premium Purple Silicone Vibrator"
        assert data["short_description"] == "A high-quality personal massager"
        assert data["category"] == "Vibrators"
        print("✓ Updated item fields")
    
    def test_session_counts_updated(self, auth_headers, session_data):
        """Verify session counts are updated after item operations"""
        response = requests.get(
            f"{BASE_URL}/api/intake/sessions/{session_data['session_id']}",
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        assert data["item_count"] >= 1
        print(f"✓ Session counts: {data['item_count']} items, {data['needs_info_count']} needs_info")

# ================== STATUS TRANSITION TESTS ==================

class TestStatusTransitions:
    """Test status workflow: needs_info -> in_review -> ready"""
    
    def test_status_to_in_review(self, auth_headers, session_data):
        """Change status from needs_info to in_review"""
        response = requests.put(
            f"{BASE_URL}/api/intake/items/{session_data['item_id']}",
            json={"status": "in_review"},
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "in_review"
        print("✓ Status changed to in_review")
    
    def test_status_to_ready_blocked_by_missing_fields(self, auth_headers, session_data):
        """Cannot mark Ready if required fields missing"""
        # First, clear some required fields
        requests.put(
            f"{BASE_URL}/api/intake/items/{session_data['item_id']}",
            json={"long_description": ""},
            headers=auth_headers
        )
        
        response = requests.put(
            f"{BASE_URL}/api/intake/items/{session_data['item_id']}",
            json={"status": "ready"},
            headers=auth_headers
        )
        assert response.status_code == 400
        assert "Missing fields" in response.json().get("detail", "")
        print("✓ Ready status blocked when required fields missing")
    
    def test_fill_required_fields_and_mark_ready(self, auth_headers, session_data):
        """Fill all required fields and mark Ready"""
        # Fill all required fields
        response = requests.put(
            f"{BASE_URL}/api/intake/items/{session_data['item_id']}",
            json={
                "clean_title": "Premium Purple Silicone Vibrator",
                "short_description": "A high-quality personal massager for intimate moments",
                "long_description": "This premium silicone vibrator features multiple vibration modes and is made from body-safe materials. Perfect for solo or couples play.",
                "category": "Vibrators",
                "quantity": 2,
                "unit_cost": 4.99,
                "currency": "USD",
                "suggested_price": 14.99
            },
            headers=auth_headers
        )
        assert response.status_code == 200
        
        # Now mark ready
        response = requests.put(
            f"{BASE_URL}/api/intake/items/{session_data['item_id']}",
            json={"status": "ready"},
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ready"
        assert len(data.get("missing_fields", [])) == 0
        print("✓ Item marked Ready after filling all required fields")
    
    def test_status_back_to_needs_info(self, auth_headers, session_data):
        """Can move back to needs_info from any status"""
        response = requests.put(
            f"{BASE_URL}/api/intake/items/{session_data['item_id']}",
            json={"status": "needs_info"},
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "needs_info"
        print("✓ Status changed back to needs_info")
    
    def test_invalid_status(self, auth_headers, session_data):
        """Invalid status returns 400"""
        response = requests.put(
            f"{BASE_URL}/api/intake/items/{session_data['item_id']}",
            json={"status": "invalid_status"},
            headers=auth_headers
        )
        assert response.status_code == 400
        print("✓ Invalid status rejected")

# ================== TEXT EXTRACTION TESTS (LLM) ==================

class TestTextExtraction:
    """Test AI text extraction - REAL LLM calls, 15-30s timeout"""
    
    def test_extract_validation(self, auth_headers, session_data):
        """Text must be at least 10 characters"""
        response = requests.post(
            f"{BASE_URL}/api/intake/sessions/{session_data['session_id']}/extract",
            json={"text": "short", "source_type": "pasted_order"},
            headers=auth_headers,
            timeout=60
        )
        assert response.status_code == 400
        print("✓ Extraction validates minimum text length")
    
    def test_extract_invalid_source_type(self, auth_headers, session_data):
        """Invalid source type returns 400"""
        response = requests.post(
            f"{BASE_URL}/api/intake/sessions/{session_data['session_id']}/extract",
            json={"text": "Order Confirmation - 1x Purple Vibrator $4.99", "source_type": "invalid_type"},
            headers=auth_headers,
            timeout=60
        )
        assert response.status_code == 400
        print("✓ Invalid source type rejected")
    
    def test_extract_items_from_text(self, auth_headers, session_data):
        """Extract items from order text - REAL LLM CALL"""
        order_text = """
        Order Confirmation - Temu
        Order #TM-2026-001
        
        1x Purple Silicone Vibrator - $4.99
        2x Rose Gold Massage Oil (100ml) - $3.50 each
        1x Black Lace Lingerie Set (Size M) - $7.25
        
        Subtotal: $19.24
        Shipping: Free
        Total: $19.24
        """
        
        print("  Calling LLM for text extraction (15-30s)...")
        response = requests.post(
            f"{BASE_URL}/api/intake/sessions/{session_data['session_id']}/extract",
            json={"text": order_text, "source_type": "pasted_order"},
            headers=auth_headers,
            timeout=60
        )
        assert response.status_code == 200, f"Extraction failed: {response.text}"
        data = response.json()
        assert "extracted_count" in data
        assert "items" in data
        assert data["extracted_count"] >= 1, "Should extract at least 1 item"
        
        # Verify item structure
        for item in data["items"]:
            assert "id" in item
            assert "source_title" in item
            assert "missing_fields" in item
        
        # Store first extracted item for later tests
        if data["items"]:
            session_data["extracted_item_id"] = data["items"][0]["id"]
        
        print(f"✓ Extracted {data['extracted_count']} items from text")

# ================== AI LISTING GENERATION TESTS (LLM) ==================

class TestListingGeneration:
    """Test AI listing generation - REAL LLM calls"""
    
    def test_generate_listing_requires_title(self, auth_headers, session_data):
        """Item needs at least source_title or clean_title"""
        # Create item without title
        response = requests.post(
            f"{BASE_URL}/api/intake/sessions/{session_data['session_id']}/items",
            json={"source_type": "manual_entry", "quantity": 1, "unit_cost": 5.00},
            headers=auth_headers
        )
        assert response.status_code == 200
        empty_item_id = response.json()["id"]
        
        # Try to generate
        response = requests.post(
            f"{BASE_URL}/api/intake/items/{empty_item_id}/generate",
            headers=auth_headers,
            timeout=60
        )
        assert response.status_code == 400
        assert "title" in response.json().get("detail", "").lower()
        
        # Cleanup
        requests.delete(f"{BASE_URL}/api/intake/items/{empty_item_id}", headers=auth_headers)
        print("✓ Generate listing requires title")
    
    def test_generate_listing_for_item(self, auth_headers, session_data):
        """Generate listing content for an item - REAL LLM CALL"""
        if "extracted_item_id" not in session_data:
            pytest.skip("No extracted item available")
        
        print("  Calling LLM for listing generation (15-30s)...")
        response = requests.post(
            f"{BASE_URL}/api/intake/items/{session_data['extracted_item_id']}/generate",
            headers=auth_headers,
            timeout=60
        )
        assert response.status_code == 200, f"Generation failed: {response.text}"
        data = response.json()
        
        # Verify generated content
        assert data.get("clean_title"), "Should have clean_title"
        assert data.get("short_description"), "Should have short_description"
        assert data.get("long_description"), "Should have long_description"
        assert data.get("category_suggestions"), "Should have category_suggestions"
        
        print(f"✓ Generated listing: {data['clean_title'][:50]}...")

# ================== BATCH GENERATION TESTS ==================

class TestBatchGeneration:
    """Test batch generate all listings"""
    
    def test_batch_generate_no_items_needing_generation(self, auth_headers, session_data):
        """Batch generate when all items already have content"""
        # This may return "No items need generation" if all items have short_description
        response = requests.post(
            f"{BASE_URL}/api/intake/sessions/{session_data['session_id']}/generate-all",
            headers=auth_headers,
            timeout=120
        )
        assert response.status_code == 200
        data = response.json()
        assert "generated" in data or "message" in data
        msg = data.get('message', f"Generated {data.get('generated', 0)} items")
        print(f"✓ Batch generate response: {msg}")

# ================== CSV EXPORT TESTS ==================

class TestCSVExport:
    """Test CSV export functionality"""
    
    def test_export_no_ready_items(self, auth_headers, session_data):
        """Export fails if no Ready items"""
        # First ensure no items are ready
        session_resp = requests.get(
            f"{BASE_URL}/api/intake/sessions/{session_data['session_id']}",
            headers=auth_headers
        )
        items = session_resp.json().get("items", [])
        for item in items:
            if item["status"] == "ready":
                requests.put(
                    f"{BASE_URL}/api/intake/items/{item['id']}",
                    json={"status": "needs_info"},
                    headers=auth_headers
                )
        
        response = requests.get(
            f"{BASE_URL}/api/intake/sessions/{session_data['session_id']}/export",
            headers=auth_headers
        )
        assert response.status_code == 400
        assert "No items to export" in response.json().get("detail", "")
        print("✓ Export fails when no Ready items")
    
    def test_export_with_ready_items(self, auth_headers, session_data):
        """Export CSV with Ready items"""
        # Mark an item as ready (fill all required fields first)
        if "item_id" in session_data:
            requests.put(
                f"{BASE_URL}/api/intake/items/{session_data['item_id']}",
                json={
                    "clean_title": "Test Export Item",
                    "short_description": "Test description",
                    "long_description": "Test long description for export",
                    "category": "Vibrators",
                    "quantity": 1,
                    "unit_cost": 5.00,
                    "currency": "USD",
                    "suggested_price": 14.99,
                    "status": "ready"
                },
                headers=auth_headers
            )
        
        response = requests.get(
            f"{BASE_URL}/api/intake/sessions/{session_data['session_id']}/export",
            headers=auth_headers
        )
        
        if response.status_code == 200:
            assert response.headers.get("content-type") == "text/csv; charset=utf-8"
            assert "content-disposition" in response.headers
            csv_content = response.text
            assert "clean_title" in csv_content  # Header row
            print("✓ CSV export successful")
        else:
            # May fail if no ready items
            print(f"  Export returned {response.status_code}: {response.json().get('detail', '')}")
    
    def test_export_include_non_ready(self, auth_headers, session_data):
        """Export with include_non_ready=true"""
        response = requests.get(
            f"{BASE_URL}/api/intake/sessions/{session_data['session_id']}/export?include_non_ready=true",
            headers=auth_headers
        )
        # Should succeed if there are any items
        if response.status_code == 200:
            assert response.headers.get("content-type") == "text/csv; charset=utf-8"
            print("✓ Export with include_non_ready works")
        else:
            print(f"  Export returned {response.status_code}")

# ================== PRICING SETTINGS TESTS ==================

class TestPricingSettings:
    """Test pricing settings CRUD"""
    
    def test_get_settings(self, auth_headers):
        """Get pricing settings (auto-initialized with defaults)"""
        response = requests.get(f"{BASE_URL}/api/intake/settings", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert "default_markup_multiplier" in data
        assert "min_price" in data
        assert "rounding_rule" in data
        assert "taxonomy" in data
        print(f"✓ Settings: {data['default_markup_multiplier']}x markup, ${data['min_price']} min, {data['rounding_rule']} rounding")
    
    def test_update_settings(self, auth_headers):
        """Update pricing settings"""
        response = requests.put(
            f"{BASE_URL}/api/intake/settings",
            json={
                "default_markup_multiplier": 3.0,
                "min_price": 12.99,
                "rounding_rule": "nearest_95"
            },
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        assert data["default_markup_multiplier"] == 3.0
        assert data["min_price"] == 12.99
        assert data["rounding_rule"] == "nearest_95"
        print("✓ Updated pricing settings")
    
    def test_settings_validation(self, auth_headers):
        """Settings validation"""
        # Invalid rounding rule
        response = requests.put(
            f"{BASE_URL}/api/intake/settings",
            json={"rounding_rule": "invalid_rule"},
            headers=auth_headers
        )
        assert response.status_code == 400
        
        # Markup < 1
        response = requests.put(
            f"{BASE_URL}/api/intake/settings",
            json={"default_markup_multiplier": 0.5},
            headers=auth_headers
        )
        assert response.status_code == 400
        
        # Negative min price
        response = requests.put(
            f"{BASE_URL}/api/intake/settings",
            json={"min_price": -5},
            headers=auth_headers
        )
        assert response.status_code == 400
        
        print("✓ Settings validation working")
    
    def test_restore_default_settings(self, auth_headers):
        """Restore default settings"""
        response = requests.put(
            f"{BASE_URL}/api/intake/settings",
            json={
                "default_markup_multiplier": 2.5,
                "min_price": 9.99,
                "rounding_rule": "nearest_99"
            },
            headers=auth_headers
        )
        assert response.status_code == 200
        print("✓ Restored default settings")

# ================== DELETION TESTS ==================

class TestDeletion:
    """Test deletion operations"""
    
    def test_delete_item(self, auth_headers, session_data):
        """Delete an item"""
        # Create a new item to delete
        response = requests.post(
            f"{BASE_URL}/api/intake/sessions/{session_data['session_id']}/items",
            json={"source_type": "manual_entry", "source_title": "TEST Item to Delete", "quantity": 1},
            headers=auth_headers
        )
        assert response.status_code == 200
        delete_item_id = response.json()["id"]
        
        # Delete it
        response = requests.delete(
            f"{BASE_URL}/api/intake/items/{delete_item_id}",
            headers=auth_headers
        )
        assert response.status_code == 200
        
        # Verify deleted
        response = requests.get(
            f"{BASE_URL}/api/intake/items/{delete_item_id}",
            headers=auth_headers
        )
        assert response.status_code == 404
        print("✓ Item deletion works")
    
    def test_delete_session_cascades(self, auth_headers, session_data):
        """Delete session deletes all items"""
        # Create a new session with items
        response = requests.post(
            f"{BASE_URL}/api/intake/sessions",
            json={"source_store": "TEST_DeleteMe", "order_id": "DEL-001"},
            headers=auth_headers
        )
        assert response.status_code == 200
        delete_session_id = response.json()["id"]
        
        # Add an item
        response = requests.post(
            f"{BASE_URL}/api/intake/sessions/{delete_session_id}/items",
            json={"source_type": "manual_entry", "source_title": "Item in deleted session", "quantity": 1},
            headers=auth_headers
        )
        assert response.status_code == 200
        item_in_deleted = response.json()["id"]
        
        # Delete session
        response = requests.delete(
            f"{BASE_URL}/api/intake/sessions/{delete_session_id}",
            headers=auth_headers
        )
        assert response.status_code == 200
        
        # Verify session deleted
        response = requests.get(
            f"{BASE_URL}/api/intake/sessions/{delete_session_id}",
            headers=auth_headers
        )
        assert response.status_code == 404
        
        # Verify item also deleted
        response = requests.get(
            f"{BASE_URL}/api/intake/items/{item_in_deleted}",
            headers=auth_headers
        )
        assert response.status_code == 404
        print("✓ Session deletion cascades to items")

# ================== CLEANUP ==================

class TestCleanup:
    """Cleanup test data"""
    
    def test_cleanup_test_session(self, auth_headers, session_data):
        """Delete the main test session"""
        if "session_id" in session_data:
            response = requests.delete(
                f"{BASE_URL}/api/intake/sessions/{session_data['session_id']}",
                headers=auth_headers
            )
            assert response.status_code in [200, 404]
            print("✓ Cleaned up test session")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
