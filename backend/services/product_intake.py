import json
import math
from rapidfuzz import fuzz
from fastapi import HTTPException
from emergentintegrations.llm.chat import LlmChat, UserMessage

from database import EMERGENT_LLM_KEY, PAGE_GENERATION_MODEL, db, logger
from services.brand_voice import BRAND_VOICE
from models import DEFAULT_TAXONOMY, DRAFT_ITEM_REQUIRED_FIELDS


async def extract_items_from_text(text: str, source_store: str = "") -> list:
    system_message = """You are an expert at extracting product data from order confirmations, cart summaries, and shopping receipts.

Extract ALL individual items from the provided text. For each item, return a JSON array where each element has:
{
    "source_title": "exact product name/title as shown",
    "color": "color if mentioned, or null",
    "size": "size if mentioned, or null",
    "style": "style/variant if mentioned, or null",
    "quantity": integer (default 1 if not clear),
    "unit_cost": number (price per unit, or null if unclear),
    "currency": "USD" or detected currency code,
    "source_url": "product URL if present, or null",
    "extraction_evidence": "the exact text snippet this item was extracted from"
}

Rules:
- Extract EVERY distinct item, even if info is partial
- If quantity is listed as a total for multiple variants, split into separate items
- Prices should be numeric (no $ signs in the value)
- If currency is ambiguous, default to USD
- Return ONLY a valid JSON array, no markdown fences, no commentary"""

    user_prompt = f"""Extract all product items from this order/cart text:

Source Store: {source_store or 'Unknown'}

---
{text}
---

Return a JSON array of extracted items."""

    try:
        chat = LlmChat(
            api_key=EMERGENT_LLM_KEY,
            session_id=f"intake-extract-{hash(text[:50])}",
            system_message=system_message
        )
        chat.with_model('openai', PAGE_GENERATION_MODEL)
        response = await chat.send_message(UserMessage(text=user_prompt))

        clean = response.strip()
        if clean.startswith('```'):
            clean = clean.split('\n', 1)[1]
            clean = clean.rsplit('```', 1)[0]

        items = json.loads(clean)
        if not isinstance(items, list):
            items = [items]
        return items
    except json.JSONDecodeError:
        logger.error("LLM returned non-JSON for text extraction")
        raise HTTPException(status_code=500, detail="Extraction returned invalid format. Try again or add items manually.")
    except Exception as e:
        logger.error(f"Text extraction error: {e}")
        raise HTTPException(status_code=500, detail=f"Extraction failed: {str(e)}")


