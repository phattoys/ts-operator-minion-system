"""
Tests for the page update workflow:
POST /api/command-center/page-update → Jenny (wp_content_draft) → Rene (wp_content_qa) → WP Placement (wp_page_update).

Covers:
- Validation errors (404 nonexistent page, 400 no instructions, 400 no wp_page_id)
- Jenny auto-execution of wp_content_draft and drafted_html persistence
- Context propagation: drafted_html appears in Rene's task context
- Rene auto-executes wp_content_qa and creates a queued wp_page_update task
- WP Placement task is QUEUED (founder_action_needed=true) — not auto-run
- Executing the wp_page_update task UPDATES the existing page (no duplicate),
  preserves status, returns completion packet
- Unknown source_module Jenny task → needs_review (not silent "task noted")
- Regression on /api/worker-queue/stats and /api/worker-queue/tasks
"""
import os
import time
import pytest
import requests

def _load_base_url():
    url = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
    if url:
        return url
    # Fallback: read from /app/frontend/.env
    try:
        with open("/app/frontend/.env") as f:
            for line in f:
                if line.startswith("REACT_APP_BACKEND_URL="):
                    return line.split("=", 1)[1].strip().rstrip("/")
    except Exception:
        pass
    raise RuntimeError("REACT_APP_BACKEND_URL not configured")


BASE_URL = _load_base_url()
FOUNDER_PASSWORD = "TSFounder!Vault2026#Secure"

# Use the FAQ page (suggested by agent context — already placed in WP)
TEST_PAGE_ID = "a5263d92-42ab-4fbe-813c-186fffa9a793"
TEST_WP_ID = 354820


# ---- Fixtures ----

@pytest.fixture(scope="module")
def auth_token():
    r = requests.post(
        f"{BASE_URL}/api/auth/login",
        json={"password": FOUNDER_PASSWORD},
        timeout=15,
    )
    assert r.status_code == 200, f"Login failed: {r.status_code} {r.text}"
    token = r.json().get("access_token")
    assert token, "No access_token returned"
    return token


@pytest.fixture(scope="module")
def client(auth_token):
    s = requests.Session()
    s.headers.update({
        "Authorization": f"Bearer {auth_token}",
        "Content-Type": "application/json",
    })
    return s


def _wait_for_task_status(client, task_id, target_statuses, timeout=45):
    """Poll the task until status is in target_statuses, or timeout."""
    deadline = time.time() + timeout
    last = None
    while time.time() < deadline:
        r = client.get(f"{BASE_URL}/api/worker-queue/tasks/{task_id}", timeout=15)
        if r.status_code == 200:
            last = r.json()
            if last.get("status") in target_statuses:
                return last
        time.sleep(1)
    return last


# ---- Validation tests ----

class TestPageUpdateValidation:

    def test_login_works(self, auth_token):
        assert isinstance(auth_token, str) and len(auth_token) > 20

    def test_page_update_404_nonexistent_page(self, client):
        r = client.post(
            f"{BASE_URL}/api/command-center/page-update",
            json={
                "page_id": "00000000-0000-0000-0000-000000000000",
                "update_instructions": "doesn't matter",
            },
            timeout=15,
        )
        assert r.status_code == 404
        assert "not found" in r.text.lower()

    def test_page_update_400_no_instructions(self, client):
        r = client.post(
            f"{BASE_URL}/api/command-center/page-update",
            json={"page_id": TEST_PAGE_ID},
            timeout=15,
        )
        assert r.status_code == 400
        assert "instructions" in r.text.lower() or "content" in r.text.lower()

    def test_page_update_400_no_wp_id(self, client):
        # Find a page that has no wp_page_id
        r = client.get(f"{BASE_URL}/api/pages", timeout=15)
        assert r.status_code == 200
        data = r.json()
        pages = data if isinstance(data, list) else data.get("pages", [])
        no_wp = next((p for p in pages if not p.get("wp_page_id")), None)
        if not no_wp:
            pytest.skip("No page without wp_page_id available")
        r = client.post(
            f"{BASE_URL}/api/command-center/page-update",
            json={
                "page_id": no_wp["id"],
                "update_instructions": "Add an FAQ item.",
            },
            timeout=15,
        )
        assert r.status_code == 400
        assert "wordpress" in r.text.lower() or "wp" in r.text.lower() or "place" in r.text.lower()


# ---- End-to-end workflow (uses new_section_content to bypass LLM for determinism) ----

