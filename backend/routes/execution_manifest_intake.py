"""
Execution Manifest Intake Routes — Phase 3.
Two controlled intake paths: authenticated server-to-server HMAC intake
(/receive) for future TSAF delivery, and founder-session manual intake
(/manual) for testing, recovery, or controlled manual handoff. Neither
path automatically queues workers or writes to WordPress -- see
services/execution_manifest_intake.py for the full design.
"""
import json
from fastapi import APIRouter, HTTPException, Depends, Request
from typing import Optional

from auth import get_current_user
from database import logger, EXECUTION_MANIFEST_MAX_BYTES
from models import ManualIntakeRequest
from services.execution_manifest_intake import (
    process_intake_packet,
    retry_receipt,
    get_receipt,
    list_receipts,
    verify_hmac_signature,
    canonicalize,
)
from services.execution_manifest import ManifestValidationError
import hashlib

intake_router = APIRouter(prefix="/api/execution-manifest-intake")


@intake_router.post("/receive")
async def receive(request: Request):
    """
    Authenticated server-to-server intake for future TSAF delivery. Not
    dependent on a founder browser session -- authenticates purely via
    the HMAC signature over the raw request body.

    No generic unauthenticated manifest endpoint exists anywhere in this
    layer; this is the only externally-callable intake path, and it is
    always signature-gated.
    """
    raw_body = await request.body()

    if len(raw_body) > EXECUTION_MANIFEST_MAX_BYTES:
        raise HTTPException(status_code=413, detail=f"Packet exceeds EXECUTION_MANIFEST_MAX_BYTES ({EXECUTION_MANIFEST_MAX_BYTES} bytes)")

    source = request.headers.get("X-TS-Source", "unknown")
    timestamp = request.headers.get("X-TS-Timestamp")
    signature = request.headers.get("X-TS-Signature")

    auth = verify_hmac_signature(raw_body, timestamp, signature)
    if not auth["ok"]:
        # Authentication failures are rejected outright and do not create a
        # receipt -- an unsigned/invalid request has no verified identity
        # to attribute a persistent audit record to, and persisting one
        # would let an attacker generate unbounded unauthenticated records.
        logger.warning(f"[Intake] /receive authentication failed: {auth['reason']} (source header: {source})")
        raise HTTPException(status_code=401, detail=f"Authentication failed: {auth['reason']}")

    try:
        envelope = json.loads(raw_body)
    except (json.JSONDecodeError, UnicodeDecodeError) as e:
        raise HTTPException(status_code=400, detail=f"Malformed JSON packet: {e}")

    if not isinstance(envelope, dict):
        raise HTTPException(status_code=400, detail="Packet must be a JSON object")

    raw_packet_hash = hashlib.sha256(raw_body).hexdigest()

    try:
        receipt = await process_intake_packet(
            envelope=envelope,
            transport="server_to_server",
            authentication_status="authenticated",
            raw_packet_hash=raw_packet_hash,
            received_by=None,
        )
    except ManifestValidationError as e:
        raise HTTPException(status_code=400, detail=e.errors)

    return receipt


@intake_router.post("/manual")
async def manual(request: ManualIntakeRequest, user: dict = Depends(get_current_user)):
    """
    Founder-session manual intake for testing, recovery, or controlled
    manual handoff. Uses the existing founder authentication -- never the
    server-to-server intake secret.
    """
    envelope = request.envelope.model_dump()
    raw_packet_hash = hashlib.sha256(canonicalize(envelope).encode("utf-8")).hexdigest()

    try:
        receipt = await process_intake_packet(
            envelope=envelope,
            transport="manual",
            authentication_status="founder_session",
            raw_packet_hash=raw_packet_hash,
            received_by=user.get("sub"),
        )
    except ManifestValidationError as e:
        raise HTTPException(status_code=400, detail=e.errors)

    return receipt


@intake_router.get("/receipts")
async def get_receipts(
    status: Optional[str] = None,
    source_system: Optional[str] = None,
    transport: Optional[str] = None,
    user: dict = Depends(get_current_user),
):
    receipts = await list_receipts(status=status, source_system=source_system, transport=transport)
    return {"receipts": receipts, "count": len(receipts)}


@intake_router.get("/receipts/{receipt_id}")
async def get_receipt_detail(receipt_id: str, user: dict = Depends(get_current_user)):
    receipt = await get_receipt(receipt_id)
    if not receipt:
        raise HTTPException(status_code=404, detail="Receipt not found")
    return receipt


@intake_router.post("/receipts/{receipt_id}/retry")
async def retry(receipt_id: str, user: dict = Depends(get_current_user)):
    """
    Founder-authenticated retry of a quarantined/failed receipt. Remains
    idempotent, never bypasses schema or authentication history, and
    never queues a worker task -- it only ever re-runs the same
    authenticate-was-already-done -> checksum -> validate -> create flow
    using the envelope captured at receipt time.
    """
    try:
        receipt = await retry_receipt(receipt_id, received_by=user.get("sub"))
    except ManifestValidationError as e:
        raise HTTPException(status_code=404, detail=e.errors)
    return receipt
