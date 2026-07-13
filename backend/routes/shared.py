from fastapi import APIRouter, Depends
from typing import List
from datetime import datetime, timezone
import uuid

from database import db, PAGE_GENERATION_MODEL, QUALITY_SCORING_MODEL, REWRITE_MODEL
from models import (
    SettingsResponse, SettingsUpdate, ActivityLog, StatsResponse,
)
from auth import get_current_user
from services.helpers import log_activity, calculate_priority_score
from services.brand_voice import BRAND_VOICE, PAGE_FAMILY_TEMPLATES


shared_router = APIRouter(prefix="/api")


# ================== BRAND VOICE ==================

@shared_router.get("/brand-voice")
async def get_brand_voice(user: dict = Depends(get_current_user)):
    return {
        "motto": BRAND_VOICE["motto"],
        "emotional_core": BRAND_VOICE["emotional_core"],
        "user_should_feel": BRAND_VOICE["user_should_feel"],
        "brand_should_feel": BRAND_VOICE["brand_should_feel"],
        "brand_should_NOT_feel": BRAND_VOICE["brand_should_NOT_feel"],
        "copy_principles": BRAND_VOICE["copy_principles"],
        "good_phrases": BRAND_VOICE["good_phrases"],
        "avoid_phrases": BRAND_VOICE["avoid_phrases"],
        "cta_style": BRAND_VOICE["cta_style"]
    }

@shared_router.get("/templates")
async def get_page_templates(user: dict = Depends(get_current_user)):
    return {
        family: {
            "system_additions": template.get("system_additions", "")[:500] + "...",
            "structure": template.get("structure", "")
        }
        for family, template in PAGE_FAMILY_TEMPLATES.items()
    }


# ================== SETTINGS ==================

@shared_router.get("/settings", response_model=SettingsResponse)
async def get_settings(user: dict = Depends(get_current_user)):
    settings = await db.settings.find_one({"id": "global"}, {"_id": 0})
    if not settings:
        settings = {
            "scoring_threshold_strong": 85,
            "scoring_threshold_usable": 70,
            "default_tone": "professional",
            "default_cta": "Learn More",
            "page_generation_model": PAGE_GENERATION_MODEL,
            "quality_scoring_model": QUALITY_SCORING_MODEL,
            "rewrite_model": REWRITE_MODEL
        }
    return settings

@shared_router.put("/settings", response_model=SettingsResponse)
async def update_settings(settings_update: SettingsUpdate, user: dict = Depends(get_current_user)):
    update_data = {k: v for k, v in settings_update.model_dump().items() if v is not None}
    await db.settings.update_one({"id": "global"}, {"$set": update_data}, upsert=True)
    settings = await db.settings.find_one({"id": "global"}, {"_id": 0})
    await log_activity("settings_updated", details=f"Updated: {list(update_data.keys())}")
    return settings


# ================== STATS & ACTIVITY ==================

@shared_router.get("/stats", response_model=StatsResponse)
async def get_stats(user: dict = Depends(get_current_user)):
    pages = await db.pages.find({}, {"_id": 0}).to_list(1000)
    total = len(pages)
    by_status = {}
    by_family = {}
    scores = []
    
    for page in pages:
        status = page.get("status", "Planned")
        family = page.get("page_family", "Unknown")
        by_status[status] = by_status.get(status, 0) + 1
        by_family[family] = by_family.get(family, 0) + 1
        if page.get("quality_score"):
            scores.append(page["quality_score"])
    
    return StatsResponse(
        total_pages=total, by_status=by_status, by_family=by_family,
        avg_quality_score=sum(scores) / len(scores) if scores else None,
        pages_ready_for_review=by_status.get("Needs Review", 0),
        pages_needing_rewrite=by_status.get("Needs Rewrite", 0)
    )

@shared_router.get("/activity", response_model=List[ActivityLog])
async def get_activity(limit: int = 20, user: dict = Depends(get_current_user)):
    activities = await db.activity_logs.find({}, {"_id": 0}).sort("timestamp", -1).to_list(limit)
    return activities


# ================== ECOSYSTEM DATA ==================

@shared_router.get("/ecosystem/families")
async def get_page_families(user: dict = Depends(get_current_user)):
    return {
        "families": [
            {"id": "core-hub", "name": "Core Hub", "description": "Main hub and homepage pages"},
            {"id": "district", "name": "District", "description": "District/pillar section pages"},
            {"id": "trust", "name": "Trust", "description": "Trust-building pages (about, testimonials, etc.)"},
            {"id": "guided-path", "name": "Guided Path", "description": "User journey and guide pages"},
            {"id": "category-support", "name": "Category Support", "description": "Category and support content"},
            {"id": "faq-support", "name": "FAQ/Support", "description": "FAQ and help pages"},
            {"id": "conversion", "name": "Conversion", "description": "Sales and conversion focused pages"},
            {"id": "media-asset", "name": "Media/Asset", "description": "Media, tools, and resource pages"}
        ]
    }

