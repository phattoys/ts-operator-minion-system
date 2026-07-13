"""Backend tests for Founder Command Center endpoints."""
import os
import pytest
import requests
from pathlib import Path

# Load BASE_URL from frontend env to avoid empty env issue
def _load_base_url():
    env_url = os.environ.get("REACT_APP_BACKEND_URL")
    if env_url:
        return env_url.rstrip("/")
    env_path = Path("/app/frontend/.env")
    if env_path.exists():
        for line in env_path.read_text().splitlines():
            if line.startswith("REACT_APP_BACKEND_URL="):
                return line.split("=", 1)[1].strip().rstrip("/")
    raise RuntimeError("REACT_APP_BACKEND_URL not set")


BASE_URL = _load_base_url()
PASSWORD = "TSFounder!Vault2026#Secure"


@pytest.fixture(scope="module")
def auth_token():
    r = requests.post(f"{BASE_URL}/api/auth/login", json={"password": PASSWORD}, timeout=30)
    assert r.status_code == 200, f"Login failed: {r.status_code} {r.text}"
    return r.json()["access_token"]


@pytest.fixture(scope="module")
def headers(auth_token):
    return {"Authorization": f"Bearer {auth_token}", "Content-Type": "application/json"}


# -------- Dashboard --------
class TestDashboard:
    def test_dashboard_shape(self, headers):
        r = requests.get(f"{BASE_URL}/api/command-center/dashboard", headers=headers, timeout=30)
        assert r.status_code == 200, r.text
        data = r.json()
        for key in ["stats", "actions", "ready_for_review", "ready_to_launch",
                    "launched", "blocked", "next_unlocks", "structure_map"]:
            assert key in data, f"missing key {key}"

        stats = data["stats"]
        for k in ["total_pages", "review_ready", "launch_ready", "launched",
                  "planned", "blocked", "deferred", "generating", "can_generate"]:
            assert k in stats

        assert isinstance(data["structure_map"], list)
        assert stats["total_pages"] >= 1
        # 25 pages expected per context
        assert stats["total_pages"] >= 20, f"Expected ~25 pages, got {stats['total_pages']}"

    def test_dashboard_unauth(self):
        r = requests.get(f"{BASE_URL}/api/command-center/dashboard", timeout=15)
        assert r.status_code in (401, 403)

    def test_actions_today_types(self, headers):
        r = requests.get(f"{BASE_URL}/api/command-center/dashboard", headers=headers, timeout=30)
        data = r.json()
        types = {a["type"] for a in data["actions"]}
        # Each action should have message + count
        for a in data["actions"]:
            assert "type" in a and "message" in a and "count" in a and "priority" in a
        # not strict on which types appear
        assert isinstance(types, set)

    def test_structure_map_fields(self, headers):
        r = requests.get(f"{BASE_URL}/api/command-center/dashboard", headers=headers, timeout=30)
        sm = r.json()["structure_map"]
        assert len(sm) >= 1
        sample = sm[0]
        for f in ["id", "page_code", "page_name", "page_family", "status",
                  "has_content", "priority_score", "wp_page_id"]:
            assert f in sample, f"structure_map missing {f}"

    def test_no_mongo_id_in_response(self, headers):
        r = requests.get(f"{BASE_URL}/api/command-center/dashboard", headers=headers, timeout=30)
        body = r.text
        # ensure raw _id not leaked
        assert '"_id"' not in body


# -------- Page Codes --------
class TestPageCodes:
    def test_page_codes_list(self, headers):
        r = requests.get(f"{BASE_URL}/api/command-center/page-codes", headers=headers, timeout=30)
        assert r.status_code == 200, r.text
        data = r.json()
        assert "codes" in data and "scheme" in data and "total" in data
        scheme = data["scheme"]
        for fam in ["Core Hub", "District", "Trust", "FAQ/Support",
                    "Guided Path", "Conversion", "Category Support",
                    "Media/Asset", "Digital/Tools"]:
            assert fam in scheme
        # codes auto-generated → all pages with families should have codes
        assert data["total"] >= 1
        # codes should match family prefix scheme
        for c in data["codes"]:
            code = c.get("page_code", "")
            fam = c.get("page_family", "")
            if fam in scheme:
                expected_prefix = scheme[fam]
                assert code.startswith(expected_prefix), (
                    f"Code {code} for family {fam} doesn't start with {expected_prefix}"
                )

    def test_update_page_code_override(self, headers):
        r = requests.get(f"{BASE_URL}/api/command-center/page-codes", headers=headers, timeout=30)
        codes = r.json()["codes"]
        assert codes
        target = codes[0]
        original_code = target["page_code"]
        page_id = target["id"]

        # Set to a unique test code
        test_code = "TESTZ99"
        u = requests.put(
            f"{BASE_URL}/api/command-center/pages/{page_id}/code",
            headers=headers, json={"page_code": test_code}, timeout=15,
        )
        assert u.status_code == 200, u.text
        assert u.json()["page_code"] == test_code

        # Verify persisted
        r2 = requests.get(f"{BASE_URL}/api/command-center/page-codes", headers=headers, timeout=30)
        found = next((c for c in r2.json()["codes"] if c["id"] == page_id), None)
        assert found and found["page_code"] == test_code

        # Restore
        requests.put(
            f"{BASE_URL}/api/command-center/pages/{page_id}/code",
            headers=headers, json={"page_code": original_code}, timeout=15,
        )

    def test_update_page_code_duplicate_rejected(self, headers):
        r = requests.get(f"{BASE_URL}/api/command-center/page-codes", headers=headers, timeout=30)
        codes = r.json()["codes"]
        if len(codes) < 2:
            pytest.skip("Need 2+ pages with codes")
        a, b = codes[0], codes[1]
        u = requests.put(
            f"{BASE_URL}/api/command-center/pages/{a['id']}/code",
            headers=headers, json={"page_code": b["page_code"]}, timeout=15,
        )
        assert u.status_code == 409


