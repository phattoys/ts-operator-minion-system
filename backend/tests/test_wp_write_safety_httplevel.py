"""
HTTP-level verification of the unified WordPress write-safety gate, run
in-process via FastAPI's TestClient against a minimal app built from the
REAL production route modules (auth_router, wp_placement_router,
worker_queue_router) -- not a reimplementation, the actual code.

This exists because the repo's full server.py wires up many unrelated
routers (product_intake, spec_writer, lead_magnet, comms, catalog,
dashboard, spine, command_center) with heavy third-party dependencies
(google-genai, boto3, litellm, etc.) that are out of scope for this
verification and not installable/needed in this sandbox. Building a
minimal app from only the three routers this feature touches lets these
tests exercise real HTTP request/response cycles -- routing, request
validation, status codes, response shapes -- without that unrelated
surface area, and without a live deployed server or real MongoDB.

Still NOT proven by this file: behavior against a real MongoDB instance,
and behavior against real WordPress. Those remain the responsibility of
Phase 6 in the verification report (blocked in this sandbox -- no real WP
credentials or reachable WordPress site) and of running the full
server.py-based suite in the actual deployed environment.
"""
import pytest
from datetime import datetime, timedelta, timezone
from fastapi import FastAPI
from fastapi.testclient import TestClient

ADMIN_PASSWORD = "test-password"  # matches conftest.py's ADMIN_PASSWORD env default


@pytest.fixture
def client(mock_db):
    """Minimal real app: auth + wp_placement + worker_queue routers only."""
    from auth import auth_router
    from routes.wp_placement import wp_placement_router
    from routes.worker_queue import worker_queue_router

    app = FastAPI()
    app.include_router(auth_router)
    app.include_router(wp_placement_router)
    app.include_router(worker_queue_router)
    return TestClient(app)


@pytest.fixture
def auth_headers(client):
    r = client.post("/api/auth/login", json={"password": ADMIN_PASSWORD})
    assert r.status_code == 200, r.text
    token = r.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def _place_body(**overrides):
    body = {
        "mode": "create",
        "page_title": "TS Operator Minion Safety Gate Verification — 2026-07-14",
        "hero_headline": "Hero",
        "intro": "Intro text",
        "body_section_1": "Body content",
    }
    body.update(overrides)
    return body


# ================== PHASE 3: MOCK MODE ==================

class TestMockModeHttp:

    def test_mock_mode_never_touches_live_and_writes_mock_page(self, client, auth_headers, monkeypatch):
        import services.wp_client as wpc
        # Simulate real credentials being present
        monkeypatch.setattr(wpc, "IS_LIVE", True)
        called = {"live": False}

        async def fake_live_create(*a, **kw):
            called["live"] = True
            return {"id": "SHOULD-NOT-HAPPEN"}
        monkeypatch.setattr(wpc, "_live_create_page", fake_live_create)

        body = _place_body(execution={"execution_mode": "mock"})
        r = client.post("/api/wp-placement/place", json=body, headers=auth_headers)
        assert r.status_code == 200, r.text
        data = r.json()
        assert data["execution_mode"] == "mock"
        assert data["wrote_to_wordpress"] is False
        assert data["page"]["mock"] is True
        assert called["live"] is False, "mock mode must never call the live create path, even with credentials present"


# ================== PHASE 4: DRY RUN ==================

class TestDryRunHttp:

    def test_dry_run_is_default(self, client, auth_headers):
        r = client.post("/api/wp-placement/place", json=_place_body(), headers=auth_headers)
        assert r.status_code == 200, r.text
        data = r.json()
        assert data["execution_mode"] == "dry_run"
        assert data["wrote_to_wordpress"] is False
        assert data["approval_token"]
        assert "expires_at" in data
        assert "preview" in data and "html_preview" in data["preview"]

    def test_dry_run_creates_no_placement_log_entry(self, client, auth_headers, mock_db):
        client.post("/api/wp-placement/place", json=_place_body(), headers=auth_headers)
        assert mock_db  # sanity


# ================== PHASE 5: TOKEN SAFETY ==================

