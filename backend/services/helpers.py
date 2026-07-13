from database import db, logger
from datetime import datetime, timezone
import uuid
from models import PROMOTION_THRESHOLDS


# ================== ACTIVITY LOGGING ==================

async def log_activity(action: str, page_id: str = None, page_name: str = None, details: str = None):
    activity = {
        "id": str(uuid.uuid4()),
        "action": action,
        "page_id": page_id,
        "page_name": page_name,
        "details": details,
        "timestamp": datetime.now(timezone.utc).isoformat()
    }
    await db.activity_logs.insert_one(activity)


# ================== VERSION HISTORY ==================

async def create_version(
    page_id: str,
    content: str,
    action_type: str,
    model_used: str = None,
    tone_used: str = None,
    variant_used: str = None,
    tightened: bool = False,
    quality_score: int = None,
    classification: str = None,
    recommendations: list = None,
    score_notes: dict = None,
    make_current: bool = True
) -> dict:
    version_count = await db.page_versions.count_documents({"page_id": page_id})
    new_version_number = version_count + 1
    
    if make_current:
        await db.page_versions.update_many(
            {"page_id": page_id},
            {"$set": {"is_current": False}}
        )
    
    version = {
        "id": str(uuid.uuid4()),
        "page_id": page_id,
        "version_number": new_version_number,
        "generated_content": content,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "generation_action_type": action_type,
        "model_used": model_used,
        "tone_used": tone_used,
        "variant_used": variant_used,
        "tightened_applied": tightened,
        "quality_score": quality_score,
        "quality_classification": classification,
        "recommendations": recommendations,
        "score_notes": score_notes,
        "label": None,
        "is_current": make_current,
        "is_exemplar": False
    }
    
    await db.page_versions.insert_one(version)
    version.pop("_id", None)
    
    return version

async def get_page_versions(page_id: str) -> list:
    versions = await db.page_versions.find(
        {"page_id": page_id},
        {"_id": 0}
    ).sort("version_number", -1).to_list(100)
    return versions

async def get_version(version_id: str) -> dict:
    version = await db.page_versions.find_one({"id": version_id}, {"_id": 0})
    return version

async def get_current_version(page_id: str) -> dict:
    version = await db.page_versions.find_one(
        {"page_id": page_id, "is_current": True},
        {"_id": 0}
    )
    return version


# ================== PRIORITY ENGINE ==================

def calculate_priority_score(page: dict) -> int:
    score = 50
    
    family_weights = {
        "Core Hub": 30, "District": 25, "Trust": 20,
        "Guided Path": 15, "Category Support": 10,
        "Conversion": 20, "FAQ/Support": 10, "Media/Asset": 5
    }
    
    type_weights = {
        "Homepage": 30, "Landing": 25, "Collection": 20,
        "Service": 20, "Guide": 15, "Article": 10,
        "FAQ": 10, "Resource": 5
    }
    
    family = page.get('page_family', '')
    page_type = page.get('page_type', '')
    
    score += family_weights.get(family, 0)
    score += type_weights.get(page_type, 0)
    
    if page.get('parent_page'):
        score -= 5
    
    return min(score, 100)

def get_recommended_next_pages(pages: list, limit: int = 5) -> list:
    actionable = [p for p in pages if p.get('status') in ['Planned', 'Needs Rewrite', 'Needs Review']]
    status_order = {'Needs Rewrite': 0, 'Needs Review': 1, 'Planned': 2}
    actionable.sort(key=lambda x: (-x.get('priority_score', 50), status_order.get(x.get('status'), 3)))
    return actionable[:limit]


# ================== PROMOTION SIGNAL EVALUATION ==================

