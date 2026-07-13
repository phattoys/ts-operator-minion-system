"""
Menu Mapper v1 — Maps pages to menu slots with approval queue,
dependency tracking, customer paths, and discovery flow logic.
"""
import uuid
from datetime import datetime, timezone
from database import db, logger


# ---- Top-Level Menu Families ----

MENU_FAMILIES = ["Shop", "Learn", "Digital Products", "AI Tools", "For Business Owners", "About", "VIP / Join"]

ITEM_STATUSES = ["existing_page", "needs_page", "needs_woo_category", "needs_product_link", "coming_soon", "do_not_add_yet"]

PLACEMENTS = ["main_menu", "mega_menu", "footer", "mobile", "hidden_funnel"]

CUSTOMER_PATHS = ["discovery", "education", "trust", "shopping", "conversion", "retention"]

DEPENDENCY_TYPES = ["page_generation", "woo_category", "copy_content", "decision_needed", "product_setup", "none"]


# ---- Menu Item Schema ----

def _create_menu_item(
    label: str,
    menu_family: str,
    placement: str,
    status: str,
    customer_path: str,
    priority: int,
    reason: str,
    destination_url: str = "",
    parent_item: str = "",
    dependency_blocker: str = "none",
    dependency_note: str = "",
    next_click: str = "",
    is_public: bool = True,
    page_code: str = "",
    page_id: str = "",
) -> dict:
    return {
        "id": str(uuid.uuid4()),
        "label": label,
        "menu_family": menu_family,
        "placement": placement,
        "status": status,
        "customer_path": customer_path,
        "priority": priority,
        "reason": reason,
        "destination_url": destination_url,
        "parent_item": parent_item,
        "dependency_blocker": dependency_blocker,
        "dependency_note": dependency_note,
        "next_click": next_click,
        "is_public": is_public,
        "page_code": page_code,
        "page_id": page_id,
        "approved": False,
        "pushed_to_wp": False,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }


# ---- Generate Full Menu Map ----

