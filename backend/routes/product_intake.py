import csv
import io
import os
from pydantic import BaseModel
from fastapi import APIRouter, HTTPException, Depends, UploadFile, File, Form
from fastapi.responses import StreamingResponse
from typing import Optional
from datetime import datetime, timezone, timedelta
import uuid

from database import db, logger
from models import (
    CreateIntakeSessionRequest, UpdateIntakeSessionRequest,
    ExtractTextRequest, CreateDraftItemRequest, UpdateDraftItemRequest,
    UpdateIntakeSettingsRequest,
    INTAKE_SOURCE_TYPES, DRAFT_ITEM_STATUSES, ROUNDING_RULES,
    DEFAULT_TAXONOMY, DRAFT_ITEM_REQUIRED_FIELDS,
)
from auth import get_current_user
from services.helpers import log_activity
from services.product_intake import (
    extract_items_from_text,
    generate_listing_content,
    calculate_suggested_price,
    compute_missing_fields,
    parse_csv_content,
    check_duplicate_flags,
    parse_cost_notes,
)
from services.pdf_intake import process_pdf

intake_router = APIRouter(prefix="/api/intake")


# ================== HELPERS ==================

async def get_intake_settings() -> dict:
    settings = await db.intake_settings.find_one({}, {"_id": 0})
    if not settings:
        settings = {
            "default_markup_multiplier": 2.5,
            "min_price": 9.99,
            "rounding_rule": "nearest_99",
            "category_overrides": {},
            "taxonomy": DEFAULT_TAXONOMY,
            "stuck_days_threshold": 7,
        }
        await db.intake_settings.insert_one(settings)
    return settings


async def recount_session(session_id: str):
    counts = {"needs_info": 0, "in_review": 0, "ready": 0}
    async for item in db.draft_items.find({"session_id": session_id}, {"status": 1}):
        st = item.get("status", "needs_info")
        if st in counts:
            counts[st] += 1
    total = sum(counts.values())
    await db.intake_sessions.update_one(
        {"id": session_id},
        {"$set": {
            "item_count": total,
            "needs_info_count": counts["needs_info"],
            "in_review_count": counts["in_review"],
            "ready_count": counts["ready"],
        }}
    )


# ================== STATS ==================

@intake_router.get("/stats")
async def intake_stats(user: dict = Depends(get_current_user)):
    session_count = await db.intake_sessions.count_documents({})
    item_count = await db.draft_items.count_documents({})

    status_pipeline = [{"$group": {"_id": "$status", "count": {"$sum": 1}}}]
    status_counts = {}
    async for doc in db.draft_items.aggregate(status_pipeline):
        status_counts[doc["_id"]] = doc["count"]

    settings = await get_intake_settings()
    stuck_days = settings.get("stuck_days_threshold", 7)
    cutoff = (datetime.now(timezone.utc) - timedelta(days=stuck_days)).isoformat()
    stuck_count = await db.draft_items.count_documents({
        "status": "needs_info",
        "created_at": {"$lte": cutoff},
    })

    return {
        "total_sessions": session_count,
        "total_items": item_count,
        "by_status": status_counts,
        "ready_count": status_counts.get("ready", 0),
        "needs_info_count": status_counts.get("needs_info", 0),
        "in_review_count": status_counts.get("in_review", 0),
        "stuck_count": stuck_count,
        "stuck_days_threshold": stuck_days,
    }


# ================== SESSIONS CRUD ==================

@intake_router.get("/sessions")
async def list_sessions(user: dict = Depends(get_current_user)):
    sessions = []
    async for doc in db.intake_sessions.find({}, {"_id": 0}).sort("created_at", -1):
        sessions.append(doc)
    return {"sessions": sessions}


@intake_router.post("/sessions")
async def create_session(
    request: CreateIntakeSessionRequest,
    user: dict = Depends(get_current_user),
):
    if not request.source_store or len(request.source_store.strip()) < 1:
        raise HTTPException(status_code=400, detail="Source store is required")

    now = datetime.now(timezone.utc).isoformat()
    session = {
        "id": str(uuid.uuid4()),
        "source_store": request.source_store.strip(),
        "order_id": (request.order_id or "").strip(),
        "purchase_date": (request.purchase_date or "").strip(),
        "notes": (request.notes or "").strip(),
        "item_count": 0,
        "needs_info_count": 0,
        "in_review_count": 0,
        "ready_count": 0,
        "created_at": now,
        "updated_at": now,
    }
    await db.intake_sessions.insert_one(session)
    await log_activity("intake_session_created", details=f"Created intake session: {request.source_store}")

    return {k: v for k, v in session.items() if k != "_id"}


@intake_router.get("/sessions/{session_id}")
async def get_session(session_id: str, user: dict = Depends(get_current_user)):
    session = await db.intake_sessions.find_one({"id": session_id}, {"_id": 0})
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    items = []
    async for doc in db.draft_items.find({"session_id": session_id}, {"_id": 0}).sort("created_at", 1):
        doc["missing_fields"] = compute_missing_fields(doc)
        items.append(doc)

    session["items"] = items
    return session


@intake_router.put("/sessions/{session_id}")
async def update_session(
    session_id: str,
    request: UpdateIntakeSessionRequest,
    user: dict = Depends(get_current_user),
):
    session = await db.intake_sessions.find_one({"id": session_id}, {"_id": 0})
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    updates = {}
    for field, value in request.dict(exclude_unset=True).items():
        if value is not None:
            updates[field] = value.strip() if isinstance(value, str) else value

    if updates:
        updates["updated_at"] = datetime.now(timezone.utc).isoformat()
        await db.intake_sessions.update_one({"id": session_id}, {"$set": updates})

    updated = await db.intake_sessions.find_one({"id": session_id}, {"_id": 0})
    return updated


@intake_router.delete("/sessions/{session_id}")
async def delete_session(session_id: str, user: dict = Depends(get_current_user)):
    session = await db.intake_sessions.find_one({"id": session_id}, {"_id": 0})
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    await db.draft_items.delete_many({"session_id": session_id})
    await db.intake_sessions.delete_one({"id": session_id})
    await log_activity("intake_session_deleted", details=f"Deleted session: {session.get('source_store')}")
    return {"message": "Session and all items deleted"}


# ================== TEXT EXTRACTION ==================

