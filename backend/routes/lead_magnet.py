from fastapi import APIRouter, HTTPException, Depends, Response
from fastapi.responses import StreamingResponse
from typing import Optional
from datetime import datetime, timezone
import uuid
import io
import os

from database import db, logger
from models import (
    CreateLeadMagnetRequest, UpdateLeadMagnetRequest,
    LEAD_MAGNET_FORMATS, LEAD_MAGNET_STATUSES, LEAD_MAGNET_LENGTHS,
)
from auth import get_current_user
from services.helpers import log_activity
from services.lead_magnet_generation import (
    generate_lead_magnet_content,
    generate_pdf_bytes,
    generate_embed_code,
)

lead_magnet_router = APIRouter(prefix="/api")


# ================== STATS ==================

@lead_magnet_router.get("/lead-magnets/stats")
async def lead_magnet_stats(user: dict = Depends(get_current_user)):
    pipeline = [
        {"$group": {"_id": "$status", "count": {"$sum": 1}}},
    ]
    status_counts = {}
    async for doc in db.lead_magnets.aggregate(pipeline):
        status_counts[doc["_id"]] = doc["count"]

    total = sum(status_counts.values())
    total_downloads = 0
    async for doc in db.lead_magnets.aggregate([
        {"$group": {"_id": None, "total": {"$sum": "$download_count"}}}
    ]):
        total_downloads = doc["total"]

    format_pipeline = [{"$group": {"_id": "$format_type", "count": {"$sum": 1}}}]
    format_counts = {}
    async for doc in db.lead_magnets.aggregate(format_pipeline):
        format_counts[doc["_id"]] = doc["count"]

    return {
        "total": total,
        "by_status": status_counts,
        "by_format": format_counts,
        "published_count": status_counts.get("Published", 0),
        "draft_count": status_counts.get("Draft", 0),
        "total_downloads": total_downloads,
    }


# ================== CRUD ==================

@lead_magnet_router.get("/lead-magnets")
async def list_lead_magnets(
    status: Optional[str] = None,
    format_type: Optional[str] = None,
    district_tag: Optional[str] = None,
    user: dict = Depends(get_current_user),
):
    query = {}
    if status:
        query["status"] = status
    if format_type:
        query["format_type"] = format_type
    if district_tag:
        query["district_tag"] = district_tag

    magnets = []
    async for doc in db.lead_magnets.find(query, {"_id": 0}).sort("created_at", -1):
        magnets.append(doc)
    return {"lead_magnets": magnets}


@lead_magnet_router.post("/lead-magnets")
async def create_lead_magnet(
    request: CreateLeadMagnetRequest,
    user: dict = Depends(get_current_user),
):
    if request.format_type not in LEAD_MAGNET_FORMATS:
        raise HTTPException(status_code=400, detail=f"Invalid format. Must be one of: {LEAD_MAGNET_FORMATS}")
    if request.length not in LEAD_MAGNET_LENGTHS:
        raise HTTPException(status_code=400, detail=f"Invalid length. Must be one of: {LEAD_MAGNET_LENGTHS}")
    if len(request.topic) < 3 or len(request.topic) > 120:
        raise HTTPException(status_code=400, detail="Topic must be 3-120 characters")
    if len(request.target_audience) < 3 or len(request.target_audience) > 240:
        raise HTTPException(status_code=400, detail="Target audience must be 3-240 characters")

    now = datetime.now(timezone.utc).isoformat()
    magnet = {
        "id": str(uuid.uuid4()),
        "public_id": str(uuid.uuid4()),
        "title": "",
        "subtitle": "",
        "description": "",
        "topic": request.topic,
        "target_audience": request.target_audience,
        "format_type": request.format_type,
        "district_tag": request.district_tag or "",
        "content_direction": request.content_direction or "",
        "length": request.length,
        "include_disclaimer": request.include_disclaimer,
        "status": "Draft",
        "markdown_content": "",
        "landing_headline": "",
        "landing_body": "",
        "landing_cta": "",
        "suggested_filename": "",
        "has_pdf": False,
        "download_count": 0,
        "current_version": 0,
        "created_at": now,
        "updated_at": now,
    }
    await db.lead_magnets.insert_one(magnet)
    await log_activity("lead_magnet_created", details=f"Created lead magnet: {request.topic}")

    result = {k: v for k, v in magnet.items() if k != "_id"}
    return result


@lead_magnet_router.get("/lead-magnets/{magnet_id}")
async def get_lead_magnet(magnet_id: str, user: dict = Depends(get_current_user)):
    magnet = await db.lead_magnets.find_one({"id": magnet_id}, {"_id": 0})
    if not magnet:
        raise HTTPException(status_code=404, detail="Lead magnet not found")
    return magnet


