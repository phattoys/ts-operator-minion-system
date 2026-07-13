"""
Field-to-Listing Service — Vision AI photo analysis, listing generation, destination packs.
Turns raw product photos + grouped pricing notes into listing-ready records.
"""
import json
import os
import re
import base64
from emergentintegrations.llm.chat import LlmChat, UserMessage, ImageContent
from database import EMERGENT_LLM_KEY, PAGE_GENERATION_MODEL, logger


UPLOAD_DIR = "/app/backend/uploads/field_listing"


def get_image_base64(image_path: str) -> str:
    """Read an image file and return base64-encoded string."""
    with open(image_path, "rb") as f:
        return base64.b64encode(f.read()).decode("utf-8")


async def analyze_photo(image_path: str, source_vendor: str = "", batch_notes: str = "") -> dict:
    """
    Use GPT-4o Vision to analyze a product photo.
    Returns structured product identification data.
    """
    b64 = get_image_base64(image_path)

    system_msg = """You are an expert product identifier for retail/resale. Analyze this product photo and extract:

Return a JSON object with:
{
  "product_type": "what this item is (e.g., 'Women's lace bodysuit', 'Men's graphic t-shirt', 'Store fixture - display rack')",
  "material": "visible material if identifiable, or null",
  "color": "primary color(s) visible",
  "condition": "new/like-new/good/fair based on visual assessment, or null if unclear",
  "notable_features": "any distinguishing features, patterns, branding visible",
  "confidence": float between 0 and 1 (how confident you are in the identification),
  "confidence_note": "brief explanation if confidence is low"
}

Rules:
- Be practical and concise, not flowery
- If the image is blurry or unclear, set confidence low and note it
- If you can see brand labels, include them
- Return ONLY valid JSON, no markdown fences"""

    context = f"Source/vendor: {source_vendor}" if source_vendor else ""
    if batch_notes:
        context += f"\nFounder notes: {batch_notes}"

    try:
        chat = LlmChat(
            api_key=EMERGENT_LLM_KEY,
            session_id=f"field-analyze-{hash(image_path)}",
            system_message=system_msg
        )
        chat.with_model('openai', 'gpt-4o')

        image_content = ImageContent(image_base64=b64)
        msg = UserMessage(
            text=f"Identify this product.{(' ' + context) if context else ''} Return JSON only.",
            file_contents=[image_content]
        )

        response = await chat.send_message(msg)
        clean = response.strip()
        if clean.startswith('```'):
            clean = clean.split('\n', 1)[1]
            clean = clean.rsplit('```', 1)[0]

        try:
            result = json.loads(clean, strict=False)
        except (json.JSONDecodeError, ValueError):
            match = re.search(r'\{[^{}]*\}', clean, re.DOTALL)
            if match:
                result = json.loads(match.group(), strict=False)
            else:
                raise ValueError(f"Could not parse JSON from response: {clean[:200]}")
        return result

    except Exception as e:
        logger.error(f"[Field Listing] Photo analysis failed: {e}")
        return {
            "product_type": "Unknown product",
            "material": None,
            "color": None,
            "condition": None,
            "notable_features": "",
            "confidence": 0.1,
            "confidence_note": f"Analysis failed: {str(e)[:100]}"
        }


