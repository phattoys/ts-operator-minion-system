"""
Goal to Execution Map — Takes messy founder goals and returns structured execution plans.
Persisted to MongoDB as reusable operating assets.
"""
import json
import uuid
import re
from datetime import datetime, timezone

from emergentintegrations.llm.chat import LlmChat, UserMessage
from database import db, EMERGENT_LLM_KEY, PAGE_GENERATION_MODEL, logger


EXECUTION_MAP_SYSTEM = """You are an execution planning system for a founder running a retail/digital ecosystem called Temporary Satisfaction. 

The founder has these active minions/tools:
- Page Ops: page creation, scoring, review queue, content generation
- Worker Queue: task routing to Jenny (copy), Rene (QA), Sam (packs), WP Placement
- WP Placement: WordPress draft creation from approved pages
- Field-to-Listing: photo batch → product listings via Vision AI
- Product Intake: invoice/order parsing → draft products
- Catalog Minion: product normalization, categorization, WooCommerce export
- Lead Magnet Minion: lead magnet creation + opt-in/email copy
- Spec Writer: idea → structured build spec
- Customer Comms: brand-right communication drafting
- Execution Spine: cross-module orchestration

The founder also works on:
- Grant writing and submissions
- Ad tools (Ad Foundry, QuickPost)
- SEO tools (TS SEO Boost)
- Digital products (Prompt Vault, Grant Pack, SEO Quick Win Kit)
- Physical retail store in Long Beach

When given a messy goal or brain dump, return a structured execution map.

Return ONLY valid JSON with this structure:
{
  "main_goal": "One clear sentence of what we're really trying to achieve",
  "phases": [
    {
      "name": "Phase name",
      "description": "What happens in this phase",
      "outcome": "What is done when this phase completes",
      "estimated_effort": "light/medium/heavy"
    }
  ],
  "first_actions": [
    {
      "action": "Specific action to take",
      "owner": "who should do this (Crystal, Page Ops, Worker Queue, etc.)",
      "priority": "high/medium/low"
    }
  ],
  "dependencies": [
    {
      "blocker": "What must happen first",
      "blocks": "What it blocks",
      "status": "ready/waiting/unknown"
    }
  ],
  "minion_ownership": [
    {
      "minion": "Minion/tool name",
      "responsibility": "What it owns in this plan"
    }
  ],
  "crystal_first_move": "The single most important thing Crystal should do right now to start this plan moving"
}

Rules:
- Keep phases to 3-6 max
- Keep first_actions to 3-7 max
- Be practical, not theoretical
- Use the founder's actual tools and systems in recommendations
- crystal_first_move should be ONE clear action, not a paragraph
- If timeframe is given, respect it in phase planning
- Dependencies should only include real blockers, not obvious sequences
- Return ONLY valid JSON, no markdown fences"""


async def generate_execution_map(goal_input: str, timeframe: str = "", priority: str = "", main_lane: str = "") -> dict:
    """Generate an execution map from a messy founder goal."""

    # Build prompt
    prompt_parts = [f"GOAL: {goal_input}"]
    if timeframe:
        prompt_parts.append(f"TIMEFRAME: {timeframe}")
    if priority:
        prompt_parts.append(f"PRIORITY: {priority}")
    if main_lane:
        prompt_parts.append(f"MAIN LANE: {main_lane}")

    prompt = "\n".join(prompt_parts) + "\n\nGenerate execution map. Return JSON only."

    try:
        chat = LlmChat(
            api_key=EMERGENT_LLM_KEY,
            session_id=f"exec-map-{uuid.uuid4().hex[:8]}",
            system_message=EXECUTION_MAP_SYSTEM,
        )
        chat.with_model('openai', PAGE_GENERATION_MODEL)

        msg = UserMessage(text=prompt)
        response = await chat.send_message(msg)

        clean = response.strip()
        if clean.startswith('```'):
            clean = clean.split('\n', 1)[1]
            clean = clean.rsplit('```', 1)[0]

        try:
            result = json.loads(clean, strict=False)
        except (json.JSONDecodeError, ValueError):
            match = re.search(r'\{.*\}', clean, re.DOTALL)
            if match:
                result = json.loads(match.group(), strict=False)
            else:
                return {"error": "Could not parse execution map from LLM response"}

        return result

    except Exception as e:
        logger.error(f"[Execution Map] Generation failed: {e}")
        return {"error": str(e)[:300]}


async def save_execution_map(goal_input: str, timeframe: str, priority: str, main_lane: str, map_data: dict) -> dict:
    """Persist an execution map to MongoDB."""
    now = datetime.now(timezone.utc).isoformat()

    doc = {
        "id": str(uuid.uuid4()),
        "goal_input": goal_input,
        "timeframe": timeframe,
        "priority": priority,
        "main_lane": main_lane,
        "main_goal": map_data.get("main_goal", ""),
        "phases": map_data.get("phases", []),
        "first_actions": map_data.get("first_actions", []),
        "dependencies": map_data.get("dependencies", []),
        "minion_ownership": map_data.get("minion_ownership", []),
        "crystal_first_move": map_data.get("crystal_first_move", ""),
        "status": "active",
        "created_at": now,
        "updated_at": now,
    }

    await db.execution_maps.insert_one(doc)
    logger.info(f"[Execution Map] Saved: {map_data.get('main_goal', '')[:60]}")
    return {k: v for k, v in doc.items() if k != "_id"}
