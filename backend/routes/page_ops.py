from fastapi import APIRouter, HTTPException, Depends, Query
from typing import Optional, List
from datetime import datetime, timezone
import uuid
import re

from database import db, PAGE_GENERATION_MODEL, QUALITY_SCORING_MODEL, logger
from models import (
    PageCreate, PageUpdate, PageResponse, GenerateRequest, TightenRequest, VariantRequest,
    PageVersion, VersionListResponse, LabelVersionRequest, RestoreVersionRequest,
    CreateExemplarRequest, UpdateExemplarRequest, EXEMPLAR_REASON_TAGS,
    CreateHouseTemplateRequest, UpdateHouseTemplateRequest,
    CreateStyleProfileRequest, UpdateStyleProfileRequest, TonalControls, SEED_STYLE_PROFILES,
    PromotionActionRequest, PROMOTION_THRESHOLDS,
    ExportRequest, ExportedPage, ExportResponse,
    BatchGenerateRequest, BatchGenerateResult, BatchGenerateResponse,
    PageDependencyInfo,
)
from auth import get_current_user
from services.helpers import (
    log_activity, create_version, get_page_versions, get_version, get_current_version,
    calculate_priority_score, get_recommended_next_pages, evaluate_promotion_signals,
)
from services.generation import (
    generate_page_content, apply_taste_tightener, generate_with_variant, score_page_quality,
)


page_ops_router = APIRouter(prefix="/api")


# ================== PAGES CRUD ==================

@page_ops_router.get("/pages")
async def get_pages(status: Optional[str] = None, family: Optional[str] = None, user: dict = Depends(get_current_user)):
    query = {}
    if status:
        query["status"] = status
    if family:
        query["page_family"] = family
    
    pages = await db.pages.find(query, {"_id": 0}).sort("priority_score", -1).to_list(1000)
    return {"pages": pages, "total": len(pages)}

@page_ops_router.get("/pages/recommended")
async def get_recommended(limit: int = 5, user: dict = Depends(get_current_user)):
    pages = await db.pages.find({}, {"_id": 0}).to_list(1000)
    recommended = get_recommended_next_pages(pages, limit)
    return recommended

@page_ops_router.get("/pages/{page_id}", response_model=PageResponse)
async def get_page(page_id: str, user: dict = Depends(get_current_user)):
    page = await db.pages.find_one({"id": page_id}, {"_id": 0})
    if not page:
        raise HTTPException(status_code=404, detail="Page not found")
    return page

@page_ops_router.post("/pages", response_model=PageResponse, status_code=201)
async def create_page(page: PageCreate, user: dict = Depends(get_current_user)):
    slug = page.slug or page.page_name.lower().replace(" ", "-").replace("&", "and").replace("'", "")
    
    new_page = {
        "id": str(uuid.uuid4()),
        "page_name": page.page_name,
        "slug": slug,
        "page_family": page.page_family,
        "district_or_pillar": page.district_or_pillar,
        "page_type": page.page_type,
        "audience": page.audience,
        "purpose": page.purpose,
        "CTA_type": page.CTA_type,
        "keyword_or_theme": page.keyword_or_theme,
        "parent_page": page.parent_page,
        "priority_score": calculate_priority_score(page.model_dump()),
        "status": "Planned",
        "quality_score": None,
        "score_notes": None,
        "edit_recommendations": None,
        "generated_content": None,
        "generation_history": [],
        "review_notes": None,
        "notes": page.notes,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "updated_at": datetime.now(timezone.utc).isoformat()
    }
    
    await db.pages.insert_one(new_page)
    new_page.pop("_id", None)
    
    await log_activity("page_created", new_page["id"], page.page_name, f"Created in {page.page_family}")
    return new_page

@page_ops_router.put("/pages/{page_id}", response_model=PageResponse)
async def update_page(page_id: str, page_update: PageUpdate, user: dict = Depends(get_current_user)):
    existing = await db.pages.find_one({"id": page_id})
    if not existing:
        raise HTTPException(status_code=404, detail="Page not found")
    
    update_data = {k: v for k, v in page_update.model_dump().items() if v is not None}
    update_data["updated_at"] = datetime.now(timezone.utc).isoformat()
    
    await db.pages.update_one({"id": page_id}, {"$set": update_data})
    
    updated = await db.pages.find_one({"id": page_id}, {"_id": 0})
    return updated

@page_ops_router.delete("/pages/{page_id}")
async def delete_page(page_id: str, user: dict = Depends(get_current_user)):
    result = await db.pages.delete_one({"id": page_id})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Page not found")
    return {"message": "Page deleted"}


# ================== GENERATION & SCORING ==================

@page_ops_router.post("/pages/{page_id}/generate", response_model=PageResponse)
async def generate_content(page_id: str, request: GenerateRequest, user: dict = Depends(get_current_user)):
    page = await db.pages.find_one({"id": page_id}, {"_id": 0})
    if not page:
        raise HTTPException(status_code=404, detail="Page not found")
    
    await db.pages.update_one({"id": page_id}, {"$set": {"status": "Generating"}})
    
    try:
        house_template = None
        if request.use_house_template:
            if request.template_id:
                house_template = await db.house_templates.find_one(
                    {"id": request.template_id, "status": "active"}, {"_id": 0}
                )
            else:
                house_template = await db.house_templates.find_one(
                    {"page_family": page.get("page_family"), "is_primary": True, "status": "active"}, {"_id": 0}
                )
        
        style_profile = None
        if request.use_style_profile:
            if request.style_profile_id:
                style_profile = await db.style_profiles.find_one(
                    {"id": request.style_profile_id, "status": "active"}, {"_id": 0}
                )
            else:
                style_profile = await db.style_profiles.find_one(
                    {"page_families": page.get("page_family"), "is_default": True, "status": "active"}, {"_id": 0}
                )
        
        exemplars = await db.exemplars.find(
            {"page_family": page.get("page_family")},
            {"_id": 0}
        ).sort("is_primary", -1).to_list(3)
        
        exemplar_context = ""
        if exemplars:
            exemplar_snippets = []
            for ex in exemplars[:2]:
                content = ex.get("generated_content", "")
                if content:
                    preview = content[:800]
                    primary_label = " (PRIMARY EXEMPLAR)" if ex.get("is_primary") else ""
                    exemplar_snippets.append(f"--- Exemplar{primary_label}: {ex.get('page_name', 'Unknown')} ---\n{preview}\n---")
            if exemplar_snippets:
                exemplar_context = "\n\nREFERENCE EXEMPLARS (study these for quality and voice, but create ORIGINAL content):\n" + "\n\n".join(exemplar_snippets)
        
        additional = request.additional_instructions or ""
        if exemplar_context:
            additional = (additional + "\n" + exemplar_context) if additional else exemplar_context
        
        content = await generate_page_content(
            page, request.tone, additional, house_template, style_profile, request.content_direction
        )
        
        content = re.sub(r'(?i)\bCTA:\s*', '', content)
        content = re.sub(r'(?i)\[CTA\]\s*', '', content)
        
        history_entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "tone": request.tone,
            "model": PAGE_GENERATION_MODEL,
            "content_preview": content[:200] if content else "",
            "template_used": house_template.get("template_name") if house_template else None,
            "style_profile_used": style_profile.get("profile_name") if style_profile else None,
            "exemplars_referenced": len(exemplars)
        }
        
        await db.pages.update_one(
            {"id": page_id},
            {
                "$set": {"generated_content": content, "status": "Draft Ready",
                         "updated_at": datetime.now(timezone.utc).isoformat()},
                "$push": {"generation_history": history_entry}
            }
        )
        
        version = await create_version(
            page_id, content, "generate",
            model_used=PAGE_GENERATION_MODEL,
            tone_used=request.tone
        )
        
        template_note = f" + template '{house_template.get('template_name')}'" if house_template else ""
        style_note = f" + style '{style_profile.get('profile_name')}'" if style_profile else ""
        exemplar_note = f" + {len(exemplars)} exemplar(s)" if exemplars else ""
        await log_activity("page_generated", page_id, page.get("page_name"),
                          f"Generated v{version['version_number']} (tone: {request.tone}){template_note}{style_note}{exemplar_note}")
        
        updated_page = await db.pages.find_one({"id": page_id}, {"_id": 0})
        return updated_page
    except Exception as e:
        await db.pages.update_one({"id": page_id}, {"$set": {"status": "Planned"}})
        raise HTTPException(status_code=500, detail=str(e))

