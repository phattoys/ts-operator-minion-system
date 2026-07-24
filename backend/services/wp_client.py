"""
WordPress Client Abstraction Layer
---
Uses real WordPress REST API when WP_SITE_URL, WP_USERNAME, WP_APP_PASSWORD are set.
Falls back to MongoDB mock when credentials are missing.
"""
import os
import uuid
import base64
import httpx
from datetime import datetime, timezone
from database import db, logger
from services.wp_write_safety import enforce_live_write, WpWriteSafetyError


WP_SITE_URL = os.environ.get("WP_SITE_URL", "").rstrip("/")
WP_USERNAME = os.environ.get("WP_USERNAME", "")
WP_APP_PASSWORD = os.environ.get("WP_APP_PASSWORD", "")

IS_LIVE = bool(WP_SITE_URL and WP_USERNAME and WP_APP_PASSWORD)

if IS_LIVE:
    _auth_string = base64.b64encode(f"{WP_USERNAME}:{WP_APP_PASSWORD}".encode()).decode()
    _headers = {
        "Authorization": f"Basic {_auth_string}",
        "Content-Type": "application/json",
    }
    _api_base = f"{WP_SITE_URL}/wp-json/wp/v2"
    logger.info(f"[WP Client] Live mode: {WP_SITE_URL} as {WP_USERNAME}")
else:
    _headers = {}
    _api_base = ""
    logger.info("[WP Client] Mock mode — no WordPress credentials")


# ================== UNIFIED WRITE-SAFETY GATE ==================
#
# create_page() and update_page() are the ONLY functions in this codebase
# that can reach real WordPress. Every write path -- the direct
# /api/wp-placement/place route, the Worker Queue's wp_placement worker,
# and any future OPS worker or execution-manifest task -- must call through
# here, and both functions now REQUIRE an explicit execution_mode. There is
# no default that means "skip the check": a caller that doesn't pass
# execution_mode gets an immediate TypeError rather than an accidental
# live write, and a caller that passes an unrecognized mode gets a raised
# WpWriteSafetyError rather than silent fallback behavior.
#
# execution_mode:
#   "mock"    -> always writes to the local Mongo mock collection, even if
#                real WordPress credentials are configured. Never touches
#                real WordPress.
#   "live"    -> requires a valid, unexpired, unconsumed, payload-bound,
#                scope-bound approval_token (see services/wp_write_safety.py).
#                Fails loudly if credentials are absent, if the token is
#                missing/invalid/expired/consumed, or if the payload/scope
#                no longer match what was approved.
#
# "dry_run" is intentionally NOT handled here: a dry run never reaches this
# module at all. Route/service code builds and returns a preview using
# services/wp_placement.build_page_content() directly and calls
# services.wp_write_safety.issue_approval_token() -- it never calls
# create_page()/update_page() in dry_run mode.
#
# Publication safety: a live write is not automatic permission to publish
# publicly. Unless publication_mode == "publish" was explicitly authorized
# at approval time, the WordPress status is forced to "draft" here,
# regardless of what status the caller requested.


async def create_page(
    title: str,
    slug: str,
    content: str,
    status: str = "draft",
    meta: dict = None,
    *,
    execution_mode: str,
    approval_token: str = None,
    scope_ids: list = None,
    user: dict = None,
) -> dict:
    if execution_mode == "mock":
        return await _mock_create_page(title, slug, content, status, meta)

    if execution_mode != "live":
        raise WpWriteSafetyError(
            f"create_page() called with unsupported execution_mode={execution_mode!r}. "
            "Dry runs must not call create_page() at all -- build a preview instead."
        )

    payload = {"title": title, "slug": slug, "content": content, "meta": meta or {}}
    approval = await enforce_live_write(
        execution_mode=execution_mode,
        approval_token=approval_token,
        scope_ids=scope_ids or [slug or title],
        payload=payload,
        user=user or {},
        is_live=IS_LIVE,
    )
    final_status = status if approval.get("publication_mode") == "publish" else "draft"
    return await _live_create_page(title, slug, content, final_status, meta)


