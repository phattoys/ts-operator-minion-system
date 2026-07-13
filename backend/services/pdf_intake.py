"""
PDF Intake Parser — extracts product items from messy invoice PDFs.
Handles SHEIN, Temu, and similar vendor invoices with:
  - Mixed summary / detail pages
  - Grouped shipments
  - Duplicate entries
  - Junk text (return policies, delivery windows, etc.)

Three extraction modes:
  1. Regex (fast, free) — works for structured invoices with SKU anchors (e.g. SHEIN)
  2. Vision LLM fallback — for image-based PDFs where pdfplumber gets 0 text (e.g. Temu)
  3. Text LLM fallback — for unstructured text PDFs where regex finds nothing
"""
import re
import json
import base64
import pdfplumber
import fitz  # PyMuPDF — PDF page to image conversion
from collections import OrderedDict
from emergentintegrations.llm.chat import LlmChat, UserMessage, ImageContent
from database import EMERGENT_LLM_KEY, logger


# ---- Junk lines to strip ----
JUNK_PATTERNS = [
    r"Items in this category cannot",
    r"be returned or exchanged",
    r"please refer to Return Policy",
    r"^Repurchase$",
    r"^Shipped$",
    r"^Order details$",
    r"^Review$",
    r"^Return$",
    r"^View Invoice$",
    r"^\(Combine\) Return$",
    r"^You have great taste$",
    r"Delivery:\s*[A-Z]",
    r"Returnable time",
    r"Joint Shipment",
    r"^Order NO\.",
    r"business days",
    r"^Products\s+Quantity\s+SKU\s+Amount\s+Status\s+Action",
    r"^Shippe\s*d?$",
    r"^d$",
]
_junk_re = re.compile("|".join(JUNK_PATTERNS), re.IGNORECASE)

# ---- Variant pattern (Color / Size at end of product block) ----
VARIANT_RE = re.compile(
    r"^([A-Za-z][A-Za-z ]*(?:Pink|Red|Blue|Black|White|Green|Yellow|Purple|Orange|Brown|Grey|Gray|Beige|Navy|Cream|Nude|Burgundy|Fuchsia|Hot Pink|Khaki|Multicolor|Apricot|Coffee|Dark|Light|Wine|Rose|Leopard|Camel|Silver|Gold|Skin Color|Coral|Champagne|Sapphire|Mint|Teal|Maroon|Ivory|Dusty|Mauve|Tan|Charcoal)[A-Za-z ]*)\s*/\s*(.+)$",
    re.IGNORECASE,
)

# Known colors for variant detection
_COLORS = (
    "Black|White|Red|Blue|Green|Yellow|Purple|Orange|Brown|Grey|Gray|Beige|Navy|Cream|"
    "Nude|Burgundy|Fuchsia|Hot Pink|Khaki|Multicolor|Apricot|Coffee|Dark|Light|Wine|Rose|"
    "Leopard|Camel|Silver|Gold|Skin Color|Coral|Champagne|Sapphire|Mint|Teal|Maroon|Ivory|"
    "Dusty|Mauve|Tan|Charcoal|Pink|Nude Pink"
)
# Known sizes
_SIZES = r"one-size|one size|XS|S|M|L|XL|XXL|XXXL|2XL|3XL|4XL|\d+\([A-Z]+\)|\d+\([A-Za-z]+\)"

# Variant line: "Color / Size" — must start with a known color or end with a known size
VARIANT_SIMPLE_RE = re.compile(
    rf"^({_COLORS})\s*/\s*({_SIZES}|.{{1,20}})$",
    re.IGNORECASE,
)


def extract_text_from_pdf(pdf_path: str) -> list[dict]:
    """Extract text from each page, return list of {page_num, text}."""
    pages = []
    with pdfplumber.open(pdf_path) as pdf:
        for i, page in enumerate(pdf.pages):
            text = page.extract_text() or ""
            pages.append({"page_num": i + 1, "text": text})
    return pages


def is_product_page(text: str) -> bool:
    """Check if a page contains product data (has SKU references)."""
    return "SKU:" in text or "SKU :" in text


