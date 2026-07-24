"""
WooCommerce Taxonomy Lane — focused tests
(ops/woocommerce-taxonomy-lane-20260723, built on
ops/page-create-hardening-known-good-20260723 @ daebaf9bf4c1840f7334aa56d2fb47408cc01f5b)

Proves the smallest safe vertical slice that lets OPS read, dry-run,
founder-approve, create, and update WooCommerce product-category taxonomy
terms -- a distinct object type from WordPress pages, never routed through
/wp/v2/pages or a page_id.

Runs entirely against the in-memory Mongo double (tests/conftest.py) and a
faked httpx transport for the "live" REST-endpoint-shape checks -- no real
MongoDB, no real WordPress/WooCommerce, no network. Consistent with the
existing worker-chain/write-safety test precedent (test_worker_chain_e2e.py,
test_wp_write_safety_unit.py, test_page_create_hardening.py): "live requires
real credentials" is proven by observing the refusal in this sandbox (no
WP_SITE_URL/WP_USERNAME/WP_APP_PASSWORD configured here), and the
token-consumption mechanics are proven by calling
services.wp_write_safety directly, exactly as the page precedent does.
"""
import pytest

import services.execution_manifest as em
import services.worker_queue as wq
import services.wp_client as wpc
import services.wp_write_safety as wws

FAKE_USER = {"sub": "founder", "role": "admin"}


# ================== FIXTURES / HELPERS ==================

def _category_data(**overrides):
    data = {
        "object_type": "woocommerce_product_category",
        "taxonomy": "product_cat",
        "operation": "taxonomy_update",
        "term_id": 78144,
        "name": "Masturbators & Strokers",
        "slug": "masturbators-and-strokers",
        "introduction": "A curated range of solo-pleasure devices.",
        "how_to_guidance": "Consider material, motor strength, and cleanup.",
        "faqs": [
            {"question": f"FAQ {i}?", "answer": f"Answer {i}."} for i in range(1, 7)
        ],
        "cta_text": "Shop Masturbators & Strokers",
        "cta_url": "/product-category/masturbators-and-strokers",
        "related_links": [
            {"url": "/product-category/water-based-lubes", "title": "Water-Based Lubes"},
            {"url": "/product-category/penis-pumps", "title": "Penis Pumps"},
            {"url": "/product-category/cock-rings", "title": "Cock Rings"},
        ],
        "seo_title": "Masturbators & Strokers | Temporary Satisfaction",
        "meta_description": "Shop masturbators and strokers.",
    }
    data.update(overrides)
    return data


def _exec_task(context, source_item_id="tax-exec-1"):
    return {"source_item_id": source_item_id, "context": context}


def _rene_task(data=None, qa=None, context_overrides=None):
    data = data if data is not None else _category_data()
    context = {
        "manifest_category_data": data,
        "qa_requirements": qa or [],
        "related_links": data.get("related_links", []),
    }
    context.update(context_overrides or {})
    return {"context": context}


def _manifest(item):
    return {
        "manifest_id": None, "schema_version": "1.0", "source_system": "TSAF",
        "source_packet_id": "pkt-taxonomy", "campaign_id": "camp-taxonomy",
        "campaign_name": "Taxonomy Hardening", "execution_items": [item], "assets": [],
    }