@intake_router.post("/sessions/{session_id}/extract")
async def extract_from_text(
    session_id: str,
    request: ExtractTextRequest,
    user: dict = Depends(get_current_user),
):
    session = await db.intake_sessions.find_one({"id": session_id}, {"_id": 0})
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    if request.source_type not in INTAKE_SOURCE_TYPES:
        raise HTTPException(status_code=400, detail=f"Invalid source type. Must be one of: {INTAKE_SOURCE_TYPES}")

    if not request.text or len(request.text.strip()) < 10:
        raise HTTPException(status_code=400, detail="Text must be at least 10 characters")

    settings = await get_intake_settings()
    extracted = await extract_items_from_text(request.text, session.get("source_store", ""))

    created_items = []
    for raw in extracted:
        unit_cost = None
        try:
            unit_cost = float(raw.get("unit_cost")) if raw.get("unit_cost") is not None else None
        except (ValueError, TypeError):
            pass

        suggested_price = None
        if unit_cost is not None and unit_cost > 0:
            suggested_price = calculate_suggested_price(unit_cost, settings)

        now = datetime.now(timezone.utc).isoformat()
        item = {
            "id": str(uuid.uuid4()),
            "session_id": session_id,
            "source_type": request.source_type,
            "source_store": session.get("source_store", ""),
            "source_title": raw.get("source_title", ""),
            "clean_title": "",
            "short_description": "",
            "long_description": "",
            "color": raw.get("color") or "",
            "size": raw.get("size") or "",
            "style": raw.get("style") or "",
            "quantity": int(raw.get("quantity", 1)) if raw.get("quantity") else 1,
            "unit_cost": unit_cost,
            "currency": raw.get("currency", "USD"),
            "suggested_price": suggested_price,
            "category": "",
            "category_suggestions": [],
            "tags": [],
            "tag_suggestions": [],
            "source_url": raw.get("source_url") or "",
            "status": "needs_info",
            "extraction_evidence": raw.get("extraction_evidence", ""),
            "publish_notes": "",
            "created_at": now,
            "updated_at": now,
        }
        await db.draft_items.insert_one(item)
        result = {k: v for k, v in item.items() if k != "_id"}
        result["missing_fields"] = compute_missing_fields(result)
        created_items.append(result)

    await recount_session(session_id)
    await log_activity("intake_extraction", details=f"Extracted {len(created_items)} items from text in session {session.get('source_store')}")

    return {"extracted_count": len(created_items), "items": created_items}




# ================== BULK ACTIONS ==================

class BulkActionRequest(BaseModel):
    item_ids: list[str]
    action: str  # "set_status", "set_category", "add_tags"
    value: str   # status name, category name, or comma-separated tags


@intake_router.post("/sessions/{session_id}/bulk-action")
async def bulk_action(
    session_id: str,
    request: BulkActionRequest,
    user: dict = Depends(get_current_user),
):
    """Apply a bulk action to selected items in a session."""
    session = await db.intake_sessions.find_one({"id": session_id}, {"_id": 0})
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    if not request.item_ids:
        raise HTTPException(status_code=400, detail="No items selected")

    valid_actions = ["set_status", "set_category", "add_tags"]
    if request.action not in valid_actions:
        raise HTTPException(status_code=400, detail=f"Invalid action. Must be one of: {valid_actions}")

    now = datetime.now(timezone.utc).isoformat()
    updated = 0
    skipped = []

    for item_id in request.item_ids:
        item = await db.draft_items.find_one({"id": item_id, "session_id": session_id}, {"_id": 0})
        if not item:
            skipped.append({"id": item_id, "reason": "not_found"})
            continue

        updates = {"updated_at": now}

        if request.action == "set_status":
            target_status = request.value
            if target_status not in DRAFT_ITEM_STATUSES:
                skipped.append({"id": item_id, "reason": f"invalid_status:{target_status}"})
                continue

            # Guard: don't mark as ready if item fails validation
            if target_status == "ready":
                eligible, reason = validate_item_for_export(item)
                if not eligible:
                    skipped.append({
                        "id": item_id,
                        "title": item.get("clean_title", item.get("source_title", ""))[:50],
                        "reason": reason,
                    })
                    continue

            updates["status"] = target_status

        elif request.action == "set_category":
            if not request.value.strip():
                skipped.append({"id": item_id, "reason": "empty_category"})
                continue
            updates["category"] = request.value.strip()

        elif request.action == "add_tags":
            new_tags = [t.strip() for t in request.value.split(",") if t.strip()]
            if not new_tags:
                skipped.append({"id": item_id, "reason": "empty_tags"})
                continue
            existing_tags = item.get("tags", []) or []
            merged = list(dict.fromkeys(existing_tags + new_tags))  # dedupe, preserve order
            updates["tags"] = merged

        await db.draft_items.update_one({"id": item_id}, {"$set": updates})
        updated += 1

    await recount_session(session_id)
    action_label = {"set_status": f"status→{request.value}", "set_category": f"category→{request.value}", "add_tags": f"tags+{request.value}"}
    await log_activity(
        "intake_bulk_action",
        details=f"Bulk {action_label.get(request.action, request.action)}: {updated} updated, {len(skipped)} skipped in session {session.get('source_store', session_id)}"
    )

    return {
        "action": request.action,
        "value": request.value,
        "updated": updated,
        "skipped": len(skipped),
        "skipped_items": skipped,
        "total_selected": len(request.item_ids),
    }


# ================== COST NOTES ==================

class CostNotesRequest(BaseModel):
    cost_notes: str

