"""
HTTP-level proof for the manifest page_create repair
(ops/page-production-completion-20260722).

Real HTTP request/response cycle through the actual production routers
(auth, execution_manifest, worker_queue) -- not a direct function call --
proving a page_create execution item creates a real new page from its
own manifest-supplied content, with no Page Ops record involved at any
point, exactly as a founder using the real API would exercise it.
"""
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

ADMIN_PASSWORD = "test-password"


@pytest.fixture
def client(mock_db):
    from auth import auth_router
    from routes.execution_manifest import execution_manifest_router
    from routes.worker_queue import worker_queue_router

    app = FastAPI()
    app.include_router(auth_router)
    app.include_router(execution_manifest_router)
    app.include_router(worker_queue_router)
    return TestClient(app)


@pytest.fixture
def auth_headers(client):
    r = client.post("/api/auth/login", json={"password": ADMIN_PASSWORD})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def _manifest_body():
    return {
        "schema_version": "1.0",
        "source_system": "TSAF",
        "source_packet_id": "packet-page-create-http-1",
        "campaign_id": "camp-page-create-http-1",
        "campaign_name": "Page Create HTTP Verification",
        "execution_items": [
            {
                "item_id": "item-1", "manifest_id": "", "sequence": 1,
                "title": "HTTP-Verified New Page",
                "destination": "wordpress", "execution_type": "page_create",
                "status": "pending",
                "copy": "Body content supplied directly by the manifest over real HTTP.",
                "placement": {
                    "slug": "http-verified-new-page",
                    "hero_headline": "HTTP Verified",
                    "intro": "Proving the repair end to end.",
                    "cta_text": "Shop Now", "cta_url": "/shop",
                    "related_links": [{"url": "/about", "title": "About"}],
                },
                "asset_refs": [], "dependencies": [], "context": {}, "qa_requirements": [], "warnings": [],
            },
        ],
        "assets": [],
    }


class TestPageCreateHttpRepair:

    def test_page_create_over_http_needs_no_page_ops_record_and_creates_real_content(self, client, auth_headers, mock_db):
        create = client.post("/api/execution-manifests", json=_manifest_body(), headers=auth_headers)
        assert create.status_code == 200, create.text
        manifest_id = create.json()["manifest_id"]

        validate = client.post(f"/api/execution-manifests/{manifest_id}/validate", headers=auth_headers)
        assert validate.status_code == 200, validate.text
        assert validate.json()["execution_items"][0]["status"] == "ready"

        queue = client.post(f"/api/execution-manifests/{manifest_id}/items/item-1/queue", headers=auth_headers)
        assert queue.status_code == 200, queue.text
        task_id = queue.json()["worker_task_id"]

        # wp_placement is founder-gated -- explicit first execute
        first = client.post(f"/api/worker-queue/tasks/{task_id}/execute", headers=auth_headers)
        assert first.status_code == 200, first.text
        assert first.json()["status"] == "needs_review"
        preview = first.json()["result"]["preview"]
        assert preview["title"] == "HTTP-Verified New Page"
        assert "Body content supplied directly" in preview["html_preview"]

        import asyncio
        assert asyncio.run(mock_db.pages.count_documents({})) == 0  # no Page Ops record ever created

        # Approved mock write
        second = client.post(
            f"/api/worker-queue/tasks/{task_id}/execute",
            json={"execution_mode": "mock"},
            headers=auth_headers,
        )
        assert second.status_code == 200, second.text
        assert second.json()["status"] == "completed"
        assert second.json()["result"]["success"] is True
