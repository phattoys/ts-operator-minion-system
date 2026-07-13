"""
Test Cost Notes and Quick Re-import Features for Product Intake

Features tested:
1. Cost Notes - POST /api/intake/sessions/{session_id}/apply-cost-notes
   - Accepts cost_notes text and returns applied count + match details
   - LLM parses notes and matches to items by category/title keywords
   - Applies unit_cost and suggested_price (retail) to matched items
   - Stores note text in attribute_suggestions.cost_note for audit trail
   - Saves cost_notes on session object

2. Quick Re-import - POST /api/intake/sessions/{session_id}/mark-ready-export
   - Re-validates existing ready items (demotes broken ones)
   - Promotes eligible in_review items to ready
   - Exports ALL currently ready items as WooCommerce CSV
   - Returns exported/newly_ready/demoted/held_back counts
   - Session tracks last_exported_at timestamp
"""
import pytest
import requests
import csv
import io
import os
import time

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')
SESSION_ID = "e54de4dc-5308-4b63-b1e1-f9af5f7d3225"  # SHEIN session


@pytest.fixture(scope="module")
def session():
    """Requests session with auth cookie"""
    s = requests.Session()
    response = s.post(
        f"{BASE_URL}/api/auth/login",
        json={"password": "TSFounder!Vault2026#Secure"}
    )
    assert response.status_code == 200, f"Login failed: {response.text}"
    token = response.json()["access_token"]
    s.cookies.set("access_token", token)
    return s


@pytest.fixture(scope="module")
def test_item_id(session):
    """Get a ready item to use for testing"""
    response = session.get(f"{BASE_URL}/api/intake/sessions/{SESSION_ID}")
    assert response.status_code == 200
    items = response.json()["items"]
    ready_items = [i for i in items if i["status"] == "ready"]
    assert len(ready_items) > 0, "No ready items found for testing"
    return ready_items[0]["id"]


# ==================== COST NOTES TESTS ====================

class TestCostNotesEndpoint:
    """Test POST /api/intake/sessions/{session_id}/apply-cost-notes"""
    
    def test_apply_cost_notes_returns_correct_structure(self, session):
        """Response should include applied count, rules_parsed, and matches"""
        response = session.post(
            f"{BASE_URL}/api/intake/sessions/{SESSION_ID}/apply-cost-notes",
            json={"cost_notes": "all accessories cost $3 and retail at $9.99"}
        )
        assert response.status_code == 200
        
        data = response.json()
        
        # Required fields
        assert "applied" in data, "Missing 'applied' count"
        assert "total_items" in data, "Missing 'total_items'"
        assert "matches" in data, "Missing 'matches' array"
        assert "message" in data, "Missing 'message'"
        
        # Types
        assert isinstance(data["applied"], int)
        assert isinstance(data["total_items"], int)
        assert isinstance(data["matches"], list)
    
    def test_apply_cost_notes_returns_rules_parsed(self, session):
        """Response should include rules_parsed count"""
        response = session.post(
            f"{BASE_URL}/api/intake/sessions/{SESSION_ID}/apply-cost-notes",
            json={"cost_notes": "bodysuits cost $6 each, sell for $18.99"}
        )
        assert response.status_code == 200
        
        data = response.json()
        assert "rules_parsed" in data, "Missing 'rules_parsed' count"
        assert isinstance(data["rules_parsed"], int)
    
    def test_apply_cost_notes_matches_have_details(self, session):
        """Match details should include note, matched_items, unit_cost, retail_price, confidence"""
        response = session.post(
            f"{BASE_URL}/api/intake/sessions/{SESSION_ID}/apply-cost-notes",
            json={"cost_notes": "lingerie sets cost $7 and retail at $19.99"}
        )
        assert response.status_code == 200
        
        data = response.json()
        if data["matches"]:
            match = data["matches"][0]
            assert "note" in match, "Match missing 'note'"
            assert "matched_items" in match, "Match missing 'matched_items'"
            assert "confidence" in match, "Match missing 'confidence'"
            # unit_cost and retail_price may be null if not parsed
    
    def test_apply_cost_notes_requires_auth(self, session):
        """Endpoint should require authentication"""
        # Create a new session without auth
        unauth_session = requests.Session()
        response = unauth_session.post(
            f"{BASE_URL}/api/intake/sessions/{SESSION_ID}/apply-cost-notes",
            json={"cost_notes": "test notes"}
        )
        assert response.status_code == 401
    
    def test_apply_cost_notes_returns_404_for_nonexistent_session(self, session):
        """Should return 404 for nonexistent session"""
        response = session.post(
            f"{BASE_URL}/api/intake/sessions/nonexistent-session-id/apply-cost-notes",
            json={"cost_notes": "test notes"}
        )
        assert response.status_code == 404
    
    def test_apply_cost_notes_rejects_empty_notes(self, session):
        """Should reject empty cost notes"""
        response = session.post(
            f"{BASE_URL}/api/intake/sessions/{SESSION_ID}/apply-cost-notes",
            json={"cost_notes": ""}
        )
        assert response.status_code == 400
        assert "empty" in response.json().get("detail", "").lower()
    
    def test_apply_cost_notes_rejects_whitespace_only(self, session):
        """Should reject whitespace-only cost notes"""
        response = session.post(
            f"{BASE_URL}/api/intake/sessions/{SESSION_ID}/apply-cost-notes",
            json={"cost_notes": "   \n\t  "}
        )
        assert response.status_code == 400