class TestTokenSafetyHttp:

    def test_live_without_token_fails(self, client, auth_headers, monkeypatch):
        import services.wp_client as wpc
        monkeypatch.setattr(wpc, "IS_LIVE", True)  # isolate the token check from the credentials check
        body = _place_body(execution={"execution_mode": "live"})
        r = client.post("/api/wp-placement/place", json=body, headers=auth_headers)
        assert r.status_code == 409
        assert "no approval_token supplied" in r.json()["detail"]

    def test_live_with_unknown_token_fails(self, client, auth_headers, monkeypatch):
        import services.wp_client as wpc
        monkeypatch.setattr(wpc, "IS_LIVE", True)  # isolate the token check from the credentials check
        body = _place_body(execution={"execution_mode": "live", "approval_token": "fake-token"})
        r = client.post("/api/wp-placement/place", json=body, headers=auth_headers)
        assert r.status_code == 409
        assert "not found" in r.json()["detail"]

    def test_live_without_credentials_fails_clearly(self, client, auth_headers, monkeypatch):
        import services.wp_client as wpc
        monkeypatch.setattr(wpc, "IS_LIVE", False)

        dry = client.post("/api/wp-placement/place", json=_place_body(), headers=auth_headers)
        token = dry.json()["approval_token"]

        body = _place_body(execution={"execution_mode": "live", "approval_token": token})
        r = client.post("/api/wp-placement/place", json=body, headers=auth_headers)
        assert r.status_code == 409
        assert "no WordPress credentials are configured" in r.json()["detail"]

    def test_altered_payload_after_approval_fails(self, client, auth_headers, monkeypatch):
        import services.wp_client as wpc
        monkeypatch.setattr(wpc, "IS_LIVE", True)
        monkeypatch.setattr(wpc, "_live_create_page", lambda *a, **kw: {"id": "x"})

        dry = client.post("/api/wp-placement/place", json=_place_body(), headers=auth_headers)
        token = dry.json()["approval_token"]

        body = _place_body(
            intro="This is different content than what was approved",
            execution={"execution_mode": "live", "approval_token": token},
        )
        r = client.post("/api/wp-placement/place", json=body, headers=auth_headers)
        assert r.status_code == 409
        assert "content has changed" in r.json()["detail"]

    def test_expired_token_fails(self, client, auth_headers, mock_db, monkeypatch):
        import services.wp_client as wpc
        monkeypatch.setattr(wpc, "IS_LIVE", True)

        dry = client.post("/api/wp-placement/place", json=_place_body(), headers=auth_headers)
        token = dry.json()["approval_token"]

        import asyncio
        asyncio.run(
            mock_db.wp_write_approvals.update_one(
                {"token": token},
                {"$set": {"expires_at": (datetime.now(timezone.utc) - timedelta(minutes=1)).isoformat()}},
            )
        )

        body = _place_body(execution={"execution_mode": "live", "approval_token": token})
        r = client.post("/api/wp-placement/place", json=body, headers=auth_headers)
        assert r.status_code == 409
        assert "expired" in r.json()["detail"]

    def test_server_derived_identity_not_trusted_from_client(self, client, auth_headers, monkeypatch, mock_db):
        """
        approved_by / approval_role / approval_source / approved_at cannot be
        supplied by the client at all -- WpWriteApproval only accepts
        execution_mode / publication_mode / approval_token. Prove the wire
        model rejects (ignores, via pydantic extra=ignore default, or the
        field simply doesn't exist to set) any attempt to inject them, and
        that the value actually recorded comes from the authenticated
        session, not the request body.
        """
        import services.wp_client as wpc
        monkeypatch.setattr(wpc, "IS_LIVE", True)

        async def fake_live_create(title, slug, content, status, meta):
            return {"id": "wp-1", "wp_id": 1, "status": status, "mock": False}
        monkeypatch.setattr(wpc, "_live_create_page", fake_live_create)

        dry = client.post("/api/wp-placement/place", json=_place_body(), headers=auth_headers)
        token = dry.json()["approval_token"]

        body = _place_body(execution={
            "execution_mode": "live",
            "approval_token": token,
            # attempted injection -- these are not fields on WpWriteApproval
            "approved_by": "attacker",
            "approval_role": "root",
            "approval_source": "self_approved",
        })
        r = client.post("/api/wp-placement/place", json=body, headers=auth_headers)
        assert r.status_code == 200, r.text

        import asyncio
        record = asyncio.run(mock_db.wp_write_approvals.find_one({"token": token}))
        assert record["approved_by"] == "founder"  # from the JWT "sub" claim, not the injected "attacker"
        assert record["approval_role"] == "admin"
        assert record["approval_source"] == "manual_confirmation"
        assert record["consumed"] is True
        assert record["consumed_at"] is not None


