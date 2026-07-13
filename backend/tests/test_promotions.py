"""
Phase 4: Variant-to-Template Promotion Logic Tests
Tests for promotion evaluation, candidate management, and promotion actions
"""
import pytest
import requests
import os
import uuid

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')
PASSWORD = "TSFounder!Vault2026#Secure"

# Known test data from seed
HOMEPAGE_PAGE_ID = "ef54de19-6e5b-405e-9e80-5316b31ddd1f"
HOMEPAGE_VERSION_ID = "426da4a4-58a4-4c15-9b85-51db78d7f083"


@pytest.fixture(scope="module")
def auth_session():
    """Create authenticated session"""
    session = requests.Session()
    session.headers.update({"Content-Type": "application/json"})
    
    # Login
    response = session.post(f"{BASE_URL}/api/auth/login", json={"password": PASSWORD})
    assert response.status_code == 200, f"Login failed: {response.text}"
    
    # Get token from response or cookies
    data = response.json()
    if "access_token" in data:
        session.headers.update({"Authorization": f"Bearer {data['access_token']}"})
    
    return session


class TestPromotionEvaluation:
    """Tests for POST /api/promotions/evaluate/{page_id}/{version_id}"""
    
    def test_evaluate_existing_version(self, auth_session):
        """Evaluate the seeded Homepage v1 for promotion"""
        response = auth_session.post(
            f"{BASE_URL}/api/promotions/evaluate/{HOMEPAGE_PAGE_ID}/{HOMEPAGE_VERSION_ID}"
        )
        assert response.status_code == 200, f"Evaluate failed: {response.text}"
        
        data = response.json()
        # Should be promotable with signals
        assert "promotable" in data
        assert "signals" in data
        assert isinstance(data["signals"], list)
        
        if data["promotable"]:
            assert "promotion_types" in data
            assert "recommendation_reason" in data
            assert "candidate" in data
            print(f"✓ Evaluation result: promotable={data['promotable']}, signals={len(data['signals'])}")
            print(f"  Promotion types: {data.get('promotion_types', [])}")
        else:
            print(f"✓ Version not promotable (may already be processed)")
    
    def test_evaluate_nonexistent_version(self, auth_session):
        """Evaluate a non-existent version returns 404"""
        fake_version_id = str(uuid.uuid4())
        response = auth_session.post(
            f"{BASE_URL}/api/promotions/evaluate/{HOMEPAGE_PAGE_ID}/{fake_version_id}"
        )
        assert response.status_code == 404
        print("✓ Non-existent version returns 404")
    
    def test_evaluate_nonexistent_page(self, auth_session):
        """Evaluate with non-existent page returns 404"""
        fake_page_id = str(uuid.uuid4())
        response = auth_session.post(
            f"{BASE_URL}/api/promotions/evaluate/{fake_page_id}/{HOMEPAGE_VERSION_ID}"
        )
        assert response.status_code == 404
        print("✓ Non-existent page returns 404")


class TestPromotionCandidates:
    """Tests for GET /api/promotions/candidates endpoints"""
    
    def test_get_all_candidates(self, auth_session):
        """Get all promotion candidates"""
        response = auth_session.get(f"{BASE_URL}/api/promotions/candidates")
        assert response.status_code == 200, f"Get candidates failed: {response.text}"
        
        data = response.json()
        assert "candidates" in data
        assert "total" in data
        assert "status_counts" in data
        
        # Verify status_counts structure
        status_counts = data["status_counts"]
        assert "pending" in status_counts
        assert "promoted" in status_counts
        assert "dismissed" in status_counts
        assert "deferred" in status_counts
        
        print(f"✓ Got {data['total']} candidates")
        print(f"  Status counts: {status_counts}")
    
    def test_get_candidates_filter_pending(self, auth_session):
        """Filter candidates by pending status"""
        response = auth_session.get(f"{BASE_URL}/api/promotions/candidates?status=pending")
        assert response.status_code == 200
        
        data = response.json()
        # All returned candidates should be pending
        for c in data["candidates"]:
            assert c["status"] == "pending", f"Expected pending, got {c['status']}"
        
        print(f"✓ Filtered pending candidates: {len(data['candidates'])}")
    
    def test_get_candidates_filter_promoted(self, auth_session):
        """Filter candidates by promoted status"""
        response = auth_session.get(f"{BASE_URL}/api/promotions/candidates?status=promoted")
        assert response.status_code == 200
        
        data = response.json()
        for c in data["candidates"]:
            assert c["status"] == "promoted"
        
        print(f"✓ Filtered promoted candidates: {len(data['candidates'])}")
    
    def test_get_candidates_filter_dismissed(self, auth_session):
        """Filter candidates by dismissed status"""
        response = auth_session.get(f"{BASE_URL}/api/promotions/candidates?status=dismissed")
        assert response.status_code == 200
        
        data = response.json()
        for c in data["candidates"]:
            assert c["status"] == "dismissed"
        
        print(f"✓ Filtered dismissed candidates: {len(data['candidates'])}")
    
    def test_get_candidates_filter_deferred(self, auth_session):
        """Filter candidates by deferred status"""
        response = auth_session.get(f"{BASE_URL}/api/promotions/candidates?status=deferred")
        assert response.status_code == 200
        
        data = response.json()
        for c in data["candidates"]:
            assert c["status"] == "deferred"
        
        print(f"✓ Filtered deferred candidates: {len(data['candidates'])}")


