import re
import json
from fastapi import HTTPException
from emergentintegrations.llm.chat import LlmChat, UserMessage

from database import EMERGENT_LLM_KEY, PAGE_GENERATION_MODEL, QUALITY_SCORING_MODEL, logger
from services.brand_voice import BRAND_VOICE, get_template_for_page


def get_model_provider(model_name: str):
    if model_name.startswith('gpt') or model_name.startswith('o'):
        return 'openai'
    elif model_name.startswith('claude'):
        return 'anthropic'
    elif model_name.startswith('gemini'):
        return 'gemini'
    return 'openai'


async def generate_page_content(page: dict, tone: str = "professional", additional_instructions: str = None, house_template: dict = None, style_profile: dict = None, content_direction: dict = None) -> str:
    template = get_template_for_page(page)
    
    brand_context = f"""
BRAND MOTTO: "{BRAND_VOICE['motto']}"

EMOTIONAL CORE: The brand should feel {', '.join(BRAND_VOICE['emotional_core'][:6])}.

THE VISITOR SHOULD FEEL: {', '.join(BRAND_VOICE['user_should_feel'])}.

COPY PRINCIPLES:
{chr(10).join('- ' + p for p in BRAND_VOICE['copy_principles'])}

AVOID THESE VIBES: {', '.join(BRAND_VOICE['brand_should_NOT_feel'][:6])}.

GOOD PHRASE PATTERNS: {', '.join(BRAND_VOICE['good_phrases'][:4])}
AVOID GENERIC PATTERNS: {', '.join(BRAND_VOICE['avoid_phrases'][:4])}

CTA STYLE: {BRAND_VOICE['cta_style']['principle']}
"""
    
    house_template_context = ""
    if house_template:
        house_template_context = f"""
HOUSE TEMPLATE GUIDANCE (from "{house_template.get('template_name', 'Unnamed')}"):
Use this proven structural pattern as a reference for section flow and emphasis. Do NOT copy verbatim — adapt the structure to this specific page while maintaining the quality patterns.

STRUCTURAL PATTERN:
{house_template.get('structural_pattern', '')}

{f"TONE GUIDANCE: {house_template.get('tone_guidance', '')}" if house_template.get('tone_guidance') else ""}

PURPOSE OF THIS TEMPLATE: {house_template.get('purpose', '')}

IMPORTANT: This template is a guide, not a script. Create original content inspired by this structural quality, not duplicated from it.
"""

    style_profile_context = ""
    if style_profile:
        tc = style_profile.get("tonal_controls", {})
        tonal_desc = []
        if tc.get("warmth", 5) >= 7:
            tonal_desc.append("very warm and inviting")
        elif tc.get("warmth", 5) <= 3:
            tonal_desc.append("cool and measured")
        if tc.get("formality", 5) >= 7:
            tonal_desc.append("polished and formal")
        elif tc.get("formality", 5) <= 3:
            tonal_desc.append("casual and relaxed")
        if tc.get("confidence", 5) >= 7:
            tonal_desc.append("highly confident")
        if tc.get("intimacy", 5) >= 7:
            tonal_desc.append("personally intimate")
        elif tc.get("intimacy", 5) <= 3:
            tonal_desc.append("professional distance")
        if tc.get("playfulness", 5) >= 7:
            tonal_desc.append("playful and light")
        elif tc.get("playfulness", 5) <= 2:
            tonal_desc.append("serious and focused")
        if tc.get("authority", 5) >= 7:
            tonal_desc.append("authoritative and expert")
        
        include_lang = style_profile.get("include_language", [])
        avoid_lang = style_profile.get("avoid_language", [])
        
        style_profile_context = f"""
HOUSE STYLE PROFILE: "{style_profile.get('profile_name', 'Unnamed')}"
{style_profile.get('description', '')}

TONAL DIRECTION: The writing should feel {', '.join(tonal_desc) if tonal_desc else 'balanced and brand-aligned'}.
Tonal dials: Warmth={tc.get('warmth',5)}/10, Formality={tc.get('formality',5)}/10, Confidence={tc.get('confidence',5)}/10, Intimacy={tc.get('intimacy',5)}/10, Playfulness={tc.get('playfulness',5)}/10, Authority={tc.get('authority',5)}/10

{f"EMPHASIZE this language/energy: {', '.join(include_lang)}" if include_lang else ""}
{f"AVOID this language/energy: {', '.join(avoid_lang)}" if avoid_lang else ""}

IMPORTANT: This style profile shapes how the content FEELS, not what it contains. It layers onto the brand voice — it does not replace it.
"""

    content_direction_context = ""
    if content_direction:
        cd_lines = []
        for key, value in content_direction.items():
            if value:
                label = key.replace('_', ' ').title()
                cd_lines.append(f"- {label}: {value}")
        if cd_lines:
            content_direction_context = f"""
FOUNDER CONTENT DIRECTION:
These are specific content guidance inputs from the founder. Follow them closely.
{chr(10).join(cd_lines)}
"""

    system_message = f"""You are an expert content writer for Temporary Satisfaction - a sophisticated adult retail and wellness ecosystem that guides people with care, confidence, discretion, style, and trust.

{brand_context}
{style_profile_context}
CONTENT REQUIREMENTS:
- Matches the specified tone: {tone}
- Embodies the brand motto without repeating it
- Creates emotional resonance, not just information
- Is unique and non-generic - NEVER sounds like template copy
- Feels like THIS brand - intentional, caring, confident
- Every sentence should pass the test: "Does this feel like US?"
- NEVER include system artifacts like "CTA:" prefix in output text
- NEVER use these generic phrases: {', '.join(BRAND_VOICE['avoid_phrases'][:8])}

PAGE FAMILY SPECIFIC REQUIREMENTS:
{template.get('system_additions', '')}
{content_direction_context}
{house_template_context}
OUTPUT STRUCTURE:
{template.get('structure', '')}"""
    
    user_prompt = f"""Generate content for this page:

Page Name: {page.get('page_name')}
Page Family: {page.get('page_family')}
District/Pillar: {page.get('district_or_pillar', 'General')}
Page Type: {page.get('page_type')}
Target Audience: {page.get('audience', 'General audience')}
Purpose: {page.get('purpose', 'Inform and engage')}
CTA Type: {page.get('CTA_type', 'Learn More')}
Keywords/Theme: {page.get('keyword_or_theme', 'N/A')}
Notes: {page.get('notes', 'N/A')}
{f'Additional Instructions: {additional_instructions}' if additional_instructions else ''}

Generate content that embodies "YOUR PASSION IS OUR PLEASURE" - caring, intentional, confident, and distinctly Temporary Satisfaction. NOT generic. NOT template-sounding. Make every word feel like it belongs to THIS brand."""

    try:
        chat = LlmChat(
            api_key=EMERGENT_LLM_KEY,
            session_id=f"page-gen-{page.get('id', 'new')}",
            system_message=system_message
        )
        provider = get_model_provider(PAGE_GENERATION_MODEL)
        chat.with_model(provider, PAGE_GENERATION_MODEL)
        
        response = await chat.send_message(UserMessage(text=user_prompt))
        return response
    except Exception as e:
        logger.error(f"LLM generation error: {e}")
        raise HTTPException(status_code=500, detail=f"Content generation failed: {str(e)}")


