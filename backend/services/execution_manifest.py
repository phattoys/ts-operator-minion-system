"""
Execution Manifest Layer — Phase 1
(ops/execution-manifest-phase-1-20260714, built on 3b47c8a1151d28026f8eacbf3ef5d5dd58fdc9ae)

Bridge between final structured campaign/output packets (from TSAF, or any
future source system) and safely routed OPS execution work.

ARCHITECTURAL LAW (do not violate):
    TSAF creates.
    Execution Manifest receives and structures.
    OPS Execution Queue organizes.
    OPS operators execute.
    TSAF is separate from OPS. OPS girls do not directly touch TSAF.

This module NEVER calls services/wp_client.py directly and NEVER issues or
consumes a WP approval token. It only ever creates ordinary worker_tasks
through the existing, unmodified services/worker_queue.create_worker_task(),
which routes into the existing, unmodified Jenny -> Rene -> WP Placement
chain and the existing, unmodified WP write-safety gate. Dry-run stays the
default, founder approval and a single-use token are still required for
any live WordPress write -- exactly as before this layer existed. This
layer only ever creates tasks that would then go through
services/wp_write_safety.py precisely as before.
"""
import uuid
from datetime import datetime, timezone

from database import db, logger
from services.worker_queue import create_worker_task


# ================== DESTINATION SUPPORT ==================
#
# Supporting a destination label does NOT mean the connector exists. Every
# recognized destination is documented here with its actual support level.
# See docs/EXECUTION_MANIFEST_SCHEMA.md for the full table and rationale.

DESTINATION_SUPPORT = {
    "wordpress": {
        "level": "supported_now",
        "reason": "WordPress connector exists (Jenny/Rene/WP Placement chain, write-safety gated).",
    },
    "metricool": {
        "level": "connector_unavailable",
        "reason": "No Metricool execution connector exists in this backend yet. Planned for a future phase.",
    },
    "facebook": {
        "level": "connector_unavailable",
        "reason": "No direct social publishing connector exists in OPS yet. Planned for a future phase.",
    },
    "instagram": {
        "level": "connector_unavailable",
        "reason": "No direct social publishing connector exists in OPS yet. Planned for a future phase.",
    },
    "tiktok": {
        "level": "connector_unavailable",
        "reason": "No direct social publishing connector exists in OPS yet. Planned for a future phase.",
    },
    "youtube_shorts": {
        "level": "connector_unavailable",
        "reason": "No direct social publishing connector exists in OPS yet. Planned for a future phase.",
    },
    "pinterest": {
        "level": "connector_unavailable",
        "reason": "No direct social publishing connector exists in OPS yet. Planned for a future phase.",
    },
    "linkedin": {
        "level": "connector_unavailable",
        "reason": "No direct social publishing connector exists in OPS yet. Planned for a future phase.",
    },
    "email": {
        "level": "connector_unavailable",
        "reason": "No email-sending connector (e.g. Klaviyo) exists in OPS yet. Planned for a future phase.",
    },
    "blog": {
        "level": "manual_required",
        "reason": "Non-WordPress blog destination has no connector; requires manual placement.",
    },
    "guide": {
        "level": "manual_required",
        "reason": "Digital guide delivery has no automated connector; requires manual handling.",
    },
    "digital_product": {
        "level": "manual_required",
        "reason": "Digital product delivery has no automated connector; requires manual handling.",
    },
    "hubspot": {
        "level": "connector_unavailable",
        "reason": "No HubSpot connector exists in OPS yet. Planned for a future phase.",
    },
    "ads": {
        "level": "connector_unavailable",
        "reason": "No ads-platform connector exists in OPS yet. Planned for a future phase.",
    },
    "manual": {
        "level": "manual_required",
        "reason": "Explicitly marked for manual execution by the source packet.",
    },
}

# Fields a manifest is never allowed to set on an execution item's context.
# These belong exclusively to the WP write-safety gate's own founder-driven
# approval flow (services/wp_write_safety.py) and must never be settable by
# a source packet, however it's structured or labeled.
FORBIDDEN_CONTEXT_KEYS = {"execution_mode", "approval_token"}


