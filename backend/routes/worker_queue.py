"""
Worker Queue Routes — API for the TS OPS Worker Routing + Task Queue.
"""
from datetime import datetime, timezone
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import Optional

from database import db, logger
from auth import get_current_user
from services.worker_queue import (
    WORKERS,
    TASK_STATUSES,
    create_worker_task,
    execute_worker_task,
    get_queue_stats,
    route_after_analysis,
)

worker_queue_router = APIRouter(prefix="/api/worker-queue")


# ================== STATS ==================

@worker_queue_router.get("/stats")
async def queue_stats(user: dict = Depends(get_current_user)):
    """Get worker queue statistics."""
    return await get_queue_stats()


# ================== WORKERS INFO ==================

@worker_queue_router.get("/workers")
async def list_workers(user: dict = Depends(get_current_user)):
    """Get all worker definitions."""
    return {"workers": WORKERS}


# ================== TASK QUEUE ==================

@worker_queue_router.get("/tasks")
async def list_tasks(
    status: Optional[str] = None,
    worker: Optional[str] = None,
    source_module: Optional[str] = None,
    limit: int = 50,
    user: dict = Depends(get_current_user),
):
    """List tasks with optional filters."""
    query = {}
    if status:
        if status == "ready":
            query["status"] = "queued"
            query["founder_action_needed"] = True
        elif status in TASK_STATUSES:
            query["status"] = status
    if worker:
        query["worker"] = worker
    if source_module:
        query["source_module"] = source_module

    tasks = []
    async for doc in db.worker_tasks.find(query, {"_id": 0}).sort("created_at", -1).limit(limit):
        tasks.append(doc)

    return {"tasks": tasks, "count": len(tasks)}


@worker_queue_router.get("/tasks/{task_id}")
async def get_task(task_id: str, user: dict = Depends(get_current_user)):
    """Get a single task by ID."""
    task = await db.worker_tasks.find_one({"id": task_id}, {"_id": 0})
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    return task


# ================== EXECUTE TASK ==================

@worker_queue_router.post("/tasks/{task_id}/execute")
async def run_task(task_id: str, user: dict = Depends(get_current_user)):
    """Manually execute a queued task (founder-triggered)."""
    task = await db.worker_tasks.find_one({"id": task_id}, {"_id": 0})
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    if task["status"] not in ["queued", "needs_review"]:
        raise HTTPException(status_code=400, detail=f"Task is {task['status']}, cannot execute")

    result = await execute_worker_task(task_id)
    return result


# ================== BATCH EXECUTE ==================

class BatchExecuteRequest(BaseModel):
    task_ids: list[str]


@worker_queue_router.post("/batch-execute")
async def batch_execute(request: BatchExecuteRequest, user: dict = Depends(get_current_user)):
    """Execute multiple tasks at once."""
    if not request.task_ids:
        raise HTTPException(status_code=400, detail="No task IDs provided")

    results = {"executed": 0, "skipped": 0, "failed": 0, "details": []}

    for task_id in request.task_ids:
        task = await db.worker_tasks.find_one({"id": task_id}, {"_id": 0})
        if not task:
            results["skipped"] += 1
            continue
        if task["status"] not in ["queued", "needs_review"]:
            results["skipped"] += 1
            continue

        try:
            result = await execute_worker_task(task_id)
            if result.get("status") == "completed":
                results["executed"] += 1
            elif result.get("status") == "needs_review":
                results["executed"] += 1
            else:
                results["failed"] += 1
            results["details"].append({"task_id": task_id, "status": result.get("status")})
        except Exception as e:
            results["failed"] += 1
            results["details"].append({"task_id": task_id, "error": str(e)[:100]})

    return results


# ================== BATCH RUN WORKER ==================

class RunWorkerRequest(BaseModel):
    worker: str
    item_ids: list[str] = []
    batch_id: str = ""


@worker_queue_router.post("/run-worker")
async def run_worker_on_items(request: RunWorkerRequest, user: dict = Depends(get_current_user)):
    """Run a specific worker on selected items or entire batch."""
    if request.worker not in WORKERS:
        raise HTTPException(status_code=400, detail=f"Unknown worker: {request.worker}")

    # Get items to process
    query = {}
    if request.item_ids:
        query["id"] = {"$in": request.item_ids}
    elif request.batch_id:
        query["batch_id"] = request.batch_id
    else:
        raise HTTPException(status_code=400, detail="Provide item_ids or batch_id")

    items = []
    async for doc in db.field_items.find(query, {"_id": 0}):
        items.append(doc)

    if not items:
        raise HTTPException(status_code=404, detail="No items found")

    # Determine task type based on worker
    task_type_map = {
        "jenny": "title_refinement",
        "rene": "qa_check",
        "sam": "destination_pack",
        "wp_placement": "wp_draft",
    }
    task_type = task_type_map.get(request.worker, "unknown")

    created = 0
    for item in items:
        # Skip if task already exists and pending
        existing = await db.worker_tasks.find_one({
            "source_item_id": item["id"],
            "worker": request.worker,
            "status": {"$in": ["queued", "processing"]},
        })
        if existing:
            continue

        await create_worker_task(
            source_module="field_listing",
            source_item_id=item["id"],
            source_batch_id=item.get("batch_id", request.batch_id),
            worker=request.worker,
            task_type=task_type,
        )
        created += 1

    return {
        "worker": request.worker,
        "worker_name": WORKERS[request.worker]["name"],
        "tasks_created": created,
        "total_items": len(items),
        "auto_executed": WORKERS[request.worker]["auto_execute"],
    }


