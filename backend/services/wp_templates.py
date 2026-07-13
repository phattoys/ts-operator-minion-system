"""
WordPress Page Templates — Flatsome/UX Builder section mapping.
3 locked templates with formalized routing rules.

Template selection is automatic via keyword inference on page_type, title, and content.
Each template defines required + optional sections mapped to reusable UX Blocks.
"""

# ================== REUSABLE UX BLOCK DEFINITIONS ==================

UX_BLOCKS = {
    "hero_block": {"label": "Hero Block", "flatsome": "[section] > [row] > [col] > [ux_text] h1 + subhead"},
    "trust_strip": {"label": "Trust Strip", "flatsome": "[section bg_color] > [row] > [col] trust messaging"},
    "cta_row": {"label": "CTA Row", "flatsome": "[section bg_color] > [row] > [col] > [button]"},
    "category_card_row": {"label": "Category Card Row", "flatsome": "[section] > [row] > [col] linked collection/category blocks"},
    "promo_banner": {"label": "Promo Banner", "flatsome": "[section bg_overlay] > [row] > [col] promo text + button"},
    "related_links_block": {"label": "Related Links Block", "flatsome": "[section] > [row] > [col] > [ux_text] ul/li links"},
    "content_block": {"label": "Content Block", "flatsome": "[section] > [row] > [col span=8 offset=2] > [ux_text] body copy"},
    "benefit_paragraph": {"label": "Benefit Paragraph", "flatsome": "[section] > [row] > [col] short benefit/intro text"},
    "local_support_row": {"label": "Local Support Row", "flatsome": "[section] > [row] > [col] in-store/online support info"},
}


# ================== TEMPLATE DEFINITIONS ==================

TEMPLATES = {
    "standard_content": {
        "id": "standard_content",
        "name": "Template A — Standard Content Page",
        "description": "Education, trust, guides, support, informational landing pages",
        "use_for": ["education", "trust", "guide", "support", "informational", "about", "faq", "beginner", "help"],
        "sections": [
            {"key": "hero", "label": "Hero Block", "ux_block": "hero_block", "input_fields": ["hero_headline", "subheadline"], "required": True},
            {"key": "intro", "label": "Short Intro Paragraph", "ux_block": "benefit_paragraph", "input_fields": ["intro"], "required": True},
            {"key": "body", "label": "Main Content Section", "ux_block": "content_block", "input_fields": ["body_section_1", "body_section_2", "body_section_3"], "required": True},
            {"key": "cta", "label": "CTA Band", "ux_block": "cta_row", "input_fields": ["cta_text", "cta_url"], "required": True},
            {"key": "related_links", "label": "Related Links", "ux_block": "related_links_block", "input_fields": ["related_links"], "required": True},
            {"key": "trust_strip", "label": "Trust Strip", "ux_block": "trust_strip", "input_fields": ["body_section_3"], "required": False},
        ],
    },
    "category_support": {
        "id": "category_support",
        "name": "Template B — Shop Support Page",
        "description": "Lingerie, intimate care, clit stimulators, customer favorites, best sellers, category-support pages",
        "use_for": ["lingerie", "intimate care", "category", "best sellers", "customer favorites", "shop", "clit stimulators", "vibrators", "collection", "favorites", "product"],
        "sections": [
            {"key": "hero", "label": "Category Banner / Hero", "ux_block": "hero_block", "input_fields": ["hero_headline", "subheadline"], "required": True},
            {"key": "intro", "label": "Short Benefit Paragraph", "ux_block": "benefit_paragraph", "input_fields": ["intro"], "required": True},
            {"key": "category_row", "label": "Featured Collection / Category Blocks", "ux_block": "category_card_row", "input_fields": ["body_section_1", "body_section_2"], "required": True},
            {"key": "cta", "label": "CTA", "ux_block": "cta_row", "input_fields": ["cta_text", "cta_url"], "required": True},
            {"key": "trust_strip", "label": "Trust Strip", "ux_block": "trust_strip", "input_fields": ["body_section_3"], "required": True},
            {"key": "promo_banner", "label": "Promo Banner", "ux_block": "promo_banner", "input_fields": ["body_section_3"], "required": False},
            {"key": "related_links", "label": "Related Links", "ux_block": "related_links_block", "input_fields": ["related_links"], "required": False},
        ],
    },
    "local_seo_landing": {
        "id": "local_seo_landing",
        "name": "Template C — Local / SEO Landing Page",
        "description": "Long Beach sex shop, lingerie store Long Beach, adult boutique near me, local SEO pages",
        "use_for": ["long beach", "near me", "local", "store", "boutique", "city", "location", "local landing", "local page", "local seo"],
        "sections": [
            {"key": "hero", "label": "Local Headline / Hero", "ux_block": "hero_block", "input_fields": ["hero_headline", "subheadline"], "required": True},
            {"key": "trust", "label": "Local Trust Paragraph", "ux_block": "benefit_paragraph", "input_fields": ["intro"], "required": True},
            {"key": "category_row", "label": "Shop Categories / Linked Category Section", "ux_block": "category_card_row", "input_fields": ["body_section_1", "body_section_2"], "required": True},
            {"key": "why_shop", "label": "Why Shop Here / Support Section", "ux_block": "content_block", "input_fields": ["body_section_3"], "required": True},
            {"key": "cta", "label": "CTA", "ux_block": "cta_row", "input_fields": ["cta_text", "cta_url"], "required": True},
            {"key": "local_support", "label": "In-Store / Online Support Row", "ux_block": "local_support_row", "input_fields": ["body_section_2"], "required": False},
            {"key": "related_links", "label": "Related Links", "ux_block": "related_links_block", "input_fields": ["related_links"], "required": False},
        ],
    },
}


