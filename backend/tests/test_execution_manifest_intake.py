"""
Execution Manifest Intake — Phase 3 tests
(ops/execution-manifest-phase-3-intake-20260716, built on 809e25f93e65cb35536a3ea2850a673e9c295217)

Real HTTP request/response cycle through the actual production routers
(auth, execution_manifest, execution_manifest_intake) via FastAPI's
TestClient, against the in-memory Mongo double (see tests/conftest.py).
No live server or real MongoDB required.
"""
import hashlib
import hmac
import json
import time

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

ADMIN_PASSWORD = "test-password"
INTAKE_SECRET = "test-intake-secret-do-not-use-in-prod"  # matches conftest.py's env default


@pytest.fixture
def client(mock_db):
    from auth import auth_router
    from routes.execution_manifest import execution_manifest_router
    from routes.execution_manifest_intake import intake_router

    app = FastAPI()
    app.include_router(auth_router)
    app.include_router(execution_manifest_router)
    app.include_router(intake_router)
    return TestClient(app)


@pytest.fixture
def auth_headers(client):
    r = client.post("/api/auth/login", json={"password": ADMIN_PASSWORD})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def _wp_item(item_id="item-1", copy="Verified: Phase 3 intake proof.", **overrides):
    item = {
        "item_id": item_id, "manifest_id": "", "sequence": 1,
        "title": "Update trust page", "destination": "wordpress",
        "execution_type": "content_draft", "status": "pending",
        "copy": copy, "placement": {"page_id": "page-intake-1", "wp_page_id": "354960"},
        "asset_refs": [], "dependencies": [], "context": {}, "qa_requirements": [], "warnings": [],
    }
    item.update(overrides)
    return item


def _metricool_item():
    return {
        "item_id": "item-2", "manifest_id": "", "sequence": 2,
        "title": "Schedule Instagram post", "destination": "metricool",
        "execution_type": "social_post", "status": "pending",
        "copy": "A post", "asset_refs": [], "dependencies": [], "context": {},
        "qa_requirements": [], "warnings": [],
    }


def _manifest(items=None):
    return {
        "schema_version": "1.0",
        "source_system": "TSAF",
        "source_packet_id": "will-be-overridden",
        "campaign_id": "camp-intake-1",
        "campaign_name": "Intake Verification Campaign",
        "execution_items": items if items is not None else [_wp_item(), _metricool_item()],
        "assets": [],
    }


def _envelope(packet_id="packet-intake-1", idempotency_key="idem-1", items=None, **overrides):
    env = {
        "packet_id": packet_id,
        "packet_version": "1.0",
        "source_system": "tsaf",
        "source_environment": "controlled-proof",
        "source_packet_type": "campaign",
        "source_packet_id": packet_id,
        "sent_at": "2026-07-16T00:00:00Z",
        "sender_id": "tsaf-controlled-proof",
        "brand_id": "ts",
        "campaign_id": "camp-intake-1",
        "campaign_name": "Intake Verification Campaign",
        "manifest": _manifest(items),
        "asset_index": [],
        "packet_location": None,
        "idempotency_key": idempotency_key,
        "metadata": {},
    }
    env.update(overrides)
    return env


def _sign(body_bytes, timestamp, secret=INTAKE_SECRET):
    signing_input = timestamp.encode("utf-8") + b"." + body_bytes
    return hmac.new(secret.encode("utf-8"), signing_input, hashlib.sha256).hexdigest()


def _signed_headers(envelope, secret=INTAKE_SECRET, timestamp=None):
    body = json.dumps(envelope).encode("utf-8")
    ts = timestamp or str(time.time())
    sig = _sign(body, ts, secret=secret)
    return body, {
        "X-TS-Source": "tsaf",
        "X-TS-Timestamp": ts,
        "X-TS-Signature": sig,
        "X-TS-Idempotency-Key": envelope["idempotency_key"],
        "Content-Type": "application/json",
    }


