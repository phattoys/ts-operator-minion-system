from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from enum import Enum
from datetime import datetime
from database import PAGE_GENERATION_MODEL, QUALITY_SCORING_MODEL, REWRITE_MODEL


# ================== PAGE MODELS ==================

class LoginRequest(BaseModel):
    password: str

class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"

class PageBase(BaseModel):
    page_name: str
    slug: Optional[str] = None
    page_family: str
    district_or_pillar: Optional[str] = None
    page_type: str
    audience: Optional[str] = None
    purpose: Optional[str] = None
    CTA_type: Optional[str] = None
    keyword_or_theme: Optional[str] = None
    parent_page: Optional[str] = None
    notes: Optional[str] = None

class PageCreate(PageBase):
    pass

class PageUpdate(BaseModel):
    page_name: Optional[str] = None
    slug: Optional[str] = None
    page_family: Optional[str] = None
    district_or_pillar: Optional[str] = None
    page_type: Optional[str] = None
    audience: Optional[str] = None
    purpose: Optional[str] = None
    CTA_type: Optional[str] = None
    keyword_or_theme: Optional[str] = None
    parent_page: Optional[str] = None
    priority_score: Optional[int] = None
    status: Optional[str] = None
    notes: Optional[str] = None
    review_notes: Optional[str] = None

class PageResponse(BaseModel):
    id: str
    page_name: str
    slug: Optional[str] = None
    page_family: str
    district_or_pillar: Optional[str] = None
    page_type: str
    audience: Optional[str] = None
    purpose: Optional[str] = None
    CTA_type: Optional[str] = None
    keyword_or_theme: Optional[str] = None
    parent_page: Optional[str] = None
    priority_score: int = 50
    status: str = "Planned"
    quality_score: Optional[int] = None
    score_notes: Optional[Dict[str, Any]] = None
    edit_recommendations: Optional[List[str]] = None
    generated_content: Optional[str] = None
    generation_history: Optional[List[Dict[str, Any]]] = None
    review_notes: Optional[str] = None
    notes: Optional[str] = None
    page_code: Optional[str] = None
    public_title: Optional[str] = None
    working_title: Optional[str] = None
    menu_destination: Optional[str] = None
    footer_destination: Optional[str] = None
    funnel_stage: Optional[str] = None
    launch_priority: Optional[int] = None
    wp_page_id: Optional[str] = None
    wp_placed_at: Optional[str] = None
    created_at: str
    updated_at: str

class GenerateRequest(BaseModel):
    tone: Optional[str] = "professional"
    additional_instructions: Optional[str] = None
    use_house_template: Optional[bool] = True
    template_id: Optional[str] = None
    use_style_profile: Optional[bool] = True
    style_profile_id: Optional[str] = None
    content_direction: Optional[Dict] = None


# ================== VERSION HISTORY MODELS ==================

class PageVersion(BaseModel):
    id: str
    page_id: str
    version_number: int
    generated_content: str
    created_at: str
    generation_action_type: str
    model_used: Optional[str] = None
    tone_used: Optional[str] = None
    variant_used: Optional[str] = None
    tightened_applied: bool = False
    quality_score: Optional[int] = None
    quality_classification: Optional[str] = None
    recommendations: Optional[List[str]] = None
    score_notes: Optional[Dict[str, Any]] = None
    label: Optional[str] = None
    is_current: bool = False
    is_exemplar: bool = False

class VersionListResponse(BaseModel):
    page_id: str
    page_name: str
    total_versions: int
    current_version: int
    versions: List[PageVersion]

class LabelVersionRequest(BaseModel):
    label: str

class RestoreVersionRequest(BaseModel):
    preserve_current_as_version: bool = True

class SettingsResponse(BaseModel):
    scoring_threshold_strong: int = 85
    scoring_threshold_usable: int = 70
    default_tone: str = "professional"
    default_cta: str = "Learn More"
    page_generation_model: str = PAGE_GENERATION_MODEL
    quality_scoring_model: str = QUALITY_SCORING_MODEL
    rewrite_model: str = REWRITE_MODEL


# ================== EXEMPLAR MODELS ==================

EXEMPLAR_REASON_TAGS = [
    "Strong brand voice",
    "Perfect structure",
    "Emotional resonance",
    "Trust-building excellence",
    "Unique voice",
    "CTA effectiveness",
    "Audience alignment",
    "Warmth without fluff",
    "Intentional phrasing",
    "Discreet confidence",
    "Family-defining quality"
]

class CreateExemplarRequest(BaseModel):
    page_id: str
    version_id: str
    reason_tags: List[str] = []
    exemplar_notes: Optional[str] = None
    is_primary: bool = False

