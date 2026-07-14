"""
Worker Queue Service — Task creation, routing rules, worker execution logic.
Workers: Jenny (copy), Rene (QA), Sam (packs), WP Placement.
"""
import uuid
from datetime import datetime, timezone

from database import db, logger
from services.field_listing import (
    refine_merged_title,
    generate_listing,
    generate_destination_pack,
)


# ---- Worker Definitions ----

WORKERS = {
    "jenny": {
        "name": "Jenny",
        "role": "Listing Copy Worker",
        "auto_execute": True,
        "task_types": ["title_refinement", "description_gen", "copy_cleanup"],
    },
    "rene": {
        "name": "Rene",
        "role": "QA / Cleanup Worker",
        "auto_execute": True,
        "task_types": ["qa_check", "readiness_check", "field_validation"],
    },
    "sam": {
        "name": "Sam",
        "role": "Routing / Pack Worker",
        "auto_execute": False,
        "task_types": ["destination_pack", "marketplace_routing"],
    },
    "wp_placement": {
        "name": "WP Placement",
        "role": "WordPress Action Worker",
        "auto_execute": False,
        "task_types": ["wp_draft", "page_placement", "wp_page_update"],
    },
}

TASK_STATUSES = ["queued", "processing", "completed", "needs_review", "failed", "held_back"]


# ---- Task Creation ----

async def create_worker_task(
    source_module: str,
    source_item_id: str,
    worker: str,
    task_type: str,
    source_batch_id: str = "",
    context: dict = None,
) -> dict:
    """Create a new worker task in the queue."""
    now = datetime.now(timezone.utc).isoformat()
    worker_def = WORKERS.get(worker, {})

    task = {
        "id": str(uuid.uuid4()),
        "source_module": source_module,
        "source_item_id": source_item_id,
        "source_batch_id": source_batch_id,
        "worker": worker,
        "worker_name": worker_def.get("name", worker),
        "task_type": task_type,
        "status": "queued",
        "auto_execute": worker_def.get("auto_execute", False),
        "founder_action_needed": not worker_def.get("auto_execute", False),
        "next_action": _get_next_action_label(worker, task_type),
        "context": context or {},
        "result": {},
        "warnings": [],
        "created_at": now,
        "started_at": None,
        "completed_at": None,
    }

    await db.worker_tasks.insert_one(task)
    logger.info(f"[Worker Queue] Created {worker}/{task_type} task for item {source_item_id[:8]}...")

    # Auto-execute if worker is configured for it
    if task["auto_execute"]:
        task = await execute_worker_task(task["id"])

    return {k: v for k, v in task.items() if k != "_id"}


def _get_next_action_label(worker: str, task_type: str) -> str:
    labels = {
        ("jenny", "title_refinement"): "Refine title from product photos",
        ("jenny", "description_gen"): "Generate listing description",
        ("jenny", "copy_cleanup"): "Clean up listing copy",
        ("rene", "qa_check"): "Run quality checks",
        ("rene", "readiness_check"): "Check export readiness",
        ("rene", "field_validation"): "Validate required fields",
        ("sam", "destination_pack"): "Generate destination packs",
        ("sam", "marketplace_routing"): "Route to marketplaces",
        ("wp_placement", "wp_draft"): "Create WordPress draft",
        ("wp_placement", "page_placement"): "Place page in WordPress",
        ("wp_placement", "wp_page_update"): "Update existing WordPress page",
        ("jenny", "wp_content_draft"): "Draft content update for WordPress page",
        ("rene", "wp_content_qa"): "QA content update before WordPress placement",
    }
    return labels.get((worker, task_type), f"{worker}: {task_type}")


# ---- Routing Rules ----

async def route_after_analysis(item_id: str, batch_id: str):
    """Route: field-listing item analyzed → Jenny task."""
    # Check if a Jenny task already exists for this item
    existing = await db.worker_tasks.find_one({
        "source_item_id": item_id,
        "worker": "jenny",
        "status": {"$in": ["queued", "processing"]},
    })
    if existing:
        return

    await create_worker_task(
        source_module="field_listing",
        source_item_id=item_id,
        source_batch_id=batch_id,
        worker="jenny",
        task_type="title_refinement",
    )


async def route_after_jenny(item_id: str, batch_id: str):
    """Route: Jenny done → Rene QA task."""
    existing = await db.worker_tasks.find_one({
        "source_item_id": item_id,
        "worker": "rene",
        "status": {"$in": ["queued", "processing"]},
    })
    if existing:
        return

    await create_worker_task(
        source_module="field_listing",
        source_item_id=item_id,
        source_batch_id=batch_id,
        worker="rene",
        task_type="qa_check",
    )


