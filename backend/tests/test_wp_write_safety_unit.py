"""
Unit-level tests for the unified WordPress write-safety gate
(safety/unified-wp-write-gate-20260714).

These exercise services/wp_write_safety.py, services/wp_client.py, and
services/worker_queue.py directly against an in-memory Mongo double
(mongomock-motor), so they can run without a live server, real MongoDB, or
real WordPress credentials -- see tests/conftest.py for why, and what is
stubbed to make that possible.

This is a supplement to, not a replacement for, HTTP-level tests
(test_wp_write_safety.py) that must ultimately run against the deployed
system with a real MongoDB and real `emergentintegrations` dependency,
consistent with this project's existing "known unproven until run in the
real environment" posture (see PRESERVATION_MANIFEST.md).
"""
import pytest
from datetime import datetime, timedelta, timezone

import services.wp_write_safety as wws
import services.wp_client as wpc
import services.worker_queue as wq


FAKE_USER = {"sub": "founder", "role": "admin"}


# ================== TOKEN LIFECYCLE ==================

class TestApprovalTokenLifecycle:

    async def test_issue_and_consume_happy_path(self, mock_db):
        payload = {"title": "T", "slug": "t", "content": "<p>hi</p>", "meta": {}}
        issued = await wws.issue_approval_token("single", ["page-1"], payload, publication_mode="draft")
        assert issued["token"]
        assert issued["consumed"] is False

        consumed = await wws.consume_approval_token(
            token=issued["token"],
            scope_ids=["page-1"],
            payload=payload,
            approved_by="founder",
            approval_role="admin",
            approval_source="manual_confirmation",
        )
        assert consumed["consumed"] is True
        assert consumed["approved_by"] == "founder"

    async def test_consumed_token_fails_on_reuse(self, mock_db):
        payload = {"title": "T", "slug": "t", "content": "x", "meta": {}}
        issued = await wws.issue_approval_token("single", ["page-1"], payload)
        await wws.consume_approval_token(issued["token"], ["page-1"], payload, "founder", "admin", "manual_confirmation")

        with pytest.raises(wws.WpWriteSafetyError, match="already been used"):
            await wws.consume_approval_token(issued["token"], ["page-1"], payload, "founder", "admin", "manual_confirmation")

    async def test_expired_token_fails(self, mock_db):
        payload = {"title": "T", "slug": "t", "content": "x", "meta": {}}
        issued = await wws.issue_approval_token("single", ["page-1"], payload)
        # Force it into the past
        await mock_db.wp_write_approvals.update_one(
            {"token": issued["token"]},
            {"$set": {"expires_at": (datetime.now(timezone.utc) - timedelta(minutes=1)).isoformat()}},
        )
        with pytest.raises(wws.WpWriteSafetyError, match="expired"):
            await wws.consume_approval_token(issued["token"], ["page-1"], payload, "founder", "admin", "manual_confirmation")

    async def test_altered_payload_fails(self, mock_db):
        payload = {"title": "T", "slug": "t", "content": "original", "meta": {}}
        issued = await wws.issue_approval_token("single", ["page-1"], payload)
        altered = {**payload, "content": "changed after approval"}
        with pytest.raises(wws.WpWriteSafetyError, match="content has changed"):
            await wws.consume_approval_token(issued["token"], ["page-1"], altered, "founder", "admin", "manual_confirmation")

    async def test_wrong_scope_fails(self, mock_db):
        payload = {"title": "T", "slug": "t", "content": "x", "meta": {}}
        issued = await wws.issue_approval_token("single", ["page-1"], payload)
        with pytest.raises(wws.WpWriteSafetyError, match="scope does not match"):
            await wws.consume_approval_token(issued["token"], ["page-2"], payload, "founder", "admin", "manual_confirmation")

    async def test_missing_token_fails(self, mock_db):
        payload = {"title": "T", "slug": "t", "content": "x", "meta": {}}
        with pytest.raises(wws.WpWriteSafetyError, match="no approval_token supplied"):
            await wws.consume_approval_token(None, ["page-1"], payload, "founder", "admin", "manual_confirmation")

    async def test_unknown_token_fails(self, mock_db):
        payload = {"title": "T", "slug": "t", "content": "x", "meta": {}}
        with pytest.raises(wws.WpWriteSafetyError, match="not found"):
            await wws.consume_approval_token("not-a-real-token", ["page-1"], payload, "founder", "admin", "manual_confirmation")


