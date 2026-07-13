from fastapi import APIRouter, HTTPException, Depends, Query
from typing import Optional
from datetime import datetime, timezone
import uuid

from database import db, logger
from models import (
    CreateSpecRequest, UpdateSpecRequest, GenerateSpecRequest,
    SubmitFollowUpRequest, UpdateSpecStatusRequest,
    SPEC_TYPES, SPEC_STATUSES,
)
from auth import get_current_user
from services.helpers import log_activity
from services.spec_generation import generate_spec_content, score_spec_completeness


spec_writer_router = APIRouter(prefix="/api")


# ================== SPEC CRUD ==================

@spec_writer_router.get("/specs")
async def list_specs(
    spec_type: Optional[str] = None,
    status: Optional[str] = None,
    priority: Optional[str] = None,
    user: dict = Depends(get_current_user),
):
    query = {}
    if spec_type:
        query["spec_type"] = spec_type
    if status:
        query["status"] = status
    if priority:
        query["priority"] = priority

    specs = await db.specs.find(query, {"_id": 0}).sort("updated_at", -1).to_list(500)
    return {"specs": specs, "total": len(specs)}


@spec_writer_router.get("/specs/stats")
async def get_spec_stats(user: dict = Depends(get_current_user)):
    specs = await db.specs.find({}, {"_id": 0}).to_list(500)
    total = len(specs)
    by_status = {}
    by_type = {}
    by_priority = {}
    scores = []

    for s in specs:
        st = s.get("status", "Draft")
        by_status[st] = by_status.get(st, 0) + 1
        tp = s.get("spec_type", "Unknown")
        by_type[tp] = by_type.get(tp, 0) + 1
        pr = s.get("priority", "P1")
        by_priority[pr] = by_priority.get(pr, 0) + 1
        if s.get("completeness_score"):
            scores.append(s["completeness_score"])

    return {
        "total": total,
        "by_status": by_status,
        "by_type": by_type,
        "by_priority": by_priority,
        "avg_completeness_score": round(sum(scores) / len(scores)) if scores else None,
        "ready_count": by_status.get("Ready", 0),
        "needs_refinement_count": by_status.get("Needs Refinement", 0),
    }


@spec_writer_router.get("/specs/{spec_id}")
async def get_spec(spec_id: str, user: dict = Depends(get_current_user)):
    spec = await db.specs.find_one({"id": spec_id}, {"_id": 0})
    if not spec:
        raise HTTPException(status_code=404, detail="Spec not found")
    return spec


@spec_writer_router.post("/specs", status_code=201)
async def create_spec(request: CreateSpecRequest, user: dict = Depends(get_current_user)):
    if request.spec_type not in SPEC_TYPES:
        raise HTTPException(status_code=400, detail=f"Invalid spec type. Valid: {SPEC_TYPES}")

    spec = {
        "id": str(uuid.uuid4()),
        "title": request.title,
        "spec_type": request.spec_type,
        "raw_idea": request.raw_idea,
        "target_audience": request.target_audience,
        "priority": request.priority,
        "constraints": request.constraints,
        "reference_links": request.reference_links,
        "input_answers": request.input_answers.model_dump() if request.input_answers else {},
        "generated_spec": None,
        "completeness_score": None,
        "score_breakdown": None,
        "complexity_estimate": None,
        "follow_up_questions": [],
        "follow_up_answers": {},
        "status": "Draft",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }

    await db.specs.insert_one(spec)
    spec.pop("_id", None)

    await log_activity("spec_created", details=f"Spec '{request.title}' created ({request.spec_type})")
    return spec


@spec_writer_router.put("/specs/{spec_id}")
async def update_spec(spec_id: str, request: UpdateSpecRequest, user: dict = Depends(get_current_user)):
    existing = await db.specs.find_one({"id": spec_id})
    if not existing:
        raise HTTPException(status_code=404, detail="Spec not found")

    update_data = {}
    if request.title is not None:
        update_data["title"] = request.title
    if request.spec_type is not None:
        if request.spec_type not in SPEC_TYPES:
            raise HTTPException(status_code=400, detail=f"Invalid spec type. Valid: {SPEC_TYPES}")
        update_data["spec_type"] = request.spec_type
    if request.raw_idea is not None:
        update_data["raw_idea"] = request.raw_idea
    if request.target_audience is not None:
        update_data["target_audience"] = request.target_audience
    if request.priority is not None:
        update_data["priority"] = request.priority
    if request.constraints is not None:
        update_data["constraints"] = request.constraints
    if request.reference_links is not None:
        update_data["reference_links"] = request.reference_links
    if request.input_answers is not None:
        update_data["input_answers"] = request.input_answers.model_dump()

    update_data["updated_at"] = datetime.now(timezone.utc).isoformat()
    await db.specs.update_one({"id": spec_id}, {"$set": update_data})

    updated = await db.specs.find_one({"id": spec_id}, {"_id": 0})
    return updated


