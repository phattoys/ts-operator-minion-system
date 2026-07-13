"""
TS OPS Execution Spine v1 — Orchestration layer connecting existing modules.
Handles: signal intake, status tracking, routing, execution actions, and logging.
Source modules still own their deep records. The spine reflects and routes work.
"""
from datetime import datetime, timezone
from database import db, logger

# ---- Normalized Status Set ----
SPINE_STATUSES = [
    "new", "processing", "needs_review", "ready",
    "exported", "drafted", "placed", "done",
    "skipped", "held_back",
]

# ---- Status Normalization Maps ----

def normalize_page_status(page: dict) -> dict:
    """Map Page Ops status to spine status + next action."""
    raw = (page.get("status") or "").lower().strip()
    mapping = {
        "planned": ("new", "Generate content", True),
        "needs review": ("needs_review", "Review and approve", True),
        "draft ready": ("ready", "Place in WordPress", True),
        "approved": ("ready", "Place in WordPress", True),
        "deferred": ("held_back", "Deferred — revisit later", False),
        "placed": ("placed", "Done — live in WordPress", False),
    }
    status, next_action, founder_needed = mapping.get(raw, ("new", "Unknown status", True))
    next_module = "wp_placement" if status == "ready" else ""

    return {
        "type": "page",
        "source_module": "page_ops",
        "ref_id": page.get("id", ""),
        "title": page.get("page_name", "Untitled Page"),
        "summary": f"{page.get('page_type', '')} | P{page.get('priority_score', 0)} | Q{page.get('quality_score', 0)}".strip(" |"),
        "status": status,
        "next_action": next_action,
        "next_module": next_module,
        "founder_action_required": founder_needed,
        "metadata": {
            "page_type": page.get("page_type", ""),
            "priority_score": page.get("priority_score", 0),
            "quality_score": page.get("quality_score", 0),
            "district": page.get("district_or_pillar", ""),
            "slug": page.get("slug", ""),
        },
    }


def normalize_intake_session(session: dict) -> dict:
    """Map Product Intake session to spine status + next action."""
    total = session.get("item_count", 0)
    ready = session.get("ready_count", 0)
    needs_info = session.get("needs_info_count", 0)
    in_review = session.get("in_review_count", 0)

    if total == 0:
        status, next_action, founder_needed = "new", "Add items to session", True
    elif ready == total:
        status, next_action, founder_needed = "ready", "Export WooCommerce CSV", True
    elif ready > 0 and needs_info == 0 and in_review == 0:
        status, next_action, founder_needed = "ready", "Export WooCommerce CSV", True
    elif in_review > 0 or needs_info > 0:
        status, next_action, founder_needed = "needs_review", f"Review {needs_info + in_review} items", True
    else:
        status, next_action, founder_needed = "processing", "Items being processed", False

    next_module = "product_intake" if status in ("needs_review", "ready") else ""

    return {
        "type": "intake_session",
        "source_module": "product_intake",
        "ref_id": session.get("id", ""),
        "title": f"{session.get('source_store', 'Unknown')} — {session.get('order_id', '')}".strip(" —"),
        "summary": f"{total} items: {ready} ready, {in_review} reviewing, {needs_info} needs info",
        "status": status,
        "next_action": next_action,
        "next_module": next_module,
        "founder_action_required": founder_needed,
        "metadata": {
            "source_store": session.get("source_store", ""),
            "order_id": session.get("order_id", ""),
            "item_count": total,
            "ready_count": ready,
            "needs_info_count": needs_info,
            "in_review_count": in_review,
        },
    }


def normalize_field_batch(batch: dict) -> dict:
    """Map Field-to-Listing batch to spine status + next action."""
    raw = (batch.get("status") or "").lower().strip()
    items = batch.get("item_count", 0)

    mapping = {
        "intake": ("new", "Upload photos and analyze", True),
        "processing": ("processing", "Vision AI analyzing photos...", False),
        "review": ("needs_review", "Review items and approve", True),
        "complete": ("ready", "Generate destination packs", True),
    }
    status, next_action, founder_needed = mapping.get(raw, ("new", "Set up batch", True))

    # If batch has packs generated, it's further along
    if batch.get("packs_generated_at"):
        status, next_action, founder_needed = "done", "Packs generated — copy and use", False

    next_module = "field_listing" if status in ("needs_review", "ready") else ""

    return {
        "type": "field_batch",
        "source_module": "field_listing",
        "ref_id": batch.get("id", ""),
        "title": batch.get("name", "Untitled Batch"),
        "summary": f"{items} items | {batch.get('source_vendor', '')}".strip(" |"),
        "status": status,
        "next_action": next_action,
        "next_module": next_module,
        "founder_action_required": founder_needed,
        "metadata": {
            "source_vendor": batch.get("source_vendor", ""),
            "item_count": items,
            "destinations": batch.get("destinations", []),
            "pricing_note": batch.get("grouped_pricing_note", ""),
        },
    }


# ---- Sync Engine ----

