import os
import uuid
import asyncio
import shutil
from datetime import datetime, timezone
from fastapi import APIRouter, HTTPException, Depends, UploadFile, File, Form
from fastapi.responses import FileResponse
from typing import Optional
from pydantic import BaseModel

from database import db, logger
from auth import get_current_user
from services.helpers import log_activity
from services.field_listing import (
    UPLOAD_DIR,
    analyze_photo,
    generate_listing,
    parse_grouped_pricing,
    generate_destination_pack,
    generate_website_page_pack,
    suggest_item_groups,
    refine_merged_title,
)
from services.worker_queue import route_after_analysis

field_listing_router = APIRouter(prefix="/api/field-listing")

VALID_DESTINATIONS = ["website", "offerup", "facebook"]
BATCH_STATUSES = ["intake", "processing", "review", "complete"]
ITEM_STATUSES = ["draft", "review", "approved", "skipped"]


# ================== STATS ==================

@field_listing_router.get("/stats")
async def field_listing_stats(user: dict = Depends(get_current_user)):
    batch_count = await db.field_batches.count_documents({})
    item_count = await db.field_items.count_documents({})
    approved = await db.field_items.count_documents({"status": "approved"})
    draft = await db.field_items.count_documents({"status": "draft"})
    return {
        "total_batches": batch_count,
        "total_items": item_count,
        "approved_items": approved,
        "draft_items": draft,
    }


# ================== BATCHES CRUD ==================

class CreateBatchRequest(BaseModel):
    name: str
    source_vendor: str = ""
    grouped_pricing_note: str = ""
    grouped_category_note: str = ""
    condition_note: str = ""
    pickup_shipping_note: str = ""
    destinations: list[str] = ["website", "offerup", "facebook"]


class UpdateBatchRequest(BaseModel):
    name: Optional[str] = None
    source_vendor: Optional[str] = None
    grouped_pricing_note: Optional[str] = None
    grouped_category_note: Optional[str] = None
    condition_note: Optional[str] = None
    pickup_shipping_note: Optional[str] = None
    destinations: Optional[list[str]] = None


@field_listing_router.get("/batches")
async def list_batches(user: dict = Depends(get_current_user)):
    batches = []
    async for doc in db.field_batches.find({}, {"_id": 0}).sort("created_at", -1):
        batches.append(doc)
    return {"batches": batches}


@field_listing_router.post("/batches")
async def create_batch(request: CreateBatchRequest, user: dict = Depends(get_current_user)):
    if not request.name.strip():
        raise HTTPException(status_code=400, detail="Batch name is required")

    # Validate destinations
    for d in request.destinations:
        if d not in VALID_DESTINATIONS:
            raise HTTPException(status_code=400, detail=f"Invalid destination: {d}")

    now = datetime.now(timezone.utc).isoformat()
    batch = {
        "id": str(uuid.uuid4()),
        "name": request.name.strip(),
        "source_vendor": request.source_vendor.strip(),
        "grouped_pricing_note": request.grouped_pricing_note.strip(),
        "grouped_category_note": request.grouped_category_note.strip(),
        "condition_note": request.condition_note.strip(),
        "pickup_shipping_note": request.pickup_shipping_note.strip(),
        "destinations": request.destinations,
        "item_count": 0,
        "status": "intake",
        "created_at": now,
        "updated_at": now,
    }

    # Create upload directory for this batch
    batch_dir = os.path.join(UPLOAD_DIR, batch["id"])
    os.makedirs(batch_dir, exist_ok=True)

    await db.field_batches.insert_one(batch)
    await log_activity("field_batch_created", details=f"Created field listing batch: {request.name}")
    return {k: v for k, v in batch.items() if k != "_id"}


@field_listing_router.get("/batches/{batch_id}")
async def get_batch(batch_id: str, user: dict = Depends(get_current_user)):
    batch = await db.field_batches.find_one({"id": batch_id}, {"_id": 0})
    if not batch:
        raise HTTPException(status_code=404, detail="Batch not found")

    items = []
    async for doc in db.field_items.find({"batch_id": batch_id}, {"_id": 0}).sort("created_at", 1):
        items.append(doc)

    batch["items"] = items
    return batch


