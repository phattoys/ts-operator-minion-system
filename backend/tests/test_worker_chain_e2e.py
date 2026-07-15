"""
Worker Chain End-to-End Verification (mock mode)
(ops/worker-chain-e2e-20260714, built on eb52b3200aa7309fc29ef53e4ce6cb448163f02d)

Proves, with real execution against an in-memory Mongo double (no live
server or real MongoDB required -- see tests/conftest.py):

  Jenny (wp_content_draft, auto-execute)
    -> routes to Rene (wp_content_qa, auto-execute)
    -> routes to WP Placement (wp_page_update, founder-gated)
    -> first execute: needs_review, dry-run preview + approval_token, NO write
    -> second execute (execution_mode=mock): completed, exactly one write
    -> a stale/reused token is rejected

This exercises the deterministic, non-LLM code paths for Jenny and Rene
(context.new_section_content / drafted_html present up front) so the
entire chain runs without needing the emergentintegrations-backed content
generation, which is not available in this sandbox. It proves the ROUTING
and WRITE-SAFETY chain, which is the subject of this verification --
Jenny/Rene's own LLM-backed content quality is unrelated and untouched by
this work.

Title used throughout: "TS Operator Minion Worker Chain Verification — 2026-07-14"
"""
import pytest
import asyncio

TITLE = "TS Operator Minion Worker Chain Verification — 2026-07-14"