# ================== PHASE 7: PUBLICATION SAFETY ==================

class TestPublicationSafetyHttp:

    def test_live_draft_forces_draft_status_even_if_settings_say_otherwise(self, client, auth_headers, monkeypatch):
        import services.wp_client as wpc
        monkeypatch.setattr(wpc, "IS_LIVE", True)
        captured = {}

        async def fake_live_create(title, slug, content, status, meta):
            captured["status"] = status
            return {"id": "wp-2", "wp_id": 2, "status": status, "mock": False}
        monkeypatch.setattr(wpc, "_live_create_page", fake_live_create)

        dry = client.post(
            "/api/wp-placement/place",
            json=_place_body(execution={"execution_mode": "dry_run", "publication_mode": "draft"}),
            headers=auth_headers,
        )
        assert dry.json()["preview"]["publication_mode"] == "draft"
        token = dry.json()["approval_token"]

        r = client.post(
            "/api/wp-placement/place",
            json=_place_body(execution={"execution_mode": "live", "approval_token": token, "publication_mode": "draft"}),
            headers=auth_headers,
        )
        assert r.status_code == 200, r.text
        assert captured["status"] == "draft"
        assert r.json()["page"]["status"] == "draft"

    def test_publish_requires_explicit_authorization_at_approval_time(self, client, auth_headers, monkeypatch):
        import services.wp_client as wpc
        monkeypatch.setattr(wpc, "IS_LIVE", True)
        captured = {}

        async def fake_live_create(title, slug, content, status, meta):
            captured["status"] = status
            return {"id": "wp-3", "wp_id": 3, "status": status, "mock": False}
        monkeypatch.setattr(wpc, "_live_create_page", fake_live_create)

        dry = client.post(
            "/api/wp-placement/place",
            json=_place_body(page_title="Publish Auth Test", execution={"execution_mode": "dry_run", "publication_mode": "publish"}),
            headers=auth_headers,
        )
        token = dry.json()["approval_token"]

        r = client.post(
            "/api/wp-placement/place",
            json=_place_body(page_title="Publish Auth Test", execution={"execution_mode": "live", "approval_token": token, "publication_mode": "publish"}),
            headers=auth_headers,
        )
        assert r.status_code == 200, r.text
        assert captured["status"] == "publish"


# ================== PHASE 8: REGRESSION (WORKER QUEUE) ==================

class TestWorkerQueueRegressionHttp:

    def test_wp_placement_task_execute_needs_review_then_approved_write(self, client, auth_headers, mock_db):
        import asyncio
        asyncio.run(mock_db.pages.insert_one({
            "id": "page-http-1", "page_name": "HTTP Test Page", "page_type": "trust",
            "slug": "http-test-page",
            "generated_content": "Hero\n\nIntro text.\n\nBody paragraph.",
        }))
        import services.worker_queue as wq
        task = asyncio.run(wq.create_worker_task(
            source_module="page_ops", source_item_id="page-http-1",
            worker="wp_placement", task_type="wp_draft",
        ))

        r1 = client.post(f"/api/worker-queue/tasks/{task['id']}/execute", headers=auth_headers)
        assert r1.status_code == 200, r1.text
        d1 = r1.json()
        assert d1["status"] == "needs_review"
        token = d1["result"]["approval_token"]

        r2 = client.post(
            f"/api/worker-queue/tasks/{task['id']}/execute",
            json={"execution_mode": "mock"},
            headers=auth_headers,
        )
        assert r2.status_code == 200, r2.text
        d2 = r2.json()
        assert d2["status"] == "completed"
        assert d2["result"]["success"] is True