class TestSingleCandidate:
    """Tests for GET /api/promotions/candidates/{id}"""
    
    def test_get_single_candidate(self, auth_session):
        """Get a single candidate by ID"""
        # First get all candidates to find one
        response = auth_session.get(f"{BASE_URL}/api/promotions/candidates")
        assert response.status_code == 200
        
        data = response.json()
        if data["total"] == 0:
            pytest.skip("No candidates available to test")
        
        candidate_id = data["candidates"][0]["id"]
        
        # Get single candidate
        response = auth_session.get(f"{BASE_URL}/api/promotions/candidates/{candidate_id}")
        assert response.status_code == 200
        
        candidate = response.json()
        assert candidate["id"] == candidate_id
        assert "signals" in candidate
        assert "promotion_types" in candidate
        assert "status" in candidate
        assert "page_name" in candidate
        assert "quality_score" in candidate
        
        # Verify signals have explanations
        for signal in candidate.get("signals", []):
            assert "signal" in signal
            assert "explanation" in signal
            assert "value" in signal
        
        print(f"✓ Got candidate: {candidate['page_name']} v{candidate.get('version_number')}")
        print(f"  Signals: {len(candidate.get('signals', []))}")
    
    def test_get_nonexistent_candidate(self, auth_session):
        """Get non-existent candidate returns 404"""
        fake_id = str(uuid.uuid4())
        response = auth_session.get(f"{BASE_URL}/api/promotions/candidates/{fake_id}")
        assert response.status_code == 404
        print("✓ Non-existent candidate returns 404")


class TestPagePromotions:
    """Tests for GET /api/promotions/page/{page_id}"""
    
    def test_get_page_promotions(self, auth_session):
        """Get promotion candidates for a specific page"""
        response = auth_session.get(f"{BASE_URL}/api/promotions/page/{HOMEPAGE_PAGE_ID}")
        assert response.status_code == 200
        
        data = response.json()
        assert "candidates" in data
        assert "total" in data
        
        # All candidates should be for this page
        for c in data["candidates"]:
            assert c["page_id"] == HOMEPAGE_PAGE_ID
        
        print(f"✓ Got {data['total']} candidates for Homepage")
    
    def test_get_page_promotions_nonexistent(self, auth_session):
        """Get promotions for non-existent page returns empty list"""
        fake_page_id = str(uuid.uuid4())
        response = auth_session.get(f"{BASE_URL}/api/promotions/page/{fake_page_id}")
        assert response.status_code == 200
        
        data = response.json()
        assert data["total"] == 0
        assert data["candidates"] == []
        print("✓ Non-existent page returns empty candidates list")