@page_ops_router.post("/pages/{page_id}/tighten", response_model=PageResponse)
async def tighten_page(page_id: str, request: TightenRequest = TightenRequest(), user: dict = Depends(get_current_user)):
    page = await db.pages.find_one({"id": page_id}, {"_id": 0})
    if not page:
        raise HTTPException(status_code=404, detail="Page not found")
    
    content = page.get("generated_content")
    if not content:
        raise HTTPException(status_code=400, detail="No content to tighten")
    
    tightened = await apply_taste_tightener(content, page)
    
    await db.pages.update_one(
        {"id": page_id},
        {"$set": {"generated_content": tightened, "updated_at": datetime.now(timezone.utc).isoformat()}}
    )
    
    version = await create_version(
        page_id, tightened, "tighten",
        model_used=QUALITY_SCORING_MODEL,
        tightened=True
    )
    
    await log_activity("page_tightened", page_id, page.get("page_name"),
                      f"Taste tightener applied -> v{version['version_number']}")
    
    updated = await db.pages.find_one({"id": page_id}, {"_id": 0})
    return updated

@page_ops_router.post("/pages/{page_id}/variant", response_model=PageResponse)
async def generate_variant(page_id: str, request: VariantRequest, user: dict = Depends(get_current_user)):
    page = await db.pages.find_one({"id": page_id}, {"_id": 0})
    if not page:
        raise HTTPException(status_code=404, detail="Page not found")
    
    base_content = page.get("generated_content")
    variant_content = await generate_with_variant(page, request.variant, base_content)
    
    if request.save_as_current:
        await db.pages.update_one(
            {"id": page_id},
            {"$set": {"generated_content": variant_content, "updated_at": datetime.now(timezone.utc).isoformat()}}
        )
    
    version = await create_version(
        page_id, variant_content, "variant",
        model_used=PAGE_GENERATION_MODEL,
        variant_used=request.variant,
        make_current=request.save_as_current
    )
    
    await log_activity("variant_generated", page_id, page.get("page_name"),
                      f"Variant '{request.variant}' -> v{version['version_number']}")
    
    updated = await db.pages.find_one({"id": page_id}, {"_id": 0})
    return updated

@page_ops_router.post("/pages/{page_id}/score", response_model=PageResponse)
async def score_page(page_id: str, user: dict = Depends(get_current_user)):
    page = await db.pages.find_one({"id": page_id}, {"_id": 0})
    if not page:
        raise HTTPException(status_code=404, detail="Page not found")
    
    if not page.get("generated_content"):
        raise HTTPException(status_code=400, detail="Page has no generated content to score")
    
    try:
        score_result = await score_page_quality(page, page["generated_content"])
        
        overall_score = score_result.get("overall_score", 75)
        classification = score_result.get("classification", "usable")
        
        if classification == "strong" or overall_score >= 85:
            new_status = "Needs Review"
        elif classification == "rewrite" or overall_score < 70:
            new_status = "Needs Rewrite"
        else:
            new_status = "Needs Review"
        
        update_data = {
            "quality_score": overall_score,
            "score_notes": score_result,
            "edit_recommendations": score_result.get("edit_recommendations", []),
            "status": new_status,
            "updated_at": datetime.now(timezone.utc).isoformat()
        }
        
        await db.pages.update_one({"id": page_id}, {"$set": update_data})
        await log_activity("page_scored", page_id, page.get("page_name"), f"Score: {overall_score}/100 - {classification}")
        
        if overall_score >= PROMOTION_THRESHOLDS["template_min_score"]:
            try:
                current_version = await db.page_versions.find_one(
                    {"page_id": page_id, "is_current": True}, {"_id": 0}
                )
                if current_version:
                    await db.page_versions.update_one(
                        {"id": current_version["id"]},
                        {"$set": {"quality_score": overall_score, "score_notes": score_result}}
                    )
                    existing_cand = await db.promotion_candidates.find_one(
                        {"version_id": current_version["id"], "status": {"$in": ["pending", "deferred"]}}
                    )
                    if not existing_cand:
                        promo_result = evaluate_promotion_signals(current_version, page, score_result)
                        if promo_result["is_promotable"]:
                            cand = {
                                "id": str(uuid.uuid4()),
                                "page_id": page_id,
                                "version_id": current_version["id"],
                                "page_name": page.get("page_name"),
                                "page_family": page.get("page_family"),
                                "page_type": page.get("page_type"),
                                "version_number": current_version.get("version_number"),
                                "quality_score": overall_score,
                                "signals": promo_result["signals"],
                                "promotion_types": promo_result["promotion_types"],
                                "recommendation_reason": promo_result["recommendation_reason"],
                                "status": "pending",
                                "action_taken": None,
                                "action_details": None,
                                "created_at": datetime.now(timezone.utc).isoformat(),
                                "updated_at": datetime.now(timezone.utc).isoformat(),
                                "resolved_at": None
                            }
                            await db.promotion_candidates.insert_one(cand)
                            logger.info(f"Auto-flagged v{current_version.get('version_number')} for promotion: {promo_result['promotion_types']}")
            except Exception as promo_err:
                logger.warning(f"Promotion evaluation failed (non-blocking): {promo_err}")
        
        updated_page = await db.pages.find_one({"id": page_id}, {"_id": 0})
        return updated_page
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ================== APPROVAL ACTIONS ==================

@page_ops_router.post("/pages/{page_id}/approve", response_model=PageResponse)
async def approve_page(page_id: str, user: dict = Depends(get_current_user)):
    result = await db.pages.update_one(
        {"id": page_id},
        {"$set": {"status": "Approved", "updated_at": datetime.now(timezone.utc).isoformat()}}
    )
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Page not found")
    page = await db.pages.find_one({"id": page_id}, {"_id": 0})
    await log_activity("page_approved", page_id, page.get("page_name"), "Page approved")

    # Auto-create WP Placement worker task
    try:
        from services.worker_queue import route_page_to_wp
        await route_page_to_wp(page_id)
    except Exception as e:
        logger.warning(f"[Page Ops] Failed to create WP worker task for {page_id}: {e}")

    return page

@page_ops_router.post("/pages/{page_id}/rewrite", response_model=PageResponse)
async def send_to_rewrite(page_id: str, user: dict = Depends(get_current_user)):
    result = await db.pages.update_one(
        {"id": page_id},
        {"$set": {"status": "Needs Rewrite", "updated_at": datetime.now(timezone.utc).isoformat()}}
    )
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Page not found")
    page = await db.pages.find_one({"id": page_id}, {"_id": 0})
    await log_activity("page_rewrite", page_id, page.get("page_name"), "Sent to rewrite queue")
    return page

