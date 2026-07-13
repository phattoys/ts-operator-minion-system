from fastapi import APIRouter, HTTPException, Depends
from typing import Optional
from datetime import datetime, timezone
import uuid

from database import db, logger
from models import WpPlacementRequest, WpPlacementSettingsUpdate, WP_PLACEMENT_MODES
from auth import get_current_user
from services.helpers import log_activity
from services.wp_templates import list_templates, get_template, infer_template, UX_BLOCKS
from services.wp_placement import build_page_content
from services.wp_client import create_page, update_page, get_pages, get_page, IS_LIVE

wp_placement_router = APIRouter(prefix="/api/wp-placement")


# ================== HELPERS ==================

async def get_wp_settings() -> dict:
    settings = await db.wp_settings.find_one({}, {"_id": 0})
    if not settings:
        settings = {
            "default_status": "draft",
            "preserve_slug_on_update": True,
            "preserve_unmapped_on_update": True,
            "flag_missing_cta": True,
            "save_placement_log": True,
        }
        await db.wp_settings.insert_one(settings)
    return settings


# ================== TEMPLATES ==================

@wp_placement_router.get("/templates")
async def get_templates(user: dict = Depends(get_current_user)):
    return {"templates": list_templates(), "ux_blocks": list(UX_BLOCKS.keys()), "wp_connected": IS_LIVE}


@wp_placement_router.get("/templates/{template_id}")
async def get_template_detail(template_id: str, user: dict = Depends(get_current_user)):
    tpl = get_template(template_id)
    if not tpl:
        raise HTTPException(status_code=404, detail="Template not found")
    return tpl


# ================== PLACEMENT ==================

@wp_placement_router.post("/place")
async def run_placement(
    request: WpPlacementRequest,
    user: dict = Depends(get_current_user),
):
    if request.mode not in WP_PLACEMENT_MODES:
        raise HTTPException(status_code=400, detail=f"Mode must be one of: {WP_PLACEMENT_MODES}")

    if not request.page_title or not request.page_title.strip():
        raise HTTPException(status_code=400, detail="Page title is required")

    # Resolve template — auto-infer if page_type provided
    template_id = request.template_id
    inference_result = None
    if request.page_type:
        inference_result = infer_template(
            page_type=request.page_type,
            title=request.page_title or "",
            content=f"{request.hero_headline or ''} {request.intro or ''} {request.body_section_1 or ''}",
        )
        if not request.template_id or request.template_id == "standard_content":
            template_id = inference_result["template_id"]

    template = get_template(template_id)
    if not template:
        raise HTTPException(status_code=400, detail=f"Unknown template: {template_id}")

    settings = await get_wp_settings()

    # Build content dict from request
    content = {
        "hero_headline": (request.hero_headline or "").strip(),
        "subheadline": (request.subheadline or "").strip(),
        "intro": (request.intro or "").strip(),
        "body_section_1": (request.body_section_1 or "").strip(),
        "body_section_2": (request.body_section_2 or "").strip(),
        "body_section_3": (request.body_section_3 or "").strip(),
        "cta_text": (request.cta_text or "").strip(),
        "cta_url": (request.cta_url or "").strip(),
        "related_links": request.related_links or [],
    }

    # Run placement engine
    result = build_page_content(template, content)

    meta = {}
    if request.seo_title:
        meta["seo_title"] = request.seo_title.strip()
    if request.meta_description:
        meta["meta_description"] = request.meta_description.strip()

    slug = (request.slug or "").strip() or request.page_title.lower().replace(" ", "-")[:60]

    # Create or update
    wp_page = None
    if request.mode == "create":
        wp_page = await create_page(
            title=request.page_title.strip(),
            slug=slug,
            content=result["html"],
            status=settings.get("default_status", "draft"),
            meta=meta,
        )
    elif request.mode == "update":
        if not request.target_page_id:
            raise HTTPException(status_code=400, detail="target_page_id is required for update mode")
        existing = await get_page(request.target_page_id)
        if not existing:
            raise HTTPException(status_code=404, detail="Target page not found")
        update_slug = None if settings.get("preserve_slug_on_update") else slug
        wp_page = await update_page(
            page_id=request.target_page_id,
            content=result["html"],
            title=request.page_title.strip(),
            slug=update_slug,
            meta=meta,
        )

    if not wp_page:
        raise HTTPException(status_code=500, detail="WordPress page operation failed")

    # Build placement record
    now = datetime.now(timezone.utc).isoformat()
    placement = {
        "id": str(uuid.uuid4()),
        "mode": request.mode,
        "page_id": wp_page.get("id"),
        "page_title": request.page_title.strip(),
        "slug": wp_page.get("slug", slug),
        "template_id": template_id,
        "template_name": template["name"],
        "inference": inference_result,
        "sections_placed": result["sections_placed"],
        "sections_skipped": result["sections_skipped"],
        "warnings": result["warnings"],
        "wp_connected": IS_LIVE,
        "status": settings.get("default_status", "draft"),
        "created_at": now,
    }

    if inference_result and inference_result.get("needs_review"):
        placement["warnings"].append(f"Template auto-inferred ({inference_result['confidence']} confidence): {inference_result.get('reason') or 'verify selection'}")

    if settings.get("save_placement_log", True):
        await db.wp_placements.insert_one(placement)

    await log_activity("wp_placement", details=f"{'Created' if request.mode == 'create' else 'Updated'} page: {request.page_title.strip()} ({template['name']})")

    return {
        "placement": {k: v for k, v in placement.items() if k != "_id"},
        "page": wp_page,
        "html_preview": result["html"],
    }