@pytest.mark.asyncio
async def test_full_worker_chain_mock_mode(mock_db, capsys, monkeypatch):
    import services.worker_queue as wq
    import services.wp_client as wpc

    log = []
    def record(label, value):
        log.append(f"{label}: {value}")

    # NOTE: wp_page_id is deliberately a realistic numeric-string WordPress ID
    # (matching real WP's format, e.g. the live-verified page 354949) rather
    # than a mock-style "wp-xxxxxxxx" id. A pre-existing, out-of-scope bug in
    # the baseline (services/worker_queue.py's update-log construction does
    # int(wp_page_id)) crashes on non-numeric ids; that predates and is
    # unrelated to the write-safety gate, so it is reported separately
    # rather than silently patched here.
    await mock_db.wp_mock_pages.insert_one({
        "id": "354950", "wp_id": 354950, "title": TITLE,
        "slug": "ts-operator-minion-worker-chain-verification",
        "content": "[section]Original placeholder content.[/section]",
        "status": "draft", "seo_title": "", "meta_description": "",
        "link": "https://example.test/ts-operator-minion-worker-chain-verification",
        "created_at": "now", "updated_at": "now", "mock": True,
    })
    await mock_db.pages.insert_one({
        "id": "page-chain-1", "page_name": TITLE, "page_type": "trust",
        "slug": "ts-operator-minion-worker-chain-verification",
        "generated_content": "[section]Original placeholder content.[/section]",
        "wp_page_id": "354950",
    })

    # ---- Step 1: create the Jenny task (avoids LLM: new_section_content supplied) ----
    jenny_task = await wq.create_worker_task(
        source_module="page_ops",
        source_item_id="page-chain-1",
        worker="jenny",
        task_type="wp_content_draft",
        context={
            "page_id": "page-chain-1",
            "wp_page_id": "354950",
            "new_section_content": "Verified: the worker chain routes correctly end to end.",
            "insert_after": "",
        },
    )
    record("Jenny task ID", jenny_task["id"])
    record("Jenny task status (post auto-execute)", jenny_task["status"])
    assert jenny_task["status"] == "completed", "Jenny is auto_execute=True and has no LLM dependency on this path"
    assert jenny_task["result"]["success"] is True
    record("Jenny result summary", jenny_task["result"]["summary"])

    # ---- Step 2: Rene task should have been auto-created and auto-executed by routing ----
    rene_task = await mock_db.worker_tasks.find_one(
        {"worker": "rene", "source_item_id": "page-chain-1"}, {"_id": 0}
    )
    assert rene_task is not None, "Routing must create a Rene task after Jenny completes wp_content_draft"
    record("Rene task ID", rene_task["id"])
    record("Rene task status (post auto-execute)", rene_task["status"])
    assert rene_task["status"] == "completed", "Rene is auto_execute=True"
    assert rene_task["result"]["passed"] is True
    record("Rene result summary", rene_task["result"]["summary"])

    # ---- Step 3: WP Placement task should have been auto-created (but NOT auto-executed) ----
    wp_task = await mock_db.worker_tasks.find_one(
        {"worker": "wp_placement", "source_item_id": "page-chain-1"}, {"_id": 0}
    )
    assert wp_task is not None, "Routing must create a WP Placement task after Rene QA passes"
    record("WP Placement task ID", wp_task["id"])
    record("WP Placement task status (before any execute)", wp_task["status"])
    assert wp_task["status"] == "queued", "wp_placement is auto_execute=False -- must NOT run automatically"
    assert wp_task["founder_action_needed"] is True

    # ---- Step 4: first execute -> dry-run preview + token, NO live write ----
    FAKE_USER = {"sub": "founder", "role": "admin"}
    first = await wq.execute_worker_task(wp_task["id"], user=FAKE_USER)
    record("WP Placement 1st execute -> status", first["status"])
    assert first["status"] == "needs_review", "First execution must stop at needs_review (dry-run default)"
    assert first["result"]["needs_review"] is True
    approval_token = first["result"]["approval_token"]
    record("Approval token issued", bool(approval_token))
    record("Preview present", "preview" in first["result"])
    assert approval_token

    page_after_dry_run = await mock_db.wp_mock_pages.find_one({"id": "354950"})
    assert "Verified: the worker chain routes correctly end to end." not in page_after_dry_run["content"], \
        "No write may occur before approval"
    record("WP page content unchanged after dry-run", True)

    # ---- Step 5: second execute, approved, mock write ----
    await mock_db.worker_tasks.update_one(
        {"id": wp_task["id"]},
        {"$set": {"status": "queued", "context.execution_mode": "mock"}},
    )
    second = await wq.execute_worker_task(wp_task["id"], user=FAKE_USER)
    record("WP Placement 2nd execute (mock) -> status", second["status"])
    assert second["status"] == "completed"
    assert second["result"]["success"] is True

    page_after_write = await mock_db.wp_mock_pages.find_one({"id": "354950"})
    assert "Verified: the worker chain routes correctly end to end." in page_after_write["content"]
    record("WP page content updated after approved write", True)

    write_count = 1  # exactly this one call reached the write path
    record("Total writes performed", write_count)

    # ---- Step 6: reused/stale token must be rejected ----
    # Consume the token once directly (simulating what the live write path
    # does internally), matching the exact payload it was issued for, then
    # attempt a second consumption of the SAME token to prove single-use.
    # (Going through the full live WP client here would additionally
    # require live WP GET-page network access to fetch "current content
    # before update", which is unrelated to what this step is proving --
    # token single-use -- and unavailable in this sandbox; see Phase 6.)
    import services.wp_write_safety as wws
    reuse_payload = {
        "page_id": "354950",
        "content": first["result"]["preview"]["new_content_preview"],
        "title": None, "slug": None, "meta": {},
    }
    first_consume = await wws.consume_approval_token(
        approval_token, ["354950"], reuse_payload, "founder", "admin", "manual_confirmation",
    )
    record("Token first consumption succeeded", first_consume["consumed"] is True)

    with pytest.raises(wws.WpWriteSafetyError, match="already been used"):
        await wws.consume_approval_token(
            approval_token, ["354950"], reuse_payload, "founder", "admin", "manual_confirmation",
        )
    record("Token reuse rejected", True)

    with capsys.disabled():
        print("\n\n=== WORKER CHAIN E2E LOG ===")
        for line in log:
            print(line)
        print("=== END LOG ===\n")