@field_listing_router.put("/batches/{batch_id}")
async def update_batch(batch_id: str, request: UpdateBatchRequest, user: dict = Depends(get_current_user)):
    batch = await db.field_batches.find_one({"id": batch_id}, {"_id": 0})
    if not batch:
        raise HTTPException(status_code=404, detail="Batch not found")

    updates = {}
    for field, value in request.dict(exclude_unset=True).items():
        if value is not None:
            if field == "destinations":
                for d in value:
                    if d not in VALID_DESTINATIONS:
                        raise HTTPException(status_code=400, detail=f"Invalid destination: {d}")
            updates[field] = value.strip() if isinstance(value, str) else value

    if updates:
        updates["updated_at"] = datetime.now(timezone.utc).isoformat()
        await db.field_batches.update_one({"id": batch_id}, {"$set": updates})

    updated = await db.field_batches.find_one({"id": batch_id}, {"_id": 0})
    return updated


@field_listing_router.delete("/batches/{batch_id}")
async def delete_batch(batch_id: str, user: dict = Depends(get_current_user)):
    batch = await db.field_batches.find_one({"id": batch_id}, {"_id": 0})
    if not batch:
        raise HTTPException(status_code=404, detail="Batch not found")

    # Delete items
    await db.field_items.delete_many({"batch_id": batch_id})
    await db.field_batches.delete_one({"id": batch_id})

    # Delete uploaded files
    batch_dir = os.path.join(UPLOAD_DIR, batch_id)
    if os.path.exists(batch_dir):
        shutil.rmtree(batch_dir, ignore_errors=True)

    await log_activity("field_batch_deleted", details=f"Deleted field listing batch: {batch.get('name')}")
    return {"message": "Batch and all items deleted"}


# ================== PHOTO UPLOAD ==================

@field_listing_router.post("/batches/{batch_id}/upload-photos")
async def upload_photos(
    batch_id: str,
    files: list[UploadFile] = File(...),
    user: dict = Depends(get_current_user),
):
    batch = await db.field_batches.find_one({"id": batch_id}, {"_id": 0})
    if not batch:
        raise HTTPException(status_code=404, detail="Batch not found")

    if not files:
        raise HTTPException(status_code=400, detail="No files provided")

    batch_dir = os.path.join(UPLOAD_DIR, batch_id)
    os.makedirs(batch_dir, exist_ok=True)

    allowed_ext = {'.jpg', '.jpeg', '.png', '.webp', '.heic', '.heif'}
    created_items = []

    # Get current max order for this batch
    existing_count = await db.field_items.count_documents({"batch_id": batch_id})
    order = existing_count

    for file in files:
        if not file.filename:
            continue

        ext = os.path.splitext(file.filename)[1].lower()
        if ext not in allowed_ext:
            continue

        try:
            content = await file.read()
            if len(content) < 100:
                continue

            # Save with unique name
            safe_name = f"{uuid.uuid4()}{ext}"
            file_path = os.path.join(batch_dir, safe_name)
            with open(file_path, "wb") as f:
                f.write(content)

            order += 1
            now = datetime.now(timezone.utc).isoformat()
            item = {
                "id": str(uuid.uuid4()),
                "batch_id": batch_id,
                "images": [{
                    "filename": safe_name,
                    "original_name": file.filename,
                    "path": file_path,
                    "order": order,
                }],
                "vision_analysis": {},
                "draft_title": "",
                "short_description": "",
                "category_suggestion": "",
                "tags": [],
                "unit_cost": None,
                "retail_price": None,
                "source_vendor": batch.get("source_vendor", ""),
                "condition": batch.get("condition_note", ""),
                "pickup_shipping": batch.get("pickup_shipping_note", ""),
                "confidence": 0,
                "confidence_flag": "pending",
                "status": "draft",
                "grouped_note_ref": batch.get("grouped_pricing_note", ""),
                "destination_packs": {},
                "created_at": now,
                "updated_at": now,
            }

            await db.field_items.insert_one(item)
            created_items.append({k: v for k, v in item.items() if k != "_id"})

        except Exception as e:
            logger.error(f"[Field Listing] Failed to save photo {file.filename}: {e}")

    # Update batch item count
    total = await db.field_items.count_documents({"batch_id": batch_id})
    await db.field_batches.update_one(
        {"id": batch_id},
        {"$set": {"item_count": total, "updated_at": datetime.now(timezone.utc).isoformat()}}
    )

    await log_activity("field_photos_uploaded", details=f"Uploaded {len(created_items)} photos to batch {batch.get('name')}")
    return {"uploaded": len(created_items), "total_items": total, "items": created_items}


