"""
OPS Page-Production Completion — tests
(ops/page-production-completion-20260722, built on 045db680aa5741fdea366105240eccbedb3f2481)

Covers the three narrow repairs identified by the practical-completion
audit: manifest-sourced page_create (no Page Ops record required),
extended Rene WP content QA (meaningful minimum checks, requirement-
driven), and the maintainable internal-link map in services/menu_mapper.py.

Executed for real against the in-memory Mongo double (see tests/conftest.py).
"""
import pytest

import services.execution_manifest as em
import services.worker_queue as wq

FAKE_USER = {"sub": "founder", "role": "admin"}


def _page_create_item(item_id="item-1", **overrides):
    item = {
        "item_id": item_id, "manifest_id": "", "sequence": 1,
        "title": "New Trust Page From Manifest",
        "description": "A brand-new page built entirely from manifest data",
        "destination": "wordpress", "execution_type": "page_create",
        "status": "pending", "priority": "normal",
        "copy": "This is the main body content supplied directly by the manifest.",
        "placement": {
            "slug": "new-trust-page",
            "hero_headline": "Welcome to Temporary Satisfaction",
            "intro": "A short intro paragraph.",
            "cta_text": "Shop Now",
            "cta_url": "/shop",
            "related_links": [{"url": "/about", "title": "About Us"}],
            "publication_mode": "draft",
        },
        "asset_refs": [], "dependencies": [], "context": {},
        "qa_requirements": [], "warnings": [],
    }
    item.update(overrides)
    return item


def _manifest_payload(items=None, manifest_id=None):
    return {
        "manifest_id": manifest_id,
        "schema_version": "1.0",
        "source_system": "TSAF",
        "source_packet_id": "packet-page-create-1",
        "campaign_id": "camp-page-create-1",
        "campaign_name": "Page Production Completion Verification",
        "execution_items": items,
        "assets": [],
    }


# ================== 1. MANIFEST PAGE_CREATE REPAIR ==================

