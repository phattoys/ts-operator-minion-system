"""
Menu / Navigation Mapper — Organizes pages into menu buckets,
detects orphans, suggests internal links, and provides menu structure.
"""
from database import db


# ---- Menu Structure Definition ----

MENU_STRUCTURE = {
    "main_nav": {
        "label": "Main Navigation",
        "description": "Top-level menu items visible on every page",
        "buckets": [
            {
                "id": "shop",
                "label": "Shop",
                "description": "Product browsing entry points",
                "pages": [],
            },
            {
                "id": "lingerie",
                "label": "Lingerie",
                "description": "Lingerie district and sub-categories",
                "pages": [],
            },
            {
                "id": "wellness",
                "label": "Wellness",
                "description": "Sexual wellness and body-safe focus",
                "pages": [],
            },
            {
                "id": "explore",
                "label": "Explore",
                "description": "Districts and discovery paths",
                "pages": [],
            },
            {
                "id": "learn",
                "label": "Learn",
                "description": "Education, guides, beginner paths",
                "pages": [],
            },
            {
                "id": "about",
                "label": "About",
                "description": "Brand identity, trust, who we are",
                "pages": [],
            },
        ],
    },
    "footer": {
        "label": "Footer Links",
        "description": "Bottom-of-page trust and utility links",
        "buckets": [
            {
                "id": "footer_about",
                "label": "About Us",
                "pages": [],
            },
            {
                "id": "footer_support",
                "label": "Support",
                "pages": [],
            },
            {
                "id": "footer_local",
                "label": "Visit Us",
                "pages": [],
            },
        ],
    },
    "hidden_utility": {
        "label": "Hidden / Utility Pages",
        "description": "Not in main navigation but accessible via direct links",
        "pages": [],
    },
}

# ---- Page-to-Bucket Mapping Rules ----

PAGE_MENU_RULES = {
    # slug → (nav_bucket, footer_bucket, is_hidden)
    "long-beach-lingerie": ("lingerie", "footer_local", False),
    "wellness-district": ("wellness", "footer_about", False),
    "long-beach-sexual-wellness": ("wellness", "footer_local", False),
    "pleasure-district": ("explore", None, False),
    "education-district": ("learn", None, False),
    "community-district": ("explore", None, False),
    "beginner-friendly-shopping": ("learn", None, False),
    "body-safe-shame-free": ("learn", "footer_about", False),
    "about": ("about", "footer_about", False),
    "about-temporary-satisfaction": ("about", "footer_about", False),
    "who-we-serve": ("about", "footer_about", False),
    "customer-stories": ("about", "footer_about", False),
    "faq": ("about", "footer_support", False),
    "shipping-and-delivery-faq": (None, "footer_support", False),
    "product-care-guide": (None, "footer_support", False),
    "long-beach-adult-boutique": ("about", "footer_local", False),
    "new-member-welcome": (None, None, True),
    "vip-membership": (None, None, True),
}

# Family-based fallback rules
FAMILY_BUCKET_FALLBACK = {
    "District": "explore",
    "Trust": "about",
    "FAQ/Support": None,
    "Guided Path": "learn",
    "Conversion": None,
    "Core Hub": "shop",
    "Category Support": "shop",
    "Digital/Tools": "shop",
    "Media/Asset": None,
}


