import csv
import io
from fastapi import APIRouter, HTTPException, Depends
from fastapi.responses import StreamingResponse
from typing import Optional
from datetime import datetime, timezone
import uuid

from database import db, logger
from models import (
    CATALOG_ITEM_STATUSES,
    ImportFromIntakeRequest, CreateCatalogItemRequest, UpdateCatalogItemRequest,
    CreateCategoryRequest, UpdateCategoryRequest,
    CreateVariantGroupRequest, ResolveDuplicateRequest,
)
from auth import get_current_user
from services.helpers import log_activity
from services.catalog_service import (
    normalize_catalog_item,
    find_duplicate_candidates,
    build_woo_csv,
)

catalog_router = APIRouter(prefix="/api/catalog")


# ================== HELPERS ==================

async def get_categories() -> list:
    cats = []
    async for doc in db.catalog_categories.find({}, {"_id": 0}).sort("name", 1):
        cats.append(doc)
    return cats


async def ensure_default_categories():
    count = await db.catalog_categories.count_documents({})
    if count == 0:
        defaults = [
            "Vibrators", "Dildos", "Couples Toys", "Bondage & Restraints",
            "Lubricants & Oils", "Lingerie", "Wellness & Self-Care",
            "Accessories", "Gift Sets", "Education & Books",
            "Bath & Body", "Massage", "Apparel", "Other",
        ]
        now = datetime.now(timezone.utc).isoformat()
        for name in defaults:
            await db.catalog_categories.insert_one({
                "id": str(uuid.uuid4()),
                "name": name,
                "parent_id": None,
                "created_at": now,
            })


# ================== STATS ==================

@catalog_router.get("/stats")
async def catalog_stats(user: dict = Depends(get_current_user)):
    await ensure_default_categories()
    total = await db.catalog_items.count_documents({})
    status_counts = {}
    async for doc in db.catalog_items.aggregate([
        {"$group": {"_id": "$status", "count": {"$sum": 1}}}
    ]):
        status_counts[doc["_id"]] = doc["count"]

    cat_count = await db.catalog_categories.count_documents({})
    group_count = await db.catalog_variant_groups.count_documents({})

    return {
        "total_items": total,
        "by_status": status_counts,
        "draft_count": status_counts.get("Draft", 0),
        "needs_review_count": status_counts.get("Needs Review", 0),
        "ready_count": status_counts.get("Ready", 0),
        "exported_count": status_counts.get("Exported", 0),
        "category_count": cat_count,
        "variant_group_count": group_count,
    }


# ================== ITEMS CRUD ==================

@catalog_router.get("/items")
async def list_items(
    status: Optional[str] = None,
    category_id: Optional[str] = None,
    search: Optional[str] = None,
    limit: int = 100,
    user: dict = Depends(get_current_user),
):
    query = {}
    if status:
        query["status"] = status
    if category_id:
        query["category_id"] = category_id
    if search:
        query["$or"] = [
            {"title": {"$regex": search, "$options": "i"}},
            {"brand": {"$regex": search, "$options": "i"}},
            {"sku": {"$regex": search, "$options": "i"}},
        ]

    items = []
    async for doc in db.catalog_items.find(query, {"_id": 0}).sort("updated_at", -1).limit(limit):
        items.append(doc)
    return {"items": items, "count": len(items)}


