# Execution Manifest Layer — Schema & Behavior (Phase 1)

Bridge between final structured campaign/output packets (from TSAF, or any
future source system) and safely routed OPS execution work. Reuses the
existing Worker Queue rather than replacing it.

```
TSAF creates.
Execution Manifest receives and structures.
OPS Execution Queue organizes.
OPS operators execute.
```

TSAF is separate from OPS. OPS girls do not directly touch TSAF.

This layer **never** calls `services/wp_client.py` directly and **never**
issues or consumes a WP write-safety approval token. It only ever creates
ordinary `worker_tasks` records through the existing, unmodified
`services/worker_queue.create_worker_task()`, which routes into the
existing, unmodified Jenny → Rene → WP Placement chain and the existing,
unmodified WP write-safety gate (`services/wp_write_safety.py`). Dry-run
stays the default; founder approval and a single-use token are still
required for any live WordPress write — exactly as before this layer
existed.

---

## Manifest Schema

| Field | Type | Notes |
|---|---|---|
| `manifest_id` | string | Server-generated (`man-<hex12>`) if not supplied. Must be unique. |
| `schema_version` | string | Required. |
| `source_system` | string | Required, e.g. `"TSAF"`. |
| `source_packet_id` | string | Required — the originating packet's own ID, for traceability. |
| `source_packet_type` | string | Optional, e.g. `"campaign"`. |
| `campaign_id` / `campaign_name` | string | Optional. |
| `brand_id` / `brand_name` | string | Optional. |
| `created_at` / `received_at` | ISO datetime | Server-set. |
| `status` | enum | See Manifest Statuses below. |
| `priority` | string | Free-form, default `"normal"`. |
| `due_at` | ISO datetime | Optional. |
| `created_by` | string | Optional. |
| `notes` | string | Optional. |
| `execution_items` | list of Execution Item | Required, at least one. |
| `assets` | list of `{asset_id, type, url, alt_text, notes}` | Referenced by items' `asset_refs`. |
| `metadata` | object | Free-form. |

### Manifest Statuses
`received`, `validated`, `needs_review`, `ready`, `in_progress`,
`partially_completed`, `completed`, `blocked`, `failed`, `cancelled`

---

## Execution Item Schema

| Field | Type | Notes |
|---|---|---|
| `item_id` | string | Required, unique within the manifest. |
| `manifest_id` | string | Server-set to the parent manifest. |
| `sequence` | int | Ordering hint. |
| `title` / `description` | string | |
| `content_type` | string | Free-form, e.g. `"section"`, `"post"`. |
| `destination` | enum | See Destination Labels below. Required. |
| `channel` / `platform` | string | Optional, free-form sub-routing hints. |
| `execution_type` | string | Required, e.g. `content_draft`, `page_update`, `page_create`, `destination_pack`. |
| `recommended_worker` | string | Set by validation (see Routing Rules). |
| `task_type` | string | Set by validation. |
| `requires_founder_approval` | bool | Advisory; the WP write-safety gate enforces this independently regardless of this flag. |
| `status` | enum | See Execution Item Statuses below. |
| `priority` | string | Default `"normal"`. |
| `due_at` | ISO datetime | Optional. |
| `asset_refs` | list of string | Must all exist in the manifest's `assets` index. |
| `copy` | string | Final, ready-to-use content, if the source system already produced it. |
| `instructions` | string | Instructions for content generation, if `copy` isn't already final. |
| `placement` | object | Destination-specific placement info. For `content_draft`/`page_update`: `{page_id, wp_page_id, insert_after, insert_before, publication_mode}`. For `page_create` (see below): `{slug, page_type, template_id, hero_headline, subheadline, intro, body_section_1, body_section_2, body_section_3, cta_text, cta_url, related_links, seo_title, meta_description, publication_mode}`. |
| `compliance_notes` | string | Optional. |
| `qa_requirements` | list of string | Optional. Convention strings Rene's WP content QA (`services/worker_queue._rene_qa_wp_content`) understands: `cta_required`, `min_internal_links:N`, `internal_only`, `required_sections:key1,key2`, `seo_required`. Unrecognized strings produce a warning, never a failure — different pages can declare different requirements; none are assumed by default. Duplicate internal-link URLs and basic malformed-href detection run unconditionally regardless of what's declared here. |
| `dependencies` | list of string | Other `item_id`s that must complete first. Validated for existence and cycles. |
| `context` | object | Free-form, merged into the created worker task's context. **May never contain `execution_mode` or `approval_token`** — see WordPress Safety Boundaries below. |
| `worker_task_id` | string | Set once queued. |
| `result` | object | Mirrors the worker task's result. |
| `warnings` | list of string | Includes routing/support explanations for blocked or needs-review items. |
| `created_at` / `updated_at` | ISO datetime | Server-set. |