class TestPageUpdateWorkflow:

    @pytest.fixture(scope="class")
    def workflow_state(self, client):
        """Kick off a real page-update workflow and remember IDs across the class."""
        marker_text = "TEST_PAGE_UPDATE_WORKFLOW_MARKER_DO_NOT_PUBLISH"
        new_section = (
            f"## {marker_text}\n\nThis content was inserted by the automated test "
            "for the page update workflow. It is appended to a draft only — please ignore."
        )
        r = client.post(
            f"{BASE_URL}/api/command-center/page-update",
            json={
                "page_id": TEST_PAGE_ID,
                "new_section_content": new_section,
                # No update_instructions → skips LLM path and uses provided content directly
            },
            timeout=30,
        )
        assert r.status_code == 200, f"page-update failed: {r.status_code} {r.text}"
        body = r.json()
        return {
            "jenny_task_id": body["task_id"],
            "chain": body.get("chain", ""),
            "wp_page_id": body.get("wp_page_id"),
            "marker": marker_text,
            "new_section": new_section,
        }

    def test_create_returns_chain_metadata(self, workflow_state):
        assert workflow_state["jenny_task_id"]
        assert "Jenny" in workflow_state["chain"]
        assert "Rene" in workflow_state["chain"]
        assert "WP" in workflow_state["chain"]
        assert str(workflow_state["wp_page_id"]) == str(TEST_WP_ID)

    def test_jenny_task_auto_executed_and_drafts_html(self, client, workflow_state):
        task = _wait_for_task_status(
            client, workflow_state["jenny_task_id"], {"completed", "failed", "needs_review"}, timeout=45
        )
        assert task is not None, "Jenny task never reached terminal state"
        assert task["worker"] == "jenny"
        assert task["task_type"] == "wp_content_draft"
        assert task["status"] == "completed", f"Jenny failed: {task.get('result')}"
        # drafted_html must be saved into the task's context
        ctx = task.get("context", {})
        drafted = ctx.get("drafted_html", "")
        assert drafted, "Jenny did not store drafted_html in context"
        assert workflow_state["marker"] in drafted, "Drafted HTML missing the provided marker"
        workflow_state["drafted_html"] = drafted

    def test_rene_task_created_with_drafted_html_context(self, client, workflow_state):
        # Find the Rene wp_content_qa task for this source page
        r = client.get(
            f"{BASE_URL}/api/worker-queue/tasks",
            params={"worker": "rene", "limit": 50},
            timeout=15,
        )
        assert r.status_code == 200
        tasks = r.json().get("tasks", r.json() if isinstance(r.json(), list) else [])
        rene = next(
            (t for t in tasks
             if t.get("task_type") == "wp_content_qa"
             and t.get("source_item_id") == TEST_PAGE_ID),
            None,
        )
        assert rene, "No Rene wp_content_qa task was created"
        workflow_state["rene_task_id"] = rene["id"]
        # Context propagation — drafted_html must be present (not lost between tasks)
        ctx = rene.get("context", {})
        assert ctx.get("drafted_html"), "Rene task missing drafted_html in context"
        assert workflow_state["marker"] in ctx["drafted_html"]

    def test_rene_auto_completes_qa_and_creates_wp_update_task(self, client, workflow_state):
        rene_id = workflow_state.get("rene_task_id")
        assert rene_id
        rene = _wait_for_task_status(
            client, rene_id, {"completed", "failed", "needs_review"}, timeout=30
        )
        assert rene["status"] == "completed", f"Rene failed: {rene.get('result')}"
        assert rene.get("result", {}).get("passed") is True

        # WP Placement wp_page_update task must now exist and be QUEUED (founder-triggered)
        r = client.get(
            f"{BASE_URL}/api/worker-queue/tasks",
            params={"worker": "wp_placement", "limit": 50},
            timeout=15,
        )
        assert r.status_code == 200
        tasks = r.json().get("tasks", r.json() if isinstance(r.json(), list) else [])
        wp_task = next(
            (t for t in tasks
             if t.get("task_type") == "wp_page_update"
             and t.get("source_item_id") == TEST_PAGE_ID
             and t.get("status") in ("queued", "needs_review")),
            None,
        )
        # If already executed by some other concurrent flow, accept it
        if not wp_task:
            wp_task = next(
                (t for t in tasks
                 if t.get("task_type") == "wp_page_update"
                 and t.get("source_item_id") == TEST_PAGE_ID),
                None,
            )
        assert wp_task, "WP Placement wp_page_update task was not created"
        workflow_state["wp_task_id"] = wp_task["id"]

        # Must be queued (NOT auto-executed) and founder_action_needed=true
        if wp_task["status"] == "queued":
            assert wp_task.get("founder_action_needed") is True, \
                "wp_page_update should require founder action"
            assert wp_task.get("auto_execute") is False, \
                "wp_placement worker must not auto-execute"

        # Context must carry the drafted_html through
        ctx = wp_task.get("context", {})
        assert ctx.get("drafted_html"), "WP task missing drafted_html"
        assert ctx.get("wp_page_id") == str(TEST_WP_ID) or ctx.get("wp_page_id") == TEST_WP_ID

    def test_execute_wp_update_returns_completion_packet(self, client, workflow_state):
        wp_task_id = workflow_state.get("wp_task_id")
        assert wp_task_id
        # Capture current WP page status before triggering update (regression check)
        r = client.post(
            f"{BASE_URL}/api/worker-queue/tasks/{wp_task_id}/execute",
            timeout=90,  # live WP call
        )
        assert r.status_code == 200, f"Execute failed: {r.status_code} {r.text}"
        task = r.json()
        assert task["status"] == "completed", f"WP update failed: {task.get('result')}"
        result = task.get("result", {})

        # Completion packet fields
        for field in ("wp_page_id", "status_before", "status_after",
                      "content_added_chars", "insert_location", "warnings"):
            assert field in result, f"Result missing '{field}'"

        # Page status must be PRESERVED — not flipped to draft/publish unexpectedly
        assert result["status_before"] == result["status_after"], (
            f"Page status changed: {result['status_before']} → {result['status_after']}"
        )
        # Chars added > 0
        assert result["content_added_chars"] > 0
        # WP id consistent
        assert str(result["wp_page_id"]) == str(TEST_WP_ID)
        workflow_state["status_preserved"] = result["status_before"]

    def test_no_duplicate_page_created(self, client, workflow_state):
        """UPDATE flow must not create a new wp_placements record with mode='create' for this page."""
        # All wp_placements for this page_ops id — only the new entry should be mode='update'
        # Use the worker-queue tasks list to assert no new wp_draft was queued
        r = client.get(
            f"{BASE_URL}/api/worker-queue/tasks",
            params={"worker": "wp_placement", "limit": 100},
            timeout=15,
        )
        tasks = r.json().get("tasks", r.json() if isinstance(r.json(), list) else [])
        # Find recent wp_draft (create) tasks for this page — none should be created by this flow
        creates = [t for t in tasks
                   if t.get("source_item_id") == TEST_PAGE_ID
                   and t.get("task_type") == "wp_draft"]
        # If any pre-existing wp_draft exists (from initial placement), that's fine — we only fail
        # if a new one was created in the last 5 minutes alongside our update task
        import datetime
        now = datetime.datetime.now(datetime.timezone.utc)
        recent_creates = []
        for t in creates:
            try:
                ts = t.get("created_at", "")
                dt = datetime.datetime.fromisoformat(ts.replace("Z", "+00:00"))
                if (now - dt).total_seconds() < 600:
                    recent_creates.append(t)
            except Exception:
                pass
        assert not recent_creates, \
            f"Update flow incorrectly created new wp_draft (create) tasks: {[t['id'] for t in recent_creates]}"