async def update_page(
    page_id: str,
    content: str,
    title: str = None,
    slug: str = None,
    meta: dict = None,
    *,
    execution_mode: str,
    approval_token: str = None,
    scope_ids: list = None,
    user: dict = None,
) -> dict:
    if execution_mode == "mock":
        return await _mock_update_page(page_id, content, title, slug, meta)

    if execution_mode != "live":
        raise WpWriteSafetyError(
            f"update_page() called with unsupported execution_mode={execution_mode!r}. "
            "Dry runs must not call update_page() at all -- build a preview instead."
        )

    payload = {"page_id": page_id, "content": content, "title": title, "slug": slug, "meta": meta or {}}
    await enforce_live_write(
        execution_mode=execution_mode,
        approval_token=approval_token,
        scope_ids=scope_ids or [page_id],
        payload=payload,
        user=user or {},
        is_live=IS_LIVE,
    )
    # Page updates never change publish status implicitly -- WordPress
    # preserves whatever status the target page already has.
    return await _live_update_page(page_id, content, title, slug, meta)


async def get_pages(status: str = "draft", per_page: int = 50) -> list:
    if IS_LIVE:
        return await _live_get_pages(status, per_page)
    return await _mock_get_pages(status, per_page)


async def get_page(page_id: str) -> dict:
    if IS_LIVE:
        return await _live_get_page(page_id)
    return await _mock_get_page(page_id)


# ================== WOOCOMMERCE TAXONOMY (PRODUCT CATEGORIES) ==================
#
# WooCommerce product categories are WordPress taxonomy TERMS, not pages.
# WooCommerce registers the `product_cat` taxonomy as a public REST-API
# taxonomy under the standard wp/v2 route (/wp-json/wp/v2/product_cat),
# using the same Basic-Auth application-password credentials as /wp/v2/pages
# -- there is no separate wc/v3 consumer-key/secret needed for this repo's
# use case, so only the wp/v2/product_cat endpoint is implemented here.
# Identified by a numeric term_id, which must never be confused with or
# passed where a page_id is expected (see create_page()/update_page() above
# -- entirely separate functions, entirely separate collections).
#
# create_product_category() and update_product_category() route through the
# SAME unified write-safety gate as create_page()/update_page()
# (services/wp_write_safety.enforce_live_write) -- no second approval
# system. They pass object_type="woocommerce_product_category" so an
# approval token issued for a page can never be replayed against a
# taxonomy-term write, or vice versa.


async def get_product_category(term_id: int) -> dict:
    if IS_LIVE:
        return await _live_get_product_category(term_id)
    return await _mock_get_product_category(term_id)


async def find_product_category_by_slug(slug: str) -> dict:
    if IS_LIVE:
        return await _live_find_product_category_by_slug(slug)
    return await _mock_find_product_category_by_slug(slug)


async def create_product_category(
    payload: dict,
    *,
    execution_mode: str,
    approval_token: str = None,
    scope_ids: list = None,
    user: dict = None,
    object_type: str = "woocommerce_product_category",
) -> dict:
    if execution_mode == "mock":
        return await _mock_create_product_category(payload)

    if execution_mode != "live":
        raise WpWriteSafetyError(
            f"create_product_category() called with unsupported execution_mode={execution_mode!r}. "
            "Dry runs must not call create_product_category() at all -- build a preview instead."
        )

    write_payload = {"taxonomy": "product_cat", **payload}
    await enforce_live_write(
        execution_mode=execution_mode,
        approval_token=approval_token,
        scope_ids=scope_ids or [payload.get("slug") or payload.get("name")],
        payload=write_payload,
        user=user or {},
        is_live=IS_LIVE,
        object_type=object_type,
    )
    return await _live_create_product_category(payload)


async def update_product_category(
    term_id: int,
    payload: dict,
    *,
    execution_mode: str,
    approval_token: str = None,
    scope_ids: list = None,
    user: dict = None,
    object_type: str = "woocommerce_product_category",
) -> dict:
    if execution_mode == "mock":
        return await _mock_update_product_category(term_id, payload)

    if execution_mode != "live":
        raise WpWriteSafetyError(
            f"update_product_category() called with unsupported execution_mode={execution_mode!r}. "
            "Dry runs must not call update_product_category() at all -- build a preview instead."
        )

    write_payload = {"term_id": term_id, "taxonomy": "product_cat", **payload}
    await enforce_live_write(
        execution_mode=execution_mode,
        approval_token=approval_token,
        scope_ids=scope_ids or [str(term_id)],
        payload=write_payload,
        user=user or {},
        is_live=IS_LIVE,
        object_type=object_type,
    )
    return await _live_update_product_category(term_id, payload)


# ================== LIVE WORDPRESS REST API ==================

def _normalize_wp_page(wp_data: dict) -> dict:
    """Normalize a WP REST API page response into our standard format."""
    return {
        "id": str(wp_data.get("id", "")),
        "wp_id": wp_data.get("id"),
        "title": wp_data.get("title", {}).get("rendered", "") if isinstance(wp_data.get("title"), dict) else wp_data.get("title", ""),
        "slug": wp_data.get("slug", ""),
        "content": wp_data.get("content", {}).get("rendered", "") if isinstance(wp_data.get("content"), dict) else "",
        "status": wp_data.get("status", "draft"),
        "link": wp_data.get("link", ""),
        "seo_title": "",
        "meta_description": "",
        "created_at": wp_data.get("date", ""),
        "updated_at": wp_data.get("modified", ""),
        "mock": False,
    }


async def _live_create_page(title, slug, content, status, meta):
    payload = {
        "title": title,
        "slug": slug or "",
        "content": content,
        "status": status or "draft",
    }

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(f"{_api_base}/pages", headers=_headers, json=payload)

        if resp.status_code in (200, 201):
            wp_page = _normalize_wp_page(resp.json())
            logger.info(f"[WP Live] Created page: {title} (WP ID: {wp_page['wp_id']})")

            # Also store in local DB for tracking
            wp_page["local_created_at"] = datetime.now(timezone.utc).isoformat()
            await db.wp_live_pages.insert_one({**wp_page})

            return {k: v for k, v in wp_page.items() if k != "_id"}
        else:
            error_detail = resp.text[:500]
            logger.error(f"[WP Live] Create page failed ({resp.status_code}): {error_detail}")
            return None
    except Exception as e:
        logger.error(f"[WP Live] Create page error: {e}")
        return None


async def _live_update_page(page_id, content, title, slug, meta):
    wp_id = page_id
    if not wp_id.isdigit():
        # Check local DB for WP ID mapping
        local = await db.wp_live_pages.find_one({"id": page_id}, {"_id": 0})
        if local and local.get("wp_id"):
            wp_id = str(local["wp_id"])
        else:
            logger.error(f"[WP Live] Cannot resolve page ID: {page_id}")
            return None

    payload = {"content": content}
    if title:
        payload["title"] = title
    if slug:
        payload["slug"] = slug

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(f"{_api_base}/pages/{wp_id}", headers=_headers, json=payload)

        if resp.status_code == 200:
            wp_page = _normalize_wp_page(resp.json())
            logger.info(f"[WP Live] Updated page: {wp_id}")

            await db.wp_live_pages.update_one(
                {"wp_id": int(wp_id)},
                {"$set": {**{k: v for k, v in wp_page.items() if k != "_id"}, "local_updated_at": datetime.now(timezone.utc).isoformat()}},
                upsert=True,
            )
            return {k: v for k, v in wp_page.items() if k != "_id"}
        else:
            error_detail = resp.text[:500]
            logger.error(f"[WP Live] Update page failed ({resp.status_code}): {error_detail}")
            return None
    except Exception as e:
        logger.error(f"[WP Live] Update page error: {e}")
        return None


async def _live_get_pages(status, per_page):
    params = {"per_page": per_page, "orderby": "modified", "order": "desc"}
    if status:
        params["status"] = status

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.get(f"{_api_base}/pages", headers=_headers, params=params)

        if resp.status_code == 200:
            pages = [_normalize_wp_page(p) for p in resp.json()]
            logger.info(f"[WP Live] Fetched {len(pages)} pages (status={status})")
            return pages
        else:
            logger.error(f"[WP Live] Get pages failed ({resp.status_code}): {resp.text[:300]}")
            return []
    except Exception as e:
        logger.error(f"[WP Live] Get pages error: {e}")
        return []