class ManifestValidationError(Exception):
    """Raised for hard validation failures. Callers should catch this and
    surface `errors` (a list of human-readable strings) to the caller."""
    def __init__(self, errors):
        self.errors = errors
        super().__init__("; ".join(errors))


# ================== VALIDATION ==================

async def validate_manifest(manifest: dict) -> list:
    """
    Validate a manifest dict (already parsed via ExecutionManifestCreateRequest
    or fetched from storage). Returns a list of error strings -- empty list
    means valid. Does not raise; callers decide what to do with the errors.
    """
    errors = []

    if not manifest.get("schema_version"):
        errors.append("schema_version is required")

    if not manifest.get("source_system"):
        errors.append("source_system is required")

    items = manifest.get("execution_items") or []
    if not items:
        errors.append("manifest must contain at least one execution item")

    # manifest_id uniqueness is checked separately at creation time (needs
    # the db to check against existing manifests) -- see create_manifest().

    item_ids = [i.get("item_id") for i in items]
    seen = set()
    for iid in item_ids:
        if not iid:
            errors.append("every execution item must have a non-empty item_id")
            continue
        if iid in seen:
            errors.append(f"duplicate execution item_id: {iid}")
        seen.add(iid)

    asset_ids = {a.get("asset_id") for a in (manifest.get("assets") or [])}

    for item in items:
        iid = item.get("item_id", "<missing>")

        destination = item.get("destination")
        if not destination:
            errors.append(f"item {iid}: destination is required")
        elif destination not in DESTINATION_SUPPORT:
            errors.append(f"item {iid}: destination '{destination}' is not a recognized destination label")

        execution_type = item.get("execution_type")
        if not execution_type:
            errors.append(f"item {iid}: execution_type is required")

        # Required instructions/content where applicable: any item destined
        # for actual content production needs copy or instructions.
        if destination == "wordpress" and execution_type in ("content_draft", "page_update", "page_create"):
            if not (item.get("copy") or "").strip() and not (item.get("instructions") or "").strip():
                errors.append(f"item {iid}: wordpress {execution_type} requires 'copy' or 'instructions'")

        # asset_refs must exist in the manifest's asset index
        for ref in item.get("asset_refs") or []:
            if ref not in asset_ids:
                errors.append(f"item {iid}: asset_ref '{ref}' not found in manifest assets")

        # dependencies must reference valid item ids (checked again below for cycles)
        for dep in item.get("dependencies") or []:
            if dep not in seen and dep not in item_ids:
                errors.append(f"item {iid}: dependency '{dep}' does not reference a valid item_id in this manifest")

        # No manifest field may bypass WordPress write-safety controls.
        ctx = item.get("context") or {}
        forbidden_present = FORBIDDEN_CONTEXT_KEYS & set(ctx.keys())
        if forbidden_present:
            errors.append(
                f"item {iid}: context may not set {sorted(forbidden_present)} -- "
                "live WordPress execution mode and approval tokens are controlled "
                "exclusively by the founder-driven WP write-safety gate, never by a manifest"
            )

    # Circular dependency detection (DFS over the whole item graph)
    if not any("dependency" in e and "does not reference" in e for e in errors):
        graph = {i.get("item_id"): (i.get("dependencies") or []) for i in items if i.get("item_id")}
        cycle = _find_cycle(graph)
        if cycle:
            errors.append(f"circular dependency detected: {' -> '.join(cycle)}")

    return errors


def _find_cycle(graph: dict):
    """DFS cycle detection. Returns the cycle path (list of item_ids) or None."""
    WHITE, GRAY, BLACK = 0, 1, 2
    color = {node: WHITE for node in graph}
    path = []

    def visit(node):
        color[node] = GRAY
        path.append(node)
        for dep in graph.get(node, []):
            if dep not in color:
                continue  # already reported as an invalid reference
            if color[dep] == GRAY:
                return path[path.index(dep):] + [dep]
            if color[dep] == WHITE:
                result = visit(dep)
                if result:
                    return result
        path.pop()
        color[node] = BLACK
        return None

    for node in graph:
        if color[node] == WHITE:
            result = visit(node)
            if result:
                return result
    return None


# ================== ROUTING ==================