async def _seed_wp_page(mock_db, page_id="page-intake-1", wp_page_id="354960"):
    await mock_db.pages.insert_one({
        "id": page_id, "page_name": "Intake Test Page", "page_type": "trust",
        "slug": "intake-test-page",
        "generated_content": "[section]Original content.[/section]",
        "wp_page_id": wp_page_id,
    })
    await mock_db.wp_mock_pages.insert_one({
        "id": wp_page_id, "wp_id": int(wp_page_id), "title": "Intake Test Page",
        "slug": "intake-test-page", "content": "[section]Original content.[/section]",
        "status": "draft", "seo_title": "", "meta_description": "",
        "link": "https://example.test/intake-test-page",
        "created_at": "now", "updated_at": "now", "mock": True,
    })


# ================== 1-5: SERVER-TO-SERVER HMAC INTAKE ==================

class TestReceiveHttpAuth:

    def test_valid_hmac_packet_accepted(self, client, mock_db):
        import asyncio
        asyncio.run(_seed_wp_page(mock_db))
        env = _envelope(packet_id="packet-valid-1", idempotency_key="idem-valid-1")
        body, headers = _signed_headers(env)
        r = client.post("/api/execution-manifest-intake/receive", data=body, headers=headers)
        assert r.status_code == 200, r.text
        data = r.json()
        assert data["status"] == "accepted"
        assert data["manifest_id"]
        assert data["authentication_status"] == "authenticated"

    def test_missing_signature_rejected(self, client):
        env = _envelope(packet_id="packet-missing-sig", idempotency_key="idem-missing-sig")
        body = json.dumps(env).encode("utf-8")
        headers = {"X-TS-Source": "tsaf", "X-TS-Timestamp": str(time.time())}
        r = client.post("/api/execution-manifest-intake/receive", data=body, headers=headers)
        assert r.status_code == 401
        assert "signature" in r.json()["detail"].lower()

    def test_invalid_signature_rejected(self, client):
        env = _envelope(packet_id="packet-bad-sig", idempotency_key="idem-bad-sig")
        body, headers = _signed_headers(env)
        headers["X-TS-Signature"] = "0" * 64  # well-formed but wrong
        r = client.post("/api/execution-manifest-intake/receive", data=body, headers=headers)
        assert r.status_code == 401
        assert "signature" in r.json()["detail"].lower()

    def test_stale_timestamp_rejected(self, client):
        env = _envelope(packet_id="packet-stale", idempotency_key="idem-stale")
        stale_ts = str(time.time() - 3600)  # 1 hour old, outside default 300s window
        body, headers = _signed_headers(env, timestamp=stale_ts)
        r = client.post("/api/execution-manifest-intake/receive", data=body, headers=headers)
        assert r.status_code == 401
        assert "timestamp" in r.json()["detail"].lower() or "replay" in r.json()["detail"].lower()

    def test_checksum_mismatch_rejected(self, client, mock_db):
        env = _envelope(packet_id="packet-checksum-bad", idempotency_key="idem-checksum-bad")
        env["packet_checksum"] = "not-the-real-checksum"
        body, headers = _signed_headers(env)
        r = client.post("/api/execution-manifest-intake/receive", data=body, headers=headers)
        assert r.status_code == 200, r.text  # a quarantine is a 200 receipt, not an HTTP error
        data = r.json()
        assert data["status"] == "quarantined"
        assert data["checksum_status"] == "mismatch"
        assert data["manifest_id"] is None

    def test_correct_checksum_verified_as_match(self, client, mock_db):
        from services.execution_manifest_intake import compute_packet_checksum
        env = _envelope(packet_id="packet-checksum-good", idempotency_key="idem-checksum-good")
        env["packet_checksum"] = compute_packet_checksum(env)
        body, headers = _signed_headers(env)
        r = client.post("/api/execution-manifest-intake/receive", data=body, headers=headers)
        assert r.status_code == 200, r.text
        data = r.json()
        assert data["checksum_status"] == "match"
        assert data["status"] == "accepted"


# ================== 6-7: MANUAL FOUNDER INTAKE ==================

class TestManualIntake:

    def test_valid_manual_founder_intake_accepted(self, client, auth_headers, mock_db):
        import asyncio
        asyncio.run(_seed_wp_page(mock_db, page_id="page-intake-2", wp_page_id="354961"))
        env = _envelope(packet_id="packet-manual-1", idempotency_key="idem-manual-1",
                         items=[_wp_item(item_id="item-1", placement={"page_id": "page-intake-2", "wp_page_id": "354961"})])
        r = client.post("/api/execution-manifest-intake/manual", json={"envelope": env}, headers=auth_headers)
        assert r.status_code == 200, r.text
        assert r.json()["status"] == "accepted"
        assert r.json()["transport"] == "manual"

    def test_unauthenticated_manual_intake_rejected(self, client):
        env = _envelope(packet_id="packet-manual-unauth", idempotency_key="idem-manual-unauth")
        r = client.post("/api/execution-manifest-intake/manual", json={"envelope": env})
        assert r.status_code in (401, 403)