@page_ops_router.post("/pages/{page_id}/defer", response_model=PageResponse)
async def defer_page(page_id: str, user: dict = Depends(get_current_user)):
    result = await db.pages.update_one(
        {"id": page_id},
        {"$set": {"status": "Deferred", "updated_at": datetime.now(timezone.utc).isoformat()}}
    )
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Page not found")
    page = await db.pages.find_one({"id": page_id}, {"_id": 0})
    await log_activity("page_deferred", page_id, page.get("page_name"), "Page deferred")
    return page


# ================== VERSION HISTORY ==================

@page_ops_router.get("/pages/{page_id}/versions")
async def list_versions(page_id: str, user: dict = Depends(get_current_user)):
    page = await db.pages.find_one({"id": page_id}, {"_id": 0})
    if not page:
        raise HTTPException(status_code=404, detail="Page not found")
    
    versions = await get_page_versions(page_id)
    current = next((v for v in versions if v.get("is_current")), None)
    
    return VersionListResponse(
        page_id=page_id,
        page_name=page.get("page_name"),
        total_versions=len(versions),
        current_version=current.get("version_number") if current else 0,
        versions=[PageVersion(**v) for v in versions]
    )

@page_ops_router.get("/pages/{page_id}/versions/{version_id}")
async def get_single_version(page_id: str, version_id: str, user: dict = Depends(get_current_user)):
    version = await get_version(version_id)
    if not version or version.get("page_id") != page_id:
        raise HTTPException(status_code=404, detail="Version not found")
    return version

@page_ops_router.post("/pages/{page_id}/versions/{version_id}/restore", response_model=PageResponse)
async def restore_version(page_id: str, version_id: str, request: RestoreVersionRequest = RestoreVersionRequest(), user: dict = Depends(get_current_user)):
    page = await db.pages.find_one({"id": page_id}, {"_id": 0})
    if not page:
        raise HTTPException(status_code=404, detail="Page not found")
    
    version = await get_version(version_id)
    if not version or version.get("page_id") != page_id:
        raise HTTPException(status_code=404, detail="Version not found")
    
    if request.preserve_current_as_version and page.get("generated_content"):
        await create_version(
            page_id, page["generated_content"], "pre-restore-snapshot",
            quality_score=page.get("quality_score"),
            make_current=False
        )
    
    await db.page_versions.update_many({"page_id": page_id}, {"$set": {"is_current": False}})
    await db.page_versions.update_one({"id": version_id}, {"$set": {"is_current": True}})
    
    await db.pages.update_one(
        {"id": page_id},
        {"$set": {
            "generated_content": version["generated_content"],
            "quality_score": version.get("quality_score"),
            "score_notes": version.get("score_notes"),
            "updated_at": datetime.now(timezone.utc).isoformat()
        }}
    )
    
    await log_activity("version_restored", page_id, page.get("page_name"),
                      f"Restored to v{version.get('version_number')}")
    
    updated = await db.pages.find_one({"id": page_id}, {"_id": 0})
    return updated

@page_ops_router.put("/pages/{page_id}/versions/{version_id}/label")
async def label_version(page_id: str, version_id: str, request: LabelVersionRequest, user: dict = Depends(get_current_user)):
    version = await get_version(version_id)
    if not version or version.get("page_id") != page_id:
        raise HTTPException(status_code=404, detail="Version not found")
    
    await db.page_versions.update_one(
        {"id": version_id},
        {"$set": {"label": request.label}}
    )
    
    updated = await db.page_versions.find_one({"id": version_id}, {"_id": 0})
    return updated

@page_ops_router.get("/pages/{page_id}/versions/compare")
async def compare_versions(page_id: str, version_a: str = Query(...), version_b: str = Query(...), user: dict = Depends(get_current_user)):
    v_a = await get_version(version_a)
    v_b = await get_version(version_b)
    
    if not v_a or v_a.get("page_id") != page_id:
        raise HTTPException(status_code=404, detail="Version A not found")
    if not v_b or v_b.get("page_id") != page_id:
        raise HTTPException(status_code=404, detail="Version B not found")
    
    return {
        "version_a": v_a,
        "version_b": v_b,
        "content_length_diff": len(v_a.get("generated_content", "")) - len(v_b.get("generated_content", "")),
        "score_diff": (v_a.get("quality_score") or 0) - (v_b.get("quality_score") or 0) if v_a.get("quality_score") and v_b.get("quality_score") else None
    }


# ================== EXEMPLAR ENDPOINTS ==================

@page_ops_router.get("/exemplars")
async def get_all_exemplars(family: Optional[str] = None, user: dict = Depends(get_current_user)):
    query = {}
    if family:
        query["page_family"] = family
    
    exemplars = await db.exemplars.find(query, {"_id": 0}).sort("created_at", -1).to_list(100)
    
    by_family = {}
    for ex in exemplars:
        fam = ex.get("page_family", "Unknown")
        if fam not in by_family:
            by_family[fam] = {"count": 0, "primary": None, "exemplars": []}
        by_family[fam]["count"] += 1
        by_family[fam]["exemplars"].append(ex.get("id"))
        if ex.get("is_primary"):
            by_family[fam]["primary"] = ex.get("id")
    
    return {
        "exemplars": exemplars,
        "total": len(exemplars),
        "by_family": by_family,
        "reason_tags_available": EXEMPLAR_REASON_TAGS
    }

@page_ops_router.get("/exemplars/family/{family}")
async def get_exemplars_by_family(family: str, user: dict = Depends(get_current_user)):
    exemplars = await db.exemplars.find(
        {"page_family": family},
        {"_id": 0}
    ).sort("created_at", -1).to_list(50)
    
    primary = next((e for e in exemplars if e.get("is_primary")), None)
    
    return {
        "family": family,
        "exemplars": exemplars,
        "total": len(exemplars),
        "primary_exemplar": primary
    }

@page_ops_router.get("/exemplars/{exemplar_id}")
async def get_exemplar(exemplar_id: str, user: dict = Depends(get_current_user)):
    exemplar = await db.exemplars.find_one({"id": exemplar_id}, {"_id": 0})
    if not exemplar:
        raise HTTPException(status_code=404, detail="Exemplar not found")
    return exemplar

@page_ops_router.post("/exemplars", status_code=201)
async def create_exemplar(request: CreateExemplarRequest, user: dict = Depends(get_current_user)):
    version = await db.page_versions.find_one({"id": request.version_id}, {"_id": 0})
    if not version:
        raise HTTPException(status_code=404, detail="Version not found")
    
    page = await db.pages.find_one({"id": request.page_id}, {"_id": 0})
    if not page:
        raise HTTPException(status_code=404, detail="Page not found")
    
    existing = await db.exemplars.find_one({"version_id": request.version_id})
    if existing:
        raise HTTPException(status_code=409, detail="This version is already an Exemplar")
    
    if request.is_primary:
        await db.exemplars.update_many(
            {"page_family": page.get("page_family"), "is_primary": True},
            {"$set": {"is_primary": False, "updated_at": datetime.now(timezone.utc).isoformat()}}
        )
    
    exemplar = {
        "id": str(uuid.uuid4()),
        "page_id": request.page_id,
        "version_id": request.version_id,
        "page_name": page.get("page_name"),
        "page_family": page.get("page_family"),
        "page_type": page.get("page_type"),
        "version_number": version.get("version_number"),
        "generated_content": version.get("generated_content"),
        "quality_score": version.get("quality_score") or page.get("quality_score"),
        "reason_tags": request.reason_tags,
        "exemplar_notes": request.exemplar_notes,
        "is_primary": request.is_primary,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "updated_at": datetime.now(timezone.utc).isoformat()
    }
    
    await db.exemplars.insert_one(exemplar)
    exemplar.pop("_id", None)
    
    await db.page_versions.update_one({"id": request.version_id}, {"$set": {"is_exemplar": True}})
    
    await log_activity(
        "exemplar_created", request.page_id, page.get("page_name"),
        f"v{version.get('version_number')} promoted to Exemplar for {page.get('page_family')}"
    )
    
    return exemplar

