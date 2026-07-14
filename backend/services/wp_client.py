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
