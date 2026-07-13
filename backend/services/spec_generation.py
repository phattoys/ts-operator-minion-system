import json
from emergentintegrations.llm.chat import LlmChat, UserMessage

from database import EMERGENT_LLM_KEY, PAGE_GENERATION_MODEL, QUALITY_SCORING_MODEL, logger


SPEC_TYPE_PROMPTS = {
    "Software Feature": "Focus on: user stories, acceptance criteria, UI/UX requirements, API contracts if relevant, integration points with existing systems, and testability.",
    "Standalone App": "Focus on: target platform(s), core user flows, MVP feature set, tech stack recommendations, deployment considerations, and scalability.",
    "Plugin / Extension": "Focus on: host platform constraints, API/hook integration points, permission requirements, marketplace submission, and compatibility.",
    "GPT / AI Agent": "Focus on: system prompt design, tool/function calling needs, knowledge base requirements, guardrails, conversation flow, and fallback behaviors.",
    "Automation / Workflow": "Focus on: trigger conditions, data flow between steps, error handling at each stage, scheduling, monitoring, and rollback procedures.",
    "Internal Tool": "Focus on: operator workflow, data sources, minimal viable interface, security constraints, and maintenance overhead.",
}


async def generate_spec_content(spec: dict) -> str:
    spec_type = spec.get("spec_type", "Software Feature")
    type_guidance = SPEC_TYPE_PROMPTS.get(spec_type, SPEC_TYPE_PROMPTS["Software Feature"])

    input_answers = spec.get("input_answers", {}) or {}
    answered_sections = []
    labels = {
        "what_is_it": "What is it",
        "who_is_it_for": "Who is it for",
        "what_pain": "What pain does it solve",
        "what_must_it_do": "What must it do",
        "what_to_avoid": "What should it avoid",
        "success_measurement": "How should success be measured",
        "build_timing": "Build now or later",
        "cost_risk_notes": "Cost/risk notes",
    }
    for key, label in labels.items():
        val = input_answers.get(key)
        if val:
            answered_sections.append(f"- {label}: {val}")

    follow_up_answers = spec.get("follow_up_answers", {}) or {}
    follow_up_context = ""
    if follow_up_answers:
        fu_lines = [f"- Q: {q}\n  A: {a}" for q, a in follow_up_answers.items() if a]
        if fu_lines:
            follow_up_context = f"\nFOLLOW-UP ANSWERS (fill gaps from these):\n" + "\n".join(fu_lines)

    system_message = f"""You are a senior technical product manager and spec writer. Your job is to convert rough founder ideas into structured, actionable specifications that builders can execute without back-and-forth.

SPEC TYPE: {spec_type}
TYPE-SPECIFIC GUIDANCE: {type_guidance}

RULES:
- Be specific, not vague. Every acceptance criterion should be testable.
- User stories use "As a [user], I want [action] so that [benefit]" format.
- Scope boundaries must be explicit — what's IN and what's OUT.
- Edge cases matter. Think about failure modes, empty states, rate limits, auth edge cases.
- Complexity estimate should be honest: Simple (1-3 days), Medium (1-2 weeks), Complex (2-6 weeks), Enterprise (6+ weeks).
- The spec should be complete enough that a competent developer can start work without asking clarification questions.
- Use markdown formatting with clear headings and bullet points.
- Do NOT include preamble or meta-commentary. Output the spec directly.

OUTPUT FORMAT:
# [Spec Title]

## Problem Statement
What pain does this solve? For whom?

## User Stories
- As a [user], I want [action] so that [benefit]

## Acceptance Criteria
- [ ] Criterion 1
- [ ] Criterion 2

## Technical Approach
Recommended architecture, stack, or method.

## Scope Definition
### In Scope
- ...
### Out of Scope
- ...

## Edge Cases
- Edge case 1

## Dependencies
External services, APIs, or tools required.

## Success Metrics
How do we know this worked?

## Complexity Estimate
Simple | Medium | Complex | Enterprise — with brief justification.

## Priority
P0 | P1 | P2

## Notes
Additional context or constraints."""

    user_prompt = f"""Generate a complete, build-ready spec for this idea:

TITLE: {spec.get('title', 'Untitled')}
TYPE: {spec_type}
RAW IDEA: {spec.get('raw_idea', '')}
TARGET AUDIENCE: {spec.get('target_audience', 'Not specified')}
PRIORITY: {spec.get('priority', 'P1')}
CONSTRAINTS: {spec.get('constraints', 'None specified')}
REFERENCE LINKS: {', '.join(spec.get('reference_links', [])) or 'None'}

FOUNDER INPUT:
{chr(10).join(answered_sections) if answered_sections else 'No structured input provided — infer what you can from the raw idea.'}
{follow_up_context}

Generate the spec now. Be thorough but concise. Every line should earn its place."""

    try:
        chat = LlmChat(
            api_key=EMERGENT_LLM_KEY,
            session_id=f"spec-gen-{spec.get('id', 'new')}",
            system_message=system_message
        )
        chat.with_model('openai', PAGE_GENERATION_MODEL)
        response = await chat.send_message(UserMessage(text=user_prompt))
        return response
    except Exception as e:
        logger.error(f"Spec generation error: {e}")
        raise