async def apply_taste_tightener(content: str, page: dict) -> str:
    content = re.sub(r'(?i)\bCTA:\s*', '', content)
    content = re.sub(r'(?i)\[CTA\]\s*', '', content)
    content = re.sub(r'(?i)CTA\s*—\s*', '', content)
    
    system_message = """You are a sophisticated copy editor for Temporary Satisfaction, tasked with making AI-generated content feel more human, restrained, and authentically branded.

YOUR JOB IS TO TIGHTEN, NOT REWRITE.

REDUCE:
- Over-poetic phrasing (anything that sounds too consciously beautiful)
- "Knowing smile" type language (precious, winking phrases)
- AI symmetry (perfectly balanced emotional phrases)
- Crafted-sounding testimonial lines (too perfect to be real)
- Vague abstract elegance without grounded specifics
- Purple prose moments
- Unnecessary softness or hedging
- Language that sounds polished but slightly unreal

REMOVE COMPLETELY:
- System artifact prefixes like "CTA:", "[CTA]", "Heading:", etc.
- These generic phrases (replace with something brand-specific):
  * "Curated For You" -> replace or remove
  * "Begin Your Journey" -> replace with something less campaign-like
  * "Explore the experience" -> replace with something grounded
  * "Elevated Essentials" -> replace with something specific
  * "Elevate your" -> replace with something direct
  * "Indulge in" -> replace or simplify
  * "Treat yourself to" -> replace with something less cliche
  * "Embark on" -> replace with something natural
  * "Dive into" -> replace with something calmer
  * "Immerse yourself" -> replace with something real

TESTIMONIAL REALISM CHECK:
- If you see quotes that sound like authored marketing copy, make them feel more like real people sharing
- Short fragments beat perfect sentences in testimonials
- "felt... elevated" -> replace with something a real person would say
- Suspiciously articulate quotes should be simplified

KEEP:
- Emotional intelligence
- Warmth
- Trust-building
- Intentionality
- Body-awareness
- Permission-based tone
- The core message and structure

THE TEST:
"Does this sound like a real, tasteful brand with emotional intelligence -- not a beautiful AI trying hard to sound premium?"

Make every line feel:
- Earned, not performed
- Confident, not precious
- Warm, not saccharine
- Direct where possible
- Specific over abstract

Return ONLY the tightened content. No commentary."""

    user_prompt = f"""Tighten this {page.get('page_family')} page content. Keep the structure and core message, but make it feel more real and less AI-polished:

{content}

Remember: Tighten, don't flatten. Keep warmth and intelligence. Remove preciousness."""

    try:
        chat = LlmChat(
            api_key=EMERGENT_LLM_KEY,
            session_id=f"page-tighten-{page.get('id', 'new')}",
            system_message=system_message
        )
        chat.with_model('anthropic', QUALITY_SCORING_MODEL)
        
        response = await chat.send_message(UserMessage(text=user_prompt))
        return response
    except Exception as e:
        logger.error(f"Taste tightener error: {e}")
        return content


