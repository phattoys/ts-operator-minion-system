# Spec Writer Minion — Build-Ready Spec (v1)

> Decisions locked by founder. Ready for implementation.

---

## 1. Purpose

Convert rough founder ideas into structured, actionable specifications that builders (devs, designers, AI agents) can execute against without back-and-forth. Reduce bad dev spend by ensuring every build starts with a tight, complete spec.

---

## 2. Locked Decisions

| Decision | Choice |
|----------|--------|
| **Spec Types** | 6 types (Software Feature, Standalone App, Plugin/Extension, GPT/AI Agent, Automation/Workflow, Internal Tool) |
| **Clarifying Q&A** | Batch-first with targeted follow-up. Show all key questions at once. Only ask follow-up if critical gaps remain after first spec draft. |
| **Server Split** | Done. `routes/page_ops.py` + `routes/shared.py` + shared core. Spec Writer will get its own `routes/spec_writer.py`. |

---

## 3. Founder Workflow

```
1. Founder opens Spec Writer → New Spec
2. Fills in:
   - Raw idea (required, free text)
   - Spec type (required, dropdown)
   - Target audience (optional)
   - Priority (optional: P0/P1/P2)
   - Constraints (optional)
   - Reference links (optional)
3. System presents structured input form:
   - What is it?
   - Who is it for?
   - What pain does it solve?
   - What must it do?
   - What should it avoid?
   - How should success be measured?
   - Build now or later?
   - Cost/risk notes
   → Founder fills what matters, skips the rest
4. GPT-5.2 generates structured spec draft
5. Claude Sonnet 4.5 scores completeness (0-100 across 6 dimensions)
6. If score < threshold → system asks ONLY the missing critical questions
7. Founder reviews, edits inline, approves
8. Spec saved to library with version history
9. Export: copy / download .md
```

---

## 4. Spec Types

| Type | Description |
|------|-------------|
| **Software Feature** | A feature for an existing or new software product |
| **Standalone App** | A complete application or SaaS product |
| **Plugin / Extension** | Add-on for existing platforms (Shopify, Chrome, etc.) |
| **GPT / AI Agent** | Custom GPT, AI agent, or LLM-powered tool |
| **Automation / Workflow** | Automated process, integration, or workflow |
| **Internal Tool** | Internal operations tool for the founder/team |

---

## 5. Spec Output Structure

```markdown
# [Spec Title]

## Problem Statement
What pain does this solve? For whom?

## User Stories
- As a [user], I want [action] so that [benefit]
- ...

## Acceptance Criteria
- [ ] Criterion 1
- [ ] Criterion 2
- ...

## Technical Approach
Recommended architecture, stack, or method.

## Scope Definition
### In Scope
- ...
### Out of Scope
- ...

## Edge Cases
- Edge case 1
- Edge case 2

## Dependencies
External services, APIs, or tools required.

## Success Metrics
How do we know this worked?

## Complexity Estimate
Simple | Medium | Complex | Enterprise

## Priority
P0 | P1 | P2

## Notes
Additional founder context or constraints.
```

---

## 6. Completeness Scoring (6 Dimensions)

| Dimension | What It Measures |
|-----------|-----------------|
| **Clarity** | Is the problem statement unambiguous? |
| **Testability** | Can acceptance criteria be verified? |
| **Scope Definition** | Are boundaries clear (in/out of scope)? |
| **Edge Coverage** | Are failure modes and edge cases identified? |
| **Feasibility** | Is the technical approach realistic? |
| **Handoff Readiness** | Can a builder start work without questions? |

**Scoring thresholds:**
- 85-100: Ready to hand off
- 70-84: Needs refinement (targeted follow-up)
- Below 70: Major gaps (auto-generate follow-up questions)

---

## 7. Status Flow

```
Draft → Scored → Needs Refinement → Ready → Handed Off → Archived
```

| Status | Description |
|--------|-------------|
| **Draft** | Initial creation, not yet generated |
| **Scored** | Spec generated and scored |
| **Needs Refinement** | Score below threshold, follow-up needed |
| **Ready** | Approved by founder, ready for handoff |
| **Handed Off** | Given to a builder |
| **Archived** | Completed or abandoned |

---

## 8. Database Collections