async def route_after_rene_approved(item_id: str, batch_id: str):
    """Route: Rene approved → Sam destination-pack task (founder-triggered)."""
    existing = await db.worker_tasks.find_one({
        "source_item_id": item_id,
        "worker": "sam",
        "status": {"$in": ["queued", "processing"]},
    })
    if existing:
        return

    await create_worker_task(
        source_module="field_listing",
        source_item_id=item_id,
        source_batch_id=batch_id,
        worker="sam",
        task_type="destination_pack",
    )


async def route_page_to_wp(page_id: str):
    """Route: approved page → WP Placement task (founder-triggered)."""
    existing = await db.worker_tasks.find_one({
        "source_item_id": page_id,
        "worker": "wp_placement",
        "status": {"$in": ["queued", "processing"]},
    })
    if existing:
        return

    await create_worker_task(
        source_module="page_ops",
        source_item_id=page_id,
        worker="wp_placement",
        task_type="wp_draft",
    )


# ---- Worker Execution ----

async def execute_worker_task(task_id: str, user: dict = None) -> dict:
    """
    Execute a worker task based on its type.

    `user` is the authenticated session (from get_current_user), threaded
    through ONLY so the wp_placement worker can resolve a server-derived
    approval identity for live WordPress writes (see services/wp_write_safety.py).
    Jenny, Rene, and Sam never touch WordPress and ignore this parameter
    entirely -- their behavior is unchanged.
    """
    task = await db.worker_tasks.find_one({"id": task_id}, {"_id": 0})
    if not task:
        return {"error": "Task not found"}

    if task["status"] not in ["queued", "needs_review"]:
        return task

    now = datetime.now(timezone.utc).isoformat()
    await db.worker_tasks.update_one({"id": task_id}, {"$set": {
        "status": "processing",
        "started_at": now,
    }})

    worker = task["worker"]
    result = {}

    try:
        if worker == "jenny":
            result = await _execute_jenny(task)
        elif worker == "rene":
            result = await _execute_rene(task)
        elif worker == "sam":
            result = await _execute_sam(task)
        elif worker == "wp_placement":
            result = await _execute_wp(task, user=user)
        else:
            result = {"error": f"Unknown worker: {worker}"}
    except Exception as e:
        logger.error(f"[Worker Queue] Execution failed for {worker}/{task_id}: {e}")
        result = {"error": str(e)[:300], "success": False}

    # Determine final status
    if result.get("needs_review"):
        status = "needs_review"
        founder_needed = True
    elif result.get("error") and not result.get("success"):
        status = "failed"
        founder_needed = True
    else:
        status = "completed"
        founder_needed = False

    completed_at = datetime.now(timezone.utc).isoformat()
    await db.worker_tasks.update_one({"id": task_id}, {"$set": {
        "status": status,
        "result": result,
        "warnings": result.get("warnings", []),
        "founder_action_needed": founder_needed,
        "completed_at": completed_at,
    }})

    # Log activity
    await _log_worker_activity(task, result, status)

    # Route to next worker if completed
    if status == "completed":
        # Pass result so routing can check outcome
        task["result"] = result
        await _route_next(task)

    updated = await db.worker_tasks.find_one({"id": task_id}, {"_id": 0})
    return updated


# ---- Jenny: Listing Copy Worker ----

async def _execute_jenny(task: dict) -> dict:
    """Jenny refines titles and generates descriptions."""
    task_type = task.get("task_type", "")

    # --- WP Page Content Drafting ---
    if task_type == "wp_content_draft":
        return await _jenny_draft_wp_content(task)

    # --- Field Listing work ---
    if task.get("source_module") == "field_listing":
        return await _jenny_field_listing(task)

    # --- Unknown task type — mark for review instead of silently noting ---
    return {
        "needs_review": True,
        "reason": f"Jenny cannot auto-handle task type '{task_type}' from module '{task.get('source_module', 'unknown')}'. Needs manual routing.",
        "warnings": [f"Unrecognized task source: {task.get('source_module')}"],
    }