@page_ops_router.put("/exemplars/{exemplar_id}")
async def update_exemplar(exemplar_id: str, request: UpdateExemplarRequest, user: dict = Depends(get_current_user)):
    exemplar = await db.exemplars.find_one({"id": exemplar_id}, {"_id": 0})
    if not exemplar:
        raise HTTPException(status_code=404, detail="Exemplar not found")
    
    update_data = {"updated_at": datetime.now(timezone.utc).isoformat()}
    
    if request.reason_tags is not None:
        update_data["reason_tags"] = request.reason_tags
    if request.exemplar_notes is not None:
        update_data["exemplar_notes"] = request.exemplar_notes
    if request.is_primary is not None:
        if request.is_primary:
            await db.exemplars.update_many(
                {"page_family": exemplar.get("page_family"), "is_primary": True},
                {"$set": {"is_primary": False, "updated_at": datetime.now(timezone.utc).isoformat()}}
            )
        update_data["is_primary"] = request.is_primary
    
    await db.exemplars.update_one({"id": exemplar_id}, {"$set": update_data})
    updated = await db.exemplars.find_one({"id": exemplar_id}, {"_id": 0})
    return updated

@page_ops_router.delete("/exemplars/{exemplar_id}")
async def delete_exemplar(exemplar_id: str, user: dict = Depends(get_current_user)):
    exemplar = await db.exemplars.find_one({"id": exemplar_id}, {"_id": 0})
    if not exemplar:
        raise HTTPException(status_code=404, detail="Exemplar not found")
    
    await db.page_versions.update_one(
        {"id": exemplar.get("version_id")},
        {"$set": {"is_exemplar": False}}
    )
    
    await db.exemplars.delete_one({"id": exemplar_id})
    
    await log_activity(
        "exemplar_removed", exemplar.get("page_id"), exemplar.get("page_name"),
        f"Exemplar removed for {exemplar.get('page_family')}"
    )
    return {"message": "Exemplar removed"}

@page_ops_router.post("/exemplars/{exemplar_id}/set-primary")
async def set_primary_exemplar(exemplar_id: str, user: dict = Depends(get_current_user)):
    exemplar = await db.exemplars.find_one({"id": exemplar_id}, {"_id": 0})
    if not exemplar:
        raise HTTPException(status_code=404, detail="Exemplar not found")
    
    await db.exemplars.update_many(
        {"page_family": exemplar.get("page_family"), "is_primary": True},
        {"$set": {"is_primary": False, "updated_at": datetime.now(timezone.utc).isoformat()}}
    )
    await db.exemplars.update_one(
        {"id": exemplar_id},
        {"$set": {"is_primary": True, "updated_at": datetime.now(timezone.utc).isoformat()}}
    )
    
    updated = await db.exemplars.find_one({"id": exemplar_id}, {"_id": 0})
    
    await log_activity(
        "exemplar_primary_set", exemplar.get("page_id"), exemplar.get("page_name"),
        f"Set as primary Exemplar for {exemplar.get('page_family')}"
    )
    return updated


# ================== HOUSE TEMPLATE ENDPOINTS ==================

@page_ops_router.get("/house-templates")
async def get_house_templates(family: Optional[str] = None, status: Optional[str] = None, user: dict = Depends(get_current_user)):
    query = {}
    if family:
        query["page_family"] = family
    if status:
        query["status"] = status
    
    templates = await db.house_templates.find(query, {"_id": 0}).sort("created_at", -1).to_list(100)
    
    by_family = {}
    for t in templates:
        fam = t.get("page_family", "Unknown")
        if fam not in by_family:
            by_family[fam] = {"count": 0, "primary": None, "templates": []}
        by_family[fam]["count"] += 1
        by_family[fam]["templates"].append(t)
        if t.get("is_primary"):
            by_family[fam]["primary"] = t.get("id")
    
    return {"templates": templates, "total": len(templates), "by_family": by_family}

@page_ops_router.get("/house-templates/family/{family}")
async def get_templates_by_family(family: str, user: dict = Depends(get_current_user)):
    templates = await db.house_templates.find(
        {"page_family": family, "status": "active"}, {"_id": 0}
    ).sort("created_at", -1).to_list(50)
    primary = next((t for t in templates if t.get("is_primary")), None)
    return {"family": family, "templates": templates, "total": len(templates), "primary_template": primary}

@page_ops_router.get("/house-templates/{template_id}")
async def get_house_template(template_id: str, user: dict = Depends(get_current_user)):
    template = await db.house_templates.find_one({"id": template_id}, {"_id": 0})
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")
    return template

@page_ops_router.post("/house-templates", status_code=201)
async def create_house_template(request: CreateHouseTemplateRequest, user: dict = Depends(get_current_user)):
    version = await db.page_versions.find_one({"id": request.source_version_id}, {"_id": 0})
    if not version:
        raise HTTPException(status_code=404, detail="Source version not found")
    page = await db.pages.find_one({"id": request.source_page_id}, {"_id": 0})
    if not page:
        raise HTTPException(status_code=404, detail="Source page not found")
    
    if request.is_primary:
        await db.house_templates.update_many(
            {"page_family": request.page_family, "is_primary": True},
            {"$set": {"is_primary": False, "updated_at": datetime.now(timezone.utc).isoformat()}}
        )
    
    template = {
        "id": str(uuid.uuid4()),
        "template_name": request.template_name,
        "purpose": request.purpose,
        "page_family": request.page_family,
        "page_type": request.page_type,
        "source_page_id": request.source_page_id,
        "source_version_id": request.source_version_id,
        "source_page_name": page.get("page_name"),
        "source_version_number": version.get("version_number"),
        "source_quality_score": version.get("quality_score"),
        "structural_pattern": request.structural_pattern,
        "tone_guidance": request.tone_guidance,
        "status": "active",
        "is_primary": request.is_primary,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "updated_at": datetime.now(timezone.utc).isoformat()
    }
    
    await db.house_templates.insert_one(template)
    template.pop("_id", None)
    
    await log_activity(
        "template_created", request.source_page_id, page.get("page_name"),
        f"House template '{request.template_name}' created for {request.page_family}"
    )
    return template

@page_ops_router.put("/house-templates/{template_id}")
async def update_house_template(template_id: str, request: UpdateHouseTemplateRequest, user: dict = Depends(get_current_user)):
    template = await db.house_templates.find_one({"id": template_id}, {"_id": 0})
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")
    
    update_data = {"updated_at": datetime.now(timezone.utc).isoformat()}
    
    if request.template_name is not None:
        update_data["template_name"] = request.template_name
    if request.purpose is not None:
        update_data["purpose"] = request.purpose
    if request.page_type is not None:
        update_data["page_type"] = request.page_type
    if request.structural_pattern is not None:
        update_data["structural_pattern"] = request.structural_pattern
    if request.tone_guidance is not None:
        update_data["tone_guidance"] = request.tone_guidance
    if request.status is not None:
        if request.status not in ["active", "inactive"]:
            raise HTTPException(status_code=400, detail="Status must be 'active' or 'inactive'")
        update_data["status"] = request.status
    if request.is_primary is not None:
        if request.is_primary:
            await db.house_templates.update_many(
                {"page_family": template.get("page_family"), "is_primary": True},
                {"$set": {"is_primary": False, "updated_at": datetime.now(timezone.utc).isoformat()}}
            )
        update_data["is_primary"] = request.is_primary
    
    await db.house_templates.update_one({"id": template_id}, {"$set": update_data})
    updated = await db.house_templates.find_one({"id": template_id}, {"_id": 0})
    
    await log_activity(
        "template_updated", template.get("source_page_id"), template.get("source_page_name"),
        f"Template '{template.get('template_name')}' updated"
    )
    return updated