async def score_spec_completeness(spec: dict, content: str) -> dict:
    system_message = """You are a spec quality reviewer. Score the completeness and clarity of a product specification across 6 dimensions.

Return a JSON object with this exact structure (no markdown, just JSON):
{
    "overall_score": <number 0-100>,
    "dimension_scores": {
        "clarity": <number 0-100>,
        "testability": <number 0-100>,
        "scope_definition": <number 0-100>,
        "edge_coverage": <number 0-100>,
        "feasibility": <number 0-100>,
        "handoff_readiness": <number 0-100>
    },
    "classification": "<ready|needs_refinement|major_gaps>",
    "weak_dimensions": ["<dimension1>", "<dimension2>"],
    "follow_up_questions": ["<question addressing the weakest gap>", "<another question if needed>"],
    "strengths": ["<strength1>", "<strength2>"]
}

SCORING GUIDANCE:
- clarity: Is the problem statement unambiguous? Would two different builders interpret it the same way?
- testability: Can each acceptance criterion be verified with a concrete test? Are success metrics measurable?
- scope_definition: Are in-scope and out-of-scope explicitly listed? Would a builder know when to stop?
- edge_coverage: Are failure modes, empty states, auth edges, and error scenarios identified?
- feasibility: Is the technical approach realistic for the stated complexity? Are dependencies identified?
- handoff_readiness: Can a builder start work TODAY without asking clarification questions?

CLASSIFICATION:
- 85-100: ready (can hand off now)
- 70-84: needs_refinement (targeted follow-up questions needed)
- below 70: major_gaps (significant information missing)

FOLLOW-UP QUESTIONS:
- Only generate questions for dimensions scoring below 75.
- Questions must be specific and actionable, not generic.
- Maximum 5 questions. Fewer is better.
- If score >= 85, return empty array for follow_up_questions."""

    user_prompt = f"""Score this spec:

SPEC TYPE: {spec.get('spec_type', 'Unknown')}
TITLE: {spec.get('title', 'Untitled')}

CONTENT:
{content}

Be strict. Generic or vague specs should score low on handoff_readiness and testability.
Return only valid JSON, no markdown formatting."""

    try:
        chat = LlmChat(
            api_key=EMERGENT_LLM_KEY,
            session_id=f"spec-score-{spec.get('id', 'new')}",
            system_message=system_message
        )
        chat.with_model('anthropic', QUALITY_SCORING_MODEL)
        response = await chat.send_message(UserMessage(text=user_prompt))

        clean = response.strip()
        if clean.startswith('```'):
            clean = clean.split('\n', 1)[1]
            clean = clean.rsplit('```', 1)[0]
        return json.loads(clean)
    except Exception as e:
        logger.error(f"Spec scoring error: {e}")
        return {
            "overall_score": 70,
            "dimension_scores": {
                "clarity": 70, "testability": 70, "scope_definition": 70,
                "edge_coverage": 70, "feasibility": 70, "handoff_readiness": 70,
            },
            "classification": "needs_refinement",
            "weak_dimensions": ["Scoring unavailable"],
            "follow_up_questions": ["Manual review recommended"],
            "strengths": [],
        }