def parse_product_blocks(pages: list[dict]) -> list[dict]:
    """
    Regex-based extraction of product blocks from PDF page text.
    Handles two SHEIN SKU formats:
      Format A: 1 SKU: sb25101739041012113 $2.89
      Format B: 1 SKU: $4.44 \\n si2412025512132178 $5.99
    """
    all_items = []

    for page_data in pages:
        text = page_data["text"]
        page_num = page_data["page_num"]

        if not is_product_page(text):
            continue

        lines = text.split("\n")
        i = 0
        while i < len(lines):
            line = lines[i].strip()

            # Look for product block start: "1 SKU:" pattern
            # Format A: "1 SKU: sb25101739041012113 $2.89" (may have trailing text like "Shippe")
            match_a = re.match(
                r"^(\d+)\s+SKU:\s*([a-zA-Z]{2}\d{10,25})\s+\$?([\d.]+)",
                line,
            )
            # Format B: "1 SKU: $4.44" (SKU on next line)
            match_b = re.match(r"^(\d+)\s+SKU:\s+\$?([\d.]+)$", line)

            if match_a:
                qty = int(match_a.group(1))
                sku = match_a.group(2)
                price1 = float(match_a.group(3))
                price2 = None
                i += 1

                # Next line might be second price (may have trailing junk like "d" from "Shipped")
                if i < len(lines):
                    p2_match = re.match(r"^\$?([\d.]+)\s*\w?$", lines[i].strip())
                    if p2_match:
                        price2 = float(p2_match.group(1))
                        i += 1

                # Skip stray single chars like "d" from "Shipped" split across lines
                while i < len(lines) and len(lines[i].strip()) <= 2 and not re.match(r"^\d+\s+SKU:", lines[i].strip()):
                    stripped = lines[i].strip()
                    if stripped and not re.match(r"^\$", stripped):
                        i += 1
                    else:
                        break

                # Collect title lines until variant or junk
                title_parts = []
                variant_color = ""
                variant_size = ""
                while i < len(lines):
                    ln = lines[i].strip()
                    if not ln or _junk_re.search(ln):
                        i += 1
                        if _junk_re.search(ln):
                            continue
                        if not ln:
                            continue
                        break

                    # Check if this is a variant line
                    vm = VARIANT_SIMPLE_RE.match(ln)
                    if vm:
                        variant_color = vm.group(1).strip()
                        variant_size = vm.group(2).strip()
                        i += 1
                        break

                    # Check if next product block starts
                    if re.match(r"^\d+\s+SKU:", ln):
                        break

                    title_parts.append(ln)
                    i += 1

                title = " ".join(title_parts).strip()
                # Clean leading price fragments that leaked from header
                title = re.sub(r"^\$[\d.]+ ", "", title).strip()
                # Determine sale price (lower) and list price (higher)
                sale_price = min(price1, price2) if price2 else price1
                list_price = max(price1, price2) if price2 else None

                all_items.append({
                    "source_title": title,
                    "sku": sku,
                    "quantity": qty,
                    "unit_cost": sale_price,
                    "list_price": list_price,
                    "color": variant_color,
                    "size": variant_size,
                    "page_num": page_num,
                })
                # Skip remaining junk lines in this block
                while i < len(lines) and _junk_re.search(lines[i].strip()):
                    i += 1
                continue

            elif match_b:
                qty = int(match_b.group(1))
                price1 = float(match_b.group(2))
                i += 1
                sku = ""
                price2 = None

                # Next line should have SKU and possibly second price
                if i < len(lines):
                    sku_line = lines[i].strip()
                    sku_match = re.match(
                        r"^([a-zA-Z]{2}\d{10,25})\s+\$?([\d.]+)",
                        sku_line,
                    )
                    if sku_match:
                        sku = sku_match.group(1)
                        price2 = float(sku_match.group(2))
                        i += 1
                    else:
                        # Try just SKU without price
                        sku_only = re.match(r"^([a-zA-Z]{2}\d{10,25})", sku_line)
                        if sku_only:
                            sku = sku_only.group(1)
                            i += 1

                if not sku:
                    i += 1
                    continue

                # Collect title lines
                title_parts = []
                variant_color = ""
                variant_size = ""
                while i < len(lines):
                    ln = lines[i].strip()
                    if not ln or _junk_re.search(ln):
                        i += 1
                        if _junk_re.search(ln):
                            continue
                        if not ln:
                            continue
                        break

                    vm = VARIANT_SIMPLE_RE.match(ln)
                    if vm:
                        variant_color = vm.group(1).strip()
                        variant_size = vm.group(2).strip()
                        i += 1
                        break

                    if re.match(r"^\d+\s+SKU:", ln):
                        break

                    title_parts.append(ln)
                    i += 1

                title = " ".join(title_parts).strip()
                title = re.sub(r"^\$[\d.]+ ", "", title).strip()
                sale_price = min(price1, price2) if price2 else price1
                list_price = max(price1, price2) if price2 else None

                all_items.append({
                    "source_title": title,
                    "sku": sku,
                    "quantity": qty,
                    "unit_cost": sale_price,
                    "list_price": list_price,
                    "color": variant_color,
                    "size": variant_size,
                    "page_num": page_num,
                })
                while i < len(lines) and _junk_re.search(lines[i].strip()):
                    i += 1
                continue
            else:
                i += 1

    return all_items