async def generate_full_menu_map() -> dict:
    """Scan all pages and generate the complete menu map with all fields."""

    # Fetch all placed/approved pages
    pages = []
    async for doc in db.pages.find({"status": {"$in": ["placed", "Approved"]}}, {"_id": 0}):
        pages.append(doc)

    page_by_slug = {p.get("slug", ""): p for p in pages}

    menu_items = []

    # === SHOP ===
    shop_items = [
        ("Shop All", "shop", "/shop", "existing_page", "shopping", 100, "Main shop entry", "", "Browse categories or use guided shopping"),
        ("New Arrivals", "shop", "/product-category/new-arrivals", "needs_woo_category", "discovery", 90, "Fresh inventory visibility", "woo_category", "Browse or filter by type"),
        ("Best Sellers", "shop", "/product-category/best-sellers", "needs_woo_category", "shopping", 88, "Social proof + easy entry", "woo_category", "Add to cart or explore related"),
        ("Lingerie", "shop", "/long-beach-lingerie", "existing_page", "shopping", 95, "Core category — strong local SEO", "", "Browse lingerie styles or visit store"),
        ("Wellness", "shop", "/long-beach-sexual-wellness", "existing_page", "shopping", 93, "Wellness positioning + body-safe focus", "", "Explore body-safe products or read guide"),
        ("Pleasure", "shop", "/pleasure-district", "existing_page", "shopping", 85, "Core product district", "", "Browse or read beginner guide"),
        ("Gift Sets", "shop", "/product-category/gift-sets", "needs_woo_category", "conversion", 80, "Revenue driver — couples/holidays", "woo_category", "Choose occasion → select gift"),
        ("Sale", "shop", "/product-category/sale", "needs_woo_category", "conversion", 75, "Price-sensitive traffic capture", "woo_category", "Browse deals"),
    ]

    for label, fam, url, status, path, pri, reason, dep, next_c in shop_items:
        pg = page_by_slug.get(url.lstrip("/"), {})
        menu_items.append(_create_menu_item(
            label=label, menu_family="Shop", placement="main_menu",
            status=status, customer_path=path, priority=pri, reason=reason,
            destination_url=url, dependency_blocker=dep,
            next_click=next_c, page_id=pg.get("id", ""), page_code=pg.get("page_code", ""),
        ))

    # === LEARN ===
    learn_items = [
        ("Beginner's Guide", "learn", "/beginner-friendly-shopping", "existing_page", "education", 95, "Removes fear for first-timers — critical trust builder", "", "Read guide → browse beginner picks → shop"),
        ("Body-Safe Shopping", "learn", "/body-safe-shame-free", "existing_page", "education", 92, "Trust + AI identity signal — what body-safe means", "", "Understand safety → explore products → wellness district"),
        ("Education District", "learn", "/education-district", "existing_page", "education", 85, "Hub for all learning content", "", "Choose topic → deep dive → shop when ready"),
        ("Who We Serve", "learn", "/who-we-serve", "existing_page", "trust", 80, "Audience identification — makes visitors feel seen", "", "Find your group → explore what we offer → shop"),
        ("FAQ", "learn", "/faq", "existing_page", "trust", 78, "Reduces anxiety — supports FAQ schema", "", "Get answers → feel ready → shop or visit"),
        ("Product Care Guide", "learn", "/product-care-guide", "existing_page", "retention", 60, "Post-purchase support — builds loyalty", "", "Care for products → explore more → return"),
    ]

    for label, fam, url, status, path, pri, reason, dep, next_c in learn_items:
        pg = page_by_slug.get(url.lstrip("/"), {})
        menu_items.append(_create_menu_item(
            label=label, menu_family="Learn", placement="main_menu",
            status=status, customer_path=path, priority=pri, reason=reason,
            destination_url=url, next_click=next_c,
            page_id=pg.get("id", ""), page_code=pg.get("page_code", ""),
        ))

    # === DIGITAL PRODUCTS ===
    digital_items = [
        ("AI Prompt Vault", "digital", "/product/ai-prompt-vault", "needs_page", "conversion", 90, "Revenue — digital product", "page_generation", "Preview → purchase → download"),
        ("Grant Pack Starter Kit", "digital", "/product/grant-pack-starter-kit", "needs_page", "conversion", 88, "Revenue — digital product", "page_generation", "Preview → purchase → download"),
        ("Boutique SEO Quick Win Kit", "digital", "/product/seo-quick-win-kit", "needs_page", "conversion", 85, "Revenue — digital product", "page_generation", "Preview → purchase → download"),
        ("All Digital Products", "digital", "/digital-products", "needs_page", "shopping", 82, "Collection landing page for all digital", "page_generation", "Browse all → choose → purchase"),
    ]

    for label, fam, url, status, path, pri, reason, dep, next_c in digital_items:
        menu_items.append(_create_menu_item(
            label=label, menu_family="Digital Products", placement="main_menu",
            status=status, customer_path=path, priority=pri, reason=reason,
            destination_url=url, dependency_blocker=dep, next_click=next_c,
        ))

    # === AI TOOLS ===
    ai_items = [
        ("Ad Foundry", "ai_tools", "/ai-tools/ad-foundry", "coming_soon", "conversion", 85, "AI ad creation — revenue tool", "decision_needed", "Choose recipe → generate → export to Canva"),
        ("QuickPost", "ai_tools", "/ai-tools/quickpost", "coming_soon", "conversion", 80, "Social media content creation", "decision_needed", "Select platform → generate → schedule"),
        ("TS SEO Boost", "ai_tools", "/ai-tools/seo-boost", "coming_soon", "conversion", 78, "SEO tool for business owners", "decision_needed", "Enter URL → get recommendations → implement"),
    ]

    for label, fam, url, status, path, pri, reason, dep, next_c in ai_items:
        menu_items.append(_create_menu_item(
            label=label, menu_family="AI Tools", placement="main_menu",
            status=status, customer_path=path, priority=pri, reason=reason,
            destination_url=url, dependency_blocker=dep, next_click=next_c, is_public=False,
        ))

    # === FOR BUSINESS OWNERS ===
    biz_items = [
        ("Business Resources", "business", "/for-business-owners", "needs_page", "education", 75, "B2B positioning — shows authority", "page_generation", "Explore resources → tools → VIP"),
        ("Wholesale / Partnerships", "business", "/wholesale", "needs_page", "conversion", 70, "Revenue expansion channel", "page_generation", "Learn terms → apply → connect"),
    ]

    for label, fam, url, status, path, pri, reason, dep, next_c in biz_items:
        menu_items.append(_create_menu_item(
            label=label, menu_family="For Business Owners", placement="main_menu",
            status=status, customer_path=path, priority=pri, reason=reason,
            destination_url=url, dependency_blocker=dep, next_click=next_c, is_public=False,
        ))

    # === ABOUT ===
    about_items = [
        ("About Us", "about", "/about", "existing_page", "trust", 95, "Brand anchor — AI identity", "", "Understand brand → explore → shop or visit"),
        ("Long Beach Boutique", "about", "/long-beach-adult-boutique", "existing_page", "trust", 90, "Local SEO + physical store trust", "", "Learn about store → get directions → visit"),
        ("Customer Stories", "about", "/customer-stories", "existing_page", "trust", 80, "Social proof", "", "Read stories → feel confident → shop"),
        ("Community District", "about", "/community-district", "existing_page", "trust", 70, "Community connection", "", "See community → feel belonging → engage"),
        ("Contact / Visit Us", "about", "/contact", "needs_page", "trust", 88, "Critical for local business — hours, directions, phone", "page_generation", "Get info → visit or call"),
    ]

    for label, fam, url, status, path, pri, reason, dep, next_c in about_items:
        pg = page_by_slug.get(url.lstrip("/"), {})
        menu_items.append(_create_menu_item(
            label=label, menu_family="About", placement="main_menu",
            status=status, customer_path=path, priority=pri, reason=reason,
            destination_url=url, dependency_blocker=dep if dep else "none", next_click=next_c,
            page_id=pg.get("id", ""), page_code=pg.get("page_code", ""),
        ))

    # === VIP / JOIN ===
    vip_items = [
        ("VIP Membership", "vip", "/vip-membership", "existing_page", "retention", 90, "Revenue + retention — loyalty layer", "", "See benefits → join → access perks"),
        ("New Member Welcome", "vip", "/new-member-welcome", "existing_page", "retention", 85, "Onboarding — post-join experience", "", "Get oriented → explore perks → shop"),
    ]

    for label, fam, url, status, path, pri, reason, dep, next_c in vip_items:
        pg = page_by_slug.get(url.lstrip("/"), {})
        menu_items.append(_create_menu_item(
            label=label, menu_family="VIP / Join", placement="hidden_funnel",
            status=status, customer_path=path, priority=pri, reason=reason,
            destination_url=url, next_click=next_c,
            page_id=pg.get("id", ""), page_code=pg.get("page_code", ""),
        ))

    # === FOOTER ITEMS ===
    footer_items = [
        ("Shipping & Delivery", "footer", "/shipping-and-delivery-faq", "existing_page", "trust", 85, "Reduces purchase anxiety", ""),
        ("FAQ", "footer", "/faq", "existing_page", "trust", 80, "Support + schema", ""),
        ("About Us", "footer", "/about", "existing_page", "trust", 90, "Brand trust", ""),
        ("Contact", "footer", "/contact", "needs_page", "trust", 88, "Critical utility link", "page_generation"),
        ("Privacy Policy", "footer", "/privacy-policy", "do_not_add_yet", "trust", 50, "Legal — verify if exists", "decision_needed"),
    ]

    for label, fam, url, status, path, pri, reason, dep in footer_items:
        pg = page_by_slug.get(url.lstrip("/"), {})
        menu_items.append(_create_menu_item(
            label=label, menu_family="Footer", placement="footer",
            status=status, customer_path=path, priority=pri, reason=reason,
            destination_url=url, dependency_blocker=dep if dep else "none",
            page_id=pg.get("id", ""), page_code=pg.get("page_code", ""),
        ))

    # Persist to DB
    await db.menu_map.delete_many({})  # Replace old map
    for item in menu_items:
        await db.menu_map.insert_one(item)

    # Build summary outputs
    missing_pages = [i for i in menu_items if i["status"] == "needs_page"]
    needs_woo = [i for i in menu_items if i["status"] == "needs_woo_category"]
    coming_soon = [i for i in menu_items if i["status"] == "coming_soon"]
    ready_items = [i for i in menu_items if i["status"] == "existing_page" and i["is_public"]]
    not_public = [i for i in menu_items if not i["is_public"]]

    return {
        "total_items": len(menu_items),
        "ready_to_add": len(ready_items),
        "missing_pages": len(missing_pages),
        "needs_woo_category": len(needs_woo),
        "coming_soon": len(coming_soon),
        "not_public_yet": len(not_public),
        "menu_items": [{k: v for k, v in i.items() if k != "_id"} for i in menu_items],
        "missing_page_queue": [{k: v for k, v in i.items() if k != "_id"} for i in missing_pages],
        "approved_to_push": [{k: v for k, v in i.items() if k != "_id"} for i in ready_items],
        "hold_list": [{k: v for k, v in i.items() if k != "_id"} for i in not_public + coming_soon],
        "wp_build_instructions": _generate_wp_instructions(menu_items),
    }