@intake_router.post("/sessions/{session_id}/apply-cost-notes")
async def apply_cost_notes(
    session_id: str,
    request: CostNotesRequest,
    user: dict = Depends(get_current_user),
):
    """
    Parse founder cost notes and apply cost/retail overrides to matching items.
    Notes like: "this group was $25 and retails at $55"
    """
    session = await db.intake_sessions.find_one({"id": session_id}, {"_id": 0})
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    if not request.cost_notes.strip():
        raise HTTPException(status_code=400, detail="Cost notes cannot be empty")

    # Get all items in session
    items = []
    async for doc in db.draft_items.find({"session_id": session_id}, {"_id": 0}):
        items.append(doc)

    if not items:
        raise HTTPException(status_code=400, detail="No items in session to apply cost notes to")

    # Parse notes via LLM
    parsed = await parse_cost_notes(request.cost_notes, items)

    if not parsed:
        return {
            "applied": 0,
            "total_items": len(items),
            "matches": [],
            "message": "Could not parse any cost rules from the notes. Try being more specific.",
        }

    settings = await get_intake_settings()
    now = datetime.now(timezone.utc).isoformat()
    applied_count = 0
    match_details = []

    for rule in parsed:
        item_ids = rule.get("item_ids", [])
        unit_cost = rule.get("unit_cost")
        retail_price = rule.get("retail_price")
        note_text = rule.get("note_text", "")
        confidence = rule.get("confidence", "medium")

        if not item_ids:
            continue

        for item_id in item_ids:
            updates = {}
            if unit_cost is not None:
                updates["unit_cost"] = float(unit_cost)
            if retail_price is not None:
                updates["suggested_price"] = float(retail_price)
            elif unit_cost is not None:
                # Recalculate suggested price from new cost
                updates["suggested_price"] = calculate_suggested_price(float(unit_cost), settings)

            if updates:
                updates["updated_at"] = now
                # Store the cost note as evidence
                existing = next((it for it in items if it["id"] == item_id), None)
                if existing:
                    existing_attrs = existing.get("attribute_suggestions", {})
                    existing_attrs["cost_note"] = note_text
                    updates["attribute_suggestions"] = existing_attrs

                await db.draft_items.update_one({"id": item_id}, {"$set": updates})
                applied_count += 1

        match_details.append({
            "note": note_text,
            "matched_items": len(item_ids),
            "unit_cost": unit_cost,
            "retail_price": retail_price,
            "confidence": confidence,
            "reason": rule.get("match_reason", ""),
        })

    # Save cost notes on session
    await db.intake_sessions.update_one(
        {"id": session_id},
        {"$set": {"cost_notes": request.cost_notes, "updated_at": now}}
    )

    await log_activity(
        "intake_cost_notes",
        details=f"Applied cost notes to {applied_count} items ({len(parsed)} rules parsed) in session {session.get('source_store', session_id)}"
    )

    return {
        "applied": applied_count,
        "total_items": len(items),
        "rules_parsed": len(parsed),
        "matches": match_details,
        "message": f"Applied {applied_count} cost updates from {len(parsed)} parsed rules",
    }


# ================== CSV/TSV FILE UPLOAD ==================

@intake_router.post("/sessions/{session_id}/upload-csv")
async def upload_csv(
    session_id: str,
    file: UploadFile = File(...),
    user: dict = Depends(get_current_user),
):
    session = await db.intake_sessions.find_one({"id": session_id}, {"_id": 0})
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    if not file.filename:
        raise HTTPException(status_code=400, detail="No file provided")

    ext = file.filename.lower().rsplit('.', 1)[-1] if '.' in file.filename else ''
    if ext not in ('csv', 'tsv', 'txt'):
        raise HTTPException(status_code=400, detail="File must be CSV, TSV, or TXT")

    try:
        content = (await file.read()).decode('utf-8', errors='replace')
    except Exception:
        raise HTTPException(status_code=400, detail="Could not read file content")

    if len(content.strip()) < 10:
        raise HTTPException(status_code=400, detail="File is too short or empty")

    delimiter = '\t' if ext == 'tsv' else None
    parsed = parse_csv_content(content, delimiter)

    if not parsed:
        raise HTTPException(status_code=400, detail="No valid product rows found in file. Ensure headers include product/name/title and price/cost columns.")

    settings = await get_intake_settings()
    created_items = []

    for raw in parsed:
        unit_cost = None
        if raw.get('unit_cost') is not None:
            try:
                unit_cost = float(raw['unit_cost'])
            except (ValueError, TypeError):
                pass

        suggested_price = None
        if unit_cost and unit_cost > 0:
            suggested_price = calculate_suggested_price(unit_cost, settings)

        now = datetime.now(timezone.utc).isoformat()
        item = {
            "id": str(uuid.uuid4()),
            "session_id": session_id,
            "source_type": "csv_upload",
            "source_store": session.get("source_store", ""),
            "source_title": raw.get("source_title", ""),
            "clean_title": "",
            "short_description": "",
            "long_description": "",
            "color": raw.get("color", ""),
            "size": raw.get("size", ""),
            "style": raw.get("style", ""),
            "quantity": raw.get("quantity", 1) or 1,
            "unit_cost": unit_cost,
            "currency": raw.get("currency", "USD"),
            "suggested_price": suggested_price,
            "category": "",
            "category_suggestions": [],
            "tags": [],
            "tag_suggestions": [],
            "attribute_suggestions": {},
            "duplicate_flags": [],
            "source_url": raw.get("source_url", ""),
            "status": "needs_info",
            "extraction_evidence": "",
            "publish_notes": raw.get("notes", ""),
            "created_at": now,
            "updated_at": now,
        }

        if raw.get("material"):
            item["attribute_suggestions"]["material"] = raw["material"]
        if raw.get("brand"):
            item["attribute_suggestions"]["brand"] = raw["brand"]
        if raw.get("sku"):
            item["attribute_suggestions"]["sku"] = raw["sku"]

        await db.draft_items.insert_one(item)
        result = {k: v for k, v in item.items() if k != "_id"}
        result["missing_fields"] = compute_missing_fields(result)
        created_items.append(result)

    await recount_session(session_id)
    await log_activity("intake_csv_upload", details=f"Uploaded {len(created_items)} items from {file.filename} in session {session.get('source_store')}")

    return {
        "uploaded_count": len(created_items),
        "filename": file.filename,
        "items": created_items,
    }



# ================== PDF FILE UPLOAD (with background processing for Vision) ==================

