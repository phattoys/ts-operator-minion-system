"""
Execution Manifest Intake — Phase 3
(ops/execution-manifest-phase-3-intake-20260716, built on 809e25f93e65cb35536a3ea2850a673e9c295217)

Intake/transport gateway: lets a finished TSAF campaign packet -- or
another authorized source -- enter OPS as a structured Execution Manifest
without a human rebuilding it manually. This is the OPS *receiving* side
only. It does not build or modify TSAF, and does not claim a live TSAF
connection exists until one is actually configured and verified.

ARCHITECTURAL LAW (do not violate):
    TSAF creates.
    Execution Manifest receives and structures.
    OPS Execution Queue organizes.
    OPS operators execute.

This module creates manifests EXCLUSIVELY through the existing, unmodified
services/execution_manifest.create_manifest() and validates the nested
manifest EXCLUSIVELY through the existing, unmodified
services/execution_manifest.validate_manifest() -- no second competing
manifest schema, no duplicated validation or routing logic. It never
calls queue_execution_item()/queue_manifest(), never touches
services/wp_client.py or services/wp_write_safety.py, and never creates a
worker task. A successfully accepted packet produces a manifest in
exactly the same "received" state as a manifest created directly through
POST /api/execution-manifests -- the founder must still validate and
queue it themselves in the existing Phase 2 workspace.
"""
import hashlib
import hmac
import json
import time
import uuid
from datetime import datetime, timezone

from database import (
    db, logger,
    EXECUTION_MANIFEST_INTAKE_SECRET,
    EXECUTION_MANIFEST_INTAKE_REPLAY_WINDOW_SECONDS,
    EXECUTION_MANIFEST_MAX_BYTES,
)
from services.execution_manifest import create_manifest, validate_manifest, ManifestValidationError


class IntakeRejected(Exception):
    """
    Raised for a hard rejection that should not even produce a receipt
    (e.g. malformed JSON, oversized payload). Authentication failures on
    /receive are handled the same way -- see routes for rationale.
    """
    def __init__(self, status_code: int, detail: str):
        self.status_code = status_code
        self.detail = detail
        super().__init__(detail)


# ================== CHECKSUM ==================

def canonicalize(obj) -> str:
    """Deterministic JSON canonicalization for hashing: sorted keys, no
    incidental whitespace differences."""
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), default=str)


def compute_packet_checksum(envelope: dict) -> str:
    """
    SHA-256 over the canonicalized envelope, excluding the
    packet_checksum field itself (a field can't hash itself). This is
    what a sender is expected to compute and place in packet_checksum
    before signing/sending.
    """
    copy = {k: v for k, v in envelope.items() if k != "packet_checksum"}
    return hashlib.sha256(canonicalize(copy).encode("utf-8")).hexdigest()


def verify_checksum(envelope: dict) -> tuple:
    """Returns (status, calculated_checksum). status is one of:
    'not_supplied', 'match', 'mismatch'."""
    supplied = envelope.get("packet_checksum")
    calculated = compute_packet_checksum(envelope)
    if not supplied:
        return "not_supplied", calculated
    return ("match" if supplied == calculated else "mismatch"), calculated


# ================== AUTHENTICATION (HMAC) ==================