def determine_routing(item: dict) -> dict:
    """
    Deterministic routing decision for one execution item. Never guesses --
    if no safe routing rule exists, returns support="needs_review".

    Returns: {support, worker, task_type, reason}
    """
    destination = item.get("destination")
    execution_type = item.get("execution_type")

    support_info = DESTINATION_SUPPORT.get(destination)
    if support_info is None:
        return {
            "support": "unrecognized",
            "worker": None,
            "task_type": None,
            "reason": f"Unrecognized destination '{destination}'",
        }

    if destination == "wordpress":
        if execution_type in ("content_draft", "page_update"):
            return {
                "support": "supported_now",
                "worker": "jenny",
                "task_type": "wp_content_draft",
                "reason": "Routed to Jenny (wp_content_draft) -> Rene (wp_content_qa) -> WP Placement (wp_page_update), write-safety gated.",
            }
        if execution_type == "page_create":
            return {
                "support": "supported_now",
                "worker": "wp_placement",
                "task_type": "wp_draft",
                "reason": "Routed to WP Placement create path, write-safety gated.",
            }
        return {
            "support": "needs_review",
            "worker": None,
            "task_type": None,
            "reason": f"No safe routing rule for wordpress execution_type '{execution_type}'",
        }

    if execution_type == "destination_pack":
        return {
            "support": "supported_now",
            "worker": "sam",
            "task_type": "destination_pack",
            "reason": "Routed to Sam (destination_pack).",
        }

    level = support_info["level"]
    if level == "supported_now":
        # Recognized + marked supported but no explicit rule matched above --
        # do not guess a worker. Needs an explicit rule to be added.
        return {
            "support": "needs_review",
            "worker": None,
            "task_type": None,
            "reason": f"Destination '{destination}' is supported in principle but has no explicit routing rule for execution_type '{execution_type}'",
        }

    return {"support": level, "worker": None, "task_type": None, "reason": support_info["reason"]}


# ================== STORAGE / CREATE ==================

async def create_manifest(payload: dict) -> dict:
    """
    Store a new manifest exactly as received (status=received). Does not
    validate or queue -- those are separate, visible steps.
    """
    now = datetime.now(timezone.utc).isoformat()
    manifest_id = payload.get("manifest_id") or f"man-{uuid.uuid4().hex[:12]}"

    existing = await db.execution_manifests.find_one({"manifest_id": manifest_id}, {"_id": 0})
    if existing:
        raise ManifestValidationError([f"manifest_id '{manifest_id}' already exists"])

    items = []
    for item in payload.get("execution_items", []):
        item = dict(item)
        item["manifest_id"] = manifest_id
        item.setdefault("status", "pending")
        item["created_at"] = now
        item["updated_at"] = now
        items.append(item)

    manifest = {
        "manifest_id": manifest_id,
        "schema_version": payload["schema_version"],
        "source_system": payload["source_system"],
        "source_packet_id": payload["source_packet_id"],
        "source_packet_type": payload.get("source_packet_type"),
        "campaign_id": payload.get("campaign_id"),
        "campaign_name": payload.get("campaign_name"),
        "brand_id": payload.get("brand_id"),
        "brand_name": payload.get("brand_name"),
        "created_at": now,
        "received_at": now,
        "status": "received",
        "priority": payload.get("priority", "normal"),
        "due_at": payload.get("due_at"),
        "created_by": payload.get("created_by"),
        "notes": payload.get("notes"),
        "execution_items": items,
        "assets": [dict(a) for a in payload.get("assets", [])],
        "metadata": payload.get("metadata", {}),
    }

    await db.execution_manifests.insert_one(dict(manifest))
    logger.info(f"[Execution Manifest] Received {manifest_id} from {manifest['source_system']} ({len(items)} items)")
    return {k: v for k, v in manifest.items() if k != "_id"}


async def get_manifest(manifest_id: str) -> dict:
    return await db.execution_manifests.find_one({"manifest_id": manifest_id}, {"_id": 0})


async def list_manifests(status: str = None) -> list:
    query = {"status": status} if status else {}
    cursor = db.execution_manifests.find(query, {"_id": 0}).sort("created_at", -1)
    return await cursor.to_list(length=500)