# ================== HOLD BACK / DISMISS ==================

@worker_queue_router.post("/tasks/{task_id}/hold")
async def hold_task(task_id: str, user: dict = Depends(get_current_user)):
    """Hold back a task from execution."""
    task = await db.worker_tasks.find_one({"id": task_id}, {"_id": 0})
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    await db.worker_tasks.update_one({"id": task_id}, {"$set": {
        "status": "held_back",
        "founder_action_needed": False,
        "completed_at": datetime.now(timezone.utc).isoformat(),
    }})
    return {"message": "Task held back", "task_id": task_id}


@worker_queue_router.post("/tasks/{task_id}/requeue")
async def requeue_task(task_id: str, user: dict = Depends(get_current_user)):
    """Requeue a held/failed/needs_review task."""
    task = await db.worker_tasks.find_one({"id": task_id}, {"_id": 0})
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    if task["status"] not in ["held_back", "failed", "needs_review"]:
        raise HTTPException(status_code=400, detail=f"Cannot requeue task with status: {task['status']}")

    await db.worker_tasks.update_one({"id": task_id}, {"$set": {
        "status": "queued",
        "founder_action_needed": not WORKERS.get(task["worker"], {}).get("auto_execute", False),
        "started_at": None,
        "completed_at": None,
        "result": {},
        "warnings": [],
    }})

    # If auto-execute, run it
    if WORKERS.get(task["worker"], {}).get("auto_execute", False):
        result = await execute_worker_task(task_id)
        return result

    updated = await db.worker_tasks.find_one({"id": task_id}, {"_id": 0})
    return updated


# ================== ACTIVITY LOG ==================

@worker_queue_router.get("/activity-log")
async def get_activity_log(
    limit: int = 30,
    worker: Optional[str] = None,
    user: dict = Depends(get_current_user),
):
    """Get worker activity log."""
    query = {}
    if worker:
        query["worker"] = worker

    logs = []
    async for doc in db.worker_activity_log.find(query, {"_id": 0}).sort("timestamp", -1).limit(limit):
        logs.append(doc)

    return {"logs": logs, "count": len(logs)}


# ================== QUEUE VIEWS (Grouped) ==================

@worker_queue_router.get("/views/ready")
async def view_ready(user: dict = Depends(get_current_user)):
    """Tasks ready for founder action."""
    tasks = []
    async for doc in db.worker_tasks.find(
        {"status": "queued", "founder_action_needed": True}, {"_id": 0}
    ).sort("created_at", -1).limit(50):
        tasks.append(doc)
    return {"tasks": tasks, "count": len(tasks)}


@worker_queue_router.get("/views/needs-review")
async def view_needs_review(user: dict = Depends(get_current_user)):
    """Tasks that need founder review."""
    tasks = []
    async for doc in db.worker_tasks.find(
        {"status": "needs_review"}, {"_id": 0}
    ).sort("created_at", -1).limit(50):
        tasks.append(doc)
    return {"tasks": tasks, "count": len(tasks)}


@worker_queue_router.get("/views/in-progress")
async def view_in_progress(user: dict = Depends(get_current_user)):
    """Tasks currently processing."""
    tasks = []
    async for doc in db.worker_tasks.find(
        {"status": {"$in": ["queued", "processing"]}}, {"_id": 0}
    ).sort("created_at", -1).limit(50):
        tasks.append(doc)
    return {"tasks": tasks, "count": len(tasks)}


@worker_queue_router.get("/views/completed")
async def view_completed(limit: int = 30, user: dict = Depends(get_current_user)):
    """Recently completed tasks."""
    tasks = []
    async for doc in db.worker_tasks.find(
        {"status": "completed"}, {"_id": 0}
    ).sort("completed_at", -1).limit(limit):
        tasks.append(doc)
    return {"tasks": tasks, "count": len(tasks)}


@worker_queue_router.get("/views/held-back")
async def view_held_back(user: dict = Depends(get_current_user)):
    """Tasks held back or skipped."""
    tasks = []
    async for doc in db.worker_tasks.find(
        {"status": {"$in": ["held_back", "failed"]}}, {"_id": 0}
    ).sort("created_at", -1).limit(50):
        tasks.append(doc)
    return {"tasks": tasks, "count": len(tasks)}