def verify_hmac_signature(raw_body: bytes, timestamp: str, signature: str) -> dict:
    """
    Verifies an X-TS-Signature HMAC-SHA256 over the raw request body,
    bound to the X-TS-Timestamp header (prevents signature reuse across
    different timestamps), checked against a replay window, using a
    constant-time comparison.

    Returns {"ok": bool, "reason": str}. Never logs or returns the secret.
    """
    if not EXECUTION_MANIFEST_INTAKE_SECRET:
        return {"ok": False, "reason": "intake secret not configured"}
    if not signature:
        return {"ok": False, "reason": "missing signature"}
    if not timestamp:
        return {"ok": False, "reason": "missing timestamp"}

    try:
        ts = float(timestamp)
    except (TypeError, ValueError):
        return {"ok": False, "reason": "invalid timestamp"}

    now = time.time()
    if abs(now - ts) > EXECUTION_MANIFEST_INTAKE_REPLAY_WINDOW_SECONDS:
        return {"ok": False, "reason": "stale timestamp (outside replay window)"}

    signing_input = timestamp.encode("utf-8") + b"." + raw_body
    expected = hmac.new(
        EXECUTION_MANIFEST_INTAKE_SECRET.encode("utf-8"),
        signing_input,
        hashlib.sha256,
    ).hexdigest()

    # Constant-time comparison -- never a plain == on secret-derived values.
    if not hmac.compare_digest(expected, signature):
        return {"ok": False, "reason": "invalid signature"}

    return {"ok": True, "reason": ""}


# ================== ENVELOPE VALIDATION ==================

REQUIRED_ENVELOPE_FIELDS = ["packet_id", "source_system", "manifest", "idempotency_key"]


def validate_envelope_shape(envelope: dict) -> list:
    """Minimal structural checks on the envelope itself (not the nested
    manifest, which is validated separately by the existing Phase 1
    validate_manifest())."""
    errors = []
    for field in REQUIRED_ENVELOPE_FIELDS:
        if not envelope.get(field):
            errors.append(f"envelope missing required field: {field}")
    if envelope.get("manifest") is not None and not isinstance(envelope["manifest"], dict):
        errors.append("envelope.manifest must be an object")
    return errors


# ================== RECEIPT STORAGE ==================

async def _find_by_idempotency_key(idempotency_key: str):
    return await db.execution_manifest_receipts.find_one({"idempotency_key": idempotency_key}, {"_id": 0})


async def _find_by_packet_id(packet_id: str):
    cursor = db.execution_manifest_receipts.find({"packet_id": packet_id}, {"_id": 0})
    return await cursor.to_list(length=50)


async def _store_receipt(fields: dict) -> dict:
    now = datetime.now(timezone.utc).isoformat()
    receipt = {
        "receipt_id": fields.get("receipt_id") or f"rcpt-{uuid.uuid4().hex[:12]}",
        "packet_id": fields.get("packet_id"),
        "idempotency_key": fields.get("idempotency_key"),
        "source_system": fields.get("source_system", "unknown"),
        "received_at": fields.get("received_at") or now,
        "authentication_status": fields.get("authentication_status", "unknown"),
        "checksum_status": fields.get("checksum_status", "not_supplied"),
        "schema_status": fields.get("schema_status", "unknown"),
        "manifest_id": fields.get("manifest_id"),
        "status": fields.get("status", ReceiptStatusValues.RECEIVED),
        "errors": fields.get("errors", []),
        "warnings": fields.get("warnings", []),
        "raw_packet_hash": fields.get("raw_packet_hash"),
        "received_by": fields.get("received_by"),
        "transport": fields.get("transport", "unknown"),
        "metadata": fields.get("metadata", {}),
        # Internal only, never part of the public ExecutionManifestReceipt
        # model / not returned by list/get by default -- needed so /retry
        # can reprocess without the sender resending. No secrets stored.
        "_envelope": fields.get("envelope"),
    }
    await db.execution_manifest_receipts.insert_one(dict(receipt))
    return {k: v for k, v in receipt.items() if k != "_id"}


def _public_receipt(receipt: dict) -> dict:
    return {k: v for k, v in receipt.items() if k != "_envelope"}


class ReceiptStatusValues:
    RECEIVED = "received"
    AUTHENTICATED = "authenticated"
    REJECTED = "rejected"
    DUPLICATE = "duplicate"
    QUARANTINED = "quarantined"
    VALIDATED = "validated"
    ACCEPTED = "accepted"
    FAILED = "failed"


# ================== MAIN INTAKE FLOW ==================