async def generate_menu_map() -> dict:
    """Generate the full menu/navigation map for all live pages."""
    # Fetch all placed pages
    placed_pages = []
    async for doc in db.pages.find({"status": "placed"}, {"_id": 0}):
        placed_pages.append(doc)

    if not placed_pages:
        return {"error": "No placed pages found", "pages": 0}

    # Build the structure
    import copy
    menu = copy.deepcopy(MENU_STRUCTURE)

    orphan_pages = []
    page_assignments = []

    for page in placed_pages:
        slug = page.get("slug", "")
        family = page.get("page_family", "")
        page_info = {
            "id": page["id"],
            "page_code": page.get("page_code", ""),
            "page_name": page.get("page_name", ""),
            "slug": slug,
            "page_family": family,
            "menu_destination": page.get("menu_destination", ""),
            "funnel_stage": page.get("funnel_stage", ""),
        }

        # Check explicit rules first
        rule = PAGE_MENU_RULES.get(slug)
        assigned = False

        if rule:
            nav_bucket, footer_bucket, is_hidden = rule

            if is_hidden:
                menu["hidden_utility"]["pages"].append(page_info)
                page_assignments.append({**page_info, "placement": "hidden_utility"})
                assigned = True
            else:
                if nav_bucket:
                    for bucket in menu["main_nav"]["buckets"]:
                        if bucket["id"] == nav_bucket:
                            bucket["pages"].append(page_info)
                            assigned = True
                            break

                if footer_bucket:
                    for bucket in menu["footer"]["buckets"]:
                        if bucket["id"] == footer_bucket:
                            bucket["pages"].append(page_info)
                            break

                if assigned:
                    page_assignments.append({**page_info, "placement": f"main_nav/{nav_bucket}"})
        
        # Fallback: use family-based mapping
        if not assigned:
            fallback_bucket = FAMILY_BUCKET_FALLBACK.get(family)
            if fallback_bucket:
                for bucket in menu["main_nav"]["buckets"]:
                    if bucket["id"] == fallback_bucket:
                        bucket["pages"].append(page_info)
                        page_assignments.append({**page_info, "placement": f"main_nav/{fallback_bucket} (auto)"})
                        assigned = True
                        break

        if not assigned:
            orphan_pages.append(page_info)
            page_assignments.append({**page_info, "placement": "ORPHAN"})

    # Generate internal link suggestions
    link_suggestions = _generate_link_suggestions(placed_pages)

    return {
        "menu": menu,
        "assignments": page_assignments,
        "orphan_pages": orphan_pages,
        "link_suggestions": link_suggestions,
        "stats": {
            "total_placed": len(placed_pages),
            "assigned": len(placed_pages) - len(orphan_pages),
            "orphans": len(orphan_pages),
            "main_nav_items": sum(len(b["pages"]) for b in menu["main_nav"]["buckets"]),
            "footer_items": sum(len(b["pages"]) for b in menu["footer"]["buckets"]),
            "hidden": len(menu["hidden_utility"]["pages"]),
        },
    }