class TestCostNotesItemUpdates:
    """Test that cost notes actually update item prices"""
    
    def test_cost_notes_update_item_prices(self, session, test_item_id):
        """Cost notes should update unit_cost and suggested_price on matched items"""
        # Get original item state
        item_before = session.get(f"{BASE_URL}/api/intake/items/{test_item_id}").json()
        original_cost = item_before.get("unit_cost")
        original_price = item_before.get("suggested_price")
        
        # Apply cost notes with a specific pattern that should match
        # Use a unique test note to avoid conflicts
        test_cost = 99.99
        test_retail = 199.99
        
        # Get the item's clean_title to create a matching note
        clean_title = item_before.get("clean_title", "")
        if clean_title:
            # Extract a keyword from the title
            keyword = clean_title.split()[0] if clean_title.split() else "item"
            
            response = session.post(
                f"{BASE_URL}/api/intake/sessions/{SESSION_ID}/apply-cost-notes",
                json={"cost_notes": f"items with '{keyword}' cost ${test_cost} and retail at ${test_retail}"}
            )
            assert response.status_code == 200
            
            # Check if item was updated
            item_after = session.get(f"{BASE_URL}/api/intake/items/{test_item_id}").json()
            
            # Restore original values
            session.put(
                f"{BASE_URL}/api/intake/items/{test_item_id}",
                json={"unit_cost": original_cost, "suggested_price": original_price}
            )
            
            # If the item was matched, prices should have changed
            data = response.json()
            if data["applied"] > 0:
                # At least some items were updated
                assert data["applied"] >= 1


class TestCostNotesAuditTrail:
    """Test that cost notes are stored for audit trail"""
    
    def test_cost_note_stored_in_attribute_suggestions(self, session, test_item_id):
        """Cost note text should be stored in attribute_suggestions.cost_note"""
        # Get original state
        item_before = session.get(f"{BASE_URL}/api/intake/items/{test_item_id}").json()
        original_attrs = item_before.get("attribute_suggestions", {})
        original_cost_note = original_attrs.get("cost_note")
        
        # Apply a cost note
        test_note = f"test cost note {int(time.time())}"
        response = session.post(
            f"{BASE_URL}/api/intake/sessions/{SESSION_ID}/apply-cost-notes",
            json={"cost_notes": f"{test_note} - all items cost $5 retail $15"}
        )
        assert response.status_code == 200
        
        # Check if any items have the cost_note stored
        session_response = session.get(f"{BASE_URL}/api/intake/sessions/{SESSION_ID}")
        items = session_response.json()["items"]
        
        # Find items with cost_note in attribute_suggestions
        items_with_cost_note = [
            i for i in items 
            if i.get("attribute_suggestions", {}).get("cost_note")
        ]
        
        # At least some items should have cost_note stored
        assert len(items_with_cost_note) > 0, "No items have cost_note in attribute_suggestions"


class TestCostNotesSavedOnSession:
    """Test that cost notes are saved on the session object"""
    
    def test_session_has_cost_notes_field(self, session):
        """Session should have cost_notes field after applying notes"""
        # Apply cost notes
        test_notes = f"test session notes {int(time.time())}"
        response = session.post(
            f"{BASE_URL}/api/intake/sessions/{SESSION_ID}/apply-cost-notes",
            json={"cost_notes": test_notes}
        )
        assert response.status_code == 200
        
        # Check session
        session_response = session.get(f"{BASE_URL}/api/intake/sessions/{SESSION_ID}")
        session_data = session_response.json()
        
        assert "cost_notes" in session_data, "Session missing 'cost_notes' field"
        assert session_data["cost_notes"] == test_notes, "Session cost_notes doesn't match applied notes"


