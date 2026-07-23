"""
Focused hardening tests for the OPS new-page (page_create) lane
(ops/page-production-completion-20260722 hardening).

Proves:
- page_create routes through automatic Rene QA before WP Placement
- a blocking Rene issue prevents WP Placement approval readiness
- passing QA allows the founder-gated dry-run placement
- Rene understands Flatsome output (button CTA, structured hero/intro/body)
- malformed / missing content still fails
- low-confidence inferred template requires explicit review; an explicit
  (or confirmed) template clears it
- the existing-page update path and write-safety protections are unchanged

Runs against the in-memory Mongo double (tests/conftest.py).
"""
import pytest

import services.execution_manifest as em
import services.worker_queue as wq

FAKE_USER = {"sub": "founder", "role": "admin"}


def _mpd(**overrides):
    data = {
        "title": "OPS Page Creation Proof",
        "slug": "ops-page-creation-proof",
        "page_type": "standard_content",
        "template_id": "standard_content",
        "hero_headline": "OPS Page Creation Proof",
        "intro": "This draft page verifies OPS can create a page from manifest content.",
        "copy": "The page-production lane carried this content through drafting and quality review.",
        "cta_text": "Return to Temporary Satisfaction",
        "cta_url": "https://temporarysatisfaction.com",
        "related_links": [{"url": "https://temporarysatisfaction.com", "title": "Home"}],
    }
    data.update(overrides)
    return data


def _rene_create_task(mpd=None, qa=None):
    data = _mpd(**(mpd or {}))
    return {"context": {
        "is_page_create": True,
        "manifest_page_data": data,
        "qa_requirements": qa or [],
        "related_links": data.get("related_links", []),
    }}


def _manifest(item):
    return {
        "manifest_id": None, "schema_version": "1.0", "source_system": "TSAF",
        "source_packet_id": "pkt-hardening", "campaign_id": "camp-hardening",
        "campaign_name": "Hardening", "execution_items": [item], "assets": [],
    }


def _page_create_item(item_id="item-1", template_id="standard_content", **overrides):
    placement = {
        "slug": "ops-page-creation-proof",
        "page_type": "standard_content",
        "hero_headline": "OPS Page Creation Proof",
        "intro": "This draft page verifies OPS can create a page from manifest content.",
        "cta_text": "Return to Temporary Satisfaction",
        "cta_url": "https://temporarysatisfaction.com",
        "related_links": [{"url": "https://temporarysatisfaction.com", "title": "Home"}],
        "publication_mode": "draft",
    }
    if template_id:
        placement["template_id"] = template_id
    if "placement" in overrides:
        placement.update(overrides.pop("placement"))
    item = {
        "item_id": item_id, "sequence": 1,
        "title": "OPS Page Creation Proof",
        "destination": "wordpress", "execution_type": "page_create",
        "status": "pending",
        "copy": "The page-production lane carried this content through drafting and quality review.",
        "qa_requirements": ["cta_required", "min_internal_links:1", "internal_only",
                            "required_sections:hero,intro,body", "seo_required"],
        "placement": placement,
        "asset_refs": [], "dependencies": [], "context": {}, "warnings": [],
    }
    item.update(overrides)
    return item


async def _queue(item):
    manifest = await em.create_manifest(_manifest(item))
    await em.run_validation(manifest["manifest_id"])
    result = await em.queue_execution_item(manifest["manifest_id"], item["item_id"], user=FAKE_USER)
    chain = await em.get_worker_chain(item["item_id"])
    return manifest, result, chain


# ================== ROUTING: page_create -> Rene ==================

