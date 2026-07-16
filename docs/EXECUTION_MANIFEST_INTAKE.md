# Execution Manifest Intake — Phase 3

Intake/transport gateway: lets a finished TSAF campaign packet — or
another authorized source — enter OPS as a structured Execution Manifest
without a human rebuilding it manually. This is the OPS **receiving**
side only. It does not build or modify TSAF, and does not claim a live
TSAF connection exists until one is actually configured and verified —
`source_system=tsaf` is used only as a packet label in this phase's
controlled proof.

```
TSAF creates.
Execution Manifest receives and structures.
OPS Execution Queue organizes.
OPS operators execute.
```

This layer creates manifests **exclusively** through the existing,
unmodified `services/execution_manifest.create_manifest()`, and validates
the nested manifest **exclusively** through the existing, unmodified
`services/execution_manifest.validate_manifest()`. No second competing
manifest schema. It never calls `queue_execution_item()`/`queue_manifest()`,
never touches `services/wp_client.py` or `services/wp_write_safety.py`,
and never creates a worker task. A successfully accepted packet produces
a manifest in exactly the same `received` state as one created directly
through `POST /api/execution-manifests` — the founder still validates and
queues it themselves in the existing Phase 2 workspace.

---

## Inbound Envelope

| Field | Type | Notes |
|---|---|---|
| `packet_id` | string | Required. Identity of this packet delivery. |
| `packet_version` | string | Default `"1.0"`. |
| `source_system` | string | Required. One of the supported labels below. |
| `source_environment` | string | Optional, e.g. `"production"`, `"controlled-proof"`. |
| `source_packet_type` | string | Optional, e.g. `"campaign"`. |
| `source_packet_id` | string | Optional — the originating system's own packet ID. |
| `source_created_at` / `sent_at` | ISO datetime | Optional. |
| `sender_id` | string | Optional. |
| `brand_id` / `campaign_id` / `campaign_name` | string | Optional. |
| `manifest` | object | **Required.** Uses the existing, unmodified Phase 1 `ExecutionManifest` schema — see `docs/EXECUTION_MANIFEST_SCHEMA.md`. |
| `asset_index` | list of asset metadata objects | See Asset Boundary below. |
| `packet_location` | string | Optional pointer to where the packet/assets live. |
| `packet_checksum` | string | SHA-256 hex digest, see Checksum below. |
| `idempotency_key` | string | **Required.** See Idempotency below. |
| `metadata` | object | Free-form. |

### Supported Source Systems
`tsaf`, `manual`, `api`, `import`, `unknown`

**A recognized source system label does not automatically mean
trusted.** Trust is established solely by `authentication_status` on the
receipt — `/receive` sets it to `authenticated` only after a valid HMAC
signature; `/manual` sets it to `founder_session`. The `source_system`
field is never itself a trust signal.

---

## HMAC Signing Process

`POST /api/execution-manifest-intake/receive` requires a valid
`X-TS-Signature` header: `HMAC-SHA256(secret, timestamp + "." + raw_body)`,
hex-encoded, checked with a constant-time comparison
(`hmac.compare_digest` — never a plain `==` on the computed value).

### Required Headers

| Header | Purpose |
|---|---|
| `X-TS-Source` | Informational sender label. |
| `X-TS-Timestamp` | Unix epoch seconds (as a string), signed alongside the body to bind the signature to a specific moment. |
| `X-TS-Signature` | `hex(HMAC-SHA256(EXECUTION_MANIFEST_INTAKE_SECRET, timestamp + "." + raw_body))` |
| `X-TS-Idempotency-Key` | Informational mirror of `envelope.idempotency_key` (the envelope field is authoritative). |

### Rules
- Missing signature → **401 rejected**.
- Invalid signature → **401 rejected**.
- Timestamp outside the replay window (`EXECUTION_MANIFEST_INTAKE_REPLAY_WINDOW_SECONDS`, default 300s) → **401 rejected**.
- The intake secret is **never** the founder login password (`ADMIN_PASSWORD`) — a dedicated, separate credential.
- The secret is never logged, never returned in any response, and never stored on a receipt.
- Authentication failures do not create a receipt (there is no verified identity yet to attribute a persistent audit record to).

### Example Signing Pseudocode