async def sync_spine_tasks():
    """Pull current state from all source modules and upsert into spine_tasks.
    Source modules own the truth — spine reflects and routes.
    """
    now = datetime.now(timezone.utc).isoformat()
    synced = {"pages": 0, "intake": 0, "field": 0}

    # Sync Page Ops pages
    async for page in db.pages.find({}, {"_id": 0}):
        task_data = normalize_page_status(page)
        task_data["last_synced_at"] = now
        await db.spine_tasks.update_one(
            {"source_module": "page_ops", "ref_id": task_data["ref_id"]},
            {"$set": task_data, "$setOnInsert": {"created_at": now}},
            upsert=True,
        )
        synced["pages"] += 1

    # Sync Product Intake sessions
    async for session in db.intake_sessions.find({}, {"_id": 0}):
        task_data = normalize_intake_session(session)
        task_data["last_synced_at"] = now
        await db.spine_tasks.update_one(
            {"source_module": "product_intake", "ref_id": task_data["ref_id"]},
            {"$set": task_data, "$setOnInsert": {"created_at": now}},
            upsert=True,
        )
        synced["intake"] += 1

    # Sync Field-to-Listing batches
    async for batch in db.field_batches.find({}, {"_id": 0}):
        task_data = normalize_field_batch(batch)
        task_data["last_synced_at"] = now
        await db.spine_tasks.update_one(
            {"source_module": "field_listing", "ref_id": task_data["ref_id"]},
            {"$set": task_data, "$setOnInsert": {"created_at": now}},
            upsert=True,
        )
        synced["field"] += 1

    # Clean up tasks for deleted source items
    all_page_ids = set()
    async for p in db.pages.find({}, {"id": 1, "_id": 0}):
        all_page_ids.add(p["id"])
    await db.spine_tasks.delete_many({
        "source_module": "page_ops",
        "ref_id": {"$nin": list(all_page_ids)},
    })

    all_session_ids = set()
    async for s in db.intake_sessions.find({}, {"id": 1, "_id": 0}):
        all_session_ids.add(s["id"])
    await db.spine_tasks.delete_many({
        "source_module": "product_intake",
        "ref_id": {"$nin": list(all_session_ids)},
    })

    all_batch_ids = set()
    async for b in db.field_batches.find({}, {"id": 1, "_id": 0}):
        all_batch_ids.add(b["id"])
    await db.spine_tasks.delete_many({
        "source_module": "field_listing",
        "ref_id": {"$nin": list(all_batch_ids)},
    })

    logger.info(f"[Spine] Synced: {synced['pages']} pages, {synced['intake']} intake sessions, {synced['field']} field batches")
    return synced


# ---- Routing Rules ----

ROUTING_RULES = {
    ("page", "ready"): {
        "action": "wp_place",
        "label": "Place in WordPress",
        "target_module": "wp_placement",
    },
    ("intake_session", "ready"): {
        "action": "woo_export",
        "label": "Export WooCommerce CSV",
        "target_module": "product_intake",
    },
    ("field_batch", "ready"): {
        "action": "generate_packs",
        "label": "Generate Destination Packs",
        "target_module": "field_listing",
    },
}


def get_available_action(task: dict) -> dict | None:
    """Check if a task has an executable routing action available."""
    key = (task.get("type"), task.get("status"))
    return ROUTING_RULES.get(key)


# ---- Execution Log ----

async def log_execution(task_id: str, action: str, source_module: str,
                        target_module: str, result: str, status_before: str,
                        status_after: str, details: str = "", warnings: list = None):
    """Write an execution result to the spine log."""
    await db.spine_execution_log.insert_one({
        "task_id": task_id,
        "action": action,
        "source_module": source_module,
        "target_module": target_module,
        "result": result,
        "status_before": status_before,
        "status_after": status_after,
        "details": details,
        "warnings": warnings or [],
        "executed_at": datetime.now(timezone.utc).isoformat(),
    })


# ---- Dashboard Aggregation ----

async def get_dashboard_data():
    """Aggregate spine tasks into dashboard sections."""
    tasks = []
    async for doc in db.spine_tasks.find({}, {"_id": 0}).sort("last_synced_at", -1):
        action = get_available_action(doc)
        doc["available_action"] = action
        tasks.append(doc)

    needs_action = [t for t in tasks if t.get("founder_action_required") and t["status"] not in ("done", "placed", "exported")]
    in_progress = [t for t in tasks if t["status"] == "processing"]
    ready_to_execute = [t for t in tasks if t.get("available_action") and t["status"] == "ready"]
    recently_completed = [t for t in tasks if t["status"] in ("done", "placed", "exported", "drafted")]
    held_back = [t for t in tasks if t["status"] in ("held_back", "skipped")]

    # Module health
    module_health = {}
    for module in ["page_ops", "product_intake", "field_listing"]:
        module_tasks = [t for t in tasks if t["source_module"] == module]
        module_health[module] = {
            "total": len(module_tasks),
            "needs_action": len([t for t in module_tasks if t.get("founder_action_required") and t["status"] not in ("done", "placed", "exported")]),
            "ready": len([t for t in module_tasks if t["status"] == "ready"]),
            "done": len([t for t in module_tasks if t["status"] in ("done", "placed", "exported", "drafted")]),
        }

    # Status breakdown
    status_counts = {}
    for t in tasks:
        s = t["status"]
        status_counts[s] = status_counts.get(s, 0) + 1

    # Recent execution log
    recent_log = []
    async for entry in db.spine_execution_log.find({}, {"_id": 0}).sort("executed_at", -1).limit(10):
        recent_log.append(entry)

    return {
        "total_tasks": len(tasks),
        "needs_action": needs_action,
        "in_progress": in_progress,
        "ready_to_execute": ready_to_execute,
        "recently_completed": recently_completed,
        "held_back": held_back,
        "module_health": module_health,
        "status_counts": status_counts,
        "recent_log": recent_log,
    }