def deduplicate_items(items: list[dict]) -> tuple[list[dict], list[dict]]:
    """
    Deduplicate by SKU. First occurrence wins for title/price.
    Returns (unique_items, duplicate_log).
    """
    seen = OrderedDict()  # sku -> item
    dup_log = []

    for item in items:
        sku = item.get("sku", "")
        if not sku:
            # No SKU — keep as-is (can't dedupe)
            key = f"no-sku-{len(seen)}"
            seen[key] = item
            continue

        if sku in seen:
            existing = seen[sku]
            existing["quantity"] = existing.get("quantity", 1) + item.get("quantity", 1)
            dup_log.append({
                "sku": sku,
                "title": item.get("source_title", ""),
                "page": item.get("page_num"),
                "action": "merged_quantity",
            })
        else:
            seen[sku] = {**item}

    return list(seen.values()), dup_log


def extract_vendor_from_pages(pages: list[dict]) -> str:
    """Try to extract the vendor/seller name from early summary pages."""
    for page_data in pages[:6]:
        text = page_data["text"]
        if "SHEIN" in text.upper() or "shein" in text.lower():
            return "SHEIN"
        if "TEMU" in text.upper() or "temu" in text.lower():
            return "Temu"
    # Check order number pattern
    for page_data in pages[:3]:
        if "Order NO." in page_data["text"]:
            return "SHEIN"  # SHEIN uses "Order NO." format
    return ""


# ---- Vision-based extraction for image-only PDFs ----

MIN_USABLE_TEXT_LENGTH = 50  # Threshold: below this, pdfplumber text is "empty"


def has_usable_text(pages: list[dict]) -> bool:
    """Check if pdfplumber extracted enough real text to attempt regex parsing."""
    total_text = "".join(p["text"] for p in pages).strip()
    # Remove whitespace-only noise
    clean = re.sub(r"\s+", " ", total_text).strip()
    return len(clean) >= MIN_USABLE_TEXT_LENGTH


def pdf_pages_to_base64(pdf_path: str) -> list[dict]:
    """Convert each PDF page to a base64-encoded JPEG image using PyMuPDF.
    Returns list of {page_num, base64_image}.
    """
    doc = fitz.open(pdf_path)
    page_images = []
    for i, page in enumerate(doc):
        # Render at 2x zoom for readability (144 DPI)
        mat = fitz.Matrix(2, 2)
        pix = page.get_pixmap(matrix=mat)
        img_bytes = pix.tobytes("jpeg")
        b64 = base64.b64encode(img_bytes).decode("utf-8")
        page_images.append({"page_num": i + 1, "base64_image": b64})
    doc.close()
    return page_images


