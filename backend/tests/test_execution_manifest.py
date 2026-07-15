"""
Execution Manifest Layer — Phase 1 tests
(ops/execution-manifest-phase-1-20260714, built on 3b47c8a1151d28026f8eacbf3ef5d5dd58fdc9ae)

Executed for real against the in-memory Mongo double (see tests/conftest.py).
Covers the required test list from the build request, including the
mandatory in-process proof: Execution Manifest -> WordPress update
execution item -> Jenny wp_content_draft task created -> routing continues
to Rene -> WP Placement remains founder-gated.
"""
import pytest

import services.execution_manifest as em

FAKE_USER = {"sub": "founder", "role": "admin"}


def _wp_item(item_id="item-1", copy="Verified: manifest-driven content.", **overrides):
    item = {
        "item_id": item_id,
        "manifest_id": "",  # filled in by create_manifest
        "sequence": 1,
        "title": "Update trust page",
        "description": "Add a verification section",
        "content_type": "section",
        "destination": "wordpress",
        "channel": None,
        "platform": None,
        "execution_type": "content_draft",
        "recommended_worker": None,
        "task_type": None,
        "requires_founder_approval": True,
        "status": "pending",
        "priority": "normal",
        "due_at": None,
        "asset_refs": [],
        "copy": copy,
        "instructions": None,
        "placement": {"page_id": "page-em-1", "wp_page_id": "354951"},
        "compliance_notes": None,
        "qa_requirements": [],
        "dependencies": [],
        "context": {},
        "worker_task_id": None,
        "result": {},
        "warnings": [],
    }
    item.update(overrides)
    return item


def _manifest_payload(manifest_id=None, items=None, assets=None, **overrides):
    payload = {
        "manifest_id": manifest_id,
        "schema_version": "1.0",
        "source_system": "TSAF",
        "source_packet_id": "packet-abc-123",
        "source_packet_type": "campaign",
        "campaign_id": "camp-001",
        "campaign_name": "Confidence Content Batch 01",
        "brand_id": "ts",
        "brand_name": "Temporary Satisfaction",
        "priority": "normal",
        "created_by": "tsaf",
        "notes": "test manifest",
        "execution_items": items if items is not None else [_wp_item()],
        "assets": assets or [],
        "metadata": {},
    }
    payload.update(overrides)
    return payload


async def _seed_wp_page(mock_db, page_id="page-em-1", wp_page_id="354951"):
    await mock_db.pages.insert_one({
        "id": page_id, "page_name": "Trust Page", "page_type": "trust",
        "slug": "trust-page",
        "generated_content": "[section]Original content.[/section]",
        "wp_page_id": wp_page_id,
    })
    await mock_db.wp_mock_pages.insert_one({
        "id": wp_page_id, "wp_id": int(wp_page_id), "title": "Trust Page",
        "slug": "trust-page", "content": "[section]Original content.[/section]",
        "status": "draft", "seo_title": "", "meta_description": "",
        "link": "https://example.test/trust-page",
        "created_at": "now", "updated_at": "now", "mock": True,
    })


# ================== 1-2: CREATION ==================

class TestManifestCreation:

    async def test_valid_manifest_creation(self, mock_db):
        manifest = await em.create_manifest(_manifest_payload())
        assert manifest["manifest_id"]
        assert manifest["status"] == "received"
        assert len(manifest["execution_items"]) == 1
        assert manifest["execution_items"][0]["manifest_id"] == manifest["manifest_id"]

    async def test_duplicate_manifest_rejection(self, mock_db):
        await em.create_manifest(_manifest_payload(manifest_id="man-dup-1"))
        with pytest.raises(em.ManifestValidationError, match="already exists"):
            await em.create_manifest(_manifest_payload(manifest_id="man-dup-1"))


# ================== 3: INVALID MANIFEST ==================