@page_ops_router.delete("/house-templates/{template_id}")
async def delete_house_template(template_id: str, user: dict = Depends(get_current_user)):
    template = await db.house_templates.find_one({"id": template_id}, {"_id": 0})
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")
    await db.house_templates.delete_one({"id": template_id})
    await log_activity("template_deleted", template.get("source_page_id"), template.get("source_page_name"),
                      f"Template '{template.get('template_name')}' deleted")
    return {"message": "Template deleted"}

@page_ops_router.post("/house-templates/{template_id}/set-primary")
async def set_primary_template(template_id: str, user: dict = Depends(get_current_user)):
    template = await db.house_templates.find_one({"id": template_id}, {"_id": 0})
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")
    
    await db.house_templates.update_many(
        {"page_family": template.get("page_family"), "is_primary": True},
        {"$set": {"is_primary": False, "updated_at": datetime.now(timezone.utc).isoformat()}}
    )
    await db.house_templates.update_one(
        {"id": template_id},
        {"$set": {"is_primary": True, "updated_at": datetime.now(timezone.utc).isoformat()}}
    )
    updated = await db.house_templates.find_one({"id": template_id}, {"_id": 0})
    await log_activity("template_primary_set", template.get("source_page_id"), template.get("source_page_name"),
                      f"Set as primary template for {template.get('page_family')}")
    return updated

@page_ops_router.post("/house-templates/{template_id}/toggle-status")
async def toggle_template_status(template_id: str, user: dict = Depends(get_current_user)):
    template = await db.house_templates.find_one({"id": template_id}, {"_id": 0})
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")
    new_status = "inactive" if template.get("status") == "active" else "active"
    await db.house_templates.update_one(
        {"id": template_id},
        {"$set": {"status": new_status, "updated_at": datetime.now(timezone.utc).isoformat()}}
    )
    updated = await db.house_templates.find_one({"id": template_id}, {"_id": 0})
    await log_activity("template_status_changed", template.get("source_page_id"), template.get("source_page_name"),
                      f"Template '{template.get('template_name')}' set to {new_status}")
    return updated

@page_ops_router.post("/house-templates/extract-structure")
async def extract_structure_from_version(page_id: str, version_id: str, user: dict = Depends(get_current_user)):
    version = await db.page_versions.find_one({"id": version_id}, {"_id": 0})
    if not version or version.get("page_id") != page_id:
        raise HTTPException(status_code=404, detail="Version not found")
    
    content = version.get("generated_content", "")
    if not content:
        raise HTTPException(status_code=400, detail="Version has no content")
    
    lines = content.split('\n')
    structure_lines = []
    for line in lines:
        stripped = line.strip()
        if stripped.startswith('#'):
            structure_lines.append(stripped)
        elif stripped.startswith('-') or stripped.startswith('*'):
            structure_lines.append("- [list item / bullet point]")
        elif stripped == '':
            if structure_lines and structure_lines[-1] != '':
                structure_lines.append('')
        else:
            if not structure_lines or not structure_lines[-1].startswith('['):
                structure_lines.append("[paragraph: narrative/descriptive content]")
    
    deduped = []
    for line in structure_lines:
        if not deduped or deduped[-1] != line:
            deduped.append(line)
    
    structural_pattern = '\n'.join(deduped)
    
    return {
        "page_id": page_id,
        "version_id": version_id,
        "version_number": version.get("version_number"),
        "structural_pattern": structural_pattern,
        "content_length": len(content),
        "sections_found": len([s for s in deduped if s.startswith('#')])
    }


# ================== STYLE PROFILE ENDPOINTS ==================

@page_ops_router.get("/style-profiles")
async def get_style_profiles(family: Optional[str] = None, status: Optional[str] = None, user: dict = Depends(get_current_user)):
    query = {}
    if family:
        query["page_families"] = family
    if status:
        query["status"] = status
    
    profiles = await db.style_profiles.find(query, {"_id": 0}).sort("created_at", -1).to_list(100)
    
    defaults_by_family = {}
    for p in profiles:
        if p.get("is_default") and p.get("status") == "active":
            for fam in p.get("page_families", []):
                if fam not in defaults_by_family:
                    defaults_by_family[fam] = p.get("id")
    
    return {"profiles": profiles, "total": len(profiles), "defaults_by_family": defaults_by_family}

@page_ops_router.get("/style-profiles/family/{family}")
async def get_profiles_by_family(family: str, user: dict = Depends(get_current_user)):
    profiles = await db.style_profiles.find(
        {"page_families": family, "status": "active"}, {"_id": 0}
    ).sort("created_at", -1).to_list(50)
    default_profile = next((p for p in profiles if p.get("is_default")), None)
    return {"family": family, "profiles": profiles, "total": len(profiles), "default_profile": default_profile}

@page_ops_router.get("/style-profiles/{profile_id}")
async def get_style_profile(profile_id: str, user: dict = Depends(get_current_user)):
    profile = await db.style_profiles.find_one({"id": profile_id}, {"_id": 0})
    if not profile:
        raise HTTPException(status_code=404, detail="Style profile not found")
    return profile

@page_ops_router.post("/style-profiles", status_code=201)
async def create_style_profile(request: CreateStyleProfileRequest, user: dict = Depends(get_current_user)):
    if request.is_default:
        for fam in request.page_families:
            await db.style_profiles.update_many(
                {"page_families": fam, "is_default": True},
                {"$set": {"is_default": False, "updated_at": datetime.now(timezone.utc).isoformat()}}
            )
    
    profile = {
        "id": str(uuid.uuid4()),
        "profile_name": request.profile_name,
        "description": request.description,
        "tonal_controls": request.tonal_controls.model_dump(),
        "include_language": request.include_language,
        "avoid_language": request.avoid_language,
        "page_families": request.page_families,
        "page_types": request.page_types,
        "is_default": request.is_default,
        "status": "active",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "updated_at": datetime.now(timezone.utc).isoformat()
    }
    
    await db.style_profiles.insert_one(profile)
    profile.pop("_id", None)
    await log_activity("style_profile_created", None, None,
                      f"Style profile '{request.profile_name}' created for {', '.join(request.page_families)}")
    return profile

