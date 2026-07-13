"""
Founder Command Center Routes — Launch queue, today's actions, page structure map.
"""
import json
from fastapi import APIRouter, HTTPException, Depends
from typing import Optional
from pydantic import BaseModel
from datetime import datetime, timezone

from database import db, logger
from auth import get_current_user
from services.command_center import (
    get_command_center_data,
    generate_page_code,
    ensure_all_page_codes,
    FAMILY_CODE_MAP,
)

command_center_router = APIRouter(prefix="/api/command-center")


# ================== MAIN DASHBOARD ==================

@command_center_router.get("/dashboard")
async def get_dashboard(user: dict = Depends(get_current_user)):
    """Get the full Founder Command Center data."""
    return await get_command_center_data()


# ================== PAGE CODE MANAGEMENT ==================

@command_center_router.get("/page-codes")
async def get_page_codes(user: dict = Depends(get_current_user)):
    """Get all page codes and the code scheme."""
    codes = []
    async for doc in db.pages.find(
        {"page_code": {"$exists": True, "$nin": [None, ""]}},
        {"_id": 0, "id": 1, "page_code": 1, "page_name": 1, "page_family": 1, "status": 1}
    ).sort("page_code", 1):
        codes.append(doc)

    return {
        "codes": codes,
        "scheme": FAMILY_CODE_MAP,
        "total": len(codes),
    }


class UpdatePageCodeRequest(BaseModel):
    page_code: str


@command_center_router.put("/pages/{page_id}/code")
async def update_page_code(page_id: str, request: UpdatePageCodeRequest, user: dict = Depends(get_current_user)):
    """Founder override: manually set a page code."""
    page = await db.pages.find_one({"id": page_id}, {"_id": 0})
    if not page:
        raise HTTPException(status_code=404, detail="Page not found")

    code = request.page_code.strip().upper()
    if not code:
        raise HTTPException(status_code=400, detail="Page code cannot be empty")

    # Check uniqueness
    existing = await db.pages.find_one({"page_code": code, "id": {"$ne": page_id}}, {"_id": 0})
    if existing:
        raise HTTPException(status_code=409, detail=f"Code '{code}' already used by '{existing.get('page_name')}'")

    await db.pages.update_one({"id": page_id}, {"$set": {
        "page_code": code,
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }})

    return {"page_id": page_id, "page_code": code, "page_name": page.get("page_name")}


# ================== PAGE TITLES (working + public) ==================

class UpdateTitlesRequest(BaseModel):
    working_title: Optional[str] = None
    public_title: Optional[str] = None
    menu_destination: Optional[str] = None
    footer_destination: Optional[str] = None
    funnel_stage: Optional[str] = None
    launch_priority: Optional[int] = None


@command_center_router.put("/pages/{page_id}/structure")
async def update_page_structure(page_id: str, request: UpdateTitlesRequest, user: dict = Depends(get_current_user)):
    """Update page structure metadata — titles, menu/footer placement, funnel stage."""
    page = await db.pages.find_one({"id": page_id}, {"_id": 0})
    if not page:
        raise HTTPException(status_code=404, detail="Page not found")

    updates = {}
    for field, value in request.dict(exclude_unset=True).items():
        if value is not None:
            updates[field] = value

    if updates:
        updates["updated_at"] = datetime.now(timezone.utc).isoformat()
        await db.pages.update_one({"id": page_id}, {"$set": updates})

    updated = await db.pages.find_one({"id": page_id}, {"_id": 0})
    return {k: v for k, v in updated.items() if k != "_id"}


# ================== BATCH LAUNCH ==================

class BatchLaunchRequest(BaseModel):
    page_ids: list[str]


@command_center_router.post("/batch-launch")
async def batch_launch(request: BatchLaunchRequest, user: dict = Depends(get_current_user)):
    """Launch multiple approved pages through WP worker at once."""
    from services.worker_queue import route_page_to_wp

    if not request.page_ids:
        raise HTTPException(status_code=400, detail="No page IDs provided")

    results = {"launched": 0, "skipped": 0, "errors": []}

    for page_id in request.page_ids:
        page = await db.pages.find_one({"id": page_id}, {"_id": 0})
        if not page:
            results["errors"].append(f"Page {page_id[:8]} not found")
            continue
        if page.get("status") != "Approved":
            results["skipped"] += 1
            continue

        try:
            await route_page_to_wp(page_id)
            results["launched"] += 1
        except Exception as e:
            results["errors"].append(f"Page {page.get('page_name')}: {str(e)[:100]}")

    return results


