"""
Founder Command Center — Aggregation logic for page launch queue,
blocking dependencies, today's actions, and page code generation.
"""
from datetime import datetime, timezone
from database import db, logger


# ---- Page Code Scheme ----

FAMILY_CODE_MAP = {
    "Core Hub": "CH",
    "District": "D",
    "Trust": "T",
    "FAQ/Support": "S",
    "Guided Path": "GP",
    "Conversion": "C",
    "Category Support": "CS",
    "Media/Asset": "A",
    "Digital/Tools": "DG",
}


async def generate_page_code(page_family: str, existing_codes: list[str] = None) -> str:
    """Auto-generate a page code like CH1, D2, T3 based on family."""
    prefix = FAMILY_CODE_MAP.get(page_family, "P")

    if existing_codes is None:
        existing_codes = []
        async for doc in db.pages.find({"page_family": page_family, "page_code": {"$exists": True}}, {"page_code": 1, "_id": 0}):
            if doc.get("page_code"):
                existing_codes.append(doc["page_code"])

    max_num = 0
    for code in existing_codes:
        if code.startswith(prefix):
            try:
                num = int(code[len(prefix):])
                max_num = max(max_num, num)
            except ValueError:
                pass

    return f"{prefix}{max_num + 1}"


async def ensure_all_page_codes():
    """Assign page codes to any pages missing them."""
    pages_without_codes = []
    async for doc in db.pages.find(
        {"$or": [{"page_code": {"$exists": False}}, {"page_code": None}, {"page_code": ""}]},
        {"_id": 0, "id": 1, "page_family": 1, "page_name": 1, "created_at": 1}
    ).sort("created_at", 1):
        pages_without_codes.append(doc)

    if not pages_without_codes:
        return 0

    assigned = 0
    for page in pages_without_codes:
        code = await generate_page_code(page.get("page_family", ""))
        await db.pages.update_one({"id": page["id"]}, {"$set": {"page_code": code}})
        assigned += 1
        logger.info(f"[Command Center] Assigned code {code} to '{page.get('page_name')}'")

    return assigned


# ---- Dependency / Blocking Logic ----

async def compute_blocked_pages() -> list[dict]:
    """Find pages blocked because their parent page isn't approved/placed."""
    blocked = []

    async for page in db.pages.find(
        {"parent_page": {"$nin": [None, ""]}, "status": {"$nin": ["Approved", "placed"]}},
        {"_id": 0}
    ):
        parent_ref = page.get("parent_page", "")
        if not parent_ref:
            continue

        # Find parent by name or ID
        parent = await db.pages.find_one(
            {"$or": [{"id": parent_ref}, {"page_name": parent_ref}]},
            {"_id": 0, "id": 1, "page_name": 1, "status": 1, "page_code": 1}
        )

        if parent and parent.get("status") not in ["Approved", "placed"]:
            blocked.append({
                "page_id": page["id"],
                "page_name": page.get("page_name"),
                "page_code": page.get("page_code", ""),
                "status": page.get("status"),
                "blocked_by_id": parent["id"],
                "blocked_by_name": parent.get("page_name"),
                "blocked_by_code": parent.get("page_code", ""),
                "blocked_by_status": parent.get("status"),
                "reason": f"Parent '{parent.get('page_name')}' is {parent.get('status')} (needs Approved)",
            })

    return blocked


async def compute_next_unlocks() -> list[dict]:
    """Find what pages/batches unlock if current ready items are approved."""
    unlocks = []

    # Find pages that are parents of blocked children
    parent_ids = set()
    async for page in db.pages.find(
        {"parent_page": {"$nin": [None, ""]}},
        {"_id": 0, "parent_page": 1}
    ):
        parent_ids.add(page.get("parent_page", ""))

    for parent_ref in parent_ids:
        parent = await db.pages.find_one(
            {"$or": [{"id": parent_ref}, {"page_name": parent_ref}]},
            {"_id": 0, "id": 1, "page_name": 1, "status": 1, "page_code": 1}
        )
        if not parent:
            continue
        if parent.get("status") in ["Approved", "placed"]:
            continue

        # Count children that would unlock
        children = []
        async for child in db.pages.find(
            {"parent_page": {"$in": [parent["id"], parent.get("page_name", "")]}},
            {"_id": 0, "id": 1, "page_name": 1, "page_code": 1, "status": 1}
        ):
            children.append({
                "page_id": child["id"],
                "page_name": child.get("page_name"),
                "page_code": child.get("page_code", ""),
            })

        if children:
            unlocks.append({
                "approve_page_id": parent["id"],
                "approve_page_name": parent.get("page_name"),
                "approve_page_code": parent.get("page_code", ""),
                "approve_page_status": parent.get("status"),
                "unlocks_count": len(children),
                "unlocks": children,
            })

    return unlocks


# ---- Command Center Aggregation ----