@shared_router.get("/ecosystem/types")
async def get_page_types(user: dict = Depends(get_current_user)):
    return {
        "types": [
            {"id": "homepage", "name": "Homepage"},
            {"id": "landing", "name": "Landing"},
            {"id": "collection", "name": "Collection"},
            {"id": "service", "name": "Service"},
            {"id": "guide", "name": "Guide"},
            {"id": "article", "name": "Article"},
            {"id": "faq", "name": "FAQ"},
            {"id": "resource", "name": "Resource"},
            {"id": "about", "name": "About"},
            {"id": "contact", "name": "Contact"}
        ]
    }

@shared_router.get("/ecosystem/statuses")
async def get_statuses(user: dict = Depends(get_current_user)):
    return {
        "statuses": [
            {"id": "planned", "name": "Planned", "color": "#8E8E93"},
            {"id": "generating", "name": "Generating", "color": "#FFCC00"},
            {"id": "draft-ready", "name": "Draft Ready", "color": "#FFCC00"},
            {"id": "needs-review", "name": "Needs Review", "color": "#FFCC00"},
            {"id": "needs-rewrite", "name": "Needs Rewrite", "color": "#FF3B30"},
            {"id": "approved", "name": "Approved", "color": "#34C759"},
            {"id": "deferred", "name": "Deferred", "color": "#8E8E93"}
        ]
    }


# ================== SEED DATA ==================