async def generate_listing(item: dict, batch: dict) -> dict:
    """
    Generate listing content for a field item using GPT-5.2.
    Uses vision analysis + grouped notes as context.
    """
    vision = item.get("vision_analysis", {})
    product_type = vision.get("product_type", item.get("draft_title", "Unknown product"))
    material = vision.get("material", "")
    color = vision.get("color", "")
    features = vision.get("notable_features", "")
    condition = item.get("condition", "") or vision.get("condition", "")

    system_msg = """You are a practical retail listing writer. Generate concise, sell-ready product listings.

Return JSON:
{
  "draft_title": "clean, searchable product title (50-80 chars)",
  "short_description": "2-3 sentence sell description, practical not flowery",
  "category_suggestion": "single best category for this item",
  "tags": ["tag1", "tag2", "tag3"],
  "confidence": float 0-1
}

Rules:
- Titles should be search-friendly and descriptive
- Descriptions should highlight key features and value
- Be concise and practical, not marketing-fluffy
- If source info is weak, keep it simple and flag low confidence
- Return ONLY valid JSON"""

    context_parts = [f"Product: {product_type}"]
    if color:
        context_parts.append(f"Color: {color}")
    if material:
        context_parts.append(f"Material: {material}")
    if features:
        context_parts.append(f"Features: {features}")
    if condition:
        context_parts.append(f"Condition: {condition}")
    if batch.get("source_vendor"):
        context_parts.append(f"Source: {batch['source_vendor']}")
    if batch.get("grouped_category_note"):
        context_parts.append(f"Category hint: {batch['grouped_category_note']}")

    try:
        chat = LlmChat(
            api_key=EMERGENT_LLM_KEY,
            session_id=f"field-listing-{item.get('id', '')}",
            system_message=system_msg
        )
        chat.with_model('openai', PAGE_GENERATION_MODEL)

        msg = UserMessage(text="\n".join(context_parts) + "\n\nGenerate listing. Return JSON only.")
        response = await chat.send_message(msg)

        clean = response.strip()
        if clean.startswith('```'):
            clean = clean.split('\n', 1)[1]
            clean = clean.rsplit('```', 1)[0]

        try:
            return json.loads(clean, strict=False)
        except (json.JSONDecodeError, ValueError):
            match = re.search(r'\{[^{}]*\}', clean, re.DOTALL)
            if match:
                return json.loads(match.group(), strict=False)
            raise ValueError(f"Could not parse JSON from response: {clean[:200]}")

    except Exception as e:
        logger.error(f"[Field Listing] Listing generation failed for {item.get('id')}: {e}")
        return {
            "draft_title": product_type,
            "short_description": "",
            "category_suggestion": "",
            "tags": [],
            "confidence": 0.2,
        }


def parse_grouped_pricing(pricing_note: str) -> dict:
    """
    Parse a grouped pricing note into structured pricing rules.
    Examples: "These were $25 each, sell at $55", "price at $12.99"
    """
    result = {"unit_cost": None, "retail_price": None, "rule_type": "unknown", "raw_note": pricing_note}

    if not pricing_note:
        return result

    note = pricing_note.strip().lower()

    # Pattern: "were $X each, sell at $Y" or "cost $X, retail $Y"
    cost_retail = re.search(r'(?:were|cost|paid|bought)\s*\$?([\d.]+).*?(?:sell|retail|price|list)\s*(?:at|for)?\s*\$?([\d.]+)', note)
    if cost_retail:
        result["unit_cost"] = float(cost_retail.group(1))
        result["retail_price"] = float(cost_retail.group(2))
        result["rule_type"] = "cost_and_retail"
        return result

    # Pattern: "sell at $X" or "price at $X"
    retail_only = re.search(r'(?:sell|retail|price|list)\s*(?:at|for)?\s*\$?([\d.]+)', note)
    if retail_only:
        result["retail_price"] = float(retail_only.group(1))
        result["rule_type"] = "retail_only"
        return result

    # Pattern: "cost $X" or "$X each"
    cost_only = re.search(r'(?:cost|paid|were|bought)\s*\$?([\d.]+)', note)
    if not cost_only:
        cost_only = re.search(r'\$?([\d.]+)\s*each', note)
    if cost_only:
        result["unit_cost"] = float(cost_only.group(1))
        result["rule_type"] = "cost_only"
        return result

    # Pattern: "can be $X" or just "$X"
    any_price = re.search(r'\$?([\d.]+)', note)
    if any_price:
        result["retail_price"] = float(any_price.group(1))
        result["rule_type"] = "price_hint"
        return result

    return result


def generate_destination_pack(item: dict, destination: str, batch: dict) -> str:
    """Generate a formatted text pack for a specific destination."""
    title = item.get("draft_title", "Untitled")
    price = item.get("retail_price") or item.get("unit_cost") or ""
    price_str = f"${price:.2f}" if isinstance(price, (int, float)) and price else "Price TBD"
    desc = item.get("short_description", "")
    condition = item.get("condition", "")
    pickup_ship = item.get("pickup_shipping", "") or batch.get("pickup_shipping_note", "")
    category = item.get("category_suggestion", "")

    # Image references
    images = item.get("images", [])
    image_refs = ", ".join(img.get("original_name", img.get("filename", "")) for img in images) if images else "No images"

    if destination == "website":
        lines = [
            f"## {title}",
            f"**Price:** {price_str}",
            f"**Category:** {category}" if category else "",
            "",
            desc,
            "",
            f"*Condition: {condition}*" if condition else "",
            f"*{pickup_ship}*" if pickup_ship else "",
            "",
            f"Images: {image_refs}",
        ]
        return "\n".join(line for line in lines if line is not None).strip()

    elif destination == "offerup":
        lines = [
            f"TITLE: {title}",
            f"PRICE: {price_str}",
            f"CONDITION: {condition or 'New'}",
            "DESCRIPTION:",
            desc or f"{title} - great deal!",
            "",
            f"PICKUP/SHIPPING: {pickup_ship or 'Local pickup available'}",
            f"IMAGES: {image_refs}",
        ]
        return "\n".join(lines).strip()

    elif destination == "facebook":
        lines = [
            f"TITLE: {title}",
            f"PRICE: {price_str}",
            f"CONDITION: {condition or 'New'}",
            f"CATEGORY: {category}" if category else "",
            "DESCRIPTION:",
            desc or f"{title} available now!",
            "",
            f"AVAILABILITY: {pickup_ship or 'Message for details'}",
            f"IMAGES: {image_refs}",
        ]
        return "\n".join(line for line in lines if line).strip()

    return ""