class TestManifestPageCreate:

    async def _queue(self, item):
        manifest = await em.create_manifest(_manifest_payload(items=[item]))
        await em.run_validation(manifest["manifest_id"])
        result = await em.queue_execution_item(manifest["manifest_id"], item["item_id"], user=FAKE_USER)
        chain = await em.get_worker_chain(item["item_id"])
        return manifest, result, chain

    async def test_page_create_auto_invokes_rene_then_founder_gated_wp_placement(self, mock_db):
        """page_create runs Rene QA FIRST; on pass it hands off to a founder-gated WP Placement create."""
        manifest, result, chain = await self._queue(_page_create_item())
        assert result["worker"] == "rene"
        assert result["task_type"] == "wp_content_qa"

        workers = [c["worker"] for c in chain]
        assert "rene" in workers and "wp_placement" in workers
        assert "jenny" not in workers  # manifest content is authoritative; no Jenny drafting

        rene = next(c for c in chain if c["worker"] == "rene")
        assert rene["status"] == "completed" and rene["result"]["passed"] is True

        wpp = next(c for c in chain if c["worker"] == "wp_placement")
        assert wpp["task_type"] == "wp_draft"
        assert wpp["status"] == "queued"  # founder-gated, never auto-executed

        executed = await wq.execute_worker_task(wpp["task_id"], user=FAKE_USER)
        assert executed["status"] == "needs_review"  # dry-run default, unchanged safety behavior
        preview = executed["result"]["preview"]
        assert preview["title"] == "New Trust Page From Manifest"
        assert "Welcome to Temporary Satisfaction" in preview["html_preview"]
        assert "This is the main body content" in preview["html_preview"]
        assert "/about" in preview["html_preview"]
        assert executed["result"].get("approval_token")
        assert await mock_db.pages.count_documents({}) == 0  # no Page Ops record required

    async def test_blocking_rene_issue_prevents_wp_placement(self, mock_db):
        """A blocking Rene QA issue means NO WP Placement task is created — no approval readiness."""
        item = _page_create_item(qa_requirements=["required_sections:pricing,warranty"])
        manifest, result, chain = await self._queue(item)
        rene = next(c for c in chain if c["worker"] == "rene")
        assert rene["status"] == "needs_review"
        assert rene["result"]["passed"] is False
        assert "pricing" in rene["result"]["reason"].lower()
        assert not any(c["worker"] == "wp_placement" for c in chain)

    async def test_page_create_approved_mock_write_creates_real_content(self, mock_db):
        manifest, result, chain = await self._queue(_page_create_item())
        wpp = next(c for c in chain if c["worker"] == "wp_placement")
        await mock_db.worker_tasks.update_one({"id": wpp["task_id"]}, {"$set": {"status": "queued", "context.execution_mode": "mock"}})
        second = await wq.execute_worker_task(wpp["task_id"], user=FAKE_USER)
        assert second["status"] == "completed"
        assert second["result"]["success"] is True

        placement = await mock_db.wp_placements.find_one({"source_execution_item_id": "item-1"})
        assert placement is not None
        assert placement["source"] == "execution_manifest"
        assert placement["page_title"] == "New Trust Page From Manifest"

    async def test_publication_intent_alone_never_authorizes_publish(self, mock_db):
        """Manifest publication_mode=publish must still require the real approval flow to take effect."""
        item = _page_create_item(placement={
            "slug": "publish-intent-test", "hero_headline": "Test", "intro": "x",
            "body_section_1": "Enough body content here for QA to pass cleanly.",
            "template_id": "standard_content",
            "publication_mode": "publish",
        })
        manifest, result, chain = await self._queue(item)
        wpp = next(c for c in chain if c["worker"] == "wp_placement")

        executed = await wq.execute_worker_task(wpp["task_id"], user=FAKE_USER)
        assert executed["result"]["preview"]["publication_mode"] == "publish"
        assert executed["status"] == "needs_review"

        await mock_db.worker_tasks.update_one({"id": wpp["task_id"]}, {"$set": {"status": "queued", "context.execution_mode": "mock"}})
        result2 = await wq.execute_worker_task(wpp["task_id"], user=FAKE_USER)
        assert result2["status"] == "completed"
        assert result2["result"]["mock"] is True  # never a real live publish

    async def test_page_create_without_title_fails_cleanly(self, mock_db):
        item = _page_create_item(title="", placement={
            "slug": "no-title", "hero_headline": "", "intro": "some intro paragraph",
            "template_id": "standard_content", "publication_mode": "draft",
        })
        manifest, result, chain = await self._queue(item)
        wpp = next((c for c in chain if c["worker"] == "wp_placement"), None)
        assert wpp is not None  # QA passes on content; the title gap is caught at placement
        executed = await wq.execute_worker_task(wpp["task_id"], user=FAKE_USER)
        assert executed["status"] == "failed"
        assert "title" in executed["result"]["error"].lower()

    async def test_old_page_ops_sourced_create_path_still_works_unchanged(self, mock_db):
        """Regression: a non-manifest wp_draft task (no manifest_page_data) must still use the original Page-Ops path exactly as before."""
        await mock_db.pages.insert_one({
            "id": "page-legacy-1", "page_name": "Legacy Page", "page_type": "trust",
            "slug": "legacy-page",
            "generated_content": "[section]Legacy content still works.[/section]",
        })
        task = await wq.create_worker_task(
            source_module="page_ops", source_item_id="page-legacy-1",
            worker="wp_placement", task_type="wp_draft",
        )
        assert task["status"] == "queued"  # founder-gated, unchanged
        result = await wq.execute_worker_task(task["id"], user=FAKE_USER)
        assert result["status"] == "needs_review"
        assert "Legacy content still works" in result["result"]["preview"]["html_preview"]


# ================== 2. EXTENDED RENE WP QA ==================

def _rene_task(context_overrides=None):
    context = {
        "drafted_html": '<p>Solid content with a <a href="/shop">Shop Now</a> link and another <a href="/about">About</a> link.</p>',
        "page_name": "Test Page",
        "page_id": "page-1",
        "wp_page_id": "354999",
    }
    context.update(context_overrides or {})
    return {"context": context}