# ================== BATCH GENERATE ==================

class BatchGenerateRequest(BaseModel):
    page_ids: list[str]


@command_center_router.post("/batch-generate")
async def batch_generate_pages(request: BatchGenerateRequest, user: dict = Depends(get_current_user)):
    """Queue content generation for multiple planned pages."""
    if not request.page_ids:
        raise HTTPException(status_code=400, detail="No page IDs provided")

    queued = 0
    skipped = 0

    for page_id in request.page_ids:
        page = await db.pages.find_one({"id": page_id}, {"_id": 0})
        if not page:
            continue
        if page.get("generated_content"):
            skipped += 1
            continue

        # Set status to Generating to signal the page ops system
        await db.pages.update_one({"id": page_id}, {"$set": {
            "status": "Generating",
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }})
        queued += 1

    return {"queued": queued, "skipped": skipped, "total": len(request.page_ids)}


# ================== MINION ROLES DIRECTORY ==================

@command_center_router.get("/minion-directory")
async def get_minion_directory(user: dict = Depends(get_current_user)):
    """Get the Minion Roles Directory — what each module does."""
    # Gather live stats for each module
    page_count = await db.pages.count_documents({})
    pages_ready = await db.pages.count_documents({"status": {"$in": ["Draft Ready", "Needs Review"]}})
    catalog_count = await db.catalog_items.count_documents({})
    intake_count = await db.intake_sessions.count_documents({})
    field_batches = await db.field_batches.count_documents({})
    worker_tasks = await db.worker_tasks.count_documents({})
    wp_placements = await db.wp_placements.count_documents({})
    lead_magnets = await db.lead_magnets.count_documents({})
    specs = await db.specs.count_documents({})
    comms = await db.comms_drafts.count_documents({})

    minions = [
        {
            "name": "Page Ops Minion",
            "code": "page_ops",
            "role": "Page creation + review queue",
            "what_it_does": "Generates, scores, and queues pages for approval and launch",
            "solves": "Page creation labor and workflow chaos",
            "inputs": "Page family, district, purpose, tone, CTA, page map logic",
            "outputs": "Draft pages, quality scores, edit recommendations, approval queue",
            "workflow_stage": "Content Creation",
            "status": "active",
            "labor_ready": True,
            "nav_path": "/queue",
            "stats": f"{page_count} pages, {pages_ready} ready for review",
            "next_action": f"Review {pages_ready} pages" if pages_ready else "Generate next batch",
        },
        {
            "name": "Worker Queue",
            "code": "worker_queue",
            "role": "Task routing + auto-execution",
            "what_it_does": "Routes tasks to Jenny/Rene/Sam/WP workers, auto-executes safe tasks, queues founder-triggered ones",
            "solves": "Handoff labor between modules — stops you from being the bridge",
            "inputs": "Module outputs (analyzed items, approved pages, QA results)",
            "outputs": "Refined titles, QA reports, destination packs, WP drafts",
            "workflow_stage": "Orchestration",
            "status": "active",
            "labor_ready": True,
            "nav_path": "/workers",
            "stats": f"{worker_tasks} total tasks",
            "next_action": "Check worker queue for pending actions",
        },
        {
            "name": "WP Page Placement",
            "code": "wp_placement",
            "role": "WordPress draft creation",
            "what_it_does": "Takes approved pages, builds Flatsome/UX Builder HTML, creates real WP drafts",
            "solves": "Manual page placement and WordPress copy-paste labor",
            "inputs": "Approved pages with generated content",
            "outputs": "Live WordPress drafts on temporarysatisfaction.com",
            "workflow_stage": "Publishing",
            "status": "active",
            "labor_ready": True,
            "nav_path": "/wp-placement",
            "stats": f"{wp_placements} pages placed",
            "next_action": "Place approved pages" if pages_ready else "Waiting on approvals",
        },
        {
            "name": "Field-to-Listing",
            "code": "field_listing",
            "role": "Photo batch → listing records",
            "what_it_does": "Takes raw product photos, runs Vision AI analysis, generates titles/descriptions/destination packs",
            "solves": "Products bought but never listed — phone photos sitting in camera roll",
            "inputs": "Product photos, vendor notes, pricing notes",
            "outputs": "Listing-ready records with titles, descriptions, marketplace packs",
            "workflow_stage": "Product Intake",
            "status": "active",
            "labor_ready": True,
            "nav_path": "/field-listing",
            "stats": f"{field_batches} batches",
            "next_action": "Upload next product batch",
        },
        {
            "name": "Product Intake Minion",
            "code": "product_intake",
            "role": "Invoice/order → draft products",
            "what_it_does": "Parses invoices, order confirmations, and vendor docs into draft product records",
            "solves": "Vendor orders that never get listed because intake is too slow",
            "inputs": "CSV, XLSX, PDF invoices, order confirmations",
            "outputs": "Draft products with titles, pricing, categories, WooCommerce export",
            "workflow_stage": "Product Intake",
            "status": "active",
            "labor_ready": True,
            "nav_path": "/intake",
            "stats": f"{intake_count} sessions",
            "next_action": "Import next vendor order",
        },
        {
            "name": "Catalog Minion",
            "code": "catalog",
            "role": "Product normalization + Woo export",
            "what_it_does": "Maps vendor feeds, AI-categorizes products, deduplicates, exports clean WooCommerce CSV",
            "solves": "Messy vendor feed cleanup and category chaos",
            "inputs": "Intake products, manual entries, vendor data",
            "outputs": "Normalized catalog, category assignments, WooCommerce-ready export",
            "workflow_stage": "Product Management",
            "status": "active",
            "labor_ready": True,
            "nav_path": "/catalog",
            "stats": f"{catalog_count} items",
            "next_action": "Review catalog items",
        },
        {
            "name": "Lead Magnet Minion",
            "code": "lead_magnets",
            "role": "Lead magnet + opt-in asset creation",
            "what_it_does": "Creates downloadable lead magnets and supporting funnel copy (opt-in, thank-you, email)",
            "solves": "List-building asset creation labor",
            "inputs": "Topic, audience, format, angle",
            "outputs": "Lead magnet content, opt-in copy, thank-you copy, email sequences",
            "workflow_stage": "Marketing",
            "status": "active",
            "labor_ready": True,
            "nav_path": "/lead-magnets",
            "stats": f"{lead_magnets} magnets",
            "next_action": "Create next lead magnet",
        },
        {
            "name": "Spec Writer Minion",
            "code": "spec_writer",
            "role": "Idea → build-ready spec",
            "what_it_does": "Turns founder ideas into structured build specs with scoring and follow-up questions",
            "solves": "Bad dev handoffs, fuzzy requirements, wasted build spend",
            "inputs": "Founder idea, pain point, intended users, build type",
            "outputs": "Structured spec, quality score, refined versions",
            "workflow_stage": "Planning",
            "status": "active",
            "labor_ready": True,
            "nav_path": "/specs",
            "stats": f"{specs} specs",
            "next_action": "Write next spec",
        },
        {
            "name": "Customer Comms Minion",
            "code": "comms",
            "role": "Brand-right communication drafting",
            "what_it_does": "Generates customer-facing communications that match brand voice",
            "solves": "Writing customer emails/messages from scratch every time",
            "inputs": "Communication scenario, customer context, tone",
            "outputs": "Ready-to-send drafts",
            "workflow_stage": "Customer Relations",
            "status": "active",
            "labor_ready": True,
            "nav_path": "/comms",
            "stats": f"{comms} drafts",
            "next_action": "Draft next communication",
        },
        {
            "name": "Execution Spine",
            "code": "spine",
            "role": "Cross-module orchestration",
            "what_it_does": "Routes tasks across modules, tracks status, provides one-click execution actions",
            "solves": "Remembering what needs to happen next across all modules",
            "inputs": "All module statuses and outputs",
            "outputs": "Unified task view, execution actions, status tracking",
            "workflow_stage": "Orchestration",
            "status": "active",
            "labor_ready": True,
            "nav_path": "/spine",
            "stats": "Connected to all modules",
            "next_action": "Check spine for pending actions",
        },
    ]

    return {"minions": minions, "total": len(minions)}