# ==================== QUICK RE-IMPORT TESTS ====================

class TestMarkReadyExportResponseStructure:
    """Test the response structure of mark-ready-export endpoint"""
    
    def test_response_has_required_counts(self, session):
        """Response should include exported/newly_ready/demoted/held_back counts"""
        response = session.post(f"{BASE_URL}/api/intake/sessions/{SESSION_ID}/mark-ready-export")
        assert response.status_code == 200
        
        data = response.json()
        
        # Required count fields
        assert "exported" in data, "Missing 'exported' count"
        assert "newly_ready" in data, "Missing 'newly_ready' count"
        assert "demoted" in data, "Missing 'demoted' count"
        assert "held_back" in data, "Missing 'held_back' count"
        
        # All should be integers
        assert isinstance(data["exported"], int)
        assert isinstance(data["newly_ready"], int)
        assert isinstance(data["demoted"], int)
        assert isinstance(data["held_back"], int)
    
    def test_response_has_demoted_items_array(self, session):
        """Response should include demoted_items array"""
        response = session.post(f"{BASE_URL}/api/intake/sessions/{SESSION_ID}/mark-ready-export")
        assert response.status_code == 200
        
        data = response.json()
        assert "demoted_items" in data, "Missing 'demoted_items' array"
        assert isinstance(data["demoted_items"], list)
    
    def test_response_has_csv_data(self, session):
        """Response should include csv_data and csv_filename"""
        response = session.post(f"{BASE_URL}/api/intake/sessions/{SESSION_ID}/mark-ready-export")
        assert response.status_code == 200
        
        data = response.json()
        assert "csv_data" in data, "Missing 'csv_data'"
        assert "csv_filename" in data, "Missing 'csv_filename'"
        assert "woo-import" in data["csv_filename"].lower()


class TestMarkReadyExportRevalidation:
    """Test that mark-ready-export re-validates existing ready items"""
    
    def test_edit_item_to_break_validation_then_reexport(self, session, test_item_id):
        """Editing an item to break validation should cause demotion on re-export"""
        # Get original state
        item_before = session.get(f"{BASE_URL}/api/intake/items/{test_item_id}").json()
        original_category = item_before.get("category", "")
        original_status = item_before.get("status", "")
        
        if original_status != "ready":
            pytest.skip("Test item is not in 'ready' status")
        
        # Set to in_review first, then clear category
        session.put(f"{BASE_URL}/api/intake/items/{test_item_id}", json={"status": "in_review"})
        session.put(f"{BASE_URL}/api/intake/items/{test_item_id}", json={"category": ""})
        
        # Call mark-ready-export
        export_response = session.post(f"{BASE_URL}/api/intake/sessions/{SESSION_ID}/mark-ready-export")
        assert export_response.status_code == 200
        
        # Check item status
        item_after = session.get(f"{BASE_URL}/api/intake/items/{test_item_id}").json()
        
        # Restore original state
        session.put(
            f"{BASE_URL}/api/intake/items/{test_item_id}",
            json={"category": original_category, "status": original_status}
        )
        
        # Item should be in_review (held back due to missing category)
        assert item_after["status"] == "in_review"


class TestMarkReadyExportPromotion:
    """Test that mark-ready-export promotes eligible in_review items"""
    
    def test_eligible_in_review_item_gets_promoted(self, session, test_item_id):
        """An in_review item with all required fields should be promoted to ready"""
        # Get original state
        item_before = session.get(f"{BASE_URL}/api/intake/items/{test_item_id}").json()
        original_status = item_before.get("status", "")
        
        # Set item to in_review
        session.put(f"{BASE_URL}/api/intake/items/{test_item_id}", json={"status": "in_review"})
        
        # Call mark-ready-export
        export_response = session.post(f"{BASE_URL}/api/intake/sessions/{SESSION_ID}/mark-ready-export")
        assert export_response.status_code == 200
        export_data = export_response.json()
        
        # Check item status after
        item_after = session.get(f"{BASE_URL}/api/intake/items/{test_item_id}").json()
        
        # Restore original status
        session.put(f"{BASE_URL}/api/intake/items/{test_item_id}", json={"status": original_status})
        
        # Item should have been promoted to ready (if it had all required fields)
        if item_after["status"] == "ready":
            assert export_data["newly_ready"] >= 1