async def generate_with_variant(page: dict, variant: str, base_content: str = None) -> str:
    variant_instructions = {
        "luxurious": "Make this more premium and elevated. Use language that suggests quality, care, and sophistication without being pretentious.",
        "warmer": "Make this more personal and comforting. Increase emotional connection and felt care.",
        "direct": "Make this more action-oriented and clear. Reduce softness. Be more confident and straightforward.",
        "trust-heavy": "Emphasize credibility and reassurance. Add more trust signals and reduce purchase anxiety.",
        "educational": "Make this more informative and guiding. Help the reader learn and understand.",
        "commanding": "Make this more confident and authoritative. Speak with certainty and leadership.",
        "feminine": "Make this feel more elegant, intuitive, and emotionally attuned. Softer but not weak.",
        "grounded": "Add more specificity and concrete details. Reduce abstraction. Make it feel real."
    }
    
    instruction = variant_instructions.get(variant, variant)
    
    system_message = f"""You are rewriting page content for Temporary Satisfaction with a specific variant flavor.

BRAND CONTEXT:
Motto: "{BRAND_VOICE['motto']}"
Core: caring, intentional, tasteful, emotionally intelligent

VARIANT INSTRUCTION: {instruction}

Keep:
- The page structure
- The core message
- Brand voice fundamentals
- Emotional intelligence

Change:
- The specific flavor/tone as instructed
- Word choices to match the variant
- Phrasing to embody the requested feel

Return ONLY the rewritten content. No commentary."""

    source_content = base_content or "Generate fresh content matching this variant style."
    
    user_prompt = f"""Rewrite this content with the "{variant}" variant:

{source_content if base_content else f'''
Page: {page.get('page_name')}
Family: {page.get('page_family')}
Type: {page.get('page_type')}
Purpose: {page.get('purpose', 'General')}
Audience: {page.get('audience', 'General')}
'''}

Apply the variant style while maintaining brand integrity."""

    try:
        chat = LlmChat(
            api_key=EMERGENT_LLM_KEY,
            session_id=f"page-variant-{page.get('id', 'new')}-{variant}",
            system_message=system_message
        )
        chat.with_model('openai', PAGE_GENERATION_MODEL)
        
        response = await chat.send_message(UserMessage(text=user_prompt))
        return response
    except Exception as e:
        logger.error(f"Variant generation error: {e}")
        raise HTTPException(status_code=500, detail=f"Variant generation failed: {str(e)}")