async def get_command_center_data() -> dict:
    """Build the full Founder Command Center data."""
    # Ensure all pages have codes
    await ensure_all_page_codes()

    # Gather pages by status
    all_pages = []
    async for doc in db.pages.find({}, {"_id": 0}).sort("priority_score", -1):
        all_pages.append(doc)

    ready_for_review = [p for p in all_pages if p.get("status") in ["Draft Ready", "Needs Review"]]
    ready_to_launch = [p for p in all_pages if p.get("status") == "Approved"]
    launched = [p for p in all_pages if p.get("status") == "placed"]
    planned = [p for p in all_pages if p.get("status") == "Planned"]
    deferred = [p for p in all_pages if p.get("status") == "Deferred"]
    generating = [p for p in all_pages if p.get("status") == "Generating"]

    # Blocked pages
    blocked = await compute_blocked_pages()

    # Next unlocks
    next_unlocks = await compute_next_unlocks()

    # Pages that can be generated next (Planned with content=None)
    can_generate = [p for p in planned if not p.get("generated_content")]

    # Worker queue stats
    worker_tasks_ready = await db.worker_tasks.count_documents({"status": "queued", "founder_action_needed": True})
    worker_tasks_review = await db.worker_tasks.count_documents({"status": "needs_review"})

    # Build Today's Actions
    actions = []

    if ready_for_review:
        actions.append({
            "type": "review",
            "priority": "high",
            "message": f"{len(ready_for_review)} page{'s' if len(ready_for_review) != 1 else ''} ready for your review",
            "count": len(ready_for_review),
            "pages": [{"id": p["id"], "name": p.get("page_name"), "code": p.get("page_code", "")} for p in ready_for_review],
        })

    if ready_to_launch:
        actions.append({
            "type": "launch",
            "priority": "high",
            "message": f"{len(ready_to_launch)} page{'s' if len(ready_to_launch) != 1 else ''} approved and ready to launch",
            "count": len(ready_to_launch),
            "pages": [{"id": p["id"], "name": p.get("page_name"), "code": p.get("page_code", "")} for p in ready_to_launch],
        })

    if next_unlocks:
        total_unlockable = sum(u["unlocks_count"] for u in next_unlocks)
        parents_to_approve = len(next_unlocks)
        actions.append({
            "type": "unlock",
            "priority": "medium",
            "message": f"Approve {parents_to_approve} parent page{'s' if parents_to_approve != 1 else ''} to unlock {total_unlockable} child page{'s' if total_unlockable != 1 else ''}",
            "count": total_unlockable,
            "unlocks": next_unlocks,
        })

    if can_generate:
        actions.append({
            "type": "generate",
            "priority": "medium",
            "message": f"{len(can_generate)} page{'s' if len(can_generate) != 1 else ''} planned and ready to generate",
            "count": len(can_generate),
            "pages": [{"id": p["id"], "name": p.get("page_name"), "code": p.get("page_code", "")} for p in can_generate[:10]],
        })

    if worker_tasks_ready > 0:
        actions.append({
            "type": "worker_execute",
            "priority": "medium",
            "message": f"{worker_tasks_ready} worker task{'s' if worker_tasks_ready != 1 else ''} waiting for your action",
            "count": worker_tasks_ready,
        })

    if worker_tasks_review > 0:
        actions.append({
            "type": "worker_review",
            "priority": "low",
            "message": f"{worker_tasks_review} worker task{'s' if worker_tasks_review != 1 else ''} need your review",
            "count": worker_tasks_review,
        })

    if blocked:
        actions.append({
            "type": "blocked",
            "priority": "info",
            "message": f"{len(blocked)} page{'s' if len(blocked) != 1 else ''} blocked by parent dependencies",
            "count": len(blocked),
        })

    # Page Structure Map — compact view of all pages
    structure_map = []
    for p in sorted(all_pages, key=lambda x: (x.get("page_family", ""), x.get("page_code", ""))):
        structure_map.append({
            "id": p["id"],
            "page_code": p.get("page_code", ""),
            "page_name": p.get("page_name", ""),
            "public_title": p.get("public_title") or p.get("page_name", ""),
            "page_family": p.get("page_family", ""),
            "district": p.get("district_or_pillar", ""),
            "parent_page": p.get("parent_page") or "",
            "slug": p.get("slug", ""),
            "status": p.get("status", ""),
            "has_content": bool(p.get("generated_content")),
            "quality_score": p.get("quality_score"),
            "priority_score": p.get("priority_score", 50),
            "wp_page_id": p.get("wp_page_id"),
            "wp_placed_at": p.get("wp_placed_at"),
        })

    # Summary stats
    stats = {
        "total_pages": len(all_pages),
        "review_ready": len(ready_for_review),
        "launch_ready": len(ready_to_launch),
        "launched": len(launched),
        "planned": len(planned),
        "blocked": len(blocked),
        "deferred": len(deferred),
        "generating": len(generating),
        "can_generate": len(can_generate),
    }

    return {
        "stats": stats,
        "actions": actions,
        "ready_for_review": _slim_pages(ready_for_review),
        "ready_to_launch": _slim_pages(ready_to_launch),
        "launched": _slim_pages(launched),
        "blocked": blocked,
        "next_unlocks": next_unlocks,
        "structure_map": structure_map,
    }


def _slim_pages(pages: list) -> list:
    """Return a compact representation of pages for the command center."""
    return [{
        "id": p["id"],
        "page_code": p.get("page_code", ""),
        "page_name": p.get("page_name", ""),
        "page_family": p.get("page_family", ""),
        "district": p.get("district_or_pillar", ""),
        "status": p.get("status", ""),
        "has_content": bool(p.get("generated_content")),
        "quality_score": p.get("quality_score"),
        "priority_score": p.get("priority_score", 50),
        "slug": p.get("slug", ""),
        "wp_page_id": p.get("wp_page_id"),
    } for p in pages]