async def run_validation(manifest_id: str) -> dict:
    """
    Validate a stored manifest, update its status to validated/needs_review,
    annotate each item's routing decision + status, and persist. Idempotent.
    """
    manifest = await get_manifest(manifest_id)
    if not manifest:
        raise ManifestValidationError([f"manifest '{manifest_id}' not found"])

    errors = await validate_manifest(manifest)

    updated_items = []
    for item in manifest["execution_items"]:
        item = dict(item)
        if errors:
            # Manifest-level errors mean nothing is safe to route yet.
            item["status"] = "needs_review"
        else:
            routing = determine_routing(item)
            item["recommended_worker"] = routing["worker"]
            item["task_type"] = routing["task_type"] or item.get("task_type")
            if routing["support"] == "supported_now":
                item["status"] = "ready"
            elif routing["support"] == "manual_required":
                item["status"] = "blocked"
                if routing["reason"] not in item.get("warnings", []):
                    item.setdefault("warnings", []).append(f"manual execution required: {routing['reason']}")
            elif routing["support"] == "connector_unavailable":
                item["status"] = "blocked"
                if routing["reason"] not in item.get("warnings", []):
                    item.setdefault("warnings", []).append(f"connector unavailable: {routing['reason']}")
            else:  # needs_review / unrecognized
                item["status"] = "needs_review"
                if routing["reason"] not in item.get("warnings", []):
                    item.setdefault("warnings", []).append(routing["reason"])
        item["updated_at"] = datetime.now(timezone.utc).isoformat()
        updated_items.append(item)

    if errors:
        manifest_status = "needs_review"
    elif any(i["status"] == "needs_review" for i in updated_items):
        manifest_status = "needs_review"
    elif all(i["status"] in ("blocked",) for i in updated_items):
        manifest_status = "blocked"
    else:
        manifest_status = "validated"

    await db.execution_manifests.update_one(
        {"manifest_id": manifest_id},
        {"$set": {
            "status": manifest_status,
            "execution_items": updated_items,
            "validation_errors": errors,
        }},
    )

    return {
        "manifest_id": manifest_id,
        "status": manifest_status,
        "errors": errors,
        "execution_items": updated_items,
    }


# ================== QUEUEING ==================

async def queue_manifest(manifest_id: str, user: dict = None) -> dict:
    """Queue every 'ready' (supported_now) item in the manifest. Idempotent per item."""
    manifest = await get_manifest(manifest_id)
    if not manifest:
        raise ManifestValidationError([f"manifest '{manifest_id}' not found"])

    results = []
    for item in manifest["execution_items"]:
        if item["status"] == "ready":
            results.append(await queue_execution_item(manifest_id, item["item_id"], user=user))
        else:
            results.append({"item_id": item["item_id"], "queued": False, "reason": f"item status is '{item['status']}', not 'ready'"})

    manifest = await get_manifest(manifest_id)  # refresh
    statuses = {i["status"] for i in manifest["execution_items"]}
    if statuses == {"completed"}:
        new_status = "completed"
    elif "queued" in statuses or "processing" in statuses or "completed" in statuses:
        new_status = "in_progress"
    else:
        new_status = manifest["status"]
    await db.execution_manifests.update_one({"manifest_id": manifest_id}, {"$set": {"status": new_status}})

    return {"manifest_id": manifest_id, "items": results}