def generate_website_page_pack(items: list[dict], batch: dict) -> str:
    """Generate a full website sale/closeout page pack from all items in a batch."""
    source = batch.get("source_vendor", "Mixed Source")
    lines = [
        f"# {source} — New Arrivals / Sale Items",
        "",
        f"*{len(items)} items available*",
        "",
    ]

    for i, item in enumerate(items):
        if item.get("status") == "skipped":
            continue
        title = item.get("draft_title", "Untitled")
        price = item.get("retail_price") or item.get("unit_cost") or ""
        price_str = f"${price:.2f}" if isinstance(price, (int, float)) and price else "Price TBD"
        desc = item.get("short_description", "")
        images = item.get("images", [])
        image_ref = images[0].get("original_name", "") if images else "No image"

        lines.append(f"### {i+1}. {title} — {price_str}")
        if desc:
            lines.append(desc)
        lines.append(f"*Image: {image_ref}*")
        lines.append("")

    pickup = batch.get("pickup_shipping_note", "")
    if pickup:
        lines.append(f"---\n*{pickup}*")

    return "\n".join(lines)


# ---- Post-Merge Title Refinement ----

async def refine_merged_title(image_paths: list[str], existing_analyses: list[dict] = None, batch: dict = None) -> dict:
    """
    Send multiple product images to Vision LLM and generate a specific,
    listing-quality title. Pulls color, pattern, cut/style, standout detail.
    Returns {refined_title, color, pattern, style, garment_type}.
    """
    if not image_paths:
        return {"refined_title": "", "error": "No images provided"}

    # Limit to 4 images max (diminishing returns beyond that)
    paths = [p for p in image_paths if os.path.exists(p)][:4]
    if not paths:
        return {"refined_title": "", "error": "No valid image files found"}

    # Build context from existing analyses
    context_hints = []
    if existing_analyses:
        for va in existing_analyses:
            if not va:
                continue
            if va.get("product_type"):
                context_hints.append(f"Previously identified as: {va['product_type']}")
            if va.get("color"):
                context_hints.append(f"Color noted: {va['color']}")
            if va.get("notable_features"):
                context_hints.append(f"Features: {va['notable_features']}")
    if batch and batch.get("grouped_category_note"):
        context_hints.append(f"Category hint: {batch['grouped_category_note']}")

    system_msg = """You are a product title specialist for retail/resale listings. You are given multiple photos of the SAME product (different angles). Generate a specific, search-friendly product title.

Your title MUST include visible details in this order of priority:
1. Primary color or color combination (e.g., "Red", "Black and White", "Pink Floral")
2. Pattern or print if visible (e.g., "Cartoon Print", "Leopard", "Striped", "Lace")
3. Cut, style, or neckline detail (e.g., "Halter", "Cut-Out", "V-Neck", "High-Waist")
4. Garment type (e.g., "Bikini Set", "Bodysuit", "Maxi Dress", "Crop Top")

Rules:
- Title should be 40-80 characters
- Be SPECIFIC — "Red Cartoon Print Halter Bikini Set" not "Women's Bikini"
- Do NOT use generic fillers like "Women's", "Ladies", "Stylish", "Beautiful"
- If you can see a brand label, include it
- If you can't identify a detail clearly, skip it rather than guess
- Return ONLY valid JSON, no markdown fences

Return JSON:
{
  "refined_title": "the specific product title",
  "color": "primary color(s)",
  "pattern": "pattern/print or null",
  "style": "cut/style detail or null",
  "garment_type": "garment type"
}"""

    try:
        chat = LlmChat(
            api_key=EMERGENT_LLM_KEY,
            session_id=f"field-refine-{hash(str(image_paths))}",
            system_message=system_msg
        )
        chat.with_model('openai', 'gpt-4o')

        image_contents = [ImageContent(image_base64=get_image_base64(p)) for p in paths]
        prompt_text = f"These are {len(paths)} photos of the same product from different angles. Generate a specific, listing-quality title."
        if context_hints:
            prompt_text += "\n\nContext:\n" + "\n".join(context_hints)
        prompt_text += "\n\nReturn JSON only."

        msg = UserMessage(text=prompt_text, file_contents=image_contents)
        response = await chat.send_message(msg)

        clean = response.strip()
        if clean.startswith('```'):
            clean = clean.split('\n', 1)[1]
            clean = clean.rsplit('```', 1)[0]

        # Fallback: regex-extract first JSON object if direct parse fails
        try:
            result = json.loads(clean, strict=False)
        except (json.JSONDecodeError, ValueError):
            match = re.search(r'\{[^{}]*\}', clean, re.DOTALL)
            if match:
                result = json.loads(match.group(), strict=False)
            else:
                logger.warning(f"[Field Listing] Could not parse refinement response: {clean[:200]}")
                return {"refined_title": "", "error": "Could not parse LLM response"}

        logger.info(f"[Field Listing] Refined title: {result.get('refined_title', '?')}")
        return result

    except Exception as e:
        logger.error(f"[Field Listing] Title refinement failed: {e}")
        return {"refined_title": "", "error": str(e)[:200]}