def _generate_wp_instructions(items: list) -> list:
    """Generate WordPress menu build instructions from approved items."""
    instructions = [
        "=== WordPress Menu Implementation ===",
        "",
        "Go to: WordPress Admin → Appearance → Menus",
        "Select: 'Main Shop Menu' (primary active menu)",
        "",
        "--- TOP-LEVEL ITEMS ---",
    ]

    # Group by family
    by_family = {}
    for item in items:
        if item["status"] == "existing_page" and item["is_public"] and item["placement"] in ("main_menu", "mega_menu"):
            fam = item["menu_family"]
            by_family.setdefault(fam, []).append(item)

    for family in MENU_FAMILIES:
        if family in by_family:
            instructions.append("")
            instructions.append(f"[{family}]")
            for item in sorted(by_family[family], key=lambda x: -x["priority"]):
                instructions.append(f"  + {item['label']} → {item['destination_url']}")
                if item["next_click"]:
                    instructions.append(f"    (next: {item['next_click']})")

    instructions.append("")
    instructions.append("--- FOOTER ---")
    footer_items = [i for i in items if i["placement"] == "footer" and i["status"] == "existing_page"]
    for item in sorted(footer_items, key=lambda x: -x["priority"]):
        instructions.append(f"  + {item['label']} → {item['destination_url']}")

    instructions.append("")
    instructions.append("--- DO NOT ADD YET ---")
    hold = [i for i in items if i["status"] in ("needs_page", "coming_soon", "do_not_add_yet") or not i["is_public"]]
    for item in hold[:10]:
        instructions.append(f"  ✗ {item['label']} — {item['status']} ({item['dependency_blocker']})")

    return instructions
