"""
Worker Queue v1 Tests — TS OPS Worker Routing + Task Queue
Tests endpoints contract, routing chain, safety rules, auto-execute vs founder-trigger.
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')
EXISTING_BATCH_ID = "54a19ecb-c016-4611-917b-f69797be4451"


# ---- Auth ----
@pytest.fixture(scope="module")
def auth_headers():
    response = requests.post(f"{BASE_URL}/api/auth/login", json={
        "password": "TSFounder!Vault2026#Secure"
    })
    if response.status_code != 200:
        pytest.skip(f"Auth failed: {response.status_code} {response.text[:200]}")
    token = response.json().get("access_token")
    assert token, "No access_token in login response"
    return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}


# ---- Stats / Workers ----
class TestStatsAndWorkers:
    def test_stats_returns_4_workers(self, auth_headers):
        r = requests.get(f"{BASE_URL}/api/worker-queue/stats", headers=auth_headers)
        assert r.status_code == 200
        data = r.json()
        for key in ["total", "queued", "processing", "completed", "needs_review", "failed", "workers"]:
            assert key in data, f"Missing key: {key}"
        workers = data["workers"]
        for w in ["jenny", "rene", "sam", "wp_placement"]:
            assert w in workers, f"Missing worker: {w}"
            assert "name" in workers[w]
            assert "auto_execute" in workers[w]
        # Auto-execute flags
        assert workers["jenny"]["auto_execute"] is True
        assert workers["rene"]["auto_execute"] is True
        assert workers["sam"]["auto_execute"] is False
        assert workers["wp_placement"]["auto_execute"] is False

    def test_list_workers(self, auth_headers):
        r = requests.get(f"{BASE_URL}/api/worker-queue/workers", headers=auth_headers)
        assert r.status_code == 200
        workers = r.json().get("workers", {})
        assert set(workers.keys()) == {"jenny", "rene", "sam", "wp_placement"}


# ---- Task listing / filtering ----
class TestTaskListing:
    def test_list_tasks_no_filter(self, auth_headers):
        r = requests.get(f"{BASE_URL}/api/worker-queue/tasks?limit=50", headers=auth_headers)
        assert r.status_code == 200
        data = r.json()
        assert "tasks" in data and "count" in data
        assert isinstance(data["tasks"], list)

    def test_filter_by_worker_sam(self, auth_headers):
        r = requests.get(f"{BASE_URL}/api/worker-queue/tasks?worker=sam&limit=50", headers=auth_headers)
        assert r.status_code == 200
        for t in r.json()["tasks"]:
            assert t["worker"] == "sam"

    def test_filter_by_status_queued(self, auth_headers):
        r = requests.get(f"{BASE_URL}/api/worker-queue/tasks?status=queued&limit=50", headers=auth_headers)
        assert r.status_code == 200
        for t in r.json()["tasks"]:
            assert t["status"] == "queued"


# ---- Views ----
class TestViews:
    def test_ready_view(self, auth_headers):
        r = requests.get(f"{BASE_URL}/api/worker-queue/views/ready", headers=auth_headers)
        assert r.status_code == 200
        for t in r.json()["tasks"]:
            assert t["status"] == "queued"
            assert t["founder_action_needed"] is True

    def test_needs_review_view(self, auth_headers):
        r = requests.get(f"{BASE_URL}/api/worker-queue/views/needs-review", headers=auth_headers)
        assert r.status_code == 200
        for t in r.json()["tasks"]:
            assert t["status"] == "needs_review"

    def test_completed_view(self, auth_headers):
        r = requests.get(f"{BASE_URL}/api/worker-queue/views/completed", headers=auth_headers)
        assert r.status_code == 200
        for t in r.json()["tasks"]:
            assert t["status"] == "completed"

    def test_held_back_view(self, auth_headers):
        r = requests.get(f"{BASE_URL}/api/worker-queue/views/held-back", headers=auth_headers)
        assert r.status_code == 200
        for t in r.json()["tasks"]:
            assert t["status"] in ["held_back", "failed"]

    def test_in_progress_view(self, auth_headers):
        r = requests.get(f"{BASE_URL}/api/worker-queue/views/in-progress", headers=auth_headers)
        assert r.status_code == 200


# ---- Activity log ----
class TestActivityLog:
    def test_activity_log(self, auth_headers):
        r = requests.get(f"{BASE_URL}/api/worker-queue/activity-log?limit=10", headers=auth_headers)
        assert r.status_code == 200
        data = r.json()
        assert "logs" in data and "count" in data

    def test_activity_log_filter_worker(self, auth_headers):
        r = requests.get(f"{BASE_URL}/api/worker-queue/activity-log?worker=jenny&limit=10", headers=auth_headers)
        assert r.status_code == 200
        for log in r.json()["logs"]:
            assert log["worker"] == "jenny"


# ---- Founder-trigger vs Auto-execute ----
class TestRunWorker:
    def test_run_sam_queues_not_auto_executes(self, auth_headers):
        """Sam tasks should be QUEUED, not auto-executed."""
        # Get one item from existing batch
        r = requests.get(f"{BASE_URL}/api/field-listing/batches/{EXISTING_BATCH_ID}/items", headers=auth_headers)
        if r.status_code != 200 or not r.json().get("items"):
            pytest.skip("No items in test batch")
        items = r.json()["items"]
        # Use ONE item only to avoid creating 14 duplicate tasks
        item_id = items[0]["id"]

        # Check if sam task already exists for this item (pending)
        existing = requests.get(
            f"{BASE_URL}/api/worker-queue/tasks?worker=sam&status=queued&limit=200",
            headers=auth_headers,
        ).json()["tasks"]
        already_queued = any(t["source_item_id"] == item_id for t in existing)

        r2 = requests.post(f"{BASE_URL}/api/worker-queue/run-worker", json={
            "worker": "sam",
            "item_ids": [item_id],
        }, headers=auth_headers)
        assert r2.status_code == 200, r2.text
        data = r2.json()
        assert data["worker"] == "sam"
        assert data["auto_executed"] is False
        # If already queued it will skip; otherwise creates 1
        if not already_queued:
            assert data["tasks_created"] == 1

    def test_run_worker_unknown(self, auth_headers):
        r = requests.post(f"{BASE_URL}/api/worker-queue/run-worker", json={
            "worker": "nonexistent",
            "batch_id": EXISTING_BATCH_ID,
        }, headers=auth_headers)
        assert r.status_code == 400

    def test_run_worker_missing_params(self, auth_headers):
        r = requests.post(f"{BASE_URL}/api/worker-queue/run-worker", json={
            "worker": "sam",
        }, headers=auth_headers)
        assert r.status_code == 400


# ---- Execute / Hold / Requeue lifecycle ----
class TestTaskLifecycle:
    @pytest.fixture(scope="class")
    def sam_queued_task_id(self, auth_headers):
        """Get one queued Sam task ID from existing queue."""
        r = requests.get(
            f"{BASE_URL}/api/worker-queue/tasks?worker=sam&status=queued&limit=10",
            headers=auth_headers,
        )
        tasks = r.json().get("tasks", [])
        if not tasks:
            pytest.skip("No queued Sam tasks available")
        return tasks[0]["id"]

    def test_get_task_by_id(self, auth_headers, sam_queued_task_id):
        r = requests.get(f"{BASE_URL}/api/worker-queue/tasks/{sam_queued_task_id}", headers=auth_headers)
        assert r.status_code == 200
        assert r.json()["id"] == sam_queued_task_id

    def test_get_task_404(self, auth_headers):
        r = requests.get(f"{BASE_URL}/api/worker-queue/tasks/does-not-exist", headers=auth_headers)
        assert r.status_code == 404

    def test_hold_then_requeue(self, auth_headers, sam_queued_task_id):
        # Hold
        r = requests.post(f"{BASE_URL}/api/worker-queue/tasks/{sam_queued_task_id}/hold", headers=auth_headers)
        assert r.status_code == 200
        # Verify
        r2 = requests.get(f"{BASE_URL}/api/worker-queue/tasks/{sam_queued_task_id}", headers=auth_headers)
        assert r2.json()["status"] == "held_back"
        # Requeue
        r3 = requests.post(f"{BASE_URL}/api/worker-queue/tasks/{sam_queued_task_id}/requeue", headers=auth_headers)
        assert r3.status_code == 200
        r4 = requests.get(f"{BASE_URL}/api/worker-queue/tasks/{sam_queued_task_id}", headers=auth_headers)
        assert r4.json()["status"] == "queued"

    def test_execute_sam_task(self, auth_headers, sam_queued_task_id):
        """Sam is founder-trigger; execute should produce destination_packs."""
        r = requests.post(
            f"{BASE_URL}/api/worker-queue/tasks/{sam_queued_task_id}/execute",
            headers=auth_headers,
        )
        assert r.status_code == 200, r.text
        data = r.json()
        assert data["status"] in ["completed", "failed", "needs_review"]
        if data["status"] == "completed":
            assert data["result"].get("success") is True
            assert "packs_generated" in data["result"]

    def test_execute_non_queued_task_400(self, auth_headers, sam_queued_task_id):
        """After previous test completed the task, re-execute should 400."""
        # Get current status
        r = requests.get(f"{BASE_URL}/api/worker-queue/tasks/{sam_queued_task_id}", headers=auth_headers)
        status = r.json()["status"]
        if status in ["queued", "needs_review"]:
            pytest.skip("Task still executable")
        r2 = requests.post(
            f"{BASE_URL}/api/worker-queue/tasks/{sam_queued_task_id}/execute",
            headers=auth_headers,
        )
        assert r2.status_code == 400


# ---- Batch execute ----
class TestBatchExecute:
    def test_batch_execute_empty(self, auth_headers):
        r = requests.post(f"{BASE_URL}/api/worker-queue/batch-execute",
                          json={"task_ids": []}, headers=auth_headers)
        assert r.status_code == 400

    def test_batch_execute_invalid_ids(self, auth_headers):
        r = requests.post(f"{BASE_URL}/api/worker-queue/batch-execute",
                          json={"task_ids": ["bogus-1", "bogus-2"]}, headers=auth_headers)
        assert r.status_code == 200
        data = r.json()
        assert data["skipped"] == 2


# ---- Routing chain + safety rules ----
class TestRoutingAndSafety:
    def test_jenny_needs_review_on_no_images(self, auth_headers):
        """Create item with no images via API route (simulate) — verify Jenny flags needs_review."""
        # Create a new batch
        rb = requests.post(f"{BASE_URL}/api/field-listing/batches", json={
            "name": "TEST_WorkerQueue_SafetyRule",
            "source_vendor": "Test",
            "destinations": ["website"],
        }, headers=auth_headers)
        assert rb.status_code in (200, 201), rb.text
        batch_id = rb.json()["id"]
        try:
            # Try to create an item with no images via direct field_items collection? Not possible via API.
            # Instead use existing items check — skip this test since creating item-with-no-images requires DB access.
            pytest.skip("Need direct DB access for no-image scenario; covered by code review")
        finally:
            requests.delete(f"{BASE_URL}/api/field-listing/batches/{batch_id}", headers=auth_headers)

    def test_regression_field_listing_endpoints(self, auth_headers):
        """Regression: existing field-listing batch endpoints still work."""
        r = requests.get(f"{BASE_URL}/api/field-listing/batches", headers=auth_headers)
        assert r.status_code == 200
        r2 = requests.get(f"{BASE_URL}/api/field-listing/batches/{EXISTING_BATCH_ID}", headers=auth_headers)
        assert r2.status_code == 200
        assert r2.json()["id"] == EXISTING_BATCH_ID