# ---- Multi-Photo Grouping Logic ----

def _normalize_for_grouping(text: str) -> str:
    """Normalize a string for grouping comparison."""
    t = text.lower().strip()
    t = re.sub(r"[^\w\s]", "", t)
    t = re.sub(r"\s+", " ", t)
    # Remove generic modifiers that vary across angles
    for word in ["front", "back", "side", "detail", "close", "closeup", "angle", "view"]:
        t = t.replace(word, "")
    return t.strip()


def _color_similarity(c1: str, c2: str) -> bool:
    """Check if two color descriptions are similar enough to be the same item."""
    if not c1 or not c2:
        return True  # If either is missing, don't disqualify
    n1 = c1.lower().strip()
    n2 = c2.lower().strip()
    if n1 == n2:
        return True
    # Check if one contains the other
    if n1 in n2 or n2 in n1:
        return True
    return False


def suggest_item_groups(items: list[dict]) -> list[dict]:
    """
    Analyze items and suggest groupings based on product type + color similarity.
    Returns list of suggested groups, each with item_ids and a confidence score.
    Conservative: only suggests, never auto-merges.
    """
    if len(items) < 2:
        return []

    # Build comparison data
    analyzed = []
    for item in items:
        vision = item.get("vision_analysis", {})
        analyzed.append({
            "id": item["id"],
            "norm_type": _normalize_for_grouping(vision.get("product_type", "") or item.get("draft_title", "")),
            "color": (vision.get("color") or "").lower().strip(),
            "product_type": vision.get("product_type", "") or item.get("draft_title", ""),
            "features": (vision.get("notable_features") or "").lower(),
            "already_grouped": len(item.get("images", [])) > 1,
        })

    # Skip items already merged (multi-image)
    candidates = [a for a in analyzed if not a["already_grouped"]]

    # Find potential groups
    used = set()
    groups = []

    for i, a in enumerate(candidates):
        if a["id"] in used:
            continue
        group_ids = [a["id"]]
        group_titles = [a["product_type"]]

        for j, b in enumerate(candidates):
            if j <= i or b["id"] in used:
                continue

            # Check product type similarity
            type_match = (
                a["norm_type"] == b["norm_type"]
                or (len(a["norm_type"]) > 5 and len(b["norm_type"]) > 5 and
                    (a["norm_type"] in b["norm_type"] or b["norm_type"] in a["norm_type"]))
            )

            if not type_match:
                continue

            # Check color similarity
            if not _color_similarity(a["color"], b["color"]):
                continue

            # This pair is likely the same item
            group_ids.append(b["id"])
            group_titles.append(b["product_type"])
            used.add(b["id"])

        if len(group_ids) > 1:
            used.add(a["id"])
            # Confidence based on how similar the titles are
            conf = 0.8 if all(t == group_titles[0] for t in group_titles) else 0.6
            groups.append({
                "item_ids": group_ids,
                "suggested_title": group_titles[0],
                "confidence": conf,
                "reason": f"Similar product type and color across {len(group_ids)} photos",
            })

    return groups
