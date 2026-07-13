import json
import io
import os
import markdown
from fpdf import FPDF
from fastapi import HTTPException
from emergentintegrations.llm.chat import LlmChat, UserMessage

from database import EMERGENT_LLM_KEY, PAGE_GENERATION_MODEL, QUALITY_SCORING_MODEL, logger
from services.brand_voice import BRAND_VOICE


BRAND_SYSTEM_CONTEXT = f"""You are a content creator for Temporary Satisfaction - a sophisticated adult retail and wellness ecosystem.

BRAND MOTTO: "{BRAND_VOICE['motto']}"
EMOTIONAL CORE: {', '.join(BRAND_VOICE['emotional_core'][:6])}
COPY PRINCIPLES:
{chr(10).join('- ' + p for p in BRAND_VOICE['copy_principles'])}
AVOID: {', '.join(BRAND_VOICE['brand_should_NOT_feel'][:6])}
GOOD PHRASES: {', '.join(BRAND_VOICE['good_phrases'][:4])}
AVOID PHRASES: {', '.join(BRAND_VOICE['avoid_phrases'][:6])}

The content must feel caring, intentional, tasteful, and emotionally intelligent. Never crude, never clinical, never generic."""


FORMAT_GUIDANCE = {
    "Guide": "Create a structured guide with clear sections, explanations, and actionable advice. Use headings (##) for sections. Include an introduction and conclusion.",
    "Checklist": "Create a checklist format with clear items the reader can check off. Group items into logical categories. Each item should be actionable and specific.",
    "Resource List": "Create a curated resource list organized by category. Each resource should have a brief description of why it matters. Include practical tips alongside resources.",
    "FAQ": "Create a well-organized FAQ with questions the target audience actually asks. Answers should be thorough but concise. Group questions by theme.",
    "Quiz": "Create a text-based self-assessment quiz with 8-12 questions. Each question should have 3-4 options. Include a scoring guide and personalized result descriptions at the end.",
}

LENGTH_GUIDANCE = {
    "Short (1-2 pages)": "Keep content concise - roughly 600-1000 words. Focus on the most essential points only.",
    "Standard (3-5 pages)": "Provide thorough coverage - roughly 1500-3000 words. Include examples and practical details.",
    "Deep (6-10 pages)": "Create comprehensive content - roughly 3000-6000 words. Include detailed explanations, multiple examples, and deep expertise.",
}


async def generate_lead_magnet_content(lead_magnet: dict) -> dict:
    fmt = lead_magnet.get("format_type", "Guide")
    length = lead_magnet.get("length", "Standard (3-5 pages)")

    system_message = f"""{BRAND_SYSTEM_CONTEXT}

You are creating a downloadable lead magnet ({fmt}) for the Temporary Satisfaction ecosystem.

FORMAT: {FORMAT_GUIDANCE.get(fmt, FORMAT_GUIDANCE['Guide'])}
LENGTH: {LENGTH_GUIDANCE.get(length, LENGTH_GUIDANCE['Standard (3-5 pages)'])}

{"Include a tasteful disclaimer block at the end reminding readers this is educational content, not medical advice, and encouraging them to consult professionals for personal health decisions." if lead_magnet.get("include_disclaimer", True) else ""}

Return a JSON object (no markdown fences) with this exact structure:
{{
    "title": "compelling title for the lead magnet",
    "subtitle": "optional subtitle or tagline",
    "description": "1-2 sentence description for listings",
    "markdown_content": "the full content in markdown format with ## headings, lists, etc.",
    "landing_headline": "attention-grabbing headline for the landing page snippet (max 15 words)",
    "landing_body": "compelling description for the landing page (50-120 words)",
    "landing_cta": "CTA button text (2-5 words)",
    "suggested_filename": "slug-style-filename"
}}"""

    user_prompt = f"""Create a lead magnet with these details:

Topic: {lead_magnet.get('topic')}
Target Audience: {lead_magnet.get('target_audience')}
Format: {fmt}
District/Area: {lead_magnet.get('district_tag', 'General')}
{f"Content Direction: {lead_magnet.get('content_direction')}" if lead_magnet.get('content_direction') else ""}

Generate content that feels authentically Temporary Satisfaction - caring, intentional, and confidence-building. Not generic marketing fluff."""

    try:
        chat = LlmChat(
            api_key=EMERGENT_LLM_KEY,
            session_id=f"lm-gen-{lead_magnet.get('id', 'new')}",
            system_message=system_message
        )
        chat.with_model('openai', PAGE_GENERATION_MODEL)
        response = await chat.send_message(UserMessage(text=user_prompt))

        clean = response.strip()
        if clean.startswith('```'):
            clean = clean.split('\n', 1)[1]
            clean = clean.rsplit('```', 1)[0]

        result = json.loads(clean)
        required = ["title", "markdown_content", "landing_headline", "landing_body", "landing_cta"]
        for field in required:
            if not result.get(field):
                raise ValueError(f"Missing required field: {field}")
        return result
    except json.JSONDecodeError:
        logger.error("LLM returned non-JSON for lead magnet generation")
        raise HTTPException(status_code=500, detail="Content generation returned invalid format. Try again.")
    except Exception as e:
        logger.error(f"Lead magnet generation error: {e}")
        raise HTTPException(status_code=500, detail=f"Content generation failed: {str(e)}")