async def _live_get_page(page_id):
    wp_id = page_id
    if not wp_id.isdigit():
        local = await db.wp_live_pages.find_one({"id": page_id}, {"_id": 0})
        if local and local.get("wp_id"):
            wp_id = str(local["wp_id"])
        else:
            return None

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.get(f"{_api_base}/pages/{wp_id}", headers=_headers, params={"context": "edit"})

        if resp.status_code == 200:
            data = resp.json()
            page = _normalize_wp_page(data)
            # Prefer raw content for editing (shortcodes preserved)
            raw_content = data.get("content", {}).get("raw", "")
            if raw_content:
                page["content"] = raw_content
            return page
        else:
            logger.error(f"[WP Live] Get page failed ({resp.status_code})")
            return None
    except Exception as e:
        logger.error(f"[WP Live] Get page error: {e}")
        return None


def _normalize_wp_category(wp_data: dict) -> dict:
    """Normalize a WP REST API product_cat term response into our standard format."""
    return {
        "term_id": wp_data.get("id"),
        "name": wp_data.get("name", ""),
        "slug": wp_data.get("slug", ""),
        "description": wp_data.get("description", ""),
        "parent": wp_data.get("parent", 0),
        "count": wp_data.get("count", 0),
        "link": wp_data.get("link", ""),
        "taxonomy": wp_data.get("taxonomy", "product_cat"),
        "object_type": "woocommerce_product_category",
        "mock": False,
    }


async def _live_get_product_category(term_id: int):
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.get(f"{_api_base}/product_cat/{term_id}", headers=_headers, params={"context": "edit"})

        if resp.status_code == 200:
            return _normalize_wp_category(resp.json())
        else:
            logger.error(f"[WP Live] Get product_cat failed ({resp.status_code}): {resp.text[:300]}")
            return None
    except Exception as e:
        logger.error(f"[WP Live] Get product_cat error: {e}")
        return None


async def _live_find_product_category_by_slug(slug: str):
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.get(f"{_api_base}/product_cat", headers=_headers, params={"slug": slug})

        if resp.status_code == 200:
            results = resp.json()
            return _normalize_wp_category(results[0]) if results else None
        else:
            logger.error(f"[WP Live] Find product_cat by slug failed ({resp.status_code}): {resp.text[:300]}")
            return None
    except Exception as e:
        logger.error(f"[WP Live] Find product_cat by slug error: {e}")
        return None


async def _live_create_product_category(payload: dict):
    body = {
        "name": payload.get("name"),
        "slug": payload.get("slug") or "",
        "description": payload.get("description", ""),
    }
    if payload.get("parent"):
        body["parent"] = payload["parent"]

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(f"{_api_base}/product_cat", headers=_headers, json=body)

        if resp.status_code in (200, 201):
            term = _normalize_wp_category(resp.json())
            logger.info(f"[WP Live] Created product category: {term['name']} (term_id: {term['term_id']})")

            term["local_created_at"] = datetime.now(timezone.utc).isoformat()
            await db.wp_live_product_categories.insert_one({**term})

            return {k: v for k, v in term.items() if k != "_id"}
        else:
            error_detail = resp.text[:500]
            logger.error(f"[WP Live] Create product_cat failed ({resp.status_code}): {error_detail}")
            return None
    except Exception as e:
        logger.error(f"[WP Live] Create product_cat error: {e}")
        return None


async def _live_update_product_category(term_id: int, payload: dict):
    body = {}
    if payload.get("name"):
        body["name"] = payload["name"]
    if payload.get("slug"):
        body["slug"] = payload["slug"]
    if "description" in payload:
        body["description"] = payload.get("description", "")
    if payload.get("parent") is not None:
        body["parent"] = payload["parent"]

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(f"{_api_base}/product_cat/{term_id}", headers=_headers, json=body)

        if resp.status_code == 200:
            term = _normalize_wp_category(resp.json())
            logger.info(f"[WP Live] Updated product category term: {term_id}")

            await db.wp_live_product_categories.update_one(
                {"term_id": term_id},
                {"$set": {**{k: v for k, v in term.items() if k != "_id"}, "local_updated_at": datetime.now(timezone.utc).isoformat()}},
                upsert=True,
            )
            return {k: v for k, v in term.items() if k != "_id"}
        else:
            error_detail = resp.text[:500]
            logger.error(f"[WP Live] Update product_cat failed ({resp.status_code}): {error_detail}")
            return None
    except Exception as e:
        logger.error(f"[WP Live] Update product_cat error: {e}")
        return None


# ================== MOCK IMPLEMENTATION ==================