async def generate_listing_content(item: dict, taxonomy: list = None) -> dict:
    if taxonomy is None:
        taxonomy = DEFAULT_TAXONOMY

    brand_context = f"""Brand: Temporary Satisfaction
Motto: "{BRAND_VOICE['motto']}"
Tone: {', '.join(BRAND_VOICE['emotional_core'][:5])}
Principles: {'; '.join(BRAND_VOICE['copy_principles'][:4])}
Avoid: {', '.join(BRAND_VOICE['brand_should_NOT_feel'][:4])}"""

    system_message = f"""{brand_context}

You are generating product listing content for Temporary Satisfaction's internal product intake system.

Given a raw product item, generate clean, brand-aligned listing content.

Available categories: {', '.join(taxonomy)}

Return a JSON object (no markdown fences):
{{
    "clean_title": "cleaned, brand-appropriate product title (remove store noise, fix capitalization)",
    "short_description": "1-3 sentence product description, warm and tasteful",
    "long_description": "detailed description with key features, materials if known, use cases. 3-6 sentences. Can include bullet points.",
    "category_suggestions": ["top category match", "second match", "third match"],
    "tag_suggestions": ["tag1", "tag2", "tag3", "tag4", "tag5"],
    "attribute_suggestions": {{
        "material": "material if identifiable from title/context, or null",
        "color": "color if identifiable, or null",
        "size": "size if identifiable, or null",
        "style": "style/variant if identifiable, or null",
        "type": "product sub-type if clear, or null"
    }},
    "confidence": {{
        "score": 0.0-1.0,
        "title_confidence": "high/medium/low",
        "category_confidence": "high/medium/low",
        "description_confidence": "high/medium/low",
        "reason": "brief explanation if confidence is below 0.7"
    }}
}}

Confidence scoring rules:
- high (0.8-1.0): clear product type, obvious category, enough detail to write good copy
- medium (0.5-0.79): recognizable product but ambiguous category or missing context
- low (0.0-0.49): vague title, unclear product type, or not enough info to generate useful content
- If the title is garbled, too generic, or in another language, score low and explain why

Rules:
- Titles should be clear, professional, and brand-appropriate
- Descriptions should be warm, confident, and never crude
- Categories must come from the provided list
- Tags should be specific and useful for filtering
- Never include explicit/graphic language
- Focus on benefits and experience, not just features"""

    source_title = item.get("source_title") or item.get("clean_title") or "Unknown Product"
    variant_info = []
    if item.get("color"):
        variant_info.append(f"Color: {item['color']}")
    if item.get("size"):
        variant_info.append(f"Size: {item['size']}")
    if item.get("style"):
        variant_info.append(f"Style: {item['style']}")

    user_prompt = f"""Generate listing content for this product:

Source Title: {source_title}
{chr(10).join(variant_info) if variant_info else 'No variant info'}
Source Store: {item.get('source_store', 'Unknown')}
Price Point: {item.get('unit_cost', 'Unknown')} {item.get('currency', 'USD')}

Generate brand-aligned listing content."""

    try:
        chat = LlmChat(
            api_key=EMERGENT_LLM_KEY,
            session_id=f"intake-gen-{item.get('id', 'new')}",
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
        logger.error("LLM returned non-JSON for listing generation")
        raise HTTPException(status_code=500, detail="Generation returned invalid format. Try again.")
    except Exception as e:
        logger.error(f"Listing generation error: {e}")
        raise HTTPException(status_code=500, detail=f"Generation failed: {str(e)}")


def calculate_suggested_price(
    unit_cost: float,
    settings: dict,
    category: str = None,
) -> float:
    multiplier = settings.get("default_markup_multiplier", 2.5)
    min_price = settings.get("min_price", 9.99)
    rounding_rule = settings.get("rounding_rule", "nearest_99")
    overrides = settings.get("category_overrides", {})

    if category and category in overrides:
        multiplier = overrides[category]

    raw_price = unit_cost * multiplier
    price = max(raw_price, min_price)

    if rounding_rule == "nearest_99":
        price = math.floor(price) + 0.99
    elif rounding_rule == "nearest_95":
        price = math.floor(price) + 0.95
    elif rounding_rule == "nearest_50":
        price = round(price * 2) / 2

    return round(price, 2)


def compute_missing_fields(item: dict) -> list:
    missing = []
    for field in DRAFT_ITEM_REQUIRED_FIELDS:
        val = item.get(field)
        if val is None or val == "" or val == 0:
            if field == "quantity" and val == 0:
                missing.append(field)
            elif field in ("unit_cost", "suggested_price") and val == 0:
                continue
            elif val is None or val == "":
                missing.append(field)
    if item.get("quantity") is not None and item["quantity"] < 1:
        if "quantity" not in missing:
            missing.append("quantity")
    return missing



def parse_csv_content(content: str, delimiter: str = None) -> list:
    """Parse CSV/TSV content into list of dicts. Auto-detects delimiter."""
    import csv as csv_mod
    import io

    if delimiter is None:
        first_line = content.split('\n')[0] if content else ''
        if '\t' in first_line:
            delimiter = '\t'
        else:
            delimiter = ','

    reader = csv_mod.DictReader(io.StringIO(content), delimiter=delimiter)
    items = []
    header_map = {
        'product': 'source_title', 'product name': 'source_title', 'item': 'source_title',
        'name': 'source_title', 'title': 'source_title', 'description': 'source_title',
        'price': 'unit_cost', 'cost': 'unit_cost', 'unit price': 'unit_cost',
        'amount': 'unit_cost', 'each': 'unit_cost',
        'qty': 'quantity', 'quantity': 'quantity', 'count': 'quantity',
        'color': 'color', 'colour': 'color',
        'size': 'size',
        'style': 'style', 'variant': 'style',
        'sku': 'sku', 'item number': 'sku', 'item #': 'sku',
        'url': 'source_url', 'link': 'source_url',
        'notes': 'notes', 'note': 'notes',
        'brand': 'brand',
        'material': 'material',
    }

    for row in reader:
        mapped = {}
        for col, val in row.items():
            if not col or not val:
                continue
            key = col.strip().lower()
            field = header_map.get(key, key)
            mapped[field] = val.strip()

        if not mapped.get('source_title'):
            for fallback in ['source_title', 'item', 'product', 'description']:
                if mapped.get(fallback):
                    mapped['source_title'] = mapped[fallback]
                    break

        if mapped.get('source_title') and mapped['source_title'].strip():
            # Parse numeric fields
            for nf in ['unit_cost', 'quantity']:
                if mapped.get(nf):
                    try:
                        cleaned = mapped[nf].replace('$', '').replace(',', '').strip()
                        mapped[nf] = float(cleaned) if nf == 'unit_cost' else int(float(cleaned))
                    except (ValueError, TypeError):
                        mapped[nf] = None

            items.append(mapped)

    return items


async def check_duplicate_flags(title: str, sku: str = "") -> list:
    """Check for duplicates against existing catalog and draft items."""
    flags = []
    clean_title = (title or "").lower().strip()
    clean_sku = (sku or "").lower().strip()

    if not clean_title:
        return flags

    # Check catalog items
    async for doc in db.catalog_items.find(
        {"status": {"$ne": "Archived"}},
        {"_id": 0, "id": 1, "title": 1, "sku": 1}
    ):
        cat_title = (doc.get("title") or "").lower().strip()
        cat_sku = (doc.get("sku") or "").lower().strip()

        if clean_sku and cat_sku and clean_sku == cat_sku:
            flags.append({"type": "catalog_sku_match", "match_title": doc.get("title"), "match_id": doc["id"]})
            continue

        if cat_title:
            score = fuzz.token_set_ratio(clean_title, cat_title)
            if score >= 75:
                flags.append({"type": "catalog_title_match", "match_title": doc.get("title"), "match_id": doc["id"], "score": score})

    # Check other draft items
    async for doc in db.draft_items.find(
        {},
        {"_id": 0, "id": 1, "source_title": 1, "clean_title": 1}
    ):
        other_title = (doc.get("clean_title") or doc.get("source_title") or "").lower().strip()
        if other_title and other_title != clean_title:
            score = fuzz.token_set_ratio(clean_title, other_title)
            if score >= 80:
                flags.append({"type": "draft_title_match", "match_title": doc.get("clean_title") or doc.get("source_title"), "match_id": doc["id"], "score": score})

    return flags[:5]


async def parse_cost_notes(cost_notes: str, items: list[dict]) -> list[dict]:
    """
    Parse founder cost notes and match them to items.
    Input: free-text notes like "this group was $25 and retails at $55"
           or "these are panties and cost $4.75 and retail at $12.99"
    Returns: list of {item_id, unit_cost, retail_price, note_matched, confidence}
    """
    if not cost_notes or not cost_notes.strip():
        return []

    # Build item summary for LLM context
    item_summaries = []
    for item in items[:100]:
        title = item.get("clean_title") or item.get("source_title", "")
        cat = item.get("category", "")
        cost = item.get("unit_cost")
        item_summaries.append(
            f'  id="{item["id"]}" title="{title[:80]}" category="{cat}" current_cost={cost}'
        )

    system_message = """You are a retail product cost note parser for an intake system.

The founder writes informal notes about product costs and retail prices. Your job is to:
1. Parse each note to extract: which items it refers to, the unit cost, and the retail/suggested price
2. Match notes to specific items by title keywords, category, or description

Examples of notes:
- "this group was $25 and retails at $55" → applies to all/most items
- "these are panties and cost $4.75 and retail at $12.99" → applies to items matching "panties"
- "lingerie set cost $8, sell for $24.99" → applies to items matching "lingerie set"
- "everything in this batch cost me $3-5 each, retail $9.99" → applies to all, use midpoint $4

Return a JSON array where each element is:
{
    "item_ids": ["id1", "id2"],
    "unit_cost": number or null,
    "retail_price": number or null,
    "note_text": "the original note text this came from",
    "match_reason": "why these items were matched",
    "confidence": "high" or "medium" or "low"
}

Rules:
- If a note says "this group" or "everything" or "all", match all items
- If a note mentions a category or product type, match by category/title keywords
- If cost is a range like "$3-5", use the midpoint
- Return ONLY a valid JSON array, no markdown fences"""

    items_text = "\n".join(item_summaries)
    user_prompt = f"""Parse these founder cost notes and match them to the items below.

COST NOTES:
{cost_notes}

ITEMS IN SESSION:
{items_text}"""

    chat = LlmChat(
        api_key=EMERGENT_LLM_KEY,
        session_id=f"intake-costnotes-{hash(cost_notes[:50])}",
        system_message=system_message,
    )
    chat.with_model('openai', PAGE_GENERATION_MODEL)
    response = await chat.send_message(UserMessage(text=user_prompt))

    try:
        text = response.strip()
        if text.startswith("```"):
            text = text.split("\n", 1)[1].rsplit("```", 1)[0]
        parsed = json.loads(text)
        if not isinstance(parsed, list):
            parsed = [parsed]
        return parsed
    except (json.JSONDecodeError, IndexError):
        logger.error(f"[Cost Notes] Failed to parse LLM response: {response[:200]}")
        return []