# ================== WP CLIENT GATE ==================

class TestWpClientGate:

    async def test_mock_never_reaches_live_even_with_credentials_present(self, mock_db, monkeypatch):
        monkeypatch.setattr(wpc, "IS_LIVE", True)
        called = {"live": False}

        async def fake_live_create(*a, **kw):
            called["live"] = True
            return {"id": "should-not-happen"}

        monkeypatch.setattr(wpc, "_live_create_page", fake_live_create)

        result = await wpc.create_page(
            "Title", "slug", "<p>x</p>", status="draft", meta={},
            execution_mode="mock",
        )
        assert called["live"] is False
        assert result["mock"] is True

    async def test_dry_run_mode_refused_by_wp_client(self, mock_db):
        # Dry runs must never reach wp_client at all -- calling it with
        # execution_mode="dry_run" is a programming error, not a valid path.
        with pytest.raises(wpc.WpWriteSafetyError, match="Dry runs must not call"):
            await wpc.create_page("Title", "slug", "<p>x</p>", execution_mode="dry_run")

    async def test_live_without_token_fails(self, mock_db, monkeypatch):
        monkeypatch.setattr(wpc, "IS_LIVE", True)
        with pytest.raises(wpc.WpWriteSafetyError, match="no approval_token supplied"):
            await wpc.create_page(
                "Title", "slug", "<p>x</p>",
                execution_mode="live", approval_token=None, scope_ids=["slug"], user=FAKE_USER,
            )

    async def test_live_without_credentials_fails_clearly(self, mock_db, monkeypatch):
        monkeypatch.setattr(wpc, "IS_LIVE", False)
        payload = {"title": "Title", "slug": "slug", "content": "<p>x</p>", "meta": {}}
        issued = await wws.issue_approval_token("single", ["slug"], payload)
        with pytest.raises(wpc.WpWriteSafetyError, match="no WordPress credentials are configured"):
            await wpc.create_page(
                "Title", "slug", "<p>x</p>",
                execution_mode="live", approval_token=issued["token"], scope_ids=["slug"], user=FAKE_USER,
            )

    async def test_live_with_valid_token_writes_as_draft_by_default(self, mock_db, monkeypatch):
        monkeypatch.setattr(wpc, "IS_LIVE", True)
        captured = {}

        async def fake_live_create(title, slug, content, status, meta):
            captured["status"] = status
            return {"id": "123", "wp_id": 123, "status": status, "mock": False}

        monkeypatch.setattr(wpc, "_live_create_page", fake_live_create)

        payload = {"title": "Title", "slug": "slug", "content": "<p>x</p>", "meta": {}}
        issued = await wws.issue_approval_token("single", ["slug"], payload, publication_mode="draft")

        result = await wpc.create_page(
            "Title", "slug", "<p>x</p>", status="publish",  # caller asks for publish...
            execution_mode="live", approval_token=issued["token"], scope_ids=["slug"], user=FAKE_USER,
        )
        # ...but publication_mode was never authorized as "publish", so the
        # gate must force draft regardless of what status was requested.
        assert captured["status"] == "draft"
        assert result["status"] == "draft"

    async def test_publish_requires_explicit_authorization(self, mock_db, monkeypatch):
        monkeypatch.setattr(wpc, "IS_LIVE", True)
        captured = {}

        async def fake_live_create(title, slug, content, status, meta):
            captured["status"] = status
            return {"id": "123", "wp_id": 123, "status": status, "mock": False}

        monkeypatch.setattr(wpc, "_live_create_page", fake_live_create)

        payload = {"title": "Title", "slug": "slug", "content": "<p>x</p>", "meta": {}}
        issued = await wws.issue_approval_token("single", ["slug"], payload, publication_mode="publish")

        result = await wpc.create_page(
            "Title", "slug", "<p>x</p>", status="publish",
            execution_mode="live", approval_token=issued["token"], scope_ids=["slug"], user=FAKE_USER,
        )
        assert captured["status"] == "publish"
        assert result["status"] == "publish"

    async def test_no_caller_can_omit_execution_mode(self):
        """
        create_page()/update_page() require execution_mode with NO default
        value -- a future caller that forgets to specify it gets an
        immediate TypeError rather than silently taking some default path.
        """
        with pytest.raises(TypeError):
            await wpc.create_page("Title", "slug", "<p>x</p>")  # no execution_mode
        with pytest.raises(TypeError):
            await wpc.update_page("123", "<p>x</p>")  # no execution_mode


