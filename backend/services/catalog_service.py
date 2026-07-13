import csv
import io
import json
from rapidfuzz import fuzz
from fastapi import HTTPException
from emergentintegrations.llm.chat import LlmChat, UserMessage

from database import EMERGENT_LLM_KEY, PAGE_GENERATION_MODEL, logger
from services.brand_voice import BRAND_VOICE


async def normalize_catalog_item(item: dict, taxonomy: list) -> dict:
    category_list = ", ".join([c["name"] for c in taxonomy]) if taxonomy else "Uncategorized"

    system_message = f"""You are a product catalog normalization specialist for Temporary Satisfaction — an adult wellness brand.
Motto: "{BRAND_VOICE['motto']}"
Tone: Caring, tasteful, confidence-building. Never crude.

Given a raw product record, normalize it into clean, consistent, site-ready fields.

Available categories: {category_list}

Return a JSON object (no markdown fences):
{{
    "title": "clean, professional product title (max 120 chars, remove store noise/emojis/ALL-CAPS)",
    "brand": "brand name if identifiable, or 'Temporary Satisfaction' for unbranded",
    "short_description": "1-2 sentence product description (max 300 chars), warm and tasteful",
    "description": "detailed product description (3-5 sentences), brand-aligned",
    "tags": ["tag1", "tag2", "tag3"],
    "attributes": {{"material": "...", "type": "..."}},
    "category_suggestion": {{
        "name": "best matching category from the list",
        "confidence": 0.85,
        "rationale": "short reason"
    }},
    "variant_hint": {{
        "is_variant": true/false,
        "variant_attributes": ["size", "color"],
        "grouping_rationale": "short reason or null"
    }}
}}"""

    raw_info = []
    for field in ["title", "source_title", "clean_title", "short_description", "description", "long_description"]:
        if item.get(field):
            raw_info.append(f"{field}: {item[field]}")
    for field in ["color", "size", "style", "brand", "sku", "category"]:
        if item.get(field):
            raw_info.append(f"{field}: {item[field]}")

    user_prompt = f"""Normalize this product record:

{chr(10).join(raw_info) if raw_info else 'No details available'}

Price: {item.get('regular_price') or item.get('suggested_price') or item.get('unit_cost') or 'Unknown'}

Generate clean, brand-aligned normalized fields."""

    try:
        chat = LlmChat(
            api_key=EMERGENT_LLM_KEY,
            session_id=f"cat-norm-{item.get('id', 'new')[:20]}",
            system_message=system_message
        )
        chat.with_model('openai', PAGE_GENERATION_MODEL)
        response = await chat.send_message(UserMessage(text=user_prompt))

        clean = response.strip()
        if clean.startswith('```'):
            clean = clean.split('\n', 1)[1]
            clean = clean.rsplit('```', 1)[0]

        result = json.loads(clean)
        return result
    except json.JSONDecodeError:
        logger.error("LLM returned non-JSON for catalog normalization")
        raise HTTPException(status_code=500, detail="Normalization returned invalid format. Try again.")
    except Exception as e:
        logger.error(f"Catalog normalization error: {e}")
        raise HTTPException(status_code=500, detail=f"Normalization failed: {str(e)}")


def find_duplicate_candidates(item: dict, all_items: list, threshold: float = 60.0) -> list:
    candidates = []
    item_title = (item.get("title") or "").lower().strip()
    item_sku = (item.get("sku") or "").lower().strip()
    item_id = item.get("id")

    if not item_title:
        return []

    for other in all_items:
        if other.get("id") == item_id:
            continue

        other_title = (other.get("title") or "").lower().strip()
        other_sku = (other.get("sku") or "").lower().strip()
        score = 0.0
        signals = {}

        if item_sku and other_sku and item_sku == other_sku:
            score = max(score, 0.9)
            signals["sku_match"] = True

        if other_title:
            title_sim = fuzz.token_set_ratio(item_title, other_title) / 100.0
            if title_sim > threshold / 100.0:
                score = max(score, title_sim)
                signals["title_similarity"] = round(title_sim, 3)

        item_brand = (item.get("brand") or "").lower().strip()
        other_brand = (other.get("brand") or "").lower().strip()
        if item_brand and other_brand and item_brand == other_brand:
            signals["brand_match"] = True
            score = min(score + 0.05, 1.0)

        if score >= threshold / 100.0:
            candidates.append({
                "other_id": other["id"],
                "other_title": other.get("title", ""),
                "score": round(score, 3),
                "signals": signals,
            })

    candidates.sort(key=lambda x: x["score"], reverse=True)
    return candidates[:10]


def build_woo_csv(items: list, categories: list) -> str:
    cat_map = {c["id"]: c["name"] for c in categories}
    output = io.StringIO()
    fields = [
        "Type", "SKU", "Name", "Published", "Short description",
        "Description", "Regular price", "Sale price", "Categories",
        "Tags", "Images", "Attribute 1 name", "Attribute 1 value(s)",
    ]
    writer = csv.DictWriter(output, fieldnames=fields)
    writer.writeheader()
    for item in items:
        cat_name = cat_map.get(item.get("category_id"), "")
        secondary = [cat_map.get(c, "") for c in (item.get("secondary_category_ids") or []) if c in cat_map]
        all_cats = ", ".join(filter(None, [cat_name] + secondary))
        tags = "; ".join(item.get("tags") or [])
        images = ", ".join(item.get("image_urls") or [])
        attrs = item.get("attributes") or {}
        attr_name = list(attrs.keys())[0] if attrs else ""
        attr_val = attrs.get(attr_name, "") if attr_name else ""

        writer.writerow({
            "Type": "simple",
            "SKU": item.get("sku", ""),
            "Name": item.get("title", ""),
            "Published": 1 if item.get("status") == "Exported" else 0,
            "Short description": item.get("short_description", ""),
            "Description": item.get("description", ""),
            "Regular price": item.get("regular_price", ""),
            "Sale price": item.get("sale_price", ""),
            "Categories": all_cats,
            "Tags": tags,
            "Images": images,
            "Attribute 1 name": attr_name,
            "Attribute 1 value(s)": attr_val,
        })
    output.seek(0)
    return output.getvalue()