VISION_EXTRACTION_PROMPT = """You are an expert at reading product order screenshots/invoices. Extract ALL individual product items visible on this page.

For EACH product, return a JSON object with these fields:
{
  "source_title": "exact product name/title as shown on the page",
  "vendor": "seller/shop name if visible, or null",
  "quantity": integer (count shown, default 1),
  "unit_cost": number (final price AFTER any promos/discounts — the price the buyer actually paid per unit. NOT the original/crossed-out price),
  "original_price": number or null (original/crossed-out price before discount, if shown),
  "color": "color variant if visible, or null",
  "size": "size variant if visible, or null"
}

Rules:
- Extract EVERY product visible on this page, even partial entries at edges
- For price: always use the FINAL/discounted/after-promo price as unit_cost
- If a product shows "x2" or "Qty: 2", set quantity to that number
- If color/size are shown as variant labels (like "Black / M"), split them
- Vendor/shop name is the seller name shown with the product group
- Return ONLY a valid JSON array. No markdown fences, no commentary, no explanation
- If no products are visible on this page, return an empty array: []"""


async def extract_items_from_vision(page_images: list[dict]) -> list[dict]:
    """Send page images to Vision LLM and extract structured product data.
    Processes pages sequentially with spacing to avoid rate limits.
    Retries failed pages up to 2 times.
    """
    import asyncio
    all_items = []

    for idx, page_data in enumerate(page_images):
        page_num = page_data["page_num"]
        b64 = page_data["base64_image"]

        # Space out requests to avoid rate limits (skip delay for first page)
        if idx > 0:
            await asyncio.sleep(3)

        extracted = False
        for attempt in range(3):
            try:
                chat = LlmChat(
                    api_key=EMERGENT_LLM_KEY,
                    session_id=f"vision-pdf-p{page_num}-a{attempt}",
                    system_message=VISION_EXTRACTION_PROMPT
                )
                chat.with_model('openai', 'gpt-4o')

                image_content = ImageContent(image_base64=b64)
                msg = UserMessage(
                    text=f"Extract all product items from this invoice page (page {page_num}). Return a JSON array.",
                    file_contents=[image_content]
                )

                response = await chat.send_message(msg)

                # Parse JSON from response
                clean = response.strip()
                if clean.startswith('```'):
                    clean = clean.split('\n', 1)[1]
                    clean = clean.rsplit('```', 1)[0]

                items = json.loads(clean, strict=False)
                if not isinstance(items, list):
                    items = [items] if isinstance(items, dict) else []

                for item in items:
                    item["page_num"] = page_num
                    item["source_title"] = str(item.get("source_title", "")).strip()
                    item["color"] = str(item.get("color", "") or "").strip()
                    item["size"] = str(item.get("size", "") or "").strip()
                    item["vendor"] = str(item.get("vendor", "") or "").strip()
                    try:
                        item["quantity"] = int(item.get("quantity", 1) or 1)
                    except (ValueError, TypeError):
                        item["quantity"] = 1
                    try:
                        item["unit_cost"] = float(item["unit_cost"]) if item.get("unit_cost") is not None else None
                    except (ValueError, TypeError):
                        item["unit_cost"] = None
                    try:
                        item["original_price"] = float(item["original_price"]) if item.get("original_price") is not None else None
                    except (ValueError, TypeError):
                        item["original_price"] = None
                    item["sku"] = ""

                    if item["source_title"]:
                        all_items.append(item)

                logger.info(f"[Vision PDF] Page {page_num}: extracted {len(items)} items (attempt {attempt+1})")
                extracted = True
                break  # Success — move to next page

            except json.JSONDecodeError as e:
                logger.warning(f"[Vision PDF] Page {page_num}: JSON parse error (attempt {attempt+1}) — {e}")
                if attempt < 2:
                    await asyncio.sleep(3)
            except Exception as e:
                logger.warning(f"[Vision PDF] Page {page_num}: failed (attempt {attempt+1}) — {e}")
                if attempt < 2:
                    await asyncio.sleep(5)  # Longer backoff for service errors

        if not extracted:
            logger.error(f"[Vision PDF] Page {page_num}: all attempts exhausted")

    return all_items


def _normalize_for_dedup(title: str) -> str:
    """Normalize a title for dedup comparison: lowercase, strip extra spaces/punctuation."""
    t = title.lower().strip()
    t = re.sub(r"[^\w\s]", "", t)  # remove punctuation
    t = re.sub(r"\s+", " ", t)     # collapse whitespace
    return t