@lead_magnet_router.put("/lead-magnets/{magnet_id}")
async def update_lead_magnet(
    magnet_id: str,
    request: UpdateLeadMagnetRequest,
    user: dict = Depends(get_current_user),
):
    magnet = await db.lead_magnets.find_one({"id": magnet_id}, {"_id": 0})
    if not magnet:
        raise HTTPException(status_code=404, detail="Lead magnet not found")

    updates = {}
    for field, value in request.dict(exclude_unset=True).items():
        if value is not None:
            updates[field] = value

    if not updates:
        return magnet

    # If content changed, save a version
    content_fields = {"markdown_content", "landing_headline", "landing_body", "landing_cta", "title", "subtitle"}
    content_changed = any(f in updates for f in content_fields)

    if content_changed and magnet.get("markdown_content"):
        version_num = magnet.get("current_version", 0) + 1
        version = {
            "id": str(uuid.uuid4()),
            "lead_magnet_id": magnet_id,
            "version_number": version_num,
            "markdown_content": updates.get("markdown_content", magnet.get("markdown_content", "")),
            "title": updates.get("title", magnet.get("title", "")),
            "landing_headline": updates.get("landing_headline", magnet.get("landing_headline", "")),
            "landing_body": updates.get("landing_body", magnet.get("landing_body", "")),
            "landing_cta": updates.get("landing_cta", magnet.get("landing_cta", "")),
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        await db.lead_magnet_versions.insert_one(version)
        updates["current_version"] = version_num

    updates["updated_at"] = datetime.now(timezone.utc).isoformat()
    await db.lead_magnets.update_one({"id": magnet_id}, {"$set": updates})
    await log_activity("lead_magnet_updated", details=f"Updated lead magnet: {magnet.get('title') or magnet.get('topic')}")

    updated = await db.lead_magnets.find_one({"id": magnet_id}, {"_id": 0})
    return updated


@lead_magnet_router.delete("/lead-magnets/{magnet_id}")
async def delete_lead_magnet(magnet_id: str, user: dict = Depends(get_current_user)):
    magnet = await db.lead_magnets.find_one({"id": magnet_id}, {"_id": 0})
    if not magnet:
        raise HTTPException(status_code=404, detail="Lead magnet not found")
    if magnet.get("status") == "Published":
        raise HTTPException(status_code=400, detail="Cannot delete a published lead magnet. Archive it first.")

    await db.lead_magnets.delete_one({"id": magnet_id})
    await db.lead_magnet_versions.delete_many({"lead_magnet_id": magnet_id})
    await log_activity("lead_magnet_deleted", details=f"Deleted lead magnet: {magnet.get('title') or magnet.get('topic')}")
    return {"message": "Lead magnet deleted"}


# ================== GENERATION ==================

@lead_magnet_router.post("/lead-magnets/{magnet_id}/generate")
async def generate_content(magnet_id: str, user: dict = Depends(get_current_user)):
    magnet = await db.lead_magnets.find_one({"id": magnet_id}, {"_id": 0})
    if not magnet:
        raise HTTPException(status_code=404, detail="Lead magnet not found")

    result = await generate_lead_magnet_content(magnet)

    version_num = magnet.get("current_version", 0) + 1
    version = {
        "id": str(uuid.uuid4()),
        "lead_magnet_id": magnet_id,
        "version_number": version_num,
        "markdown_content": result["markdown_content"],
        "title": result.get("title", ""),
        "landing_headline": result.get("landing_headline", ""),
        "landing_body": result.get("landing_body", ""),
        "landing_cta": result.get("landing_cta", ""),
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    await db.lead_magnet_versions.insert_one(version)

    updates = {
        "title": result.get("title", magnet.get("title", "")),
        "subtitle": result.get("subtitle", ""),
        "description": result.get("description", ""),
        "markdown_content": result["markdown_content"],
        "landing_headline": result["landing_headline"],
        "landing_body": result["landing_body"],
        "landing_cta": result["landing_cta"],
        "suggested_filename": result.get("suggested_filename", ""),
        "current_version": version_num,
        "has_pdf": False,
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    await db.lead_magnets.update_one({"id": magnet_id}, {"$set": updates})
    await log_activity("lead_magnet_generated", details=f"Generated content for: {result.get('title', magnet.get('topic'))}")

    updated = await db.lead_magnets.find_one({"id": magnet_id}, {"_id": 0})
    return updated


@lead_magnet_router.post("/lead-magnets/{magnet_id}/regenerate-section")
async def regenerate_section(
    magnet_id: str,
    section: str = "content",
    user: dict = Depends(get_current_user),
):
    magnet = await db.lead_magnets.find_one({"id": magnet_id}, {"_id": 0})
    if not magnet:
        raise HTTPException(status_code=404, detail="Lead magnet not found")
    if not magnet.get("markdown_content"):
        raise HTTPException(status_code=400, detail="Generate content first before regenerating sections.")

    result = await generate_lead_magnet_content(magnet)

    updates = {"updated_at": datetime.now(timezone.utc).isoformat()}
    if section == "content":
        updates["markdown_content"] = result["markdown_content"]
    elif section == "landing":
        updates["landing_headline"] = result["landing_headline"]
        updates["landing_body"] = result["landing_body"]
        updates["landing_cta"] = result["landing_cta"]
    else:
        raise HTTPException(status_code=400, detail="Section must be 'content' or 'landing'")

    await db.lead_magnets.update_one({"id": magnet_id}, {"$set": updates})
    updated = await db.lead_magnets.find_one({"id": magnet_id}, {"_id": 0})
    return updated


# ================== PDF ==================

@lead_magnet_router.post("/lead-magnets/{magnet_id}/generate-pdf")
async def generate_pdf(magnet_id: str, user: dict = Depends(get_current_user)):
    magnet = await db.lead_magnets.find_one({"id": magnet_id}, {"_id": 0})
    if not magnet:
        raise HTTPException(status_code=404, detail="Lead magnet not found")
    if not magnet.get("markdown_content"):
        raise HTTPException(status_code=400, detail="Generate content before creating a PDF.")

    try:
        pdf_data = generate_pdf_bytes(magnet)

        pdf_dir = "/app/backend/pdf_storage"
        os.makedirs(pdf_dir, exist_ok=True)
        filename = magnet.get("suggested_filename") or magnet["id"]
        filepath = os.path.join(pdf_dir, f"{filename}.pdf")
        with open(filepath, "wb") as f:
            f.write(pdf_data)

        await db.lead_magnets.update_one(
            {"id": magnet_id},
            {"$set": {
                "has_pdf": True,
                "pdf_path": filepath,
                "updated_at": datetime.now(timezone.utc).isoformat(),
            }}
        )
        await log_activity("lead_magnet_pdf", details=f"PDF generated for: {magnet.get('title', magnet.get('topic'))}")

        return {"message": "PDF generated", "has_pdf": True}
    except Exception as e:
        import traceback
        logger.error(f"PDF generation error: {e}")
        logger.error(f"PDF generation traceback: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=f"PDF generation failed: {str(e)}")


@lead_magnet_router.get("/lead-magnets/{magnet_id}/preview-pdf")
async def preview_pdf(magnet_id: str, user: dict = Depends(get_current_user)):
    magnet = await db.lead_magnets.find_one({"id": magnet_id}, {"_id": 0})
    if not magnet:
        raise HTTPException(status_code=404, detail="Lead magnet not found")
    if not magnet.get("has_pdf") or not magnet.get("pdf_path"):
        raise HTTPException(status_code=400, detail="No PDF generated yet.")

    filepath = magnet["pdf_path"]
    if not os.path.exists(filepath):
        raise HTTPException(status_code=404, detail="PDF file not found on disk.")

    with open(filepath, "rb") as f:
        data = f.read()

    return Response(
        content=data,
        media_type="application/pdf",
        headers={"Content-Disposition": f"inline; filename={magnet.get('suggested_filename', magnet['id'])}.pdf"}
    )


# ================== PUBLISH / ARCHIVE ==================

@lead_magnet_router.post("/lead-magnets/{magnet_id}/mark-ready")
async def mark_ready(magnet_id: str, user: dict = Depends(get_current_user)):
    magnet = await db.lead_magnets.find_one({"id": magnet_id}, {"_id": 0})
    if not magnet:
        raise HTTPException(status_code=404, detail="Lead magnet not found")

    errors = []
    if not magnet.get("title"):
        errors.append("Title is required")
    if not magnet.get("landing_headline") or not magnet.get("landing_cta"):
        errors.append("Landing snippet (headline + CTA) is required")
    if not magnet.get("has_pdf"):
        errors.append("PDF must be generated first")
    if errors:
        raise HTTPException(status_code=400, detail="; ".join(errors))

    await db.lead_magnets.update_one(
        {"id": magnet_id},
        {"$set": {"status": "Ready", "updated_at": datetime.now(timezone.utc).isoformat()}}
    )
    await log_activity("lead_magnet_ready", details=f"Marked ready: {magnet.get('title')}")
    updated = await db.lead_magnets.find_one({"id": magnet_id}, {"_id": 0})
    return updated


@lead_magnet_router.post("/lead-magnets/{magnet_id}/publish")
async def publish_lead_magnet(magnet_id: str, user: dict = Depends(get_current_user)):
    magnet = await db.lead_magnets.find_one({"id": magnet_id}, {"_id": 0})
    if not magnet:
        raise HTTPException(status_code=404, detail="Lead magnet not found")
    if magnet["status"] not in ("Ready", "Published"):
        raise HTTPException(status_code=400, detail="Lead magnet must be in Ready status to publish. Mark it ready first.")

    download_url = f"/api/lm/{magnet['public_id']}/download"
    embed_code = generate_embed_code(magnet, download_url)

    await db.lead_magnets.update_one(
        {"id": magnet_id},
        {"$set": {
            "status": "Published",
            "embed_code": embed_code,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }}
    )
    await log_activity("lead_magnet_published", details=f"Published: {magnet.get('title')}")
    updated = await db.lead_magnets.find_one({"id": magnet_id}, {"_id": 0})
    return updated


@lead_magnet_router.post("/lead-magnets/{magnet_id}/archive")
async def archive_lead_magnet(magnet_id: str, user: dict = Depends(get_current_user)):
    magnet = await db.lead_magnets.find_one({"id": magnet_id}, {"_id": 0})
    if not magnet:
        raise HTTPException(status_code=404, detail="Lead magnet not found")

    await db.lead_magnets.update_one(
        {"id": magnet_id},
        {"$set": {"status": "Archived", "updated_at": datetime.now(timezone.utc).isoformat()}}
    )
    await log_activity("lead_magnet_archived", details=f"Archived: {magnet.get('title')}")
    updated = await db.lead_magnets.find_one({"id": magnet_id}, {"_id": 0})
    return updated


# ================== PUBLIC DOWNLOAD ==================

@lead_magnet_router.get("/lm/{public_id}/download")
async def public_download(public_id: str):
    magnet = await db.lead_magnets.find_one({"public_id": public_id}, {"_id": 0})
    if not magnet:
        raise HTTPException(status_code=404, detail="Not found")
    if magnet.get("status") == "Archived":
        raise HTTPException(status_code=410, detail="This resource has been archived.")
    if magnet.get("status") != "Published":
        raise HTTPException(status_code=404, detail="Not found")
    if not magnet.get("pdf_path") or not os.path.exists(magnet["pdf_path"]):
        raise HTTPException(status_code=404, detail="PDF not available")

    await db.lead_magnets.update_one(
        {"public_id": public_id},
        {
            "$inc": {"download_count": 1},
            "$set": {"last_download_at": datetime.now(timezone.utc).isoformat()},
        }
    )

    with open(magnet["pdf_path"], "rb") as f:
        data = f.read()

    filename = magnet.get("suggested_filename") or "lead-magnet"
    return Response(
        content=data,
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename={filename}.pdf"}
    )


# ================== VERSIONS ==================

@lead_magnet_router.get("/lead-magnets/{magnet_id}/versions")
async def list_versions(magnet_id: str, user: dict = Depends(get_current_user)):
    magnet = await db.lead_magnets.find_one({"id": magnet_id}, {"_id": 0})
    if not magnet:
        raise HTTPException(status_code=404, detail="Lead magnet not found")

    versions = []
    async for doc in db.lead_magnet_versions.find(
        {"lead_magnet_id": magnet_id}, {"_id": 0}
    ).sort("version_number", -1).limit(20):
        versions.append(doc)

    return {
        "lead_magnet_id": magnet_id,
        "title": magnet.get("title", ""),
        "current_version": magnet.get("current_version", 0),
        "versions": versions,
    }


@lead_magnet_router.post("/lead-magnets/{magnet_id}/versions/{version_id}/restore")
async def restore_version(magnet_id: str, version_id: str, user: dict = Depends(get_current_user)):
    magnet = await db.lead_magnets.find_one({"id": magnet_id}, {"_id": 0})
    if not magnet:
        raise HTTPException(status_code=404, detail="Lead magnet not found")

    version = await db.lead_magnet_versions.find_one(
        {"id": version_id, "lead_magnet_id": magnet_id}, {"_id": 0}
    )
    if not version:
        raise HTTPException(status_code=404, detail="Version not found")

    updates = {
        "markdown_content": version.get("markdown_content", ""),
        "title": version.get("title", magnet.get("title", "")),
        "landing_headline": version.get("landing_headline", magnet.get("landing_headline", "")),
        "landing_body": version.get("landing_body", magnet.get("landing_body", "")),
        "landing_cta": version.get("landing_cta", magnet.get("landing_cta", "")),
        "has_pdf": False,
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    await db.lead_magnets.update_one({"id": magnet_id}, {"$set": updates})
    await log_activity("lead_magnet_version_restored", details=f"Restored version {version.get('version_number')} for: {magnet.get('title')}")

    updated = await db.lead_magnets.find_one({"id": magnet_id}, {"_id": 0})
    return updated