class TestPromotionActions:
    """Tests for POST /api/promotions/candidates/{id}/action"""
    
    def test_action_dismiss(self, auth_session):
        """Test dismiss action on a candidate"""
        # First get a pending candidate
        response = auth_session.get(f"{BASE_URL}/api/promotions/candidates?status=pending")
        assert response.status_code == 200
        
        data = response.json()
        if len(data["candidates"]) == 0:
            pytest.skip("No pending candidates to test dismiss action")
        
        candidate = data["candidates"][0]
        candidate_id = candidate["id"]
        
        # Dismiss the candidate
        response = auth_session.post(
            f"{BASE_URL}/api/promotions/candidates/{candidate_id}/action",
            json={"action": "dismiss", "notes": "TEST_dismissed for testing"}
        )
        assert response.status_code == 200
        
        result = response.json()
        assert result["status"] == "dismissed"
        assert result["action_taken"] == "dismiss"
        assert result["resolved_at"] is not None
        
        print(f"✓ Dismissed candidate: {candidate['page_name']}")
    
    def test_action_decide_later(self, auth_session):
        """Test decide-later action on a candidate"""
        # First evaluate to create a fresh candidate
        response = auth_session.post(
            f"{BASE_URL}/api/promotions/evaluate/{HOMEPAGE_PAGE_ID}/{HOMEPAGE_VERSION_ID}"
        )
        
        # Get a pending candidate
        response = auth_session.get(f"{BASE_URL}/api/promotions/candidates?status=pending")
        assert response.status_code == 200
        
        data = response.json()
        if len(data["candidates"]) == 0:
            pytest.skip("No pending candidates to test decide-later action")
        
        candidate = data["candidates"][0]
        candidate_id = candidate["id"]
        
        # Defer the candidate
        response = auth_session.post(
            f"{BASE_URL}/api/promotions/candidates/{candidate_id}/action",
            json={"action": "decide-later", "notes": "TEST_deferred for later review"}
        )
        assert response.status_code == 200
        
        result = response.json()
        assert result["status"] == "deferred"
        assert result["action_taken"] == "decide-later"
        
        print(f"✓ Deferred candidate: {candidate['page_name']}")
    
    def test_action_invalid(self, auth_session):
        """Test invalid action returns 400"""
        # Get any candidate
        response = auth_session.get(f"{BASE_URL}/api/promotions/candidates")
        assert response.status_code == 200
        
        data = response.json()
        if data["total"] == 0:
            pytest.skip("No candidates to test invalid action")
        
        candidate_id = data["candidates"][0]["id"]
        
        # Try invalid action
        response = auth_session.post(
            f"{BASE_URL}/api/promotions/candidates/{candidate_id}/action",
            json={"action": "invalid-action"}
        )
        assert response.status_code == 400
        print("✓ Invalid action returns 400")
    
    def test_action_on_nonexistent_candidate(self, auth_session):
        """Test action on non-existent candidate returns 404"""
        fake_id = str(uuid.uuid4())
        response = auth_session.post(
            f"{BASE_URL}/api/promotions/candidates/{fake_id}/action",
            json={"action": "dismiss"}
        )
        assert response.status_code == 404
        print("✓ Action on non-existent candidate returns 404")


class TestPromoteExemplar:
    """Tests for promote-exemplar action"""
    
    def test_promote_exemplar_creates_exemplar(self, auth_session):
        """Test that promote-exemplar actually creates an exemplar"""
        # Get a pending/deferred candidate that can be promoted to exemplar
        response = auth_session.get(f"{BASE_URL}/api/promotions/candidates")
        assert response.status_code == 200
        
        data = response.json()
        candidate = None
        for c in data["candidates"]:
            if c["status"] in ["pending", "deferred"] and "exemplar" in c.get("promotion_types", []):
                candidate = c
                break
        
        if not candidate:
            pytest.skip("No candidate available for exemplar promotion test")
        
        # Check if this version is already an exemplar
        response = auth_session.get(f"{BASE_URL}/api/exemplars")
        assert response.status_code == 200
        exemplars = response.json().get("exemplars", [])
        already_exemplar = any(e["version_id"] == candidate["version_id"] for e in exemplars)
        
        if already_exemplar:
            # Try to promote - should get 409
            response = auth_session.post(
                f"{BASE_URL}/api/promotions/candidates/{candidate['id']}/action",
                json={"action": "promote-exemplar", "notes": "TEST_promoted via test"}
            )
            assert response.status_code == 409, "Expected 409 for already-exemplar version"
            print(f"✓ Correctly returned 409 for already-exemplar version")
        else:
            # Promote to exemplar
            response = auth_session.post(
                f"{BASE_URL}/api/promotions/candidates/{candidate['id']}/action",
                json={"action": "promote-exemplar", "notes": "TEST_promoted via test", "is_primary": False}
            )
            assert response.status_code == 200
            
            result = response.json()
            assert result["status"] == "promoted"
            assert result["action_taken"] == "promote-exemplar"
            assert "exemplar_id" in result.get("action_details", {})
            
            # Verify exemplar was created
            exemplar_id = result["action_details"]["exemplar_id"]
            response = auth_session.get(f"{BASE_URL}/api/exemplars/{exemplar_id}")
            assert response.status_code == 200
            
            exemplar = response.json()
            assert exemplar["version_id"] == candidate["version_id"]
            print(f"✓ Created exemplar: {exemplar['page_name']} v{exemplar['version_number']}")