@spec_writer_router.delete("/specs/{spec_id}")
async def delete_spec(spec_id: str, user: dict = Depends(get_current_user)):
    result = await db.specs.delete_one({"id": spec_id})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Spec not found")
    await db.spec_versions.delete_many({"spec_id": spec_id})
    await log_activity("spec_deleted", details=f"Spec {spec_id} deleted")
    return {"message": "Spec deleted"}


# ================== GENERATION & SCORING ==================

@spec_writer_router.post("/specs/{spec_id}/generate")
async def generate_spec(spec_id: str, request: GenerateSpecRequest = GenerateSpecRequest(), user: dict = Depends(get_current_user)):
    spec = await db.specs.find_one({"id": spec_id}, {"_id": 0})
    if not spec:
        raise HTTPException(status_code=404, detail="Spec not found")

    try:
        content = await generate_spec_content(spec)

        # Save version
        version_count = await db.spec_versions.count_documents({"spec_id": spec_id})
        trigger = "follow_up" if spec.get("follow_up_answers") else "initial"
        if request.regenerate:
            trigger = "regenerate"

        version = {
            "id": str(uuid.uuid4()),
            "spec_id": spec_id,
            "version_number": version_count + 1,
            "generated_spec": content,
            "completeness_score": None,
            "score_breakdown": None,
            "generation_trigger": trigger,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "is_current": True,
        }

        # Mark old versions as non-current
        await db.spec_versions.update_many(
            {"spec_id": spec_id}, {"$set": {"is_current": False}}
        )
        await db.spec_versions.insert_one(version)
        version.pop("_id", None)

        # Update spec
        await db.specs.update_one(
            {"id": spec_id},
            {"$set": {
                "generated_spec": content,
                "status": "Draft",
                "updated_at": datetime.now(timezone.utc).isoformat(),
            }},
        )

        await log_activity("spec_generated", details=f"Spec '{spec.get('title')}' v{version['version_number']} generated")

        updated = await db.specs.find_one({"id": spec_id}, {"_id": 0})
        return {"spec": updated, "version": version}
    except Exception as e:
        logger.error(f"Spec generation failed: {e}")
        raise HTTPException(status_code=500, detail=f"Generation failed: {str(e)}")


@spec_writer_router.post("/specs/{spec_id}/score")
async def score_spec(spec_id: str, user: dict = Depends(get_current_user)):
    spec = await db.specs.find_one({"id": spec_id}, {"_id": 0})
    if not spec:
        raise HTTPException(status_code=404, detail="Spec not found")

    content = spec.get("generated_spec")
    if not content:
        raise HTTPException(status_code=400, detail="Spec has no generated content to score")

    try:
        result = await score_spec_completeness(spec, content)

        overall = result.get("overall_score", 70)
        classification = result.get("classification", "needs_refinement")

        if classification == "ready" or overall >= 85:
            new_status = "Scored"
        elif classification == "major_gaps" or overall < 70:
            new_status = "Needs Refinement"
        else:
            new_status = "Needs Refinement"

        # Extract complexity from spec content if present
        complexity = None
        content_lower = content.lower()
        for level in ["enterprise", "complex", "medium", "simple"]:
            if level in content_lower:
                complexity = level.capitalize()
                break

        await db.specs.update_one(
            {"id": spec_id},
            {"$set": {
                "completeness_score": overall,
                "score_breakdown": result.get("dimension_scores", {}),
                "follow_up_questions": result.get("follow_up_questions", []),
                "complexity_estimate": complexity,
                "status": new_status,
                "updated_at": datetime.now(timezone.utc).isoformat(),
            }},
        )

        # Update current version with score
        await db.spec_versions.update_one(
            {"spec_id": spec_id, "is_current": True},
            {"$set": {
                "completeness_score": overall,
                "score_breakdown": result.get("dimension_scores", {}),
            }},
        )

        await log_activity("spec_scored", details=f"Spec '{spec.get('title')}' scored {overall}/100 ({classification})")

        updated = await db.specs.find_one({"id": spec_id}, {"_id": 0})
        return {"spec": updated, "score_result": result}
    except Exception as e:
        logger.error(f"Spec scoring failed: {e}")
        raise HTTPException(status_code=500, detail=f"Scoring failed: {str(e)}")