@catalog_router.post("/items")
async def create_item(
    request: CreateCatalogItemRequest,
    user: dict = Depends(get_current_user),
):
    if not request.title or not request.title.strip():
        raise HTTPException(status_code=400, detail="Title is required")

    now = datetime.now(timezone.utc).isoformat()
    item = {
        "id": str(uuid.uuid4()),
        "title": request.title.strip(),
        "brand": (request.brand or "").strip(),
        "short_description": (request.short_description or "").strip(),
        "description": (request.description or "").strip(),
        "sku": (request.sku or "").strip(),
        "regular_price": request.regular_price,
        "sale_price": None,
        "category_id": request.category_id,
        "secondary_category_ids": [],
        "tags": request.tags or [],
        "attributes": request.attributes or {},
        "color": (request.color or "").strip(),
        "size": (request.size or "").strip(),
        "image_urls": [],
        "variant_group_id": None,
        "source_intake_id": None,
        "normalized": False,
        "status": "Draft",
        "created_at": now,
        "updated_at": now,
    }
    await db.catalog_items.insert_one(item)
    await log_activity("catalog_item_created", details=f"Created catalog item: {item['title']}")
    return {k: v for k, v in item.items() if k != "_id"}


@catalog_router.get("/items/{item_id}")
async def get_item(item_id: str, user: dict = Depends(get_current_user)):
    item = await db.catalog_items.find_one({"id": item_id}, {"_id": 0})
    if not item:
        raise HTTPException(status_code=404, detail="Catalog item not found")
    return item


@catalog_router.put("/items/{item_id}")
async def update_item(
    item_id: str,
    request: UpdateCatalogItemRequest,
    user: dict = Depends(get_current_user),
):
    item = await db.catalog_items.find_one({"id": item_id}, {"_id": 0})
    if not item:
        raise HTTPException(status_code=404, detail="Catalog item not found")

    updates = {}
    for field, value in request.dict(exclude_unset=True).items():
        if value is not None:
            updates[field] = value

    if "status" in updates and updates["status"] not in CATALOG_ITEM_STATUSES:
        raise HTTPException(status_code=400, detail=f"Invalid status. Must be one of: {CATALOG_ITEM_STATUSES}")

    if updates:
        updates["updated_at"] = datetime.now(timezone.utc).isoformat()
        await db.catalog_items.update_one({"id": item_id}, {"$set": updates})

    updated = await db.catalog_items.find_one({"id": item_id}, {"_id": 0})
    return updated


@catalog_router.delete("/items/{item_id}")
async def delete_item(item_id: str, user: dict = Depends(get_current_user)):
    item = await db.catalog_items.find_one({"id": item_id}, {"_id": 0})
    if not item:
        raise HTTPException(status_code=404, detail="Catalog item not found")
    await db.catalog_items.delete_one({"id": item_id})
    await log_activity("catalog_item_deleted", details=f"Deleted: {item.get('title')}")
    return {"message": "Catalog item deleted"}


# ================== NORMALIZE ==================