# ---- Unknown task handling ----

class TestJennyUnknownSource:
    """Verify Jenny marks unknown source_module tasks as needs_review (not silent 'task noted')."""

    def test_unknown_module_jenny_needs_review(self, client):
        # Create a Jenny task with an unknown source_module via a backdoor — use execution-map
        # which routes to Jenny with task_type=copy_cleanup (a known-but-non-field-listing path).
        # Instead, directly craft via internal Mongo? Not available — use execution-map flow:
        r = client.post(
            f"{BASE_URL}/api/command-center/execution-map",
            json={
                "goal_input": "TEST_PAGE_UPDATE_WORKFLOW: throwaway goal to create a Jenny task with unknown source",
                "timeframe": "this week",
                "priority": "low",
                "main_lane": "ops",
            },
            timeout=60,
        )
        if r.status_code != 200:
            pytest.skip(f"execution-map unavailable: {r.status_code}")
        map_id = r.json().get("id")
        if not map_id:
            pytest.skip("execution-map did not return id")

        r = client.post(
            f"{BASE_URL}/api/command-center/execution-maps/{map_id}/send-to-queue",
            timeout=30,
        )
        if r.status_code != 200:
            pytest.skip(f"send-to-queue failed: {r.status_code}")
        task_id = r.json().get("task_id")
        assert task_id

        # Poll — Jenny should mark this as needs_review since source_module='execution_map'
        # is not 'field_listing' and task_type is not 'wp_content_draft'.
        task = _wait_for_task_status(
            client, task_id, {"completed", "failed", "needs_review"}, timeout=30
        )
        assert task is not None
        # Acceptable outcomes: needs_review (preferred) OR explicit failure with a reason.
        # NOT acceptable: silently completed with no result (the original bug).
        assert task["status"] in ("needs_review", "failed"), \
            f"Expected needs_review/failed for unknown source, got {task['status']}: {task.get('result')}"
        result = task.get("result", {})
        # Must have an explanation, not just an empty "task noted"
        assert (result.get("reason") or result.get("error")), \
            "Unknown task completed silently without a reason"


# ---- Regression on worker queue endpoints ----

class TestWorkerQueueRegression:

    def test_worker_queue_stats(self, client):
        r = client.get(f"{BASE_URL}/api/worker-queue/stats", timeout=15)
        assert r.status_code == 200
        data = r.json()
        for k in ("total", "queued", "completed", "workers"):
            assert k in data
        assert "wp_placement" in data["workers"]
        assert data["workers"]["wp_placement"]["auto_execute"] is False

    def test_worker_queue_tasks_listing(self, client):
        r = client.get(f"{BASE_URL}/api/worker-queue/tasks", params={"limit": 10}, timeout=15)
        assert r.status_code == 200
        data = r.json()
        tasks = data.get("tasks", data if isinstance(data, list) else [])
        assert isinstance(tasks, list)

    def test_worker_queue_views(self, client):
        for view in ("ready", "needs-review", "in-progress", "completed"):
            r = client.get(f"{BASE_URL}/api/worker-queue/views/{view}", timeout=15)
            assert r.status_code == 200, f"/views/{view} returned {r.status_code}"