class TestManifestValidation:

    async def test_invalid_manifest_missing_fields_rejected(self, mock_db):
        manifest = await em.create_manifest(_manifest_payload())
        # Corrupt it post-creation to simulate a bad manifest reaching validation
        await mock_db.execution_manifests.update_one(
            {"manifest_id": manifest["manifest_id"]},
            {"$set": {"schema_version": "", "source_system": "", "execution_items": []}},
        )
        result = await em.run_validation(manifest["manifest_id"])
        assert result["status"] == "needs_review"
        assert any("schema_version" in e for e in result["errors"])
        assert any("source_system" in e for e in result["errors"])
        assert any("at least one execution item" in e for e in result["errors"])

    async def test_duplicate_execution_item_id_rejection(self, mock_db):
        items = [_wp_item(item_id="dup"), _wp_item(item_id="dup", copy="second")]
        manifest = await em.create_manifest(_manifest_payload(items=items))
        result = await em.run_validation(manifest["manifest_id"])
        assert any("duplicate execution item_id" in e for e in result["errors"])
        assert result["status"] == "needs_review"

    async def test_missing_asset_reference_rejection(self, mock_db):
        item = _wp_item(asset_refs=["asset-does-not-exist"])
        manifest = await em.create_manifest(_manifest_payload(items=[item]))
        result = await em.run_validation(manifest["manifest_id"])
        assert any("asset_ref" in e and "not found" in e for e in result["errors"])

    async def test_valid_asset_reference_passes(self, mock_db):
        item = _wp_item(asset_refs=["asset-1"])
        assets = [{"asset_id": "asset-1", "type": "image", "url": "https://example.test/a.jpg"}]
        manifest = await em.create_manifest(_manifest_payload(items=[item], assets=assets))
        result = await em.run_validation(manifest["manifest_id"])
        assert not any("asset_ref" in e for e in result["errors"])

    async def test_invalid_dependency_rejection(self, mock_db):
        item = _wp_item(dependencies=["item-does-not-exist"])
        manifest = await em.create_manifest(_manifest_payload(items=[item]))
        result = await em.run_validation(manifest["manifest_id"])
        assert any("does not reference a valid item_id" in e for e in result["errors"])

    async def test_circular_dependency_rejection(self, mock_db):
        item_a = _wp_item(item_id="a", dependencies=["b"])
        item_b = _wp_item(item_id="b", copy="b content", dependencies=["a"])
        manifest = await em.create_manifest(_manifest_payload(items=[item_a, item_b]))
        result = await em.run_validation(manifest["manifest_id"])
        assert any("circular dependency" in e for e in result["errors"])

    async def test_valid_manifest_validates_clean(self, mock_db, monkeypatch):
        manifest = await em.create_manifest(_manifest_payload())
        result = await em.run_validation(manifest["manifest_id"])
        assert result["errors"] == []
        assert result["status"] == "validated"
        assert result["execution_items"][0]["status"] == "ready"
        assert result["execution_items"][0]["recommended_worker"] == "jenny"


# ================== WordPress safety cannot be bypassed by a manifest ==================

class TestManifestCannotBypassWpSafety:

    async def test_manifest_context_cannot_set_execution_mode_live(self, mock_db):
        item = _wp_item(context={"execution_mode": "live"})
        manifest = await em.create_manifest(_manifest_payload(items=[item]))
        result = await em.run_validation(manifest["manifest_id"])
        assert any("execution_mode" in e and "context may not set" in e for e in result["errors"])
        assert result["status"] == "needs_review"

    async def test_manifest_context_cannot_set_approval_token(self, mock_db):
        item = _wp_item(context={"approval_token": "forged-token"})
        manifest = await em.create_manifest(_manifest_payload(items=[item]))
        result = await em.run_validation(manifest["manifest_id"])
        assert any("approval_token" in e and "context may not set" in e for e in result["errors"])


# ================== 8-9: ROUTING + CHAIN INTEGRITY (the required proof) ==================