# ================== 8-10: IDEMPOTENCY AND CONFLICT ==================

class TestIdempotencyAndConflict:

    def test_duplicate_idempotency_key_returns_original_receipt(self, client, mock_db):
        import asyncio
        asyncio.run(_seed_wp_page(mock_db, page_id="page-intake-3", wp_page_id="354962"))
        env = _envelope(packet_id="packet-dup-1", idempotency_key="idem-dup-1",
                         items=[_wp_item(item_id="item-1", placement={"page_id": "page-intake-3", "wp_page_id": "354962"})])
        body, headers = _signed_headers(env)
        first = client.post("/api/execution-manifest-intake/receive", data=body, headers=headers)
        assert first.status_code == 200

        second = client.post("/api/execution-manifest-intake/receive", data=body, headers=headers)
        assert second.status_code == 200
        assert second.json()["receipt_id"] == first.json()["receipt_id"]
        assert second.json()["manifest_id"] == first.json()["manifest_id"]

    def test_duplicate_packet_does_not_create_duplicate_manifest(self, client, mock_db):
        import asyncio
        asyncio.run(_seed_wp_page(mock_db, page_id="page-intake-4", wp_page_id="354963"))
        env = _envelope(packet_id="packet-dup-2", idempotency_key="idem-dup-2",
                         items=[_wp_item(item_id="item-1", placement={"page_id": "page-intake-4", "wp_page_id": "354963"})])
        body, headers = _signed_headers(env)
        client.post("/api/execution-manifest-intake/receive", data=body, headers=headers)
        client.post("/api/execution-manifest-intake/receive", data=body, headers=headers)

        count = asyncio.run(mock_db.execution_manifests.count_documents({"intake_packet_id": "packet-dup-2"}))
        assert count == 1

    def test_same_packet_id_changed_payload_is_quarantined(self, client, mock_db):
        env1 = _envelope(packet_id="packet-conflict-1", idempotency_key="idem-conflict-a")
        body1, headers1 = _signed_headers(env1)
        r1 = client.post("/api/execution-manifest-intake/receive", data=body1, headers=headers1)
        assert r1.status_code == 200

        env2 = _envelope(packet_id="packet-conflict-1", idempotency_key="idem-conflict-b",
                          items=[_wp_item(item_id="item-1", copy="This is different content.")])
        body2, headers2 = _signed_headers(env2)
        r2 = client.post("/api/execution-manifest-intake/receive", data=body2, headers=headers2)
        assert r2.status_code == 200
        assert r2.json()["status"] == "quarantined"
        assert r2.json()["manifest_id"] is None


# ================== 11-13: INVALID / UNSAFE MANIFEST CONTENT ==================

class TestUnsafeManifestRejection:

    def test_invalid_nested_manifest_rejected(self, client):
        env = _envelope(packet_id="packet-invalid-manifest", idempotency_key="idem-invalid-manifest", items=[])
        body, headers = _signed_headers(env)
        r = client.post("/api/execution-manifest-intake/receive", data=body, headers=headers)
        assert r.status_code == 200
        data = r.json()
        assert data["status"] in ("rejected", "quarantined")
        assert data["schema_status"] == "invalid"
        assert any("at least one execution item" in e for e in data["errors"])

    def test_unsafe_execution_mode_field_rejected(self, client):
        item = _wp_item(context={"execution_mode": "live"})
        env = _envelope(packet_id="packet-unsafe-mode", idempotency_key="idem-unsafe-mode", items=[item])
        body, headers = _signed_headers(env)
        r = client.post("/api/execution-manifest-intake/receive", data=body, headers=headers)
        assert r.status_code == 200
        data = r.json()
        assert data["manifest_id"] is None
        assert any("execution_mode" in e and "context may not set" in e for e in data["errors"])

    def test_unsafe_approval_token_field_rejected(self, client):
        item = _wp_item(context={"approval_token": "forged-token"})
        env = _envelope(packet_id="packet-unsafe-token", idempotency_key="idem-unsafe-token", items=[item])
        body, headers = _signed_headers(env)
        r = client.post("/api/execution-manifest-intake/receive", data=body, headers=headers)
        assert r.status_code == 200
        data = r.json()
        assert data["manifest_id"] is None
        assert any("approval_token" in e and "context may not set" in e for e in data["errors"])