```python
import hmac, hashlib, time, json

secret = EXECUTION_MANIFEST_INTAKE_SECRET  # shared secret, out of band
body = json.dumps(envelope).encode("utf-8")
timestamp = str(time.time())
signing_input = timestamp.encode("utf-8") + b"." + body
signature = hmac.new(secret.encode("utf-8"), signing_input, hashlib.sha256).hexdigest()

headers = {
    "X-TS-Source": "tsaf",
    "X-TS-Timestamp": timestamp,
    "X-TS-Signature": signature,
    "X-TS-Idempotency-Key": envelope["idempotency_key"],
    "Content-Type": "application/json",
}
# POST body (the raw bytes used above) + headers to /api/execution-manifest-intake/receive
```

---

## Checksum Process

`packet_checksum` is a SHA-256 hex digest over the **canonicalized**
envelope (`json.dumps(..., sort_keys=True, separators=(",", ":"))`),
**excluding** the `packet_checksum` field itself (a field can't hash
itself). Senders compute this before signing.

- Checksum matches → `checksum_status: "match"`.
- Checksum omitted → `checksum_status: "not_supplied"` (accepted, with a warning — checksum is recommended, not mandatory, since some legitimate manual/testing intake won't have one).
- Checksum present but wrong → `checksum_status: "mismatch"` → **quarantined, no manifest created.**

---

## Idempotency Behavior

Idempotency is mandatory and keyed on `idempotency_key` first:

1. Same `idempotency_key` seen before → the **original** receipt is
   returned unchanged (status stays whatever it originally was). No
   second manifest, no second receipt, no duplicate worker tasks (none
   are ever created by intake regardless).
2. Same `packet_id` seen before, but with a **different** payload
   (different `raw_packet_hash`) and a different `idempotency_key` → this
   is a **conflict**, not a duplicate. The packet is **quarantined**;
   no manifest is created.

---

## Quarantine Rules

A packet is quarantined or rejected (never silently discarded — always
visible to the founder via the receipt) for:

- invalid authentication (rejected before a receipt even exists, see above)
- stale timestamp / replay conflict
- checksum mismatch
- malformed envelope (missing `packet_id`, `source_system`, `manifest`, or `idempotency_key`)
- invalid nested manifest (per the existing Phase 1 `validate_manifest()` — missing items, duplicate item IDs, invalid dependencies, circular dependencies, unrecognized destinations, etc.)
- packet ID reused with a different payload
- a manifest `context` attempting to set `execution_mode` or `approval_token` — rejected by the same existing Phase 1 validator that already forbids this; the intake layer does not duplicate this check, it inherits it for free by calling `validate_manifest()`
- missing required packet identity fields

---

## Manual Intake

`POST /api/execution-manifest-intake/manual` — requires the existing
founder session (the same auth as every other OPS endpoint), never the
server-to-server secret. Accepts a pasted/uploaded envelope JSON.
Records `transport: "manual"`.

Frontend: `/execution-manifests/intake` — paste or upload a `.json` file,
see a **local, readability-only** preview (packet ID, source system,
campaign, item count, destination summary, asset-reference count — parses
JSON client-side only to build this preview; the backend remains the sole
authority on schema/checksum/safety validation), submit, and see the
resulting receipt (accepted/rejected/quarantined, errors, warnings, and a
link to the created manifest when accepted).

---

## API Endpoints

| Method | Path | Auth | Notes |
|---|---|---|---|
| `POST` | `/api/execution-manifest-intake/receive` | HMAC signature | Server-to-server, for future TSAF delivery. Not dependent on a founder browser session. |
| `POST` | `/api/execution-manifest-intake/manual` | Founder session | Paste/upload JSON. |
| `GET` | `/api/execution-manifest-intake/receipts` | Founder session | List, with `status`/`source_system`/`transport` filters. |
| `GET` | `/api/execution-manifest-intake/receipts/{receipt_id}` | Founder session | Single receipt detail. |
| `POST` | `/api/execution-manifest-intake/receipts/{receipt_id}/retry` | Founder session | Re-runs the same checksum→validate→create flow using the envelope captured at receipt time. Idempotent; never bypasses authentication history; never queues a worker task. |

There is no generic unauthenticated manifest-creation endpoint anywhere
in this layer.

---

## Receipt Model

| Field | Notes |
|---|---|
| `receipt_id` | Server-generated (`rcpt-<hex12>`). |
| `packet_id` / `idempotency_key` | From the envelope. |
| `source_system` | From the envelope (not a trust signal — see above). |
| `received_at` | Server timestamp. |
| `authentication_status` | `authenticated` (via `/receive`) or `founder_session` (via `/manual`). |
| `checksum_status` | `match` / `mismatch` / `not_supplied`. |
| `schema_status` | `valid` / `invalid` / `not_evaluated`. |
| `manifest_id` | Set only when a manifest was actually created. |
| `status` | `received`, `authenticated`, `rejected`, `duplicate`, `quarantined`, `validated`, `accepted`, `failed`. |
| `errors` / `warnings` | Human-readable strings. |
| `raw_packet_hash` | SHA-256 of the canonicalized envelope — used for the packet-identity-conflict check. |
| `received_by` | Founder user ID for manual/retry; `null` for server-to-server. |
| `transport` | `server_to_server` or `manual`. |
| `metadata` | Free-form. |

Stored in `execution_manifest_receipts`. No plaintext secrets are ever
stored on a receipt — the HMAC secret never appears in this collection.

---

## Traceability

```
source packet → intake receipt → execution manifest → execution item → worker chain
```

An accepted manifest is stamped with `intake_receipt_id`,
`intake_packet_id`, `intake_source_system`, `intake_transport`, and
`intake_received_at`. The existing manifest detail page displays this
origin block when present. **Legacy Phase 1/2 manifests, and any manifest
created directly through `POST /api/execution-manifests`, simply don't
have these fields and continue to render exactly as before** —
`receipt_id` is never required.

---

## Asset-Metadata Boundary

Phase 3 accepts and stores asset **metadata/references only**:
`asset_id`, `filename`, `type`, `mime_type`, `dimensions`, `url`, `path`,
`checksum`, `destination`, `metadata`. Inaccessible or malformed
references are reported as warnings on the receipt, not silently dropped.

**No binary asset storage, ZIP extraction, media editing, or CDN upload
in this phase.**

---

## ZIP / Binary Transport Boundary

**Not implemented in this phase.** TSAF may still produce a
human-downloadable ZIP for people, but OPS Phase 3 receives only the
machine-readable packet envelope and manifest JSON described above.
Ingesting or extracting a ZIP/binary transport is documented here as
**future work**, not built.

---

## Environment Variables

| Variable | Default | Purpose |
|---|---|---|
| `EXECUTION_MANIFEST_INTAKE_SECRET` | `""` (empty) | Dedicated server-to-server HMAC secret. Empty by default so `/receive` fails closed until explicitly configured. **Never** set this to the founder login password. |
| `EXECUTION_MANIFEST_INTAKE_REPLAY_WINDOW_SECONDS` | `300` | How old a request timestamp may be before it's rejected. |
| `EXECUTION_MANIFEST_MAX_BYTES` | `5242880` (5 MB) | Hard server-side cap on inbound packet size — never relies only on the browser/client. |

---

## Example TSAF Packet JSON

```json
{
  "packet_id": "packet-controlled-proof-1",
  "packet_version": "1.0",
  "source_system": "tsaf",
  "source_environment": "controlled-proof",
  "source_packet_type": "campaign",
  "source_packet_id": "packet-controlled-proof-1",
  "sent_at": "2026-07-16T00:00:00Z",
  "sender_id": "tsaf-controlled-proof",
  "brand_id": "ts",
  "campaign_id": "camp-001",
  "campaign_name": "Confidence Content Batch 01",
  "manifest": {
    "schema_version": "1.0",
    "source_system": "TSAF",
    "source_packet_id": "packet-controlled-proof-1",
    "campaign_id": "camp-001",
    "campaign_name": "Confidence Content Batch 01",
    "execution_items": [
      {
        "item_id": "item-1",
        "manifest_id": "",
        "sequence": 1,
        "title": "Update trust page",
        "destination": "wordpress",
        "execution_type": "content_draft",
        "status": "pending",
        "copy": "Final, ready-to-place copy for the new section.",
        "placement": { "page_id": "page-1", "wp_page_id": "354951" },
        "asset_refs": [],
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
      { "asset_id": "asset-1", "type": "image", "url": "https://example.test/a.jpg" }
    ]
  },
  "asset_index": [
    { "asset_id": "asset-1", "filename": "a.jpg", "type": "image", "mime_type": "image/jpeg", "url": "https://example.test/a.jpg" }
  ],
  "packet_checksum": "<sha256 of the canonicalized envelope, excluding this field>",
  "idempotency_key": "camp-001-batch-01-2026-07-16"
}
```