async def _jenny_field_listing(task: dict) -> dict:
    """Jenny handles field-listing items: title refinement + descriptions."""
    item_id = task["source_item_id"]
    item = await db.field_items.find_one({"id": item_id}, {"_id": 0})
    if not item:
        return {"error": "Item not found", "success": False}

    images = item.get("images", [])
    vision = item.get("vision_analysis", {})
    warnings = []

    # Safety checks
    if not images:
        return {
            "needs_review": True,
            "reason": "No images available for title refinement",
            "warnings": ["No usable images"],
        }

    confidence = item.get("confidence", 0)
    if confidence < 0.3:
        return {
            "needs_review": True,
            "reason": f"Low confidence ({confidence:.0%}) — unclear product identification",
            "warnings": ["Low confidence on product identification"],
        }

    changes = {}

    # Title refinement — use multi-image if available
    image_paths = [img.get("path", "") for img in images if img.get("path")]
    valid_paths = [p for p in image_paths if p]

    if valid_paths and (not item.get("title_refined") or not item.get("draft_title")):
        refined = await refine_merged_title(
            valid_paths,
            [vision] if vision else [],
            await db.field_batches.find_one({"id": item.get("batch_id")}, {"_id": 0})
        )
        if refined.get("refined_title"):
            changes["draft_title"] = refined["refined_title"]
            changes["title_refined"] = True
        elif refined.get("error"):
            warnings.append(f"Title refinement issue: {refined['error'][:100]}")

    # Description generation — if missing
    if not item.get("short_description"):
        batch = await db.field_batches.find_one({"id": item.get("batch_id")}, {"_id": 0}) or {}
        # Use updated title if we just refined it
        item_for_listing = dict(item)
        if changes.get("draft_title"):
            item_for_listing["draft_title"] = changes["draft_title"]

        listing = await generate_listing(item_for_listing, batch)
        if listing.get("short_description"):
            changes["short_description"] = listing["short_description"]
            if listing.get("category_suggestion") and not item.get("category_suggestion"):
                changes["category_suggestion"] = listing["category_suggestion"]
            if listing.get("tags") and not item.get("tags"):
                changes["tags"] = listing["tags"]
            # If title from listing is better and we didn't just refine
            if listing.get("draft_title") and not changes.get("draft_title"):
                changes["draft_title"] = listing["draft_title"]

    # Apply changes
    if changes:
        changes["updated_at"] = datetime.now(timezone.utc).isoformat()
        await db.field_items.update_one({"id": item_id}, {"$set": changes})

    return {
        "success": True,
        "changes": changes,
        "warnings": warnings,
        "summary": f"Updated {len(changes)} fields" if changes else "No changes needed",
    }


async def _jenny_draft_wp_content(task: dict) -> dict:
    """Jenny drafts content for an existing WordPress page update."""
    from emergentintegrations.llm.chat import LlmChat, UserMessage
    from database import EMERGENT_LLM_KEY, PAGE_GENERATION_MODEL
    from services.wp_formatter import format_content_for_wp

    context = task.get("context", {})
    page_id = context.get("page_id", task["source_item_id"])
    update_instructions = context.get("update_instructions", "")
    insert_after = context.get("insert_after", "")
    insert_before = context.get("insert_before", "")
    new_section_content = context.get("new_section_content", "")

    if not update_instructions and not new_section_content:
        return {
            "needs_review": True,
            "reason": "No update instructions or content provided",
            "warnings": ["Missing update instructions"],
        }

    # Fetch the page
    page = await db.pages.find_one({"id": page_id}, {"_id": 0})
    if not page:
        return {"error": f"Page '{page_id}' not found", "success": False}

    current_content = page.get("generated_content", "")
    page_name = page.get("page_name", "Unknown")

    # If explicit new section content is provided, use it directly
    if new_section_content:
        drafted_html = format_content_for_wp(new_section_content)
    else:
        # Use LLM to draft the content update
        try:
            chat = LlmChat(
                api_key=EMERGENT_LLM_KEY,
                session_id=f"wp-update-{page_id[:8]}",
                system_message="You are a content editor for Temporary Satisfaction, a curated adult boutique in Long Beach, CA. Generate ONLY the new/updated section content in markdown format. Do not regenerate the entire page. Match the existing page tone and style. Be concise."
            )
            chat.with_model('openai', PAGE_GENERATION_MODEL)

            prompt = f"Page: {page_name}\nExisting content preview:\n{current_content[:1000]}\n\nUpdate request: {update_instructions}\n"
            if insert_after:
                prompt += f"Insert this AFTER the section: '{insert_after}'\n"
            if insert_before:
                prompt += f"Insert this BEFORE the section: '{insert_before}'\n"
            prompt += "\nGenerate only the new section content in markdown."

            msg = UserMessage(text=prompt)
            response = await chat.send_message(msg)
            drafted_html = format_content_for_wp(response.strip())
        except Exception as e:
            return {"error": f"Content drafting failed: {str(e)[:200]}", "success": False}

    # Store the draft in the task context for Rene/WP to use
    await db.worker_tasks.update_one({"id": task["id"]}, {"$set": {
        "context.drafted_html": drafted_html,
        "context.page_name": page_name,
        "context.page_id": page_id,
        "context.wp_page_id": page.get("wp_page_id", ""),
        "context.insert_after": insert_after,
        "context.insert_before": insert_before,
        "context.current_content_preview": current_content[:500],
    }})

    return {
        "success": True,
        "drafted_html": drafted_html[:300] + "..." if len(drafted_html) > 300 else drafted_html,
        "page_name": page_name,
        "summary": f"Drafted content update for '{page_name}' ({len(drafted_html)} chars)",
        "warnings": [],
    }