# ================== IMAGE SERVING ==================

@field_listing_router.get("/images/{batch_id}/{filename}")
async def serve_image(batch_id: str, filename: str):
    """Serve uploaded product images."""
    file_path = os.path.join(UPLOAD_DIR, batch_id, filename)
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="Image not found")
    return FileResponse(file_path)


# ================== ANALYZE PHOTOS (Vision AI) ==================

async def _analyze_batch_photos(batch_id: str, job_id: str):
    """Background task: analyze all unanalyzed photos in a batch via Vision AI."""
    try:
        batch = await db.field_batches.find_one({"id": batch_id}, {"_id": 0})
        items = []
        async for doc in db.field_items.find(
            {"batch_id": batch_id, "confidence_flag": "pending"}, {"_id": 0}
        ):
            items.append(doc)

        analyzed = 0
        failed = 0

        for idx, item in enumerate(items):
            if idx > 0:
                await asyncio.sleep(2)

            images = item.get("images", [])
            if not images:
                continue

            image_path = images[0].get("path", "")
            if not image_path or not os.path.exists(image_path):
                failed += 1
                continue

            vision = await analyze_photo(
                image_path,
                source_vendor=batch.get("source_vendor", ""),
                batch_notes=batch.get("grouped_category_note", "")
            )

            conf = vision.get("confidence", 0.5)
            if conf >= 0.7:
                flag = "high"
            elif conf >= 0.4:
                flag = "medium"
            else:
                flag = "weak"

            await db.field_items.update_one({"id": item["id"]}, {"$set": {
                "vision_analysis": vision,
                "draft_title": vision.get("product_type", ""),
                "confidence": conf,
                "confidence_flag": flag,
                "condition": vision.get("condition") or item.get("condition", ""),
                "updated_at": datetime.now(timezone.utc).isoformat(),
            }})
            analyzed += 1
            logger.info(f"[Field Listing] Analyzed photo {idx+1}/{len(items)}: {vision.get('product_type', '?')} (conf={conf})")

            # Auto-route to Jenny for copy work
            try:
                await route_after_analysis(item["id"], batch_id)
            except Exception as route_err:
                logger.warning(f"[Field Listing] Worker routing failed for {item['id']}: {route_err}")

        await db.field_jobs.update_one({"id": job_id}, {"$set": {
            "status": "completed",
            "analyzed": analyzed,
            "failed": failed,
            "completed_at": datetime.now(timezone.utc).isoformat(),
        }})

        await db.field_batches.update_one({"id": batch_id}, {"$set": {
            "status": "review",
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }})

    except Exception as e:
        logger.error(f"[Field Listing] Batch analysis failed: {e}")
        await db.field_jobs.update_one({"id": job_id}, {"$set": {
            "status": "failed",
            "error": str(e)[:500],
            "completed_at": datetime.now(timezone.utc).isoformat(),
        }})


@field_listing_router.post("/batches/{batch_id}/analyze")
async def analyze_batch(batch_id: str, user: dict = Depends(get_current_user)):
    """Start Vision AI analysis of all photos in the batch."""
    batch = await db.field_batches.find_one({"id": batch_id}, {"_id": 0})
    if not batch:
        raise HTTPException(status_code=404, detail="Batch not found")

    pending = await db.field_items.count_documents({"batch_id": batch_id, "confidence_flag": "pending"})
    if pending == 0:
        return {"message": "No photos pending analysis", "pending": 0}

    job_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()
    await db.field_jobs.insert_one({
        "id": job_id,
        "batch_id": batch_id,
        "type": "analyze",
        "status": "processing",
        "total": pending,
        "created_at": now,
    })

    await db.field_batches.update_one({"id": batch_id}, {"$set": {"status": "processing", "updated_at": now}})

    asyncio.create_task(_analyze_batch_photos(batch_id, job_id))

    return {
        "status": "processing",
        "job_id": job_id,
        "message": f"Analyzing {pending} photos via Vision AI. Poll /api/field-listing/jobs/{job_id} for status.",
        "pending": pending,
    }


# ================== JOB POLLING ==================

@field_listing_router.get("/jobs/{job_id}")
async def get_job_status(job_id: str, user: dict = Depends(get_current_user)):
    job = await db.field_jobs.find_one({"id": job_id}, {"_id": 0})
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return job


# ================== APPLY GROUPED PRICING ==================

