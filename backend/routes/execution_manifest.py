"""
Execution Manifest Layer Routes — Phase 1.
Bridge between structured campaign/output packets and the existing OPS
Worker Queue. See services/execution_manifest.py for the full design notes
and the architectural law this layer must never violate.
"""
from fastapi import APIRouter, HTTPException, Depends
from typing import Optional

from auth import get_current_user
from models import ExecutionManifestCreateRequest, QueueItemRequest
from services.execution_manifest import (
    create_manifest,
    get_manifest,
    list_manifests,
    run_validation,
    queue_manifest,
    queue_execution_item,
    get_trace,
    ManifestValidationError,
)

execution_manifest_router = APIRouter(prefix="/api/execution-manifests")


@execution_manifest_router.post("")
async def create(request: ExecutionManifestCreateRequest, user: dict = Depends(get_current_user)):
    """
    Receive a structured execution manifest and store it. Does NOT validate,
    route, or execute anything -- those are separate, visible steps. No
    external write of any kind occurs here.
    """
    try:
        manifest = await create_manifest(request.model_dump())
    except ManifestValidationError as e:
        raise HTTPException(status_code=409, detail=e.errors)
    return manifest


@execution_manifest_router.get("")
async def list_all(status: Optional[str] = None, user: dict = Depends(get_current_user)):
    manifests = await list_manifests(status=status)
    return {"manifests": manifests, "count": len(manifests)}


@execution_manifest_router.get("/{manifest_id}")
async def get_one(manifest_id: str, user: dict = Depends(get_current_user)):
    manifest = await get_manifest(manifest_id)
    if not manifest:
        raise HTTPException(status_code=404, detail="Manifest not found")
    return manifest


@execution_manifest_router.post("/{manifest_id}/validate")
async def validate(manifest_id: str, user: dict = Depends(get_current_user)):
    """
    Validate a stored manifest and annotate each execution item with its
    routing decision (supported_now / needs_review / manual_required /
    connector_unavailable / unrecognized). Does not queue or execute
    anything.
    """
    try:
        result = await run_validation(manifest_id)
    except ManifestValidationError as e:
        raise HTTPException(status_code=404, detail=e.errors)
    return result


@execution_manifest_router.post("/{manifest_id}/queue")
async def queue_all(manifest_id: str, user: dict = Depends(get_current_user)):
    """
    Queue every 'ready' execution item as an existing worker_tasks record.
    Founder-gated tasks (e.g. WP Placement) remain founder-gated -- queueing
    only creates the task; it does not execute anything requiring approval.
    Idempotent per item.
    """
    try:
        result = await queue_manifest(manifest_id, user=user)
    except ManifestValidationError as e:
        raise HTTPException(status_code=404, detail=e.errors)
    return result


@execution_manifest_router.post("/{manifest_id}/items/{item_id}/queue")
async def queue_one(
    manifest_id: str,
    item_id: str,
    body: Optional[QueueItemRequest] = None,
    user: dict = Depends(get_current_user),
):
    """Queue a single execution item. Idempotent -- will not duplicate an existing worker task."""
    try:
        result = await queue_execution_item(manifest_id, item_id, user=user)
    except ManifestValidationError as e:
        raise HTTPException(status_code=404, detail=e.errors)
    return result


@execution_manifest_router.get("/{manifest_id}/trace")
async def trace(manifest_id: str, user: dict = Depends(get_current_user)):
    """manifest -> execution item -> worker task -> status -> result -> warnings"""
    try:
        result = await get_trace(manifest_id)
    except ManifestValidationError as e:
        raise HTTPException(status_code=404, detail=e.errors)
    return result