async def _process_pdf_and_save_items(session_id: str, pdf_path: str, filename: str, job_id: str):
    """Background task: process PDF and save extracted items to DB."""
    try:
        result = await process_pdf(pdf_path)

        if not result["items"]:
            await db.pdf_jobs.update_one({"id": job_id}, {"$set": {
                "status": "failed",
                "error": "No product items found in PDF.",
                "completed_at": datetime.now(timezone.utc).isoformat(),
            }})
            return

        session = await db.intake_sessions.find_one({"id": session_id}, {"_id": 0})
        settings = await get_intake_settings()
        detected_vendor = result.get("detected_vendor", "")
        extraction_method = result.get("extraction_method", "regex")
        created_count = 0

        for raw in result["items"]:
            unit_cost = raw.get("unit_cost")
            list_price = raw.get("list_price")
            suggested_price = None
            if unit_cost and unit_cost > 0:
                suggested_price = calculate_suggested_price(unit_cost, settings)

            now = datetime.now(timezone.utc).isoformat()
            item = {
                "id": str(uuid.uuid4()),
                "session_id": session_id,
                "source_type": "pdf_upload",
                "source_store": (session or {}).get("source_store", "") or detected_vendor,
                "source_title": raw.get("source_title", ""),
                "clean_title": "",
                "short_description": "",
                "long_description": "",
                "color": raw.get("color", ""),
                "size": raw.get("size", ""),
                "style": "",
                "quantity": raw.get("quantity", 1) or 1,
                "unit_cost": unit_cost,
                "currency": "USD",
                "suggested_price": suggested_price,
                "category": "",
                "category_suggestions": [],
                "tags": [],
                "tag_suggestions": [],
                "attribute_suggestions": {},
                "duplicate_flags": [],
                "source_url": "",
                "status": "needs_info",
                "extraction_evidence": f"PDF page {raw.get('page_num', '?')} | {extraction_method}" + (f" | SKU: {raw.get('sku', '')}" if raw.get("sku") else ""),
                "publish_notes": "",
                "created_at": now,
                "updated_at": now,
            }
            if raw.get("sku"):
                item["attribute_suggestions"]["sku"] = raw["sku"]
            if list_price:
                item["attribute_suggestions"]["list_price"] = str(list_price)
            if detected_vendor:
                item["attribute_suggestions"]["vendor"] = detected_vendor
            if raw.get("vendor") and raw["vendor"] != detected_vendor:
                item["attribute_suggestions"]["vendor"] = raw["vendor"]

            await db.draft_items.insert_one(item)
            created_count += 1

        await recount_session(session_id)
        await log_activity(
            "intake_pdf_upload",
            details=f"Uploaded {created_count} items from {filename} ({result['total_pages']} pages, {result['duplicate_count']} dupes merged, method={extraction_method}) in session {(session or {}).get('source_store', session_id)}"
        )

        await db.pdf_jobs.update_one({"id": job_id}, {"$set": {
            "status": "completed",
            "uploaded_count": created_count,
            "total_pages": result["total_pages"],
            "product_pages": result["product_pages"],
            "raw_item_count": result["raw_item_count"],
            "duplicate_count": result["duplicate_count"],
            "detected_vendor": detected_vendor,
            "extraction_method": extraction_method,
            "duplicate_log": result["duplicate_log"][:20],
            "completed_at": datetime.now(timezone.utc).isoformat(),
        }})

    except Exception as e:
        logger.error(f"[PDF Job {job_id}] Processing failed: {e}")
        await db.pdf_jobs.update_one({"id": job_id}, {"$set": {
            "status": "failed",
            "error": str(e)[:500],
            "completed_at": datetime.now(timezone.utc).isoformat(),
        }})
    finally:
        try:
            os.unlink(pdf_path)
        except Exception:
            pass


@intake_router.post("/sessions/{session_id}/upload-pdf")
async def upload_pdf(
    session_id: str,
    file: UploadFile = File(...),
    user: dict = Depends(get_current_user),
):
    session = await db.intake_sessions.find_one({"id": session_id}, {"_id": 0})
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    if not file.filename:
        raise HTTPException(status_code=400, detail="No file provided")

    ext = file.filename.lower().rsplit('.', 1)[-1] if '.' in file.filename else ''
    if ext != 'pdf':
        raise HTTPException(status_code=400, detail="File must be a PDF")

    # Save to persistent temp file
    try:
        content = await file.read()
        if len(content) < 100:
            raise HTTPException(status_code=400, detail="PDF file is too small or empty")

        pdf_dir = "/app/backend/pdf_storage"
        os.makedirs(pdf_dir, exist_ok=True)
        pdf_filename = f"{uuid.uuid4()}.pdf"
        pdf_path = os.path.join(pdf_dir, pdf_filename)
        with open(pdf_path, "wb") as f:
            f.write(content)
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=400, detail="Could not read PDF file")

    # Quick check: does this PDF have text? (determines sync vs async path)
    from services.pdf_intake import extract_text_from_pdf, has_usable_text
    pages = extract_text_from_pdf(pdf_path)
    needs_vision = not has_usable_text(pages)

    if needs_vision:
        # Image-based PDF → process in background, return job ID for polling
        job_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc).isoformat()
        await db.pdf_jobs.insert_one({
            "id": job_id,
            "session_id": session_id,
            "filename": file.filename,
            "status": "processing",
            "total_pages": len(pages),
            "extraction_method": "vision_llm",
            "created_at": now,
        })

        import asyncio
        asyncio.create_task(_process_pdf_and_save_items(session_id, pdf_path, file.filename, job_id))

        return {
            "status": "processing",
            "job_id": job_id,
            "message": f"Image-based PDF detected ({len(pages)} pages). Processing via Vision AI — this takes ~2-3 minutes. Poll /api/intake/pdf-jobs/{job_id} for status.",
            "total_pages": len(pages),
            "extraction_method": "vision_llm",
        }
    else:
        # Text-based PDF → process synchronously (fast regex)
        try:
            result = await process_pdf(pdf_path)
        except Exception as e:
            logger.error(f"PDF processing error: {e}")
            raise HTTPException(status_code=500, detail=f"PDF processing failed: {str(e)}")
        finally:
            try:
                os.unlink(pdf_path)
            except Exception:
                pass

        if not result["items"]:
            raise HTTPException(
                status_code=400,
                detail="No product items found in PDF. The PDF may be empty or in an unsupported format."
            )

        settings = await get_intake_settings()
        created_items = []
        detected_vendor = result.get("detected_vendor", "")
        extraction_method = result.get("extraction_method", "regex")

        for raw in result["items"]:
            unit_cost = raw.get("unit_cost")
            list_price = raw.get("list_price")
            suggested_price = None
            if unit_cost and unit_cost > 0:
                suggested_price = calculate_suggested_price(unit_cost, settings)

            now = datetime.now(timezone.utc).isoformat()
            item = {
                "id": str(uuid.uuid4()),
                "session_id": session_id,
                "source_type": "pdf_upload",
                "source_store": session.get("source_store", "") or detected_vendor,
                "source_title": raw.get("source_title", ""),
                "clean_title": "",
                "short_description": "",
                "long_description": "",
                "color": raw.get("color", ""),
                "size": raw.get("size", ""),
                "style": "",
                "quantity": raw.get("quantity", 1) or 1,
                "unit_cost": unit_cost,
                "currency": "USD",
                "suggested_price": suggested_price,
                "category": "",
                "category_suggestions": [],
                "tags": [],
                "tag_suggestions": [],
                "attribute_suggestions": {},
                "duplicate_flags": [],
                "source_url": "",
                "status": "needs_info",
                "extraction_evidence": f"PDF page {raw.get('page_num', '?')} | {extraction_method}" + (f" | SKU: {raw.get('sku', '')}" if raw.get("sku") else ""),
                "publish_notes": "",
                "created_at": now,
                "updated_at": now,
            }
            if raw.get("sku"):
                item["attribute_suggestions"]["sku"] = raw["sku"]
            if list_price:
                item["attribute_suggestions"]["list_price"] = str(list_price)
            if detected_vendor:
                item["attribute_suggestions"]["vendor"] = detected_vendor
            if raw.get("vendor") and raw["vendor"] != detected_vendor:
                item["attribute_suggestions"]["vendor"] = raw["vendor"]

            await db.draft_items.insert_one(item)
            result_item = {k: v for k, v in item.items() if k != "_id"}
            result_item["missing_fields"] = compute_missing_fields(result_item)
            created_items.append(result_item)

        await recount_session(session_id)
        await log_activity(
            "intake_pdf_upload",
            details=f"Uploaded {len(created_items)} items from {file.filename} ({result['total_pages']} pages, {result['duplicate_count']} dupes merged) in session {session.get('source_store')}"
        )

        return {
            "status": "completed",
            "uploaded_count": len(created_items),
            "filename": file.filename,
            "total_pages": result["total_pages"],
            "product_pages": result["product_pages"],
            "raw_item_count": result["raw_item_count"],
            "duplicate_count": result["duplicate_count"],
            "detected_vendor": detected_vendor,
            "extraction_method": extraction_method,
            "duplicate_log": result["duplicate_log"][:20],
            "items": created_items,
        }