@spec_writer_router.post("/specs/{spec_id}/follow-up")
async def submit_follow_up(spec_id: str, request: SubmitFollowUpRequest, user: dict = Depends(get_current_user)):
    spec = await db.specs.find_one({"id": spec_id}, {"_id": 0})
    if not spec:
        raise HTTPException(status_code=404, detail="Spec not found")

    existing_answers = spec.get("follow_up_answers", {}) or {}
    existing_answers.update(request.answers)

    await db.specs.update_one(
        {"id": spec_id},
        {"$set": {
            "follow_up_answers": existing_answers,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }},
    )

    # Re-generate with follow-up context
    updated_spec = await db.specs.find_one({"id": spec_id}, {"_id": 0})
    content = await generate_spec_content(updated_spec)

    version_count = await db.spec_versions.count_documents({"spec_id": spec_id})
    version = {
        "id": str(uuid.uuid4()),
        "spec_id": spec_id,
        "version_number": version_count + 1,
        "generated_spec": content,
        "completeness_score": None,
        "score_breakdown": None,
        "generation_trigger": "follow_up",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "is_current": True,
    }
    await db.spec_versions.update_many(
        {"spec_id": spec_id}, {"$set": {"is_current": False}}
    )
    await db.spec_versions.insert_one(version)
    version.pop("_id", None)

    await db.specs.update_one(
        {"id": spec_id},
        {"$set": {
            "generated_spec": content,
            "follow_up_questions": [],
            "status": "Draft",
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }},
    )

    await log_activity("spec_follow_up", details=f"Spec '{spec.get('title')}' regenerated with follow-up answers")

    final = await db.specs.find_one({"id": spec_id}, {"_id": 0})
    return {"spec": final, "version": version}


# ================== VERSIONS ==================

@spec_writer_router.get("/specs/{spec_id}/versions")
async def list_spec_versions(spec_id: str, user: dict = Depends(get_current_user)):
    spec = await db.specs.find_one({"id": spec_id}, {"_id": 0})
    if not spec:
        raise HTTPException(status_code=404, detail="Spec not found")

    versions = await db.spec_versions.find(
        {"spec_id": spec_id}, {"_id": 0}
    ).sort("version_number", -1).to_list(50)

    return {
        "spec_id": spec_id,
        "title": spec.get("title"),
        "total_versions": len(versions),
        "versions": versions,
    }


@spec_writer_router.post("/specs/{spec_id}/versions/{version_id}/restore")
async def restore_spec_version(spec_id: str, version_id: str, user: dict = Depends(get_current_user)):
    version = await db.spec_versions.find_one({"id": version_id, "spec_id": spec_id}, {"_id": 0})
    if not version:
        raise HTTPException(status_code=404, detail="Version not found")

    await db.spec_versions.update_many(
        {"spec_id": spec_id}, {"$set": {"is_current": False}}
    )
    await db.spec_versions.update_one(
        {"id": version_id}, {"$set": {"is_current": True}}
    )

    await db.specs.update_one(
        {"id": spec_id},
        {"$set": {
            "generated_spec": version.get("generated_spec"),
            "completeness_score": version.get("completeness_score"),
            "score_breakdown": version.get("score_breakdown"),
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }},
    )

    await log_activity("spec_version_restored", details=f"Spec restored to v{version.get('version_number')}")
    updated = await db.specs.find_one({"id": spec_id}, {"_id": 0})
    return updated


# ================== STATUS & EXPORT ==================

@spec_writer_router.post("/specs/{spec_id}/status")
async def update_spec_status(spec_id: str, request: UpdateSpecStatusRequest, user: dict = Depends(get_current_user)):
    if request.status not in SPEC_STATUSES:
        raise HTTPException(status_code=400, detail=f"Invalid status. Valid: {SPEC_STATUSES}")

    result = await db.specs.update_one(
        {"id": spec_id},
        {"$set": {"status": request.status, "updated_at": datetime.now(timezone.utc).isoformat()}},
    )
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Spec not found")

    await log_activity("spec_status_changed", details=f"Spec {spec_id} -> {request.status}")
    updated = await db.specs.find_one({"id": spec_id}, {"_id": 0})
    return updated


@spec_writer_router.get("/specs/{spec_id}/export")
async def export_spec(spec_id: str, user: dict = Depends(get_current_user)):
    spec = await db.specs.find_one({"id": spec_id}, {"_id": 0})
    if not spec:
        raise HTTPException(status_code=404, detail="Spec not found")

    content = spec.get("generated_spec", "")
    if not content:
        raise HTTPException(status_code=400, detail="Spec has no content to export")

    header = f"""---
title: {spec.get('title')}
type: {spec.get('spec_type')}
priority: {spec.get('priority')}
status: {spec.get('status')}
completeness_score: {spec.get('completeness_score', 'N/A')}/100
complexity: {spec.get('complexity_estimate', 'N/A')}
exported: {datetime.now(timezone.utc).isoformat()}
---

"""
    return {"content": header + content, "title": spec.get("title"), "format": "markdown"}
