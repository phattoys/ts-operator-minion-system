from fastapi import APIRouter, Depends
from datetime import datetime, timezone, timedelta

from database import db, logger
from auth import get_current_user
from services.catalog_service import find_duplicate_candidates

dashboard_router = APIRouter(prefix="/api/dashboard")


@dashboard_router.get("/health")
async def operator_health(user: dict = Depends(get_current_user)):
    now = datetime.now(timezone.utc)
    seven_days_ago = (now - timedelta(days=7)).isoformat()
    fourteen_days_ago = (now - timedelta(days=14)).isoformat()

    # ================== PAGE OPS ==================
    page_status_counts = {}
    async for doc in db.pages.aggregate([{"$group": {"_id": "$status", "count": {"$sum": 1}}}]):
        page_status_counts[doc["_id"]] = doc["count"]
    total_pages = sum(page_status_counts.values())
    pages_approved = page_status_counts.get("Approved", 0)

    # Pages created this week vs last week
    pages_this_week = await db.pages.count_documents({"created_at": {"$gte": seven_days_ago}})
    pages_last_week = await db.pages.count_documents({
        "created_at": {"$gte": fourteen_days_ago, "$lt": seven_days_ago}
    })

    # Stuck pages (Queued or Draft for > 7 days)
    stuck_pages = await db.pages.count_documents({
        "status": {"$in": ["Queued", "Draft"]},
        "created_at": {"$lte": seven_days_ago},
    })

    # ================== LEAD MAGNETS ==================
    lm_status_counts = {}
    async for doc in db.lead_magnets.aggregate([{"$group": {"_id": "$status", "count": {"$sum": 1}}}]):
        lm_status_counts[doc["_id"]] = doc["count"]
    total_magnets = sum(lm_status_counts.values())

    total_downloads = 0
    async for doc in db.lead_magnets.aggregate([
        {"$group": {"_id": None, "total": {"$sum": "$download_count"}}}
    ]):
        total_downloads = doc["total"]

    lm_published = lm_status_counts.get("Published", 0)
    lm_ready = lm_status_counts.get("Ready", 0)
    lm_drafts = lm_status_counts.get("Draft", 0)

    # ================== PRODUCT INTAKE ==================
    intake_status_counts = {}
    async for doc in db.draft_items.aggregate([{"$group": {"_id": "$status", "count": {"$sum": 1}}}]):
        intake_status_counts[doc["_id"]] = doc["count"]
    total_intake_items = sum(intake_status_counts.values())
    intake_ready = intake_status_counts.get("ready", 0)
    intake_needs_info = intake_status_counts.get("needs_info", 0)
    intake_in_review = intake_status_counts.get("in_review", 0)

    total_sessions = await db.intake_sessions.count_documents({})

    # Stuck intake items (needs_info for > 7 days)
    stuck_intake = await db.draft_items.count_documents({
        "status": "needs_info",
        "created_at": {"$lte": seven_days_ago},
    })

    # Revenue estimate from ready items
    revenue_estimate = 0.0
    async for doc in db.draft_items.aggregate([
        {"$match": {"status": "ready", "suggested_price": {"$gt": 0}}},
        {"$group": {"_id": None, "total": {
            "$sum": {"$multiply": ["$suggested_price", {"$ifNull": ["$quantity", 1]}]}
        }}}
    ]):
        revenue_estimate = round(doc["total"], 2)

    # Items processed this week
    intake_this_week = await db.draft_items.count_documents({"created_at": {"$gte": seven_days_ago}})
    intake_last_week = await db.draft_items.count_documents({
        "created_at": {"$gte": fourteen_days_ago, "$lt": seven_days_ago}
    })

    # ================== SPECS ==================
    spec_status_counts = {}
    async for doc in db.specs.aggregate([{"$group": {"_id": "$status", "count": {"$sum": 1}}}]):
        spec_status_counts[doc["_id"]] = doc["count"]
    total_specs = sum(spec_status_counts.values())

    # ================== PROMOTIONS ==================
    promo_status_counts = {}
    async for doc in db.promotion_candidates.aggregate([{"$group": {"_id": "$status", "count": {"$sum": 1}}}]):
        promo_status_counts[doc["_id"]] = doc["count"]
    pending_promos = promo_status_counts.get("pending", 0) + promo_status_counts.get("Pending", 0)

    # ================== ACTIVITY FEED ==================
    recent_activity = []
    async for doc in db.activity_logs.find({}, {"_id": 0}).sort("timestamp", -1).limit(15):
        recent_activity.append(doc)

    # ================== CATALOG HEALTH ==================
    catalog_total = await db.catalog_items.count_documents({"status": {"$ne": "Archived"}})
    catalog_normalized = await db.catalog_items.count_documents({"normalized": True, "status": {"$ne": "Archived"}})
    catalog_stuck_draft = await db.catalog_items.count_documents({
        "status": "Draft",
        "created_at": {"$lte": seven_days_ago},
    })

    # Lightweight duplicate count
    catalog_dup_count = 0
    if catalog_total >= 2 and catalog_total <= 500:
        cat_items = []
        async for doc in db.catalog_items.find({"status": {"$ne": "Archived"}}, {"_id": 0, "id": 1, "title": 1, "sku": 1, "brand": 1}):
            cat_items.append(doc)
        seen = set()
        for ci in cat_items:
            dupes = find_duplicate_candidates(ci, cat_items, 60.0)
            for d in dupes:
                pair_key = tuple(sorted([ci["id"], d["other_id"]]))
                seen.add(pair_key)
        catalog_dup_count = len(seen)

    pct_normalized = round((catalog_normalized / catalog_total * 100), 1) if catalog_total > 0 else 0

    catalog_health = {
        "total": catalog_total,
        "normalized": catalog_normalized,
        "pct_normalized": pct_normalized,
        "unresolved_duplicates": catalog_dup_count,
        "stuck_draft_7d": catalog_stuck_draft,
        "needs_attention": pct_normalized < 50 or catalog_dup_count > 3 or catalog_stuck_draft > 5,
    }

    # ================== BOTTLENECK DETECTION ==================
    bottlenecks = []
    if stuck_pages > 0:
        bottlenecks.append({
            "module": "Page Ops",
            "issue": f"{stuck_pages} pages stuck in Queue/Draft for 7+ days",
            "severity": "warning" if stuck_pages < 5 else "critical",
            "count": stuck_pages,
        })
    if stuck_intake > 0:
        bottlenecks.append({
            "module": "Product Intake",
            "issue": f"{stuck_intake} items stuck in Needs Info for 7+ days",
            "severity": "warning" if stuck_intake < 5 else "critical",
            "count": stuck_intake,
        })
    if lm_drafts > lm_published:
        bottlenecks.append({
            "module": "Lead Magnets",
            "issue": f"{lm_drafts} drafts vs {lm_published} published — content sitting unused",
            "severity": "info",
            "count": lm_drafts,
        })
    if pending_promos > 0:
        bottlenecks.append({
            "module": "Promotions",
            "issue": f"{pending_promos} promotion candidates awaiting review",
            "severity": "info",
            "count": pending_promos,
        })
    if catalog_stuck_draft > 0:
        bottlenecks.append({
            "module": "Catalog",
            "issue": f"{catalog_stuck_draft} catalog items stuck in Draft for 7+ days",
            "severity": "warning" if catalog_stuck_draft < 5 else "critical",
            "count": catalog_stuck_draft,
        })
    if catalog_dup_count > 3:
        bottlenecks.append({
            "module": "Catalog",
            "issue": f"{catalog_dup_count} unresolved duplicate pairs need review",
            "severity": "warning" if catalog_dup_count < 10 else "critical",
            "count": catalog_dup_count,
        })

    # ================== ASSEMBLE ==================
    return {
        "generated_at": now.isoformat(),
        "modules": {
            "page_ops": {
                "total": total_pages,
                "by_status": page_status_counts,
                "approved": pages_approved,
                "stuck": stuck_pages,
                "velocity": {
                    "this_week": pages_this_week,
                    "last_week": pages_last_week,
                    "trend": "up" if pages_this_week > pages_last_week else "down" if pages_this_week < pages_last_week else "flat",
                },
            },
            "lead_magnets": {
                "total": total_magnets,
                "by_status": lm_status_counts,
                "published": lm_published,
                "ready": lm_ready,
                "drafts": lm_drafts,
                "total_downloads": total_downloads,
            },
            "product_intake": {
                "total_sessions": total_sessions,
                "total_items": total_intake_items,
                "by_status": intake_status_counts,
                "ready": intake_ready,
                "needs_info": intake_needs_info,
                "in_review": intake_in_review,
                "stuck": stuck_intake,
                "revenue_estimate": revenue_estimate,
                "velocity": {
                    "this_week": intake_this_week,
                    "last_week": intake_last_week,
                    "trend": "up" if intake_this_week > intake_last_week else "down" if intake_this_week < intake_last_week else "flat",
                },
            },
            "specs": {
                "total": total_specs,
                "by_status": spec_status_counts,
            },
            "promotions": {
                "by_status": promo_status_counts,
                "pending": pending_promos,
            },
        },
        "ready_to_publish": {
            "pages_approved": pages_approved,
            "lead_magnets_ready": lm_ready + lm_published,
            "intake_items_ready": intake_ready,
            "total": pages_approved + lm_ready + lm_published + intake_ready,
        },
        "catalog_health": catalog_health,
        "bottlenecks": bottlenecks,
        "recent_activity": recent_activity,
    }