# ================== EXECUTION MAP ==================

class ExecutionMapRequest(BaseModel):
    goal_input: str
    timeframe: str = ""
    priority: str = ""
    main_lane: str = ""


@command_center_router.post("/execution-map")
async def create_execution_map(request: ExecutionMapRequest, user: dict = Depends(get_current_user)):
    """Generate and persist an execution map from a messy founder goal."""
    from services.execution_map import generate_execution_map, save_execution_map

    if not request.goal_input.strip():
        raise HTTPException(status_code=400, detail="Goal input is required")

    # Generate the map via LLM
    map_data = await generate_execution_map(
        goal_input=request.goal_input.strip(),
        timeframe=request.timeframe.strip(),
        priority=request.priority.strip(),
        main_lane=request.main_lane.strip(),
    )

    if map_data.get("error"):
        raise HTTPException(status_code=500, detail=map_data["error"])

    # Persist to MongoDB
    saved = await save_execution_map(
        goal_input=request.goal_input.strip(),
        timeframe=request.timeframe.strip(),
        priority=request.priority.strip(),
        main_lane=request.main_lane.strip(),
        map_data=map_data,
    )

    return saved


@command_center_router.get("/execution-maps")
async def list_execution_maps(limit: int = 20, user: dict = Depends(get_current_user)):
    """List all saved execution maps."""
    maps = []
    async for doc in db.execution_maps.find({}, {"_id": 0}).sort("created_at", -1).limit(limit):
        maps.append(doc)
    return {"maps": maps, "count": len(maps)}