async def queue_execution_item(manifest_id: str, item_id: str, user: dict = None) -> dict:
    """
    Convert one 'ready' execution item into an existing worker_tasks record.
    Idempotent: if the item already has a worker_task_id pointing at a real
    task, does NOT create a duplicate.
    """
    manifest = await get_manifest(manifest_id)
    if not manifest:
        raise ManifestValidationError([f"manifest '{manifest_id}' not found"])

    item = next((i for i in manifest["execution_items"] if i["item_id"] == item_id), None)
    if not item:
        raise ManifestValidationError([f"execution item '{item_id}' not found in manifest '{manifest_id}'"])

    # Duplicate-queue protection
    if item.get("worker_task_id"):
        existing_task = await db.worker_tasks.find_one({"id": item["worker_task_id"]}, {"_id": 0})
        if existing_task:
            return {
                "item_id": item_id,
                "queued": False,
                "already_queued": True,
                "worker_task_id": item["worker_task_id"],
                "reason": "item already has a worker task; not creating a duplicate",
            }

    if item["status"] != "ready":
        return {"item_id": item_id, "queued": False, "reason": f"item status is '{item['status']}', not 'ready'"}

    routing = determine_routing(item)
    if routing["support"] != "supported_now":
        return {"item_id": item_id, "queued": False, "reason": routing["reason"]}

    # Build task context: traceability fields are mandatory and always win
    # over anything the manifest tried to set under the same keys.
    task_context = dict(item.get("context") or {})
    task_context.pop("execution_mode", None)
    task_context.pop("approval_token", None)

    if routing["worker"] == "jenny" and routing["task_type"] == "wp_content_draft":
        placement = item.get("placement") or {}
        task_context.setdefault("page_id", placement.get("page_id") or item.get("context", {}).get("page_id"))
        task_context.setdefault("wp_page_id", placement.get("wp_page_id") or item.get("context", {}).get("wp_page_id"))
        task_context.setdefault("insert_after", placement.get("insert_after", ""))
        task_context.setdefault("insert_before", placement.get("insert_before", ""))
        if item.get("copy"):
            task_context.setdefault("new_section_content", item["copy"])
        elif item.get("instructions"):
            task_context.setdefault("update_instructions", item["instructions"])
        if placement.get("publication_mode"):
            task_context.setdefault("publication_mode", placement["publication_mode"])

    task_context.update({
        "manifest_id": manifest_id,
        "execution_item_id": item_id,
        "source_packet_id": manifest.get("source_packet_id"),
        "campaign_id": manifest.get("campaign_id"),
        "destination": item.get("destination"),
        "execution_type": item.get("execution_type"),
    })

    task = await create_worker_task(
        source_module="execution_manifest",
        source_item_id=item_id,
        worker=routing["worker"],
        task_type=routing["task_type"],
        source_batch_id=manifest_id,
        context=task_context,
    )

    now = datetime.now(timezone.utc).isoformat()
    if task["status"] == "needs_review":
        new_item_status = "needs_review"
    elif task["status"] == "completed":
        new_item_status = "completed"
    elif task["status"] == "failed":
        new_item_status = "failed"
    else:
        new_item_status = "queued"

    await db.execution_manifests.update_one(
        {"manifest_id": manifest_id, "execution_items.item_id": item_id},
        {"$set": {
            "execution_items.$.worker_task_id": task["id"],
            "execution_items.$.status": new_item_status,
            "execution_items.$.result": task.get("result", {}),
            "execution_items.$.warnings": task.get("warnings", []),
            "execution_items.$.updated_at": now,
        }},
    )

    return {
        "item_id": item_id,
        "queued": True,
        "worker_task_id": task["id"],
        "worker": routing["worker"],
        "task_type": routing["task_type"],
        "task_status": task["status"],
    }


# ================== TRACEABILITY ==================

async def get_trace(manifest_id: str) -> dict:
    """manifest -> execution item -> worker task -> status -> result -> warnings"""
    manifest = await get_manifest(manifest_id)
    if not manifest:
        raise ManifestValidationError([f"manifest '{manifest_id}' not found"])

    trace_items = []
    for item in manifest["execution_items"]:
        task = None
        if item.get("worker_task_id"):
            task = await db.worker_tasks.find_one({"id": item["worker_task_id"]}, {"_id": 0})
        trace_items.append({
            "item_id": item["item_id"],
            "title": item.get("title"),
            "destination": item.get("destination"),
            "execution_type": item.get("execution_type"),
            "item_status": item.get("status"),
            "worker_task_id": item.get("worker_task_id"),
            "worker": task.get("worker") if task else item.get("recommended_worker"),
            "task_status": task.get("status") if task else None,
            "task_result": task.get("result") if task else {},
            "task_warnings": task.get("warnings") if task else [],
        })

    return {
        "manifest_id": manifest_id,
        "manifest_status": manifest["status"],
        "source_packet_id": manifest.get("source_packet_id"),
        "campaign_id": manifest.get("campaign_id"),
        "items": trace_items,
    }