class UpdateExemplarRequest(BaseModel):
    reason_tags: Optional[List[str]] = None
    exemplar_notes: Optional[str] = None
    is_primary: Optional[bool] = None

class ExemplarResponse(BaseModel):
    id: str
    page_id: str
    version_id: str
    page_name: str
    page_family: str


# ================== HOUSE TEMPLATE MODELS ==================

class CreateHouseTemplateRequest(BaseModel):
    template_name: str
    purpose: str
    page_family: str
    page_type: Optional[str] = None
    source_page_id: str
    source_version_id: str
    structural_pattern: str
    tone_guidance: Optional[str] = None
    is_primary: bool = False

class UpdateHouseTemplateRequest(BaseModel):
    template_name: Optional[str] = None
    purpose: Optional[str] = None
    page_type: Optional[str] = None
    structural_pattern: Optional[str] = None
    tone_guidance: Optional[str] = None
    is_primary: Optional[bool] = None
    status: Optional[str] = None


# ================== STYLE PROFILE MODELS ==================

SEED_STYLE_PROFILES = [
    {
        "profile_name": "Brand Welcome",
        "description": "The warm first-impression tone. Makes visitors feel seen, safe, and curious. Used for landing and entry-point pages.",
        "tonal_controls": {"warmth": 9, "formality": 4, "confidence": 7, "intimacy": 6, "playfulness": 3, "authority": 4},
        "include_language": ["welcome", "here for you", "at your pace", "no pressure", "glad you're here", "curiosity"],
        "avoid_language": ["hurry", "limited time", "don't miss out", "act now", "exclusive offer"],
        "page_families": ["Core Hub"],
    },
    {
        "profile_name": "Warm Guidance",
        "description": "Helpful without being pushy. Guides the visitor through choices like a knowledgeable friend, not a salesperson.",
        "tonal_controls": {"warmth": 8, "formality": 5, "confidence": 8, "intimacy": 5, "playfulness": 2, "authority": 6},
        "include_language": ["let us help", "explore", "discover", "we recommend", "designed for", "pathway"],
        "avoid_language": ["buy now", "best seller", "trending", "everyone loves", "you need this"],
        "page_families": ["Guided Path", "Category Support"],
    },
    {
        "profile_name": "Trust First",
        "description": "Builds credibility and safety. Emphasizes transparency, care, and professionalism. For pages where trust is the primary job.",
        "tonal_controls": {"warmth": 7, "formality": 7, "confidence": 9, "intimacy": 3, "playfulness": 1, "authority": 8},
        "include_language": ["your privacy", "discreet", "trusted", "safely", "our commitment", "standards"],
        "avoid_language": ["cheap", "guarantee", "risk-free", "no questions asked", "secret"],
        "page_families": ["Trust"],
    },
    {
        "profile_name": "Quiet Luxury",
        "description": "Understated elegance. Lets the quality speak. Minimal words, maximum intent. For premium and aspirational pages.",
        "tonal_controls": {"warmth": 5, "formality": 8, "confidence": 9, "intimacy": 4, "playfulness": 1, "authority": 7},
        "include_language": ["curated", "refined", "crafted", "intentional", "elevated", "considered"],
        "avoid_language": ["amazing", "awesome", "incredible", "game-changer", "mind-blowing", "insane"],
        "page_families": ["District"],
    },
    {
        "profile_name": "Sensual-Professional",
        "description": "Confident and tasteful adult-content tone. Never crude, never clinical. Warm without being explicit. For product and category pages.",
        "tonal_controls": {"warmth": 7, "formality": 5, "confidence": 9, "intimacy": 7, "playfulness": 4, "authority": 5},
        "include_language": ["pleasure", "connection", "experience", "intimacy", "designed for you", "personal"],
        "avoid_language": ["kinky", "naughty", "dirty", "guilty pleasure", "sinful", "taboo"],
        "page_families": ["Conversion"],
    },
    {
        "profile_name": "Grounded Education",
        "description": "Clear, informative, and caring. Teaches without condescending. For FAQ, guides, and support content.",
        "tonal_controls": {"warmth": 7, "formality": 6, "confidence": 8, "intimacy": 3, "playfulness": 2, "authority": 7},
        "include_language": ["here's how", "good to know", "common question", "we've got you", "step by step"],
        "avoid_language": ["obviously", "simply", "just", "basically", "everyone knows"],
        "page_families": ["FAQ/Support", "Media/Asset"],
    },
]

class TonalControls(BaseModel):
    warmth: int = 5
    formality: int = 5
    confidence: int = 5
    intimacy: int = 5
    playfulness: int = 5
    authority: int = 5

class CreateStyleProfileRequest(BaseModel):
    profile_name: str
    description: str
    tonal_controls: TonalControls
    include_language: List[str] = []
    avoid_language: List[str] = []
    page_families: List[str] = []
    page_types: List[str] = []
    is_default: bool = False

class UpdateStyleProfileRequest(BaseModel):
    profile_name: Optional[str] = None
    description: Optional[str] = None
    tonal_controls: Optional[TonalControls] = None
    include_language: Optional[List[str]] = None
    avoid_language: Optional[List[str]] = None
    page_families: Optional[List[str]] = None
    page_types: Optional[List[str]] = None
    is_default: Optional[bool] = None
    status: Optional[str] = None


# ================== PROMOTION LOGIC MODELS ==================

PROMOTION_THRESHOLDS = {
    "exemplar_min_score": 85,
    "template_min_score": 80,
    "style_candidate_min_score": 82,
    "brand_fit_min": 8,
    "emotional_presence_min": 8,
}

class PromotionActionRequest(BaseModel):
    action: str
    reason_tags: Optional[List[str]] = None
    notes: Optional[str] = None
    is_primary: Optional[bool] = False

class SettingsUpdate(BaseModel):
    scoring_threshold_strong: Optional[int] = None
    scoring_threshold_usable: Optional[int] = None
    default_tone: Optional[str] = None
    default_cta: Optional[str] = None

class ActivityLog(BaseModel):
    id: str
    action: str
    page_id: Optional[str] = None
    page_name: Optional[str] = None
    details: Optional[str] = None
    timestamp: str

class StatsResponse(BaseModel):
    total_pages: int
    by_status: Dict[str, int]
    by_family: Dict[str, int]
    avg_quality_score: Optional[float]
    pages_ready_for_review: int
    pages_needing_rewrite: int


# ================== EXPORT & BATCH MODELS ==================

class TightenRequest(BaseModel):
    apply_to_current: bool = True

class VariantRequest(BaseModel):
    variant: str
    save_as_current: bool = True

class ExportRequest(BaseModel):
    page_ids: List[str]
    format: str = "markdown"

class ExportedPage(BaseModel):
    page_name: str
    slug: str
    page_family: str
    page_type: str
    status: str
    quality_score: Optional[int]
    content: Optional[str]
    metadata: Dict[str, Any]

class ExportResponse(BaseModel):
    exported_count: int
    pages: List[ExportedPage]
    export_date: str

class BatchGenerateRequest(BaseModel):
    count: int = 5
    tone: str = "professional"
    auto_score: bool = True
    score_threshold: int = 70

class BatchGenerateResult(BaseModel):
    page_id: str
    page_name: str
    status: str
    quality_score: Optional[int]
    classification: Optional[str]
    success: bool
    error: Optional[str] = None

class BatchGenerateResponse(BaseModel):
    total_processed: int
    successful: int
    needs_rewrite: int
    ready_for_review: int
    results: List[BatchGenerateResult]

class PageDependencyInfo(BaseModel):
    page_id: str
    page_name: str
    dependency_status: str
    parent_page: Optional[str]
    parent_status: Optional[str]
    children_count: int
    recommendation: str



# ================== SPEC WRITER MODELS ==================

SPEC_TYPES = [
    "Software Feature",
    "Standalone App",
    "Plugin / Extension",
    "GPT / AI Agent",
    "Automation / Workflow",
    "Internal Tool",
]

SPEC_STATUSES = [
    "Draft",
    "Scored",
    "Needs Refinement",
    "Ready",
    "Handed Off",
    "Archived",
]

class SpecInputAnswers(BaseModel):
    what_is_it: Optional[str] = None
    who_is_it_for: Optional[str] = None
    what_pain: Optional[str] = None
    what_must_it_do: Optional[str] = None
    what_to_avoid: Optional[str] = None
    success_measurement: Optional[str] = None
    build_timing: Optional[str] = None
    cost_risk_notes: Optional[str] = None

class CreateSpecRequest(BaseModel):
    title: str
    spec_type: str
    raw_idea: str
    target_audience: Optional[str] = None
    priority: str = "P1"
    constraints: Optional[str] = None
    reference_links: List[str] = []
    input_answers: Optional[SpecInputAnswers] = None

class UpdateSpecRequest(BaseModel):
    title: Optional[str] = None
    spec_type: Optional[str] = None
    raw_idea: Optional[str] = None
    target_audience: Optional[str] = None
    priority: Optional[str] = None
    constraints: Optional[str] = None
    reference_links: Optional[List[str]] = None
    input_answers: Optional[SpecInputAnswers] = None