@page_ops_router.put("/style-profiles/{profile_id}")
async def update_style_profile(profile_id: str, request: UpdateStyleProfileRequest, user: dict = Depends(get_current_user)):
    profile = await db.style_profiles.find_one({"id": profile_id}, {"_id": 0})
    if not profile:
        raise HTTPException(status_code=404, detail="Style profile not found")
    
    update_data = {"updated_at": datetime.now(timezone.utc).isoformat()}
    if request.profile_name is not None:
        update_data["profile_name"] = request.profile_name
    if request.description is not None:
        update_data["description"] = request.description
    if request.tonal_controls is not None:
        update_data["tonal_controls"] = request.tonal_controls.model_dump()
    if request.include_language is not None:
        update_data["include_language"] = request.include_language
    if request.avoid_language is not None:
        update_data["avoid_language"] = request.avoid_language
    if request.page_families is not None:
        update_data["page_families"] = request.page_families
    if request.page_types is not None:
        update_data["page_types"] = request.page_types
    if request.status is not None:
        if request.status not in ["active", "inactive"]:
            raise HTTPException(status_code=400, detail="Status must be 'active' or 'inactive'")
        update_data["status"] = request.status
    if request.is_default is not None:
        if request.is_default:
            families = request.page_families if request.page_families is not None else profile.get("page_families", [])
            for fam in families:
                await db.style_profiles.update_many(
                    {"page_families": fam, "is_default": True, "id": {"$ne": profile_id}},
                    {"$set": {"is_default": False, "updated_at": datetime.now(timezone.utc).isoformat()}}
                )
        update_data["is_default"] = request.is_default
    
    await db.style_profiles.update_one({"id": profile_id}, {"$set": update_data})
    updated = await db.style_profiles.find_one({"id": profile_id}, {"_id": 0})
    await log_activity("style_profile_updated", None, None, f"Style profile '{profile.get('profile_name')}' updated")
    return updated

@page_ops_router.delete("/style-profiles/{profile_id}")
async def delete_style_profile(profile_id: str, user: dict = Depends(get_current_user)):
    profile = await db.style_profiles.find_one({"id": profile_id}, {"_id": 0})
    if not profile:
        raise HTTPException(status_code=404, detail="Style profile not found")
    await db.style_profiles.delete_one({"id": profile_id})
    await log_activity("style_profile_deleted", None, None, f"Style profile '{profile.get('profile_name')}' deleted")
    return {"message": "Style profile deleted"}

@page_ops_router.post("/style-profiles/{profile_id}/set-default")
async def set_default_style_profile(profile_id: str, user: dict = Depends(get_current_user)):
    profile = await db.style_profiles.find_one({"id": profile_id}, {"_id": 0})
    if not profile:
        raise HTTPException(status_code=404, detail="Style profile not found")
    for fam in profile.get("page_families", []):
        await db.style_profiles.update_many(
            {"page_families": fam, "is_default": True},
            {"$set": {"is_default": False, "updated_at": datetime.now(timezone.utc).isoformat()}}
        )
    await db.style_profiles.update_one(
        {"id": profile_id},
        {"$set": {"is_default": True, "updated_at": datetime.now(timezone.utc).isoformat()}}
    )
    updated = await db.style_profiles.find_one({"id": profile_id}, {"_id": 0})
    await log_activity("style_profile_default_set", None, None,
                      f"'{profile.get('profile_name')}' set as default for {', '.join(profile.get('page_families', []))}")
    return updated

@page_ops_router.post("/style-profiles/{profile_id}/toggle-status")
async def toggle_style_profile_status(profile_id: str, user: dict = Depends(get_current_user)):
    profile = await db.style_profiles.find_one({"id": profile_id}, {"_id": 0})
    if not profile:
        raise HTTPException(status_code=404, detail="Style profile not found")
    new_status = "inactive" if profile.get("status") == "active" else "active"
    await db.style_profiles.update_one(
        {"id": profile_id},
        {"$set": {"status": new_status, "updated_at": datetime.now(timezone.utc).isoformat()}}
    )
    updated = await db.style_profiles.find_one({"id": profile_id}, {"_id": 0})
    await log_activity("style_profile_status_changed", None, None,
                      f"'{profile.get('profile_name')}' set to {new_status}")
    return updated

@page_ops_router.post("/style-profiles/seed")
async def seed_style_profiles(user: dict = Depends(get_current_user)):
    existing = await db.style_profiles.count_documents({})
    if existing > 0:
        return {"message": f"Already {existing} profiles exist. Skipping seed.", "seeded": 0}
    
    seeded = 0
    for seed in SEED_STYLE_PROFILES:
        profile = {
            "id": str(uuid.uuid4()),
            "profile_name": seed["profile_name"],
            "description": seed["description"],
            "tonal_controls": seed["tonal_controls"],
            "include_language": seed["include_language"],
            "avoid_language": seed["avoid_language"],
            "page_families": seed["page_families"],
            "page_types": [],
            "is_default": True,
            "status": "active",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "updated_at": datetime.now(timezone.utc).isoformat()
        }
        await db.style_profiles.insert_one(profile)
        seeded += 1
    
    await log_activity("style_profiles_seeded", None, None, f"Seeded {seeded} initial style profiles")
    return {"message": f"Seeded {seeded} style profiles", "seeded": seeded}


# ================== PROMOTION LOGIC ENDPOINTS ==================

@page_ops_router.post("/promotions/evaluate/{page_id}/{version_id}")
async def evaluate_promotion(page_id: str, version_id: str, user: dict = Depends(get_current_user)):
    version = await db.page_versions.find_one({"id": version_id}, {"_id": 0})
    if not version or version.get("page_id") != page_id:
        raise HTTPException(status_code=404, detail="Version not found")

    page = await db.pages.find_one({"id": page_id}, {"_id": 0})
    if not page:
        raise HTTPException(status_code=404, detail="Page not found")

    score_notes = page.get("score_notes") or version.get("score_notes") or {}

    existing = await db.promotion_candidates.find_one(
        {"version_id": version_id, "status": {"$in": ["pending", "deferred"]}},
        {"_id": 0}
    )

    result = evaluate_promotion_signals(version, page, score_notes)

    if not result["is_promotable"]:
        return {
            "promotable": False,
            "signals": result["signals"],
            "message": "This version doesn't currently meet promotion thresholds.",
            "candidate": existing
        }

    if existing:
        await db.promotion_candidates.update_one(
            {"id": existing["id"]},
            {"$set": {
                "signals": result["signals"],
                "promotion_types": result["promotion_types"],
                "recommendation_reason": result["recommendation_reason"],
                "quality_score": version.get("quality_score") or page.get("quality_score"),
                "updated_at": datetime.now(timezone.utc).isoformat()
            }}
        )
        updated = await db.promotion_candidates.find_one({"id": existing["id"]}, {"_id": 0})
        return {
            "promotable": True, "signals": result["signals"],
            "promotion_types": result["promotion_types"],
            "recommendation_reason": result["recommendation_reason"],
            "candidate": updated, "is_existing": True
        }

    candidate = {
        "id": str(uuid.uuid4()),
        "page_id": page_id,
        "version_id": version_id,
        "page_name": page.get("page_name"),
        "page_family": page.get("page_family"),
        "page_type": page.get("page_type"),
        "version_number": version.get("version_number"),
        "quality_score": version.get("quality_score") or page.get("quality_score"),
        "signals": result["signals"],
        "promotion_types": result["promotion_types"],
        "recommendation_reason": result["recommendation_reason"],
        "status": "pending",
        "action_taken": None,
        "action_details": None,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "resolved_at": None
    }

    await db.promotion_candidates.insert_one(candidate)
    candidate.pop("_id", None)

    await log_activity(
        "promotion_candidate", page_id, page.get("page_name"),
        f"v{version.get('version_number')} flagged for promotion: {', '.join(result['promotion_types'])}"
    )

    return {
        "promotable": True, "signals": result["signals"],
        "promotion_types": result["promotion_types"],
        "recommendation_reason": result["recommendation_reason"],
        "candidate": candidate, "is_existing": False
    }


@page_ops_router.get("/promotions/candidates")
async def get_promotion_candidates(status: Optional[str] = None, user: dict = Depends(get_current_user)):
    query = {}
    if status:
        query["status"] = status
    candidates = await db.promotion_candidates.find(query, {"_id": 0}).sort("created_at", -1).to_list(100)
    status_counts = {"pending": 0, "promoted": 0, "dismissed": 0, "deferred": 0}
    for c in candidates:
        s = c.get("status", "pending")
        if s in status_counts:
            status_counts[s] += 1
    return {"candidates": candidates, "total": len(candidates), "status_counts": status_counts}