def sanitize_text_for_pdf(text: str) -> str:
    """Replace Unicode characters with ASCII equivalents for PDF compatibility"""
    if not text:
        return text
    replacements = {
        '\u2018': "'",  # Left single quote
        '\u2019': "'",  # Right single quote (apostrophe)
        '\u201C': '"',  # Left double quote
        '\u201D': '"',  # Right double quote
        '\u2013': '-',  # En dash
        '\u2014': '--', # Em dash
        '\u2011': '-',  # Non-breaking hyphen
        '\u2010': '-',  # Hyphen
        '\u2026': '...', # Ellipsis
        '\u00A0': ' ',  # Non-breaking space
        '\u2022': '-',  # Bullet
        '\u00B7': '-',  # Middle dot
        '\u2032': "'",  # Prime
        '\u2033': '"',  # Double prime
        '\u00AB': '"',  # Left guillemet
        '\u00BB': '"',  # Right guillemet
        '\u201A': ',',  # Single low quote
        '\u201E': '"',  # Double low quote
        '\u2212': '-',  # Minus sign
        '\u00AD': '',   # Soft hyphen (remove)
        '\u2015': '--', # Horizontal bar
        '\u2017': '_',  # Double low line
        '\u2039': '<',  # Single left angle quote
        '\u203A': '>',  # Single right angle quote
        '\u2020': '+',  # Dagger
        '\u2021': '++', # Double dagger
        '\u2122': '(TM)', # Trademark
        '\u00A9': '(c)', # Copyright
        '\u00AE': '(R)', # Registered
        '\u2116': 'No.', # Numero sign
    }
    for unicode_char, ascii_char in replacements.items():
        text = text.replace(unicode_char, ascii_char)
    
    # More aggressive: replace any non-ASCII character with a space or remove
    result = []
    for char in text:
        if ord(char) < 128:
            result.append(char)
        elif char in replacements.values():
            result.append(char)
        else:
            # Replace unknown unicode with space
            result.append(' ')
    return ''.join(result)


class BrandedPDF(FPDF):
    def __init__(self, title="", subtitle=""):
        super().__init__()
        self._doc_title = title
        self._doc_subtitle = subtitle

    def header(self):
        # Simple header without complex layout
        self.set_font("Helvetica", "B", 9)
        self.set_text_color(120, 120, 120)
        self.cell(0, 8, "TEMPORARY SATISFACTION", align="L", new_x="LMARGIN", new_y="NEXT")
        self.set_draw_color(60, 60, 60)
        self.line(self.l_margin, self.get_y(), self.w - self.r_margin, self.get_y())
        self.ln(4)

    def footer(self):
        self.set_y(-15)
        self.set_font("Helvetica", "", 7)
        self.set_text_color(120, 120, 120)
        self.cell(0, 6, f"temporarysatisfaction.com - Page {self.page_no()}", align="C")