### Execution Item Statuses
`pending`, `needs_review`, `ready`, `queued`, `processing`, `completed`,
`blocked`, `failed`, `cancelled`

---

## Destination Labels & Support Levels

Supporting a destination label does **not** mean the connector exists.
Every recognized label has an explicit, documented support level:

| Destination | Support level | Planned? | Notes |
|---|---|---|---|
| `wordpress` | **supported_now** | — | Routed through Jenny/Rene/WP Placement, write-safety gated. |
| `metricool` | connector_unavailable | yes | No execution connector in this backend yet. |
| `facebook` | connector_unavailable | yes | No direct social publishing connector yet. |
| `instagram` | connector_unavailable | yes | No direct social publishing connector yet. |
| `tiktok` | connector_unavailable | yes | No direct social publishing connector yet. |
| `youtube_shorts` | connector_unavailable | yes | No direct social publishing connector yet. |
| `pinterest` | connector_unavailable | yes | No direct social publishing connector yet. |
| `linkedin` | connector_unavailable | yes | No direct social publishing connector yet. |
| `email` | connector_unavailable | yes | No email-sending connector (e.g. Klaviyo) yet. |
| `blog` | manual_required | no (by nature) | Non-WordPress blog; no connector, always manual. |
| `guide` | manual_required | no (by nature) | Digital guide delivery; no connector, always manual. |
| `digital_product` | manual_required | no (by nature) | Digital product delivery; no connector, always manual. |
| `hubspot` | connector_unavailable | yes | No HubSpot connector yet. |
| `ads` | connector_unavailable | yes | No ads-platform connector yet. |
| `manual` | manual_required | n/a | Explicitly marked for manual execution by the source packet. |

Any destination string **not** in this table is `unrecognized` and fails
validation outright — the system never guesses.

`services/execution_manifest.py:DESTINATION_SUPPORT` is the single source
of truth for this table; keep this document in sync with it.

---

## Routing Rules (deterministic, explicit)

1. **WordPress content draft/update** — `destination=wordpress`,
   `execution_type` in (`content_draft`, `page_update`) →
   Jenny (`wp_content_draft`) → Rene (`wp_content_qa`) → WP Placement
   (`wp_page_update`). Founder gating and the write-safety gate are
   entirely unmodified and unaware this task originated from a manifest.

2. **WordPress new page placement** — `destination=wordpress`,
   `execution_type=page_create` → WP Placement (`wp_draft`). Built
   directly from the item's own `copy`/`title`/`placement` fields (see
   `placement` row above) — no pre-existing Page Ops record required.
   Founder gating and the write-safety gate preserved and unchanged.

3. **Destination pack** — `execution_type=destination_pack` (any
   destination) → Sam (`destination_pack`).

4. **Unsupported connector destinations** (`metricool`, `email`, social
   platforms, `hubspot`, `ads`, etc.) — never faked. Marked `blocked` with
   a `connector unavailable` warning; full instructions and assets are
   preserved on the item for later execution once a connector exists.

5. **`manual` / `blog` / `guide` / `digital_product`** — marked `blocked`
   with a `manual execution required` warning. Never routed to a worker.

6. **No safe rule matches** — the item is marked `needs_review`. The
   system never guesses a worker or task type.

---

## WordPress Safety Boundaries

The following are **absolute** and enforced independently of this layer,
by the existing, unmodified write-safety gate:

- `dry_run` remains the default execution mode for any WordPress write.
- Founder review and an explicit approve step remain required.
- A valid, unexpired, unconsumed, payload-hash-bound, scope-bound approval
  token is required for any live write.
- Live writes default to WordPress status `draft`.
- Publishing requires its own separate, explicit authorization.

**No manifest field may bypass any of the above.** Specifically:
`item.context` may never contain `execution_mode` or `approval_token` —
validation hard-rejects any manifest that tries. A manifest **may**
express `placement.publication_mode: "publish"` as an *intent* (it is
passed through to the created task's `context.publication_mode`), but this
alone never authorizes a live write or a publish — it only affects what a
human reviewing the dry-run preview sees requested. Actual live execution
still requires the separate, founder-driven approval-token flow, exactly
as before this layer existed.

---

## API Endpoints

| Method | Path | Behavior |
|---|---|---|
| `POST` | `/api/execution-manifests` | Store a manifest as received. No validation, routing, or execution happens here. |
| `GET` | `/api/execution-manifests` | List manifests, optional `?status=` filter. |
| `GET` | `/api/execution-manifests/{manifest_id}` | Fetch one manifest. |
| `POST` | `/api/execution-manifests/{manifest_id}/validate` | Validate + annotate routing decisions. Visible, separate step. |
| `POST` | `/api/execution-manifests/{manifest_id}/queue` | Queue every `ready` item. Idempotent per item. |
| `POST` | `/api/execution-manifests/{manifest_id}/items/{item_id}/queue` | Queue a single item. Idempotent. |
| `GET` | `/api/execution-manifests/{manifest_id}/trace` | manifest → item → worker task → status → result → warnings. |

Creation never triggers any external write. Validation is separate and
visible. Queueing only ever creates existing `worker_tasks` records for
items whose support level is `supported_now`; everything else stays
visible with a clear blocker reason. Duplicate queue requests never
duplicate a worker task — the item's `worker_task_id` is checked first.

---

## Traceability

Every worker task created from a manifest item carries:
- `source_module = "execution_manifest"`
- `context.manifest_id`
- `context.execution_item_id`
- `context.source_packet_id`
- `context.campaign_id`
- `context.destination`
- `context.execution_type`

The execution item stores `worker_task_id` once queued. The trace endpoint
joins manifest → item → task → status/result/warnings in one call.

---

## Example Manifest JSON

```json
{
  "schema_version": "1.0",
  "source_system": "TSAF",
  "source_packet_id": "packet-abc-123",
  "source_packet_type": "campaign",
  "campaign_id": "camp-001",
  "campaign_name": "Confidence Content Batch 01",
  "brand_id": "ts",
  "brand_name": "Temporary Satisfaction",
  "priority": "normal",
  "created_by": "tsaf",
  "execution_items": [
    {
      "item_id": "item-1",
      "manifest_id": "",
      "sequence": 1,
      "title": "Update trust page",
      "description": "Add a new confidence-building section",
      "content_type": "section",
      "destination": "wordpress",
      "execution_type": "content_draft",
      "requires_founder_approval": true,
      "status": "pending",
      "priority": "normal",
      "asset_refs": [],
      "copy": "Final, ready-to-place copy for the new section.",
      "placement": {
        "page_id": "page-em-1",
        "wp_page_id": "354951",
        "insert_after": "",
        "publication_mode": "draft"
      },
      "dependencies": [],
      "context": {}
    },
    {
      "item_id": "item-2",
      "manifest_id": "",
      "sequence": 2,
      "title": "Schedule Instagram post",
      "destination": "metricool",
      "execution_type": "social_post",
      "status": "pending",
      "copy": "Caption text for the post.",
      "asset_refs": ["asset-1"],
      "dependencies": []
    }
  ],
  "assets": [
    {"asset_id": "asset-1", "type": "image", "url": "https://example.test/a.jpg"}
  ],
  "metadata": {}
}
```

After `POST /validate`: `item-1` becomes `ready` (routed to Jenny), and
`item-2` becomes `blocked` with a `connector unavailable` warning (no
Metricool execution connector exists in this backend yet) — its
instructions and asset reference are preserved for later execution.