# ================== 14-15: NO AUTOMATIC EXECUTION ==================

class TestNoAutomaticExecution:

    def test_accepted_intake_creates_no_worker_tasks_and_no_wp_write(self, client, mock_db):
        import asyncio
        asyncio.run(_seed_wp_page(mock_db, page_id="page-intake-5", wp_page_id="354964"))
        env = _envelope(packet_id="packet-no-exec", idempotency_key="idem-no-exec",
                         items=[_wp_item(item_id="item-1", placement={"page_id": "page-intake-5", "wp_page_id": "354964"})])
        body, headers = _signed_headers(env)
        r = client.post("/api/execution-manifest-intake/receive", data=body, headers=headers)
        assert r.status_code == 200
        manifest_id = r.json()["manifest_id"]

        task_count = asyncio.run(mock_db.worker_tasks.count_documents({}))
        assert task_count == 0

        page = asyncio.run(mock_db.wp_mock_pages.find_one({"id": "354964"}))
        assert page["content"] == "[section]Original content.[/section]"

        manifest = asyncio.run(mock_db.execution_manifests.find_one({"manifest_id": manifest_id}))
        assert manifest["status"] == "received"


# ================== 16-18: TRACEABILITY AND RETRY ==================

class TestTraceabilityAndRetry:

    def test_receipt_links_to_manifest_and_manifest_exposes_receipt_origin(self, client, mock_db):
        import asyncio
        asyncio.run(_seed_wp_page(mock_db, page_id="page-intake-6", wp_page_id="354965"))
        env = _envelope(packet_id="packet-trace-1", idempotency_key="idem-trace-1",
                         items=[_wp_item(item_id="item-1", placement={"page_id": "page-intake-6", "wp_page_id": "354965"})])
        body, headers = _signed_headers(env)
        r = client.post("/api/execution-manifest-intake/receive", data=body, headers=headers)
        receipt_id = r.json()["receipt_id"]
        manifest_id = r.json()["manifest_id"]

        manifest = asyncio.run(mock_db.execution_manifests.find_one({"manifest_id": manifest_id}, {"_id": 0}))
        assert manifest["intake_receipt_id"] == receipt_id
        assert manifest["intake_packet_id"] == "packet-trace-1"
        assert manifest["intake_source_system"] == "tsaf"
        assert manifest["intake_transport"] == "server_to_server"

    def test_retry_remains_idempotent(self, client, auth_headers, mock_db):
        env = _envelope(packet_id="packet-retry-1", idempotency_key="idem-retry-1", items=[])
        body, headers = _signed_headers(env)
        r = client.post("/api/execution-manifest-intake/receive", data=body, headers=headers)
        receipt_id = r.json()["receipt_id"]
        assert r.json()["status"] in ("rejected", "quarantined")

        retry1 = client.post(f"/api/execution-manifest-intake/receipts/{receipt_id}/retry", headers=auth_headers)
        assert retry1.status_code == 200
        assert retry1.json()["status"] in ("rejected", "quarantined")

        retry2 = client.post(f"/api/execution-manifest-intake/receipts/{receipt_id}/retry", headers=auth_headers)
        assert retry2.json()["receipt_id"] == retry1.json()["receipt_id"]

    def test_legacy_manifest_without_receipt_still_renders(self, client, auth_headers, mock_db):
        import asyncio
        from services.execution_manifest import create_manifest
        legacy = asyncio.run(create_manifest({
            "schema_version": "1.0", "source_system": "TSAF", "source_packet_id": "legacy-packet",
            "execution_items": [_wp_item(item_id="item-1")], "assets": [],
        }))
        r = client.get(f"/api/execution-manifests/{legacy['manifest_id']}", headers=auth_headers)
        assert r.status_code == 200
        assert r.json().get("intake_receipt_id") is None


# ================== SECURITY TESTS ==================