class GenerateSpecRequest(BaseModel):
    regenerate: bool = False

class SubmitFollowUpRequest(BaseModel):
    answers: Dict[str, str]

class UpdateSpecStatusRequest(BaseModel):
    status: str



# ================== BATCH JOB MODELS ==================

BATCH_JOB_TYPES = ["generate", "score", "tighten", "status_change", "export"]
BATCH_JOB_STATES = ["queued", "running", "completed", "canceled", "failed"]
BATCH_ITEM_STATES = ["queued", "running", "success", "failed", "skipped", "canceled"]
MAX_BATCH_SIZE = 50

class CreateBatchJobRequest(BaseModel):
    type: str
    page_ids: List[str]
    params: Optional[Dict[str, Any]] = {}


# ================== LEAD MAGNET MODELS ==================

LEAD_MAGNET_FORMATS = ["Guide", "Checklist", "Resource List", "FAQ", "Quiz"]
LEAD_MAGNET_STATUSES = ["Draft", "Ready", "Published", "Archived"]
LEAD_MAGNET_LENGTHS = ["Short (1-2 pages)", "Standard (3-5 pages)", "Deep (6-10 pages)"]

class CreateLeadMagnetRequest(BaseModel):
    topic: str
    target_audience: str
    format_type: str
    district_tag: Optional[str] = None
    content_direction: Optional[str] = None
    length: str = "Standard (3-5 pages)"
    include_disclaimer: bool = True

class UpdateLeadMagnetRequest(BaseModel):
    title: Optional[str] = None
    subtitle: Optional[str] = None
    description: Optional[str] = None
    topic: Optional[str] = None
    target_audience: Optional[str] = None
    format_type: Optional[str] = None
    district_tag: Optional[str] = None
    content_direction: Optional[str] = None
    length: Optional[str] = None
    include_disclaimer: bool = True
    markdown_content: Optional[str] = None
    landing_headline: Optional[str] = None
    landing_body: Optional[str] = None
    landing_cta: Optional[str] = None



# ================== PRODUCT INTAKE MODELS ==================

INTAKE_SOURCE_TYPES = ["email_text", "pasted_order", "manual_entry", "csv_upload", "pdf_upload"]
DRAFT_ITEM_STATUSES = ["needs_info", "in_review", "ready"]
ROUNDING_RULES = ["nearest_99", "nearest_95", "nearest_50", "none"]

DRAFT_ITEM_REQUIRED_FIELDS = [
    "clean_title", "quantity", "unit_cost", "currency",
    "suggested_price", "short_description", "long_description", "category",
]

DEFAULT_TAXONOMY = [
    "Vibrators", "Dildos", "Couples Toys", "Bondage & Restraints",
    "Lubricants & Oils", "Lingerie", "Wellness & Self-Care",
    "Accessories", "Gift Sets", "Education & Books",
    "Bath & Body", "Massage", "Apparel", "Other",
]


class CreateIntakeSessionRequest(BaseModel):
    source_store: str
    order_id: Optional[str] = None
    purchase_date: Optional[str] = None
    notes: Optional[str] = None
    cost_notes: Optional[str] = None


class UpdateIntakeSessionRequest(BaseModel):
    source_store: Optional[str] = None
    order_id: Optional[str] = None
    purchase_date: Optional[str] = None
    notes: Optional[str] = None
    cost_notes: Optional[str] = None


class ExtractTextRequest(BaseModel):
    text: str
    source_type: str = "pasted_order"


class CreateDraftItemRequest(BaseModel):
    source_type: str = "manual_entry"
    source_title: Optional[str] = None
    clean_title: Optional[str] = None
    color: Optional[str] = None
    size: Optional[str] = None
    style: Optional[str] = None
    quantity: Optional[int] = None
    unit_cost: Optional[float] = None
    currency: str = "USD"
    source_url: Optional[str] = None
    notes: Optional[str] = None


class UpdateDraftItemRequest(BaseModel):
    source_title: Optional[str] = None
    clean_title: Optional[str] = None
    short_description: Optional[str] = None
    long_description: Optional[str] = None
    color: Optional[str] = None
    size: Optional[str] = None
    style: Optional[str] = None
    quantity: Optional[int] = None
    unit_cost: Optional[float] = None
    currency: Optional[str] = None
    suggested_price: Optional[float] = None
    category: Optional[str] = None
    tags: Optional[List[str]] = None
    source_url: Optional[str] = None
    status: Optional[str] = None


# ================== CUSTOMER COMMS MODELS ==================

COMMS_CHANNELS = ["email", "sms", "chat"]

COMMS_SCENARIOS = [
    {"key": "order_confirmation", "label": "Order Confirmation Follow-Up", "required_fields": ["order_number"], "optional_fields": ["customer_name", "items_ordered", "delivery_estimate"]},
    {"key": "shipping_delay", "label": "Shipping Delay", "required_fields": ["order_number", "carrier_status"], "optional_fields": ["customer_name", "tracking_number", "expected_date"]},
    {"key": "delivered_not_received", "label": "Delivered But Not Received", "required_fields": ["order_number", "tracking_number"], "optional_fields": ["customer_name", "delivery_date", "carrier"]},
    {"key": "wrong_defective_item", "label": "Wrong / Defective Item", "required_fields": ["order_number", "issue_description"], "optional_fields": ["customer_name", "product_name", "resolution_offered"]},
    {"key": "refund_return", "label": "Refund / Return Request", "required_fields": ["order_number"], "optional_fields": ["customer_name", "product_name", "reason", "refund_amount"]},
    {"key": "discreet_reassurance", "label": "Discreet Packaging / Billing Reassurance", "required_fields": [], "optional_fields": ["customer_name", "concern_details"]},
    {"key": "product_care", "label": "Product Care / Use Guidance", "required_fields": ["product_name"], "optional_fields": ["customer_name", "specific_question"]},
    {"key": "review_request", "label": "Review Request", "required_fields": ["order_number"], "optional_fields": ["customer_name", "product_name", "days_since_delivery"]},
    {"key": "apology_resolution", "label": "Apology + Resolution Update", "required_fields": ["order_number", "issue_summary"], "optional_fields": ["customer_name", "resolution_offered", "timeline"]},
]


class GenerateCommsRequest(BaseModel):
    scenario_key: str
    channel: str = "email"
    customer_message: Optional[str] = None
    context_fields: Optional[Dict[str, str]] = {}
    max_discretion: bool = False
    generate_with_placeholders: bool = False


class SaveFavoriteRequest(BaseModel):
    draft_id: str
    label: Optional[str] = None
    publish_notes: Optional[str] = None


class UpdateIntakeSettingsRequest(BaseModel):
    default_markup_multiplier: Optional[float] = None
    min_price: Optional[float] = None
    rounding_rule: Optional[str] = None
    category_overrides: Optional[Dict[str, float]] = None
    taxonomy: Optional[List[str]] = None
    stuck_days_threshold: Optional[int] = None


# ================== CATALOG MODELS ==================

CATALOG_ITEM_STATUSES = ["Draft", "Needs Review", "Ready", "Exported", "Archived"]

class ImportFromIntakeRequest(BaseModel):
    session_id: Optional[str] = None
    item_ids: Optional[List[str]] = None
    statuses: Optional[List[str]] = None

class CreateCatalogItemRequest(BaseModel):
    title: str
    brand: Optional[str] = None
    short_description: Optional[str] = None
    description: Optional[str] = None
    sku: Optional[str] = None
    regular_price: Optional[float] = None
    category_id: Optional[str] = None
    tags: Optional[List[str]] = None
    attributes: Optional[Dict[str, str]] = None
    color: Optional[str] = None
    size: Optional[str] = None

class UpdateCatalogItemRequest(BaseModel):
    title: Optional[str] = None
    brand: Optional[str] = None
    short_description: Optional[str] = None
    description: Optional[str] = None
    sku: Optional[str] = None
    regular_price: Optional[float] = None
    sale_price: Optional[float] = None
    category_id: Optional[str] = None
    secondary_category_ids: Optional[List[str]] = None
    tags: Optional[List[str]] = None
    attributes: Optional[Dict[str, str]] = None
    color: Optional[str] = None
    size: Optional[str] = None
    status: Optional[str] = None
    image_urls: Optional[List[str]] = None

class CreateCategoryRequest(BaseModel):
    name: str
    parent_id: Optional[str] = None

class UpdateCategoryRequest(BaseModel):
    name: Optional[str] = None
    parent_id: Optional[str] = None

class CreateVariantGroupRequest(BaseModel):
    name: str
    attribute_keys: List[str]
    member_ids: List[str]

class ResolveDuplicateRequest(BaseModel):
    action: str  # "not_duplicate", "merge_keep_left", "merge_keep_right"


# ================== WP PLACEMENT MODELS ==================

WP_PLACEMENT_MODES = ["create", "update"]

# ---- WooCommerce Taxonomy Lane ----
# WooCommerce product-category taxonomy terms are NOT WordPress pages. They
# are read/written via /wp-json/wp/v2/product_cat (a standard taxonomy REST
# route WooCommerce registers under wp/v2, not a separate wc/v3 API), keyed
# by a numeric term_id -- never a page_id. See services/wp_client.py's
# term-aware functions and services/worker_queue.py's
# _execute_wp_taxonomy_update/_execute_wp_taxonomy_create.
TAXONOMY_EXECUTION_TYPES = ["taxonomy_update", "taxonomy_create"]
WOOCOMMERCE_PRODUCT_CATEGORY_OBJECT_TYPE = "woocommerce_product_category"


# ---- WP Write-Safety Models ----
# Unified write-safety contract for ALL WordPress write paths (direct route,
# Worker Queue, and any future OPS worker or execution-manifest task).
# See: safety/unified-wp-write-gate-20260714

class WpExecutionMode(str, Enum):
    """
    mock     -> never touches real WordPress, regardless of credentials present
    dry_run  -> builds/validates content and returns a preview + approval token; no write
    live     -> performs the real WordPress write; requires a valid approval token
    """
    MOCK = "mock"
    DRY_RUN = "dry_run"
    LIVE = "live"

class WpPublicationMode(str, Enum):
    """
    A live write is not automatically permission to publish publicly.
    draft   -> (default) creates/updates a real WordPress draft
    publish -> requires its own explicit authorization; never the implicit default
    """
    DRAFT = "draft"
    PUBLISH = "publish"

class WpApprovalScope(str, Enum):
    SINGLE = "single"
    BATCH = "batch"

class WpWriteApproval(BaseModel):
    """
    Attached to any request/task that may reach the WP client.
    Only execution_mode and approval_token are ever supplied by a caller.
    approved_by / approval_role / approval_source / approved_at are NEVER
    accepted as client input -- they are resolved server-side, from the
    authenticated session, at the moment a token is consumed.
    """
    execution_mode: WpExecutionMode = WpExecutionMode.DRY_RUN
    publication_mode: WpPublicationMode = WpPublicationMode.DRAFT
    approval_token: Optional[str] = None

class WpApprovalRecord(BaseModel):
    """
    Server-side record of an issued approval token. Stored in the
    `wp_write_approvals` collection. Never exposed to the client except
    as the opaque `token` string.
    """
    token: str
    scope: WpApprovalScope
    scope_ids: List[str]
    payload_hash: str
    publication_mode: WpPublicationMode = WpPublicationMode.DRAFT
    # "page" (default, existing pages) or "woocommerce_product_category"
    # (taxonomy lane). A live write must present a token whose object_type
    # matches the operation being performed -- see
    # services/wp_write_safety.consume_approval_token().
    object_type: str = "page"
    issued_at: datetime
    expires_at: datetime
    consumed: bool = False
    consumed_at: Optional[datetime] = None
    # Extensible identity fields -- deliberately not hard-coded to "founder"
    # so future trusted-execution policies or additional authorized roles
    # can be introduced without a data-model redesign.
    approved_by: Optional[str] = None
    approval_role: Optional[str] = None
    approval_source: Optional[str] = None


class WpPlacementRequest(BaseModel):
    mode: str = "create"
    template_id: str = "standard_content"
    target_page_id: Optional[str] = None
    page_title: str
    slug: Optional[str] = None
    page_type: Optional[str] = None
    hero_headline: Optional[str] = None
    subheadline: Optional[str] = None
    intro: Optional[str] = None
    body_section_1: Optional[str] = None
    body_section_2: Optional[str] = None
    body_section_3: Optional[str] = None
    cta_text: Optional[str] = None
    cta_url: Optional[str] = None
    related_links: Optional[List[Dict[str, str]]] = None
    seo_title: Optional[str] = None
    meta_description: Optional[str] = None
    execution: WpWriteApproval = Field(default_factory=WpWriteApproval)

class WpPlacementSettingsUpdate(BaseModel):
    default_status: Optional[str] = None
    preserve_slug_on_update: Optional[bool] = None
    preserve_unmapped_on_update: Optional[bool] = None
    flag_missing_cta: Optional[bool] = None
    save_placement_log: Optional[bool] = None

# ================== EXECUTION MANIFEST LAYER (PHASE 1) ==================
#
# Bridge between final structured campaign/output packets (from TSAF or any
# future source system) and safely routed OPS execution work. Reuses the
# existing Worker Queue rather than replacing it -- an execution manifest
# item, once queued, becomes an ordinary worker_tasks record with
# source_module="execution_manifest".
#
# ARCHITECTURAL LAW (do not violate):
#   TSAF creates.
#   Execution Manifest receives and structures.
#   OPS Execution Queue organizes.
#   OPS operators execute.
#   TSAF is separate from OPS. OPS girls do not directly touch TSAF.
#
# This layer NEVER writes to WordPress itself and NEVER grants live/publish
# authorization. It only creates worker_tasks through the existing,
# unmodified WP write-safety gate -- dry_run stays the default, founder
# approval and a single-use token are still required for any live write,
# exactly as before this layer existed.

class ManifestStatus(str, Enum):
    RECEIVED = "received"
    VALIDATED = "validated"
    NEEDS_REVIEW = "needs_review"
    READY = "ready"
    IN_PROGRESS = "in_progress"
    PARTIALLY_COMPLETED = "partially_completed"
    COMPLETED = "completed"
    BLOCKED = "blocked"
    FAILED = "failed"
    CANCELLED = "cancelled"

class ExecutionItemStatus(str, Enum):
    PENDING = "pending"
    NEEDS_REVIEW = "needs_review"
    READY = "ready"
    QUEUED = "queued"
    PROCESSING = "processing"
    COMPLETED = "completed"
    BLOCKED = "blocked"
    FAILED = "failed"
    CANCELLED = "cancelled"

class DestinationLabel(str, Enum):
    """
    Supporting a destination label here does NOT mean the connector exists.
    See services/execution_manifest.py:DESTINATION_SUPPORT for the actual
    support level of each, and docs/EXECUTION_MANIFEST_SCHEMA.md for the
    documented distinction between recognized / supported now / connector
    unavailable / manual required / future planned.
    """
    WORDPRESS = "wordpress"
    METRICOOL = "metricool"
    FACEBOOK = "facebook"
    INSTAGRAM = "instagram"
    TIKTOK = "tiktok"
    YOUTUBE_SHORTS = "youtube_shorts"
    PINTEREST = "pinterest"
    LINKEDIN = "linkedin"
    EMAIL = "email"
    BLOG = "blog"
    GUIDE = "guide"
    DIGITAL_PRODUCT = "digital_product"
    HUBSPOT = "hubspot"
    ADS = "ads"
    MANUAL = "manual"

class DestinationSupportLevel(str, Enum):
    SUPPORTED_NOW = "supported_now"
    CONNECTOR_UNAVAILABLE = "connector_unavailable"
    MANUAL_REQUIRED = "manual_required"
    UNRECOGNIZED = "unrecognized"


class ExecutionItem(BaseModel):
    item_id: str
    manifest_id: str
    sequence: int = 0
    title: str
    description: Optional[str] = None
    content_type: Optional[str] = None
    destination: str
    channel: Optional[str] = None
    platform: Optional[str] = None
    execution_type: str
    recommended_worker: Optional[str] = None
    task_type: Optional[str] = None
    requires_founder_approval: bool = True
    status: str = ExecutionItemStatus.PENDING.value
    priority: str = "normal"
    due_at: Optional[str] = None
    asset_refs: List[str] = Field(default_factory=list)
    copy: Optional[str] = None
    instructions: Optional[str] = None
    placement: Dict[str, Any] = Field(default_factory=dict)
    compliance_notes: Optional[str] = None
    qa_requirements: List[str] = Field(default_factory=list)
    dependencies: List[str] = Field(default_factory=list)
    context: Dict[str, Any] = Field(default_factory=dict)
    worker_task_id: Optional[str] = None
    result: Dict[str, Any] = Field(default_factory=dict)
    warnings: List[str] = Field(default_factory=list)
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


class ExecutionManifestAsset(BaseModel):
    asset_id: str
    type: Optional[str] = None
    url: Optional[str] = None
    alt_text: Optional[str] = None
    notes: Optional[str] = None


class ExecutionManifest(BaseModel):
    manifest_id: Optional[str] = None  # server-generated if not supplied
    schema_version: str
    source_system: str
    source_packet_id: str
    source_packet_type: Optional[str] = None
    campaign_id: Optional[str] = None
    campaign_name: Optional[str] = None
    brand_id: Optional[str] = None
    brand_name: Optional[str] = None
    created_at: Optional[str] = None
    received_at: Optional[str] = None
    status: str = ManifestStatus.RECEIVED.value
    priority: str = "normal"
    due_at: Optional[str] = None
    created_by: Optional[str] = None
    notes: Optional[str] = None
    execution_items: List[ExecutionItem] = Field(default_factory=list)
    assets: List[ExecutionManifestAsset] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)