class TestManifestToWorkerChainProof:

    async def test_wordpress_update_routing_creates_jenny_task(self, mock_db):
        await _seed_wp_page(mock_db)
        manifest = await em.create_manifest(_manifest_payload())
        await em.run_validation(manifest["manifest_id"])

        result = await em.queue_execution_item(manifest["manifest_id"], "item-1", user=FAKE_USER)
        assert result["queued"] is True
        assert result["worker"] == "jenny"
        assert result["task_type"] == "wp_content_draft"

        task = await mock_db.worker_tasks.find_one({"id": result["worker_task_id"]}, {"_id": 0})
        assert task["source_module"] == "execution_manifest"
        assert task["status"] == "completed"  # Jenny auto-executes and has no LLM dependency on this path
        assert task["context"]["manifest_id"] == manifest["manifest_id"]
        assert task["context"]["execution_item_id"] == "item-1"
        assert task["context"]["source_packet_id"] == "packet-abc-123"
        assert task["context"]["campaign_id"] == "camp-001"
        assert task["context"]["destination"] == "wordpress"
        assert task["context"]["execution_type"] == "content_draft"

    async def test_full_chain_manifest_to_wp_placement_needs_review_then_approved_write(self, mock_db):
        """
        THE required proof:
        Execution Manifest -> WordPress update execution item -> Jenny
        wp_content_draft task created -> routing continues to Rene ->
        WP Placement created and remains founder-gated (does not
        auto-execute) -> first execute -> needs_review (dry-run,
        no write) -> approved second execute -> exactly one write.
        """
        await _seed_wp_page(mock_db)
        manifest = await em.create_manifest(_manifest_payload())
        await em.run_validation(manifest["manifest_id"])
        result = await em.queue_execution_item(manifest["manifest_id"], "item-1", user=FAKE_USER)
        jenny_task_id = result["worker_task_id"]

        jenny_task = await mock_db.worker_tasks.find_one({"id": jenny_task_id}, {"_id": 0})
        assert jenny_task["status"] == "completed"

        # Routing must have continued to Rene automatically (Jenny is auto_execute)
        rene_task = await mock_db.worker_tasks.find_one(
            {"worker": "rene", "source_item_id": "item-1"}, {"_id": 0}
        )
        assert rene_task is not None, "Routing must continue Jenny -> Rene even when the task originated from a manifest"
        assert rene_task["status"] == "completed"
        assert rene_task["result"]["passed"] is True

        # Routing must have continued to WP Placement, and it must NOT auto-execute
        wp_task = await mock_db.worker_tasks.find_one(
            {"worker": "wp_placement", "source_item_id": "item-1"}, {"_id": 0}
        )
        assert wp_task is not None, "Routing must continue Rene -> WP Placement even when the task originated from a manifest"
        assert wp_task["status"] == "queued", "WP Placement must remain founder-gated -- it must NOT auto-execute"
        assert wp_task["founder_action_needed"] is True

        # First execute: dry-run default, needs_review, NO write
        import services.worker_queue as wq
        first = await wq.execute_worker_task(wp_task["id"], user=FAKE_USER)
        assert first["status"] == "needs_review"
        assert first["result"]["needs_review"] is True
        token = first["result"]["approval_token"]
        assert token

        page_before = await mock_db.wp_mock_pages.find_one({"id": "354951"})
        assert "manifest-driven content" not in page_before["content"]

        # Approved second execute (mock mode -- no real credentials in this sandbox)
        await mock_db.worker_tasks.update_one(
            {"id": wp_task["id"]}, {"$set": {"status": "queued", "context.execution_mode": "mock"}}
        )
        second = await wq.execute_worker_task(wp_task["id"], user=FAKE_USER)
        assert second["status"] == "completed"
        assert second["result"]["success"] is True

        page_after = await mock_db.wp_mock_pages.find_one({"id": "354951"})
        assert "manifest-driven content" in page_after["content"]


# ================== 10: UNSUPPORTED DESTINATION ==================

class TestUnsupportedDestination:

    async def test_unsupported_destination_does_not_fake_execution(self, mock_db):
        item = _wp_item(item_id="item-metricool", destination="metricool", execution_type="social_post", copy="A post")
        manifest = await em.create_manifest(_manifest_payload(items=[item]))
        result = await em.run_validation(manifest["manifest_id"])
        assert result["execution_items"][0]["status"] == "blocked"
        assert any("connector unavailable" in w for w in result["execution_items"][0]["warnings"])

        queue_result = await em.queue_execution_item(manifest["manifest_id"], "item-metricool", user=FAKE_USER)
        assert queue_result["queued"] is False
        assert await mock_db.worker_tasks.count_documents({"source_item_id": "item-metricool"}) == 0

    async def test_manual_destination_marked_manual_required(self, mock_db):
        item = _wp_item(item_id="item-manual", destination="manual", execution_type="manual_task", copy="Do this by hand")
        manifest = await em.create_manifest(_manifest_payload(items=[item]))
        result = await em.run_validation(manifest["manifest_id"])
        assert result["execution_items"][0]["status"] == "blocked"
        assert any("manual execution required" in w for w in result["execution_items"][0]["warnings"])

    async def test_unrecognized_destination_needs_review(self, mock_db):
        item = _wp_item(item_id="item-unknown", destination="carrier_pigeon", execution_type="deliver", copy="fly")
        manifest = await em.create_manifest(_manifest_payload(items=[item]))
        result = await em.run_validation(manifest["manifest_id"])
        assert any("not a recognized destination label" in e for e in result["errors"])


