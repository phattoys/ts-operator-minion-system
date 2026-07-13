import asyncio
import uuid
import io
import zipfile
import json
import re
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, HTTPException, Depends
from fastapi.responses import StreamingResponse

from database import db, PAGE_GENERATION_MODEL, QUALITY_SCORING_MODEL, logger
from models import (
    CreateBatchJobRequest, BATCH_JOB_TYPES, MAX_BATCH_SIZE,
)
from auth import get_current_user
from services.helpers import log_activity, create_version
from services.generation import (
    generate_page_content, apply_taste_tightener, score_page_quality,
)

batch_router = APIRouter(prefix="/api")

# Track running tasks so we can cancel
_running_tasks = {}


async def _process_batch_job(job_id: str):
    """Background worker that processes batch job items sequentially."""
    try:
        job = await db.batch_jobs.find_one({"id": job_id}, {"_id": 0})
        if not job:
            return

        await db.batch_jobs.update_one(
            {"id": job_id},
            {"$set": {"state": "running", "updated_at": datetime.now(timezone.utc).isoformat()}}
        )

        items = await db.batch_job_items.find(
            {"batch_job_id": job_id, "state": "queued"}, {"_id": 0}
        ).sort("created_at", 1).to_list(MAX_BATCH_SIZE)

        job_type = job.get("type")
        params = job.get("params", {})
        completed = 0
        failed = 0
        skipped = 0

        for item in items:
            # Check for cancellation
            fresh_job = await db.batch_jobs.find_one({"id": job_id}, {"_id": 0})
            if fresh_job and fresh_job.get("state") == "canceled":
                remaining = await db.batch_job_items.count_documents(
                    {"batch_job_id": job_id, "state": "queued"}
                )
                await db.batch_job_items.update_many(
                    {"batch_job_id": job_id, "state": "queued"},
                    {"$set": {"state": "canceled", "message": "Batch canceled by user"}}
                )
                break

            page_id = item["page_id"]
            item_id = item["id"]

            await db.batch_job_items.update_one(
                {"id": item_id},
                {"$set": {"state": "running", "started_at": datetime.now(timezone.utc).isoformat()}}
            )

            try:
                page = await db.pages.find_one({"id": page_id}, {"_id": 0})
                if not page:
                    await _mark_item(item_id, "failed", "Page not found")
                    failed += 1
                    continue

                if job_type == "generate":
                    await _process_generate(page, params)
                elif job_type == "score":
                    await _process_score(page, params)
                elif job_type == "tighten":
                    await _process_tighten(page)
                elif job_type == "status_change":
                    await _process_status_change(page, params)
                elif job_type == "export":
                    pass  # Export is handled at download time

                await _mark_item(item_id, "success")
                completed += 1

            except Exception as e:
                logger.error(f"Batch item {item_id} failed: {e}")
                await _mark_item(item_id, "failed", str(e)[:500])
                failed += 1

            # Update job progress
            await db.batch_jobs.update_one(
                {"id": job_id},
                {"$set": {
                    "completed_items": completed,
                    "failed_items": failed,
                    "skipped_items": skipped,
                    "updated_at": datetime.now(timezone.utc).isoformat(),
                }}
            )

        # Final state
        final_job = await db.batch_jobs.find_one({"id": job_id}, {"_id": 0})
        if final_job and final_job.get("state") != "canceled":
            final_state = "completed" if failed == 0 else "completed"
            await db.batch_jobs.update_one(
                {"id": job_id},
                {"$set": {
                    "state": final_state,
                    "completed_items": completed,
                    "failed_items": failed,
                    "skipped_items": skipped,
                    "updated_at": datetime.now(timezone.utc).isoformat(),
                }}
            )

        await log_activity(
            "batch_completed",
            details=f"Batch {job_type}: {completed} success, {failed} failed, {skipped} skipped"
        )

    except Exception as e:
        logger.error(f"Batch job {job_id} crashed: {e}")
        await db.batch_jobs.update_one(
            {"id": job_id},
            {"$set": {"state": "failed", "updated_at": datetime.now(timezone.utc).isoformat()}}
        )
    finally:
        _running_tasks.pop(job_id, None)


async def _mark_item(item_id: str, state: str, message: str = None):
    update = {"state": state, "finished_at": datetime.now(timezone.utc).isoformat()}
    if message:
        update["message"] = message
    await db.batch_job_items.update_one({"id": item_id}, {"$set": update})