class ApplyPricingRequest(BaseModel):
    pricing_note: str = ""
    unit_cost: Optional[float] = None
    retail_price: Optional[float] = None
    item_ids: list[str] = []  # empty = apply to all


@field_listing_router.post("/batches/{batch_id}/apply-pricing")
async def apply_pricing(batch_id: str, request: ApplyPricingRequest, user: dict = Depends(get_current_user)):
    batch = await db.field_batches.find_one({"id": batch_id}, {"_id": 0})
    if not batch:
        raise HTTPException(status_code=404, detail="Batch not found")

    # Parse pricing from note if no explicit values
    unit_cost = request.unit_cost
    retail_price = request.retail_price

    if request.pricing_note and not unit_cost and not retail_price:
        parsed = parse_grouped_pricing(request.pricing_note)
        unit_cost = parsed.get("unit_cost") or unit_cost
        retail_price = parsed.get("retail_price") or retail_price

    if not unit_cost and not retail_price:
        raise HTTPException(status_code=400, detail="No pricing could be determined. Provide explicit values or a clearer pricing note.")

    # Build query
    query = {"batch_id": batch_id}
    if request.item_ids:
        query["id"] = {"$in": request.item_ids}

    now = datetime.now(timezone.utc).isoformat()
    updates = {"updated_at": now}
    if unit_cost is not None:
        updates["unit_cost"] = unit_cost
    if retail_price is not None:
        updates["retail_price"] = retail_price
    if request.pricing_note:
        updates["grouped_note_ref"] = request.pricing_note

    result = await db.field_items.update_many(query, {"$set": updates})

    # Update batch pricing note
    if request.pricing_note:
        await db.field_batches.update_one(
            {"id": batch_id},
            {"$set": {"grouped_pricing_note": request.pricing_note, "updated_at": now}}
        )

    await log_activity("field_pricing_applied", details=f"Applied pricing to {result.modified_count} items in batch {batch.get('name')}")

    return {
        "updated": result.modified_count,
        "unit_cost": unit_cost,
        "retail_price": retail_price,
        "pricing_note": request.pricing_note,
    }


# ================== GENERATE LISTINGS ==================

async def _generate_batch_listings(batch_id: str, job_id: str):
    """Background: generate listing content for all draft items."""
    try:
        batch = await db.field_batches.find_one({"id": batch_id}, {"_id": 0})
        items = []
        async for doc in db.field_items.find(
            {"batch_id": batch_id, "short_description": {"$in": ["", None]}},
            {"_id": 0}
        ):
            if doc.get("draft_title") or doc.get("vision_analysis", {}).get("product_type"):
                items.append(doc)

        generated = 0
        failed = 0

        for idx, item in enumerate(items):
            if idx > 0:
                await asyncio.sleep(2)

            try:
                result = await generate_listing(item, batch)
                conf = result.get("confidence", 0.5)

                await db.field_items.update_one({"id": item["id"]}, {"$set": {
                    "draft_title": result.get("draft_title", item.get("draft_title", "")),
                    "short_description": result.get("short_description", ""),
                    "category_suggestion": result.get("category_suggestion", ""),
                    "tags": result.get("tags", []),
                    "confidence": max(item.get("confidence", 0), conf),
                    "status": "review",
                    "updated_at": datetime.now(timezone.utc).isoformat(),
                }})
                generated += 1
            except Exception as e:
                logger.error(f"[Field Listing] Generation failed for item {item['id']}: {e}")
                failed += 1

        await db.field_jobs.update_one({"id": job_id}, {"$set": {
            "status": "completed",
            "generated": generated,
            "failed": failed,
            "completed_at": datetime.now(timezone.utc).isoformat(),
        }})

    except Exception as e:
        logger.error(f"[Field Listing] Batch generation failed: {e}")
        await db.field_jobs.update_one({"id": job_id}, {"$set": {
            "status": "failed",
            "error": str(e)[:500],
            "completed_at": datetime.now(timezone.utc).isoformat(),
        }})