@catalog_router.post("/items/{item_id}/normalize")
async def normalize_item(item_id: str, user: dict = Depends(get_current_user)):
    item = await db.catalog_items.find_one({"id": item_id}, {"_id": 0})
    if not item:
        raise HTTPException(status_code=404, detail="Catalog item not found")

    categories = await get_categories()
    result = await normalize_catalog_item(item, categories)

    updates = {
        "normalized": True,
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    if result.get("title"):
        updates["title"] = result["title"]
    if result.get("brand"):
        updates["brand"] = result["brand"]
    if result.get("short_description"):
        updates["short_description"] = result["short_description"]
    if result.get("description"):
        updates["description"] = result["description"]
    if result.get("tags"):
        updates["tags"] = result["tags"]
    if result.get("attributes"):
        updates["attributes"] = result["attributes"]

    cat_suggestion = result.get("category_suggestion")
    if cat_suggestion and cat_suggestion.get("name"):
        matched = None
        for c in categories:
            if c["name"].lower() == cat_suggestion["name"].lower():
                matched = c
                break
        if matched:
            updates["category_id"] = matched["id"]

    if item.get("status") == "Draft":
        updates["status"] = "Needs Review"

    await db.catalog_items.update_one({"id": item_id}, {"$set": updates})
    await log_activity("catalog_item_normalized", details=f"Normalized: {updates.get('title', item.get('title'))}")

    updated = await db.catalog_items.find_one({"id": item_id}, {"_id": 0})
    return {
        "item": updated,
        "normalization_result": result,
    }


# ================== IMPORT FROM INTAKE ==================

@catalog_router.post("/import-from-intake")
async def import_from_intake(
    request: ImportFromIntakeRequest,
    user: dict = Depends(get_current_user),
):
    query = {}
    if request.session_id:
        query["session_id"] = request.session_id
    if request.item_ids:
        query["id"] = {"$in": request.item_ids}
    if request.statuses:
        query["status"] = {"$in": request.statuses}
    elif not request.item_ids:
        query["status"] = "ready"

    intake_items = []
    async for doc in db.draft_items.find(query, {"_id": 0}):
        intake_items.append(doc)

    if not intake_items:
        raise HTTPException(status_code=400, detail="No matching intake items found")

    now = datetime.now(timezone.utc).isoformat()
    created = []
    categories = await get_categories()
    cat_name_map = {c["name"].lower(): c["id"] for c in categories}

    for di in intake_items:
        existing = await db.catalog_items.find_one({"source_intake_id": di["id"]}, {"_id": 0})
        if existing:
            continue

        cat_id = None
        if di.get("category"):
            cat_id = cat_name_map.get(di["category"].lower())

        item = {
            "id": str(uuid.uuid4()),
            "title": di.get("clean_title") or di.get("source_title") or "Untitled",
            "brand": "",
            "short_description": di.get("short_description", ""),
            "description": di.get("long_description", ""),
            "sku": "",
            "regular_price": di.get("suggested_price"),
            "sale_price": None,
            "category_id": cat_id,
            "secondary_category_ids": [],
            "tags": di.get("tags", []),
            "attributes": {},
            "color": di.get("color", ""),
            "size": di.get("size", ""),
            "image_urls": [],
            "variant_group_id": None,
            "source_intake_id": di["id"],
            "normalized": False,
            "status": "Draft",
            "created_at": now,
            "updated_at": now,
        }
        await db.catalog_items.insert_one(item)
        created.append({k: v for k, v in item.items() if k != "_id"})

    await log_activity("catalog_import", details=f"Imported {len(created)} items from intake")
    return {"imported_count": len(created), "skipped_duplicates": len(intake_items) - len(created), "items": created}


# ================== DUPLICATES ==================

@catalog_router.get("/duplicates")
async def scan_duplicates(
    threshold: float = 60.0,
    user: dict = Depends(get_current_user),
):
    all_items = []
    async for doc in db.catalog_items.find({"status": {"$ne": "Archived"}}, {"_id": 0}):
        all_items.append(doc)

    if len(all_items) < 2:
        return {"pairs": [], "count": 0}

    seen_pairs = set()
    pairs = []
    for item in all_items:
        candidates = find_duplicate_candidates(item, all_items, threshold)
        for c in candidates:
            pair_key = tuple(sorted([item["id"], c["other_id"]]))
            if pair_key in seen_pairs:
                continue
            seen_pairs.add(pair_key)
            other = next((x for x in all_items if x["id"] == c["other_id"]), None)
            if other:
                pairs.append({
                    "item_a": item,
                    "item_b": other,
                    "score": c["score"],
                    "signals": c["signals"],
                })

    pairs.sort(key=lambda x: x["score"], reverse=True)
    return {"pairs": pairs[:50], "count": len(pairs)}


@catalog_router.post("/duplicates/resolve")
async def resolve_duplicate(
    request: ResolveDuplicateRequest,
    item_a_id: str = "",
    item_b_id: str = "",
    user: dict = Depends(get_current_user),
):
    if not item_a_id or not item_b_id:
        raise HTTPException(status_code=400, detail="Both item_a_id and item_b_id are required")

    a = await db.catalog_items.find_one({"id": item_a_id}, {"_id": 0})
    b = await db.catalog_items.find_one({"id": item_b_id}, {"_id": 0})
    if not a or not b:
        raise HTTPException(status_code=404, detail="One or both items not found")

    if request.action == "not_duplicate":
        await log_activity("catalog_duplicate_dismissed", details=f"Dismissed: {a['title']} vs {b['title']}")
        return {"message": "Marked as not duplicate", "action": "dismissed"}

    elif request.action == "merge_keep_left":
        keep, discard = a, b
    elif request.action == "merge_keep_right":
        keep, discard = b, a
    else:
        raise HTTPException(status_code=400, detail="Invalid action. Use: not_duplicate, merge_keep_left, merge_keep_right")

    merge_updates = {}
    for field in ["short_description", "description", "brand", "sku", "category_id"]:
        if not keep.get(field) and discard.get(field):
            merge_updates[field] = discard[field]

    keep_tags = set(keep.get("tags") or [])
    discard_tags = set(discard.get("tags") or [])
    merged_tags = list(keep_tags | discard_tags)
    if merged_tags != list(keep_tags):
        merge_updates["tags"] = merged_tags

    keep_attrs = keep.get("attributes") or {}
    discard_attrs = discard.get("attributes") or {}
    merged_attrs = {**discard_attrs, **keep_attrs}
    if merged_attrs != keep_attrs:
        merge_updates["attributes"] = merged_attrs

    if merge_updates:
        merge_updates["updated_at"] = datetime.now(timezone.utc).isoformat()
        await db.catalog_items.update_one({"id": keep["id"]}, {"$set": merge_updates})

    await db.catalog_items.update_one({"id": discard["id"]}, {"$set": {"status": "Archived", "updated_at": datetime.now(timezone.utc).isoformat()}})
    await log_activity("catalog_duplicate_merged", details=f"Merged: kept '{keep['title']}', archived '{discard['title']}'")

    updated_keep = await db.catalog_items.find_one({"id": keep["id"]}, {"_id": 0})
    return {"message": "Merged successfully", "kept": updated_keep, "archived_id": discard["id"]}


# ================== CATEGORIES ==================

@catalog_router.get("/categories")
async def list_categories(user: dict = Depends(get_current_user)):
    await ensure_default_categories()
    cats = await get_categories()
    return {"categories": cats}


@catalog_router.post("/categories")
async def create_category(
    request: CreateCategoryRequest,
    user: dict = Depends(get_current_user),
):
    if not request.name or not request.name.strip():
        raise HTTPException(status_code=400, detail="Category name is required")

    existing = await db.catalog_categories.find_one({"name": {"$regex": f"^{request.name.strip()}$", "$options": "i"}}, {"_id": 0})
    if existing:
        raise HTTPException(status_code=400, detail="Category already exists")

    now = datetime.now(timezone.utc).isoformat()
    cat = {
        "id": str(uuid.uuid4()),
        "name": request.name.strip(),
        "parent_id": request.parent_id,
        "created_at": now,
    }
    await db.catalog_categories.insert_one(cat)
    await log_activity("catalog_category_created", details=f"Created category: {cat['name']}")
    return {k: v for k, v in cat.items() if k != "_id"}


@catalog_router.put("/categories/{cat_id}")
async def update_category(
    cat_id: str,
    request: UpdateCategoryRequest,
    user: dict = Depends(get_current_user),
):
    cat = await db.catalog_categories.find_one({"id": cat_id}, {"_id": 0})
    if not cat:
        raise HTTPException(status_code=404, detail="Category not found")

    updates = {}
    if request.name is not None:
        updates["name"] = request.name.strip()
    if request.parent_id is not None:
        updates["parent_id"] = request.parent_id

    if updates:
        await db.catalog_categories.update_one({"id": cat_id}, {"$set": updates})

    updated = await db.catalog_categories.find_one({"id": cat_id}, {"_id": 0})
    return updated


@catalog_router.delete("/categories/{cat_id}")
async def delete_category(cat_id: str, user: dict = Depends(get_current_user)):
    cat = await db.catalog_categories.find_one({"id": cat_id}, {"_id": 0})
    if not cat:
        raise HTTPException(status_code=404, detail="Category not found")

    items_using = await db.catalog_items.count_documents({"category_id": cat_id})
    if items_using > 0:
        raise HTTPException(status_code=400, detail=f"Cannot delete: {items_using} catalog item(s) use this category. Reassign them first.")

    await db.catalog_categories.delete_one({"id": cat_id})
    await log_activity("catalog_category_deleted", details=f"Deleted category: {cat['name']}")
    return {"message": "Category deleted"}


# ================== VARIANT GROUPS ==================

@catalog_router.get("/variant-groups")
async def list_variant_groups(user: dict = Depends(get_current_user)):
    groups = []
    async for doc in db.catalog_variant_groups.find({}, {"_id": 0}).sort("created_at", -1):
        groups.append(doc)
    return {"groups": groups}


@catalog_router.post("/variant-groups")
async def create_variant_group(
    request: CreateVariantGroupRequest,
    user: dict = Depends(get_current_user),
):
    if not request.name or not request.name.strip():
        raise HTTPException(status_code=400, detail="Group name is required")
    if len(request.member_ids) < 2:
        raise HTTPException(status_code=400, detail="At least 2 members required")

    for mid in request.member_ids:
        item = await db.catalog_items.find_one({"id": mid}, {"_id": 0})
        if not item:
            raise HTTPException(status_code=404, detail=f"Item {mid} not found")

    now = datetime.now(timezone.utc).isoformat()
    group = {
        "id": str(uuid.uuid4()),
        "name": request.name.strip(),
        "attribute_keys": request.attribute_keys,
        "member_ids": request.member_ids,
        "created_at": now,
    }
    await db.catalog_variant_groups.insert_one(group)

    for mid in request.member_ids:
        await db.catalog_items.update_one({"id": mid}, {"$set": {"variant_group_id": group["id"]}})

    await log_activity("catalog_variant_group_created", details=f"Variant group: {group['name']} ({len(request.member_ids)} items)")
    return {k: v for k, v in group.items() if k != "_id"}


@catalog_router.delete("/variant-groups/{group_id}")
async def delete_variant_group(group_id: str, user: dict = Depends(get_current_user)):
    group = await db.catalog_variant_groups.find_one({"id": group_id}, {"_id": 0})
    if not group:
        raise HTTPException(status_code=404, detail="Variant group not found")

    await db.catalog_items.update_many(
        {"variant_group_id": group_id},
        {"$set": {"variant_group_id": None}}
    )
    await db.catalog_variant_groups.delete_one({"id": group_id})
    await log_activity("catalog_variant_group_deleted", details=f"Deleted variant group: {group['name']}")
    return {"message": "Variant group deleted"}


# ================== WOO EXPORT ==================

@catalog_router.get("/export/woo-csv")
async def export_woo_csv(
    status: Optional[str] = "Ready",
    user: dict = Depends(get_current_user),
):
    query = {}
    if status:
        query["status"] = status

    items = []
    async for doc in db.catalog_items.find(query, {"_id": 0}).sort("title", 1):
        items.append(doc)

    if not items:
        raise HTTPException(status_code=400, detail="No items to export")

    categories = await get_categories()
    csv_content = build_woo_csv(items, categories)

    now_str = datetime.now(timezone.utc).strftime('%Y%m%d')
    filename = f"woo-catalog-export-{now_str}.csv"

    await db.catalog_items.update_many(
        {"id": {"$in": [i["id"] for i in items]}, "status": "Ready"},
        {"$set": {"status": "Exported", "updated_at": datetime.now(timezone.utc).isoformat()}}
    )
    await log_activity("catalog_woo_export", details=f"Exported {len(items)} items to Woo CSV")

    return StreamingResponse(
        iter([csv_content]),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )
