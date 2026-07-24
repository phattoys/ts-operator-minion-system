"""
WordPress Write-Safety Gate
---
Single source of truth for the unified write-safety contract that protects
every WordPress write path: the direct /api/wp-placement/place route, the
Worker Queue (wp_placement worker), and any future OPS worker or
execution-manifest task.

Design (approved 2026-07-14, branch safety/unified-wp-write-gate-20260714):

- Three execution modes: mock, dry_run, live.
- `mock` and `dry_run` never reach real WordPress.
- `live` requires a valid, unexpired, unconsumed, payload-bound,
  scope-bound approval_token, issued by a prior dry_run.
- approved_by / approval_role / approval_source / approved_at are NEVER
  trusted from client input. They are resolved here, server-side, at the
  moment a token is consumed.
- Live writes default to WordPress status "draft". Publishing requires its
  own explicit publication_mode == "publish" authorization and is never the
  implicit default.

This module does not itself call WordPress. It is imported by
services/wp_client.py (the only file that does) and is the mandatory
checkpoint that create_page()/update_page() run through before their live
branches may execute. Any new route, worker, or future execution-manifest
task has no other path to real WordPress, so it cannot bypass this gate
without directly editing wp_client.py itself.
"""
import hashlib
import json
import secrets
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from database import db, logger, WP_APPROVAL_TOKEN_TTL_MINUTES


class WpWriteSafetyError(Exception):
    """
    Raised whenever a live WordPress write is requested without meeting the
    full safety contract. Callers must let this propagate as a clear,
    loud failure -- never catch-and-silently-fall-back-to-mock.
    """
    pass


def hash_payload(payload: Dict[str, Any]) -> str:
    """
    Deterministic hash of the operation content, used to bind an approval
    token to the exact content that was previewed. If the content changes
    between dry_run and live (e.g. someone edits the draft after approval),
    the hash will no longer match and the live write will be refused.
    """
    normalized = json.dumps(payload, sort_keys=True, default=str)
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


async def issue_approval_token(
    scope: str,
    scope_ids: List[str],
    payload: Dict[str, Any],
    publication_mode: str = "draft",
    object_type: str = "page",
) -> Dict[str, Any]:
    """
    Called at the end of a successful dry_run. Issues a short-lived,
    single-use token bound to this exact payload and scope.

    scope: "single" or "batch"
    scope_ids: the page_id(s)/term_id(s)/task_id(s) this token covers
    payload: the exact structured content that was previewed (used for hashing)
    publication_mode: "draft" or "publish" -- locked in at issuance time so a
        caller cannot request draft approval and then execute a publish.
    object_type: "page" (default, unchanged existing behavior) or
        "woocommerce_product_category" (taxonomy lane). Bound into the
        token so it can never be consumed against the wrong object type --
        see consume_approval_token().
    """
    now = datetime.now(timezone.utc)
    token = secrets.token_urlsafe(32)
    record = {
        "token": token,
        "scope": scope,
        "scope_ids": scope_ids,
        "payload_hash": hash_payload(payload),
        "publication_mode": publication_mode,
        "object_type": object_type,
        "issued_at": now.isoformat(),
        "expires_at": (now + timedelta(minutes=WP_APPROVAL_TOKEN_TTL_MINUTES)).isoformat(),
        "consumed": False,
        "consumed_at": None,
        "approved_by": None,
        "approval_role": None,
        "approval_source": None,
    }
    await db.wp_write_approvals.insert_one(dict(record))
    logger.info(f"[WP Safety] Issued approval token for scope={scope} ids={scope_ids} object_type={object_type} ttl={WP_APPROVAL_TOKEN_TTL_MINUTES}m")

    return {k: v for k, v in record.items() if k != "_id"}