@field_listing_router.post("/batches/{batch_id}/generate-listings")
async def generate_listings(batch_id: str, user: dict = Depends(get_current_user)):
    batch = await db.field_batches.find_one({"id": batch_id}, {"_id": 0})
    if not batch:
        raise HTTPException(status_code=404, detail="Batch not found")

    pending = await db.field_items.count_documents({
        "batch_id": batch_id,
        "short_description": {"$in": ["", None]},
        "draft_title": {"$ne": ""},
    })

    if pending == 0:
        return {"message": "No items need listing generation", "pending": 0}

    job_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()
    await db.field_jobs.insert_one({
        "id": job_id,
        "batch_id": batch_id,
        "type": "generate",
        "status": "processing",
        "total": pending,
        "created_at": now,
    })

    asyncio.create_task(_generate_batch_listings(batch_id, job_id))

    return {
        "status": "processing",
        "job_id": job_id,
        "message": f"Generating listings for {pending} items. Poll /api/field-listing/jobs/{job_id} for status.",
        "pending": pending,
    }


# ================== GENERATE DESTINATION PACKS ==================

@field_listing_router.post("/batches/{batch_id}/generate-packs")
async def generate_packs(batch_id: str, user: dict = Depends(get_current_user)):
    """Generate destination packs for all approved/review items in the batch."""
    batch = await db.field_batches.find_one({"id": batch_id}, {"_id": 0})
    if not batch:
        raise HTTPException(status_code=404, detail="Batch not found")

    destinations = batch.get("destinations", ["website", "offerup", "facebook"])
    items = []
    async for doc in db.field_items.find(
        {"batch_id": batch_id, "status": {"$in": ["review", "approved"]}},
        {"_id": 0}
    ):
        items.append(doc)

    if not items:
        raise HTTPException(status_code=400, detail="No items available for pack generation. Analyze photos and generate listings first.")

    now = datetime.now(timezone.utc).isoformat()
    updated = 0

    for item in items:
        packs = {}
        for dest in destinations:
            packs[dest] = generate_destination_pack(item, dest, batch)

        await db.field_items.update_one({"id": item["id"]}, {"$set": {
            "destination_packs": packs,
            "updated_at": now,
        }})
        updated += 1

    # Generate website page pack (aggregate)
    website_page = generate_website_page_pack(items, batch) if "website" in destinations else ""

    await db.field_batches.update_one({"id": batch_id}, {"$set": {
        "website_page_pack": website_page,
        "packs_generated_at": now,
        "updated_at": now,
    }})

    await log_activity("field_packs_generated", details=f"Generated destination packs for {updated} items in batch {batch.get('name')}")

    return {
        "updated": updated,
        "destinations": destinations,
        "website_page_pack": website_page,
    }


# ================== GET PACKS ==================

@field_listing_router.get("/batches/{batch_id}/packs")
async def get_batch_packs(batch_id: str, user: dict = Depends(get_current_user)):
    """Get all destination packs for a batch."""
    batch = await db.field_batches.find_one({"id": batch_id}, {"_id": 0})
    if not batch:
        raise HTTPException(status_code=404, detail="Batch not found")

    items = []
    async for doc in db.field_items.find(
        {"batch_id": batch_id, "destination_packs": {"$ne": {}}},
        {"_id": 0}
    ):
        items.append({
            "id": doc["id"],
            "draft_title": doc.get("draft_title", ""),
            "retail_price": doc.get("retail_price"),
            "images": doc.get("images", []),
            "destination_packs": doc.get("destination_packs", {}),
        })

    return {
        "batch_name": batch.get("name", ""),
        "website_page_pack": batch.get("website_page_pack", ""),
        "items": items,
    }


# ================== ITEM UPDATE ==================

class UpdateFieldItemRequest(BaseModel):
    draft_title: Optional[str] = None
    short_description: Optional[str] = None
    category_suggestion: Optional[str] = None
    tags: Optional[list[str]] = None
    unit_cost: Optional[float] = None
    retail_price: Optional[float] = None
    condition: Optional[str] = None
    pickup_shipping: Optional[str] = None
    status: Optional[str] = None


@field_listing_router.put("/items/{item_id}")
async def update_field_item(item_id: str, request: UpdateFieldItemRequest, user: dict = Depends(get_current_user)):
    item = await db.field_items.find_one({"id": item_id}, {"_id": 0})
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")

    updates = {}
    for field, value in request.dict(exclude_unset=True).items():
        if value is not None:
            if field == "status" and value not in ITEM_STATUSES:
                raise HTTPException(status_code=400, detail=f"Invalid status: {value}")
            updates[field] = value

    if updates:
        updates["updated_at"] = datetime.now(timezone.utc).isoformat()
        await db.field_items.update_one({"id": item_id}, {"$set": updates})

    updated = await db.field_items.find_one({"id": item_id}, {"_id": 0})
    return updated


