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


def _generate_link_suggestions(pages: list) -> list:
    """Generate 'discover next' internal link suggestions."""
    suggestions = []

    # Build lookup
    by_slug = {p.get("slug", ""): p for p in pages}
    by_family = {}
    for p in pages:
        fam = p.get("page_family", "")
        by_family.setdefault(fam, []).append(p)

    # Link rules
    link_rules = [
        # (from_slug, to_slugs, reason)
        ("about", ["who-we-serve", "long-beach-adult-boutique", "customer-stories"], "Brand exploration path"),
        ("long-beach-adult-boutique", ["long-beach-lingerie", "long-beach-sexual-wellness", "beginner-friendly-shopping"], "Local discovery path"),
        ("long-beach-sexual-wellness", ["body-safe-shame-free", "wellness-district", "beginner-friendly-shopping"], "Wellness exploration"),
        ("long-beach-lingerie", ["pleasure-district", "long-beach-adult-boutique"], "Lingerie to boutique"),
        ("beginner-friendly-shopping", ["body-safe-shame-free", "who-we-serve", "faq"], "Beginner trust path"),
        ("body-safe-shame-free", ["wellness-district", "beginner-friendly-shopping", "long-beach-sexual-wellness"], "Safety to wellness"),
        ("who-we-serve", ["beginner-friendly-shopping", "about", "long-beach-adult-boutique"], "Audience to action"),
        ("faq", ["shipping-and-delivery-faq", "body-safe-shame-free", "beginner-friendly-shopping"], "FAQ support path"),
        ("wellness-district", ["long-beach-sexual-wellness", "body-safe-shame-free", "pleasure-district"], "Wellness cluster"),
        ("pleasure-district", ["wellness-district", "long-beach-lingerie", "beginner-friendly-shopping"], "Pleasure cluster"),
    ]

    for from_slug, to_slugs, reason in link_rules:
        if from_slug in by_slug:
            valid_links = [s for s in to_slugs if s in by_slug]
            if valid_links:
                suggestions.append({
                    "from_page": by_slug[from_slug].get("page_name", from_slug),
                    "from_slug": from_slug,
                    "links_to": [{"slug": s, "name": by_slug[s].get("page_name", s)} for s in valid_links],
                    "reason": reason,
                })

    return suggestions
