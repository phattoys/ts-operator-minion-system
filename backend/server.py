from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from database import client, db, logger
from auth import auth_router
from routes.page_ops import page_ops_router
from routes.shared import shared_router
from routes.spec_writer import spec_writer_router
from routes.batch_ops import batch_router
from routes.lead_magnet import lead_magnet_router
from routes.product_intake import intake_router
from routes.dashboard import dashboard_router
from routes.comms import comms_router
from routes.catalog import catalog_router
from routes.wp_placement import wp_placement_router
from routes.field_listing import field_listing_router
from routes.spine import spine_router
from routes.worker_queue import worker_queue_router
from routes.command_center import command_center_router

app = FastAPI(title="TS Operator Minion", version="2.8")

# Include all routers
app.include_router(auth_router)
app.include_router(page_ops_router)
app.include_router(spec_writer_router)
app.include_router(batch_router)
app.include_router(lead_magnet_router)
app.include_router(intake_router)
app.include_router(dashboard_router)
app.include_router(comms_router)
app.include_router(catalog_router)
app.include_router(wp_placement_router)
app.include_router(field_listing_router)
app.include_router(spine_router)
app.include_router(worker_queue_router)
app.include_router(command_center_router)
app.include_router(shared_router)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Root endpoint
@app.get("/")
async def root():
    return {
        "name": "TS Operator Minion",
        "version": "2.0",
        "modules": ["Page Ops Minion", "Spec Writer Minion", "Lead Magnet Minion", "Product Intake Minion", "Operator Dashboard", "Customer Comms Minion", "Catalog Minion", "WP Page Placement Minion"],
        "status": "operational",
        "architecture": "modular"
    }

@app.on_event("startup")
async def startup_event():
    try:
        await client.admin.command('ping')
        logger.info("Connected to MongoDB successfully")
        
        # Ensure indexes
        await db.pages.create_index("id", unique=True)
        await db.pages.create_index("status")
        await db.pages.create_index("page_family")
        await db.page_versions.create_index("id", unique=True)
        await db.page_versions.create_index("page_id")
        await db.activity_logs.create_index("timestamp")
        await db.exemplars.create_index("id", unique=True)
        await db.exemplars.create_index("page_family")
        await db.house_templates.create_index("id", unique=True)
        await db.house_templates.create_index("page_family")
        await db.style_profiles.create_index("id", unique=True)
        await db.promotion_candidates.create_index("id", unique=True)
        await db.promotion_candidates.create_index("status")
        await db.specs.create_index("id", unique=True)
        await db.specs.create_index("status")
        await db.specs.create_index("spec_type")
        await db.spec_versions.create_index("id", unique=True)
        await db.spec_versions.create_index("spec_id")
        await db.batch_jobs.create_index("id", unique=True)
        await db.batch_jobs.create_index("state")
        await db.batch_job_items.create_index("id", unique=True)
        await db.batch_job_items.create_index("batch_job_id")
        await db.lead_magnets.create_index("id", unique=True)
        await db.lead_magnets.create_index("public_id", unique=True)
        await db.lead_magnets.create_index("status")
        await db.lead_magnet_versions.create_index("id", unique=True)
        await db.lead_magnet_versions.create_index("lead_magnet_id")
        await db.intake_sessions.create_index("id", unique=True)
        await db.draft_items.create_index("id", unique=True)
        await db.draft_items.create_index("session_id")
        await db.draft_items.create_index("status")
        await db.comms_drafts.create_index("id", unique=True)
        await db.comms_drafts.create_index("scenario_key")
        await db.comms_drafts.create_index("created_at")
        
        await db.catalog_items.create_index("id", unique=True)
        await db.catalog_items.create_index("status")
        await db.catalog_items.create_index("category_id")
        await db.catalog_items.create_index("source_intake_id")
        await db.catalog_categories.create_index("id", unique=True)
        await db.catalog_categories.create_index("name")
        await db.catalog_variant_groups.create_index("id", unique=True)
        
        await db.wp_placements.create_index("id", unique=True)
        await db.wp_placements.create_index("created_at")
        await db.wp_mock_pages.create_index("id", unique=True)
        await db.wp_settings.create_index("default_status")

        # Worker Queue indexes
        await db.worker_tasks.create_index("id", unique=True)
        await db.worker_tasks.create_index("status")
        await db.worker_tasks.create_index("worker")
        await db.worker_tasks.create_index("source_item_id")
        await db.worker_tasks.create_index("source_batch_id")
        await db.worker_tasks.create_index([("worker", 1), ("status", 1)])
        await db.worker_activity_log.create_index("id", unique=True)
        await db.worker_activity_log.create_index("task_id")
        await db.worker_activity_log.create_index("timestamp")
        
        logger.info("Database indexes ensured")
    except Exception as e:
        logger.error(f"Database connection failed: {e}")

@app.on_event("shutdown")
async def shutdown_db_client():
    client.close()