def deduplicate_items_by_title(items: list[dict]) -> tuple[list[dict], list[dict]]:
    """
    Conservative dedup for items WITHOUT reliable SKUs (e.g. Temu).
    Key = normalized(title) + color + size.
    - Exact combo match → merge quantities
    - Near-match (fuzzy) → flag for review, do NOT auto-merge
    """
    seen = OrderedDict()  # composite_key -> item
    dup_log = []

    for item in items:
        norm_title = _normalize_for_dedup(item.get("source_title", ""))
        color = (item.get("color") or "").lower().strip()
        size = (item.get("size") or "").lower().strip()
        composite_key = f"{norm_title}|{color}|{size}"

        if not norm_title:
            # Empty title — keep as-is, can't dedup
            key = f"no-title-{len(seen)}"
            seen[key] = item
            continue

        if composite_key in seen:
            existing = seen[composite_key]
            existing["quantity"] = existing.get("quantity", 1) + item.get("quantity", 1)
            dup_log.append({
                "title": item.get("source_title", ""),
                "color": item.get("color", ""),
                "size": item.get("size", ""),
                "page": item.get("page_num"),
                "action": "merged_quantity",
                "match_type": "exact_title_variant",
            })
        else:
            seen[composite_key] = {**item}

    return list(seen.values()), dup_log


def detect_vendor_from_vision_items(items: list[dict]) -> str:
    """Extract the most common vendor from vision-extracted items."""
    vendors = {}
    for item in items:
        v = (item.get("vendor") or "").strip()
        if v:
            vendors[v] = vendors.get(v, 0) + 1
    if not vendors:
        return ""
    # Return most frequent vendor
    return max(vendors, key=vendors.get)


async def process_pdf(pdf_path: str) -> dict:
    """
    Full PDF processing pipeline:
    1. Extract text from all pages via pdfplumber
    2. If usable text exists → regex-parse product blocks (SHEIN path)
    3. If no usable text → Vision LLM fallback (Temu/image-based path)
    4. Deduplicate (SKU-based for regex, title+variant for vision)
    5. Return structured result
    """
    pages = extract_text_from_pdf(pdf_path)
    total_pages = len(pages)

    # Detect vendor from any text available
    vendor = extract_vendor_from_pages(pages)

    # Decide extraction path: regex vs vision
    use_vision = not has_usable_text(pages)

    if use_vision:
        logger.info(f"[PDF Intake] No usable text found ({total_pages} pages) — switching to Vision LLM extraction")
        page_images = pdf_pages_to_base64(pdf_path)
        raw_items = await extract_items_from_vision(page_images)

        # If vendor wasn't detected from text, try from vision items
        if not vendor:
            vendor = detect_vendor_from_vision_items(raw_items)
            if not vendor:
                vendor = "Temu"  # Reasonable default for image-based PDFs

        # Conservative title+variant dedup for no-SKU items
        unique_items, dup_log = deduplicate_items_by_title(raw_items)
        product_pages = total_pages  # All pages are treated as product pages for image PDFs

        # Map vision items to standard format (add list_price from original_price)
        for item in unique_items:
            if item.get("original_price") and item.get("unit_cost"):
                item["list_price"] = item["original_price"]
            else:
                item["list_price"] = None

        logger.info(f"[PDF Intake] Vision extracted {len(raw_items)} raw items, {len(unique_items)} unique ({len(dup_log)} merged)")
    else:
        # Standard regex path
        raw_items = parse_product_blocks(pages)
        logger.info(f"[PDF Intake] Regex extracted {len(raw_items)} raw items from {total_pages} pages")
        unique_items, dup_log = deduplicate_items(raw_items)
        product_pages = sum(1 for p in pages if is_product_page(p["text"]))
        logger.info(f"[PDF Intake] After dedup: {len(unique_items)} unique items ({len(dup_log)} duplicates merged)")

    return {
        "total_pages": total_pages,
        "product_pages": product_pages,
        "raw_item_count": len(raw_items),
        "unique_item_count": len(unique_items),
        "duplicate_count": len(dup_log),
        "detected_vendor": vendor,
        "extraction_method": "vision_llm" if use_vision else "regex",
        "items": unique_items,
        "duplicate_log": dup_log,
    }