class TestPageCreateRouting:

    def test_routing_sends_page_create_to_rene_qa_first(self):
        routing = em.determine_routing({"destination": "wordpress", "execution_type": "page_create"})
        assert routing["support"] == "supported_now"
        assert routing["worker"] == "rene"
        assert routing["task_type"] == "wp_content_qa"

    async def test_page_create_automatically_invokes_rene_then_wp_placement(self, mock_db):
        _, result, chain = await _queue(_page_create_item())
        assert result["worker"] == "rene" and result["task_type"] == "wp_content_qa"
        workers = [c["worker"] for c in chain]
        assert workers.count("rene") == 1
        assert "jenny" not in workers  # no Jenny drafting unless content missing
        rene = next(c for c in chain if c["worker"] == "rene")
        assert rene["result"]["passed"] is True
        wpp = next(c for c in chain if c["worker"] == "wp_placement")
        assert wpp["task_type"] == "wp_draft" and wpp["status"] == "queued"

    async def test_passing_qa_allows_dry_run_placement_with_token(self, mock_db):
        _, _, chain = await _queue(_page_create_item())
        wpp = next(c for c in chain if c["worker"] == "wp_placement")
        executed = await wq.execute_worker_task(wpp["task_id"], user=FAKE_USER)
        assert executed["status"] == "needs_review"
        assert executed["result"]["approval_token"]
        tok = await mock_db.wp_write_approvals.find_one({"token": executed["result"]["approval_token"]}, {"_id": 0})
        assert tok["consumed"] is False and tok["publication_mode"] == "draft"

    async def test_blocking_rene_issue_prevents_wp_placement_readiness(self, mock_db):
        item = _page_create_item(qa_requirements=["required_sections:pricing,warranty"])
        _, _, chain = await _queue(item)
        rene = next(c for c in chain if c["worker"] == "rene")
        assert rene["result"]["passed"] is False
        assert not any(c["worker"] == "wp_placement" for c in chain)


# ================== RENE UNDERSTANDS FLATSOME OUTPUT ==================

class TestReneUnderstandsFlatsome:

    async def test_flatsome_button_satisfies_cta_required(self, mock_db):
        task = _rene_create_task(qa=["cta_required"])
        result = await wq._rene_qa_wp_content(task)
        assert result["passed"] is True  # [button ...] shortcode counts as a CTA

    async def test_cta_required_still_fails_when_no_cta_anywhere(self, mock_db):
        task = _rene_create_task(mpd={"cta_text": "", "cta_url": ""}, qa=["cta_required"])
        result = await wq._rene_qa_wp_content(task)
        assert result["passed"] is False
        assert "CTA" in result["reason"]

    async def test_structured_hero_intro_body_satisfy_required_sections(self, mock_db):
        task = _rene_create_task(qa=["required_sections:hero,intro,body"])
        result = await wq._rene_qa_wp_content(task)
        assert result["passed"] is True

    async def test_missing_body_still_fails_required_sections(self, mock_db):
        task = _rene_create_task(mpd={"copy": "", "body_section_1": None},
                                 qa=["required_sections:hero,intro,body"])
        result = await wq._rene_qa_wp_content(task)
        assert result["passed"] is False
        assert "body" in result["reason"].lower()

    async def test_entirely_missing_content_fails(self, mock_db):
        task = _rene_create_task(mpd={
            "hero_headline": "", "title": "", "intro": "", "copy": "",
            "cta_text": "", "cta_url": "", "related_links": [],
        })
        result = await wq._rene_qa_wp_content(task)
        assert result["passed"] is False
        assert "No drafted HTML" in result["reason"]

    async def test_seo_required_is_warning_not_blocking(self, mock_db):
        task = _rene_create_task(qa=["seo_required"])
        result = await wq._rene_qa_wp_content(task)
        assert result["passed"] is True
        assert any("SEO title" in w for w in result["warnings"])

    async def test_internal_only_and_min_links_from_related_links(self, mock_db):
        task = _rene_create_task(qa=["min_internal_links:1", "internal_only"])
        result = await wq._rene_qa_wp_content(task)
        assert result["passed"] is True


# ================== TEMPLATE RESOLUTION / REVIEW ==================