@command_center_router.get("/execution-maps/{map_id}")
async def get_execution_map(map_id: str, user: dict = Depends(get_current_user)):
    """Get a single execution map by ID."""
    doc = await db.execution_maps.find_one({"id": map_id}, {"_id": 0})
    if not doc:
        raise HTTPException(status_code=404, detail="Execution map not found")
    return doc


@command_center_router.post("/execution-maps/{map_id}/send-to-queue")
async def send_first_action_to_queue(map_id: str, user: dict = Depends(get_current_user)):
    """Send the first action from an execution map to the worker queue as a real task."""
    from services.worker_queue import create_worker_task

    doc = await db.execution_maps.find_one({"id": map_id}, {"_id": 0})
    if not doc:
        raise HTTPException(status_code=404, detail="Execution map not found")

    first_actions = doc.get("first_actions", [])
    if not first_actions:
        raise HTTPException(status_code=400, detail="No first actions in this execution map")

    first = first_actions[0]
    action_text = first.get("action", "")
    owner = first.get("owner", "").lower()

    # Map owner to a worker or create a general task
    worker = "jenny"  # default
    task_type = "copy_cleanup"
    if "page" in owner or "page ops" in owner:
        worker = "jenny"
        task_type = "title_refinement"
    elif "rene" in owner or "qa" in owner:
        worker = "rene"
        task_type = "qa_check"
    elif "sam" in owner or "pack" in owner:
        worker = "sam"
        task_type = "destination_pack"
    elif "wp" in owner or "wordpress" in owner:
        worker = "wp_placement"
        task_type = "wp_draft"

    task = await create_worker_task(
        source_module="execution_map",
        source_item_id=map_id,
        worker=worker,
        task_type=task_type,
        context={"action": action_text, "from_map": doc.get("main_goal", "")},
    )

    # Mark the action as sent
    now = datetime.now(timezone.utc).isoformat()
    await db.execution_maps.update_one({"id": map_id}, {"$set": {
        "first_action_sent_to_queue": True,
        "queue_task_id": task.get("id"),
        "updated_at": now,
    }})

    return {
        "task_id": task.get("id"),
        "action": action_text,
        "worker": worker,
        "status": task.get("status"),
        "message": f"First action sent to {task.get('worker_name', worker)} queue",
    }



# ================== BULK RETROFIT ==================