# ================== BULK ACTIONS ==================

class BulkFieldActionRequest(BaseModel):
    item_ids: list[str]
    action: str  # "approve", "skip", "set_price"
    value: str = ""


@field_listing_router.post("/batches/{batch_id}/bulk-action")
async def bulk_field_action(batch_id: str, request: BulkFieldActionRequest, user: dict = Depends(get_current_user)):
    batch = await db.field_batches.find_one({"id": batch_id}, {"_id": 0})
    if not batch:
        raise HTTPException(status_code=404, detail="Batch not found")

    now = datetime.now(timezone.utc).isoformat()
    updated = 0

    for item_id in request.item_ids:
        updates = {"updated_at": now}

        if request.action == "approve":
            updates["status"] = "approved"
        elif request.action == "skip":
            updates["status"] = "skipped"
        elif request.action == "set_price":
            try:
                updates["retail_price"] = float(request.value)
            except (ValueError, TypeError):
                continue
        else:
            continue

        result = await db.field_items.update_one(
            {"id": item_id, "batch_id": batch_id},
            {"$set": updates}
        )
        if result.modified_count > 0:
            updated += 1

    return {"action": request.action, "updated": updated, "total_selected": len(request.item_ids)}

# ================== MERGE ITEMS ==================

class MergeItemsRequest(BaseModel):
    item_ids: list[str]  # 2+ items to merge into one


@field_listing_router.post("/batches/{batch_id}/merge-items")
async def merge_items(batch_id: str, request: MergeItemsRequest, user: dict = Depends(get_current_user)):
    """Merge 2+ items into one. Combines all images, keeps primary item's metadata."""
    batch = await db.field_batches.find_one({"id": batch_id}, {"_id": 0})
    if not batch:
        raise HTTPException(status_code=404, detail="Batch not found")

    if len(request.item_ids) < 2:
        raise HTTPException(status_code=400, detail="Need at least 2 items to merge")

    # Fetch all items
    items = []
    for item_id in request.item_ids:
        item = await db.field_items.find_one({"id": item_id, "batch_id": batch_id}, {"_id": 0})
        if not item:
            raise HTTPException(status_code=404, detail=f"Item {item_id} not found in this batch")
        items.append(item)

    # Primary item = first in list (keeps its metadata as base)
    primary = items[0]
    merged_images = list(primary.get("images", []))

    # Collect images from all secondary items
    for secondary in items[1:]:
        for img in secondary.get("images", []):
            merged_images.append(img)

    # Update primary with all images
    now = datetime.now(timezone.utc).isoformat()
    await db.field_items.update_one({"id": primary["id"]}, {"$set": {
        "images": merged_images,
        "merged_from": [i["id"] for i in items[1:]],
        "updated_at": now,
    }})

    # Delete secondary items
    secondary_ids = [i["id"] for i in items[1:]]
    await db.field_items.delete_many({"id": {"$in": secondary_ids}, "batch_id": batch_id})

    # Update batch item count
    total = await db.field_items.count_documents({"batch_id": batch_id})
    await db.field_batches.update_one({"id": batch_id}, {"$set": {
        "item_count": total,
        "updated_at": now,
    }})

    # --- Post-Merge Title Refinement ---
    image_paths = [img.get("path", "") for img in merged_images if img.get("path")]
    existing_analyses = [it.get("vision_analysis", {}) for it in items if it.get("vision_analysis")]
    refined = {}
    if len(image_paths) >= 2:
        try:
            refined = await refine_merged_title(image_paths, existing_analyses, batch)
            if refined.get("refined_title"):
                await db.field_items.update_one({"id": primary["id"]}, {"$set": {
                    "draft_title": refined["refined_title"],
                    "title_refined": True,
                    "updated_at": datetime.now(timezone.utc).isoformat(),
                }})
        except Exception as e:
            logger.error(f"[Field Listing] Post-merge title refinement failed: {e}")

    await log_activity("field_items_merged", details=f"Merged {len(items)} items into 1 in batch {batch.get('name')}")

    # Return updated primary
    updated = await db.field_items.find_one({"id": primary["id"]}, {"_id": 0})
    return {
        "merged_item": updated,
        "removed_count": len(secondary_ids),
        "total_images": len(merged_images),
        "title_refined": bool(refined.get("refined_title")),
        "refined_title": refined.get("refined_title", ""),
    }


