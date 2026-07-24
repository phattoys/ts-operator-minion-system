# OPS Backlog Packages

Executable Execution Manifest JSON files, ready to `POST` to
`/api/execution-manifests` (create → validate → queue), covering
real founder-authored backlog work. Not auto-loaded into MongoDB by
anything — a founder or operator submits these deliberately.

## `ts-14-category-taxonomy-backlog-20260723.json`

14 WooCommerce product-category taxonomy terms (13 `taxonomy_update` +
1 `taxonomy_create`), built against the WooCommerce Taxonomy Lane
(`ops/woocommerce-taxonomy-lane-20260723`, see
`docs/EXECUTION_MANIFEST_SCHEMA.md`'s WooCommerce Taxonomy Lane section
and `docs/PROJECT_STATE.md`).

**Content status:** every `copy` and `placement.description` field is the
literal placeholder `"PENDING_CONTENT — not yet drafted"`. This manifest
proves the pipeline shape end to end (validation → routing → Rene QA →
dry-run preview → founder approval) — it deliberately does **not** contain
founder-approved final category copy. Queuing these items correctly lands
each one in `needs_review` at Rene QA until real `introduction` /
`how_to_guidance` / `faqs` content is supplied — verified directly against
the real pipeline code (not just described) before this file was added to
the repo.

### Updates (existing WooCommerce categories)

| item_id | Title | Slug | term_id | Priority |
|---|---|---|---|---|
| tax-001 | Masturbators & Strokers | `masturbators-and-strokers` | 78144 | normal |
| tax-002 | Cock Rings | `cock-rings` | 78147 | normal |
| tax-003 | Remote & App Controlled | `remote-and-app-controlled` | 78129 | normal |
| tax-004 | Anal Plugs | `anal-plugs` | 78138 | normal |
| tax-005 | Wearable & Panty Vibes | `wearable-and-panty-vibes` | 78130 | normal |
| tax-006 | Wand Massagers | `wand-massagers` | 78125 | normal |
| tax-007 | Air Pulse & Suction | `air-pulse-and-suction` | 78126 | normal |
| tax-008 | Kegel & Benwa Balls | `kegel-and-benwa-balls` | 78239 | normal |
| tax-009 | Water Based Lubes | `water-based-lubes` | 78164 | **high** (internal-link hub) |
| tax-010 | Dildos & Dongs | `dildos-and-dongs` | 78235 | normal |
| tax-011 | Penis Pumps | `penis-pumps` | 78146 | normal |
| tax-012 | Strap On Dildos | `strap-on-dildos` | 78136 | normal |
| tax-013 | Clit Stimulators | `clit-stimulators` | 77446 | normal |

### Create (new WooCommerce category)

| item_id | Title | Slug |
|---|---|---|
| tax-014 | Lingerie Sets, Babydolls & Teddies | `lingerie-sets-babydolls-teddies` |

### Held out of this backlog (not in this file — leave alone)

- `bullet-and-mini-vibrators` — existing rich content
- `g-spot-toys` — existing complete content
- `rabbit-vibrators` — content complete; scheduled for a later
  internal-link-only pass

These three remain valid **link destinations** for the items above once
real content is drafted.

### Internal-link dependency plan

Derived from ordinary product-taxonomy adjacency (lube-compatibility,
harness/dong pairing, wearable/app-control overlap, stimulation-type
overlap) — not verified against live category descriptions (the taxonomy
lane's *read* capability exists in code but was not exercised against a
real site for this plan).

| Source | Destination | Reason | Required? | Must wait? |
|---|---|---|---|---|
| masturbators-and-strokers | water-based-lubes | Lube compatibility | required | no |
| masturbators-and-strokers | penis-pumps | Adjacent solo-pleasure category | optional | no |
| cock-rings | water-based-lubes | Lube compatibility | required | no |
| cock-rings | wearable-and-panty-vibes | Couples-play cross-sell | optional | no |
| remote-and-app-controlled | wearable-and-panty-vibes | Many wearables are app-controlled | required | no |
| remote-and-app-controlled | bullet-and-mini-vibrators (held out) | App-controlled bullets are common | optional | no |
| anal-plugs | water-based-lubes | Lube compatibility, safety-critical | required | no |
| anal-plugs | kegel-and-benwa-balls | Adjacent anatomy/wellness category | optional | no |
| wearable-and-panty-vibes | remote-and-app-controlled | Reciprocal | required | no |
| wand-massagers | air-pulse-and-suction | External-stimulation overlap | optional | no |
| wand-massagers | clit-stimulators | Product overlap | optional | no |
| air-pulse-and-suction | clit-stimulators | Strong product overlap | required | no |
| clit-stimulators | air-pulse-and-suction | Reciprocal | required | no |
| clit-stimulators | rabbit-vibrators (held out) | Combo-toy cross-sell | optional | no |
| kegel-and-benwa-balls | water-based-lubes | Lube compatibility | optional | no |
| water-based-lubes | dildos-and-dongs | Universal lube cross-sell | optional | no |
| water-based-lubes | strap-on-dildos | Universal lube cross-sell | optional | no |
| dildos-and-dongs | strap-on-dildos | Harness/dong compatibility | required | no |
| dildos-and-dongs | g-spot-toys (held out) | Adjacent insertable category | optional | no |
| penis-pumps | water-based-lubes | Lube compatibility | optional | no |
| strap-on-dildos | dildos-and-dongs | Reciprocal | required | no |
| **strap-on-dildos** | **lingerie-sets-babydolls-teddies (tax-014)** | Harness/lingerie co-shopping | required | **yes — wait until tax-014 exists** |
| lingerie-sets-babydolls-teddies | wearable-and-panty-vibes | Co-shopped with wearables | optional | no (outbound, fine once tax-014 exists) |

**Only one sequencing constraint exists**: the inbound link from
`strap-on-dildos` (tax-012) to `lingerie-sets-babydolls-teddies` (tax-014)
is intentionally **omitted** from `tax-012`'s `placement.related_links` in
the JSON — `tax-012.dependencies` names `tax-014` for traceability, but
the manifest layer does not (and, per this build's scope, still does not)
automatically block execution on `dependencies`; a founder/operator must
add that link manually once `tax-014` is created, or sequence the queue
manually. Every other pair already exists, so no other link carries a
sequencing constraint.