# ---- Internal Link Map ----
#
# Maintainable, curated internal-link recommendations. Each row is one
# source -> destination relationship. This is a recommendation list
# (Rene enforces minimum counts / duplicate detection on whatever
# related_links a page actually ends up with -- see
# services/worker_queue._rene_qa_wp_content -- this map is only the
# source of *suggestions*, not enforcement).
#
# Fields:
#   source_slug       - the page this suggestion applies to
#   destination_slug   - the recommended internal link target
#   anchor_label        - suggested link text (falls back to the live
#                          page's own page_name at generation time if
#                          the destination page's name differs)
#   reason              - why this link makes sense (shown to the founder)
#   required            - True if this specific link should be treated as
#                          a hard requirement rather than a suggestion
#                          (currently none are -- existing entries are all
#                          recommendations, matching prior behavior)
#
# Extend this list with real slugs as the 14-page backlog is placed.
# Do not invent placeholder slugs here -- add real ones as pages exist.
INTERNAL_LINK_MAP = [
    {"source_slug": "about", "destination_slug": "who-we-serve", "anchor_label": "Who We Serve", "reason": "Brand exploration path", "required": False},
    {"source_slug": "about", "destination_slug": "long-beach-adult-boutique", "anchor_label": "Long Beach Adult Boutique", "reason": "Brand exploration path", "required": False},
    {"source_slug": "about", "destination_slug": "customer-stories", "anchor_label": "Customer Stories", "reason": "Brand exploration path", "required": False},
    {"source_slug": "long-beach-adult-boutique", "destination_slug": "long-beach-lingerie", "anchor_label": "Long Beach Lingerie", "reason": "Local discovery path", "required": False},
    {"source_slug": "long-beach-adult-boutique", "destination_slug": "long-beach-sexual-wellness", "anchor_label": "Long Beach Sexual Wellness", "reason": "Local discovery path", "required": False},
    {"source_slug": "long-beach-adult-boutique", "destination_slug": "beginner-friendly-shopping", "anchor_label": "Beginner-Friendly Shopping", "reason": "Local discovery path", "required": False},
    {"source_slug": "long-beach-sexual-wellness", "destination_slug": "body-safe-shame-free", "anchor_label": "Body-Safe, Shame-Free", "reason": "Wellness exploration", "required": False},
    {"source_slug": "long-beach-sexual-wellness", "destination_slug": "wellness-district", "anchor_label": "Wellness District", "reason": "Wellness exploration", "required": False},
    {"source_slug": "long-beach-sexual-wellness", "destination_slug": "beginner-friendly-shopping", "anchor_label": "Beginner-Friendly Shopping", "reason": "Wellness exploration", "required": False},
    {"source_slug": "long-beach-lingerie", "destination_slug": "pleasure-district", "anchor_label": "Pleasure District", "reason": "Lingerie to boutique", "required": False},
    {"source_slug": "long-beach-lingerie", "destination_slug": "long-beach-adult-boutique", "anchor_label": "Long Beach Adult Boutique", "reason": "Lingerie to boutique", "required": False},
    {"source_slug": "beginner-friendly-shopping", "destination_slug": "body-safe-shame-free", "anchor_label": "Body-Safe, Shame-Free", "reason": "Beginner trust path", "required": False},
    {"source_slug": "beginner-friendly-shopping", "destination_slug": "who-we-serve", "anchor_label": "Who We Serve", "reason": "Beginner trust path", "required": False},
    {"source_slug": "beginner-friendly-shopping", "destination_slug": "faq", "anchor_label": "FAQ", "reason": "Beginner trust path", "required": False},
    {"source_slug": "body-safe-shame-free", "destination_slug": "wellness-district", "anchor_label": "Wellness District", "reason": "Safety to wellness", "required": False},
    {"source_slug": "body-safe-shame-free", "destination_slug": "beginner-friendly-shopping", "anchor_label": "Beginner-Friendly Shopping", "reason": "Safety to wellness", "required": False},
    {"source_slug": "body-safe-shame-free", "destination_slug": "long-beach-sexual-wellness", "anchor_label": "Long Beach Sexual Wellness", "reason": "Safety to wellness", "required": False},
    {"source_slug": "who-we-serve", "destination_slug": "beginner-friendly-shopping", "anchor_label": "Beginner-Friendly Shopping", "reason": "Audience to action", "required": False},
    {"source_slug": "who-we-serve", "destination_slug": "about", "anchor_label": "About", "reason": "Audience to action", "required": False},
    {"source_slug": "who-we-serve", "destination_slug": "long-beach-adult-boutique", "anchor_label": "Long Beach Adult Boutique", "reason": "Audience to action", "required": False},
    {"source_slug": "faq", "destination_slug": "shipping-and-delivery-faq", "anchor_label": "Shipping & Delivery FAQ", "reason": "FAQ support path", "required": False},
    {"source_slug": "faq", "destination_slug": "body-safe-shame-free", "anchor_label": "Body-Safe, Shame-Free", "reason": "FAQ support path", "required": False},
    {"source_slug": "faq", "destination_slug": "beginner-friendly-shopping", "anchor_label": "Beginner-Friendly Shopping", "reason": "FAQ support path", "required": False},
    {"source_slug": "wellness-district", "destination_slug": "long-beach-sexual-wellness", "anchor_label": "Long Beach Sexual Wellness", "reason": "Wellness cluster", "required": False},
    {"source_slug": "wellness-district", "destination_slug": "body-safe-shame-free", "anchor_label": "Body-Safe, Shame-Free", "reason": "Wellness cluster", "required": False},
    {"source_slug": "wellness-district", "destination_slug": "pleasure-district", "anchor_label": "Pleasure District", "reason": "Wellness cluster", "required": False},
    {"source_slug": "pleasure-district", "destination_slug": "wellness-district", "anchor_label": "Wellness District", "reason": "Pleasure cluster", "required": False},
    {"source_slug": "pleasure-district", "destination_slug": "long-beach-lingerie", "anchor_label": "Long Beach Lingerie", "reason": "Pleasure cluster", "required": False},
    {"source_slug": "pleasure-district", "destination_slug": "beginner-friendly-shopping", "anchor_label": "Beginner-Friendly Shopping", "reason": "Pleasure cluster", "required": False},
]