@intake_router.get("/pdf-jobs/{job_id}")
async def get_pdf_job_status(job_id: str, user: dict = Depends(get_current_user)):
    """Poll for the status of a background PDF processing job."""
    job = await db.pdf_jobs.find_one({"id": job_id}, {"_id": 0})
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return job


# ================== DUPLICATE CHECK ==================

@intake_router.get("/items/{item_id}/check-duplicates")
async def check_item_duplicates(item_id: str, user: dict = Depends(get_current_user)):
    item = await db.draft_items.find_one({"id": item_id}, {"_id": 0})
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")

    title = item.get("clean_title") or item.get("source_title") or ""
    sku = (item.get("attribute_suggestions") or {}).get("sku", "")
    flags = await check_duplicate_flags(title, sku)

    # Save flags to item
    await db.draft_items.update_one({"id": item_id}, {"$set": {"duplicate_flags": flags}})

    return {"item_id": item_id, "duplicate_flags": flags, "count": len(flags)}


# ================== ITEMS CRUD ==================

@intake_router.post("/sessions/{session_id}/items")
async def create_item(
    session_id: str,
    request: CreateDraftItemRequest,
    user: dict = Depends(get_current_user),
):
    session = await db.intake_sessions.find_one({"id": session_id}, {"_id": 0})
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    settings = await get_intake_settings()
    suggested_price = None
    if request.unit_cost is not None and request.unit_cost > 0:
        suggested_price = calculate_suggested_price(request.unit_cost, settings)

    now = datetime.now(timezone.utc).isoformat()
    item = {
        "id": str(uuid.uuid4()),
        "session_id": session_id,
        "source_type": request.source_type if request.source_type in INTAKE_SOURCE_TYPES else "manual_entry",
        "source_store": session.get("source_store", ""),
        "source_title": (request.source_title or "").strip(),
        "clean_title": (request.clean_title or "").strip(),
        "short_description": "",
        "long_description": "",
        "color": (request.color or "").strip(),
        "size": (request.size or "").strip(),
        "style": (request.style or "").strip(),
        "quantity": request.quantity or 1,
        "unit_cost": request.unit_cost,
        "currency": request.currency or "USD",
        "suggested_price": suggested_price,
        "category": "",
        "category_suggestions": [],
        "tags": [],
        "tag_suggestions": [],
        "source_url": (request.source_url or "").strip(),
        "status": "needs_info",
        "extraction_evidence": "",
        "publish_notes": (request.notes or "").strip(),
        "created_at": now,
        "updated_at": now,
    }
    await db.draft_items.insert_one(item)
    await recount_session(session_id)
    await log_activity("intake_item_created", details=f"Added item manually: {item['source_title'] or item['clean_title'] or 'Untitled'}")

    result = {k: v for k, v in item.items() if k != "_id"}
    result["missing_fields"] = compute_missing_fields(result)
    return result


@intake_router.get("/items/{item_id}")
async def get_item(item_id: str, user: dict = Depends(get_current_user)):
    item = await db.draft_items.find_one({"id": item_id}, {"_id": 0})
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")
    item["missing_fields"] = compute_missing_fields(item)
    return item


@intake_router.put("/items/{item_id}")
async def update_item(
    item_id: str,
    request: UpdateDraftItemRequest,
    user: dict = Depends(get_current_user),
):
    item = await db.draft_items.find_one({"id": item_id}, {"_id": 0})
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")

    updates = {}
    for field, value in request.dict(exclude_unset=True).items():
        if value is not None:
            updates[field] = value

    if "status" in updates:
        new_status = updates["status"]
        if new_status not in DRAFT_ITEM_STATUSES:
            raise HTTPException(status_code=400, detail=f"Invalid status. Must be one of: {DRAFT_ITEM_STATUSES}")
        if new_status == "ready":
            test_item = {**item, **updates}
            missing = compute_missing_fields(test_item)
            if missing:
                raise HTTPException(
                    status_code=400,
                    detail=f"Cannot mark Ready. Missing fields: {', '.join(missing)}"
                )

    if updates:
        updates["updated_at"] = datetime.now(timezone.utc).isoformat()
        await db.draft_items.update_one({"id": item_id}, {"$set": updates})

    await recount_session(item["session_id"])

    updated = await db.draft_items.find_one({"id": item_id}, {"_id": 0})
    updated["missing_fields"] = compute_missing_fields(updated)
    return updated


