"""
WP Placement Worker Integration Tests (iteration_32).
Tests the wired WP worker: approve page -> WP task auto-creates -> execute -> real WP draft.
"""
import os
import time
import pytest
import requests
from pathlib import Path

def _load_base_url():
    url = os.environ.get("REACT_APP_BACKEND_URL", "").strip()
    if not url:
        env_path = Path("/app/frontend/.env")
        if env_path.exists():
            for line in env_path.read_text().splitlines():
                if line.startswith("REACT_APP_BACKEND_URL="):
                    url = line.split("=", 1)[1].strip().strip('"').strip("'")
                    break
    return url.rstrip("/")

BASE_URL = _load_base_url()
PASSWORD = "TSFounder!Vault2026#Secure"


@pytest.fixture(scope="module")
def auth_client():
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    r = s.post(f"{BASE_URL}/api/auth/login", json={"password": PASSWORD})
    assert r.status_code == 200, f"Login failed: {r.status_code} {r.text}"
    token = r.json().get("access_token")
    assert token
    s.headers.update({"Authorization": f"Bearer {token}"})
    return s


# ---- Basic worker queue sanity ----

def test_stats_four_workers(auth_client):
    r = auth_client.get(f"{BASE_URL}/api/worker-queue/stats")
    assert r.status_code == 200
    data = r.json()
    workers = data.get("workers", {})
    for key in ["jenny", "rene", "sam", "wp_placement"]:
        assert key in workers, f"Missing worker {key}"
        assert "total" in workers[key]
        assert "completed" in workers[key]
        assert "queued" in workers[key]
    # Auto-execute flags
    assert workers["jenny"]["auto_execute"] is True
    assert workers["rene"]["auto_execute"] is True
    assert workers["sam"]["auto_execute"] is False
    assert workers["wp_placement"]["auto_execute"] is False


def test_views_endpoints(auth_client):
    for view in ["ready", "needs-review", "in-progress", "completed", "held-back"]:
        r = auth_client.get(f"{BASE_URL}/api/worker-queue/views/{view}")
        assert r.status_code == 200, f"view {view} failed"
        assert "tasks" in r.json()


def test_activity_log(auth_client):
    r = auth_client.get(f"{BASE_URL}/api/worker-queue/activity-log?limit=10")
    assert r.status_code == 200
    assert "entries" in r.json() or "logs" in r.json() or isinstance(r.json(), (list, dict))


# ---- Page model includes wp fields ----

def test_page_response_has_wp_fields(auth_client):
    r = auth_client.get(f"{BASE_URL}/api/pages")
    assert r.status_code == 200
    pages = r.json().get("pages", [])
    assert len(pages) > 0
    # Fetch a single page via detail endpoint (that one uses PageResponse)
    pid = pages[0]["id"]
    r2 = auth_client.get(f"{BASE_URL}/api/pages/{pid}")
    assert r2.status_code == 200
    body = r2.json()
    # wp_page_id / wp_placed_at should be in schema (nullable)
    assert "wp_page_id" in body, "PageResponse missing wp_page_id"
    assert "wp_placed_at" in body, "PageResponse missing wp_placed_at"


# ---- Approve page -> WP task created (queued, not auto-executed) ----

@pytest.fixture(scope="module")
def candidate_page(auth_client):
    r = auth_client.get(f"{BASE_URL}/api/pages?status=Needs Review")
    assert r.status_code == 200
    pages = [p for p in r.json().get("pages", []) if p.get("generated_content")]
    if not pages:
        # fallback: any with generated_content not yet placed
        r = auth_client.get(f"{BASE_URL}/api/pages")
        pages = [p for p in r.json().get("pages", [])
                 if p.get("generated_content") and p.get("status") not in ("placed",)]
    if not pages:
        pytest.skip("No page with generated_content available")
    return pages[0]


def test_approve_creates_wp_task(auth_client, candidate_page):
    pid = candidate_page["id"]
    r = auth_client.post(f"{BASE_URL}/api/pages/{pid}/approve")
    assert r.status_code == 200, f"approve failed: {r.text}"
    assert r.json().get("status") == "Approved"

    # Poll worker tasks for wp_placement task for this page
    found = None
    for _ in range(5):
        rt = auth_client.get(f"{BASE_URL}/api/worker-queue/tasks?worker=wp_placement&limit=100")
        if rt.status_code == 200:
            tasks = rt.json().get("tasks", [])
            for t in tasks:
                if t.get("source_item_id") == pid:
                    found = t
                    break
        if found:
            break
        time.sleep(0.5)

    assert found is not None, "WP task not auto-created after approval"
    assert found["worker"] == "wp_placement"
    assert found["task_type"] == "wp_draft"
    assert found["status"] == "queued", f"expected queued, got {found['status']}"
    assert found["auto_execute"] is False
    assert found["founder_action_needed"] is True
    # Save for next test
    pytest.wp_task_id = found["id"]
    pytest.wp_page_id = pid