async def _process_generate(page: dict, params: dict):
    page_id = page["id"]
    tone = params.get("tone", "professional")

    content = await generate_page_content(page, tone)
    content = re.sub(r'(?i)\bCTA:\s*', '', content)

    history_entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "tone": tone,
        "model": PAGE_GENERATION_MODEL,
        "content_preview": content[:200],
        "batch_generated": True,
    }

    await db.pages.update_one(
        {"id": page_id},
        {
            "$set": {
                "generated_content": content,
                "status": "Draft Ready",
                "updated_at": datetime.now(timezone.utc).isoformat(),
            },
            "$push": {"generation_history": history_entry},
        }
    )

    await create_version(
        page_id, content, "batch-generate",
        model_used=PAGE_GENERATION_MODEL, tone_used=tone,
    )


async def _process_score(page: dict, params: dict):
    page_id = page["id"]
    content = page.get("generated_content")
    if not content:
        raise Exception("No content to score")

    force = params.get("force_rescore", False)
    if not force and page.get("quality_score") and page.get("score_notes"):
        raise Exception("Already scored (use force_rescore to override)")

    score_result = await score_page_quality(page, content)
    overall = score_result.get("overall_score", 75)
    classification = score_result.get("classification", "usable")

    if classification == "strong" or overall >= 85:
        new_status = "Needs Review"
    elif classification == "rewrite" or overall < 70:
        new_status = "Needs Rewrite"
    else:
        new_status = "Needs Review"

    await db.pages.update_one(
        {"id": page_id},
        {"$set": {
            "quality_score": overall,
            "score_notes": score_result,
            "edit_recommendations": score_result.get("edit_recommendations", []),
            "status": new_status,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }}
    )


async def _process_tighten(page: dict):
    page_id = page["id"]
    content = page.get("generated_content")
    if not content:
        raise Exception("No content to tighten")

    tightened = await apply_taste_tightener(content, page)

    await db.pages.update_one(
        {"id": page_id},
        {"$set": {
            "generated_content": tightened,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }}
    )

    await create_version(
        page_id, tightened, "batch-tighten",
        model_used=QUALITY_SCORING_MODEL, tightened=True,
    )


async def _process_status_change(page: dict, params: dict):
    target_status = params.get("target_status")
    if not target_status:
        raise Exception("No target_status specified")

    valid = ["Approved", "Needs Rewrite", "Deferred"]
    if target_status not in valid:
        raise Exception(f"Invalid target status: {target_status}")

    await db.pages.update_one(
        {"id": page["id"]},
        {"$set": {"status": target_status, "updated_at": datetime.now(timezone.utc).isoformat()}}
    )

    await log_activity(
        f"batch_{target_status.lower().replace(' ', '_')}",
        page["id"], page.get("page_name"),
        f"Batch status change -> {target_status}"
    )


# ================== BATCH ENDPOINTS ==================

@batch_router.post("/batch-jobs", status_code=201)
async def create_batch_job(request: CreateBatchJobRequest, user: dict = Depends(get_current_user)):
    if request.type not in BATCH_JOB_TYPES:
        raise HTTPException(status_code=400, detail=f"Invalid type. Valid: {BATCH_JOB_TYPES}")

    if not request.page_ids:
        raise HTTPException(status_code=400, detail="No pages selected")

    # Deduplicate
    unique_ids = list(dict.fromkeys(request.page_ids))

    if len(unique_ids) > MAX_BATCH_SIZE:
        raise HTTPException(
            status_code=400,
            detail=f"Max batch size is {MAX_BATCH_SIZE}. Please run in multiple batches."
        )

    now = datetime.now(timezone.utc).isoformat()
    job = {
        "id": str(uuid.uuid4()),
        "type": request.type,
        "state": "queued",
        "params": request.params or {},
        "total_items": len(unique_ids),
        "completed_items": 0,
        "failed_items": 0,
        "skipped_items": 0,
        "created_at": now,
        "updated_at": now,
    }

    items = []
    for pid in unique_ids:
        items.append({
            "id": str(uuid.uuid4()),
            "batch_job_id": job["id"],
            "page_id": pid,
            "state": "queued",
            "message": None,
            "started_at": None,
            "finished_at": None,
            "created_at": now,
        })

    await db.batch_jobs.insert_one(job)
    job.pop("_id", None)

    if items:
        await db.batch_job_items.insert_many(items)

    await log_activity(
        "batch_created",
        details=f"Batch {request.type}: {len(unique_ids)} pages"
    )

    # Start background processing
    task = asyncio.create_task(_process_batch_job(job["id"]))
    _running_tasks[job["id"]] = task

    return {"job": job}


@batch_router.get("/batch-jobs")
async def list_batch_jobs(user: dict = Depends(get_current_user)):
    jobs = await db.batch_jobs.find({}, {"_id": 0}).sort("created_at", -1).to_list(50)
    return {"jobs": jobs, "total": len(jobs)}