# Auto-suggestion caps for the generic same-family/same-district fallback
# below -- keeps the output usable instead of combinatorial.
_AUTO_SUGGESTION_MAX_PER_SOURCE = 3


def _generate_link_suggestions(pages: list) -> list:
    """
    Generate 'discover next' internal link suggestions.

    Two sources, combined:
    1. INTERNAL_LINK_MAP -- curated, explicit source->destination rows.
    2. A generic same-page_family / same-district_or_pillar fallback, so
       NEW pages (the 14-page backlog, whatever their real slugs turn out
       to be) still get real suggestions without needing to be
       pre-registered in the curated map above. This does not replace
       curating real links later -- it just means nothing ships with zero
       suggestions merely because it's new.
    """
    suggestions = []

    # Build lookup
    by_slug = {p.get("slug", ""): p for p in pages}
    by_family = {}
    by_district = {}
    for p in pages:
        by_family.setdefault(p.get("page_family", ""), []).append(p)
        district = p.get("district_or_pillar")
        if district:
            by_district.setdefault(district, []).append(p)

    # ---- 1. Curated map ----
    curated_by_source = {}
    for row in INTERNAL_LINK_MAP:
        curated_by_source.setdefault(row["source_slug"], []).append(row)

    curated_pairs = set()
    for source_slug, rows in curated_by_source.items():
        if source_slug not in by_slug:
            continue
        valid_rows = [r for r in rows if r["destination_slug"] in by_slug]
        if not valid_rows:
            continue
        # Group by reason for the same friendly display shape as before,
        # while still being sourced from the flat, maintainable list.
        by_reason = {}
        for r in valid_rows:
            by_reason.setdefault(r["reason"], []).append(r)
            curated_pairs.add((source_slug, r["destination_slug"]))
        for reason, rows_for_reason in by_reason.items():
            suggestions.append({
                "from_page": by_slug[source_slug].get("page_name", source_slug),
                "from_slug": source_slug,
                "links_to": [
                    {
                        "slug": r["destination_slug"],
                        "name": by_slug[r["destination_slug"]].get("page_name", r["destination_slug"]),
                        "anchor_label": r["anchor_label"],
                        "required": r["required"],
                    }
                    for r in rows_for_reason
                ],
                "reason": reason,
                "source": "curated",
            })

    # ---- 2. Generic same-family / same-district fallback ----
    for source in pages:
        source_slug = source.get("slug", "")
        if not source_slug:
            continue

        candidates = []
        family = source.get("page_family", "")
        if family:
            candidates.extend([p for p in by_family.get(family, []) if p.get("slug") != source_slug])
        district = source.get("district_or_pillar")
        if district:
            candidates.extend([p for p in by_district.get(district, []) if p.get("slug") != source_slug])

        # De-dupe candidates and drop anything already covered by the curated map
        seen_slugs = set()
        auto_links = []
        for c in candidates:
            c_slug = c.get("slug", "")
            if not c_slug or c_slug in seen_slugs:
                continue
            if (source_slug, c_slug) in curated_pairs:
                continue
            seen_slugs.add(c_slug)
            auto_links.append({
                "slug": c_slug,
                "name": c.get("page_name", c_slug),
                "anchor_label": c.get("page_name", c_slug),
                "required": False,
            })
            if len(auto_links) >= _AUTO_SUGGESTION_MAX_PER_SOURCE:
                break

        if auto_links:
            reason = f"Same {'district' if district else 'page family'}"
            suggestions.append({
                "from_page": source.get("page_name", source_slug),
                "from_slug": source_slug,
                "links_to": auto_links,
                "reason": reason,
                "source": "auto",
            })

    return suggestions