class TestIntakeSecurity:

    def test_secret_never_appears_in_any_response(self, client):
        env = _envelope(packet_id="packet-secret-check", idempotency_key="idem-secret-check")
        body, headers = _signed_headers(env)
        r = client.post("/api/execution-manifest-intake/receive", data=body, headers=headers)
        assert INTAKE_SECRET not in r.text

    def test_secret_never_stored_in_receipt_document(self, client, mock_db):
        import asyncio
        env = _envelope(packet_id="packet-secret-store-check", idempotency_key="idem-secret-store-check")
        body, headers = _signed_headers(env)
        client.post("/api/execution-manifest-intake/receive", data=body, headers=headers)
        receipt = asyncio.run(mock_db.execution_manifest_receipts.find_one({"packet_id": "packet-secret-store-check"}))
        assert INTAKE_SECRET not in json.dumps(receipt, default=str)

    def test_malformed_json_returns_controlled_error(self, client):
        ts = str(time.time())
        body = b"{not valid json"
        sig = _sign(body, ts)
        headers = {"X-TS-Source": "tsaf", "X-TS-Timestamp": ts, "X-TS-Signature": sig}
        r = client.post("/api/execution-manifest-intake/receive", data=body, headers=headers)
        assert r.status_code == 400
        assert "json" in r.json()["detail"].lower()

    def test_oversized_request_rejected_regardless_of_client(self, client, monkeypatch):
        import routes.execution_manifest_intake as intake_route
        monkeypatch.setattr(intake_route, "EXECUTION_MANIFEST_MAX_BYTES", 10)
        env = _envelope(packet_id="packet-oversized", idempotency_key="idem-oversized")
        body, headers = _signed_headers(env)
        r = client.post("/api/execution-manifest-intake/receive", data=body, headers=headers)
        assert r.status_code == 413

    def test_timestamp_just_inside_replay_window_accepted(self, client):
        from database import EXECUTION_MANIFEST_INTAKE_REPLAY_WINDOW_SECONDS
        env = _envelope(packet_id="packet-window-inside", idempotency_key="idem-window-inside")
        ts = str(time.time() - (EXECUTION_MANIFEST_INTAKE_REPLAY_WINDOW_SECONDS - 5))
        body, headers = _signed_headers(env, timestamp=ts)
        r = client.post("/api/execution-manifest-intake/receive", data=body, headers=headers)
        assert r.status_code == 200

    def test_timestamp_just_outside_replay_window_rejected(self, client):
        from database import EXECUTION_MANIFEST_INTAKE_REPLAY_WINDOW_SECONDS
        env = _envelope(packet_id="packet-window-outside", idempotency_key="idem-window-outside")
        ts = str(time.time() - (EXECUTION_MANIFEST_INTAKE_REPLAY_WINDOW_SECONDS + 5))
        body, headers = _signed_headers(env, timestamp=ts)
        r = client.post("/api/execution-manifest-intake/receive", data=body, headers=headers)
        assert r.status_code == 401

    def test_constant_time_comparison_is_used_structurally(self):
        """
        Testing actual timing-safety is unreliable in an automated unit
        test; instead, prove the implementation structurally uses
        hmac.compare_digest (never a plain == on the computed signature).
        """
        import inspect
        import services.execution_manifest_intake as intake_svc
        src = inspect.getsource(intake_svc.verify_hmac_signature)
        assert "hmac.compare_digest" in src
        assert "expected == signature" not in src and "signature == expected" not in src


# ================== MANIFEST STILL VISIBLE IN PHASE 2 WORKSPACE ==================

class TestManifestVisibleAfterIntake:

    def test_intake_created_manifest_is_visible_via_phase2_list_and_metricool_still_blocked(self, client, auth_headers, mock_db):
        import asyncio
        asyncio.run(_seed_wp_page(mock_db, page_id="page-intake-7", wp_page_id="354966"))
        env = _envelope(packet_id="packet-visible-1", idempotency_key="idem-visible-1",
                         items=[_wp_item(item_id="item-1", placement={"page_id": "page-intake-7", "wp_page_id": "354966"}), _metricool_item()])
        body, headers = _signed_headers(env)
        r = client.post("/api/execution-manifest-intake/receive", data=body, headers=headers)
        manifest_id = r.json()["manifest_id"]

        listed = client.get("/api/execution-manifests", headers=auth_headers)
        assert any(m["manifest_id"] == manifest_id for m in listed.json()["manifests"])

        validate = client.post(f"/api/execution-manifests/{manifest_id}/validate", headers=auth_headers)
        assert validate.status_code == 200
        metricool_item = next(i for i in validate.json()["execution_items"] if i["destination"] == "metricool")
        assert metricool_item["status"] == "blocked"
        assert any("connector unavailable" in w for w in metricool_item["warnings"])