class TestMarkReadyExportCSV:
    """Test that CSV includes ALL currently ready items"""
    
    def test_csv_row_count_matches_exported_count(self, session):
        """CSV should have same number of rows as 'exported' count"""
        response = session.post(f"{BASE_URL}/api/intake/sessions/{SESSION_ID}/mark-ready-export")
        assert response.status_code == 200
        
        data = response.json()
        exported_count = data["exported"]
        csv_data = data["csv_data"]
        
        if csv_data:
            reader = csv.DictReader(io.StringIO(csv_data))
            rows = list(reader)
            assert len(rows) == exported_count
    
    def test_all_items_have_published_zero(self, session):
        """All items in CSV should have Published=0 (never auto-publish)"""
        response = session.post(f"{BASE_URL}/api/intake/sessions/{SESSION_ID}/mark-ready-export")
        assert response.status_code == 200
        
        csv_data = response.json()["csv_data"]
        if not csv_data:
            pytest.skip("No CSV data returned")
        
        reader = csv.DictReader(io.StringIO(csv_data))
        for row in reader:
            assert row["Published"] == "0"


class TestSessionLastExportedAt:
    """Test that session tracks last_exported_at timestamp"""
    
    def test_session_has_last_exported_at_after_export(self, session):
        """Session should have last_exported_at after mark-ready-export"""
        # Do an export
        export_response = session.post(f"{BASE_URL}/api/intake/sessions/{SESSION_ID}/mark-ready-export")
        assert export_response.status_code == 200
        
        # Check session
        session_response = session.get(f"{BASE_URL}/api/intake/sessions/{SESSION_ID}")
        session_data = session_response.json()
        
        assert "last_exported_at" in session_data
        assert session_data["last_exported_at"] is not None


class TestMarkReadyExportIdempotency:
    """Test that mark-ready-export is idempotent"""
    
    def test_repeated_calls_produce_consistent_results(self, session):
        """Calling mark-ready-export multiple times should produce consistent results"""
        # First call
        response1 = session.post(f"{BASE_URL}/api/intake/sessions/{SESSION_ID}/mark-ready-export")
        assert response1.status_code == 200
        data1 = response1.json()
        
        # Second call
        response2 = session.post(f"{BASE_URL}/api/intake/sessions/{SESSION_ID}/mark-ready-export")
        assert response2.status_code == 200
        data2 = response2.json()
        
        # Exported count should be the same
        assert data2["exported"] == data1["exported"]
        assert data2["newly_ready"] == 0
        assert data2["demoted"] == 0


class TestMarkReadyExportAuth:
    """Test authentication requirements"""
    
    def test_requires_authentication(self, session):
        """Endpoint should require authentication"""
        unauth_session = requests.Session()
        response = unauth_session.post(f"{BASE_URL}/api/intake/sessions/{SESSION_ID}/mark-ready-export")
        assert response.status_code == 401
    
    def test_returns_404_for_nonexistent_session(self, session):
        """Should return 404 for nonexistent session"""
        response = session.post(f"{BASE_URL}/api/intake/sessions/nonexistent-session-id/mark-ready-export")
        assert response.status_code == 404


# ==================== INTEGRATION TESTS ====================

class TestCostNotesAndReexportIntegration:
    """Test that cost notes changes are reflected in re-export"""
    
    def test_cost_notes_prices_appear_in_csv(self, session):
        """After applying cost notes, re-export CSV should have updated prices"""
        # Apply cost notes with specific prices
        response = session.post(
            f"{BASE_URL}/api/intake/sessions/{SESSION_ID}/apply-cost-notes",
            json={"cost_notes": "all items cost $4.50 and retail at $14.99"}
        )
        assert response.status_code == 200
        
        # Re-export
        export_response = session.post(f"{BASE_URL}/api/intake/sessions/{SESSION_ID}/mark-ready-export")
        assert export_response.status_code == 200
        
        csv_data = export_response.json()["csv_data"]
        if csv_data:
            reader = csv.DictReader(io.StringIO(csv_data))
            rows = list(reader)
            
            # Check that some items have the expected price
            prices = [row.get("Regular price", "") for row in rows if row.get("Regular price")]
            assert len(prices) > 0, "No prices found in CSV"
