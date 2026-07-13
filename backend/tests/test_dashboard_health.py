"""
Test suite for Operator Health Dashboard API
Tests the GET /api/dashboard/health endpoint which aggregates data from all modules
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')
PASSWORD = "TSFounder!Vault2026#Secure"


@pytest.fixture(scope="module")
def auth_token():
    """Get authentication token for all tests"""
    response = requests.post(
        f"{BASE_URL}/api/auth/login",
        json={"password": PASSWORD}
    )
    assert response.status_code == 200, f"Auth failed: {response.text}"
    return response.json()["access_token"]


@pytest.fixture
def auth_headers(auth_token):
    """Headers with auth token"""
    return {"Authorization": f"Bearer {auth_token}"}


class TestDashboardHealthEndpoint:
    """Tests for GET /api/dashboard/health"""

    def test_health_requires_auth(self):
        """Dashboard health endpoint requires authentication"""
        response = requests.get(f"{BASE_URL}/api/dashboard/health")
        assert response.status_code == 401

    def test_health_returns_200(self, auth_headers):
        """Dashboard health endpoint returns 200 with valid auth"""
        response = requests.get(
            f"{BASE_URL}/api/dashboard/health",
            headers=auth_headers
        )
        assert response.status_code == 200

    def test_health_response_structure(self, auth_headers):
        """Dashboard health response has correct top-level structure"""
        response = requests.get(
            f"{BASE_URL}/api/dashboard/health",
            headers=auth_headers
        )
        data = response.json()
        
        # Check top-level keys
        assert "generated_at" in data
        assert "modules" in data
        assert "ready_to_publish" in data
        assert "bottlenecks" in data
        assert "recent_activity" in data

    def test_modules_structure(self, auth_headers):
        """Modules object contains all 5 module sections"""
        response = requests.get(
            f"{BASE_URL}/api/dashboard/health",
            headers=auth_headers
        )
        modules = response.json()["modules"]
        
        # All 5 modules present
        assert "page_ops" in modules
        assert "lead_magnets" in modules
        assert "product_intake" in modules
        assert "specs" in modules
        assert "promotions" in modules

    def test_page_ops_structure(self, auth_headers):
        """Page Ops module has correct structure"""
        response = requests.get(
            f"{BASE_URL}/api/dashboard/health",
            headers=auth_headers
        )
        page_ops = response.json()["modules"]["page_ops"]
        
        assert "total" in page_ops
        assert "by_status" in page_ops
        assert "approved" in page_ops
        assert "stuck" in page_ops
        assert "velocity" in page_ops
        
        # Velocity structure
        velocity = page_ops["velocity"]
        assert "this_week" in velocity
        assert "last_week" in velocity
        assert "trend" in velocity
        assert velocity["trend"] in ["up", "down", "flat"]

    def test_lead_magnets_structure(self, auth_headers):
        """Lead Magnets module has correct structure"""
        response = requests.get(
            f"{BASE_URL}/api/dashboard/health",
            headers=auth_headers
        )
        lm = response.json()["modules"]["lead_magnets"]
        
        assert "total" in lm
        assert "by_status" in lm
        assert "published" in lm
        assert "ready" in lm
        assert "drafts" in lm
        assert "total_downloads" in lm

    def test_product_intake_structure(self, auth_headers):
        """Product Intake module has correct structure"""
        response = requests.get(
            f"{BASE_URL}/api/dashboard/health",
            headers=auth_headers
        )
        intake = response.json()["modules"]["product_intake"]
        
        assert "total_sessions" in intake
        assert "total_items" in intake
        assert "by_status" in intake
        assert "ready" in intake
        assert "needs_info" in intake
        assert "in_review" in intake
        assert "stuck" in intake
        assert "revenue_estimate" in intake
        assert "velocity" in intake
        
        # Velocity structure
        velocity = intake["velocity"]
        assert "this_week" in velocity
        assert "last_week" in velocity
        assert "trend" in velocity

    def test_specs_structure(self, auth_headers):
        """Specs module has correct structure"""
        response = requests.get(
            f"{BASE_URL}/api/dashboard/health",
            headers=auth_headers
        )
        specs = response.json()["modules"]["specs"]
        
        assert "total" in specs
        assert "by_status" in specs

    def test_promotions_structure(self, auth_headers):
        """Promotions module has correct structure"""
        response = requests.get(
            f"{BASE_URL}/api/dashboard/health",
            headers=auth_headers
        )
        promos = response.json()["modules"]["promotions"]
        
        assert "by_status" in promos
        assert "pending" in promos

    def test_ready_to_publish_structure(self, auth_headers):
        """Ready to publish section has correct structure"""
        response = requests.get(
            f"{BASE_URL}/api/dashboard/health",
            headers=auth_headers
        )
        rtp = response.json()["ready_to_publish"]
        
        assert "pages_approved" in rtp
        assert "lead_magnets_ready" in rtp
        assert "intake_items_ready" in rtp
        assert "total" in rtp
        
        # Total should be sum of components
        expected_total = rtp["pages_approved"] + rtp["lead_magnets_ready"] + rtp["intake_items_ready"]
        assert rtp["total"] == expected_total

    def test_bottlenecks_structure(self, auth_headers):
        """Bottlenecks array has correct item structure"""
        response = requests.get(
            f"{BASE_URL}/api/dashboard/health",
            headers=auth_headers
        )
        bottlenecks = response.json()["bottlenecks"]
        
        assert isinstance(bottlenecks, list)
        
        # If there are bottlenecks, check structure
        for b in bottlenecks:
            assert "module" in b
            assert "issue" in b
            assert "severity" in b
            assert "count" in b
            assert b["severity"] in ["info", "warning", "critical"]

    def test_recent_activity_structure(self, auth_headers):
        """Recent activity array has correct item structure"""
        response = requests.get(
            f"{BASE_URL}/api/dashboard/health",
            headers=auth_headers
        )
        activity = response.json()["recent_activity"]
        
        assert isinstance(activity, list)
        
        # If there are activities, check structure
        for a in activity:
            assert "action" in a
            assert "timestamp" in a

    def test_data_values_are_integers(self, auth_headers):
        """Numeric values are proper integers"""
        response = requests.get(
            f"{BASE_URL}/api/dashboard/health",
            headers=auth_headers
        )
        data = response.json()
        
        # Page ops
        assert isinstance(data["modules"]["page_ops"]["total"], int)
        assert isinstance(data["modules"]["page_ops"]["approved"], int)
        assert isinstance(data["modules"]["page_ops"]["stuck"], int)
        
        # Lead magnets
        assert isinstance(data["modules"]["lead_magnets"]["total"], int)
        assert isinstance(data["modules"]["lead_magnets"]["published"], int)
        assert isinstance(data["modules"]["lead_magnets"]["total_downloads"], int)
        
        # Product intake
        assert isinstance(data["modules"]["product_intake"]["total_sessions"], int)
        assert isinstance(data["modules"]["product_intake"]["total_items"], int)
        
        # Specs
        assert isinstance(data["modules"]["specs"]["total"], int)

    def test_data_matches_known_state(self, auth_headers):
        """Data values match known database state (25 pages, 6 lead magnets, 4 intake items, 6 specs)"""
        response = requests.get(
            f"{BASE_URL}/api/dashboard/health",
            headers=auth_headers
        )
        data = response.json()
        
        # Based on context: 25 pages, 6 lead magnets, 4 intake items in 1 session, 6 specs
        assert data["modules"]["page_ops"]["total"] == 25
        assert data["modules"]["lead_magnets"]["total"] == 6
        assert data["modules"]["product_intake"]["total_items"] == 4
        assert data["modules"]["product_intake"]["total_sessions"] == 1
        assert data["modules"]["specs"]["total"] == 6

    def test_velocity_trend_values(self, auth_headers):
        """Velocity trend is correctly calculated"""
        response = requests.get(
            f"{BASE_URL}/api/dashboard/health",
            headers=auth_headers
        )
        data = response.json()
        
        # Page ops velocity
        page_vel = data["modules"]["page_ops"]["velocity"]
        if page_vel["this_week"] > page_vel["last_week"]:
            assert page_vel["trend"] == "up"
        elif page_vel["this_week"] < page_vel["last_week"]:
            assert page_vel["trend"] == "down"
        else:
            assert page_vel["trend"] == "flat"
        
        # Product intake velocity
        intake_vel = data["modules"]["product_intake"]["velocity"]
        if intake_vel["this_week"] > intake_vel["last_week"]:
            assert intake_vel["trend"] == "up"
        elif intake_vel["this_week"] < intake_vel["last_week"]:
            assert intake_vel["trend"] == "down"
        else:
            assert intake_vel["trend"] == "flat"

    def test_activity_limited_to_15(self, auth_headers):
        """Recent activity is limited to 15 items"""
        response = requests.get(
            f"{BASE_URL}/api/dashboard/health",
            headers=auth_headers
        )
        activity = response.json()["recent_activity"]
        
        assert len(activity) <= 15

    def test_activity_sorted_by_timestamp_desc(self, auth_headers):
        """Recent activity is sorted by timestamp descending (newest first)"""
        response = requests.get(
            f"{BASE_URL}/api/dashboard/health",
            headers=auth_headers
        )
        activity = response.json()["recent_activity"]
        
        if len(activity) > 1:
            timestamps = [a["timestamp"] for a in activity]
            assert timestamps == sorted(timestamps, reverse=True)

    def test_no_mongodb_id_in_response(self, auth_headers):
        """Response does not contain MongoDB _id fields"""
        response = requests.get(
            f"{BASE_URL}/api/dashboard/health",
            headers=auth_headers
        )
        data = response.json()
        
        # Check activity items don't have _id
        for a in data["recent_activity"]:
            assert "_id" not in a
        
        # Check bottlenecks don't have _id
        for b in data["bottlenecks"]:
            assert "_id" not in b