@intake_router.delete("/items/{item_id}")
async def delete_item(item_id: str, user: dict = Depends(get_current_user)):
    item = await db.draft_items.find_one({"id": item_id}, {"_id": 0})
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")

    await db.draft_items.delete_one({"id": item_id})
    await recount_session(item["session_id"])
    await log_activity("intake_item_deleted", details=f"Deleted item: {item.get('clean_title') or item.get('source_title')}")
    return {"message": "Item deleted"}


# ================== AI GENERATION ==================

@intake_router.post("/items/{item_id}/generate")
async def generate_item_listing(item_id: str, user: dict = Depends(get_current_user)):
    item = await db.draft_items.find_one({"id": item_id}, {"_id": 0})
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")

    if not item.get("source_title") and not item.get("clean_title"):
        raise HTTPException(status_code=400, detail="Item needs at least a source title or clean title before generating content.")

    settings = await get_intake_settings()
    taxonomy = settings.get("taxonomy", DEFAULT_TAXONOMY)
    result = await generate_listing_content(item, taxonomy)

    # Extract confidence
    confidence = result.get("confidence", {})
    conf_score = 0.5
    if isinstance(confidence, dict):
        conf_score = confidence.get("score", 0.5)
    elif isinstance(confidence, (int, float)):
        conf_score = float(confidence)
        confidence = {"score": conf_score}

    # Merge attribute_suggestions: preserve existing (sku, vendor, list_price), add new
    existing_attrs = item.get("attribute_suggestions", {})
    new_attrs = result.get("attribute_suggestions", {})
    merged_attrs = {**existing_attrs}
    for k, v in new_attrs.items():
        if v and v != "null":
            merged_attrs[k] = v

    updates = {
        "clean_title": result.get("clean_title", item.get("clean_title", "")),
        "short_description": result.get("short_description", ""),
        "long_description": result.get("long_description", ""),
        "category_suggestions": result.get("category_suggestions", []),
        "tag_suggestions": result.get("tag_suggestions", []),
        "attribute_suggestions": merged_attrs,
        "generation_confidence": confidence,
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }

    if result.get("category_suggestions"):
        updates["category"] = result["category_suggestions"][0]
    if result.get("tag_suggestions"):
        updates["tags"] = result["tag_suggestions"]

    # Fill color/size/style from LLM if not already set
    if new_attrs.get("color") and new_attrs["color"] != "null" and not item.get("color"):
        updates["color"] = new_attrs["color"]
    if new_attrs.get("size") and new_attrs["size"] != "null" and not item.get("size"):
        updates["size"] = new_attrs["size"]
    if new_attrs.get("style") and new_attrs["style"] != "null" and not item.get("style"):
        updates["style"] = new_attrs["style"]

    if item.get("unit_cost") and not item.get("suggested_price"):
        updates["suggested_price"] = calculate_suggested_price(
            item["unit_cost"], settings, updates.get("category")
        )

    # Status: move to in_review if confidence ok
    if conf_score >= 0.5:
        updates["status"] = "in_review"
    # Preserve duplicate_flags — never overwrite

    await db.draft_items.update_one({"id": item_id}, {"$set": updates})
    await log_activity("intake_item_generated", details=f"Generated listing for: {updates.get('clean_title', 'item')}")

    updated = await db.draft_items.find_one({"id": item_id}, {"_id": 0})
    updated["missing_fields"] = compute_missing_fields(updated)
    return updated


# ================== BATCH GENERATE ==================

@intake_router.post("/sessions/{session_id}/generate-all")
async def generate_all_items(session_id: str, user: dict = Depends(get_current_user)):
    session = await db.intake_sessions.find_one({"id": session_id}, {"_id": 0})
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    items = []
    async for doc in db.draft_items.find(
        {"session_id": session_id, "short_description": {"$in": ["", None]}},
        {"_id": 0}
    ):
        if doc.get("source_title") or doc.get("clean_title"):
            items.append(doc)

    if not items:
        return {
            "message": "No items need generation",
            "generated": 0, "failed": 0, "flagged": 0, "total": 0,
            "results": [],
        }

    settings = await get_intake_settings()
    taxonomy = settings.get("taxonomy", DEFAULT_TAXONOMY)
    generated = 0
    failed = 0
    flagged = 0
    results = []

    for item in items:
        item_result = {"id": item["id"], "source_title": item.get("source_title", "")}
        try:
            result = await generate_listing_content(item, taxonomy)

            # Extract confidence
            confidence = result.get("confidence", {})
            conf_score = 0.5
            if isinstance(confidence, dict):
                conf_score = confidence.get("score", 0.5)
            elif isinstance(confidence, (int, float)):
                conf_score = float(confidence)
                confidence = {"score": conf_score}

            # Merge attribute_suggestions: preserve existing (sku, vendor, list_price), add new
            existing_attrs = item.get("attribute_suggestions", {})
            new_attrs = result.get("attribute_suggestions", {})
            merged_attrs = {**existing_attrs}
            for k, v in new_attrs.items():
                if v and v != "null":
                    merged_attrs[k] = v

            updates = {
                "clean_title": result.get("clean_title", item.get("clean_title", "")),
                "short_description": result.get("short_description", ""),
                "long_description": result.get("long_description", ""),
                "category_suggestions": result.get("category_suggestions", []),
                "tag_suggestions": result.get("tag_suggestions", []),
                "attribute_suggestions": merged_attrs,
                "generation_confidence": confidence,
                "updated_at": datetime.now(timezone.utc).isoformat(),
            }

            if result.get("category_suggestions"):
                updates["category"] = result["category_suggestions"][0]
            if result.get("tag_suggestions"):
                updates["tags"] = result["tag_suggestions"]

            # Fill color/size/style from LLM if not already set
            if new_attrs.get("color") and new_attrs["color"] != "null" and not item.get("color"):
                updates["color"] = new_attrs["color"]
            if new_attrs.get("size") and new_attrs["size"] != "null" and not item.get("size"):
                updates["size"] = new_attrs["size"]
            if new_attrs.get("style") and new_attrs["style"] != "null" and not item.get("style"):
                updates["style"] = new_attrs["style"]

            # Price: recalculate with category if missing
            if item.get("unit_cost") and not item.get("suggested_price"):
                updates["suggested_price"] = calculate_suggested_price(
                    item["unit_cost"], settings, updates.get("category")
                )

            # Status: move to in_review if confidence >= 0.5, else flag for review
            if conf_score >= 0.5:
                updates["status"] = "in_review"
            else:
                updates["status"] = "needs_info"
                flagged += 1

            # Preserve duplicate_flags — never overwrite
            await db.draft_items.update_one({"id": item["id"]}, {"$set": updates})
            generated += 1
            item_result["status"] = "generated"
            item_result["clean_title"] = updates["clean_title"]
            item_result["confidence"] = conf_score
            item_result["new_status"] = updates["status"]
            item_result["category"] = updates.get("category", "")

        except Exception as e:
            logger.error(f"Batch generation failed for item {item['id']}: {e}")
            failed += 1
            item_result["status"] = "failed"
            item_result["error"] = str(e)[:100]

        results.append(item_result)

    await recount_session(session_id)
    await log_activity(
        "intake_batch_generated",
        details=f"Batch generated {generated}/{len(items)} items ({flagged} low-confidence) in session {session.get('source_store', session_id)}"
    )

    return {
        "message": f"Generated {generated} of {len(items)} items",
        "generated": generated,
        "failed": failed,
        "flagged": flagged,
        "total": len(items),
        "results": results,
    }