# ---- Rene: QA / Cleanup Worker ----

async def _execute_rene(task: dict) -> dict:
    """Rene checks quality, flags issues, validates readiness."""
    task_type = task.get("task_type", "")

    # --- WP Content QA ---
    if task_type == "wp_content_qa":
        return await _rene_qa_wp_content(task)

    # --- Field Listing QA ---
    item_id = task["source_item_id"]
    item = await db.field_items.find_one({"id": item_id}, {"_id": 0})
    if not item:
        # If not a field item, check if this is a page-related task
        if task.get("source_module") == "page_ops":
            return {"success": True, "passed": True, "summary": "Page QA — passed to next step", "warnings": []}
        return {"error": "Item not found", "success": False}

    issues = []
    warnings = []

    # Check required fields
    if not item.get("draft_title") or len(item.get("draft_title", "")) < 5:
        issues.append("Missing or too-short title")

    if not item.get("short_description"):
        issues.append("Missing description")

    if not item.get("images") or len(item.get("images", [])) == 0:
        issues.append("No images")

    # Check title quality
    title = item.get("draft_title", "")
    generic_titles = ["unknown product", "women's bikini", "product", "item", "untitled"]
    if title.lower().strip() in generic_titles:
        issues.append(f"Generic title: '{title}' — needs refinement")

    if len(title) < 15 and title:
        warnings.append(f"Short title ({len(title)} chars) — could be more descriptive")

    # Check price
    if not item.get("retail_price") and not item.get("unit_cost"):
        warnings.append("No price set — will need pricing before export")

    # Check confidence
    confidence = item.get("confidence", 0)
    if confidence < 0.4:
        warnings.append(f"Low confidence ({confidence:.0%}) — verify product identification")

    # Determine result
    if issues:
        return {
            "needs_review": True,
            "reason": f"QA failed: {'; '.join(issues)}",
            "issues": issues,
            "warnings": warnings,
            "passed": False,
        }

    # All checks passed — mark item as reviewed
    await db.field_items.update_one({"id": item_id}, {"$set": {
        "status": "review",
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }})

    return {
        "success": True,
        "passed": True,
        "issues": [],
        "warnings": warnings,
        "summary": f"QA passed{' with ' + str(len(warnings)) + ' warnings' if warnings else ''}",
    }


async def _rene_qa_wp_content(task: dict) -> dict:
    """Rene QA for WP page update: check drafted content exists and is reasonable."""
    context = task.get("context", {})
    drafted_html = context.get("drafted_html", "")
    page_name = context.get("page_name", "Unknown")

    issues = []
    warnings = []

    if not drafted_html:
        issues.append("No drafted HTML content found — Jenny may not have completed drafting")

    if drafted_html and len(drafted_html) < 20:
        issues.append(f"Drafted content is too short ({len(drafted_html)} chars)")

    if drafted_html and "<script" in drafted_html.lower():
        issues.append("Drafted content contains <script> tag — potential security issue")

    if not context.get("page_id") and not context.get("wp_page_id"):
        issues.append("No target page ID — cannot route to WP Placement")

    if issues:
        return {
            "needs_review": True,
            "reason": f"WP content QA failed for '{page_name}': {'; '.join(issues)}",
            "issues": issues,
            "warnings": warnings,
            "passed": False,
        }

    return {
        "success": True,
        "passed": True,
        "issues": [],
        "warnings": warnings,
        "summary": f"WP content QA passed for '{page_name}' ({len(drafted_html)} chars ready)",
    }