@command_center_router.post("/bulk-retrofit")
async def bulk_retrofit_pages(user: dict = Depends(get_current_user)):
    """Re-place all previously placed pages through the updated formatter + hero fix."""
    from services.worker_queue import route_page_to_wp

    placed_pages = []
    async for doc in db.pages.find({"status": "placed"}, {"_id": 0, "id": 1, "page_name": 1, "wp_page_id": 1}):
        placed_pages.append(doc)

    if not placed_pages:
        return {"message": "No placed pages to retrofit", "count": 0}

    # Reset each page to Approved so WP worker can re-place
    tasks_created = 0
    for page in placed_pages:
        await db.pages.update_one({"id": page["id"]}, {"$set": {
            "status": "Approved",
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }})
        try:
            await route_page_to_wp(page["id"])
            tasks_created += 1
        except Exception as e:
            logger.warning(f"[Retrofit] Failed for {page.get('page_name')}: {e}")

    return {
        "message": f"Retrofit queued: {tasks_created} pages will be re-placed with updated formatting",
        "pages_queued": tasks_created,
        "total_placed": len(placed_pages),
    }


# ================== SCHEMA + LLMS.TXT ==================

class StoreInfoRequest(BaseModel):
    phone: str = ""
    email: str = ""
    street: str = ""
    zip: str = ""
    lat: str = ""
    lng: str = ""
    instagram: str = ""
    facebook: str = ""
    yelp: str = ""
    google_business: str = ""
    image: str = ""
    hours: list = []


@command_center_router.get("/schema/local-business")
async def get_local_business_schema(user: dict = Depends(get_current_user)):
    """Get LocalBusiness JSON-LD schema."""
    from services.schema_gen import generate_local_business_schema
    # Load saved store info if exists
    store_info = await db.store_settings.find_one({"type": "store_info"}, {"_id": 0})
    schema = generate_local_business_schema(store_info or {})
    return {"schema": schema, "json_ld": f'<script type="application/ld+json">\n{json.dumps(schema, indent=2)}\n</script>'}


@command_center_router.get("/schema/organization")
async def get_organization_schema(user: dict = Depends(get_current_user)):
    """Get Organization JSON-LD schema."""
    from services.schema_gen import generate_organization_schema
    schema = generate_organization_schema()
    return {"schema": schema, "json_ld": f'<script type="application/ld+json">\n{json.dumps(schema, indent=2)}\n</script>'}


@command_center_router.get("/schema/faq")
async def get_faq_schema(user: dict = Depends(get_current_user)):
    """Get FAQ JSON-LD schema."""
    from services.schema_gen import generate_faq_schema, DEFAULT_FAQS
    # Use default FAQs + any custom ones
    custom_faqs = []
    async for doc in db.store_faqs.find({}, {"_id": 0}):
        custom_faqs.append(doc)
    faqs = custom_faqs if custom_faqs else DEFAULT_FAQS
    schema = generate_faq_schema(faqs)
    return {"schema": schema, "json_ld": f'<script type="application/ld+json">\n{json.dumps(schema, indent=2)}\n</script>', "faq_count": len(faqs)}


@command_center_router.get("/schema/all")
async def get_all_schemas(user: dict = Depends(get_current_user)):
    """Get all schemas bundled together for easy placement."""
    from services.schema_gen import generate_local_business_schema, generate_organization_schema, generate_faq_schema, DEFAULT_FAQS
    import json as json_mod

    store_info = await db.store_settings.find_one({"type": "store_info"}, {"_id": 0}) or {}
    local_biz = generate_local_business_schema(store_info)
    org = generate_organization_schema()

    custom_faqs = []
    async for doc in db.store_faqs.find({}, {"_id": 0}):
        custom_faqs.append(doc)
    faqs = custom_faqs if custom_faqs else DEFAULT_FAQS
    faq_schema = generate_faq_schema(faqs)

    all_schemas = [local_biz, org, faq_schema]
    combined_json_ld = "\n".join([
        f'<script type="application/ld+json">\n{json_mod.dumps(s, indent=2)}\n</script>'
        for s in all_schemas if s
    ])

    return {
        "schemas": {
            "local_business": local_biz,
            "organization": org,
            "faq": faq_schema,
        },
        "combined_json_ld": combined_json_ld,
        "placement_instructions": "Add this code block to your WordPress theme's header.php or use a plugin like 'Insert Headers and Footers' to paste it site-wide. Place before </head>.",
    }


@command_center_router.get("/llms-txt")
async def get_llms_txt(user: dict = Depends(get_current_user)):
    """Get the llms.txt file content."""
    from services.schema_gen import generate_llms_txt
    content = generate_llms_txt()
    return {
        "content": content,
        "placement_instructions": "Upload this as /llms.txt at your domain root (https://temporarysatisfaction.com/llms.txt). In WordPress, create a page with slug 'llms.txt' or use a file manager plugin to place it at the root.",
        "filename": "llms.txt",
    }


