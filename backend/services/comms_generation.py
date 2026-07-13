import json
from fastapi import HTTPException
from emergentintegrations.llm.chat import LlmChat, UserMessage

from database import EMERGENT_LLM_KEY, PAGE_GENERATION_MODEL, logger
from services.brand_voice import BRAND_VOICE
from models import COMMS_SCENARIOS


BRAND_COMMS_CONTEXT = f"""You are a customer communication specialist for Temporary Satisfaction — a sophisticated adult wellness brand.

BRAND MOTTO: "{BRAND_VOICE['motto']}"
EMOTIONAL CORE: {', '.join(BRAND_VOICE['emotional_core'][:6])}
COPY PRINCIPLES:
{chr(10).join('- ' + p for p in BRAND_VOICE['copy_principles'])}
MUST AVOID: {', '.join(BRAND_VOICE['brand_should_NOT_feel'][:6])}
GOOD PHRASES: {', '.join(BRAND_VOICE['good_phrases'][:4])}
AVOID PHRASES: {', '.join(BRAND_VOICE['avoid_phrases'][:6])}

CRITICAL RULES FOR CUSTOMER COMMUNICATIONS:
- Always be calm, warm, respectful, and discreet
- Never use crude or explicit language — use brand-approved euphemisms only
- Never make medical claims — if health questions arise, redirect to a professional
- Never fabricate order facts — if information is missing, use [PLACEHOLDER] brackets
- Treat every customer with dignity and zero judgment
- Prioritize de-escalation for upset customers
- Keep billing/packaging discretion language reassuring and clear"""


CHANNEL_INSTRUCTIONS = {
    "email": "Format as a professional email. Include a Subject line, greeting, body paragraphs, and warm sign-off. Sign as 'The Temporary Satisfaction Team'.",
    "sms": "Format as a concise SMS message. Keep under 320 characters. No subject line. Warm but brief. Include a link placeholder if relevant.",
    "chat": "Format as a live chat response. Conversational, warm, slightly more casual than email. No subject line. Break into short paragraphs.",
}

DISCRETION_INSTRUCTION = """MAXIMUM DISCRETION MODE ACTIVE:
- Do NOT mention specific product types, categories, or adult-industry terms
- Use neutral language like 'your order', 'your item', 'your purchase'
- Minimize brand name mentions in the message body
- Keep language that could appear on a screen completely neutral
- Avoid any terms that could identify the product category to someone reading over the customer's shoulder"""


def get_scenario(key: str) -> dict:
    for s in COMMS_SCENARIOS:
        if s["key"] == key:
            return s
    return None


def check_missing_fields(scenario: dict, context_fields: dict, allow_placeholders: bool) -> list:
    missing = []
    for field in scenario.get("required_fields", []):
        val = context_fields.get(field, "").strip()
        if not val:
            missing.append(field)
    if missing and not allow_placeholders:
        return missing
    return []


async def generate_comms_draft(
    scenario_key: str,
    channel: str,
    customer_message: str,
    context_fields: dict,
    max_discretion: bool,
    use_placeholders: bool,
) -> dict:
    scenario = get_scenario(scenario_key)
    if not scenario:
        raise HTTPException(status_code=400, detail=f"Unknown scenario: {scenario_key}")

    # Build context block from fields
    context_lines = []
    for field, value in context_fields.items():
        if value and value.strip():
            context_lines.append(f"- {field.replace('_', ' ').title()}: {value}")

    # Note missing required fields that will use placeholders
    missing_required = []
    for field in scenario.get("required_fields", []):
        if not context_fields.get(field, "").strip():
            missing_required.append(field)

    system_message = f"""{BRAND_COMMS_CONTEXT}

{DISCRETION_INSTRUCTION if max_discretion else ""}

You are generating a customer communication draft for this scenario: **{scenario['label']}**

CHANNEL: {channel.upper()}
{CHANNEL_INSTRUCTIONS.get(channel, CHANNEL_INSTRUCTIONS['email'])}

Generate exactly 3 variants:
1. **Short** — concise, warm, gets to the point quickly
2. **Standard** — thorough, caring, covers all bases
3. **Extra-Careful** — maximum reassurance, extra empathy, explicit discretion, de-escalation language

{f"PLACEHOLDER FIELDS: The following required fields are missing. Use [FIELD_NAME] placeholders: {', '.join(missing_required)}" if missing_required and use_placeholders else ""}

Return a JSON object (no markdown fences):
{{
    "subject": "email subject line (null for SMS/chat)",
    "variants": [
        {{
            "type": "short",
            "body": "the message text"
        }},
        {{
            "type": "standard",
            "body": "the message text"
        }},
        {{
            "type": "extra_careful",
            "body": "the message text"
        }}
    ],
    "ps_line": "optional P.S. line or null"
}}"""

    user_prompt = f"""Draft a {channel} response for scenario: {scenario['label']}

Known facts:
{chr(10).join(context_lines) if context_lines else '- No specific details provided'}

{f"Customer's message:{chr(10)}{customer_message}" if customer_message else "No customer message provided — generate proactive outreach."}

Generate 3 brand-right variants (Short, Standard, Extra-Careful)."""

    try:
        chat = LlmChat(
            api_key=EMERGENT_LLM_KEY,
            session_id=f"comms-{scenario_key}-{hash(str(context_fields))}"[:50],
            system_message=system_message
        )
        chat.with_model('openai', PAGE_GENERATION_MODEL)
        response = await chat.send_message(UserMessage(text=user_prompt))

        clean = response.strip()
        if clean.startswith('```'):
            clean = clean.split('\n', 1)[1]
            clean = clean.rsplit('```', 1)[0]

        result = json.loads(clean)

        # Validate structure
        if "variants" not in result or not isinstance(result["variants"], list):
            raise ValueError("Missing variants array")
        if len(result["variants"]) < 3:
            raise ValueError("Expected 3 variants")

        return result
    except json.JSONDecodeError:
        logger.error("LLM returned non-JSON for comms generation")
        raise HTTPException(status_code=500, detail="Generation returned invalid format. Try again.")
    except Exception as e:
        logger.error(f"Comms generation error: {e}")
        raise HTTPException(status_code=500, detail=f"Generation failed: {str(e)}")