# ---- Sam: Routing / Pack Worker ----

async def _execute_sam(task: dict) -> dict:
    """Sam generates destination packs for marketplace routing."""
    item_id = task["source_item_id"]
    batch_id = task.get("source_batch_id", "")

    item = await db.field_items.find_one({"id": item_id}, {"_id": 0})
    if not item:
        return {"error": "Item not found", "success": False}

    batch = await db.field_batches.find_one({"id": batch_id or item.get("batch_id")}, {"_id": 0})
    if not batch:
        return {"error": "Batch not found", "success": False}

    destinations = batch.get("destinations", ["website", "offerup", "facebook"])
    packs = {}
    for dest in destinations:
        packs[dest] = generate_destination_pack(item, dest, batch)

    now = datetime.now(timezone.utc).isoformat()
    await db.field_items.update_one({"id": item_id}, {"$set": {
        "destination_packs": packs,
        "updated_at": now,
    }})

    return {
        "success": True,
        "destinations": destinations,
        "packs_generated": len(packs),
        "summary": f"Generated packs for {', '.join(destinations)}",
    }


# ---- WP Placement Worker ----

async def _execute_wp(task: dict, user: dict = None) -> dict:
    """
    WP Placement worker: creates new drafts OR updates existing pages.

    Write-safety gate (safety/unified-wp-write-gate-20260714):
    task["context"]["execution_mode"] controls what happens, defaulting to
    "dry_run" when absent so a task's first execution (the founder's first
    click on "Execute") NEVER writes to WordPress -- it produces a preview
    and an approval_token, and the task lands in "needs_review" via the
    existing status mechanism (result.needs_review == True). A second,
    explicit execute call with execution_mode="live" and that token is
    required to actually write.
    """
    task_type = task.get("task_type", "")

    # Route to update handler for existing page updates
    if task_type == "wp_page_update":
        return await _execute_wp_update(task, user=user)

    # --- Original: create new WP draft ---
    from services.wp_templates import infer_template, get_template
    from services.wp_placement import build_page_content
    from services.wp_client import create_page, IS_LIVE
    from services.wp_write_safety import issue_approval_token, WpWriteSafetyError
    from services.wp_formatter import parse_content_into_sections, format_content_for_wp

    page_id = task["source_item_id"]
    warnings = []
    context = task.get("context", {}) or {}
    execution_mode = context.get("execution_mode", "dry_run")
    publication_mode = context.get("publication_mode", "draft")
    approval_token = context.get("approval_token")

    # 1. Fetch page from Page Ops
    page = await db.pages.find_one({"id": page_id}, {"_id": 0})
    if not page:
        return {"error": f"Page {page_id} not found in Page Ops", "success": False}

    content_raw = page.get("generated_content", "")
    if not content_raw:
        return {
            "needs_review": True,
            "reason": "Page has no generated content — generate content in Page Ops first",
            "warnings": ["No generated content"],
        }

    page_title = page.get("page_name", "Untitled Page")
    page_type = page.get("page_type", "")

    # 2. Parse content into structured sections with proper formatting
    parsed = parse_content_into_sections(content_raw)
    hero = parsed["hero"]
    intro = parsed["intro"]
    body_sections = parsed["body_sections"]

    # 3. Infer template
    inference = infer_template(
        page_type=page_type,
        title=page_title,
        content=content_raw[:500],
    )
    template_id = inference.get("template_id", "standard_content")
    template = get_template(template_id)

    if not template:
        return {"error": f"Template {template_id} not found", "success": False}

    if inference.get("needs_review"):
        warnings.append(f"Template auto-inferred with {inference.get('confidence', '?')} confidence — verify selection")

    # 4. Build structured content with formatted HTML
    structured_content = {
        "hero_headline": hero,
        "subheadline": "",
        "intro": intro,
        "body_section_1": body_sections[0] if len(body_sections) > 0 else "",
        "body_section_2": body_sections[1] if len(body_sections) > 1 else "",
        "body_section_3": "\n".join(body_sections[2:]) if len(body_sections) > 2 else "",
        "cta_text": "",
        "cta_url": "",
        "related_links": [],
    }

    # 5. Build page HTML — safe to do in every mode, this never writes anywhere
    result = build_page_content(template, structured_content)
    html = result["html"]

    if not html or not html.strip():
        return {
            "needs_review": True,
            "reason": "Template rendering produced empty HTML — content may not map to template sections",
            "warnings": result.get("warnings", []),
        }

    warnings.extend(result.get("warnings", []))
    slug = page.get("slug", "") or page_title.lower().replace(" ", "-")[:60]

    # 6. Fetch WP settings
    settings = await db.wp_settings.find_one({}, {"_id": 0}) or {}
    wp_status = settings.get("default_status", "draft")

    write_payload = {"title": page_title, "slug": slug, "content": html, "meta": {}}

    # ---- DRY RUN (default): preview + approval token, no write ----
    if execution_mode == "dry_run":
        approval = await issue_approval_token(
            scope="single",
            scope_ids=[page_id],
            payload=write_payload,
            publication_mode=publication_mode,
        )
        return {
            "needs_review": True,
            "reason": "Dry-run preview ready — review and re-execute with execution_mode=live to write to WordPress",
            "preview": {
                "template": template["name"],
                "sections_placed": result["sections_placed"],
                "sections_skipped": result["sections_skipped"],
                "html_preview": html,
                "publication_mode": publication_mode,
            },
            "approval_token": approval["token"],
            "expires_at": approval["expires_at"],
            "warnings": warnings,
        }

    # ---- MOCK / LIVE: an actual write is being requested ----
    try:
        wp_page = await create_page(
            title=page_title,
            slug=slug,
            content=html,
            status=wp_status,
            meta={},
            execution_mode=execution_mode,
            approval_token=approval_token,
            scope_ids=[page_id],
            user=user,
        )
    except WpWriteSafetyError as e:
        return {"error": str(e), "success": False, "warnings": warnings}

    if not wp_page:
        return {
            "error": "WordPress page creation failed — check WP connection and credentials",
            "success": False,
            "warnings": warnings,
        }

    # 8. Log placement record
    now = datetime.now(timezone.utc).isoformat()
    placement = {
        "id": str(uuid.uuid4()),
        "mode": "create",
        "page_id": wp_page.get("id"),
        "wp_id": wp_page.get("wp_id"),
        "page_title": page_title,
        "slug": wp_page.get("slug", slug),
        "template_id": template_id,
        "template_name": template["name"],
        "inference": inference,
        "sections_placed": result["sections_placed"],
        "sections_skipped": result["sections_skipped"],
        "warnings": warnings,
        "wp_connected": IS_LIVE,
        "execution_mode": execution_mode,
        "status": wp_page.get("status", wp_status),
        "source": "worker_queue",
        "source_page_ops_id": page_id,
        "created_at": now,
    }
    await db.wp_placements.insert_one(placement)

    # 9. Update page status in Page Ops
    await db.pages.update_one({"id": page_id}, {"$set": {
        "status": "placed",
        "wp_page_id": wp_page.get("id"),
        "wp_placed_at": now,
        "updated_at": now,
    }})

    return {
        "success": True,
        "wp_page_id": wp_page.get("id"),
        "wp_id": wp_page.get("wp_id"),
        "wp_status": wp_page.get("status", wp_status),
        "template": template["name"],
        "sections_placed": len(result["sections_placed"]),
        "sections_skipped": len(result["sections_skipped"]),
        "wp_connected": IS_LIVE,
        "mock": wp_page.get("mock", False),
        "warnings": warnings,
        "summary": f"{'Created WP draft' if execution_mode == 'live' else 'Created mock draft'}: {page_title} ({template['name']}, {len(result['sections_placed'])} sections)",
    }