# ================== 11: DUPLICATE QUEUE PROTECTION ==================

class TestDuplicateQueueProtection:

    async def test_duplicate_queue_request_does_not_duplicate_worker_task(self, mock_db):
        await _seed_wp_page(mock_db)
        manifest = await em.create_manifest(_manifest_payload())
        await em.run_validation(manifest["manifest_id"])

        first = await em.queue_execution_item(manifest["manifest_id"], "item-1", user=FAKE_USER)
        assert first["queued"] is True

        second = await em.queue_execution_item(manifest["manifest_id"], "item-1", user=FAKE_USER)
        assert second["queued"] is False
        assert second["already_queued"] is True
        assert second["worker_task_id"] == first["worker_task_id"]

        # source_item_id is shared by every task in the Jenny->Rene->WP
        # Placement chain (that's how routing finds "the same item"), so
        # duplicate-queue protection must be checked specifically -- exactly
        # one Jenny task should exist for this item, not a blanket count of
        # every task sharing that source_item_id.
        jenny_count = await mock_db.worker_tasks.count_documents({"source_item_id": "item-1", "worker": "jenny"})
        assert jenny_count == 1


# ================== 12: FOUNDER GATING PRESERVED ==================

class TestFounderGating:

    async def test_founder_gated_tasks_remain_founder_gated(self, mock_db):
        await _seed_wp_page(mock_db)
        manifest = await em.create_manifest(_manifest_payload())
        await em.run_validation(manifest["manifest_id"])
        await em.queue_execution_item(manifest["manifest_id"], "item-1", user=FAKE_USER)

        wp_task = await mock_db.worker_tasks.find_one({"worker": "wp_placement", "source_item_id": "item-1"}, {"_id": 0})
        assert wp_task["auto_execute"] is False
        assert wp_task["founder_action_needed"] is True
        assert wp_task["status"] == "queued"


# ================== 14: TRACEABILITY ==================

class TestTraceability:

    async def test_traceability_manifest_to_worker_task(self, mock_db):
        await _seed_wp_page(mock_db)
        manifest = await em.create_manifest(_manifest_payload())
        await em.run_validation(manifest["manifest_id"])
        queued = await em.queue_execution_item(manifest["manifest_id"], "item-1", user=FAKE_USER)

        trace = await em.get_trace(manifest["manifest_id"])
        assert trace["manifest_id"] == manifest["manifest_id"]
        assert len(trace["items"]) == 1
        traced_item = trace["items"][0]
        assert traced_item["item_id"] == "item-1"
        # Top-level fields reflect the chain's LAST/current task (repaired
        # behavior -- previously this was always Jenny's own task, even
        # after the chain moved on to Rene/WP Placement).
        assert traced_item["worker"] == "wp_placement"
        assert traced_item["task_status"] == "queued"
        # Jenny is still represented -- via the chain, not the top-level fields.
        chain_workers = [t["worker"] for t in traced_item["worker_chain"]]
        assert chain_workers == ["jenny", "rene", "wp_placement"]
        assert traced_item["worker_chain"][0]["status"] == "completed"

        # queue_execution_item's own return value still refers to the task
        # IT created (Jenny) -- unchanged meaning, used only for the
        # duplicate-queue check.
        assert queued["worker"] == "jenny"

        # And the manifest itself stores worker_task_id (still Jenny's, per
        # the documented backward-compatibility choice) on the item
        stored = await em.get_manifest(manifest["manifest_id"])
        stored_item = next(i for i in stored["execution_items"] if i["item_id"] == "item-1")
        assert stored_item["worker_task_id"] == queued["worker_task_id"]
        # But the item's overall status reflects the chain's current step,
        # not just Jenny's completion -- this is the actual repair.
        assert stored_item["status"] == "queued"