async def consume_approval_token(
    token: Optional[str],
    scope_ids: List[str],
    payload: Dict[str, Any],
    approved_by: str,
    approval_role: str,
    approval_source: str,
    object_type: str = "page",
) -> Dict[str, Any]:
    """
    Validates and consumes an approval token for a live execution. Raises
    WpWriteSafetyError on ANY failure -- there is no silent-degrade path.

    Checks, in order:
      1. token supplied at all
      2. token exists
      3. token not already consumed
      4. token not expired
      5. scope_ids match exactly what was approved
      6. object_type matches what was approved (a page token can never be
         replayed against a taxonomy-term write, or vice versa)
      7. payload hash still matches what was previewed

    On success, marks the token consumed and records the server-derived
    approval identity (never taken from client input).
    """
    if not token:
        raise WpWriteSafetyError(
            "Live WordPress write refused: no approval_token supplied. "
            "Run a dry_run first to obtain a token."
        )

    record = await db.wp_write_approvals.find_one({"token": token}, {"_id": 0})
    if not record:
        raise WpWriteSafetyError("Live WordPress write refused: approval_token not found or already invalidated.")

    if record.get("consumed"):
        raise WpWriteSafetyError("Live WordPress write refused: approval_token has already been used.")

    expires_at = datetime.fromisoformat(record["expires_at"])
    if datetime.now(timezone.utc) > expires_at:
        raise WpWriteSafetyError(
            f"Live WordPress write refused: approval_token expired at {record['expires_at']}. "
            "Run a fresh dry_run to obtain a new token."
        )

    if sorted(record.get("scope_ids", [])) != sorted(scope_ids):
        raise WpWriteSafetyError(
            "Live WordPress write refused: approval_token scope does not match this operation."
        )

    if record.get("object_type", "page") != object_type:
        raise WpWriteSafetyError(
            "Live WordPress write refused: approval_token object_type does not match this operation "
            f"(token was issued for '{record.get('object_type', 'page')}', operation is '{object_type}')."
        )

    current_hash = hash_payload(payload)
    if record.get("payload_hash") != current_hash:
        raise WpWriteSafetyError(
            "Live WordPress write refused: content has changed since the approval preview was generated. "
            "Run a fresh dry_run to re-approve the updated content."
        )

    now = datetime.now(timezone.utc).isoformat()
    await db.wp_write_approvals.update_one(
        {"token": token},
        {"$set": {
            "consumed": True,
            "consumed_at": now,
            "approved_by": approved_by,
            "approval_role": approval_role,
            "approval_source": approval_source,
        }},
    )
    logger.info(f"[WP Safety] Consumed approval token scope_ids={scope_ids} approved_by={approved_by}")

    record["consumed"] = True
    record["consumed_at"] = now
    record["approved_by"] = approved_by
    record["approval_role"] = approval_role
    record["approval_source"] = approval_source
    return record


def resolve_approval_identity(user: dict) -> Dict[str, str]:
    """
    Derives approved_by / approval_role / approval_source from the
    authenticated session -- NEVER from client-supplied request fields.

    Deliberately not hard-coded to a single literal "founder" string beyond
    what the current single-founder auth model actually provides, so that
    future trusted-execution policies or additional authorized roles can be
    introduced later without redesigning this data model. Today, the JWT
    payload's "sub" claim is the only identity source available.
    """
    return {
        "approved_by": user.get("sub", "unknown"),
        "approval_role": user.get("role", "founder"),
        "approval_source": "manual_confirmation",
    }


async def enforce_live_write(
    execution_mode: str,
    approval_token: Optional[str],
    scope_ids: List[str],
    payload: Dict[str, Any],
    user: dict,
    is_live: bool,
    object_type: str = "page",
) -> Optional[Dict[str, Any]]:
    """
    The single checkpoint wp_client.py calls before ANY real WordPress
    write. Returns the consumed approval record if execution_mode == "live"
    and everything checks out; returns None for mock/dry_run (no real write
    should be attempted by the caller in those modes).

    Raises WpWriteSafetyError for any failure. Callers must NOT catch this
    and silently proceed as mock -- that is exactly the accidental-live
    (or accidental-silent-no-op) behavior this gate exists to prevent.

    object_type defaults to "page" (unchanged existing behavior for
    create_page()/update_page()). The taxonomy lane's
    create_product_category()/update_product_category() pass
    object_type="woocommerce_product_category" so a token issued for one
    object type can never be consumed against the other.
    """
    if execution_mode in ("mock", "dry_run"):
        return None

    if execution_mode != "live":
        raise WpWriteSafetyError(f"Unknown execution_mode: {execution_mode}")

    if not is_live:
        raise WpWriteSafetyError(
            "Live WordPress write refused: no WordPress credentials are configured "
            "(WP_SITE_URL / WP_USERNAME / WP_APP_PASSWORD). Live execution requires "
            "real credentials -- it will not silently fall back to mock."
        )

    identity = resolve_approval_identity(user)
    return await consume_approval_token(
        token=approval_token,
        scope_ids=scope_ids,
        payload=payload,
        approved_by=identity["approved_by"],
        approval_role=identity["approval_role"],
        approval_source=identity["approval_source"],
        object_type=object_type,
    )