# ================== AUTO-INFER TEMPLATE ==================

@wp_placement_router.post("/infer-template")
async def infer_template_endpoint(
    page_type: str = "",
    title: str = "",
    content: str = "",
    user: dict = Depends(get_current_user),
):
    result = infer_template(page_type=page_type, title=title, content=content)
    tpl = get_template(result["template_id"])
    result["template_name"] = tpl["name"] if tpl else "Unknown"
    return result


# ================== IMPORT FROM PAGE OPS ==================

@wp_placement_router.post("/import-from-pages/{page_id}")
async def import_from_page_ops(page_id: str, user: dict = Depends(get_current_user)):
    from services.wp_formatter import parse_content_into_sections

    page = await db.pages.find_one({"id": page_id}, {"_id": 0})
    if not page:
        raise HTTPException(status_code=404, detail="Page not found in Page Ops")

    content = page.get("generated_content", "")
    if not content:
        raise HTTPException(status_code=400, detail="Page has no generated content")

    # Parse content with proper formatting
    parsed = parse_content_into_sections(content)
    body_sections = parsed["body_sections"]

    return {
        "page_id": page_id,
        "page_name": page.get("page_name", ""),
        "page_type": page.get("page_type", ""),
        "page_family": page.get("page_family", ""),
        "prefilled": {
            "page_title": page.get("page_name", ""),
            "slug": page.get("slug", ""),
            "page_type": page.get("page_type", ""),
            "hero_headline": parsed["hero"],
            "intro": parsed["intro"],
            "body_section_1": body_sections[0] if len(body_sections) > 0 else "",
            "body_section_2": body_sections[1] if len(body_sections) > 1 else "",
            "body_section_3": "\n".join(body_sections[2:]) if len(body_sections) > 2 else "",
        },
        "inference": infer_template(
            page_type=page.get("page_type", ""),
            title=page.get("page_name", ""),
            content=content[:500],
        ),
    }


# ================== DRAFTS (WP Pages) ==================

@wp_placement_router.get("/drafts")
async def list_drafts(
    status: Optional[str] = "draft",
    user: dict = Depends(get_current_user),
):
    pages = await get_pages(status=status)
    return {"pages": pages, "count": len(pages), "wp_connected": IS_LIVE}


@wp_placement_router.get("/drafts/{page_id}")
async def get_draft(page_id: str, user: dict = Depends(get_current_user)):
    page = await get_page(page_id)
    if not page:
        raise HTTPException(status_code=404, detail="Page not found")
    return page


# ================== PLACEMENT LOG ==================

@wp_placement_router.get("/log")
async def get_placement_log(
    limit: int = 50,
    user: dict = Depends(get_current_user),
):
    logs = []
    async for doc in db.wp_placements.find({}, {"_id": 0}).sort("created_at", -1).limit(limit):
        logs.append(doc)
    return {"placements": logs, "count": len(logs)}


@wp_placement_router.get("/log/{placement_id}")
async def get_placement_detail(placement_id: str, user: dict = Depends(get_current_user)):
    p = await db.wp_placements.find_one({"id": placement_id}, {"_id": 0})
    if not p:
        raise HTTPException(status_code=404, detail="Placement not found")
    return p


# ================== STATS ==================

@wp_placement_router.get("/stats")
async def placement_stats(user: dict = Depends(get_current_user)):
    total_placements = await db.wp_placements.count_documents({})
    creates = await db.wp_placements.count_documents({"mode": "create"})
    updates = await db.wp_placements.count_documents({"mode": "update"})

    by_template = {}
    async for doc in db.wp_placements.aggregate([
        {"$group": {"_id": "$template_id", "count": {"$sum": 1}}}
    ]):
        by_template[doc["_id"]] = doc["count"]

    return {
        "total_placements": total_placements,
        "creates": creates,
        "updates": updates,
        "by_template": by_template,
        "wp_connected": IS_LIVE,
    }


# ================== SETTINGS ==================

@wp_placement_router.get("/settings")
async def get_settings(user: dict = Depends(get_current_user)):
    settings = await get_wp_settings()
    settings["wp_connected"] = IS_LIVE
    return settings


@wp_placement_router.put("/settings")
async def update_settings(
    request: WpPlacementSettingsUpdate,
    user: dict = Depends(get_current_user),
):
    await get_wp_settings()
    updates = {}
    for field, value in request.dict(exclude_unset=True).items():
        if value is not None:
            updates[field] = value

    if updates:
        await db.wp_settings.update_one({}, {"$set": updates}, upsert=True)
        await log_activity("wp_settings_updated", details=f"Updated WP placement settings: {', '.join(updates.keys())}")

    return await get_wp_settings()