class TestTraceRepairWorkerChain:
    """
    Repair (ops/execution-manifest-phase-2-workspace-20260714, repair pass):
    real-browser review found the trace endpoint showed only the initial
    Jenny task even after Rene and WP Placement had been created by the
    existing routing chain. These tests prove the fix directly.
    """

    async def test_trace_returns_full_jenny_rene_wp_placement_chain(self, mock_db):
        await _seed_wp_page(mock_db)
        manifest = await em.create_manifest(_manifest_payload())
        await em.run_validation(manifest["manifest_id"])
        await em.queue_execution_item(manifest["manifest_id"], "item-1", user=FAKE_USER)

        trace = await em.get_trace(manifest["manifest_id"])
        chain = trace["items"][0]["worker_chain"]
        assert len(chain) == 3
        workers = [t["worker"] for t in chain]
        assert workers == ["jenny", "rene", "wp_placement"]
        # Jenny and Rene auto-executed and completed; WP Placement remains
        # founder-gated and queued -- exactly the real verified chain.
        assert chain[0]["status"] == "completed"
        assert chain[1]["status"] == "completed"
        assert chain[2]["status"] == "queued"
        assert chain[2]["auto_execute"] is False
        assert chain[2]["founder_action_needed"] is True
        # Required fields present on every chain entry
        for task in chain:
            for field in ("task_id", "worker", "worker_name", "task_type", "status",
                          "auto_execute", "founder_action_needed", "next_action",
                          "result", "warnings", "created_at", "started_at", "completed_at"):
                assert field in task

    async def test_chain_order_is_deterministic(self, mock_db):
        await _seed_wp_page(mock_db)
        manifest = await em.create_manifest(_manifest_payload())
        await em.run_validation(manifest["manifest_id"])
        await em.queue_execution_item(manifest["manifest_id"], "item-1", user=FAKE_USER)

        # Fetch twice -- order must not depend on query/storage happenstance.
        chain_a = await em.get_worker_chain("item-1")
        chain_b = await em.get_worker_chain("item-1")
        assert [t["worker"] for t in chain_a] == ["jenny", "rene", "wp_placement"]
        assert [t["task_id"] for t in chain_a] == [t["task_id"] for t in chain_b]

    async def test_trace_omits_nonexistent_workers_never_invents_tasks(self, mock_db):
        """An item that hasn't been queued at all must show an empty chain,
        never a fabricated Jenny/Rene/WP Placement placeholder."""
        manifest = await em.create_manifest(_manifest_payload())
        await em.run_validation(manifest["manifest_id"])
        # Not queued -- item stays "ready", no worker_tasks exist for it.
        trace = await em.get_trace(manifest["manifest_id"])
        assert trace["items"][0]["worker_chain"] == []

    async def test_blocked_metricool_item_has_empty_chain_never_invented(self, mock_db):
        item = _wp_item(item_id="item-metricool", destination="metricool", execution_type="social_post", copy="A post")
        manifest = await em.create_manifest(_manifest_payload(items=[item]))
        await em.run_validation(manifest["manifest_id"])
        trace = await em.get_trace(manifest["manifest_id"])
        assert trace["items"][0]["worker_chain"] == []

    async def test_no_duplicate_worker_tasks_created_by_chain_aggregation(self, mock_db):
        """Aggregating the full chain must not itself create any task, and
        re-queueing must still be refused as a duplicate."""
        await _seed_wp_page(mock_db)
        manifest = await em.create_manifest(_manifest_payload())
        await em.run_validation(manifest["manifest_id"])
        await em.queue_execution_item(manifest["manifest_id"], "item-1", user=FAKE_USER)

        count_before = await mock_db.worker_tasks.count_documents({"source_item_id": "item-1"})
        await em.get_trace(manifest["manifest_id"])  # must be read-only
        count_after = await mock_db.worker_tasks.count_documents({"source_item_id": "item-1"})
        assert count_before == count_after == 3

        second = await em.queue_execution_item(manifest["manifest_id"], "item-1", user=FAKE_USER)
        assert second["already_queued"] is True
        count_final = await mock_db.worker_tasks.count_documents({"source_item_id": "item-1"})
        assert count_final == 3
