"""
HTTP-level proof for the Execution Manifest trace repair
(ops/execution-manifest-phase-2-workspace-20260714, repair pass).

Real HTTP request/response cycle through the actual
routes/execution_manifest.py router (not a direct function call), proving
GET /api/execution-manifests/{id}/trace returns the full Jenny -> Rene ->
WP Placement worker chain -- the exact defect the real-browser review
found (trace previously showed only the initial Jenny task).
"""
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

ADMIN_PASSWORD = "test-password"


@pytest.fixture
def client(mock_db):
    from auth import auth_router
    from routes.execution_manifest import execution_manifest_router

    app = FastAPI()
    app.include_router(auth_router)
    app.include_router(execution_manifest_router)
    return TestClient(app)


@pytest.fixture
def auth_headers(client):
    r = client.post("/api/auth/login", json={"password": ADMIN_PASSWORD})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


async def _seed_wp_page(mock_db, page_id="page-http-1", wp_page_id="354952"):
    await mock_db.pages.insert_one({
        "id": page_id, "page_name": "HTTP Trace Test Page", "page_type": "trust",
        "slug": "http-trace-test-page",
        "generated_content": "[section]Original content.[/section]",
        "wp_page_id": wp_page_id,
    })
    await mock_db.wp_mock_pages.insert_one({
        "id": wp_page_id, "wp_id": int(wp_page_id), "title": "HTTP Trace Test Page",
        "slug": "http-trace-test-page", "content": "[section]Original content.[/section]",
        "status": "draft", "seo_title": "", "meta_description": "",
        "link": "https://example.test/http-trace-test-page",
        "created_at": "now", "updated_at": "now", "mock": True,
    })


def _manifest_body(page_id="page-http-1", wp_page_id="354952"):
    return {
        "schema_version": "1.0",
        "source_system": "TSAF",
        "source_packet_id": "packet-http-1",
        "campaign_id": "camp-http-1",
        "campaign_name": "HTTP Trace Repair Verification",
        "execution_items": [
            {
                "item_id": "item-1", "manifest_id": "", "sequence": 1,
                "title": "Update trust page", "destination": "wordpress",
                "execution_type": "content_draft", "status": "pending",
                "copy": "Verified: HTTP-level trace repair proof.",
                "placement": {"page_id": page_id, "wp_page_id": wp_page_id},
                "asset_refs": [], "dependencies": [], "context": {}, "qa_requirements": [], "warnings": [],
            },
            {
                "item_id": "item-2", "manifest_id": "", "sequence": 2,
                "title": "Schedule Instagram post", "destination": "metricool",
                "execution_type": "social_post", "status": "pending",
                "copy": "A post", "asset_refs": [], "dependencies": [], "context": {},
                "qa_requirements": [], "warnings": [],
            },
        ],
        "assets": [],
    }


class TestTraceHttpRepair:

    def test_trace_endpoint_returns_full_worker_chain_over_http(self, client, auth_headers, mock_db):
        import asyncio
        asyncio.run(_seed_wp_page(mock_db))

        create = client.post("/api/execution-manifests", json=_manifest_body(), headers=auth_headers)
        assert create.status_code == 200, create.text
        manifest_id = create.json()["manifest_id"]

        validate = client.post(f"/api/execution-manifests/{manifest_id}/validate", headers=auth_headers)
        assert validate.status_code == 200, validate.text

        queue = client.post(f"/api/execution-manifests/{manifest_id}/items/item-1/queue", headers=auth_headers)
        assert queue.status_code == 200, queue.text
        assert queue.json()["queued"] is True

        trace = client.get(f"/api/execution-manifests/{manifest_id}/trace", headers=auth_headers)
        assert trace.status_code == 200, trace.text
        item1 = next(i for i in trace.json()["items"] if i["item_id"] == "item-1")

        chain = item1["worker_chain"]
        assert [t["worker"] for t in chain] == ["jenny", "rene", "wp_placement"]
        assert chain[0]["status"] == "completed"
        assert chain[1]["status"] == "completed"
        assert chain[2]["status"] == "queued"
        assert chain[2]["founder_action_needed"] is True
        assert chain[2]["auto_execute"] is False

        # Metricool item never got a task at all -- empty chain, never invented
        item2 = next(i for i in trace.json()["items"] if i["item_id"] == "item-2")
        assert item2["worker_chain"] == []

    def test_duplicate_queue_over_http_creates_no_extra_tasks(self, client, auth_headers, mock_db):
        import asyncio
        asyncio.run(_seed_wp_page(mock_db, page_id="page-http-2", wp_page_id="354953"))

        body = _manifest_body(page_id="page-http-2", wp_page_id="354953")
        body["source_packet_id"] = "packet-http-2"
        create = client.post("/api/execution-manifests", json=body, headers=auth_headers)
        manifest_id = create.json()["manifest_id"]
        client.post(f"/api/execution-manifests/{manifest_id}/validate", headers=auth_headers)

        first = client.post(f"/api/execution-manifests/{manifest_id}/items/item-1/queue", headers=auth_headers)
        assert first.json()["queued"] is True

        second = client.post(f"/api/execution-manifests/{manifest_id}/items/item-1/queue", headers=auth_headers)
        assert second.json()["already_queued"] is True

        trace = client.get(f"/api/execution-manifests/{manifest_id}/trace", headers=auth_headers)
        chain = next(i for i in trace.json()["items"] if i["item_id"] == "item-1")["worker_chain"]
        assert len(chain) == 3  # still exactly one Jenny, one Rene, one WP Placement task