# ================== SPLIT ITEM ==================

@field_listing_router.post("/items/{item_id}/split")
async def split_item(item_id: str, user: dict = Depends(get_current_user)):
    """Split a multi-image item back into separate items (one per image)."""
    item = await db.field_items.find_one({"id": item_id}, {"_id": 0})
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")

    images = item.get("images", [])
    if len(images) < 2:
        raise HTTPException(status_code=400, detail="Item has only 1 image, nothing to split")

    batch_id = item["batch_id"]
    now = datetime.now(timezone.utc).isoformat()

    # Keep first image on original item
    await db.field_items.update_one({"id": item_id}, {"$set": {
        "images": [images[0]],
        "merged_from": [],
        "updated_at": now,
    }})

    # Create new items for remaining images
    created = []
    for img in images[1:]:
        new_item = {
            "id": str(uuid.uuid4()),
            "batch_id": batch_id,
            "images": [img],
            "vision_analysis": {},
            "draft_title": item.get("draft_title", ""),
            "short_description": "",
            "category_suggestion": item.get("category_suggestion", ""),
            "tags": list(item.get("tags", [])),
            "unit_cost": item.get("unit_cost"),
            "retail_price": item.get("retail_price"),
            "source_vendor": item.get("source_vendor", ""),
            "condition": item.get("condition", ""),
            "pickup_shipping": item.get("pickup_shipping", ""),
            "confidence": 0,
            "confidence_flag": "pending",
            "status": "draft",
            "grouped_note_ref": item.get("grouped_note_ref", ""),
            "destination_packs": {},
            "split_from": item_id,
            "created_at": now,
            "updated_at": now,
        }
        await db.field_items.insert_one(new_item)
        created.append({k: v for k, v in new_item.items() if k != "_id"})

    # Update batch item count
    total = await db.field_items.count_documents({"batch_id": batch_id})
    await db.field_batches.update_one({"id": batch_id}, {"$set": {
        "item_count": total,
        "updated_at": now,
    }})

    await log_activity("field_item_split", details=f"Split item into {len(images)} separate items")
    return {"original_id": item_id, "new_items": created, "total_split": len(images)}


# ================== SUGGEST GROUPS ==================

@field_listing_router.post("/items/{item_id}/refine-title")
async def refine_item_title(item_id: str, user: dict = Depends(get_current_user)):
    """Re-run title refinement on a multi-image item using all its photos."""
    item = await db.field_items.find_one({"id": item_id}, {"_id": 0})
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")

    images = item.get("images", [])
    if len(images) < 1:
        raise HTTPException(status_code=400, detail="Item has no images")

    batch = await db.field_batches.find_one({"id": item["batch_id"]}, {"_id": 0})

    image_paths = [img.get("path", "") for img in images if img.get("path")]
    existing_analyses = [item.get("vision_analysis", {})] if item.get("vision_analysis") else []

    refined = await refine_merged_title(image_paths, existing_analyses, batch)

    if not refined.get("refined_title"):
        raise HTTPException(status_code=500, detail=refined.get("error", "Title refinement failed"))

    now = datetime.now(timezone.utc).isoformat()
    await db.field_items.update_one({"id": item_id}, {"$set": {
        "draft_title": refined["refined_title"],
        "title_refined": True,
        "updated_at": now,
    }})

    updated = await db.field_items.find_one({"id": item_id}, {"_id": 0})
    return {
        "item": updated,
        "refined_title": refined["refined_title"],
        "details": {k: v for k, v in refined.items() if k != "refined_title"},
    }


@field_listing_router.post("/batches/{batch_id}/suggest-groups")
async def suggest_groups(batch_id: str, user: dict = Depends(get_current_user)):
    """Analyze batch items and suggest which ones might be the same product."""
    batch = await db.field_batches.find_one({"id": batch_id}, {"_id": 0})
    if not batch:
        raise HTTPException(status_code=404, detail="Batch not found")

    items = []
    async for doc in db.field_items.find({"batch_id": batch_id}, {"_id": 0}):
        items.append(doc)

    if len(items) < 2:
        return {"suggestions": [], "message": "Not enough items to suggest groups"}

    groups = suggest_item_groups(items)

    return {
        "suggestions": groups,
        "total_items": len(items),
        "suggested_merges": len(groups),
        "message": f"Found {len(groups)} potential groupings" if groups else "No obvious groupings detected",
    }

