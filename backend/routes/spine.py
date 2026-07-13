"""
TS OPS Execution Spine v1 — API Routes.
Connects existing modules into one founder-side workflow system.
"""
import io
from fastapi import APIRouter, HTTPException, Depends
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import Optional

from database import db, logger
from auth import get_current_user
from services.helpers import log_activity
from services.spine import (
    sync_spine_tasks, get_dashboard_data, get_available_action,
    log_execution, SPINE_STATUSES,
)

spine_router = APIRouter(prefix="/api/spine")


# ================== DASHBOARD ==================

@spine_router.get("/dashboard")
async def spine_dashboard(user: dict = Depends(get_current_user)):
    """Main ops center — syncs from source modules, returns dashboard data."""
    await sync_spine_tasks()
    data = await get_dashboard_data()
    return data


# ================== SYNC ==================

@spine_router.post("/sync")
async def spine_sync(user: dict = Depends(get_current_user)):
    """Force-refresh spine tasks from all source modules."""
    synced = await sync_spine_tasks()
    return {"synced": synced, "message": "Spine synced from all source modules"}


# ================== TASKS ==================

@spine_router.get("/tasks")
async def list_tasks(
    status: Optional[str] = None,
    source_module: Optional[str] = None,
    task_type: Optional[str] = None,
    user: dict = Depends(get_current_user),
):
    """List spine tasks with optional filters."""
    query = {}
    if status:
        query["status"] = status
    if source_module:
        query["source_module"] = source_module
    if task_type:
        query["type"] = task_type

    tasks = []
    async for doc in db.spine_tasks.find(query, {"_id": 0}).sort("last_synced_at", -1):
        action = get_available_action(doc)
        doc["available_action"] = action
        tasks.append(doc)

    return {"tasks": tasks, "count": len(tasks)}


# ================== STATUS UPDATE ==================

class UpdateStatusRequest(BaseModel):
    status: str
    note: str = ""


@spine_router.post("/tasks/{ref_id}/status")
async def update_task_status(ref_id: str, request: UpdateStatusRequest, user: dict = Depends(get_current_user)):
    """Manually override a spine task status (founder decision)."""
    if request.status not in SPINE_STATUSES:
        raise HTTPException(status_code=400, detail=f"Invalid status: {request.status}. Valid: {SPINE_STATUSES}")

    task = await db.spine_tasks.find_one({"ref_id": ref_id}, {"_id": 0})
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    old_status = task.get("status", "unknown")
    from datetime import datetime, timezone
    now = datetime.now(timezone.utc).isoformat()

    await db.spine_tasks.update_one({"ref_id": ref_id}, {"$set": {
        "status": request.status,
        "updated_at": now,
    }})

    await log_execution(
        task_id=ref_id,
        action="manual_status_update",
        source_module=task.get("source_module", ""),
        target_module="",
        result="success",
        status_before=old_status,
        status_after=request.status,
        details=request.note or f"Manual status change: {old_status} → {request.status}",
    )

    await log_activity("spine_status_update", details=f"Spine: {task.get('title', ref_id)} status {old_status} → {request.status}")
    return {"ref_id": ref_id, "old_status": old_status, "new_status": request.status}


# ================== EXECUTE ACTIONS ==================

@spine_router.post("/tasks/{ref_id}/execute")
async def execute_task_action(ref_id: str, user: dict = Depends(get_current_user)):
    """Execute the next routing action for a task. Founder-triggered only."""
    task = await db.spine_tasks.find_one({"ref_id": ref_id}, {"_id": 0})
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    action = get_available_action(task)
    if not action:
        raise HTTPException(status_code=400, detail=f"No action available for task in status '{task.get('status')}'")

    old_status = task["status"]
    action_name = action["action"]

    try:
        if action_name == "wp_place":
            result = await _execute_wp_place(task)
        elif action_name == "woo_export":
            result = await _execute_woo_export(task)
        elif action_name == "generate_packs":
            result = await _execute_generate_packs(task)
        else:
            raise HTTPException(status_code=400, detail=f"Unknown action: {action_name}")

        # Log success
        new_status = result.get("new_status", old_status)
        await log_execution(
            task_id=ref_id,
            action=action_name,
            source_module=task.get("source_module", ""),
            target_module=action.get("target_module", ""),
            result="success",
            status_before=old_status,
            status_after=new_status,
            details=result.get("details", ""),
            warnings=result.get("warnings", []),
        )

        await log_activity("spine_execution", details=f"Spine: {action['label']} for {task.get('title', ref_id)}")

        # Re-sync to pick up changes
        await sync_spine_tasks()

        return {
            "action": action_name,
            "result": "success",
            "old_status": old_status,
            "new_status": new_status,
            "details": result.get("details", ""),
            "warnings": result.get("warnings", []),
            "data": result.get("data"),
        }

    except HTTPException:
        raise
    except Exception as e:
        # Log failure
        await log_execution(
            task_id=ref_id,
            action=action_name,
            source_module=task.get("source_module", ""),
            target_module=action.get("target_module", ""),
            result="failed",
            status_before=old_status,
            status_after=old_status,
            details=str(e)[:500],
        )
        logger.error(f"[Spine] Execution failed for {ref_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Execution failed: {str(e)[:200]}")


# ---- Execution Handlers ----

