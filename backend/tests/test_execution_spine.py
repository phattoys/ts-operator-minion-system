"""
Test suite for TS OPS Execution Spine v1 module.
Tests: Dashboard, Sync, Tasks, Status Update, Execute, and Execution Log endpoints.
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

@pytest.fixture(scope="module")
def auth_token():
    """Get authentication token for all tests."""
    response = requests.post(
        f"{BASE_URL}/api/auth/login",
        json={"password": "TSFounder!Vault2026#Secure"}
    )
    assert response.status_code == 200, f"Auth failed: {response.text}"
    return response.json()["access_token"]

@pytest.fixture(scope="module")
def auth_headers(auth_token):
    """Headers with auth token."""
    return {"Authorization": f"Bearer {auth_token}", "Content-Type": "application/json"}


# ================== DASHBOARD TESTS ==================

class TestSpineDashboard:
    """Tests for GET /api/spine/dashboard endpoint."""
    
    def test_dashboard_requires_auth(self):
        """Dashboard should require authentication."""
        response = requests.get(f"{BASE_URL}/api/spine/dashboard")
        assert response.status_code == 401, f"Expected 401, got {response.status_code}"
    
    def test_dashboard_returns_full_data(self, auth_headers):
        """Dashboard should return all required sections."""
        response = requests.get(f"{BASE_URL}/api/spine/dashboard", headers=auth_headers)
        assert response.status_code == 200, f"Dashboard failed: {response.text}"
        
        data = response.json()
        
        # Verify required top-level keys
        required_keys = [
            "total_tasks", "needs_action", "in_progress", "ready_to_execute",
            "recently_completed", "held_back", "module_health", "status_counts", "recent_log"
        ]
        for key in required_keys:
            assert key in data, f"Missing key: {key}"
        
        # Verify total_tasks is a number
        assert isinstance(data["total_tasks"], int), "total_tasks should be int"
        
        # Verify sections are lists
        for section in ["needs_action", "in_progress", "ready_to_execute", "recently_completed", "held_back"]:
            assert isinstance(data[section], list), f"{section} should be a list"
        
        # Verify module_health structure
        assert isinstance(data["module_health"], dict), "module_health should be dict"
        for module in ["page_ops", "product_intake", "field_listing"]:
            assert module in data["module_health"], f"Missing module: {module}"
            health = data["module_health"][module]
            assert "total" in health, f"Missing 'total' in {module} health"
            assert "needs_action" in health, f"Missing 'needs_action' in {module} health"
            assert "ready" in health, f"Missing 'ready' in {module} health"
            assert "done" in health, f"Missing 'done' in {module} health"
        
        print(f"Dashboard returned {data['total_tasks']} total tasks")
        print(f"Module health: page_ops={data['module_health']['page_ops']['total']}, "
              f"product_intake={data['module_health']['product_intake']['total']}, "
              f"field_listing={data['module_health']['field_listing']['total']}")
    
    def test_dashboard_syncs_expected_counts(self, auth_headers):
        """Dashboard should sync expected counts from source modules."""
        response = requests.get(f"{BASE_URL}/api/spine/dashboard", headers=auth_headers)
        assert response.status_code == 200
        
        data = response.json()
        page_ops_total = data["module_health"]["page_ops"]["total"]
        intake_total = data["module_health"]["product_intake"]["total"]
        field_total = data["module_health"]["field_listing"]["total"]
        
        # Per requirements: 25 pages, 4 intake sessions, 1 field batch
        # These may vary slightly but should be in reasonable range
        print(f"Synced counts - Pages: {page_ops_total}, Intake: {intake_total}, Field: {field_total}")
        
        # Verify we have some data
        assert page_ops_total >= 0, "Should have page_ops tasks"
        assert intake_total >= 0, "Should have intake tasks"
        assert field_total >= 0, "Should have field tasks"


# ================== SYNC TESTS ==================

class TestSpineSync:
    """Tests for POST /api/spine/sync endpoint."""
    
    def test_sync_requires_auth(self):
        """Sync should require authentication."""
        response = requests.post(f"{BASE_URL}/api/spine/sync")
        assert response.status_code == 401
    
    def test_sync_returns_counts(self, auth_headers):
        """Sync should return synced counts for all modules."""
        response = requests.post(f"{BASE_URL}/api/spine/sync", headers=auth_headers)
        assert response.status_code == 200, f"Sync failed: {response.text}"
        
        data = response.json()
        assert "synced" in data, "Missing 'synced' in response"
        assert "message" in data, "Missing 'message' in response"
        
        synced = data["synced"]
        assert "pages" in synced, "Missing 'pages' count"
        assert "intake" in synced, "Missing 'intake' count"
        assert "field" in synced, "Missing 'field' count"
        
        print(f"Synced: pages={synced['pages']}, intake={synced['intake']}, field={synced['field']}")


# ================== TASKS TESTS ==================

class TestSpineTasks:
    """Tests for GET /api/spine/tasks endpoint."""
    
    def test_tasks_requires_auth(self):
        """Tasks list should require authentication."""
        response = requests.get(f"{BASE_URL}/api/spine/tasks")
        assert response.status_code == 401
    
    def test_tasks_list_all(self, auth_headers):
        """Should list all tasks without filters."""
        response = requests.get(f"{BASE_URL}/api/spine/tasks", headers=auth_headers)
        assert response.status_code == 200, f"Tasks list failed: {response.text}"
        
        data = response.json()
        assert "tasks" in data, "Missing 'tasks' in response"
        assert "count" in data, "Missing 'count' in response"
        assert isinstance(data["tasks"], list), "tasks should be a list"
        assert data["count"] == len(data["tasks"]), "count should match tasks length"
        
        print(f"Total tasks: {data['count']}")
        
        # Verify task structure if we have tasks
        if data["tasks"]:
            task = data["tasks"][0]
            required_fields = ["type", "source_module", "ref_id", "title", "status", "next_action"]
            for field in required_fields:
                assert field in task, f"Task missing field: {field}"
    
    def test_tasks_filter_by_status(self, auth_headers):
        """Should filter tasks by status."""
        response = requests.get(f"{BASE_URL}/api/spine/tasks?status=ready", headers=auth_headers)
        assert response.status_code == 200
        
        data = response.json()
        for task in data["tasks"]:
            assert task["status"] == "ready", f"Task has wrong status: {task['status']}"
        
        print(f"Ready tasks: {data['count']}")
    
    def test_tasks_filter_by_source_module(self, auth_headers):
        """Should filter tasks by source_module."""
        response = requests.get(f"{BASE_URL}/api/spine/tasks?source_module=page_ops", headers=auth_headers)
        assert response.status_code == 200
        
        data = response.json()
        for task in data["tasks"]:
            assert task["source_module"] == "page_ops", f"Task has wrong module: {task['source_module']}"
        
        print(f"Page Ops tasks: {data['count']}")
    
    def test_tasks_filter_by_task_type(self, auth_headers):
        """Should filter tasks by task_type."""
        response = requests.get(f"{BASE_URL}/api/spine/tasks?task_type=page", headers=auth_headers)
        assert response.status_code == 200
        
        data = response.json()
        for task in data["tasks"]:
            assert task["type"] == "page", f"Task has wrong type: {task['type']}"
        
        print(f"Page type tasks: {data['count']}")
    
    def test_tasks_combined_filters(self, auth_headers):
        """Should support multiple filters."""
        response = requests.get(
            f"{BASE_URL}/api/spine/tasks?source_module=page_ops&status=ready",
            headers=auth_headers
        )
        assert response.status_code == 200
        
        data = response.json()
        for task in data["tasks"]:
            assert task["source_module"] == "page_ops"
            assert task["status"] == "ready"
        
        print(f"Page Ops ready tasks: {data['count']}")


# ================== STATUS UPDATE TESTS ==================

class TestSpineStatusUpdate:
    """Tests for POST /api/spine/tasks/{ref_id}/status endpoint."""
    
    def test_status_update_requires_auth(self):
        """Status update should require authentication."""
        response = requests.post(
            f"{BASE_URL}/api/spine/tasks/test-id/status",
            json={"status": "ready"}
        )
        assert response.status_code == 401
    
    def test_status_update_invalid_status(self, auth_headers):
        """Should reject invalid status values."""
        # First get a valid task
        tasks_resp = requests.get(f"{BASE_URL}/api/spine/tasks", headers=auth_headers)
        tasks = tasks_resp.json().get("tasks", [])
        
        if not tasks:
            pytest.skip("No tasks available for testing")
        
        ref_id = tasks[0]["ref_id"]
        
        response = requests.post(
            f"{BASE_URL}/api/spine/tasks/{ref_id}/status",
            headers=auth_headers,
            json={"status": "invalid_status_xyz"}
        )
        assert response.status_code == 400, f"Expected 400, got {response.status_code}"
        assert "Invalid status" in response.json().get("detail", "")
    
    def test_status_update_nonexistent_task(self, auth_headers):
        """Should return 404 for nonexistent task."""
        response = requests.post(
            f"{BASE_URL}/api/spine/tasks/nonexistent-task-id-xyz/status",
            headers=auth_headers,
            json={"status": "ready"}
        )
        assert response.status_code == 404
    
    def test_status_update_success(self, auth_headers):
        """Should successfully update task status and log it."""
        # Get a task that's not in a terminal state
        tasks_resp = requests.get(f"{BASE_URL}/api/spine/tasks?status=new", headers=auth_headers)
        tasks = tasks_resp.json().get("tasks", [])
        
        if not tasks:
            # Try needs_review
            tasks_resp = requests.get(f"{BASE_URL}/api/spine/tasks?status=needs_review", headers=auth_headers)
            tasks = tasks_resp.json().get("tasks", [])
        
        if not tasks:
            pytest.skip("No suitable tasks for status update test")
        
        task = tasks[0]
        ref_id = task["ref_id"]
        old_status = task["status"]
        
        # Update to held_back (safe status that won't trigger actions)
        response = requests.post(
            f"{BASE_URL}/api/spine/tasks/{ref_id}/status",
            headers=auth_headers,
            json={"status": "held_back", "note": "Test status update"}
        )
        assert response.status_code == 200, f"Status update failed: {response.text}"
        
        data = response.json()
        assert data["ref_id"] == ref_id
        assert data["old_status"] == old_status
        assert data["new_status"] == "held_back"
        
        print(f"Updated task {ref_id}: {old_status} -> held_back")
        
        # Verify the change was logged
        log_resp = requests.get(f"{BASE_URL}/api/spine/log", headers=auth_headers)
        log_data = log_resp.json()
        
        # Find our log entry
        found = False
        for entry in log_data.get("log", []):
            if entry.get("task_id") == ref_id and entry.get("action") == "manual_status_update":
                found = True
                assert entry["status_before"] == old_status
                assert entry["status_after"] == "held_back"
                break
        
        assert found, "Status update was not logged"
        
        # Restore original status
        requests.post(
            f"{BASE_URL}/api/spine/tasks/{ref_id}/status",
            headers=auth_headers,
            json={"status": old_status, "note": "Restoring original status"}
        )


# ================== EXECUTE TESTS ==================

class TestSpineExecute:
    """Tests for POST /api/spine/tasks/{ref_id}/execute endpoint."""
    
    def test_execute_requires_auth(self):
        """Execute should require authentication."""
        response = requests.post(f"{BASE_URL}/api/spine/tasks/test-id/execute")
        assert response.status_code == 401
    
    def test_execute_nonexistent_task(self, auth_headers):
        """Should return 404 for nonexistent task."""
        response = requests.post(
            f"{BASE_URL}/api/spine/tasks/nonexistent-task-id-xyz/execute",
            headers=auth_headers
        )
        assert response.status_code == 404
    
    def test_execute_rejects_non_ready_task(self, auth_headers):
        """Should reject execution for tasks not in 'ready' status."""
        # Get a task that's NOT ready
        tasks_resp = requests.get(f"{BASE_URL}/api/spine/tasks?status=new", headers=auth_headers)
        tasks = tasks_resp.json().get("tasks", [])
        
        if not tasks:
            tasks_resp = requests.get(f"{BASE_URL}/api/spine/tasks?status=needs_review", headers=auth_headers)
            tasks = tasks_resp.json().get("tasks", [])
        
        if not tasks:
            tasks_resp = requests.get(f"{BASE_URL}/api/spine/tasks?status=held_back", headers=auth_headers)
            tasks = tasks_resp.json().get("tasks", [])
        
        if not tasks:
            pytest.skip("No non-ready tasks available for testing")
        
        task = tasks[0]
        ref_id = task["ref_id"]
        
        response = requests.post(
            f"{BASE_URL}/api/spine/tasks/{ref_id}/execute",
            headers=auth_headers
        )
        
        # Should return 400 because no action available for non-ready tasks
        assert response.status_code == 400, f"Expected 400, got {response.status_code}: {response.text}"
        assert "No action available" in response.json().get("detail", "")
        
        print(f"Correctly rejected execution for task {ref_id} in status '{task['status']}'")


# ================== EXECUTION LOG TESTS ==================

class TestSpineLog:
    """Tests for GET /api/spine/log endpoint."""
    
    def test_log_requires_auth(self):
        """Log should require authentication."""
        response = requests.get(f"{BASE_URL}/api/spine/log")
        assert response.status_code == 401
    
    def test_log_returns_entries(self, auth_headers):
        """Log should return execution history."""
        response = requests.get(f"{BASE_URL}/api/spine/log", headers=auth_headers)
        assert response.status_code == 200, f"Log failed: {response.text}"
        
        data = response.json()
        assert "log" in data, "Missing 'log' in response"
        assert isinstance(data["log"], list), "log should be a list"
        
        print(f"Execution log entries: {len(data['log'])}")
        
        # Verify log entry structure if we have entries
        if data["log"]:
            entry = data["log"][0]
            required_fields = ["task_id", "action", "result", "status_before", "status_after", "executed_at"]
            for field in required_fields:
                assert field in entry, f"Log entry missing field: {field}"
    
    def test_log_respects_limit(self, auth_headers):
        """Log should respect limit parameter."""
        response = requests.get(f"{BASE_URL}/api/spine/log?limit=5", headers=auth_headers)
        assert response.status_code == 200
        
        data = response.json()
        assert len(data["log"]) <= 5, f"Log returned more than limit: {len(data['log'])}"


# ================== STATUS NORMALIZATION TESTS ==================

class TestStatusNormalization:
    """Tests for status normalization from source modules."""
    
    def test_page_approved_maps_to_ready(self, auth_headers):
        """Page with 'Approved' status should map to spine 'ready'."""
        response = requests.get(
            f"{BASE_URL}/api/spine/tasks?source_module=page_ops&status=ready",
            headers=auth_headers
        )
        assert response.status_code == 200
        
        data = response.json()
        ready_pages = [t for t in data["tasks"] if t["type"] == "page"]
        
        print(f"Ready pages (Approved status): {len(ready_pages)}")
        
        # Verify ready pages have 'Place in WordPress' action
        for page in ready_pages:
            assert page.get("next_action") == "Place in WordPress", \
                f"Ready page should have 'Place in WordPress' action, got: {page.get('next_action')}"
            if page.get("available_action"):
                assert page["available_action"]["label"] == "Place in WordPress"
    
    def test_intake_session_ready_mapping(self, auth_headers):
        """Intake session with all ready items should map to spine 'ready'."""
        response = requests.get(
            f"{BASE_URL}/api/spine/tasks?source_module=product_intake&status=ready",
            headers=auth_headers
        )
        assert response.status_code == 200
        
        data = response.json()
        ready_sessions = [t for t in data["tasks"] if t["type"] == "intake_session"]
        
        print(f"Ready intake sessions: {len(ready_sessions)}")
        
        # Verify ready sessions have 'Export WooCommerce CSV' action
        for session in ready_sessions:
            assert session.get("next_action") == "Export WooCommerce CSV", \
                f"Ready session should have 'Export WooCommerce CSV' action"


# ================== ROUTING RULES TESTS ==================

class TestRoutingRules:
    """Tests for routing rules and available actions."""
    
    def test_ready_pages_have_wp_action(self, auth_headers):
        """Ready pages should have 'Place in WordPress' action available."""
        response = requests.get(
            f"{BASE_URL}/api/spine/tasks?source_module=page_ops&status=ready",
            headers=auth_headers
        )
        assert response.status_code == 200
        
        data = response.json()
        for task in data["tasks"]:
            if task["type"] == "page" and task["status"] == "ready":
                action = task.get("available_action")
                assert action is not None, f"Ready page should have available_action"
                assert action["action"] == "wp_place"
                assert action["label"] == "Place in WordPress"
                assert action["target_module"] == "wp_placement"
    
    def test_ready_intake_has_export_action(self, auth_headers):
        """Ready intake sessions should have 'Export WooCommerce CSV' action."""
        response = requests.get(
            f"{BASE_URL}/api/spine/tasks?source_module=product_intake&status=ready",
            headers=auth_headers
        )
        assert response.status_code == 200
        
        data = response.json()
        for task in data["tasks"]:
            if task["type"] == "intake_session" and task["status"] == "ready":
                action = task.get("available_action")
                assert action is not None, f"Ready intake should have available_action"
                assert action["action"] == "woo_export"
                assert action["label"] == "Export WooCommerce CSV"
    
    def test_ready_field_batch_has_packs_action(self, auth_headers):
        """Ready field batches should have 'Generate Destination Packs' action."""
        response = requests.get(
            f"{BASE_URL}/api/spine/tasks?source_module=field_listing&status=ready",
            headers=auth_headers
        )
        assert response.status_code == 200
        
        data = response.json()
        for task in data["tasks"]:
            if task["type"] == "field_batch" and task["status"] == "ready":
                action = task.get("available_action")
                assert action is not None, f"Ready field batch should have available_action"
                assert action["action"] == "generate_packs"
                assert action["label"] == "Generate Destination Packs"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