async def _execute_wp_update(task: dict, user: dict = None) -> dict:
    """
    WP Placement: UPDATE an existing WordPress page (not create new).

    Same write-safety gate as _execute_wp(): defaults to execution_mode
    "dry_run", which builds the exact new_content and returns it as a
    preview + approval_token without writing, leaving the Jenny -> Rene
    content-drafting chain that feeds this task completely unaffected.
    """
    from services.wp_client import update_page, get_page, IS_LIVE
    from services.wp_write_safety import issue_approval_token, WpWriteSafetyError

    context = task.get("context", {})
    drafted_html = context.get("drafted_html", "")
    page_id = context.get("page_id", task["source_item_id"])
    wp_page_id = context.get("wp_page_id", "")
    insert_after = context.get("insert_after", "")
    insert_before = context.get("insert_before", "")
    page_name = context.get("page_name", "Unknown")
    execution_mode = context.get("execution_mode", "dry_run")
    publication_mode = context.get("publication_mode", "draft")
    approval_token = context.get("approval_token")
    warnings = []

    if not drafted_html:
        return {"error": "No drafted content to insert", "success": False}

    # Resolve WP page ID
    if not wp_page_id:
        page = await db.pages.find_one({"id": page_id}, {"_id": 0})
        if page:
            wp_page_id = page.get("wp_page_id", "")
            page_name = page.get("page_name", page_name)

    if not wp_page_id:
        return {
            "error": f"Cannot find WordPress page ID for '{page_name}'. Page may not be placed yet.",
            "success": False,
        }

    # Fetch current WP page content
    current_wp = await get_page(str(wp_page_id))
    if not current_wp:
        return {"error": f"Could not fetch WP page {wp_page_id}", "success": False}

    current_content = current_wp.get("content", "")
    status_before = current_wp.get("status", "unknown")

    # Insert the new content at the specified location
    if insert_after:
        # Find the marker in the existing content and insert after it
        marker_idx = current_content.lower().find(insert_after.lower())
        if marker_idx >= 0:
            # Find the end of the section containing the marker
            # Look for the next [/section] or </section> after the marker
            section_end = current_content.find("[/section]", marker_idx)
            if section_end >= 0:
                insert_point = section_end + len("[/section]")
                new_content = current_content[:insert_point] + "\n" + drafted_html + "\n" + current_content[insert_point:]
            else:
                # No section marker found, insert after the paragraph containing the marker
                next_break = current_content.find("\n", marker_idx + len(insert_after))
                if next_break >= 0:
                    new_content = current_content[:next_break] + "\n" + drafted_html + "\n" + current_content[next_break:]
                else:
                    new_content = current_content + "\n" + drafted_html
        else:
            warnings.append(f"Could not find '{insert_after}' in page — appended at end")
            new_content = current_content + "\n" + drafted_html
    elif insert_before:
        marker_idx = current_content.lower().find(insert_before.lower())
        if marker_idx >= 0:
            # Find the start of the section containing the marker
            section_start = current_content.rfind("[section", 0, marker_idx)
            if section_start >= 0:
                new_content = current_content[:section_start] + drafted_html + "\n" + current_content[section_start:]
            else:
                new_content = current_content[:marker_idx] + drafted_html + "\n" + current_content[marker_idx:]
        else:
            warnings.append(f"Could not find '{insert_before}' in page — appended at end")
            new_content = current_content + "\n" + drafted_html
    else:
        # No specific location — append at end
        new_content = current_content + "\n" + drafted_html
        warnings.append("No insert location specified — content appended at end")

    write_payload = {"page_id": str(wp_page_id), "content": new_content, "title": None, "slug": None, "meta": {}}

    # ---- DRY RUN (default): preview + approval token, no write ----
    if execution_mode == "dry_run":
        approval = await issue_approval_token(
            scope="single",
            scope_ids=[str(wp_page_id)],
            payload=write_payload,
            publication_mode=publication_mode,
        )
        return {
            "needs_review": True,
            "reason": "Dry-run preview ready — review and re-execute with execution_mode=live to write to WordPress",
            "preview": {
                "page_title": page_name,
                "status_before": status_before,
                "content_added_chars": len(drafted_html),
                "insert_location": insert_after or insert_before or "end of page",
                "new_content_preview": new_content,
            },
            "approval_token": approval["token"],
            "expires_at": approval["expires_at"],
            "warnings": warnings,
        }

    # ---- MOCK / LIVE: an actual write is being requested ----
    # (preserve current status — this path never publishes; see wp_client.py)
    try:
        wp_result = await update_page(
            page_id=str(wp_page_id),
            content=new_content,
            execution_mode=execution_mode,
            approval_token=approval_token,
            scope_ids=[str(wp_page_id)],
            user=user,
        )
    except WpWriteSafetyError as e:
        return {"error": str(e), "success": False, "warnings": warnings}

    if not wp_result:
        return {
            "error": f"WordPress update failed for page {wp_page_id}",
            "success": False,
            "warnings": warnings,
        }

    # Log the update
    now = datetime.now(timezone.utc).isoformat()
    update_log = {
        "id": str(uuid.uuid4()),
        "mode": "update",
        "wp_id": int(wp_page_id),
        "page_title": page_name,
        "page_ops_id": page_id,
        "status_before": status_before,
        "status_after": wp_result.get("status", status_before),
        "section_inserted": drafted_html[:200],
        "insert_after": insert_after,
        "insert_before": insert_before,
        "content_length_before": len(current_content),
        "content_length_after": len(new_content),
        "warnings": warnings,
        "wp_connected": IS_LIVE,
        "source": "worker_queue_update",
        "created_at": now,
    }
    await db.wp_placements.insert_one(update_log)

    return {
        "success": True,
        "wp_page_id": str(wp_page_id),
        "page_title": page_name,
        "page_url": wp_result.get("link", ""),
        "status_before": status_before,
        "status_after": wp_result.get("status", status_before),
        "content_added_chars": len(drafted_html),
        "insert_location": insert_after or insert_before or "end of page",
        "warnings": warnings,
        "wp_connected": IS_LIVE,
        "summary": f"Updated '{page_name}' (WP {wp_page_id}) — inserted {len(drafted_html)} chars {'after ' + insert_after if insert_after else 'before ' + insert_before if insert_before else 'at end'}",
    }