def evaluate_promotion_signals(version: dict, page: dict, score_notes: dict) -> dict:
    signals = []
    promotion_types = []
    quality_score = version.get("quality_score") or page.get("quality_score") or 0
    category_scores = score_notes.get("category_scores", {}) if score_notes else {}
    classification = score_notes.get("classification", "") if score_notes else ""
    brand_alignment = score_notes.get("brand_alignment", "") if score_notes else ""
    generic_flags = score_notes.get("generic_flags", []) if score_notes else ""
    edit_recs = score_notes.get("edit_recommendations", []) if score_notes else []
    label = version.get("label", "")

    if quality_score >= PROMOTION_THRESHOLDS["exemplar_min_score"]:
        signals.append({"signal": "high_overall_score", "value": quality_score,
            "explanation": f"Quality score of {quality_score} exceeds the gold standard threshold of {PROMOTION_THRESHOLDS['exemplar_min_score']}."})
    elif quality_score >= PROMOTION_THRESHOLDS["template_min_score"]:
        signals.append({"signal": "strong_score", "value": quality_score,
            "explanation": f"Quality score of {quality_score} is strong enough for structural reuse."})

    bvf = category_scores.get("brand_voice_fit", 0)
    if bvf >= 85:
        signals.append({"signal": "high_brand_fit", "value": bvf,
            "explanation": f"Brand voice fit of {bvf}/100 — this sounds distinctly like the brand."})

    ep = category_scores.get("emotional_presence", 0)
    if ep >= 85:
        signals.append({"signal": "high_emotional_presence", "value": ep,
            "explanation": f"Emotional presence of {ep}/100 — the reader genuinely feels something."})

    structure_signals = [
        category_scores.get("clarity_of_purpose", 0),
        category_scores.get("completeness", 0),
        category_scores.get("headline_strength", 0)
    ]
    avg_structure = sum(structure_signals) / len(structure_signals) if structure_signals else 0
    if avg_structure >= 82:
        signals.append({"signal": "strong_structure", "value": round(avg_structure),
            "explanation": f"Structural quality (clarity, completeness, headlines) averages {round(avg_structure)}/100 — reusable section flow."})

    if classification == "strong" and len(edit_recs) <= 2 and len(generic_flags) == 0:
        signals.append({"signal": "low_rewrite_need", "value": len(edit_recs),
            "explanation": f"Classified as 'strong' with only {len(edit_recs)} minor recommendations and zero generic flags."})

    if brand_alignment == "on-brand":
        signals.append({"signal": "on_brand", "value": brand_alignment,
            "explanation": "Scorer confirmed this is fully on-brand."})

    if label in ["Finalist", "Favorite", "Exemplar"]:
        signals.append({"signal": "notable_label", "value": label,
            "explanation": f"This version was labeled '{label}' — indicating founder recognition."})

    wwf = category_scores.get("warmth_without_fluff", 0)
    if wwf >= 85:
        signals.append({"signal": "warm_without_fluff", "value": wwf,
            "explanation": f"Warmth score of {wwf}/100 without being saccharine — a tonal asset."})

    uniq = category_scores.get("uniqueness", 0)
    if uniq >= 85:
        signals.append({"signal": "high_uniqueness", "value": uniq,
            "explanation": f"Uniqueness of {uniq}/100 — this doesn't sound like generic AI copy."})

    signal_names = [s["signal"] for s in signals]

    if len(signals) >= 4 and quality_score >= PROMOTION_THRESHOLDS["exemplar_min_score"]:
        promotion_types.append("exemplar")
    if ("strong_structure" in signal_names or avg_structure >= 78) and quality_score >= PROMOTION_THRESHOLDS["template_min_score"]:
        promotion_types.append("template")
    if ("high_emotional_presence" in signal_names or "warm_without_fluff" in signal_names or "high_brand_fit" in signal_names) and quality_score >= PROMOTION_THRESHOLDS["style_candidate_min_score"]:
        promotion_types.append("style-candidate")

    if not promotion_types:
        recommendation = None
    elif len(promotion_types) == 1:
        type_labels = {"exemplar": "Exemplar", "template": "House Template", "style-candidate": "Style Profile Candidate"}
        recommendation = f"This version shows strong signals for {type_labels[promotion_types[0]]} status."
    else:
        type_labels = {"exemplar": "Exemplar", "template": "House Template", "style-candidate": "Style Profile Candidate"}
        labels = [type_labels[t] for t in promotion_types]
        recommendation = f"This version shows strong signals for multiple promotion paths: {', '.join(labels)}."

    return {
        "signals": signals,
        "promotion_types": promotion_types,
        "recommendation_reason": recommendation,
        "signal_count": len(signals),
        "is_promotable": len(promotion_types) > 0
    }
