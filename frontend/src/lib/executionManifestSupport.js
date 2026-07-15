/**
 * Presentational support-level derivation for execution items.
 *
 * This does NOT duplicate backend validation or routing logic. The
 * backend is the sole authority on whether an item is actually
 * queueable — this module only interprets the item's existing
 * `status` + `warnings` (both already computed and returned by
 * POST /validate) into one of six labeled badge states for display.
 * If the backend hasn't validated the item yet, we say so honestly
 * rather than guessing.
 *
 * PLANNED_DESTINATIONS mirrors docs/EXECUTION_MANIFEST_SCHEMA.md's
 * destination support table (display metadata only — which recognized,
 * currently-unavailable destinations are on the roadmap). It is not a
 * routing decision and has no effect on what can be queued.
 */

export const SUPPORT_BADGE = {
  SUPPORTED_NOW: 'SUPPORTED NOW',
  CONNECTOR_UNAVAILABLE: 'CONNECTOR UNAVAILABLE',
  MANUAL_REQUIRED: 'MANUAL EXECUTION REQUIRED',
  FUTURE_PLANNED: 'FUTURE CONNECTOR PLANNED',
  NEEDS_REVIEW: 'NEEDS REVIEW',
  BLOCKED: 'BLOCKED',
  NOT_YET_VALIDATED: 'NOT YET VALIDATED',
};

export const SUPPORT_BADGE_STYLE = {
  [SUPPORT_BADGE.SUPPORTED_NOW]: 'text-emerald-400 border-emerald-800 bg-emerald-950/20',
  [SUPPORT_BADGE.CONNECTOR_UNAVAILABLE]: 'text-zinc-400 border-zinc-700 bg-zinc-900/40',
  [SUPPORT_BADGE.MANUAL_REQUIRED]: 'text-amber-400 border-amber-800 bg-amber-950/20',
  [SUPPORT_BADGE.FUTURE_PLANNED]: 'text-blue-400 border-blue-800 bg-blue-950/20',
  [SUPPORT_BADGE.NEEDS_REVIEW]: 'text-red-400 border-red-800 bg-red-950/20',
  [SUPPORT_BADGE.BLOCKED]: 'text-red-500 border-red-900 bg-red-950/30',
  [SUPPORT_BADGE.NOT_YET_VALIDATED]: 'text-zinc-500 border-zinc-800 bg-zinc-900/20',
};

// Destinations documented as "connector_unavailable, planned" in
// docs/EXECUTION_MANIFEST_SCHEMA.md. Display metadata only.
const PLANNED_DESTINATIONS = new Set([
  'metricool', 'facebook', 'instagram', 'tiktok', 'youtube_shorts',
  'pinterest', 'linkedin', 'email', 'hubspot', 'ads',
]);

/**
 * Derive a display badge + explanation from an execution item as returned
 * by the backend. Never invents a "supported" state the backend didn't say.
 */
export function deriveSupportBadge(item) {
  const warnings = item.warnings || [];
  const hasWarningContaining = (needle) => warnings.some((w) => w.toLowerCase().includes(needle));

  if (item.status === 'pending') {
    return { badge: SUPPORT_BADGE.NOT_YET_VALIDATED, reason: 'This item has not been validated yet.' };
  }
  if (item.status === 'ready' || item.status === 'queued' || item.status === 'processing' || item.status === 'completed') {
    return { badge: SUPPORT_BADGE.SUPPORTED_NOW, reason: 'Recognized destination with an existing execution connector.' };
  }
  if (item.status === 'blocked') {
    if (hasWarningContaining('connector unavailable')) {
      const planned = PLANNED_DESTINATIONS.has(item.destination);
      return {
        badge: planned ? SUPPORT_BADGE.FUTURE_PLANNED : SUPPORT_BADGE.CONNECTOR_UNAVAILABLE,
        reason: warnings.find((w) => w.toLowerCase().includes('connector unavailable')) || 'No connector exists for this destination yet.',
      };
    }
    if (hasWarningContaining('manual execution required')) {
      return {
        badge: SUPPORT_BADGE.MANUAL_REQUIRED,
        reason: warnings.find((w) => w.toLowerCase().includes('manual execution required')) || 'This destination requires manual execution.',
      };
    }
    return { badge: SUPPORT_BADGE.BLOCKED, reason: warnings[0] || 'This item is blocked.' };
  }
  if (item.status === 'needs_review') {
    return { badge: SUPPORT_BADGE.NEEDS_REVIEW, reason: warnings[0] || 'No safe routing rule exists for this item yet.' };
  }
  if (item.status === 'failed') {
    return { badge: SUPPORT_BADGE.BLOCKED, reason: warnings[0] || 'This item failed execution.' };
  }
  return { badge: SUPPORT_BADGE.NOT_YET_VALIDATED, reason: 'Unknown item status.' };
}

// Worker names that are known, from services/worker_queue.py's WORKERS
// dict, to be founder-gated (auto_execute: False). Display metadata only
// — the actual gate is enforced entirely server-side regardless of this.
export const FOUNDER_GATED_WORKERS = new Set(['wp_placement', 'sam']);