# ================== MARK READY & EXPORT ==================

WOO_CSV_FIELDS = [
    "Name", "Type", "SKU", "Published", "Is featured?",
    "Short description", "Description", "Regular price", "Sale price",
    "Categories", "Tags", "Images",
    "Attribute 1 name", "Attribute 1 value(s)",
    "Attribute 2 name", "Attribute 2 value(s)",
    "Attribute 3 name", "Attribute 3 value(s)",
    "Stock", "Meta: _source_title", "Meta: _source_sku",
    "Meta: _unit_cost", "Meta: _vendor", "Meta: _confidence",
]


def validate_item_for_export(item: dict) -> tuple[bool, str]:
    """Check if an item is eligible for mark-ready + export.
    Returns (eligible, reason_if_not).
    """
    # Missing critical fields
    missing = []
    if not item.get("clean_title"):
        missing.append("clean_title")
    if not item.get("short_description"):
        missing.append("short_description")
    if not item.get("category"):
        missing.append("category")
    if item.get("suggested_price") is None and item.get("unit_cost") is None:
        missing.append("price")
    if missing:
        return False, f"missing_fields:{','.join(missing)}"

    # Low confidence
    conf = item.get("generation_confidence", {})
    score = conf.get("score", 1.0) if isinstance(conf, dict) else 1.0
    if score < 0.4:
        return False, f"low_confidence:{score:.0%}"

    # Unresolved duplicates (has dupe flags but hasn't been reviewed past them)
    dupe_flags = item.get("duplicate_flags", [])
    if len(dupe_flags) > 2:
        return False, f"unresolved_duplicates:{len(dupe_flags)}"

    return True, ""


def item_to_woo_row(item: dict) -> dict:
    """Convert a draft item to a WooCommerce CSV row."""
    attrs = item.get("attribute_suggestions", {})
    tags = item.get("tags", [])
    if isinstance(tags, list):
        tags = ", ".join(tags)

    row = {
        "Name": item.get("clean_title", ""),
        "Type": "simple",
        "SKU": attrs.get("sku", ""),
        "Published": "0",  # Never auto-publish — always draft in WooCommerce
        "Is featured?": "0",
        "Short description": item.get("short_description", ""),
        "Description": item.get("long_description", ""),
        "Regular price": str(item.get("suggested_price", "")) if item.get("suggested_price") else "",
        "Sale price": "",
        "Categories": item.get("category", ""),
        "Tags": tags,
        "Images": "",
        "Attribute 1 name": "Color" if item.get("color") else "",
        "Attribute 1 value(s)": item.get("color", ""),
        "Attribute 2 name": "Size" if item.get("size") else "",
        "Attribute 2 value(s)": item.get("size", ""),
        "Attribute 3 name": "Material" if attrs.get("material") else "",
        "Attribute 3 value(s)": attrs.get("material", ""),
        "Stock": str(item.get("quantity", 1)),
        "Meta: _source_title": item.get("source_title", ""),
        "Meta: _source_sku": attrs.get("sku", ""),
        "Meta: _unit_cost": str(item.get("unit_cost", "")) if item.get("unit_cost") else "",
        "Meta: _vendor": attrs.get("vendor", ""),
        "Meta: _confidence": str(item.get("generation_confidence", {}).get("score", "")) if item.get("generation_confidence") else "",
    }
    return row


async def build_woo_csv_content(session_id: str) -> str:
    """Build WooCommerce CSV content string for ready items. Used by Spine execution."""
    items = []
    async for doc in db.draft_items.find(
        {"session_id": session_id, "status": "ready"},
        {"_id": 0}
    ).sort("created_at", 1):
        items.append(doc)

    if not items:
        return ""

    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=WOO_CSV_FIELDS)
    writer.writeheader()
    for item in items:
        writer.writerow(item_to_woo_row(item))
    return output.getvalue()