# ---- Routing After Completion ----

async def _route_next(task: dict):
    """After a task completes, create the next task in the chain."""
    worker = task["worker"]
    item_id = task["source_item_id"]
    batch_id = task.get("source_batch_id", "")
    task_type = task.get("task_type", "")
    context = task.get("context", {})

    if worker == "jenny":
        if task_type == "wp_content_draft":
            # Jenny drafted WP content → route to Rene QA with UPDATED context
            # Fetch the latest context from Jenny's task (has drafted_html)
            updated_task = await db.worker_tasks.find_one({"id": task["id"]}, {"_id": 0})
            updated_context = updated_task.get("context", context) if updated_task else context
            await create_worker_task(
                source_module="page_ops",
                source_item_id=item_id,
                worker="rene",
                task_type="wp_content_qa",
                context=updated_context,
            )
        else:
            await route_after_jenny(item_id, batch_id)
    elif worker == "rene":
        result = task.get("result", {})
        if result.get("passed"):
            if task_type == "wp_content_qa":
                # Rene approved WP content → route to WP Placement for update
                await create_worker_task(
                    source_module="page_ops",
                    source_item_id=item_id,
                    worker="wp_placement",
                    task_type="wp_page_update",
                    context=context,
                )
            else:
                await route_after_rene_approved(item_id, batch_id)