# ================== WORKER QUEUE (Jenny -> Rene -> WP Placement) ==================

class TestWorkerQueueGate:

    async def test_jenny_and_rene_definitions_unchanged(self):
        """Jenny and Rene remain unaffected by the write-safety change."""
        assert wq.WORKERS["jenny"]["auto_execute"] is True
        assert wq.WORKERS["rene"]["auto_execute"] is True
        assert wq.WORKERS["wp_placement"]["auto_execute"] is False

    async def test_wp_placement_first_execution_is_dry_run_preview(self, mock_db, monkeypatch):
        # Seed a Page Ops page with generated content
        await mock_db.pages.insert_one({
            "id": "page-1",
            "page_name": "Test Page",
            "page_type": "trust",
            "slug": "test-page",
            "generated_content": "Hero headline\n\nSome intro text.\n\nBody paragraph one.",
        })

        task = await wq.create_worker_task(
            source_module="page_ops",
            source_item_id="page-1",
            worker="wp_placement",
            task_type="wp_draft",
        )
        # wp_placement is not auto_execute, so it stays queued until a
        # manual execute call -- exactly the existing behavior, preserved.
        assert task["status"] == "queued"
        assert task["founder_action_needed"] is True

        result = await wq.execute_worker_task(task["id"], user=FAKE_USER)
        assert result["status"] == "needs_review"
        assert result["founder_action_needed"] is True
        assert result["result"]["needs_review"] is True
        assert result["result"].get("approval_token")
        assert "preview" in result["result"]

        # No live write should have happened -- nothing in wp_mock_pages,
        # nothing in wp_placements.
        assert await mock_db.wp_mock_pages.count_documents({}) == 0
        assert await mock_db.wp_placements.count_documents({}) == 0

    async def test_wp_placement_second_execution_with_token_writes_mock(self, mock_db):
        await mock_db.pages.insert_one({
            "id": "page-2",
            "page_name": "Second Page",
            "page_type": "trust",
            "slug": "second-page",
            "generated_content": "Hero headline\n\nIntro text.\n\nBody paragraph.",
        })
        task = await wq.create_worker_task(
            source_module="page_ops", source_item_id="page-2",
            worker="wp_placement", task_type="wp_draft",
        )
        preview = await wq.execute_worker_task(task["id"], user=FAKE_USER)
        token = preview["result"]["approval_token"]

        # Approve & execute live (IS_LIVE is False in this test env, so
        # "live" falls through to a clear credential failure -- proving the
        # gate does NOT silently write when credentials are absent)
        await mock_db.worker_tasks.update_one(
            {"id": task["id"]},
            {"$set": {"context.execution_mode": "live", "context.approval_token": token}},
        )
        result = await wq.execute_worker_task(task["id"], user=FAKE_USER)
        assert result["status"] == "failed"
        assert "credentials" in result["result"]["error"]

        # Now prove the success path using execution_mode="mock", which
        # never requires a token and never touches real WordPress.
        await mock_db.worker_tasks.update_one(
            {"id": task["id"]},
            {"$set": {"status": "queued", "context.execution_mode": "mock", "context.approval_token": None}},
        )
        result2 = await wq.execute_worker_task(task["id"], user=FAKE_USER)
        assert result2["status"] == "completed"
        assert result2["result"]["success"] is True
        assert await mock_db.wp_mock_pages.count_documents({}) == 1

    async def test_wp_page_update_first_execution_is_dry_run_preview(self, mock_db):
        await mock_db.wp_mock_pages.insert_one({
            "id": "wp-existing-1", "wp_id": None, "title": "Existing",
            "slug": "existing", "content": "[section]Old content[/section]",
            "status": "draft", "seo_title": "", "meta_description": "",
            "link": "https://x/existing", "created_at": "now", "updated_at": "now", "mock": True,
        })
        task = await wq.create_worker_task(
            source_module="page_ops", source_item_id="page-3",
            worker="wp_placement", task_type="wp_page_update",
            context={"drafted_html": "<p>new section</p>", "wp_page_id": "wp-existing-1", "page_name": "Existing"},
        )
        result = await wq.execute_worker_task(task["id"], user=FAKE_USER)
        assert result["status"] == "needs_review"
        assert result["result"]["approval_token"]
        # Nothing written yet
        page = await mock_db.wp_mock_pages.find_one({"id": "wp-existing-1"})
        assert "new section" not in page["content"]