@batch_router.get("/batch-jobs/{job_id}")
async def get_batch_job(job_id: str, user: dict = Depends(get_current_user)):
    job = await db.batch_jobs.find_one({"id": job_id}, {"_id": 0})
    if not job:
        raise HTTPException(status_code=404, detail="Batch job not found")

    items = await db.batch_job_items.find(
        {"batch_job_id": job_id}, {"_id": 0}
    ).sort("created_at", 1).to_list(MAX_BATCH_SIZE)

    # Enrich items with page names
    page_ids = [i["page_id"] for i in items]
    pages = await db.pages.find({"id": {"$in": page_ids}}, {"_id": 0, "id": 1, "page_name": 1}).to_list(len(page_ids))
    name_map = {p["id"]: p["page_name"] for p in pages}
    for item in items:
        item["page_name"] = name_map.get(item["page_id"], "Unknown")

    return {"job": job, "items": items}


@batch_router.post("/batch-jobs/{job_id}/cancel")
async def cancel_batch_job(job_id: str, user: dict = Depends(get_current_user)):
    job = await db.batch_jobs.find_one({"id": job_id}, {"_id": 0})
    if not job:
        raise HTTPException(status_code=404, detail="Batch job not found")

    if job["state"] not in ["queued", "running"]:
        raise HTTPException(status_code=400, detail=f"Cannot cancel job in state: {job['state']}")

    await db.batch_jobs.update_one(
        {"id": job_id},
        {"$set": {"state": "canceled", "updated_at": datetime.now(timezone.utc).isoformat()}}
    )

    await log_activity("batch_canceled", details=f"Batch {job['type']} canceled")
    return {"state": "canceled"}


@batch_router.post("/batch-jobs/{job_id}/retry-failed")
async def retry_failed_items(job_id: str, user: dict = Depends(get_current_user)):
    job = await db.batch_jobs.find_one({"id": job_id}, {"_id": 0})
    if not job:
        raise HTTPException(status_code=404, detail="Batch job not found")

    failed_items = await db.batch_job_items.find(
        {"batch_job_id": job_id, "state": "failed"}, {"_id": 0}
    ).to_list(MAX_BATCH_SIZE)

    if not failed_items:
        raise HTTPException(status_code=400, detail="No failed items to retry")

    page_ids = [i["page_id"] for i in failed_items]

    # Create a new batch job with just the failed items
    new_request = CreateBatchJobRequest(
        type=job["type"],
        page_ids=page_ids,
        params=job.get("params", {}),
    )

    return await create_batch_job(new_request, user)


@batch_router.get("/batch-jobs/{job_id}/download")
async def download_batch_export(job_id: str, user: dict = Depends(get_current_user)):
    job = await db.batch_jobs.find_one({"id": job_id}, {"_id": 0})
    if not job:
        raise HTTPException(status_code=404, detail="Batch job not found")

    if job["type"] != "export":
        raise HTTPException(status_code=400, detail="Not an export job")

    items = await db.batch_job_items.find(
        {"batch_job_id": job_id}, {"_id": 0}
    ).to_list(MAX_BATCH_SIZE)

    page_ids = [i["page_id"] for i in items]
    pages = await db.pages.find({"id": {"$in": page_ids}}, {"_id": 0}).to_list(len(page_ids))

    buf = io.BytesIO()
    manifest = []
    used_filenames = set()

    with zipfile.ZipFile(buf, 'w', zipfile.ZIP_DEFLATED) as zf:
        for page in pages:
            content = page.get("generated_content", "")
            if not content:
                continue

            slug = page.get("slug", page.get("page_name", "untitled").lower().replace(" ", "-"))
            filename = f"{slug}.md"
            counter = 1
            while filename in used_filenames:
                filename = f"{slug}-{counter}.md"
                counter += 1
            used_filenames.add(filename)

            header = f"""---
page_name: {page.get('page_name')}
slug: {page.get('slug')}
family: {page.get('page_family')}
type: {page.get('page_type')}
status: {page.get('status')}
score: {page.get('quality_score', 'N/A')}/100
---

"""
            zf.writestr(filename, header + content)
            manifest.append({
                "id": page.get("id"),
                "slug": slug,
                "title": page.get("page_name"),
                "status": page.get("status"),
                "filename": filename,
            })

        zf.writestr("manifest.json", json.dumps(manifest, indent=2))

    # Mark all items as success for export
    await db.batch_job_items.update_many(
        {"batch_job_id": job_id},
        {"$set": {"state": "success", "finished_at": datetime.now(timezone.utc).isoformat()}}
    )
    await db.batch_jobs.update_one(
        {"id": job_id},
        {"$set": {
            "state": "completed",
            "completed_items": len(pages),
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }}
    )

    buf.seek(0)
    return StreamingResponse(
        buf,
        media_type="application/zip",
        headers={"Content-Disposition": f"attachment; filename=page-export-{job_id[:8]}.zip"}
    )
