# Execution Manifest Workspace — Frontend (Phase 2)

Founder-facing review and execution workspace connected to the
known-good Phase 1 backend (`services/execution_manifest.py`,
`routes/execution_manifest.py`). This is not a mock-up — every value
shown comes from a real API response; no manifest validation, routing,
or write-safety decision is computed client-side.

## Routes

| Route | Component | Purpose |
|---|---|---|
| `/execution-manifests` | `ExecutionManifestList` | List all manifests, with filters/sort, plus the Founder Action Center view. |
| `/execution-manifests/:manifestId` | `ExecutionManifestDetail` | Manifest header, every execution item as a card, queue actions, trace, asset index. |

Nav entry: sidebar → **OPS Execution → Execution Manifests**.

## Manifest List View

Table columns: manifest name/ID, source system, status, priority, item
count, completed count, blocked count, founder-action count, created
date, due date.

Filters: status, destination, priority, source system, "founder action
needed" checkbox, "blocked only" checkbox.

Sort: newest, oldest, due date, priority, most blocked, most founder
action needed.

Empty state: distinguishes "no manifests received at all" from "no
manifests match the current filters" — never a fake success state.

## Manifest Detail View

Header: campaign name, source system, source packet ID, manifest ID,
status, priority, due date, notes, asset index (collapsible).

Each execution item renders as a card showing: title, description,
destination/channel/platform, execution type, current status, a
**destination support badge** (see below), recommended worker, worker
task ID (if queued), founder-gated indicator, priority, due date, and
(when expanded) copy, instructions, placement, compliance notes, QA
requirements, dependencies, asset references, warnings, and the trace.

## Destination Support Badges

Badges are **derived from the item's existing `status` + `warnings`**
(both already computed by `POST /validate`) — never recomputed or
guessed client-side:

| Badge | Derived from |
|---|---|
| `SUPPORTED NOW` | `status` in (`ready`, `queued`, `processing`, `completed`) |
| `CONNECTOR UNAVAILABLE` | `status=blocked` + a "connector unavailable" warning, destination not on the roadmap list |
| `FUTURE CONNECTOR PLANNED` | same as above, but destination *is* on the documented roadmap list (see `docs/EXECUTION_MANIFEST_SCHEMA.md`) |
| `MANUAL EXECUTION REQUIRED` | `status=blocked` + a "manual execution required" warning |
| `NEEDS REVIEW` | `status=needs_review` |
| `BLOCKED` | `status` in (`blocked`, `failed`) without a recognized warning pattern |
| `NOT YET VALIDATED` | `status=pending` (validation hasn't run yet — an honest 7th state, not one of the 6 requested, shown rather than guessing) |

Metricool always shows `CONNECTOR UNAVAILABLE` / `FUTURE CONNECTOR
PLANNED` unless the backend's `DESTINATION_SUPPORT` table changes to say
otherwise — the frontend has no way to make it look executable.

## Queue Behavior

- **Queue Item** — only rendered for items whose backend `status` is
  `ready`. Calls `POST /items/{item_id}/queue`. If the response says
  `already_queued`, that's what's displayed — never a fresh "success."
- **Queue All Ready (N)** — calls `POST /queue`, disabled when there are
  zero ready items. Summarizes queued vs. already-queued counts from the
  real response.
- Duplicate queue requests never duplicate a worker task; the UI simply
  reflects what the backend reports.
- Unsupported items (blocked/needs_review) never show a Queue button —
  they show "Cannot queue" plus the real blocker reason.

## Founder Action Behavior

The Founder Action Center (a toggle on the list view, not a separate
route) surfaces, across all manifests:
- items with `status=needs_review`
- items with `status=queued` whose `recommended_worker` is a known
  founder-gated worker (`wp_placement`, `sam` — from
  `services/worker_queue.py`'s `WORKERS` dict, not invented)

For WP Placement specifically: the UI never exposes a one-click live
publish. The documented next action is always "open the item in Worker
Queue and run its dry-run preview, then approve" — the existing
dry-run → approval-token → live flow is completely untouched and is not
reachable from this workspace by design.

## Trace View

Expanding an item calls `GET /trace` and renders: Manifest → Execution
Item → Worker Task → Worker → Status, plus any task result/warnings. If
the item has no `worker_task_id` yet, it says so plainly ("Not yet
queued — no worker task exists") rather than showing an empty or
misleading chain.

## Asset Visibility

Collapsible asset index on the detail header: asset ID, type, URL, alt
text, and which execution items reference it (`asset_refs`). Read-only —
no asset editing in Phase 2.

## Empty / Blocked / Error States

Honest, distinct states for: no manifests at all, no manifests matching
filters, no founder actions pending, a manifest that doesn't exist (404),
a manifest whose backend is unreachable (network error), a manifest with
zero execution items, an item blocked by an unsupported connector, an
item blocked by an invalid/missing dependency, and a failed validation
result (the raw backend error list is shown, not a generic message).

## Testing

`src/pages/__tests__/ExecutionManifestList.test.js` and
`ExecutionManifestDetail.test.js` (19 tests total, Jest + React Testing
Library, axios mocked). Covers list rendering, badges, Founder Action
Center (including that a blocked-but-not-founder-gated item like
Metricool never appears there), queue/duplicate-queue/queue-all
responses, trace view (queued and not-yet-queued cases), asset index,
and all listed empty/blocked/error states.

**Test-tooling note:** running these required adding
`@testing-library/react`, `@testing-library/jest-dom`, and
`@testing-library/user-event`, plus a `jest.configure` block in
`craco.config.js` and a polyfill in `setupTests.js` — both fix a
pre-existing `jest-resolve` v27 vs. `react-router-dom` v7 / `axios`
conditional-`exports` incompatibility unrelated to this feature. See
`docs/PROJECT_STATE.md`'s Phase 2 entry for details.