class TestCreateTemplate:
    """Tests for create-template action"""
    
    def test_create_template_creates_house_template(self, auth_session):
        """Test that create-template actually creates a house template"""
        # Get a pending/deferred candidate that can be promoted to template
        response = auth_session.get(f"{BASE_URL}/api/promotions/candidates")
        assert response.status_code == 200
        
        data = response.json()
        candidate = None
        for c in data["candidates"]:
            if c["status"] in ["pending", "deferred"] and "template" in c.get("promotion_types", []):
                candidate = c
                break
        
        if not candidate:
            pytest.skip("No candidate available for template creation test")
        
        # Create template
        response = auth_session.post(
            f"{BASE_URL}/api/promotions/candidates/{candidate['id']}/action",
            json={"action": "create-template", "notes": "TEST_Template Pattern", "is_primary": False}
        )
        assert response.status_code == 200
        
        result = response.json()
        assert result["status"] == "promoted"
        assert result["action_taken"] == "create-template"
        assert "template_id" in result.get("action_details", {})
        
        # Verify template was created
        template_id = result["action_details"]["template_id"]
        response = auth_session.get(f"{BASE_URL}/api/house-templates/{template_id}")
        assert response.status_code == 200
        
        template = response.json()
        assert template["source_version_id"] == candidate["version_id"]
        assert "structural_pattern" in template
        print(f"✓ Created template: {template['template_name']}")


class TestSaveStyleCandidate:
    """Tests for save-style-candidate action"""
    
    def test_save_style_candidate(self, auth_session):
        """Test that save-style-candidate saves the candidate"""
        # Get a pending/deferred candidate that can be saved as style candidate
        response = auth_session.get(f"{BASE_URL}/api/promotions/candidates")
        assert response.status_code == 200
        
        data = response.json()
        candidate = None
        for c in data["candidates"]:
            if c["status"] in ["pending", "deferred"] and "style-candidate" in c.get("promotion_types", []):
                candidate = c
                break
        
        if not candidate:
            pytest.skip("No candidate available for style candidate test")
        
        # Save as style candidate
        response = auth_session.post(
            f"{BASE_URL}/api/promotions/candidates/{candidate['id']}/action",
            json={"action": "save-style-candidate", "notes": "TEST_Style candidate for review"}
        )
        assert response.status_code == 200
        
        result = response.json()
        assert result["status"] == "promoted"
        assert result["action_taken"] == "save-style-candidate"
        assert "candidate_type" in result.get("action_details", {})
        assert result["action_details"]["candidate_type"] == "style-profile"
        
        print(f"✓ Saved style candidate: {candidate['page_name']}")


class TestSignalExplanations:
    """Tests for signal explanations being human-readable"""
    
    def test_signals_have_explanations(self, auth_session):
        """Verify all signals have plain-language explanations"""
        response = auth_session.get(f"{BASE_URL}/api/promotions/candidates")
        assert response.status_code == 200
        
        data = response.json()
        if data["total"] == 0:
            pytest.skip("No candidates to verify signals")
        
        # Check signals in first candidate
        candidate = data["candidates"][0]
        signals = candidate.get("signals", [])
        
        for signal in signals:
            assert "signal" in signal, "Signal missing 'signal' field"
            assert "explanation" in signal, f"Signal {signal['signal']} missing 'explanation'"
            assert "value" in signal, f"Signal {signal['signal']} missing 'value'"
            
            # Explanation should be a non-empty string
            assert isinstance(signal["explanation"], str)
            assert len(signal["explanation"]) > 10, f"Explanation too short: {signal['explanation']}"
        
        print(f"✓ All {len(signals)} signals have valid explanations")
        for s in signals[:3]:  # Print first 3 as examples
            print(f"  - {s['signal']}: {s['explanation'][:60]}...")


class TestCleanup:
    """Cleanup test data"""
    
    def test_cleanup_test_templates(self, auth_session):
        """Remove TEST_ prefixed templates"""
        response = auth_session.get(f"{BASE_URL}/api/house-templates")
        if response.status_code == 200:
            templates = response.json().get("templates", [])
            for t in templates:
                if t.get("template_name", "").startswith("TEST_"):
                    auth_session.delete(f"{BASE_URL}/api/house-templates/{t['id']}")
                    print(f"  Cleaned up template: {t['template_name']}")
        print("✓ Cleanup complete")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