async def _execute_wp_place(task: dict) -> dict:
    """Place an approved page into WordPress via WP Placement module."""
    page_id = task["ref_id"]
    page = await db.pages.find_one({"id": page_id}, {"_id": 0})
    if not page:
        raise HTTPException(status_code=404, detail="Source page not found")

    warnings = []

    # Check for generated content
    sections = page.get("generated_sections", {})
    headline = sections.get("headline") or page.get("headline", "")
    intro = sections.get("intro") or ""
    body1 = sections.get("body_section_1") or sections.get("body", "") or ""

    if not headline and not body1:
        warnings.append("Page has no generated content. WP draft may be minimal.")

    # Use WP Placement engine directly
    from services.wp_placement import create_page
    from routes.wp_placement import get_wp_settings

    settings = await get_wp_settings()
    page_name = page.get("page_name", "Untitled")
    slug = page.get("slug", "") or page_name.lower().replace(" ", "-")[:60]

    # Build basic HTML content from whatever sections exist
    content_parts = []
    if headline:
        content_parts.append(f"<h1>{headline}</h1>")
    if intro:
        content_parts.append(f"<p>{intro}</p>")
    if body1:
        content_parts.append(f"<div>{body1}</div>")
    if sections.get("body_section_2"):
        content_parts.append(f"<div>{sections['body_section_2']}</div>")
    if sections.get("cta_text"):
        cta_url = sections.get("cta_url", "#")
        content_parts.append(f'<p><a href="{cta_url}">{sections["cta_text"]}</a></p>')

    html_content = "\n".join(content_parts) if content_parts else f"<h1>{page_name}</h1><p>Content pending.</p>"

    try:
        wp_page = await create_page(
            title=page_name,
            slug=slug,
            content=html_content,
            status=settings.get("default_status", "draft"),
            meta={},
        )

        # Update page status
        from datetime import datetime, timezone
        now = datetime.now(timezone.utc).isoformat()
        await db.pages.update_one({"id": page_id}, {"$set": {"status": "Placed", "updated_at": now}})

        # Log in WP placement log
        await db.wp_placement_log.insert_one({
            "page_id": page_id,
            "page_name": page_name,
            "wp_page_id": wp_page.get("id"),
            "wp_url": wp_page.get("link", ""),
            "template_id": "spine_direct",
            "mode": "create",
            "status": "success",
            "created_at": now,
        })

        return {
            "new_status": "drafted",
            "details": f"Created WP draft: {page_name} (WP ID: {wp_page.get('id')})",
            "warnings": warnings,
            "data": {"wp_url": wp_page.get("link", ""), "wp_id": wp_page.get("id")},
        }
    except Exception as e:
        raise Exception(f"WP Placement failed: {e}")


async def _execute_woo_export(task: dict) -> dict:
    """Export intake session as WooCommerce CSV."""
    session_id = task["ref_id"]
    session = await db.intake_sessions.find_one({"id": session_id}, {"_id": 0})
    if not session:
        raise HTTPException(status_code=404, detail="Intake session not found")

    warnings = []
    ready_count = session.get("ready_count", 0)
    total = session.get("item_count", 0)

    if ready_count == 0:
        raise HTTPException(status_code=400, detail="No ready items to export")

    if ready_count < total:
        warnings.append(f"Only {ready_count}/{total} items are ready. Non-ready items will be skipped.")

    # Build CSV using existing export logic
    from routes.product_intake import build_woo_csv_content
    csv_content = await build_woo_csv_content(session_id)

    return {
        "new_status": "exported",
        "details": f"Exported {ready_count} items as WooCommerce CSV from {session.get('source_store', '')}",
        "warnings": warnings,
        "data": {"csv_preview": csv_content[:500] if csv_content else "", "ready_count": ready_count},
    }


async def _execute_generate_packs(task: dict) -> dict:
    """Generate destination packs for a field-listing batch."""
    batch_id = task["ref_id"]
    batch = await db.field_batches.find_one({"id": batch_id}, {"_id": 0})
    if not batch:
        raise HTTPException(status_code=404, detail="Field batch not found")

    destinations = batch.get("destinations", ["website", "offerup", "facebook"])
    warnings = []

    # Get items
    items = []
    async for doc in db.field_items.find(
        {"batch_id": batch_id, "status": {"$in": ["review", "approved"]}},
        {"_id": 0}
    ):
        items.append(doc)

    if not items:
        raise HTTPException(status_code=400, detail="No items available for pack generation")

    # Generate packs using existing service
    from services.field_listing import generate_destination_pack, generate_website_page_pack
    from datetime import datetime, timezone
    now = datetime.now(timezone.utc).isoformat()

    for item in items:
        packs = {}
        for dest in destinations:
            packs[dest] = generate_destination_pack(item, dest, batch)
        await db.field_items.update_one({"id": item["id"]}, {"$set": {
            "destination_packs": packs,
            "updated_at": now,
        }})

    website_page = generate_website_page_pack(items, batch) if "website" in destinations else ""
    await db.field_batches.update_one({"id": batch_id}, {"$set": {
        "website_page_pack": website_page,
        "packs_generated_at": now,
        "status": "complete",
        "updated_at": now,
    }})

    return {
        "new_status": "done",
        "details": f"Generated packs for {len(items)} items across {len(destinations)} destinations",
        "warnings": warnings,
        "data": {"item_count": len(items), "destinations": destinations},
    }


# ================== EXECUTION LOG ==================

@spine_router.get("/log")
async def get_execution_log(limit: int = 20, user: dict = Depends(get_current_user)):
    """View recent execution history."""
    entries = []
    async for doc in db.spine_execution_log.find({}, {"_id": 0}).sort("executed_at", -1).limit(limit):
        entries.append(doc)
    return {"log": entries}