class TestExtendedReneQA:

    async def test_backward_compatible_basics_unchanged_when_no_requirements_declared(self):
        task = _rene_task()
        result = await wq._rene_qa_wp_content(task)
        assert result["passed"] is True
        assert result["success"] is True

    async def test_missing_drafted_html_still_fails(self):
        task = _rene_task({"drafted_html": ""})
        result = await wq._rene_qa_wp_content(task)
        assert result["passed"] is False
        assert "No drafted HTML" in result["reason"]

    async def test_script_tag_still_fails(self):
        task = _rene_task({"drafted_html": '<p>hi</p><script>alert(1)</script>'})
        result = await wq._rene_qa_wp_content(task)
        assert result["passed"] is False
        assert "script" in result["reason"].lower()

    async def test_duplicate_links_always_fail_even_without_declared_requirement(self):
        task = _rene_task({"drafted_html": '<p><a href="/shop">Shop</a> and again <a href="/shop">Shop</a></p>'})
        result = await wq._rene_qa_wp_content(task)
        assert result["passed"] is False
        assert "duplicate" in result["reason"].lower()

    async def test_malformed_href_is_a_warning_not_a_failure(self):
        task = _rene_task({"drafted_html": '<p>Solid content <a href="javascript:void(0)">click</a></p>'})
        result = await wq._rene_qa_wp_content(task)
        assert result["passed"] is True
        assert any("malformed" in w.lower() for w in result["warnings"])

    async def test_cta_required_passes_when_present(self):
        task = _rene_task({"qa_requirements": ["cta_required"]})
        result = await wq._rene_qa_wp_content(task)
        assert result["passed"] is True

    async def test_cta_required_fails_when_absent(self):
        task = _rene_task({
            "drafted_html": '<p>Just some text with an <a href="/about">About</a> link, no CTA verbs.</p>',
            "qa_requirements": ["cta_required"],
        })
        result = await wq._rene_qa_wp_content(task)
        assert result["passed"] is False
        assert "CTA" in result["reason"]

    async def test_min_internal_links_enforced_when_declared(self):
        task = _rene_task({"qa_requirements": ["min_internal_links:5"]})
        result = await wq._rene_qa_wp_content(task)
        assert result["passed"] is False
        assert "Minimum internal-link count" in result["reason"]

    async def test_min_internal_links_passes_when_met(self):
        task = _rene_task({"qa_requirements": ["min_internal_links:2"]})
        result = await wq._rene_qa_wp_content(task)
        assert result["passed"] is True

    async def test_internal_only_fails_on_external_link(self):
        task = _rene_task({
            "drafted_html": '<p>Content with <a href="https://external-site.com">external</a> link.</p>',
            "qa_requirements": ["internal_only"],
        })
        result = await wq._rene_qa_wp_content(task)
        assert result["passed"] is False
        assert "Non-internal" in result["reason"]

    async def test_required_sections_missing_fails(self):
        task = _rene_task({"qa_requirements": ["required_sections:pricing,warranty"]})
        result = await wq._rene_qa_wp_content(task)
        assert result["passed"] is False
        assert "pricing" in result["reason"].lower()

    async def test_required_sections_present_passes(self):
        task = _rene_task({
            "drafted_html": '<p>Our pricing is fair and our warranty is solid. <a href="/shop">Shop</a></p>',
            "qa_requirements": ["required_sections:pricing,warranty"],
        })
        result = await wq._rene_qa_wp_content(task)
        assert result["passed"] is True

    async def test_seo_required_produces_warnings_not_failures(self):
        task = _rene_task({"qa_requirements": ["seo_required"]})
        result = await wq._rene_qa_wp_content(task)
        assert result["passed"] is True  # warnings, not blocking
        assert any("SEO title" in w for w in result["warnings"])
        assert any("Meta description" in w for w in result["warnings"])

    async def test_seo_required_satisfied_produces_no_warning(self):
        task = _rene_task({"qa_requirements": ["seo_required"], "seo_title": "x", "meta_description": "y"})
        result = await wq._rene_qa_wp_content(task)
        assert not any("SEO title" in w for w in result["warnings"])

    async def test_unrecognized_requirement_is_a_warning_only(self):
        task = _rene_task({"qa_requirements": ["some_future_check_not_implemented_yet"]})
        result = await wq._rene_qa_wp_content(task)
        assert result["passed"] is True
        assert any("Unrecognized qa_requirement" in w for w in result["warnings"])

    async def test_different_pages_can_have_different_requirements(self):
        """Explicitly proves no one-size-fits-all: page A requires a CTA, page B doesn't, using the same function."""
        task_a = _rene_task({
            "drafted_html": '<p>No CTA verbs here, just an <a href="/about">about</a> link.</p>',
            "qa_requirements": ["cta_required"],
        })
        task_b = _rene_task({
            "drafted_html": '<p>No CTA verbs here, just an <a href="/about">about</a> link.</p>',
            "qa_requirements": [],
        })
        result_a = await wq._rene_qa_wp_content(task_a)
        result_b = await wq._rene_qa_wp_content(task_b)
        assert result_a["passed"] is False
        assert result_b["passed"] is True

    async def test_link_marked_internal_but_actually_external_fails(self):
        task = _rene_task({
            "related_links": [{"url": "https://external-site.com", "title": "Bad", "internal": True}],
        })
        result = await wq._rene_qa_wp_content(task)
        assert result["passed"] is False
        assert "not actually internal" in result["reason"]