async def process_intake_packet(
    envelope: dict,
    transport: str,
    authentication_status: str,
    raw_packet_hash: str,
    received_by: str = None,
) -> dict:
    """
    Inbound packet -> authenticate transport (done by caller) -> verify
    checksum -> validate envelope -> validate nested existing manifest
    schema -> create intake receipt -> create existing Execution Manifest
    -> store receipt<->manifest linkage -> leave manifest unqueued.

    Idempotency and packet-identity-conflict checks happen first, before
    any of the above, so a replay or conflicting resend never re-executes
    validation/creation.
    """
    idempotency_key = envelope.get("idempotency_key")
    packet_id = envelope.get("packet_id")
    source_system = envelope.get("source_system", "unknown")

    # ---- Idempotency: exact same key already processed ----
    if idempotency_key:
        existing = await _find_by_idempotency_key(idempotency_key)
        if existing:
            logger.info(f"[Intake] Duplicate idempotency_key={idempotency_key}, returning original receipt {existing['receipt_id']}")
            return _public_receipt(existing)

    # ---- Packet-identity conflict: same packet_id, different payload ----
    if packet_id:
        prior = await _find_by_packet_id(packet_id)
        for p in prior:
            if p.get("raw_packet_hash") and p["raw_packet_hash"] != raw_packet_hash:
                receipt = await _store_receipt({
                    "packet_id": packet_id,
                    "idempotency_key": idempotency_key,
                    "source_system": source_system,
                    "authentication_status": authentication_status,
                    "checksum_status": "not_evaluated",
                    "schema_status": "not_evaluated",
                    "status": ReceiptStatusValues.QUARANTINED,
                    "errors": [f"packet_id '{packet_id}' was previously received with a different payload (conflict)"],
                    "raw_packet_hash": raw_packet_hash,
                    "received_by": received_by,
                    "transport": transport,
                    "envelope": envelope,
                })
                return _public_receipt(receipt)

    errors = []
    warnings = []

    # ---- Checksum ----
    checksum_status, calculated = verify_checksum(envelope)
    if checksum_status == "mismatch":
        errors.append(f"packet_checksum mismatch: supplied={envelope.get('packet_checksum')} calculated={calculated}")
    elif checksum_status == "not_supplied":
        warnings.append("no packet_checksum supplied -- integrity not verified")

    # ---- Envelope shape ----
    envelope_errors = validate_envelope_shape(envelope)
    errors.extend(envelope_errors)

    # ---- Nested manifest, via the EXISTING Phase 1 validator only ----
    schema_status = "not_evaluated"
    manifest_errors = []
    manifest_payload = envelope.get("manifest") if isinstance(envelope.get("manifest"), dict) else None
    if manifest_payload is not None:
        manifest_errors = await validate_manifest(manifest_payload)
        schema_status = "valid" if not manifest_errors else "invalid"
        errors.extend(manifest_errors)
    elif not envelope_errors:
        schema_status = "invalid"
        errors.append("envelope.manifest is missing or not an object")

    if errors:
        status = ReceiptStatusValues.QUARANTINED if checksum_status == "mismatch" or manifest_errors else ReceiptStatusValues.REJECTED
        receipt = await _store_receipt({
            "packet_id": packet_id,
            "idempotency_key": idempotency_key,
            "source_system": source_system,
            "authentication_status": authentication_status,
            "checksum_status": checksum_status,
            "schema_status": schema_status,
            "status": status,
            "errors": errors,
            "warnings": warnings,
            "raw_packet_hash": raw_packet_hash,
            "received_by": received_by,
            "transport": transport,
            "envelope": envelope,
        })
        return _public_receipt(receipt)

    # ---- All checks passed: create the manifest via the EXISTING Phase 1
    # function only. This never validates+queues, never executes a
    # worker, never touches WordPress. ----
    manifest_payload_for_create = dict(manifest_payload)
    manifest_payload_for_create.setdefault("source_system", source_system)
    manifest_payload_for_create.setdefault("source_packet_id", envelope.get("source_packet_id") or packet_id)
    manifest_payload_for_create.setdefault("campaign_id", envelope.get("campaign_id"))
    manifest_payload_for_create.setdefault("campaign_name", envelope.get("campaign_name"))
    manifest_payload_for_create.setdefault("brand_id", envelope.get("brand_id"))

    try:
        manifest = await create_manifest(manifest_payload_for_create)
    except ManifestValidationError as e:
        receipt = await _store_receipt({
            "packet_id": packet_id,
            "idempotency_key": idempotency_key,
            "source_system": source_system,
            "authentication_status": authentication_status,
            "checksum_status": checksum_status,
            "schema_status": schema_status,
            "status": ReceiptStatusValues.FAILED,
            "errors": e.errors,
            "warnings": warnings,
            "raw_packet_hash": raw_packet_hash,
            "received_by": received_by,
            "transport": transport,
            "envelope": envelope,
        })
        return _public_receipt(receipt)

    receipt = await _store_receipt({
        "packet_id": packet_id,
        "idempotency_key": idempotency_key,
        "source_system": source_system,
        "authentication_status": authentication_status,
        "checksum_status": checksum_status,
        "schema_status": schema_status,
        "manifest_id": manifest["manifest_id"],
        "status": ReceiptStatusValues.ACCEPTED,
        "errors": [],
        "warnings": warnings,
        "raw_packet_hash": raw_packet_hash,
        "received_by": received_by,
        "transport": transport,
        "envelope": envelope,
    })

    # Link the manifest back to its receipt for traceability, without
    # requiring this field for legacy (pre-Phase-3) manifests.
    await db.execution_manifests.update_one(
        {"manifest_id": manifest["manifest_id"]},
        {"$set": {
            "intake_receipt_id": receipt["receipt_id"],
            "intake_packet_id": packet_id,
            "intake_source_system": source_system,
            "intake_transport": transport,
            "intake_received_at": receipt["received_at"],
        }},
    )

    return _public_receipt(receipt)


