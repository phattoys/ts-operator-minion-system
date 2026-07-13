from fastapi import APIRouter, HTTPException, Depends
from typing import Optional
from datetime import datetime, timezone
import uuid

from database import db, logger
from models import (
    GenerateCommsRequest, SaveFavoriteRequest,
    COMMS_CHANNELS, COMMS_SCENARIOS,
)
from auth import get_current_user
from services.helpers import log_activity
from services.comms_generation import (
    generate_comms_draft,
    get_scenario,
    check_missing_fields,
)

comms_router = APIRouter(prefix="/api/comms")


@comms_router.get("/scenarios")
async def list_scenarios(user: dict = Depends(get_current_user)):
    return {"scenarios": COMMS_SCENARIOS, "channels": COMMS_CHANNELS}


@comms_router.post("/generate")
async def generate_draft(
    request: GenerateCommsRequest,
    user: dict = Depends(get_current_user),
):
    scenario = get_scenario(request.scenario_key)
    if not scenario:
        raise HTTPException(status_code=400, detail=f"Unknown scenario: {request.scenario_key}")

    if request.channel not in COMMS_CHANNELS:
        raise HTTPException(status_code=400, detail=f"Invalid channel. Must be one of: {COMMS_CHANNELS}")

    context = request.context_fields or {}

    # Check missing required fields
    missing = check_missing_fields(scenario, context, request.generate_with_placeholders)
    if missing:
        return {
            "status": "needs_info",
            "missing_fields": missing,
            "scenario": scenario,
            "message": f"Required fields missing: {', '.join(f.replace('_', ' ') for f in missing)}. Fill them in or enable 'Generate with placeholders'.",
        }

    result = await generate_comms_draft(
        scenario_key=request.scenario_key,
        channel=request.channel,
        customer_message=request.customer_message or "",
        context_fields=context,
        max_discretion=request.max_discretion,
        use_placeholders=request.generate_with_placeholders,
    )

    now = datetime.now(timezone.utc).isoformat()
    draft = {
        "id": str(uuid.uuid4()),
        "scenario_key": request.scenario_key,
        "scenario_label": scenario["label"],
        "channel": request.channel,
        "customer_message": request.customer_message or "",
        "context_fields": context,
        "max_discretion": request.max_discretion,
        "used_placeholders": request.generate_with_placeholders,
        "subject": result.get("subject"),
        "variants": result.get("variants", []),
        "ps_line": result.get("ps_line"),
        "is_favorite": False,
        "favorite_label": "",
        "created_at": now,
    }
    await db.comms_drafts.insert_one(draft)
    await log_activity("comms_generated", details=f"Generated {request.channel} draft: {scenario['label']}")

    return {k: v for k, v in draft.items() if k != "_id"}


@comms_router.get("/history")
async def list_history(
    scenario_key: Optional[str] = None,
    channel: Optional[str] = None,
    search: Optional[str] = None,
    favorites_only: bool = False,
    limit: int = 50,
    user: dict = Depends(get_current_user),
):
    query = {}
    if scenario_key:
        query["scenario_key"] = scenario_key
    if channel:
        query["channel"] = channel
    if favorites_only:
        query["is_favorite"] = True
    if search:
        query["$or"] = [
            {"scenario_label": {"$regex": search, "$options": "i"}},
            {"context_fields.order_number": {"$regex": search, "$options": "i"}},
            {"context_fields.customer_name": {"$regex": search, "$options": "i"}},
        ]

    drafts = []
    async for doc in db.comms_drafts.find(query, {"_id": 0}).sort("created_at", -1).limit(limit):
        drafts.append(doc)
    return {"drafts": drafts, "count": len(drafts)}


@comms_router.get("/history/{draft_id}")
async def get_draft(draft_id: str, user: dict = Depends(get_current_user)):
    draft = await db.comms_drafts.find_one({"id": draft_id}, {"_id": 0})
    if not draft:
        raise HTTPException(status_code=404, detail="Draft not found")
    return draft


@comms_router.post("/history/{draft_id}/favorite")
async def toggle_favorite(
    draft_id: str,
    request: SaveFavoriteRequest,
    user: dict = Depends(get_current_user),
):
    draft = await db.comms_drafts.find_one({"id": draft_id}, {"_id": 0})
    if not draft:
        raise HTTPException(status_code=404, detail="Draft not found")

    new_fav = not draft.get("is_favorite", False)
    updates = {"is_favorite": new_fav}
    if request.label:
        updates["favorite_label"] = request.label

    await db.comms_drafts.update_one({"id": draft_id}, {"$set": updates})
    updated = await db.comms_drafts.find_one({"id": draft_id}, {"_id": 0})
    return updated


@comms_router.post("/history/{draft_id}/duplicate")
async def duplicate_draft(draft_id: str, user: dict = Depends(get_current_user)):
    draft = await db.comms_drafts.find_one({"id": draft_id}, {"_id": 0})
    if not draft:
        raise HTTPException(status_code=404, detail="Draft not found")

    return {
        "scenario_key": draft["scenario_key"],
        "channel": draft["channel"],
        "customer_message": draft.get("customer_message", ""),
        "context_fields": draft.get("context_fields", {}),
        "max_discretion": draft.get("max_discretion", False),
    }


@comms_router.delete("/history/{draft_id}")
async def delete_draft(draft_id: str, user: dict = Depends(get_current_user)):
    draft = await db.comms_drafts.find_one({"id": draft_id}, {"_id": 0})
    if not draft:
        raise HTTPException(status_code=404, detail="Draft not found")
    await db.comms_drafts.delete_one({"id": draft_id})
    return {"message": "Draft deleted"}


@comms_router.get("/stats")
async def comms_stats(user: dict = Depends(get_current_user)):
    total = await db.comms_drafts.count_documents({})
    favorites = await db.comms_drafts.count_documents({"is_favorite": True})

    by_scenario = {}
    async for doc in db.comms_drafts.aggregate([
        {"$group": {"_id": "$scenario_key", "count": {"$sum": 1}}}
    ]):
        by_scenario[doc["_id"]] = doc["count"]

    by_channel = {}
    async for doc in db.comms_drafts.aggregate([
        {"$group": {"_id": "$channel", "count": {"$sum": 1}}}
    ]):
        by_channel[doc["_id"]] = doc["count"]

    return {
        "total_drafts": total,
        "favorites": favorites,
        "by_scenario": by_scenario,
        "by_channel": by_channel,
    }
