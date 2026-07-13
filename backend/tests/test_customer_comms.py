"""
Customer Comms Minion Backend Tests
Tests for: /api/comms/* endpoints
- GET /api/comms/scenarios - List 9 scenarios and 3 channels
- POST /api/comms/generate - Generate drafts with LLM (GPT-5.2)
- GET /api/comms/history - List drafts with filters
- GET /api/comms/history/{id} - Get single draft
- POST /api/comms/history/{id}/favorite - Toggle favorite
- POST /api/comms/history/{id}/duplicate - Duplicate draft inputs
- DELETE /api/comms/history/{id} - Delete draft
- GET /api/comms/stats - Get stats
"""

import pytest
import requests
import os
import time

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')
PASSWORD = "TSFounder!Vault2026#Secure"


@pytest.fixture(scope="module")
def auth_token():
    """Get authentication token"""
    response = requests.post(f"{BASE_URL}/api/auth/login", json={"password": PASSWORD})
    if response.status_code == 200:
        return response.json().get("access_token")
    pytest.skip("Authentication failed - skipping tests")


@pytest.fixture(scope="module")
def auth_headers(auth_token):
    """Headers with auth token"""
    return {"Authorization": f"Bearer {auth_token}", "Content-Type": "application/json"}


class TestCommsScenarios:
    """Test GET /api/comms/scenarios endpoint"""
    
    def test_scenarios_requires_auth(self):
        """Scenarios endpoint requires authentication"""
        response = requests.get(f"{BASE_URL}/api/comms/scenarios")
        assert response.status_code == 401, f"Expected 401, got {response.status_code}"
        print("PASS: Scenarios endpoint requires auth")
    
    def test_scenarios_returns_9_scenarios(self, auth_headers):
        """Should return exactly 9 scenarios"""
        response = requests.get(f"{BASE_URL}/api/comms/scenarios", headers=auth_headers)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        data = response.json()
        assert "scenarios" in data, "Response missing 'scenarios' key"
        assert len(data["scenarios"]) == 9, f"Expected 9 scenarios, got {len(data['scenarios'])}"
        print(f"PASS: Got 9 scenarios")
    
    def test_scenarios_returns_3_channels(self, auth_headers):
        """Should return exactly 3 channels"""
        response = requests.get(f"{BASE_URL}/api/comms/scenarios", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert "channels" in data, "Response missing 'channels' key"
        assert len(data["channels"]) == 3, f"Expected 3 channels, got {len(data['channels'])}"
        assert set(data["channels"]) == {"email", "sms", "chat"}, f"Unexpected channels: {data['channels']}"
        print(f"PASS: Got 3 channels: {data['channels']}")
    
    def test_scenarios_have_correct_structure(self, auth_headers):
        """Each scenario should have key, label, required_fields, optional_fields"""
        response = requests.get(f"{BASE_URL}/api/comms/scenarios", headers=auth_headers)
        data = response.json()
        for scenario in data["scenarios"]:
            assert "key" in scenario, f"Scenario missing 'key': {scenario}"
            assert "label" in scenario, f"Scenario missing 'label': {scenario}"
            assert "required_fields" in scenario, f"Scenario missing 'required_fields': {scenario}"
            assert "optional_fields" in scenario, f"Scenario missing 'optional_fields': {scenario}"
        print("PASS: All scenarios have correct structure")
    
    def test_expected_scenario_keys(self, auth_headers):
        """Verify all 9 expected scenario keys are present"""
        expected_keys = [
            "order_confirmation", "shipping_delay", "delivered_not_received",
            "wrong_defective_item", "refund_return", "discreet_reassurance",
            "product_care", "review_request", "apology_resolution"
        ]
        response = requests.get(f"{BASE_URL}/api/comms/scenarios", headers=auth_headers)
        data = response.json()
        actual_keys = [s["key"] for s in data["scenarios"]]
        for key in expected_keys:
            assert key in actual_keys, f"Missing scenario key: {key}"
        print(f"PASS: All 9 expected scenario keys present")


class TestCommsGenerateMissingFields:
    """Test POST /api/comms/generate with missing required fields"""
    
    def test_generate_requires_auth(self):
        """Generate endpoint requires authentication"""
        response = requests.post(f"{BASE_URL}/api/comms/generate", json={
            "scenario_key": "order_confirmation",
            "channel": "email"
        })
        assert response.status_code == 401, f"Expected 401, got {response.status_code}"
        print("PASS: Generate endpoint requires auth")
    
    def test_generate_missing_required_field_returns_needs_info(self, auth_headers):
        """Generate without required field (order_number) should return needs_info"""
        response = requests.post(f"{BASE_URL}/api/comms/generate", json={
            "scenario_key": "order_confirmation",
            "channel": "email",
            "context_fields": {},  # Missing order_number
            "generate_with_placeholders": False
        }, headers=auth_headers)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        data = response.json()
        assert data.get("status") == "needs_info", f"Expected status 'needs_info', got {data.get('status')}"
        assert "missing_fields" in data, "Response missing 'missing_fields'"
        assert "order_number" in data["missing_fields"], f"Expected 'order_number' in missing_fields: {data['missing_fields']}"
        print(f"PASS: Missing required field returns needs_info with missing_fields: {data['missing_fields']}")
    
    def test_generate_with_placeholders_bypasses_missing_fields(self, auth_headers):
        """Generate with placeholders=true should generate despite missing required fields"""
        response = requests.post(f"{BASE_URL}/api/comms/generate", json={
            "scenario_key": "order_confirmation",
            "channel": "email",
            "context_fields": {},  # Missing order_number
            "generate_with_placeholders": True
        }, headers=auth_headers, timeout=60)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        data = response.json()
        # Should NOT return needs_info, should return actual draft
        assert data.get("status") != "needs_info", f"Expected draft, got needs_info: {data}"
        assert "variants" in data, f"Response missing 'variants': {data}"
        assert len(data["variants"]) == 3, f"Expected 3 variants, got {len(data['variants'])}"
        print(f"PASS: Generate with placeholders bypasses missing fields, got {len(data['variants'])} variants")


class TestCommsGenerateDiscreetReassurance:
    """Test discreet_reassurance scenario which has NO required fields"""
    
    def test_discreet_reassurance_generates_immediately(self, auth_headers):
        """discreet_reassurance has no required fields, should generate immediately"""
        response = requests.post(f"{BASE_URL}/api/comms/generate", json={
            "scenario_key": "discreet_reassurance",
            "channel": "email",
            "context_fields": {},
            "generate_with_placeholders": False
        }, headers=auth_headers, timeout=60)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        data = response.json()
        # Should NOT return needs_info since no required fields
        assert data.get("status") != "needs_info", f"Expected draft, got needs_info: {data}"
        assert "variants" in data, f"Response missing 'variants': {data}"
        assert len(data["variants"]) == 3, f"Expected 3 variants, got {len(data['variants'])}"
        assert "id" in data, "Response missing 'id'"
        print(f"PASS: discreet_reassurance generates immediately with 3 variants")
        return data["id"]


class TestCommsGenerateWithValidFields:
    """Test POST /api/comms/generate with valid required fields"""
    
    def test_generate_with_valid_fields_returns_3_variants(self, auth_headers):
        """Generate with valid required fields should return 3 variants"""
        response = requests.post(f"{BASE_URL}/api/comms/generate", json={
            "scenario_key": "order_confirmation",
            "channel": "email",
            "context_fields": {
                "order_number": "TEST-12345",
                "customer_name": "Test Customer"
            },
            "generate_with_placeholders": False,
            "max_discretion": False
        }, headers=auth_headers, timeout=60)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        data = response.json()
        assert "variants" in data, f"Response missing 'variants': {data}"
        assert len(data["variants"]) == 3, f"Expected 3 variants, got {len(data['variants'])}"
        
        # Check variant structure
        variant_types = [v["type"] for v in data["variants"]]
        assert "short" in variant_types, "Missing 'short' variant"
        assert "standard" in variant_types, "Missing 'standard' variant"
        assert "extra_careful" in variant_types, "Missing 'extra_careful' variant"
        
        # Check each variant has body
        for v in data["variants"]:
            assert "body" in v, f"Variant missing 'body': {v}"
            assert len(v["body"]) > 0, f"Variant body is empty: {v}"
        
        # Email should have subject
        assert "subject" in data, "Email response missing 'subject'"
        
        print(f"PASS: Generate with valid fields returns 3 variants with subject")
        return data["id"]
    
    def test_generate_sms_no_subject(self, auth_headers):
        """SMS channel should not have subject line"""
        response = requests.post(f"{BASE_URL}/api/comms/generate", json={
            "scenario_key": "discreet_reassurance",
            "channel": "sms",
            "context_fields": {},
            "generate_with_placeholders": False
        }, headers=auth_headers, timeout=60)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        data = response.json()
        assert "variants" in data, f"Response missing 'variants'"
        # SMS should have null subject
        assert data.get("subject") is None, f"SMS should have null subject, got: {data.get('subject')}"
        print("PASS: SMS channel has null subject")
    
    def test_generate_with_max_discretion(self, auth_headers):
        """Generate with max_discretion flag"""
        response = requests.post(f"{BASE_URL}/api/comms/generate", json={
            "scenario_key": "discreet_reassurance",
            "channel": "chat",
            "context_fields": {},
            "max_discretion": True,
            "generate_with_placeholders": False
        }, headers=auth_headers, timeout=60)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        data = response.json()
        assert "variants" in data, f"Response missing 'variants'"
        assert data.get("max_discretion") == True, f"max_discretion should be True in response"
        print("PASS: Generate with max_discretion flag works")


class TestCommsHistory:
    """Test GET /api/comms/history endpoint"""
    
    def test_history_requires_auth(self):
        """History endpoint requires authentication"""
        response = requests.get(f"{BASE_URL}/api/comms/history")
        assert response.status_code == 401, f"Expected 401, got {response.status_code}"
        print("PASS: History endpoint requires auth")
    
    def test_history_returns_drafts(self, auth_headers):
        """History should return list of drafts"""
        response = requests.get(f"{BASE_URL}/api/comms/history", headers=auth_headers)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        data = response.json()
        assert "drafts" in data, "Response missing 'drafts'"
        assert "count" in data, "Response missing 'count'"
        assert isinstance(data["drafts"], list), "drafts should be a list"
        print(f"PASS: History returns {data['count']} drafts")
    
    def test_history_filter_by_scenario(self, auth_headers):
        """History can filter by scenario_key"""
        response = requests.get(f"{BASE_URL}/api/comms/history", 
                               params={"scenario_key": "discreet_reassurance"},
                               headers=auth_headers)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        data = response.json()
        for draft in data["drafts"]:
            assert draft["scenario_key"] == "discreet_reassurance", f"Filter failed: {draft['scenario_key']}"
        print(f"PASS: History filter by scenario works, got {data['count']} drafts")
    
    def test_history_filter_favorites_only(self, auth_headers):
        """History can filter favorites only"""
        response = requests.get(f"{BASE_URL}/api/comms/history", 
                               params={"favorites_only": True},
                               headers=auth_headers)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        data = response.json()
        for draft in data["drafts"]:
            assert draft["is_favorite"] == True, f"Filter failed: draft is not favorite"
        print(f"PASS: History filter favorites_only works, got {data['count']} favorites")


class TestCommsHistoryOperations:
    """Test history operations: favorite, duplicate, delete"""
    
    @pytest.fixture(scope="class")
    def test_draft_id(self, auth_headers):
        """Create a test draft for operations"""
        response = requests.post(f"{BASE_URL}/api/comms/generate", json={
            "scenario_key": "discreet_reassurance",
            "channel": "email",
            "context_fields": {"customer_name": "TEST_HistoryOps"},
            "generate_with_placeholders": False
        }, headers=auth_headers, timeout=60)
        assert response.status_code == 200, f"Failed to create test draft: {response.text}"
        data = response.json()
        assert "id" in data, f"Response missing 'id': {data}"
        return data["id"]
    
    def test_get_single_draft(self, auth_headers, test_draft_id):
        """GET /api/comms/history/{id} returns single draft"""
        response = requests.get(f"{BASE_URL}/api/comms/history/{test_draft_id}", headers=auth_headers)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        data = response.json()
        assert data["id"] == test_draft_id, f"ID mismatch: {data['id']} != {test_draft_id}"
        assert "variants" in data, "Response missing 'variants'"
        print(f"PASS: Get single draft works")
    
    def test_toggle_favorite(self, auth_headers, test_draft_id):
        """POST /api/comms/history/{id}/favorite toggles favorite"""
        # Get initial state
        response = requests.get(f"{BASE_URL}/api/comms/history/{test_draft_id}", headers=auth_headers)
        initial_favorite = response.json().get("is_favorite", False)
        
        # Toggle favorite
        response = requests.post(f"{BASE_URL}/api/comms/history/{test_draft_id}/favorite", 
                                json={"draft_id": test_draft_id},
                                headers=auth_headers)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        data = response.json()
        assert data["is_favorite"] != initial_favorite, f"Favorite not toggled: {data['is_favorite']} == {initial_favorite}"
        print(f"PASS: Toggle favorite works (was {initial_favorite}, now {data['is_favorite']})")
    
    def test_duplicate_draft(self, auth_headers, test_draft_id):
        """POST /api/comms/history/{id}/duplicate returns draft inputs"""
        response = requests.post(f"{BASE_URL}/api/comms/history/{test_draft_id}/duplicate", 
                                json={},
                                headers=auth_headers)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        data = response.json()
        assert "scenario_key" in data, "Response missing 'scenario_key'"
        assert "channel" in data, "Response missing 'channel'"
        assert "context_fields" in data, "Response missing 'context_fields'"
        print(f"PASS: Duplicate draft returns inputs: scenario={data['scenario_key']}, channel={data['channel']}")
    
    def test_delete_draft(self, auth_headers, test_draft_id):
        """DELETE /api/comms/history/{id} deletes draft"""
        response = requests.delete(f"{BASE_URL}/api/comms/history/{test_draft_id}", headers=auth_headers)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        # Verify deleted
        response = requests.get(f"{BASE_URL}/api/comms/history/{test_draft_id}", headers=auth_headers)
        assert response.status_code == 404, f"Expected 404 after delete, got {response.status_code}"
        print("PASS: Delete draft works")


class TestCommsStats:
    """Test GET /api/comms/stats endpoint"""
    
    def test_stats_requires_auth(self):
        """Stats endpoint requires authentication"""
        response = requests.get(f"{BASE_URL}/api/comms/stats")
        assert response.status_code == 401, f"Expected 401, got {response.status_code}"
        print("PASS: Stats endpoint requires auth")
    
    def test_stats_returns_correct_structure(self, auth_headers):
        """Stats should return total_drafts, favorites, by_scenario, by_channel"""
        response = requests.get(f"{BASE_URL}/api/comms/stats", headers=auth_headers)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        data = response.json()
        assert "total_drafts" in data, "Response missing 'total_drafts'"
        assert "favorites" in data, "Response missing 'favorites'"
        assert "by_scenario" in data, "Response missing 'by_scenario'"
        assert "by_channel" in data, "Response missing 'by_channel'"
        assert isinstance(data["total_drafts"], int), "total_drafts should be int"
        assert isinstance(data["favorites"], int), "favorites should be int"
        print(f"PASS: Stats returns correct structure: {data['total_drafts']} drafts, {data['favorites']} favorites")


class TestCommsErrorHandling:
    """Test error handling for invalid inputs"""
    
    def test_invalid_scenario_key(self, auth_headers):
        """Invalid scenario key should return 400"""
        response = requests.post(f"{BASE_URL}/api/comms/generate", json={
            "scenario_key": "invalid_scenario",
            "channel": "email"
        }, headers=auth_headers)
        assert response.status_code == 400, f"Expected 400, got {response.status_code}"
        print("PASS: Invalid scenario key returns 400")
    
    def test_invalid_channel(self, auth_headers):
        """Invalid channel should return 400"""
        response = requests.post(f"{BASE_URL}/api/comms/generate", json={
            "scenario_key": "discreet_reassurance",
            "channel": "invalid_channel"
        }, headers=auth_headers)
        assert response.status_code == 400, f"Expected 400, got {response.status_code}"
        print("PASS: Invalid channel returns 400")
    
    def test_nonexistent_draft_id(self, auth_headers):
        """Nonexistent draft ID should return 404"""
        response = requests.get(f"{BASE_URL}/api/comms/history/nonexistent-id-12345", headers=auth_headers)
        assert response.status_code == 404, f"Expected 404, got {response.status_code}"
        print("PASS: Nonexistent draft ID returns 404")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