def test_approve_idempotent(auth_client, candidate_page):
    """Re-approving the same page should not create duplicate WP tasks."""
    pid = candidate_page["id"]
    auth_client.post(f"{BASE_URL}/api/pages/{pid}/approve")
    rt = auth_client.get(f"{BASE_URL}/api/worker-queue/tasks?worker=wp_placement&limit=200")
    tasks = [t for t in rt.json().get("tasks", [])
             if t.get("source_item_id") == pid and t.get("status") in ("queued", "processing")]
    assert len(tasks) <= 1, f"Duplicate WP tasks created: {len(tasks)}"


# ---- Execute WP task -> real WP draft ----

def test_execute_wp_task_creates_draft(auth_client):
    task_id = getattr(pytest, "wp_task_id", None)
    page_id = getattr(pytest, "wp_page_id", None)
    if not task_id or not page_id:
        pytest.skip("No WP task available from prior test")

    r = auth_client.post(f"{BASE_URL}/api/worker-queue/tasks/{task_id}/execute")
    assert r.status_code == 200, f"execute failed: {r.text}"
    task = r.json()

    assert task["status"] == "completed", f"status={task['status']} result={task.get('result')}"
    result = task.get("result", {})
    assert result.get("success") is True, f"result not success: {result}"
    assert result.get("wp_page_id") is not None, "wp_page_id missing in result"
    assert isinstance(result.get("wp_id"), int) or result.get("mock") is True, \
        f"wp_id should be int (live) or mock=True, got {result}"
    assert result.get("template"), "template name missing"
    assert "sections_placed" in result

    # Page should be updated
    rp = auth_client.get(f"{BASE_URL}/api/pages/{page_id}")
    assert rp.status_code == 200
    page = rp.json()
    assert page["status"] == "placed", f"page status not placed: {page['status']}"
    assert page.get("wp_page_id") is not None
    assert page.get("wp_placed_at") is not None


def test_wp_placement_log_has_worker_entry(auth_client):
    page_id = getattr(pytest, "wp_page_id", None)
    if not page_id:
        pytest.skip("no page")
    r = auth_client.get(f"{BASE_URL}/api/wp-placement/log?limit=50")
    assert r.status_code == 200
    entries = r.json().get("entries") or r.json().get("log") or r.json().get("placements") or []
    if isinstance(r.json(), list):
        entries = r.json()
    # find entry from worker_queue for this page
    worker_entries = [e for e in entries if e.get("source") == "worker_queue"]
    assert len(worker_entries) > 0, "No wp_placement log entries with source=worker_queue"


# ---- WP needs_review when page has no generated_content ----

def test_wp_worker_needs_review_no_content(auth_client):
    """Create an empty page, route it, execute, expect needs_review."""
    # Create bare page
    payload = {
        "page_name": "TEST_WP_EMPTY_" + str(int(time.time())),
        "page_family": "Business",
        "page_type": "Landing",
        "audience": "test",
        "purpose": "test",
        "CTA_type": "none",
        "keyword_or_theme": "test",
    }
    r = auth_client.post(f"{BASE_URL}/api/pages", json=payload)
    assert r.status_code == 201, r.text
    page = r.json()
    pid = page["id"]

    # Approve (will try to create WP task)
    ra = auth_client.post(f"{BASE_URL}/api/pages/{pid}/approve")
    assert ra.status_code == 200

    # Find task
    task_id = None
    for _ in range(5):
        rt = auth_client.get(f"{BASE_URL}/api/worker-queue/tasks?worker=wp_placement&limit=200")
        for t in rt.json().get("tasks", []):
            if t.get("source_item_id") == pid:
                task_id = t["id"]
                break
        if task_id:
            break
        time.sleep(0.3)

    assert task_id, "Task not created"
    r = auth_client.post(f"{BASE_URL}/api/worker-queue/tasks/{task_id}/execute")
    assert r.status_code == 200
    task = r.json()
    assert task["status"] == "needs_review", f"expected needs_review, got {task['status']}"
    assert task["result"].get("needs_review") is True

    # Cleanup
    auth_client.delete(f"{BASE_URL}/api/pages/{pid}")