async def score_page_quality(page: dict, content: str) -> dict:
    system_message = f"""You are an expert content quality reviewer for Temporary Satisfaction, a sophisticated adult retail and wellness ecosystem.

BRAND CONTEXT:
Motto: "{BRAND_VOICE['motto']}"
The brand should feel: {', '.join(BRAND_VOICE['brand_should_feel'][:8])}
The brand should NOT feel: {', '.join(BRAND_VOICE['brand_should_NOT_feel'][:6])}

Score pages on a 0-100 scale. Be STRICT about brand fit - generic copy should score low.

Return a JSON object with this exact structure (no markdown, just JSON):
{{
    "overall_score": <number 0-100>,
    "category_scores": {{
        "clarity_of_purpose": <number 0-100>,
        "headline_strength": <number 0-100>,
        "emotional_presence": <number 0-100>,
        "brand_voice_fit": <number 0-100>,
        "intentionality": <number 0-100>,
        "warmth_without_fluff": <number 0-100>,
        "cta_fit": <number 0-100>,
        "completeness": <number 0-100>,
        "uniqueness": <number 0-100>,
        "confidence_building": <number 0-100>
    }},
    "classification": "<strong|usable|rewrite>",
    "brand_alignment": "<on-brand|needs-work|off-brand>",
    "weak_areas": ["<area1>", "<area2>"],
    "edit_recommendations": ["<recommendation1>", "<recommendation2>"],
    "generic_flags": ["<any phrases that feel too generic or AI-templated>"]
}}

SCORING GUIDANCE:
- "brand_voice_fit": Does it embody caring, intentional, tasteful, emotionally intelligent?
- "emotional_presence": Does the visitor FEEL something, or is it just information?
- "intentionality": Does every sentence feel purposeful and brand-aligned?
- "warmth_without_fluff": Is it warm but not saccharine or over-written?
- "uniqueness": Does it sound like THIS brand or could it be any website?
- "confidence_building": Would a visitor feel more confident after reading?

FLAG AS GENERIC if you see phrases like: "browse our selection", "quality products", "wide range", "something for everyone", "shop now", "welcome to our store", "curated for you", "begin your journey", "explore the experience", "elevated essentials", "elevate your"

ALSO FLAG any CTA artifacts like "CTA: [text]" -- these are system formatting errors.

PAGE FAMILY SCORING ADJUSTMENTS:
- FAQ/Support/Care pages: Prioritize CLARITY, SCANNABILITY, and UTILITY over emotional_presence. A clear, well-structured support page scoring 75 on emotional_presence but 95 on clarity_of_purpose is BETTER than one that scores 90 on emotional_presence but is hard to scan. Do NOT penalize utility-first pages for being direct.
- Trust pages: Score testimonial sections on REALISM. Overly-polished quotes that sound like authored marketing copy should lower the score. Real-feeling, imperfect quotes should be rewarded.
- District/Category pages: Balance between brand feel and practical usefulness.

Classification thresholds:
- 85-100: strong (ready for review)
- 70-84: usable (needs edits)
- below 70: rewrite (regenerate recommended)"""

    user_prompt = f"""Score this page content for Temporary Satisfaction:

Page Name: {page.get('page_name')}
Page Family: {page.get('page_family')}
Page Type: {page.get('page_type')}
Purpose: {page.get('purpose', 'General')}
Target Audience: {page.get('audience', 'General')}

Content:
{content}

Be strict about brand fit. Generic ecommerce copy should score LOW on brand_voice_fit and uniqueness.
Return only valid JSON, no markdown formatting."""

    try:
        chat = LlmChat(
            api_key=EMERGENT_LLM_KEY,
            session_id=f"page-score-{page.get('id', 'new')}",
            system_message=system_message
        )
        provider = get_model_provider(QUALITY_SCORING_MODEL)
        chat.with_model(provider, QUALITY_SCORING_MODEL)
        
        response = await chat.send_message(UserMessage(text=user_prompt))
        
        clean_response = response.strip()
        if clean_response.startswith('```'):
            clean_response = clean_response.split('\n', 1)[1]
            clean_response = clean_response.rsplit('```', 1)[0]
        
        return json.loads(clean_response)
    except Exception as e:
        logger.error(f"LLM scoring error: {e}")
        return {
            "overall_score": 75,
            "category_scores": {
                "clarity_of_purpose": 75, "headline_strength": 75,
                "emotional_presence": 75, "brand_voice_fit": 75,
                "intentionality": 75, "warmth_without_fluff": 75,
                "cta_fit": 75, "completeness": 75,
                "uniqueness": 75, "confidence_building": 75
            },
            "classification": "usable",
            "brand_alignment": "needs-work",
            "weak_areas": ["Scoring unavailable - manual review recommended"],
            "edit_recommendations": ["Review content manually"],
            "generic_flags": []
        }