@command_center_router.put("/store-info")
async def update_store_info(request: StoreInfoRequest, user: dict = Depends(get_current_user)):
    """Save store info for schema generation."""
    data = request.dict(exclude_unset=True)
    data["type"] = "store_info"
    data["updated_at"] = datetime.now(timezone.utc).isoformat()
    await db.store_settings.update_one({"type": "store_info"}, {"$set": data}, upsert=True)
    return {"message": "Store info updated", "data": data}


# ================== REVIEW REQUEST SYSTEM ==================

@command_center_router.get("/review-system")
async def get_review_system(user: dict = Depends(get_current_user)):
    """Get the complete review request system pack."""
    from services.review_system import generate_review_request_pack
    return generate_review_request_pack()



# ================== MENU / NAVIGATION ==================

@command_center_router.get("/menu-map")
async def get_menu_map(user: dict = Depends(get_current_user)):
    """Get the full menu/navigation map with page assignments and link suggestions."""
    from services.menu_mapper import generate_menu_map


# ================== DEPLOYMENT GUIDE ==================

@command_center_router.get("/deployment-guide")
async def get_deployment_guide(user: dict = Depends(get_current_user)):
    """Get the complete deployment guide — schema, llms.txt, and menu implementation."""
    from services.schema_gen import generate_local_business_schema, generate_organization_schema, generate_faq_schema, DEFAULT_FAQS, generate_llms_txt
    from services.menu_mapper import generate_menu_map
    import json as json_mod

    store_info = await db.store_settings.find_one({"type": "store_info"}, {"_id": 0}) or {}
    local_biz = generate_local_business_schema(store_info)
    org = generate_organization_schema()
    faq_schema = generate_faq_schema(DEFAULT_FAQS)

    combined_schema = f"""<!-- TS OPS Schema Pack - Generated {datetime.now(timezone.utc).strftime('%Y-%m-%d')} -->
<script type="application/ld+json">
{json_mod.dumps(local_biz, indent=2)}
</script>
<script type="application/ld+json">
{json_mod.dumps(org, indent=2)}
</script>
<script type="application/ld+json">
{json_mod.dumps(faq_schema, indent=2)}
</script>"""

    llms_content = generate_llms_txt()
    menu_map = await generate_menu_map()

    # Build clean menu implementation text
    menu_instructions = []
    for bucket in menu_map["menu"]["main_nav"]["buckets"]:
        if bucket["pages"]:
            items = [f"    - {p['page_name']} → /{p['slug']}" for p in bucket["pages"]]
            menu_instructions.append(f"  {bucket['label']}:\n" + "\n".join(items))

    footer_instructions = []
    for bucket in menu_map["menu"]["footer"]["buckets"]:
        if bucket["pages"]:
            items = [f"    - {p['page_name']} → /{p['slug']}" for p in bucket["pages"]]
            footer_instructions.append(f"  {bucket['label']}:\n" + "\n".join(items))

    return {
        "schema": {
            "code": combined_schema,
            "instructions": [
                "1. Go to WordPress Admin → Appearance → Theme Editor (or use 'Insert Headers and Footers' plugin)",
                "2. If using a plugin: paste the entire code block into the 'Scripts in Header' section",
                "3. If editing theme: paste into header.php before the closing </head> tag",
                "4. If using Flatsome: go to Theme Options → Advanced → Custom Head Scripts",
                "5. Save/publish",
                "6. Verify at: https://search.google.com/test/rich-results (paste any page URL)",
            ],
        },
        "llms_txt": {
            "content": llms_content,
            "filename": "llms.txt",
            "instructions": [
                "1. This file must be placed at the DOMAIN ROOT: https://temporarysatisfaction.com/llms.txt",
                "2. Option A (cPanel/FTP): Upload the file to public_html/ folder as 'llms.txt'",
                "3. Option B (File Manager): Use your hosting file manager to create 'llms.txt' in the root",
                "4. Option C (WP Plugin): Use 'Create Text Files' or 'LLMs.txt' plugin if available",
                "5. Do NOT create this as a WordPress page — it must be a real .txt file at the root",
                "6. Verify by visiting: https://temporarysatisfaction.com/llms.txt",
            ],
        },
        "menu": {
            "main_nav_structure": "\n".join(menu_instructions),
            "footer_structure": "\n".join(footer_instructions),
            "hidden_pages": [p["page_name"] for p in menu_map["menu"]["hidden_utility"]["pages"]],
            "instructions": [
                "1. Go to WordPress Admin → Appearance → Menus",
                "2. Select 'Main Shop Menu' (the active primary menu)",
                "3. Add new pages to the correct parent items using the structure below",
                "4. Use 'Pages' panel on left to find and add each page",
                "5. Drag items to create parent/child (dropdown) relationships",
                "6. For footer: select the footer menu and add support/about pages there",
                "7. Save Menu after each section",
                "8. Do NOT remove existing menu items unless you're sure they're obsolete",
            ],
            "link_suggestions": menu_map.get("link_suggestions", []),
        },
    }

    return await generate_menu_map()