@page_ops_router.get("/promotions/candidates/{candidate_id}")
async def get_promotion_candidate(candidate_id: str, user: dict = Depends(get_current_user)):
    candidate = await db.promotion_candidates.find_one({"id": candidate_id}, {"_id": 0})
    if not candidate:
        raise HTTPException(status_code=404, detail="Candidate not found")
    return candidate


@page_ops_router.get("/promotions/page/{page_id}")
async def get_page_promotions(page_id: str, user: dict = Depends(get_current_user)):
    candidates = await db.promotion_candidates.find(
        {"page_id": page_id}, {"_id": 0}
    ).sort("created_at", -1).to_list(50)
    return {"candidates": candidates, "total": len(candidates)}


@page_ops_router.post("/promotions/candidates/{candidate_id}/action")
async def execute_promotion_action(candidate_id: str, request: PromotionActionRequest, user: dict = Depends(get_current_user)):
    candidate = await db.promotion_candidates.find_one({"id": candidate_id}, {"_id": 0})
    if not candidate:
        raise HTTPException(status_code=404, detail="Candidate not found")
    
    if candidate.get("status") not in ["pending", "deferred"]:
        raise HTTPException(status_code=400, detail=f"Candidate already resolved (status: {candidate.get('status')})")
    
    valid_actions = ["promote-exemplar", "create-template", "save-style-candidate", "dismiss", "decide-later"]
    if request.action not in valid_actions:
        raise HTTPException(status_code=400, detail=f"Invalid action. Valid: {valid_actions}")
    
    action_details = {}
    new_status = "promoted"
    
    if request.action == "dismiss":
        new_status = "dismissed"
        action_details = {"reason": request.notes or "Dismissed by founder"}
        await log_activity("promotion_dismissed", candidate["page_id"], candidate["page_name"],
            f"v{candidate['version_number']} promotion dismissed")
    
    elif request.action == "decide-later":
        new_status = "deferred"
        action_details = {"reason": request.notes or "Deferred for later review"}
        await log_activity("promotion_deferred", candidate["page_id"], candidate["page_name"],
            f"v{candidate['version_number']} promotion deferred")
    
    elif request.action == "promote-exemplar":
        version = await db.page_versions.find_one({"id": candidate["version_id"]}, {"_id": 0})
        if not version:
            raise HTTPException(status_code=404, detail="Source version not found")
        
        page = await db.pages.find_one({"id": candidate["page_id"]}, {"_id": 0})
        
        existing_ex = await db.exemplars.find_one({"version_id": candidate["version_id"]})
        if existing_ex:
            raise HTTPException(status_code=409, detail="This version is already an Exemplar")
        
        if request.is_primary:
            await db.exemplars.update_many(
                {"page_family": candidate.get("page_family"), "is_primary": True},
                {"$set": {"is_primary": False, "updated_at": datetime.now(timezone.utc).isoformat()}}
            )
        
        exemplar = {
            "id": str(uuid.uuid4()),
            "page_id": candidate["page_id"],
            "version_id": candidate["version_id"],
            "page_name": candidate.get("page_name"),
            "page_family": candidate.get("page_family"),
            "page_type": candidate.get("page_type"),
            "version_number": candidate.get("version_number"),
            "generated_content": version.get("generated_content"),
            "quality_score": candidate.get("quality_score"),
            "reason_tags": request.reason_tags or [],
            "exemplar_notes": request.notes,
            "is_primary": request.is_primary or False,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "updated_at": datetime.now(timezone.utc).isoformat()
        }
        await db.exemplars.insert_one(exemplar)
        exemplar.pop("_id", None)
        
        await db.page_versions.update_one({"id": candidate["version_id"]}, {"$set": {"is_exemplar": True}})
        
        action_details = {"exemplar_id": exemplar["id"], "is_primary": exemplar["is_primary"]}
        await log_activity("promotion_to_exemplar", candidate["page_id"], candidate["page_name"],
            f"v{candidate['version_number']} promoted to Exemplar via promotion logic")
    
    elif request.action == "create-template":
        version = await db.page_versions.find_one({"id": candidate["version_id"]}, {"_id": 0})
        if not version:
            raise HTTPException(status_code=404, detail="Source version not found")
        
        content = version.get("generated_content", "")
        lines = content.split('\n')
        structure_lines = []
        for line in lines:
            stripped = line.strip()
            if stripped.startswith('#'):
                structure_lines.append(stripped)
            elif stripped.startswith('-') or stripped.startswith('*'):
                structure_lines.append("- [list item]")
            elif stripped == '':
                if structure_lines and structure_lines[-1] != '':
                    structure_lines.append('')
            else:
                if not structure_lines or not structure_lines[-1].startswith('['):
                    structure_lines.append("[paragraph: narrative content]")
        
        deduped = []
        for line in structure_lines:
            if not deduped or deduped[-1] != line:
                deduped.append(line)
        
        template = {
            "id": str(uuid.uuid4()),
            "template_name": request.notes or f"{candidate.get('page_name')} Pattern",
            "purpose": f"Structural pattern extracted from {candidate.get('page_name')} v{candidate.get('version_number')} (score: {candidate.get('quality_score')})",
            "page_family": candidate.get("page_family"),
            "page_type": candidate.get("page_type"),
            "source_page_id": candidate.get("page_id"),
            "source_version_id": candidate.get("version_id"),
            "source_page_name": candidate.get("page_name"),
            "source_version_number": candidate.get("version_number"),
            "source_quality_score": candidate.get("quality_score"),
            "structural_pattern": '\n'.join(structure_lines),
            "tone_guidance": None,
            "status": "active",
            "is_primary": request.is_primary or False,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "updated_at": datetime.now(timezone.utc).isoformat()
        }
        await db.house_templates.insert_one(template)
        template.pop("_id", None)
        
        action_details = {"template_id": template["id"], "template_name": template["template_name"]}
        await log_activity("promotion_to_template", candidate["page_id"], candidate["page_name"],
            f"v{candidate['version_number']} promoted to House Template via promotion logic")
    
    elif request.action == "save-style-candidate":
        action_details = {
            "candidate_type": "style-profile",
            "notes": request.notes or "Saved as style profile candidate for later review",
            "page_family": candidate.get("page_family"),
            "tonal_signals": [s for s in candidate.get("signals", [])
                            if s["signal"] in ("high_emotional_presence", "warm_without_fluff", "high_brand_fit", "high_uniqueness")]
        }
        new_status = "promoted"
        await log_activity("promotion_style_candidate", candidate["page_id"], candidate["page_name"],
            f"v{candidate['version_number']} saved as Style Profile candidate")
    
    await db.promotion_candidates.update_one(
        {"id": candidate_id},
        {"$set": {
            "status": new_status,
            "action_taken": request.action,
            "action_details": action_details,
            "resolved_at": datetime.now(timezone.utc).isoformat(),
            "updated_at": datetime.now(timezone.utc).isoformat()
        }}
    )
    
    updated = await db.promotion_candidates.find_one({"id": candidate_id}, {"_id": 0})
    return updated


# ================== EXPORT ==================