# ---- Activity Logging ----

async def _log_worker_activity(task: dict, result: dict, status: str):
    """Log worker activity for audit trail."""
    log_entry = {
        "id": str(uuid.uuid4()),
        "task_id": task["id"],
        "worker": task["worker"],
        "worker_name": task.get("worker_name", task["worker"]),
        "task_type": task["task_type"],
        "source_module": task["source_module"],
        "source_item_id": task["source_item_id"],
        "source_batch_id": task.get("source_batch_id", ""),
        "action": task.get("next_action", ""),
        "status": status,
        "success": status == "completed",
        "changes": result.get("changes", {}),
        "warnings": result.get("warnings", []),
        "summary": result.get("summary", ""),
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    await db.worker_activity_log.insert_one(log_entry)


# ---- Queue Stats ----

async def get_queue_stats() -> dict:
    """Get worker queue statistics."""
    total = await db.worker_tasks.count_documents({})
    queued = await db.worker_tasks.count_documents({"status": "queued"})
    processing = await db.worker_tasks.count_documents({"status": "processing"})
    completed = await db.worker_tasks.count_documents({"status": "completed"})
    needs_review = await db.worker_tasks.count_documents({"status": "needs_review"})
    failed = await db.worker_tasks.count_documents({"status": "failed"})
    held_back = await db.worker_tasks.count_documents({"status": "held_back"})

    # Per-worker counts
    worker_stats = {}
    for w_key, w_def in WORKERS.items():
        w_total = await db.worker_tasks.count_documents({"worker": w_key})
        w_completed = await db.worker_tasks.count_documents({"worker": w_key, "status": "completed"})
        w_queued = await db.worker_tasks.count_documents({"worker": w_key, "status": "queued"})
        worker_stats[w_key] = {
            "name": w_def["name"],
            "role": w_def["role"],
            "total": w_total,
            "completed": w_completed,
            "queued": w_queued,
            "auto_execute": w_def["auto_execute"],
        }

    return {
        "total": total,
        "queued": queued,
        "processing": processing,
        "completed": completed,
        "needs_review": needs_review,
        "failed": failed,
        "held_back": held_back,
        "workers": worker_stats,
    }