# ================== MENU MAPPER V2 ==================

@command_center_router.get("/menu-mapper")
async def get_menu_mapper(user: dict = Depends(get_current_user)):
    """Get the full Menu Mapper v1 — map, queue, approval, instructions."""
    from services.menu_mapper_v2 import generate_full_menu_map
    return await generate_full_menu_map()


@command_center_router.post("/menu-mapper/approve/{item_id}")
async def approve_menu_item(item_id: str, user: dict = Depends(get_current_user)):
    """Approve a menu item for WordPress implementation."""
    result = await db.menu_map.update_one({"id": item_id}, {"$set": {"approved": True}})
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Menu item not found")
    return {"message": "Menu item approved", "item_id": item_id}


@command_center_router.post("/menu-mapper/approve-all-ready")
async def approve_all_ready(user: dict = Depends(get_current_user)):
    """Approve all existing_page items that are public."""
    result = await db.menu_map.update_many(
        {"status": "existing_page", "is_public": True},
        {"$set": {"approved": True}}
    )
    return {"approved_count": result.modified_count}


@command_center_router.get("/menu-mapper/wp-instructions")
async def get_wp_menu_instructions(user: dict = Depends(get_current_user)):
    """Get WordPress build instructions for approved items only."""
    from services.menu_mapper_v2 import _generate_wp_instructions, MENU_FAMILIES
    items = []
    async for doc in db.menu_map.find({"approved": True}, {"_id": 0}):
        items.append(doc)
    instructions = _generate_wp_instructions(items)
    return {"instructions": instructions, "approved_count": len(items)}



# ================== PAGE UPDATE WORKFLOW ==================

class PageUpdateRequest(BaseModel):
    page_id: str
    update_instructions: str = ""
    new_section_content: str = ""
    insert_after: str = ""
    insert_before: str = ""


@command_center_router.post("/page-update")
async def create_page_update_task(request: PageUpdateRequest, user: dict = Depends(get_current_user)):
    """Create a page update task that routes through Jenny → Rene → WP Placement."""
    from services.worker_queue import create_worker_task

    page = await db.pages.find_one({"id": request.page_id}, {"_id": 0})
    if not page:
        raise HTTPException(status_code=404, detail="Page not found")

    if not request.update_instructions and not request.new_section_content:
        raise HTTPException(status_code=400, detail="Provide update_instructions or new_section_content")

    wp_page_id = page.get("wp_page_id", "")
    if not wp_page_id:
        raise HTTPException(status_code=400, detail=f"Page '{page.get('page_name')}' has no WordPress page ID — place it first")

    context = {
        "page_id": request.page_id,
        "wp_page_id": wp_page_id,
        "page_name": page.get("page_name", ""),
        "update_instructions": request.update_instructions,
        "new_section_content": request.new_section_content,
        "insert_after": request.insert_after,
        "insert_before": request.insert_before,
    }

    # Create Jenny task to draft the content (auto-executes)
    task = await create_worker_task(
        source_module="page_ops",
        source_item_id=request.page_id,
        worker="jenny",
        task_type="wp_content_draft",
        context=context,
    )

    return {
        "message": f"Page update task created for '{page.get('page_name')}'",
        "task_id": task.get("id"),
        "status": task.get("status"),
        "chain": "Jenny (draft) → Rene (QA) → WP Placement (update)",
        "wp_page_id": wp_page_id,
    }