@page_ops_router.get("/pages/{page_id}/export")
async def export_single_page(page_id: str, format: str = "markdown", user: dict = Depends(get_current_user)):
    page = await db.pages.find_one({"id": page_id}, {"_id": 0})
    if not page:
        raise HTTPException(status_code=404, detail="Page not found")
    
    content = page.get("generated_content", "")
    
    if format == "text":
        text_content = re.sub(r'#{1,6}\s*', '', content)
        text_content = re.sub(r'\*\*([^*]+)\*\*', r'\1', text_content)
        text_content = re.sub(r'\*([^*]+)\*', r'\1', text_content)
        export_content = f"""PAGE: {page.get('page_name')}
SLUG: {page.get('slug')}
TYPE: {page.get('page_type')} | FAMILY: {page.get('page_family')}
STATUS: {page.get('status')} | SCORE: {page.get('quality_score', 'N/A')}/100

---

{text_content}

---
Exported: {datetime.now(timezone.utc).isoformat()}
"""
    elif format == "json":
        return {
            "page_name": page.get("page_name"), "slug": page.get("slug"),
            "page_family": page.get("page_family"), "page_type": page.get("page_type"),
            "district_or_pillar": page.get("district_or_pillar"),
            "audience": page.get("audience"), "purpose": page.get("purpose"),
            "CTA_type": page.get("CTA_type"), "status": page.get("status"),
            "quality_score": page.get("quality_score"), "content": content,
            "export_date": datetime.now(timezone.utc).isoformat()
        }
    else:
        export_content = f"""---
page_name: {page.get('page_name')}
slug: {page.get('slug')}
family: {page.get('page_family')}
type: {page.get('page_type')}
district: {page.get('district_or_pillar', 'N/A')}
status: {page.get('status')}
score: {page.get('quality_score', 'N/A')}/100
exported: {datetime.now(timezone.utc).isoformat()}
---

{content}
"""
    
    await log_activity("page_exported", page_id, page.get("page_name"), f"Exported as {format}")
    return {"content": export_content, "format": format, "page_name": page.get("page_name")}

@page_ops_router.post("/pages/export-batch", response_model=ExportResponse)
async def export_batch_pages(request: ExportRequest, user: dict = Depends(get_current_user)):
    pages = await db.pages.find({"id": {"$in": request.page_ids}}, {"_id": 0}).to_list(100)
    if not pages:
        raise HTTPException(status_code=404, detail="No pages found")
    
    exported = []
    for page in pages:
        exported.append(ExportedPage(
            page_name=page.get("page_name"), slug=page.get("slug", ""),
            page_family=page.get("page_family"), page_type=page.get("page_type"),
            status=page.get("status"), quality_score=page.get("quality_score"),
            content=page.get("generated_content"),
            metadata={
                "district": page.get("district_or_pillar"), "audience": page.get("audience"),
                "purpose": page.get("purpose"), "CTA_type": page.get("CTA_type"),
                "priority_score": page.get("priority_score")
            }
        ))
    
    await log_activity("batch_export", details=f"Exported {len(exported)} pages")
    return ExportResponse(exported_count=len(exported), pages=exported, export_date=datetime.now(timezone.utc).isoformat())


# ================== BATCH GENERATION ==================

@page_ops_router.post("/pages/batch-generate", response_model=BatchGenerateResponse)
async def batch_generate_next(request: BatchGenerateRequest, user: dict = Depends(get_current_user)):
    all_pages = await db.pages.find({}, {"_id": 0}).to_list(1000)
    recommended = get_recommended_next_pages(all_pages, request.count)
    
    if not recommended:
        raise HTTPException(status_code=400, detail="No pages available for generation")
    
    results = []
    successful = 0
    needs_rewrite = 0
    ready_for_review = 0
    
    for page in recommended:
        page_id = page["id"]
        page_name = page["page_name"]
        
        try:
            await db.pages.update_one({"id": page_id}, {"$set": {"status": "Generating"}})
            content = await generate_page_content(page, request.tone)
            
            history_entry = {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "tone": request.tone, "model": PAGE_GENERATION_MODEL,
                "content_preview": content[:200] if content else "",
                "batch_generated": True
            }
            
            await db.pages.update_one(
                {"id": page_id},
                {"$set": {"generated_content": content, "updated_at": datetime.now(timezone.utc).isoformat()},
                 "$push": {"generation_history": history_entry}}
            )
            
            quality_score = None
            classification = None
            final_status = "Draft Ready"
            
            if request.auto_score:
                try:
                    score_result = await score_page_quality(page, content)
                    quality_score = score_result.get("overall_score", 75)
                    classification = score_result.get("classification", "usable")
                    
                    if quality_score < request.score_threshold:
                        final_status = "Needs Rewrite"
                        needs_rewrite += 1
                    else:
                        final_status = "Needs Review"
                        ready_for_review += 1
                    
                    await db.pages.update_one(
                        {"id": page_id},
                        {"$set": {"quality_score": quality_score, "score_notes": score_result,
                                  "edit_recommendations": score_result.get("edit_recommendations", []),
                                  "status": final_status}}
                    )
                except Exception as score_error:
                    logger.error(f"Scoring failed for {page_name}: {score_error}")
                    final_status = "Draft Ready"
                    await db.pages.update_one({"id": page_id}, {"$set": {"status": final_status}})
            else:
                await db.pages.update_one({"id": page_id}, {"$set": {"status": final_status}})
            
            successful += 1
            results.append(BatchGenerateResult(
                page_id=page_id, page_name=page_name, status=final_status,
                quality_score=quality_score, classification=classification, success=True
            ))
            await log_activity("batch_generated", page_id, page_name, f"Score: {quality_score}/100 -> {final_status}")
            
        except Exception as e:
            logger.error(f"Batch generation failed for {page_name}: {e}")
            await db.pages.update_one({"id": page_id}, {"$set": {"status": "Planned"}})
            results.append(BatchGenerateResult(
                page_id=page_id, page_name=page_name, status="Planned",
                quality_score=None, classification=None, success=False, error=str(e)
            ))
    
    await log_activity("batch_generate_complete",
                      details=f"Processed {len(results)}: {successful} success, {needs_rewrite} rewrite, {ready_for_review} review")
    
    return BatchGenerateResponse(
        total_processed=len(results), successful=successful,
        needs_rewrite=needs_rewrite, ready_for_review=ready_for_review, results=results
    )


# ================== DEPENDENCY LOGIC ==================

@page_ops_router.get("/pages/{page_id}/dependency")
async def get_page_dependency(page_id: str, user: dict = Depends(get_current_user)):
    page = await db.pages.find_one({"id": page_id}, {"_id": 0})
    if not page:
        raise HTTPException(status_code=404, detail="Page not found")
    
    parent_page = page.get("parent_page")
    parent_status = None
    dependency_status = "ready_now"
    recommendation = "Ready to generate"
    
    if parent_page:
        parent = await db.pages.find_one({"page_name": parent_page}, {"_id": 0})
        if parent:
            parent_status = parent.get("status")
            if parent_status not in ["Approved", "Needs Review"]:
                dependency_status = "needs_parent"
                recommendation = f"Parent page '{parent_page}' should be completed first (currently: {parent_status})"
            elif parent_status == "Needs Rewrite":
                dependency_status = "blocked"
                recommendation = f"Blocked: Parent page '{parent_page}' needs rewrite"
    else:
        if page.get("page_family") in ["Core Hub", "District"]:
            dependency_status = "foundational"
            recommendation = "Foundational page - prioritize first"
    
    children = await db.pages.count_documents({"parent_page": page.get("page_name")})
    
    return PageDependencyInfo(
        page_id=page_id, page_name=page.get("page_name"),
        dependency_status=dependency_status, parent_page=parent_page,
        parent_status=parent_status, children_count=children,
        recommendation=recommendation
    )