# ================== INFERENCE KEYWORDS ==================

# Weighted keyword lists for each template.
# Higher-priority keywords listed first. Checked against page_type + title + content.

INFERENCE_RULES = {
    "standard_content": {
        "strong": ["education", "guide", "faq", "trust", "about us", "support page", "informational", "beginner guide", "help center"],
        "moderate": ["support", "about", "help", "beginner", "learn", "how to", "what is", "tips", "advice"],
    },
    "category_support": {
        "strong": ["lingerie", "intimate care", "clit stimulators", "vibrators", "best sellers", "customer favorites", "shop support", "category page"],
        "moderate": ["category", "shop", "collection", "favorites", "product", "toys", "accessories", "wellness", "couples", "bondage", "lubricant", "massage"],
    },
    "local_seo_landing": {
        "strong": ["long beach", "near me", "adult boutique", "sex shop", "lingerie store long beach", "local seo", "local landing"],
        "moderate": ["local", "store", "boutique", "city", "location", "visit us", "in-store", "local page", "neighborhood"],
    },
}


def get_template(template_id: str) -> dict:
    return TEMPLATES.get(template_id)


def list_templates() -> list:
    result = []
    for t in TEMPLATES.values():
        required = [s["label"] for s in t["sections"] if s["required"]]
        optional = [s["label"] for s in t["sections"] if not s["required"]]
        result.append({
            "id": t["id"],
            "name": t["name"],
            "description": t["description"],
            "use_for": t["use_for"],
            "required_sections": required,
            "optional_sections": optional,
        })
    return result


def infer_template(page_type: str = "", title: str = "", content: str = "") -> dict:
    """
    Auto-infer the correct template using keyword matching.
    Returns {template_id, confidence, matched_keywords, needs_review}.
    """
    text = f"{page_type} {title} {content}".lower()

    scores = {}
    matched = {}

    for tid, rules in INFERENCE_RULES.items():
        score = 0
        hits = []
        for kw in rules.get("strong", []):
            if kw in text:
                score += 3
                hits.append(kw)
        for kw in rules.get("moderate", []):
            if kw in text:
                score += 1
                hits.append(kw)
        scores[tid] = score
        matched[tid] = hits

    best_tid = max(scores, key=scores.get)
    best_score = scores[best_tid]

    # Check for ambiguity: if top 2 are close, flag for review
    sorted_scores = sorted(scores.values(), reverse=True)
    is_ambiguous = len(sorted_scores) > 1 and sorted_scores[0] > 0 and (sorted_scores[0] - sorted_scores[1]) <= 1
    no_match = best_score == 0

    if no_match:
        return {
            "template_id": "standard_content",
            "confidence": "low",
            "matched_keywords": [],
            "needs_review": True,
            "reason": "No keywords matched — defaulting to Standard Content. Founder should verify.",
        }

    if is_ambiguous:
        return {
            "template_id": best_tid,
            "confidence": "medium",
            "matched_keywords": matched[best_tid],
            "needs_review": True,
            "reason": f"Close match between templates. Best guess: {TEMPLATES[best_tid]['name']}. Founder should verify.",
        }

    confidence = "high" if best_score >= 3 else "medium"
    return {
        "template_id": best_tid,
        "confidence": confidence,
        "matched_keywords": matched[best_tid],
        "needs_review": confidence != "high",
        "reason": None,
    }