def _taxonomy_item(item_id="tax-item-1", execution_type="taxonomy_update", **overrides):
    placement = {
        "term_id": 78144,
        "slug": "masturbators-and-strokers",
        "description": "PENDING_CONTENT — not yet drafted",
        "introduction": "A curated range of solo-pleasure devices.",
        "how_to_guidance": "Consider material, motor strength, and cleanup.",
        "faqs": [{"question": f"FAQ {i}?", "answer": f"Answer {i}."} for i in range(1, 7)],
        "cta_text": "Shop Masturbators & Strokers",
        "cta_url": "/product-category/masturbators-and-strokers",
        "related_links": [{"url": "/product-category/water-based-lubes", "title": "Water-Based Lubes"}],
    }
    if "placement" in overrides:
        placement.update(overrides.pop("placement"))
    item = {
        "item_id": item_id, "sequence": 1,
        "title": "Masturbators & Strokers",
        "destination": "wordpress", "execution_type": execution_type,
        "status": "pending",
        "copy": "PENDING_CONTENT — not yet drafted",
        "qa_requirements": [],
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


class _FakeResponse:
    def __init__(self, status_code, data):
        self.status_code = status_code
        self._data = data
        self.text = str(data)

    def json(self):
        return self._data


class _FakeAsyncClient:
    """Records every call so tests can assert the exact REST path used."""
    calls = []

    def __init__(self, *a, **kw):
        pass

    async def __aenter__(self):
        return self

    async def __aexit__(self, *a):
        return False

    async def get(self, url, headers=None, params=None):
        _FakeAsyncClient.calls.append(("GET", url, params))
        term = {
            "id": 78144, "name": "Masturbators & Strokers", "slug": "masturbators-and-strokers",
            "description": "existing desc", "parent": 0, "count": 3,
            "link": "https://example.test/product-category/masturbators-and-strokers",
            "taxonomy": "product_cat",
        }
        # A single-term GET hits /product_cat/{id}; a slug lookup hits the
        # bare collection endpoint with ?slug=... and WP REST returns a list.
        if url.rstrip("/").endswith("/product_cat"):
            return _FakeResponse(200, [term])
        return _FakeResponse(200, term)

    async def post(self, url, headers=None, json=None):
        _FakeAsyncClient.calls.append(("POST", url, json))
        return _FakeResponse(200, {
            "id": 78144, "name": (json or {}).get("name", "x"), "slug": (json or {}).get("slug", "x"),
            "description": (json or {}).get("description", ""), "parent": (json or {}).get("parent", 0) or 0,
            "count": 0, "link": "https://example.test/product-category/x", "taxonomy": "product_cat",
        })


# ================== 1. TAXONOMY READS USE THE TAXONOMY ENDPOINT ==================

class TestTaxonomyEndpointUsage:

    async def test_get_product_category_uses_product_cat_not_pages(self, mock_db, monkeypatch):
        _FakeAsyncClient.calls = []
        monkeypatch.setattr(wpc, "IS_LIVE", True)
        monkeypatch.setattr(wpc, "_api_base", "https://example.test/wp-json/wp/v2")
        monkeypatch.setattr(wpc, "_headers", {})
        monkeypatch.setattr(wpc.httpx, "AsyncClient", _FakeAsyncClient)

        result = await wpc.get_product_category(78144)

        assert result["term_id"] == 78144
        assert result["object_type"] == "woocommerce_product_category"
        assert len(_FakeAsyncClient.calls) == 1
        method, url, _ = _FakeAsyncClient.calls[0]
        assert "/product_cat/78144" in url
        assert "/pages" not in url

    async def test_find_product_category_by_slug_uses_product_cat_not_pages(self, mock_db, monkeypatch):
        _FakeAsyncClient.calls = []
        monkeypatch.setattr(wpc, "IS_LIVE", True)
        monkeypatch.setattr(wpc, "_api_base", "https://example.test/wp-json/wp/v2")
        monkeypatch.setattr(wpc, "_headers", {})
        monkeypatch.setattr(wpc.httpx, "AsyncClient", _FakeAsyncClient)

        result = await wpc.find_product_category_by_slug("masturbators-and-strokers")

        assert result["slug"] == "masturbators-and-strokers"
        method, url, params = _FakeAsyncClient.calls[0]
        assert url.endswith("/product_cat")
        assert params == {"slug": "masturbators-and-strokers"}

    async def test_create_product_category_posts_to_product_cat_not_pages(self, mock_db, monkeypatch):
        _FakeAsyncClient.calls = []
        monkeypatch.setattr(wpc, "IS_LIVE", True)
        monkeypatch.setattr(wpc, "_api_base", "https://example.test/wp-json/wp/v2")
        monkeypatch.setattr(wpc, "_headers", {})
        monkeypatch.setattr(wpc.httpx, "AsyncClient", _FakeAsyncClient)

        token = await wws.issue_approval_token(
            scope="single", scope_ids=["ex-1"],
            payload={"taxonomy": "product_cat", "name": "New Cat", "slug": "new-cat", "description": "d", "parent": None},
            publication_mode="n/a", object_type="woocommerce_product_category",
        )
        result = await wpc.create_product_category(
            {"name": "New Cat", "slug": "new-cat", "description": "d", "parent": None},
            execution_mode="live", approval_token=token["token"], scope_ids=["ex-1"], user=FAKE_USER,
        )
        assert result["term_id"] == 78144
        method, url, body = _FakeAsyncClient.calls[0]
        assert url.endswith("/product_cat")
        assert "/pages" not in url


# ================== 2. TERM_ID NEVER ROUTES THROUGH PAGE_ID ==================

class TestTermIdNeverConfusedWithPageId:

    async def test_get_page_and_get_product_category_hit_separate_collections(self, mock_db):
        # Same literal identifier value used for a page id (string) and a
        # term id (int) -- they must resolve to completely independent
        # records, proving no shared lookup path exists.
        await mock_db.wp_mock_pages.insert_one({
            "id": "78144", "wp_id": None, "title": "A Page, Not A Category",
            "slug": "a-page", "content": "x", "status": "draft",
            "seo_title": "", "meta_description": "", "link": "l",
            "created_at": "now", "updated_at": "now", "mock": True,
        })
        await mock_db.wp_mock_product_categories.insert_one({
            "term_id": 78144, "name": "Masturbators & Strokers", "slug": "masturbators-and-strokers",
            "description": "d", "parent": 0, "count": 0, "link": "l",
            "taxonomy": "product_cat", "object_type": "woocommerce_product_category",
            "created_at": "now", "updated_at": "now", "mock": True,
        })

        page = await wpc.get_page("78144")
        category = await wpc.get_product_category(78144)

        assert page["title"] == "A Page, Not A Category"
        assert category["name"] == "Masturbators & Strokers"
        assert page.get("term_id") is None
        assert category.get("wp_id") is None and "page" not in category


# ================== 3. ROUTING ==================

class TestTaxonomyRouting:

    def test_taxonomy_update_routes_to_rene_wp_taxonomy_qa(self):
        routing = em.determine_routing({"destination": "wordpress", "execution_type": "taxonomy_update"})
        assert routing["support"] == "supported_now"
        assert routing["worker"] == "rene"
        assert routing["task_type"] == "wp_taxonomy_qa"

    def test_taxonomy_create_routes_to_rene_wp_taxonomy_qa(self):
        routing = em.determine_routing({"destination": "wordpress", "execution_type": "taxonomy_create"})
        assert routing["support"] == "supported_now"
        assert routing["worker"] == "rene"
        assert routing["task_type"] == "wp_taxonomy_qa"

    async def test_taxonomy_update_item_auto_routes_rene_then_wp_placement_update(self, mock_db):
        await mock_db.wp_mock_product_categories.insert_one({
            "term_id": 78144, "name": "Masturbators & Strokers", "slug": "masturbators-and-strokers",
            "description": "old", "parent": 0, "count": 0, "link": "l",
            "taxonomy": "product_cat", "object_type": "woocommerce_product_category",
            "created_at": "now", "updated_at": "now", "mock": True,
        })
        _, result, chain = await _queue(_taxonomy_item(execution_type="taxonomy_update"))
        assert result["worker"] == "rene" and result["task_type"] == "wp_taxonomy_qa"
        assert "jenny" not in [c["worker"] for c in chain]
        rene = next(c for c in chain if c["worker"] == "rene")
        assert rene["result"]["passed"] is True
        wpp = next(c for c in chain if c["worker"] == "wp_placement")
        assert wpp["task_type"] == "wp_taxonomy_update" and wpp["status"] == "queued"

    async def test_taxonomy_create_item_auto_routes_rene_then_wp_placement_create(self, mock_db):
        item = _taxonomy_item(
            item_id="tax-item-create", execution_type="taxonomy_create",
            title="Lingerie Sets, Babydolls & Teddies",
            placement={"term_id": None, "slug": "lingerie-sets-babydolls-teddies"},
        )
        _, result, chain = await _queue(item)
        assert result["worker"] == "rene" and result["task_type"] == "wp_taxonomy_qa"
        wpp = next(c for c in chain if c["worker"] == "wp_placement")
        assert wpp["task_type"] == "wp_taxonomy_create" and wpp["status"] == "queued"


# ================== 4. RENE TAXONOMY QA ==================

class TestReneTaxonomyQA:

    async def test_full_valid_content_passes(self, mock_db):
        task = _rene_task(qa=["intro_required", "how_to_required", "faq_count:6",
                               "cta_required", "min_internal_links:3", "internal_only", "seo_required"])
        result = await wq._rene_qa_taxonomy_content(task)
        assert result["passed"] is True

    async def test_missing_name_and_slug_and_description_fails(self, mock_db):
        task = _rene_task(data=_category_data(name="", slug="", introduction="", how_to_guidance="",
                                                faqs=[], cta_text="", cta_url="", related_links=[]))
        result = await wq._rene_qa_taxonomy_content(task)
        assert result["passed"] is False
        assert any("name" in i.lower() for i in result["issues"])
        assert any("slug" in i.lower() for i in result["issues"])

    async def test_missing_term_id_blocks_update(self, mock_db):
        task = _rene_task(data=_category_data(term_id=None, operation="taxonomy_update"))
        result = await wq._rene_qa_taxonomy_content(task)
        assert result["passed"] is False
        assert any("term_id" in i for i in result["issues"])

    async def test_non_numeric_term_id_blocks_update(self, mock_db):
        task = _rene_task(data=_category_data(term_id="not-a-number", operation="taxonomy_update"))
        result = await wq._rene_qa_taxonomy_content(task)
        assert result["passed"] is False
        assert any("numeric term_id" in i for i in result["issues"])

    async def test_duplicate_slug_blocks_create(self, mock_db):
        await mock_db.wp_mock_product_categories.insert_one({
            "term_id": 900123, "name": "Existing", "slug": "lingerie-sets-babydolls-teddies",
            "description": "existing", "parent": 0, "count": 0, "link": "l",
            "taxonomy": "product_cat", "object_type": "woocommerce_product_category",
            "created_at": "now", "updated_at": "now", "mock": True,
        })
        data = _category_data(operation="taxonomy_create", term_id=None,
                               name="Lingerie Sets, Babydolls & Teddies",
                               slug="lingerie-sets-babydolls-teddies")
        task = _rene_task(data=data)
        result = await wq._rene_qa_taxonomy_content(task)
        assert result["passed"] is False
        assert any("already exists" in i for i in result["issues"])

    async def test_duplicate_slug_confirmed_allows_create(self, mock_db):
        await mock_db.wp_mock_product_categories.insert_one({
            "term_id": 900123, "name": "Existing", "slug": "lingerie-sets-babydolls-teddies",
            "description": "existing", "parent": 0, "count": 0, "link": "l",
            "taxonomy": "product_cat", "object_type": "woocommerce_product_category",
            "created_at": "now", "updated_at": "now", "mock": True,
        })
        data = _category_data(operation="taxonomy_create", term_id=None,
                               name="Lingerie Sets, Babydolls & Teddies",
                               slug="lingerie-sets-babydolls-teddies")
        task = _rene_task(data=data, context_overrides={"duplicate_slug_confirmed": True})
        result = await wq._rene_qa_taxonomy_content(task)
        assert result["passed"] is True

    async def test_faq_count_requirement_enforced(self, mock_db):
        data = _category_data(faqs=[{"question": "Only one?", "answer": "Yes."}])
        task = _rene_task(data=data, qa=["faq_count:6"])
        result = await wq._rene_qa_taxonomy_content(task)
        assert result["passed"] is False
        assert any("FAQ" in i for i in result["issues"])

    async def test_pending_content_marker_alone_is_too_short_and_fails(self, mock_db):
        # The authoritative backlog schema marks undrafted content with a
        # literal "PENDING_CONTENT" marker (see docs/backlogs/...json) --
        # this must NOT be mistaken for real, ready content.
        data = _category_data(introduction="", how_to_guidance="", faqs=[])
        data["description"] = "PENDING_CONTENT — not yet drafted"
        task = {"context": {
            "manifest_category_data": data,
            "qa_requirements": ["intro_required"],
            "drafted_description": "",
        }}
        result = await wq._rene_qa_taxonomy_content(task)
        assert result["passed"] is False


# ================== 5. DRY-RUN: ZERO WRITES, TOKEN ISSUED ==================

class TestTaxonomyDryRun:

    async def test_dry_run_update_zero_writes_issues_token(self, mock_db):
        await mock_db.wp_mock_product_categories.insert_one({
            "term_id": 78144, "name": "Masturbators & Strokers", "slug": "masturbators-and-strokers",
            "description": "original description", "parent": 0, "count": 0, "link": "l",
            "taxonomy": "product_cat", "object_type": "woocommerce_product_category",
            "created_at": "now", "updated_at": "now", "mock": True,
        })
        task = _exec_task({"manifest_category_data": _category_data()})
        result = await wq._execute_wp_taxonomy_update(task, user=FAKE_USER)

        assert result["needs_review"] is True
        assert result["approval_token"]
        preview = result["preview"]
        assert preview["object_type"] == "woocommerce_product_category"
        assert preview["operation"] == "taxonomy_update"
        assert "/product_cat/78144" in preview["rest_endpoint"]
        assert "/pages" not in preview["rest_endpoint"]

        unchanged = await mock_db.wp_mock_product_categories.find_one({"term_id": 78144}, {"_id": 0})
        assert unchanged["description"] == "original description"
        assert await mock_db.wp_taxonomy_placements.count_documents({}) == 0

    async def test_dry_run_create_zero_writes_issues_token(self, mock_db):
        data = _category_data(operation="taxonomy_create", term_id=None,
                               name="Lingerie Sets, Babydolls & Teddies",
                               slug="lingerie-sets-babydolls-teddies")
        task = _exec_task({"manifest_category_data": data})
        result = await wq._execute_wp_taxonomy_create(task, user=FAKE_USER)

        assert result["needs_review"] is True
        assert result["approval_token"]
        preview = result["preview"]
        assert preview["operation"] == "taxonomy_create"
        assert preview["rest_endpoint"] == "/wp-json/wp/v2/product_cat"

        assert await mock_db.wp_mock_product_categories.count_documents(
            {"slug": "lingerie-sets-babydolls-teddies"}
        ) == 0
        assert await mock_db.wp_taxonomy_placements.count_documents({}) == 0

    async def test_dry_run_create_blocked_by_existing_slug(self, mock_db):
        await mock_db.wp_mock_product_categories.insert_one({
            "term_id": 900555, "name": "Existing", "slug": "lingerie-sets-babydolls-teddies",
            "description": "existing", "parent": 0, "count": 0, "link": "l",
            "taxonomy": "product_cat", "object_type": "woocommerce_product_category",
            "created_at": "now", "updated_at": "now", "mock": True,
        })
        data = _category_data(operation="taxonomy_create", term_id=None,
                               name="Lingerie Sets, Babydolls & Teddies",
                               slug="lingerie-sets-babydolls-teddies")
        task = _exec_task({"manifest_category_data": data})
        result = await wq._execute_wp_taxonomy_create(task, user=FAKE_USER)
        assert result["needs_review"] is True
        assert "already exists" in result["reason"]
        assert not result.get("approval_token")


# ================== 6. MOCK-MODE WRITE + READ-AFTER-WRITE PROOF ==================

class TestTaxonomyMockWriteAndProofLogging:

    async def test_mock_update_writes_once_and_records_verified_proof(self, mock_db):
        await mock_db.wp_mock_product_categories.insert_one({
            "term_id": 78144, "name": "Masturbators & Strokers", "slug": "masturbators-and-strokers",
            "description": "original description", "parent": 0, "count": 0, "link": "l",
            "taxonomy": "product_cat", "object_type": "woocommerce_product_category",
            "created_at": "now", "updated_at": "now", "mock": True,
        })
        task = _exec_task({"manifest_category_data": _category_data(), "execution_mode": "mock"})
        result = await wq._execute_wp_taxonomy_update(task, user=FAKE_USER)

        assert result["success"] is True
        assert result["read_after_write_verified"] is True

        updated = await mock_db.wp_mock_product_categories.find_one({"term_id": 78144}, {"_id": 0})
        assert updated["description"] != "original description"
        assert "curated range" in updated["description"]

        proof = await mock_db.wp_taxonomy_placements.find_one({"term_id": 78144}, {"_id": 0})
        assert proof is not None
        assert proof["object_type"] == "woocommerce_product_category"
        assert proof["operation"] == "taxonomy_update"
        assert proof["read_after_write_verified"] is True
        assert proof["description_length_before"] == len("original description")

    async def test_mock_create_writes_once_and_records_verified_proof(self, mock_db):
        data = _category_data(operation="taxonomy_create", term_id=None,
                               name="Lingerie Sets, Babydolls & Teddies",
                               slug="lingerie-sets-babydolls-teddies")
        task = _exec_task({"manifest_category_data": data, "execution_mode": "mock"})
        result = await wq._execute_wp_taxonomy_create(task, user=FAKE_USER)

        assert result["success"] is True
        assert isinstance(result["term_id"], int)
        assert result["read_after_write_verified"] is True

        created = await mock_db.wp_mock_product_categories.find_one(
            {"slug": "lingerie-sets-babydolls-teddies"}, {"_id": 0}
        )
        assert created is not None
        assert isinstance(created["term_id"], int)

        proof = await mock_db.wp_taxonomy_placements.find_one(
            {"operation": "taxonomy_create", "term_slug": "lingerie-sets-babydolls-teddies"}, {"_id": 0}
        )
        assert proof is not None
        assert proof["read_after_write_verified"] is True


# ================== 7. LIVE WRITE REQUIRES CREDENTIALS + TOKEN ==================

class TestTaxonomyLiveWriteSafety:

    async def test_live_update_refused_without_real_credentials(self, mock_db):
        """
        This sandbox has no WP_SITE_URL/WP_USERNAME/WP_APP_PASSWORD configured
        (services.wp_client.IS_LIVE is False), so a "live" execution_mode must
        be refused loudly -- never silently downgraded to a mock write. This
        mirrors the exact refusal the page lane proves under the same
        sandbox constraint (see docs/PROJECT_STATE.md Phase 6 notes).
        """
        assert wpc.IS_LIVE is False
        await mock_db.wp_mock_product_categories.insert_one({
            "term_id": 78144, "name": "Masturbators & Strokers", "slug": "masturbators-and-strokers",
            "description": "original description", "parent": 0, "count": 0, "link": "l",
            "taxonomy": "product_cat", "object_type": "woocommerce_product_category",
            "created_at": "now", "updated_at": "now", "mock": True,
        })
        task = _exec_task({
            "manifest_category_data": _category_data(),
            "execution_mode": "live",
            "approval_token": "irrelevant-because-credentials-check-runs-first",
        })
        result = await wq._execute_wp_taxonomy_update(task, user=FAKE_USER)
        assert result.get("success") is not True
        assert "error" in result
        assert "credentials" in result["error"].lower()

    async def test_live_create_refused_without_real_credentials(self, mock_db):
        assert wpc.IS_LIVE is False
        data = _category_data(operation="taxonomy_create", term_id=None,
                               name="Lingerie Sets, Babydolls & Teddies",
                               slug="lingerie-sets-babydolls-teddies")
        task = _exec_task({
            "manifest_category_data": data,
            "execution_mode": "live",
            "approval_token": "irrelevant-because-credentials-check-runs-first",
        })
        result = await wq._execute_wp_taxonomy_create(task, user=FAKE_USER)
        assert result.get("success") is not True
        assert "error" in result
        assert "credentials" in result["error"].lower()

    async def test_live_write_requires_a_token_at_all(self, mock_db):
        """
        Token-presence enforcement proven directly against the write-safety
        engine (bypassing the credentials gate, exactly as the page-lane
        precedent does in test_worker_chain_e2e.py) -- consume_approval_token
        refuses immediately when no token is supplied, before it would ever
        reach a real WordPress/WooCommerce call.
        """
        with pytest.raises(wws.WpWriteSafetyError, match="no approval_token supplied"):
            await wws.consume_approval_token(
                None, ["78144"], {"term_id": 78144}, "founder", "admin", "manual_confirmation",
                object_type="woocommerce_product_category",
            )

    async def test_token_object_type_mismatch_fails(self, mock_db):
        token = await wws.issue_approval_token(
            scope="single", scope_ids=["78144"],
            payload={"term_id": 78144, "taxonomy": "product_cat", "name": "x", "slug": "x",
                      "description": "d", "parent": 0},
            publication_mode="n/a", object_type="woocommerce_product_category",
        )
        with pytest.raises(wws.WpWriteSafetyError, match="object_type does not match"):
            await wws.consume_approval_token(
                token["token"], ["78144"],
                {"term_id": 78144, "taxonomy": "product_cat", "name": "x", "slug": "x",
                 "description": "d", "parent": 0},
                "founder", "admin", "manual_confirmation",
                object_type="page",
            )

    async def test_page_token_cannot_be_replayed_against_taxonomy_write(self, mock_db):
        # A token issued with the (default) "page" object_type must be
        # refused when consumed as a taxonomy write, and vice versa --
        # proven both directions.
        page_token = await wws.issue_approval_token(
            scope="single", scope_ids=["354950"], payload={"page_id": "354950", "content": "x"},
        )
        with pytest.raises(wws.WpWriteSafetyError, match="object_type does not match"):
            await wws.consume_approval_token(
                page_token["token"], ["354950"], {"page_id": "354950", "content": "x"},
                "founder", "admin", "manual_confirmation",
                object_type="woocommerce_product_category",
            )

    async def test_token_consumed_once(self, mock_db):
        token = await wws.issue_approval_token(
            scope="single", scope_ids=["78144"],
            payload={"term_id": 78144, "taxonomy": "product_cat", "name": "x", "slug": "x",
                      "description": "d", "parent": 0},
            publication_mode="n/a", object_type="woocommerce_product_category",
        )
        payload = {"term_id": 78144, "taxonomy": "product_cat", "name": "x", "slug": "x",
                   "description": "d", "parent": 0}
        first = await wws.consume_approval_token(
            token["token"], ["78144"], payload, "founder", "admin", "manual_confirmation",
            object_type="woocommerce_product_category",
        )
        assert first["consumed"] is True

        with pytest.raises(wws.WpWriteSafetyError, match="already been used"):
            await wws.consume_approval_token(
                token["token"], ["78144"], payload, "founder", "admin", "manual_confirmation",
                object_type="woocommerce_product_category",
            )


# ================== 8. MOCK CANNOT TOUCH LIVE WORDPRESS ==================

class TestMockNeverTouchesNetwork:

    async def test_mock_create_and_update_never_call_httpx(self, mock_db, monkeypatch):
        class _ExplodingClient:
            def __init__(self, *a, **kw):
                raise AssertionError("mock execution_mode must never open an HTTP client")

        monkeypatch.setattr(wpc.httpx, "AsyncClient", _ExplodingClient)

        created = await wpc.create_product_category(
            {"name": "Safe Mock Cat", "slug": "safe-mock-cat", "description": "d", "parent": None},
            execution_mode="mock",
        )
        assert created["mock"] is True

        updated = await wpc.update_product_category(
            created["term_id"], {"description": "updated"}, execution_mode="mock",
        )
        assert updated["description"] == "updated"


# ================== 9. PAGE LANES UNCHANGED ==================

class TestPageLanesUnchanged:

    def test_page_create_routing_still_unchanged(self):
        routing = em.determine_routing({"destination": "wordpress", "execution_type": "page_create"})
        assert routing["worker"] == "rene" and routing["task_type"] == "wp_content_qa"

    def test_page_update_routing_still_unchanged(self):
        routing = em.determine_routing({"destination": "wordpress", "execution_type": "page_update"})
        assert routing["worker"] == "jenny" and routing["task_type"] == "wp_content_draft"

    def test_wp_placement_worker_still_advertises_original_page_task_types(self):
        task_types = wq.WORKERS["wp_placement"]["task_types"]
        for original in ("wp_draft", "page_placement", "wp_page_update"):
            assert original in task_types
        for added in ("wp_taxonomy_update", "wp_taxonomy_create"):
            assert added in task_types

    async def test_page_token_still_defaults_to_page_object_type(self, mock_db):
        token = await wws.issue_approval_token(
            scope="single", scope_ids=["354950"], payload={"page_id": "354950", "content": "x"},
        )
        assert token["object_type"] == "page"