class ExecutionManifestCreateRequest(BaseModel):
    """
    Wire model for POST /api/execution-manifests. Deliberately does NOT
    accept execution_mode, approval_token, or any WordPress write-safety
    field anywhere -- those belong exclusively to the existing WP
    write-safety gate and are never settable through a manifest. See
    services/execution_manifest.validate_manifest() for the hard rejection
    of any such field found in item.context.
    """
    manifest_id: Optional[str] = None
    schema_version: str
    source_system: str
    source_packet_id: str
    source_packet_type: Optional[str] = None
    campaign_id: Optional[str] = None
    campaign_name: Optional[str] = None
    brand_id: Optional[str] = None
    brand_name: Optional[str] = None
    priority: str = "normal"
    due_at: Optional[str] = None
    created_by: Optional[str] = None
    notes: Optional[str] = None
    execution_items: List[ExecutionItem]
    assets: List[ExecutionManifestAsset] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)


class QueueItemRequest(BaseModel):
    """Optional override context for a single item queue request. No
    execution_mode/approval_token fields -- see ExecutionManifestCreateRequest."""
    notes: Optional[str] = None


# ================== EXECUTION MANIFEST INTAKE LAYER (PHASE 3) ==================
#
# Intake/transport gateway: lets a finished TSAF campaign packet (or another
# authorized source) enter OPS as a structured Execution Manifest without a
# human rebuilding it manually. This is the OPS *receiving* side only --
# it does not build or modify TSAF, and does not claim a live TSAF
# connection exists until one is actually configured and verified.
#
# The nested `manifest` field always uses the existing, unmodified Phase 1
# ExecutionManifest schema -- this layer creates no second competing
# manifest schema. See services/execution_manifest_intake.py.
#
# NO AUTOMATIC EXECUTION: successful intake creates a manifest via the
# existing Phase 1 create_manifest() only. It never validates+queues,
# never executes Jenny/Rene/WP Placement, never issues a WP approval
# token, never writes to WordPress or any connector. The founder still
# reviews in the existing Phase 2 workspace.

class IntakeSourceSystem(str, Enum):
    TSAF = "tsaf"
    MANUAL = "manual"
    API = "api"
    IMPORT = "import"
    UNKNOWN = "unknown"
    # A recognized source does NOT automatically mean trusted -- trust is
    # established solely by authentication_status on the receipt, never by
    # this label.

class ReceiptStatus(str, Enum):
    RECEIVED = "received"
    AUTHENTICATED = "authenticated"
    REJECTED = "rejected"
    DUPLICATE = "duplicate"
    QUARANTINED = "quarantined"
    VALIDATED = "validated"
    ACCEPTED = "accepted"
    FAILED = "failed"


class InboundPacketAsset(BaseModel):
    """
    Phase 3 accepts and stores asset METADATA/REFERENCES ONLY. No binary
    storage, ZIP extraction, media editing, or CDN upload in this phase.
    """
    asset_id: str
    filename: Optional[str] = None
    type: Optional[str] = None
    mime_type: Optional[str] = None
    dimensions: Optional[str] = None
    url: Optional[str] = None
    path: Optional[str] = None
    checksum: Optional[str] = None
    destination: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


class InboundPacketEnvelope(BaseModel):
    """
    Wire model for both intake paths (/receive and /manual). `manifest` is
    a raw dict validated against the existing Phase 1 schema by
    services/execution_manifest.validate_manifest() -- never a separate
    schema.
    """
    packet_id: str
    packet_version: str = "1.0"
    source_system: str
    source_environment: Optional[str] = None
    source_packet_type: Optional[str] = None
    source_packet_id: Optional[str] = None
    source_created_at: Optional[str] = None
    sent_at: Optional[str] = None
    sender_id: Optional[str] = None
    brand_id: Optional[str] = None
    campaign_id: Optional[str] = None
    campaign_name: Optional[str] = None
    manifest: Dict[str, Any]
    asset_index: List[InboundPacketAsset] = Field(default_factory=list)
    packet_location: Optional[str] = None
    packet_checksum: Optional[str] = None
    idempotency_key: str
    metadata: Dict[str, Any] = Field(default_factory=dict)


class ManualIntakeRequest(BaseModel):
    """POST /api/execution-manifest-intake/manual body -- founder-session only."""
    envelope: InboundPacketEnvelope


class ExecutionManifestReceipt(BaseModel):
    receipt_id: str
    packet_id: Optional[str] = None
    idempotency_key: Optional[str] = None
    source_system: str
    received_at: str
    authentication_status: str
    checksum_status: str
    schema_status: str
    manifest_id: Optional[str] = None
    status: str = ReceiptStatus.RECEIVED.value
    errors: List[str] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)
    raw_packet_hash: Optional[str] = None
    received_by: Optional[str] = None
    transport: str  # "server_to_server" | "manual"
    metadata: Dict[str, Any] = Field(default_factory=dict)