# ================== 3. INTERNAL LINK MAP ==================

class TestInternalLinkMap:

    def test_link_map_structure_is_well_formed(self):
        import services.menu_mapper as mm
        required_keys = {"source_slug", "destination_slug", "anchor_label", "reason", "required"}
        assert len(mm.INTERNAL_LINK_MAP) > 0
        for row in mm.INTERNAL_LINK_MAP:
            assert required_keys.issubset(row.keys())
            assert isinstance(row["required"], bool)

    def test_curated_suggestions_preserved_for_existing_pages(self):
        import services.menu_mapper as mm
        pages = [
            {"slug": "about", "page_name": "About", "page_family": "Trust"},
            {"slug": "who-we-serve", "page_name": "Who We Serve", "page_family": "Trust"},
            {"slug": "long-beach-adult-boutique", "page_name": "LB Boutique", "page_family": "District"},
        ]
        suggestions = mm._generate_link_suggestions(pages)
        about_suggestion = next(s for s in suggestions if s["from_slug"] == "about" and s["source"] == "curated")
        linked_slugs = {l["slug"] for l in about_suggestion["links_to"]}
        assert "who-we-serve" in linked_slugs
        assert "long-beach-adult-boutique" in linked_slugs

    def test_auto_fallback_suggests_links_for_new_pages_sharing_family(self):
        import services.menu_mapper as mm
        pages = [
            {"slug": "new-page-1", "page_name": "New Page 1", "page_family": "District"},
            {"slug": "new-page-2", "page_name": "New Page 2", "page_family": "District"},
        ]
        suggestions = mm._generate_link_suggestions(pages)
        auto = [s for s in suggestions if s["source"] == "auto"]
        assert len(auto) == 2  # each page suggests the other
        assert auto[0]["links_to"][0]["slug"] in ("new-page-1", "new-page-2")

    def test_auto_fallback_never_duplicates_a_curated_pair(self):
        import services.menu_mapper as mm
        pages = [
            {"slug": "about", "page_name": "About", "page_family": "Trust"},
            {"slug": "who-we-serve", "page_name": "Who We Serve", "page_family": "Trust"},
        ]
        suggestions = mm._generate_link_suggestions(pages)
        about_curated = next(s for s in suggestions if s["from_slug"] == "about" and s["source"] == "curated")
        about_auto = [s for s in suggestions if s["from_slug"] == "about" and s["source"] == "auto"]
        curated_targets = {l["slug"] for l in about_curated["links_to"]}
        if about_auto:
            auto_targets = {l["slug"] for l in about_auto[0]["links_to"]}
            assert curated_targets.isdisjoint(auto_targets)