# ================== RETRY ==================

async def retry_receipt(receipt_id: str, received_by: str = None) -> dict:
    """
    Founder-authenticated retry of a quarantined/failed receipt, using the
    envelope stored at receipt time (never re-authenticates against a
    resend -- authentication history is preserved, not bypassed). Remains
    idempotent: if the receipt's idempotency_key now matches an ACCEPTED
    receipt (e.g. a concurrent successful delivery), returns that instead
    of creating a second manifest.
    """
    existing = await db.execution_manifest_receipts.find_one({"receipt_id": receipt_id}, {"_id": 0})
    if not existing:
        raise ManifestValidationError([f"receipt '{receipt_id}' not found"])

    if existing["status"] == ReceiptStatusValues.ACCEPTED:
        return _public_receipt(existing)

    envelope = existing.get("_envelope")
    if not envelope:
        raise ManifestValidationError([f"receipt '{receipt_id}' has no stored envelope to retry"])

    # Preserve original authentication history -- retry does not
    # re-authenticate or upgrade an untrusted receipt to authenticated.
    result = await process_intake_packet(
        envelope=envelope,
        transport=existing.get("transport", "unknown"),
        authentication_status=existing.get("authentication_status", "unknown"),
        raw_packet_hash=existing.get("raw_packet_hash"),
        received_by=received_by or existing.get("received_by"),
    )
    return result


# ================== READ ==================

async def get_receipt(receipt_id: str) -> dict:
    receipt = await db.execution_manifest_receipts.find_one({"receipt_id": receipt_id}, {"_id": 0})
    return _public_receipt(receipt) if receipt else None


async def list_receipts(status: str = None, source_system: str = None, transport: str = None) -> list:
    query = {}
    if status:
        query["status"] = status
    if source_system:
        query["source_system"] = source_system
    if transport:
        query["transport"] = transport
    cursor = db.execution_manifest_receipts.find(query, {"_id": 0}).sort("received_at", -1)
    receipts = await cursor.to_list(length=500)
    return [_public_receipt(r) for r in receipts]