@intake_router.post("/sessions/{session_id}/mark-ready-export")
async def mark_ready_and_export(
    session_id: str,
    user: dict = Depends(get_current_user),
):
    """
    Full re-validate + export cycle (Quick Re-import safe):
    1. Re-validate existing 'ready' items — demote any that now fail
    2. Validate 'in_review' items — promote eligible ones to ready
    3. Export ALL currently ready items as WooCommerce CSV
    """
    session = await db.intake_sessions.find_one({"id": session_id}, {"_id": 0})
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    now = datetime.now(timezone.utc).isoformat()

    # Phase 1: Re-validate existing ready items (catch edits that broke them)
    demoted = []
    async for doc in db.draft_items.find(
        {"session_id": session_id, "status": "ready"}, {"_id": 0}
    ):
        eligible, reason = validate_item_for_export(doc)
        if not eligible:
            await db.draft_items.update_one(
                {"id": doc["id"]},
                {"$set": {"status": "in_review", "updated_at": now}}
            )
            demoted.append({
                "id": doc["id"],
                "clean_title": doc.get("clean_title", ""),
                "reason": reason,
                "action": "demoted",
            })

    # Phase 2: Validate in_review items — promote eligible
    newly_ready = []
    held_back = []
    async for doc in db.draft_items.find(
        {"session_id": session_id, "status": "in_review"}, {"_id": 0}
    ):
        eligible, reason = validate_item_for_export(doc)
        if eligible:
            await db.draft_items.update_one(
                {"id": doc["id"]},
                {"$set": {"status": "ready", "updated_at": now}}
            )
            newly_ready.append(doc)
        else:
            held_back.append({
                "id": doc["id"],
                "source_title": doc.get("source_title", ""),
                "clean_title": doc.get("clean_title", ""),
                "reason": reason,
            })

    # Phase 3: Export ALL currently ready items
    all_ready = []
    async for doc in db.draft_items.find(
        {"session_id": session_id, "status": "ready"}, {"_id": 0}
    ).sort("created_at", 1):
        all_ready.append(doc)

    csv_data = ""
    if all_ready:
        output = io.StringIO()
        writer = csv.DictWriter(output, fieldnames=WOO_CSV_FIELDS)
        writer.writeheader()
        for item in all_ready:
            writer.writerow(item_to_woo_row(item))
        csv_data = output.getvalue()

    # Track export timestamp
    await db.intake_sessions.update_one(
        {"id": session_id},
        {"$set": {"last_exported_at": now, "updated_at": now}}
    )
    await recount_session(session_id)

    action_summary = []
    if newly_ready:
        action_summary.append(f"{len(newly_ready)} newly ready")
    if demoted:
        action_summary.append(f"{len(demoted)} demoted")
    if held_back:
        action_summary.append(f"{len(held_back)} held back")
    await log_activity(
        "intake_export",
        details=f"Exported {len(all_ready)} items ({', '.join(action_summary) or 'no changes'}) in session {session.get('source_store', session_id)}"
    )

    return {
        "exported": len(all_ready),
        "newly_ready": len(newly_ready),
        "demoted": len(demoted),
        "held_back": len(held_back),
        "total_in_session": len(all_ready) + len(held_back) + len(demoted),
        "held_back_items": held_back,
        "demoted_items": demoted,
        "csv_data": csv_data,
        "csv_filename": f"woo-import-{session.get('source_store', 'export').replace(' ', '-').lower()}-{datetime.now(timezone.utc).strftime('%Y%m%d-%H%M')}.csv",
        "exported_at": now,
    }


@intake_router.get("/sessions/{session_id}/export-woo")
async def export_woo_csv(
    session_id: str,
    user: dict = Depends(get_current_user),
):
    """Export ready items as WooCommerce-formatted CSV file download."""
    session = await db.intake_sessions.find_one({"id": session_id}, {"_id": 0})
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    items = []
    async for doc in db.draft_items.find(
        {"session_id": session_id, "status": "ready"},
        {"_id": 0}
    ).sort("created_at", 1):
        items.append(doc)

    if not items:
        raise HTTPException(status_code=400, detail="No ready items to export. Use 'Mark Ready & Export' first.")

    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=WOO_CSV_FIELDS)
    writer.writeheader()
    for item in items:
        writer.writerow(item_to_woo_row(item))

    output.seek(0)
    filename = f"woo-import-{session.get('source_store', 'export').replace(' ', '-').lower()}-{datetime.now(timezone.utc).strftime('%Y%m%d')}.csv"

    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )


# ================== BASIC EXPORT ==================

@intake_router.get("/sessions/{session_id}/export")
async def export_session(
    session_id: str,
    include_non_ready: bool = False,
    user: dict = Depends(get_current_user),
):
    session = await db.intake_sessions.find_one({"id": session_id}, {"_id": 0})
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    query = {"session_id": session_id}
    if not include_non_ready:
        query["status"] = "ready"

    items = []
    async for doc in db.draft_items.find(query, {"_id": 0}).sort("created_at", 1):
        items.append(doc)

    if not items:
        raise HTTPException(status_code=400, detail="No items to export" + (" (only Ready items are exported by default)" if not include_non_ready else ""))

    output = io.StringIO()
    fields = [
        "clean_title", "short_description", "long_description",
        "category", "tags", "suggested_price", "unit_cost", "currency",
        "quantity", "color", "size", "style",
        "source_store", "source_url", "source_title",
        "status", "publish_notes", "id",
    ]
    writer = csv.DictWriter(output, fieldnames=fields)
    writer.writeheader()
    for item in items:
        row = {}
        for f in fields:
            val = item.get(f, "")
            if isinstance(val, list):
                val = "; ".join(val)
            row[f] = val
        writer.writerow(row)

    output.seek(0)
    filename = f"intake-{session.get('source_store', 'export').replace(' ', '-').lower()}-{datetime.now(timezone.utc).strftime('%Y%m%d')}.csv"

    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )


# ================== SETTINGS ==================

@intake_router.get("/settings")
async def get_settings(user: dict = Depends(get_current_user)):
    return await get_intake_settings()


@intake_router.put("/settings")
async def update_settings(
    request: UpdateIntakeSettingsRequest,
    user: dict = Depends(get_current_user),
):
    await get_intake_settings()  # ensure defaults exist

    updates = {}
    for field, value in request.dict(exclude_unset=True).items():
        if value is not None:
            if field == "rounding_rule" and value not in ROUNDING_RULES:
                raise HTTPException(status_code=400, detail=f"Invalid rounding rule. Must be one of: {ROUNDING_RULES}")
            if field == "default_markup_multiplier" and value < 1:
                raise HTTPException(status_code=400, detail="Markup multiplier must be >= 1")
            if field == "min_price" and value < 0:
                raise HTTPException(status_code=400, detail="Min price must be >= 0")
            updates[field] = value

    if updates:
        await db.intake_settings.update_one({}, {"$set": updates}, upsert=True)
        await log_activity("intake_settings_updated", details=f"Updated intake settings: {', '.join(updates.keys())}")

    return await get_intake_settings()
