"""
WP Content Formatter — Converts markdown-style generated content into
clean WordPress-ready HTML with proper headings, paragraphs, and lists.
"""
import re


def format_content_for_wp(raw_content: str) -> str:
    """Convert markdown-formatted content into clean WordPress HTML."""
    if not raw_content:
        return ""

    lines = raw_content.split("\n")
    html_parts = []
    in_list = False
    paragraph_buffer = []

    def flush_paragraph():
        nonlocal paragraph_buffer
        if paragraph_buffer:
            text = " ".join(paragraph_buffer).strip()
            if text:
                # Handle inline bold/italic
                text = _inline_formatting(text)
                html_parts.append(f"<p>{text}</p>")
            paragraph_buffer = []

    def flush_list():
        nonlocal in_list
        if in_list:
            html_parts.append("</ul>")
            in_list = False

    for line in lines:
        stripped = line.strip()

        # Empty line = paragraph break
        if not stripped:
            flush_paragraph()
            flush_list()
            continue

        # Heading: ## or ### or ####
        heading_match = re.match(r'^(#{1,4})\s+(.+)$', stripped)
        if heading_match:
            flush_paragraph()
            flush_list()
            level = len(heading_match.group(1))
            text = _inline_formatting(heading_match.group(2).strip())
            # Map: ## → h2, ### → h3, #### → h4
            tag = f"h{min(level, 4)}"
            html_parts.append(f"<{tag}>{text}</{tag}>")
            continue

        # Bullet list: - item or * item
        bullet_match = re.match(r'^[-*]\s+(.+)$', stripped)
        if bullet_match:
            flush_paragraph()
            if not in_list:
                html_parts.append("<ul>")
                in_list = True
            item_text = _inline_formatting(bullet_match.group(1).strip())
            html_parts.append(f"  <li>{item_text}</li>")
            continue

        # Numbered list: 1. item
        numbered_match = re.match(r'^\d+\.\s+(.+)$', stripped)
        if numbered_match:
            flush_paragraph()
            if not in_list:
                html_parts.append("<ol>")
                in_list = True
            item_text = _inline_formatting(numbered_match.group(1).strip())
            html_parts.append(f"  <li>{item_text}</li>")
            continue

        # Horizontal rule
        if stripped in ('---', '***', '___'):
            flush_paragraph()
            flush_list()
            html_parts.append("<hr />")
            continue

        # Close list if we hit non-list content
        if in_list:
            if in_list:
                # Check if it was <ol> or <ul>
                for i in range(len(html_parts) - 1, -1, -1):
                    if html_parts[i] == "<ul>":
                        html_parts.append("</ul>")
                        break
                    elif html_parts[i] == "<ol>":
                        html_parts.append("</ol>")
                        break
                in_list = False

        # Regular text — add to paragraph buffer
        paragraph_buffer.append(stripped)

    # Flush remaining
    flush_paragraph()
    if in_list:
        # Find the matching open tag
        for i in range(len(html_parts) - 1, -1, -1):
            if html_parts[i] in ("<ul>", "<ol>"):
                close_tag = "</ul>" if html_parts[i] == "<ul>" else "</ol>"
                html_parts.append(close_tag)
                break

    return "\n".join(html_parts)


def _inline_formatting(text: str) -> str:
    """Convert inline markdown to HTML (bold, italic, links)."""
    # Bold: **text** or __text__
    text = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', text)
    text = re.sub(r'__(.+?)__', r'<strong>\1</strong>', text)
    # Italic: *text* or _text_
    text = re.sub(r'\*(.+?)\*', r'<em>\1</em>', text)
    # Links: [text](url)
    text = re.sub(r'\[(.+?)\]\((.+?)\)', r'<a href="\2">\1</a>', text)
    return text


def parse_content_into_sections(raw_content: str) -> dict:
    """
    Parse generated markdown content into structured sections for WP templates.
    Returns {hero, intro, body_sections[], cta_text, cta_url}.
    """
    if not raw_content:
        return {"hero": "", "intro": "", "body_sections": []}

    lines = raw_content.strip().split("\n")

    hero = ""
    sections = []
    current_section_title = ""
    current_section_lines = []

    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue

        # Check for heading (## or ###)
        heading_match = re.match(r'^#{1,3}\s+(.+)$', stripped)
        if heading_match:
            # Save previous section
            if current_section_lines:
                sections.append({
                    "title": current_section_title,
                    "content": "\n".join(current_section_lines),
                })
                current_section_lines = []

            heading_text = heading_match.group(1).strip()
            if not hero:
                hero = heading_text
                current_section_title = ""
            else:
                current_section_title = heading_text
            continue

        current_section_lines.append(stripped)

    # Save last section
    if current_section_lines:
        sections.append({
            "title": current_section_title,
            "content": "\n".join(current_section_lines),
        })

    # Extract intro from first section
    intro = ""
    body_sections = []
    for i, sec in enumerate(sections):
        if i == 0 and not sec["title"]:
            # First untitled section = intro
            intro = format_content_for_wp(sec["content"])
        else:
            # Format each section as HTML
            html = ""
            if sec["title"]:
                html += f"<h3>{_inline_formatting(sec['title'])}</h3>\n"
            html += format_content_for_wp(sec["content"])
            body_sections.append(html)

    return {
        "hero": hero,
        "intro": intro,
        "body_sections": body_sections,
    }
