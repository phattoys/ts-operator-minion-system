"""
Placement Engine — maps structured content into template sections,
builds Flatsome/UX Builder shortcode output.
"""


def build_page_content(template: dict, content: dict) -> dict:
    """
    Takes a template definition and structured content dict,
    returns {html, sections_placed, sections_skipped, warnings}.
    """
    sections_placed = []
    sections_skipped = []
    warnings = []
    html_parts = []

    for section in template["sections"]:
        key = section["key"]
        input_fields = section["input_fields"]
        has_content = any(content.get(f) for f in input_fields)

        if not has_content:
            if section["required"]:
                warnings.append(f"Required section '{section['label']}' has no content — left empty")
            sections_skipped.append({
                "key": key,
                "label": section["label"],
                "ux_block": section.get("ux_block", ""),
                "reason": "no content provided",
                "required": section["required"],
            })
            continue

        section_html = _render_section(key, section, content)
        if section_html:
            html_parts.append(section_html)
            sections_placed.append({
                "key": key,
                "label": section["label"],
                "ux_block": section.get("ux_block", ""),
            })

    # CTA warnings
    if content.get("cta_text") and not content.get("cta_url"):
        warnings.append("CTA text provided but URL is missing")
    if not content.get("cta_text") and not content.get("cta_url"):
        warnings.append("No CTA provided — CTA section left empty")

    full_html = "\n\n".join(html_parts)

    return {
        "html": full_html,
        "sections_placed": sections_placed,
        "sections_skipped": sections_skipped,
        "warnings": warnings,
    }


def _render_section(key: str, section: dict, content: dict) -> str:
    """Render a single section as Flatsome UX Builder shortcode markup."""
    ux_block = section.get("ux_block", "")

    # ---- Hero Block ----
    if key == "hero":
        headline = content.get("hero_headline", "")
        sub = content.get("subheadline", "")

        # If no headline, suppress the hero entirely — no empty black block
        if not headline and not sub:
            return ""

        sub_block = f'\n[gap height="10px"]\n[ux_text text_align="center"]\n<p style="color: #a1a1aa; font-size: 1.1rem;">{sub}</p>\n[/ux_text]' if sub else ""
        return f"""[section bg_color="rgb(24,24,27)" padding="60px" padding__sm="40px"]
[row]
[col span__sm="12" align="center"]
[ux_text text_align="center"]
<h1 style="color: #ffffff; font-size: 2.2rem; font-weight: 600; letter-spacing: -0.02em; line-height: 1.3;">{headline}</h1>
[/ux_text]{sub_block}
[/col]
[/row]
[/section]"""

    # ---- Intro / Trust / Benefit Paragraph ----
    if key in ("intro", "trust"):
        intro = content.get("intro", "")
        return f"""[section padding="60px"]
[row]
[col span="8" span__sm="12" offset="2"]
[ux_text]
{intro}
[/ux_text]
[/col]
[/row]
[/section]"""

    # ---- Main Body / Content Block ----
    if key == "body":
        parts = []
        for f in section["input_fields"]:
            if content.get(f):
                parts.append(content[f])
        if not parts:
            return ""
        body_html = "\n\n".join(parts)
        return f"""[section padding="40px"]
[row]
[col span="8" span__sm="12" offset="2"]
[ux_text]
{body_html}
[/ux_text]
[/col]
[/row]
[/section]"""

    # ---- Why Shop Here / Support Section ----
    if key == "why_shop":
        parts = [content.get(f, "") for f in section["input_fields"] if content.get(f)]
        if not parts:
            return ""
        return f"""[section bg_color="rgb(245,245,245)" padding="50px"]
[row]
[col span="8" span__sm="12" offset="2"]
[ux_text]
<h3>Why Shop With Us</h3>
{chr(10).join(parts)}
[/ux_text]
[/col]
[/row]
[/section]"""

    # ---- Category Card Row / Featured Collection Blocks ----
    if key == "category_row":
        parts = [content.get(f, "") for f in section["input_fields"] if content.get(f)]
        if not parts:
            return ""
        cols = []
        for part in parts:
            cols.append(f"""[col span="6" span__sm="12"]
[ux_text]
{part}
[/ux_text]
[/col]""")
        return f"""[section padding="40px"]
[row]
{chr(10).join(cols)}
[/row]
[/section]"""

    # ---- Trust Strip ----
    if key == "trust_strip":
        trust_text = ""
        for f in section["input_fields"]:
            if content.get(f):
                trust_text = content[f]
                break
        if not trust_text:
            return ""
        return f"""[section bg_color="rgb(250,250,250)" padding="30px"]
[row]
[col span__sm="12" align="center"]
[ux_text text_align="center"]
<p class="trust-strip">{trust_text}</p>
[/ux_text]
[/col]
[/row]
[/section]"""

    # ---- Promo Banner ----
    if key == "promo_banner":
        promo_text = ""
        for f in section["input_fields"]:
            if content.get(f):
                promo_text = content[f]
                break
        if not promo_text:
            return ""
        return f"""[section bg_color="rgb(30,30,30)" padding="40px"]
[row]
[col span__sm="12" align="center"]
[ux_text text_align="center"]
<p class="promo-text">{promo_text}</p>
[/ux_text]
[/col]
[/row]
[/section]"""

    # ---- Local Support Row ----
    if key == "local_support":
        support_text = ""
        for f in section["input_fields"]:
            if content.get(f):
                support_text = content[f]
                break
        if not support_text:
            return ""
        return f"""[section padding="40px"]
[row]
[col span="6" span__sm="12"]
[ux_text]
<h4>In-Store</h4>
{support_text}
[/ux_text]
[/col]
[col span="6" span__sm="12"]
[ux_text]
<h4>Shop Online</h4>
<p>Browse our full collection online with discreet shipping.</p>
[/ux_text]
[/col]
[/row]
[/section]"""

    # ---- CTA Row ----
    if key == "cta":
        cta_text = content.get("cta_text", "")
        cta_url = content.get("cta_url", "#")
        if not cta_text:
            return ""
        return f"""[section bg_color="rgb(30,30,30)" padding="50px"]
[row]
[col span__sm="12" align="center"]
[button text="{cta_text}" link="{cta_url}" style="shade" size="larger" radius="0"]
[/col]
[/row]
[/section]"""

    # ---- Related Links Block ----
    if key == "related_links":
        links = content.get("related_links", [])
        if not links:
            return ""
        link_items = []
        for link in links:
            if isinstance(link, dict):
                link_items.append(f'<li><a href="{link.get("url", "#")}">{link.get("title", "Link")}</a></li>')
            elif isinstance(link, str):
                link_items.append(f"<li>{link}</li>")
        if not link_items:
            return ""
        links_html = "\n".join(link_items)
        return f"""[section padding="40px"]
[row]
[col span="8" span__sm="12" offset="2"]
[ux_text]
<h3>Related</h3>
<ul>
{links_html}
</ul>
[/ux_text]
[/col]
[/row]
[/section]"""

    return ""