async def _mock_create_page(title, slug, content, status, meta):
    now = datetime.now(timezone.utc).isoformat()
    page_id = f"wp-{uuid.uuid4().hex[:8]}"
    page = {
        "id": page_id,
        "wp_id": None,
        "title": title,
        "slug": slug or title.lower().replace(" ", "-")[:60],
        "content": content,
        "status": status,
        "seo_title": (meta or {}).get("seo_title", ""),
        "meta_description": (meta or {}).get("meta_description", ""),
        "link": f"https://yoursite.com/{slug or 'page'}",
        "created_at": now,
        "updated_at": now,
        "mock": True,
    }
    await db.wp_mock_pages.insert_one(page)
    logger.info(f"[WP Mock] Created page: {title} ({page_id})")
    return {k: v for k, v in page.items() if k != "_id"}


async def _mock_update_page(page_id, content, title, slug, meta):
    page = await db.wp_mock_pages.find_one({"id": page_id}, {"_id": 0})
    if not page:
        return None
    updates = {"content": content, "updated_at": datetime.now(timezone.utc).isoformat()}
    if title:
        updates["title"] = title
    if slug:
        updates["slug"] = slug
    if meta:
        if meta.get("seo_title"):
            updates["seo_title"] = meta["seo_title"]
        if meta.get("meta_description"):
            updates["meta_description"] = meta["meta_description"]
    await db.wp_mock_pages.update_one({"id": page_id}, {"$set": updates})
    updated = await db.wp_mock_pages.find_one({"id": page_id}, {"_id": 0})
    logger.info(f"[WP Mock] Updated page: {page_id}")
    return updated


async def _mock_get_pages(status, per_page):
    pages = []
    query = {}
    if status:
        query["status"] = status
    async for doc in db.wp_mock_pages.find(query, {"_id": 0}).sort("updated_at", -1).limit(per_page):
        pages.append(doc)
    return pages


async def _mock_get_page(page_id):
    page = await db.wp_mock_pages.find_one({"id": page_id}, {"_id": 0})
    return page


async def _mock_get_product_category(term_id: int):
    return await db.wp_mock_product_categories.find_one({"term_id": term_id}, {"_id": 0})


async def _mock_find_product_category_by_slug(slug: str):
    return await db.wp_mock_product_categories.find_one({"slug": slug}, {"_id": 0})


async def _mock_create_product_category(payload: dict):
    now = datetime.now(timezone.utc).isoformat()
    # Synthetic numeric term_id, distinct range from real WooCommerce term
    # IDs and from the mock page "wp-xxxxxxxx" string IDs -- a term_id must
    # always be numeric, never confused with a page_id.
    term_id = 900000 + (uuid.uuid4().int % 99999)
    name = payload.get("name") or ""
    category = {
        "term_id": term_id,
        "name": name,
        "slug": payload.get("slug") or name.lower().replace(" ", "-")[:60],
        "description": payload.get("description", ""),
        "parent": payload.get("parent") or 0,
        "count": 0,
        "link": f"https://yoursite.com/product-category/{payload.get('slug', '')}",
        "taxonomy": "product_cat",
        "object_type": "woocommerce_product_category",
        "created_at": now,
        "updated_at": now,
        "mock": True,
    }
    await db.wp_mock_product_categories.insert_one(category)
    logger.info(f"[WP Mock] Created product category: {name} (term_id {term_id})")
    return {k: v for k, v in category.items() if k != "_id"}


async def _mock_update_product_category(term_id: int, payload: dict):
    category = await db.wp_mock_product_categories.find_one({"term_id": term_id}, {"_id": 0})
    if not category:
        return None
    updates = {"updated_at": datetime.now(timezone.utc).isoformat()}
    if payload.get("name"):
        updates["name"] = payload["name"]
    if payload.get("slug"):
        updates["slug"] = payload["slug"]
    if "description" in payload:
        updates["description"] = payload.get("description", "")
    if payload.get("parent") is not None:
        updates["parent"] = payload["parent"]
    await db.wp_mock_product_categories.update_one({"term_id": term_id}, {"$set": updates})
    logger.info(f"[WP Mock] Updated product category term: {term_id}")
    return await db.wp_mock_product_categories.find_one({"term_id": term_id}, {"_id": 0})