@shared_router.post("/seed")
async def seed_data(user: dict = Depends(get_current_user)):
    existing = await db.pages.count_documents({})
    if existing > 0:
        return {"message": f"Database already has {existing} pages. Skipping seed."}
    
    seed_pages = [
        {"page_name": "Temporary Satisfaction Home", "page_family": "Core Hub", "page_type": "Homepage", "district_or_pillar": "Main", "audience": "All visitors", "purpose": "Central entry point and ecosystem navigation", "CTA_type": "Explore"},
        {"page_name": "About Temporary Satisfaction", "page_family": "Trust", "page_type": "About", "district_or_pillar": "Brand", "audience": "New visitors", "purpose": "Build trust and explain brand story", "CTA_type": "Learn More"},
        {"page_name": "Wellness District", "page_family": "District", "page_type": "Landing", "district_or_pillar": "Wellness", "audience": "Health-conscious adults", "purpose": "Wellness products and resources hub", "CTA_type": "Shop Now"},
        {"page_name": "Pleasure District", "page_family": "District", "page_type": "Landing", "district_or_pillar": "Pleasure", "audience": "Adult consumers", "purpose": "Adult products collection hub", "CTA_type": "Explore"},
        {"page_name": "Education District", "page_family": "District", "page_type": "Landing", "district_or_pillar": "Education", "audience": "Learning seekers", "purpose": "Educational resources and guides", "CTA_type": "Start Learning"},
        {"page_name": "Community District", "page_family": "District", "page_type": "Landing", "district_or_pillar": "Community", "audience": "Community members", "purpose": "Community engagement and connection", "CTA_type": "Join"},
        {"page_name": "Privacy & Discretion Promise", "page_family": "Trust", "page_type": "About", "district_or_pillar": "Trust", "audience": "Concerned shoppers", "purpose": "Privacy commitment and policies", "CTA_type": "Learn More"},
        {"page_name": "Customer Stories", "page_family": "Trust", "page_type": "Collection", "district_or_pillar": "Trust", "audience": "Hesitant buyers", "purpose": "Social proof and testimonials", "CTA_type": "Read More"},
        {"page_name": "Expert Partnerships", "page_family": "Trust", "page_type": "About", "district_or_pillar": "Trust", "audience": "Quality seekers", "purpose": "Credibility through expert endorsements", "CTA_type": "Learn More"},
        {"page_name": "New Member Welcome", "page_family": "Conversion", "page_type": "Landing", "district_or_pillar": "Onboarding", "audience": "New visitors", "purpose": "Convert visitors to members", "CTA_type": "Sign Up"},
        {"page_name": "First Purchase Guide", "page_family": "Conversion", "page_type": "Guide", "district_or_pillar": "Sales", "audience": "First-time buyers", "purpose": "Guide to first purchase", "CTA_type": "Shop Now"},
        {"page_name": "VIP Membership", "page_family": "Conversion", "page_type": "Landing", "district_or_pillar": "Membership", "audience": "Loyal customers", "purpose": "Upsell to premium membership", "CTA_type": "Join VIP"},
        {"page_name": "Beginner's Journey", "page_family": "Guided Path", "page_type": "Guide", "district_or_pillar": "Education", "audience": "Newcomers", "purpose": "Onboard new users to ecosystem", "CTA_type": "Start Here"},
        {"page_name": "Product Discovery Quiz", "page_family": "Guided Path", "page_type": "Resource", "district_or_pillar": "Sales", "audience": "Undecided shoppers", "purpose": "Help find right products", "CTA_type": "Take Quiz"},
        {"page_name": "Wellness Path", "page_family": "Guided Path", "page_type": "Guide", "district_or_pillar": "Wellness", "audience": "Wellness seekers", "purpose": "Guided wellness journey", "CTA_type": "Begin"},
        {"page_name": "Toys Collection", "page_family": "Category Support", "page_type": "Collection", "district_or_pillar": "Pleasure", "audience": "Product browsers", "purpose": "Browse toys category", "CTA_type": "Shop"},
        {"page_name": "Wellness Products", "page_family": "Category Support", "page_type": "Collection", "district_or_pillar": "Wellness", "audience": "Health shoppers", "purpose": "Browse wellness items", "CTA_type": "Shop"},
        {"page_name": "Accessories Collection", "page_family": "Category Support", "page_type": "Collection", "district_or_pillar": "Pleasure", "audience": "Accessory seekers", "purpose": "Browse accessories", "CTA_type": "Shop"},
        {"page_name": "Gift Guide", "page_family": "Category Support", "page_type": "Guide", "district_or_pillar": "Sales", "audience": "Gift shoppers", "purpose": "Help find gifts", "CTA_type": "Find Gift"},
        {"page_name": "Shipping & Delivery FAQ", "page_family": "FAQ/Support", "page_type": "FAQ", "district_or_pillar": "Support", "audience": "Buyers", "purpose": "Answer shipping questions", "CTA_type": "Contact Us"},
        {"page_name": "Returns & Exchanges", "page_family": "FAQ/Support", "page_type": "FAQ", "district_or_pillar": "Support", "audience": "Post-purchase", "purpose": "Handle returns info", "CTA_type": "Start Return"},
        {"page_name": "Product Care Guide", "page_family": "FAQ/Support", "page_type": "Guide", "district_or_pillar": "Support", "audience": "Customers", "purpose": "Product maintenance info", "CTA_type": "Learn More"},
        {"page_name": "Contact Support", "page_family": "FAQ/Support", "page_type": "Contact", "district_or_pillar": "Support", "audience": "Anyone needing help", "purpose": "Contact support team", "CTA_type": "Get Help"},
        {"page_name": "Blog Hub", "page_family": "Media/Asset", "page_type": "Collection", "district_or_pillar": "Content", "audience": "Content consumers", "purpose": "Blog content hub", "CTA_type": "Read"},
        {"page_name": "Video Resources", "page_family": "Media/Asset", "page_type": "Collection", "district_or_pillar": "Content", "audience": "Visual learners", "purpose": "Video content library", "CTA_type": "Watch"},
    ]
    
    created_pages = []
    for page_data in seed_pages:
        page = {
            "id": str(uuid.uuid4()),
            "page_name": page_data["page_name"],
            "slug": page_data["page_name"].lower().replace(" ", "-").replace("&", "and").replace("'", ""),
            "page_family": page_data["page_family"],
            "district_or_pillar": page_data.get("district_or_pillar"),
            "page_type": page_data["page_type"],
            "audience": page_data.get("audience"),
            "purpose": page_data.get("purpose"),
            "CTA_type": page_data.get("CTA_type"),
            "keyword_or_theme": None,
            "parent_page": None,
            "priority_score": calculate_priority_score(page_data),
            "status": "Planned",
            "quality_score": None,
            "score_notes": None,
            "edit_recommendations": None,
            "generated_content": None,
            "generation_history": [],
            "review_notes": None,
            "notes": None,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "updated_at": datetime.now(timezone.utc).isoformat()
        }
        await db.pages.insert_one(page)
        created_pages.append(page["page_name"])
    
    await db.settings.update_one(
        {"id": "global"},
        {"$set": {
            "id": "global",
            "scoring_threshold_strong": 85,
            "scoring_threshold_usable": 70,
            "default_tone": "professional",
            "default_cta": "Learn More",
            "page_generation_model": PAGE_GENERATION_MODEL,
            "quality_scoring_model": QUALITY_SCORING_MODEL,
            "rewrite_model": REWRITE_MODEL
        }},
        upsert=True
    )
    
    await log_activity("seed_complete", details=f"Seeded {len(created_pages)} pages")
    return {"message": f"Seeded {len(created_pages)} pages", "pages": created_pages}