def generate_pdf_bytes(lead_magnet: dict) -> bytes:
    title = sanitize_text_for_pdf(lead_magnet.get("title", "Lead Magnet"))
    subtitle = sanitize_text_for_pdf(lead_magnet.get("subtitle", ""))
    content = sanitize_text_for_pdf(lead_magnet.get("markdown_content", ""))
    disclaimer = lead_magnet.get("include_disclaimer", True)

    # Use basic FPDF without custom header/footer to avoid layout issues
    pdf = FPDF()
    pdf.set_margins(25, 25, 25)  # very generous margins
    pdf.set_auto_page_break(auto=True, margin=25)
    pdf.add_page()

    # Brand header
    pdf.set_font("Helvetica", "B", 9)
    pdf.set_text_color(120, 120, 120)
    pdf.cell(0, 8, "TEMPORARY SATISFACTION", align="L", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(5)

    # Title
    pdf.set_font("Helvetica", "B", 16)
    pdf.set_text_color(30, 30, 30)
    pdf.multi_cell(0, 8, title, new_x="LMARGIN", new_y="NEXT")
    if subtitle:
        pdf.set_font("Helvetica", "I", 10)
        pdf.set_text_color(100, 100, 100)
        pdf.multi_cell(0, 6, subtitle, new_x="LMARGIN", new_y="NEXT")
    pdf.ln(5)

    # Parse markdown to structured content
    lines = content.split('\n')
    for idx, line in enumerate(lines):
        stripped = line.strip()
        if not stripped:
            pdf.ln(3)
            continue

        # Remove markdown bold markers for simpler rendering
        clean_text = stripped.replace('**', '')
        
        # Check for indentation (nested items)
        indent_level = len(line) - len(line.lstrip())
        indent_prefix = "    " if indent_level > 0 else ""
        
        try:
            if stripped.startswith('### '):
                pdf.ln(3)
                pdf.set_font("Helvetica", "B", 11)
                pdf.set_text_color(50, 50, 50)
                pdf.multi_cell(0, 6, clean_text[4:], new_x="LMARGIN", new_y="NEXT")
                pdf.ln(2)
            elif stripped.startswith('## '):
                pdf.ln(4)
                pdf.set_font("Helvetica", "B", 13)
                pdf.set_text_color(30, 30, 30)
                pdf.multi_cell(0, 7, clean_text[3:], new_x="LMARGIN", new_y="NEXT")
                pdf.ln(2)
            elif stripped.startswith('# '):
                pass  # Skip H1, we already have the title
            elif stripped.startswith('- [ ]') or stripped.startswith('- [x]'):
                # Checkbox items
                pdf.set_font("Helvetica", "", 9)
                pdf.set_text_color(40, 40, 40)
                checkbox = "[ ]" if '[ ]' in stripped else "[x]"
                item_text = stripped.replace('- [ ]', '').replace('- [x]', '').strip()
                item_text = item_text.replace('**', '')
                pdf.multi_cell(0, 5, f"{indent_prefix}{checkbox} {item_text}", new_x="LMARGIN", new_y="NEXT")
            elif stripped.startswith('- ') or stripped.startswith('* '):
                pdf.set_font("Helvetica", "", 9)
                pdf.set_text_color(40, 40, 40)
                bullet_text = clean_text[2:]
                pdf.multi_cell(0, 5, f"{indent_prefix}- {bullet_text}", new_x="LMARGIN", new_y="NEXT")
            elif len(stripped) > 0 and stripped[0].isdigit() and '. ' in stripped[:4]:
                pdf.set_font("Helvetica", "", 9)
                pdf.set_text_color(40, 40, 40)
                pdf.multi_cell(0, 5, f"{indent_prefix}{clean_text}", new_x="LMARGIN", new_y="NEXT")
            elif stripped.startswith('>'):
                pdf.ln(2)
                pdf.set_fill_color(245, 245, 245)
                pdf.set_font("Helvetica", "I", 9)
                pdf.set_text_color(80, 80, 80)
                callout = clean_text.lstrip('> ')
                pdf.multi_cell(0, 5, f"  {callout}  ", fill=True, new_x="LMARGIN", new_y="NEXT")
                pdf.ln(2)
            else:
                pdf.set_font("Helvetica", "", 9)
                pdf.set_text_color(40, 40, 40)
                pdf.multi_cell(0, 5, clean_text, new_x="LMARGIN", new_y="NEXT")
        except Exception as line_err:
            logger.error(f"PDF error at line {idx}: {line_err}, text: {clean_text[:50] if clean_text else 'empty'}")
            # Skip problematic line and continue
            continue

    # Disclaimer
    if disclaimer:
        pdf.ln(10)
        pdf.set_draw_color(180, 180, 180)
        pdf.line(pdf.l_margin, pdf.get_y(), pdf.w - pdf.r_margin, pdf.get_y())
        pdf.ln(6)
        pdf.set_font("Helvetica", "I", 8)
        pdf.set_text_color(120, 120, 120)
        pdf.multi_cell(0, 5,
            "Disclaimer: This content is provided for educational and informational purposes only. "
            "It is not intended as medical, therapeutic, or professional health advice. "
            "Please consult qualified professionals for personal health decisions. "
            "Temporary Satisfaction encourages informed, consent-forward exploration.",
            new_x="LMARGIN", new_y="NEXT"
        )

    return pdf.output()


def generate_embed_code(lead_magnet: dict, download_url: str) -> str:
    headline = lead_magnet.get("landing_headline", "")
    body = lead_magnet.get("landing_body", "")
    cta = lead_magnet.get("landing_cta", "Download Now")
    public_id = lead_magnet.get("public_id", "")

    return f"""<!-- Temporary Satisfaction Lead Magnet -->
<div data-ts-leadmagnet-id="{public_id}" style="max-width:480px;padding:24px;border:1px solid #e5e7eb;border-radius:8px;font-family:system-ui,sans-serif;">
  <h3 style="margin:0 0 8px;font-size:18px;color:#1a1a1a;">{headline}</h3>
  <p style="margin:0 0 16px;font-size:14px;color:#6b7280;line-height:1.5;">{body}</p>
  <a href="{download_url}" style="display:inline-block;padding:10px 24px;background:#1a1a1a;color:#fff;text-decoration:none;font-size:14px;font-weight:500;border-radius:4px;">{cta}</a>
  <p style="margin:8px 0 0;font-size:11px;color:#9ca3af;">Connect CTA to your email capture form URL</p>
</div>"""