class TestRealControlledIntakeFlow:
    """
    THE required real proof, combined in one place:

    signed TSAF-labeled packet -> intake receipt -> checksum verified ->
    nested manifest created -> receipt linked to manifest -> manifest
    visible in Phase 2 workspace -> no worker task created -> no
    WordPress write.

    Then: same packet delivered again -> duplicate acknowledged ->
    original receipt returned -> no second manifest.

    Then: Metricool execution item remains connector-unavailable after
    intake.

    source_system="tsaf" is used only as a packet label here -- no live
    TSAF connection is claimed or configured.
    """

    def test_full_controlled_intake_flow(self, client, auth_headers, mock_db):
        import asyncio
        from services.execution_manifest_intake import compute_packet_checksum

        asyncio.run(_seed_wp_page(mock_db, page_id="page-controlled-proof", wp_page_id="354970"))

        env = _envelope(
            packet_id="packet-controlled-proof-1",
            idempotency_key="idem-controlled-proof-1",
            items=[
                _wp_item(item_id="item-1", copy="Controlled proof: real intake flow.",
                         placement={"page_id": "page-controlled-proof", "wp_page_id": "354970"}),
                _metricool_item(),
            ],
        )
        env["packet_checksum"] = compute_packet_checksum(env)
        body, headers = _signed_headers(env)

        # ---- Step 1: signed TSAF-labeled packet -> receipt, checksum verified, manifest created ----
        r1 = client.post("/api/execution-manifest-intake/receive", data=body, headers=headers)
        assert r1.status_code == 200, r1.text
        receipt1 = r1.json()
        assert receipt1["status"] == "accepted"
        assert receipt1["checksum_status"] == "match"
        assert receipt1["source_system"] == "tsaf"
        manifest_id = receipt1["manifest_id"]
        assert manifest_id

        # ---- Step 2: receipt linked to manifest ----
        manifest_doc = asyncio.run(mock_db.execution_manifests.find_one({"manifest_id": manifest_id}, {"_id": 0}))
        assert manifest_doc["intake_receipt_id"] == receipt1["receipt_id"]
        assert manifest_doc["intake_packet_id"] == "packet-controlled-proof-1"

        # ---- Step 3: manifest visible in the Phase 2 workspace ----
        detail = client.get(f"/api/execution-manifests/{manifest_id}", headers=auth_headers)
        assert detail.status_code == 200
        assert detail.json()["manifest_id"] == manifest_id

        # ---- Step 4: no worker task created, no WordPress write ----
        assert asyncio.run(mock_db.worker_tasks.count_documents({})) == 0
        page = asyncio.run(mock_db.wp_mock_pages.find_one({"id": "354970"}))
        assert page["content"] == "[section]Original content.[/section]"

        # ---- Step 5: same packet delivered again -> duplicate acknowledged, original receipt returned ----
        r2 = client.post("/api/execution-manifest-intake/receive", data=body, headers=headers)
        assert r2.status_code == 200
        receipt2 = r2.json()
        assert receipt2["receipt_id"] == receipt1["receipt_id"]
        assert receipt2["manifest_id"] == manifest_id
        manifest_count = asyncio.run(mock_db.execution_manifests.count_documents({"intake_packet_id": "packet-controlled-proof-1"}))
        assert manifest_count == 1  # no second manifest

        # ---- Step 6: Metricool item remains connector-unavailable after intake ----
        validate = client.post(f"/api/execution-manifests/{manifest_id}/validate", headers=auth_headers)
        metricool_item = next(i for i in validate.json()["execution_items"] if i["destination"] == "metricool")
        assert metricool_item["status"] == "blocked"
        assert any("connector unavailable" in w for w in metricool_item["warnings"])

        # Still no worker tasks and no WP write after validation (validate never queues)
        assert asyncio.run(mock_db.worker_tasks.count_documents({})) == 0