class TestTemplateReview:

    def test_explicit_template_id_is_preserved_and_needs_no_review(self):
        r = wq.resolve_manifest_template({"template_id": "standard_content", "title": "x"})
        assert r["template_id"] == "standard_content"
        assert r["explicit"] is True and r["needs_review"] is False

    def test_low_confidence_inference_needs_review(self):
        r = wq.resolve_manifest_template({"title": "Quarterly Notes", "intro": "notes", "copy": "general notes"})
        assert r["explicit"] is False
        assert r["needs_review"] is True

    def test_template_confirmed_clears_review_without_explicit_id(self):
        r = wq.resolve_manifest_template({"title": "Quarterly Notes", "copy": "general notes", "template_confirmed": True})
        assert r["needs_review"] is False

    async def test_low_confidence_template_blocks_page_create(self, mock_db):
        # No template_id and no strong keywords -> low confidence -> must review.
        item = _page_create_item(template_id=None, placement={
            "hero_headline": "Quarterly Update", "intro": "Some notes.",
        }, title="Quarterly Update Notes",
            copy="General internal notes without shop keywords.",
            qa_requirements=[])
        _, _, chain = await _queue(item)
        rene = next(c for c in chain if c["worker"] == "rene")
        assert rene["result"]["passed"] is False
        assert "template" in rene["result"]["reason"].lower()
        assert not any(c["worker"] == "wp_placement" for c in chain)

    async def test_explicit_standard_content_clears_review(self, mock_db):
        item = _page_create_item(template_id="standard_content", title="Quarterly Update Notes",
                                 copy="General internal notes without shop keywords.",
                                 qa_requirements=[])
        _, _, chain = await _queue(item)
        rene = next(c for c in chain if c["worker"] == "rene")
        assert rene["result"]["passed"] is True
        assert any(c["worker"] == "wp_placement" for c in chain)

    async def test_create_path_refuses_token_when_template_unreviewed(self, mock_db):
        """Defense in depth: the create dry-run issues NO token for an unreviewed low-confidence template."""
        task = await wq.create_worker_task(
            source_module="execution_manifest", source_item_id="item-x",
            worker="wp_placement", task_type="wp_draft",
            context={"manifest_page_data": {
                "title": "Quarterly Update Notes", "slug": "q-notes",
                "hero_headline": "Quarterly Update", "intro": "Notes.",
                "copy": "General internal notes.",
            }},
        )
        executed = await wq.execute_worker_task(task["id"], user=FAKE_USER)
        assert executed["status"] == "needs_review"
        assert "template" in executed["result"]["reason"].lower()
        assert not executed["result"].get("approval_token")


# ================== EXISTING PATHS UNCHANGED ==================

class TestExistingPathsUnchanged:

    async def test_update_path_still_requires_target_page_id(self, mock_db):
        """Non-page_create (update) QA must still enforce the target-page-ID basic."""
        task = {"context": {
            "drafted_html": "<p>Solid update content with an <a href=\"/shop\">Shop</a> link.</p>",
            "page_name": "Existing",
        }}
        result = await wq._rene_qa_wp_content(task)
        assert result["passed"] is False
        assert "No target page ID" in result["reason"]

    async def test_update_path_passes_with_target_and_clean_content(self, mock_db):
        task = {"context": {
            "drafted_html": "<p>Solid update content with an <a href=\"/shop\">Shop</a> link.</p>",
            "page_name": "Existing", "page_id": "page-1", "wp_page_id": "354999",
        }}
        result = await wq._rene_qa_wp_content(task)
        assert result["passed"] is True

    async def test_page_ops_sourced_create_path_unchanged(self, mock_db):
        await mock_db.pages.insert_one({
            "id": "page-legacy-2", "page_name": "Legacy", "page_type": "trust",
            "slug": "legacy", "generated_content": "[section]Legacy content works.[/section]",
        })
        task = await wq.create_worker_task(
            source_module="page_ops", source_item_id="page-legacy-2",
            worker="wp_placement", task_type="wp_draft",
        )
        assert task["status"] == "queued"
        result = await wq.execute_worker_task(task["id"], user=FAKE_USER)
        assert result["status"] == "needs_review"
        assert "Legacy content works" in result["result"]["preview"]["html_preview"]