### `specs`
```json
{
  "id": "uuid",
  "title": "string",
  "spec_type": "string (one of 6 types)",
  "raw_idea": "string",
  "target_audience": "string?",
  "priority": "P0|P1|P2",
  "constraints": "string?",
  "reference_links": ["string"],
  "input_answers": {
    "what_is_it": "string?",
    "who_is_it_for": "string?",
    "what_pain": "string?",
    "what_must_it_do": "string?",
    "what_to_avoid": "string?",
    "success_measurement": "string?",
    "build_timing": "string?",
    "cost_risk_notes": "string?"
  },
  "generated_spec": "string (markdown)",
  "completeness_score": "int 0-100",
  "score_breakdown": {
    "clarity": "int",
    "testability": "int",
    "scope_definition": "int",
    "edge_coverage": "int",
    "feasibility": "int",
    "handoff_readiness": "int"
  },
  "complexity_estimate": "Simple|Medium|Complex|Enterprise",
  "follow_up_questions": ["string"],
  "follow_up_answers": {"question": "answer"},
  "status": "Draft|Scored|Needs Refinement|Ready|Handed Off|Archived",
  "created_at": "datetime",
  "updated_at": "datetime"
}
```

### `spec_versions`
```json
{
  "id": "uuid",
  "spec_id": "uuid",
  "version_number": "int",
  "generated_spec": "string",
  "completeness_score": "int?",
  "score_breakdown": "object?",
  "generation_trigger": "initial|follow_up|manual_edit",
  "created_at": "datetime",
  "is_current": "bool"
}
```

---

## 9. API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/specs` | List all specs (filter by type, status, priority) |
| POST | `/api/specs` | Create new spec (raw idea + type) |
| GET | `/api/specs/{id}` | Get single spec |
| PUT | `/api/specs/{id}` | Update spec metadata |
| DELETE | `/api/specs/{id}` | Delete spec |
| POST | `/api/specs/{id}/generate` | Generate spec from inputs (GPT-5.2) |
| POST | `/api/specs/{id}/score` | Score spec completeness (Claude) |
| POST | `/api/specs/{id}/follow-up` | Submit follow-up answers, regenerate |
| GET | `/api/specs/{id}/versions` | List spec versions |
| POST | `/api/specs/{id}/versions/{vid}/restore` | Restore a version |
| GET | `/api/specs/{id}/export` | Export spec as markdown |
| POST | `/api/specs/{id}/status` | Update spec status |
| GET | `/api/specs/stats` | Spec library stats |

---

## 10. Frontend Pages

| Page | Route | Purpose |
|------|-------|---------|
| **Spec Library** | `/specs` | List all specs with filters, search, stats |
| **Spec Workspace** | `/specs/:id` | Create/view/edit/generate/score a single spec |

---

## 11. Integration with Existing System

| Aspect | How |
|--------|-----|
| Auth | Same password (TSFounder!Vault2026#Secure) |
| Nav | Add "Spec Writer" section in sidebar (below Page Ops modules) |
| Backend | New `routes/spec_writer.py` alongside `routes/page_ops.py` |
| LLM | Same Emergent Universal Key, GPT-5.2 for generation, Claude for scoring |
| DB | Same MongoDB, new collections: `specs`, `spec_versions` |
| Activity | Shares `activity_logs` collection |
| Design | Same dark terminal UI, Tailwind + Shadcn |

---

## 12. What v1 Does NOT Include

- No collaboration/multi-user
- No Jira/Linear/Notion sync
- No voice input processing
- No code generation
- No recursive spec splitting
- No template marketplace
- No cost estimation beyond complexity labels
- No auto-assignment to builders

---

## 13. Implementation Plan

### Phase 1: Backend Foundation
- Spec models in `models.py`
- CRUD endpoints in `routes/spec_writer.py`
- Version history (reuse pattern from page_versions)
- Register router in `server.py`

### Phase 2: Spec Generation
- GPT-5.2 prompt for structured spec output
- Type-specific prompt variations
- Input answers folded into generation context

### Phase 3: Completeness Scoring
- Claude Sonnet 4.5 scoring across 6 dimensions
- Threshold-based follow-up question generation
- Score storage and version tracking

### Phase 4: Frontend
- Spec Library page with filters
- Spec Workspace (input form + generated output + scoring + follow-up Q&A)
- Nav integration
- Export functionality

### Phase 5: Polish
- Status flow management
- Activity logging
- Stats dashboard integration