# -------- Page Structure Update --------
class TestPageStructure:
    def test_update_titles(self, headers):
        r = requests.get(f"{BASE_URL}/api/command-center/page-codes", headers=headers, timeout=30)
        codes = r.json()["codes"]
        page_id = codes[0]["id"]

        payload = {
            "working_title": "TEST_WORKING_TITLE",
            "public_title": "TEST_PUBLIC_TITLE",
            "menu_destination": "Top Nav",
            "footer_destination": "Footer Col 1",
            "funnel_stage": "Awareness",
            "launch_priority": 5,
        }
        u = requests.put(
            f"{BASE_URL}/api/command-center/pages/{page_id}/structure",
            headers=headers, json=payload, timeout=15,
        )
        assert u.status_code == 200, u.text
        body = u.json()
        for k, v in payload.items():
            assert body.get(k) == v, f"{k} not persisted"


# -------- Minion Directory --------
class TestMinionDirectory:
    def test_minion_directory(self, headers):
        r = requests.get(f"{BASE_URL}/api/command-center/minion-directory", headers=headers, timeout=30)
        assert r.status_code == 200, r.text
        data = r.json()
        assert "minions" in data and data["total"] >= 10
        codes = {m["code"] for m in data["minions"]}
        for expected in ["page_ops", "worker_queue", "wp_placement",
                         "field_listing", "product_intake", "catalog",
                         "lead_magnets", "spec_writer", "comms", "spine"]:
            assert expected in codes, f"Missing minion {expected}"
        for m in data["minions"]:
            for f in ["name", "code", "role", "what_it_does", "stats", "next_action", "nav_path"]:
                assert f in m


# -------- Batch Launch --------
class TestBatchLaunch:
    def test_batch_launch_empty(self, headers):
        r = requests.post(
            f"{BASE_URL}/api/command-center/batch-launch",
            headers=headers, json={"page_ids": []}, timeout=15,
        )
        assert r.status_code == 400

    def test_batch_launch_skips_non_approved(self, headers):
        # Find a planned page
        d = requests.get(f"{BASE_URL}/api/command-center/dashboard", headers=headers, timeout=30).json()
        planned = [p for p in d["structure_map"] if p["status"] == "Planned"]
        if not planned:
            pytest.skip("No planned pages to test skip path")
        r = requests.post(
            f"{BASE_URL}/api/command-center/batch-launch",
            headers=headers, json={"page_ids": [planned[0]["id"]]}, timeout=30,
        )
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["skipped"] >= 1
        assert body["launched"] == 0

    def test_batch_launch_unknown_id(self, headers):
        r = requests.post(
            f"{BASE_URL}/api/command-center/batch-launch",
            headers=headers, json={"page_ids": ["nonexistent-id-xyz"]}, timeout=15,
        )
        assert r.status_code == 200
        body = r.json()
        assert any("not found" in e for e in body["errors"])


# -------- Batch Generate --------
class TestBatchGenerate:
    def test_batch_generate_empty(self, headers):
        r = requests.post(
            f"{BASE_URL}/api/command-center/batch-generate",
            headers=headers, json={"page_ids": []}, timeout=15,
        )
        assert r.status_code == 400

    def test_batch_generate_sets_generating(self, headers):
        d = requests.get(f"{BASE_URL}/api/command-center/dashboard", headers=headers, timeout=30).json()
        planned = [p for p in d["structure_map"] if p["status"] == "Planned" and not p["has_content"]]
        if not planned:
            pytest.skip("No planned pages without content")
        target_id = planned[0]["id"]
        r = requests.post(
            f"{BASE_URL}/api/command-center/batch-generate",
            headers=headers, json={"page_ids": [target_id]}, timeout=15,
        )
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["queued"] + body["skipped"] == 1

        # Verify status changed in dashboard
        d2 = requests.get(f"{BASE_URL}/api/command-center/dashboard", headers=headers, timeout=30).json()
        target = next((p for p in d2["structure_map"] if p["id"] == target_id), None)
        assert target is not None
        if body["queued"] == 1:
            assert target["status"] == "Generating"
            # Restore to Planned via direct DB-like API isn't available;
            # leave as Generating — main agent's Page Ops can pick up.


# -------- Regression: existing endpoints still work --------
class TestRegression:
    def test_pages_list(self, headers):
        r = requests.get(f"{BASE_URL}/api/pages", headers=headers, timeout=30)
        assert r.status_code == 200
        data = r.json()
        assert isinstance(data, (list, dict))

    def test_worker_stats(self, headers):
        r = requests.get(f"{BASE_URL}/api/worker-queue/stats", headers=headers, timeout=30)
        assert r.status_code == 200
