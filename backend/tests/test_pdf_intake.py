"""
PDF Intake Feature Tests
Tests the PDF upload endpoint and PDF parsing functionality for Product Intake Minion.
Features tested:
- POST /api/intake/sessions/{session_id}/upload-pdf
- PDF processing extracts product items (title, SKU, color, size, unit_cost, quantity)
- PDF deduplication merges items by SKU
- PDF auto-detects vendor name (SHEIN)
- Source type 'pdf_upload' stored on items
- Suggested price calculation
- extraction_evidence field with page number and SKU
- Error handling for non-PDF files
- GET /api/intake/sessions/{session_id} returns PDF-imported items
- POST /api/intake/items/{item_id}/check-duplicates works on PDF items
"""
import pytest
import requests
import os
import io

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')
PASSWORD = "TSFounder!Vault2026#Secure"
SHEIN_SESSION_ID = "e54de4dc-5308-4b63-b1e1-f9af5f7d3225"
TEST_PDF_URL = "https://customer-assets.emergentagent.com/job_page-queue-hub/artifacts/jfgjr4ge_shein%20order%201.pdf"


@pytest.fixture(scope="module")
def auth_token():
    """Get authentication token"""
    response = requests.post(
        f"{BASE_URL}/api/auth/login",
        json={"password": PASSWORD}
    )
    assert response.status_code == 200, f"Login failed: {response.text}"
    return response.json()["access_token"]


@pytest.fixture(scope="module")
def auth_headers(auth_token):
    """Headers with auth token"""
    return {"Authorization": f"Bearer {auth_token}"}


class TestExistingSheinSession:
    """Tests for the existing SHEIN PDF session (e54de4dc-5308-4b63-b1e1-f9af5f7d3225)"""
    
    def test_shein_session_exists(self, auth_headers):
        """Verify the SHEIN session exists with 63 items"""
        response = requests.get(
            f"{BASE_URL}/api/intake/sessions/{SHEIN_SESSION_ID}",
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        
        # Verify session metadata
        assert data["id"] == SHEIN_SESSION_ID
        assert data["source_store"] == "SHEIN"
        assert data["item_count"] == 63
        assert len(data["items"]) == 63
        print(f"✓ SHEIN session has {data['item_count']} items")
    
    def test_shein_items_have_pdf_source_type(self, auth_headers):
        """Verify all items have source_type='pdf_upload'"""
        response = requests.get(
            f"{BASE_URL}/api/intake/sessions/{SHEIN_SESSION_ID}",
            headers=auth_headers
        )
        assert response.status_code == 200
        items = response.json()["items"]
        
        pdf_items = [i for i in items if i.get("source_type") == "pdf_upload"]
        assert len(pdf_items) == 63, f"Expected 63 pdf_upload items, got {len(pdf_items)}"
        print(f"✓ All 63 items have source_type='pdf_upload'")
    
    def test_shein_items_have_extraction_evidence(self, auth_headers):
        """Verify items have extraction_evidence with page number and SKU"""
        response = requests.get(
            f"{BASE_URL}/api/intake/sessions/{SHEIN_SESSION_ID}",
            headers=auth_headers
        )
        assert response.status_code == 200
        items = response.json()["items"]
        
        items_with_evidence = [i for i in items if i.get("extraction_evidence")]
        assert len(items_with_evidence) == 63, f"Expected 63 items with evidence, got {len(items_with_evidence)}"
        
        # Check evidence format
        sample = items[0]
        evidence = sample.get("extraction_evidence", "")
        assert "PDF page" in evidence, f"Evidence should contain 'PDF page': {evidence}"
        assert "SKU:" in evidence, f"Evidence should contain 'SKU:': {evidence}"
        print(f"✓ All items have extraction_evidence (sample: {evidence})")
    
    def test_shein_items_have_sku_in_attributes(self, auth_headers):
        """Verify items have SKU in attribute_suggestions"""
        response = requests.get(
            f"{BASE_URL}/api/intake/sessions/{SHEIN_SESSION_ID}",
            headers=auth_headers
        )
        assert response.status_code == 200
        items = response.json()["items"]
        
        items_with_sku = [i for i in items if i.get("attribute_suggestions", {}).get("sku")]
        assert len(items_with_sku) == 63, f"Expected 63 items with SKU, got {len(items_with_sku)}"
        
        # Check SKU format (SHEIN SKUs start with 2 letters followed by digits)
        sample_sku = items[0]["attribute_suggestions"]["sku"]
        assert len(sample_sku) >= 12, f"SKU should be at least 12 chars: {sample_sku}"
        print(f"✓ All items have SKU in attribute_suggestions (sample: {sample_sku})")
    
    def test_shein_items_have_vendor_in_attributes(self, auth_headers):
        """Verify items have vendor='SHEIN' in attribute_suggestions"""
        response = requests.get(
            f"{BASE_URL}/api/intake/sessions/{SHEIN_SESSION_ID}",
            headers=auth_headers
        )
        assert response.status_code == 200
        items = response.json()["items"]
        
        items_with_vendor = [i for i in items if i.get("attribute_suggestions", {}).get("vendor") == "SHEIN"]
        assert len(items_with_vendor) == 63, f"Expected 63 items with vendor=SHEIN, got {len(items_with_vendor)}"
        print(f"✓ All items have vendor='SHEIN' in attribute_suggestions")
    
    def test_shein_items_have_suggested_price(self, auth_headers):
        """Verify items have suggested_price calculated"""
        response = requests.get(
            f"{BASE_URL}/api/intake/sessions/{SHEIN_SESSION_ID}",
            headers=auth_headers
        )
        assert response.status_code == 200
        items = response.json()["items"]
        
        items_with_price = [i for i in items if i.get("suggested_price") is not None]
        assert len(items_with_price) == 63, f"Expected 63 items with suggested_price, got {len(items_with_price)}"
        
        # Check price is reasonable (should be > unit_cost)
        sample = items[0]
        assert sample["suggested_price"] >= sample["unit_cost"], "Suggested price should be >= unit_cost"
        print(f"✓ All items have suggested_price (sample: ${sample['suggested_price']} from cost ${sample['unit_cost']})")
    
    def test_shein_items_have_color_and_size(self, auth_headers):
        """Verify items have color and size extracted"""
        response = requests.get(
            f"{BASE_URL}/api/intake/sessions/{SHEIN_SESSION_ID}",
            headers=auth_headers
        )
        assert response.status_code == 200
        items = response.json()["items"]
        
        items_with_color = [i for i in items if i.get("color")]
        items_with_size = [i for i in items if i.get("size")]
        
        # Most items should have color/size (some may not have variants)
        assert len(items_with_color) > 30, f"Expected >30 items with color, got {len(items_with_color)}"
        assert len(items_with_size) > 30, f"Expected >30 items with size, got {len(items_with_size)}"
        print(f"✓ {len(items_with_color)} items have color, {len(items_with_size)} have size")
    
    def test_shein_items_have_unit_cost(self, auth_headers):
        """Verify items have unit_cost extracted"""
        response = requests.get(
            f"{BASE_URL}/api/intake/sessions/{SHEIN_SESSION_ID}",
            headers=auth_headers
        )
        assert response.status_code == 200
        items = response.json()["items"]
        
        items_with_cost = [i for i in items if i.get("unit_cost") is not None and i["unit_cost"] > 0]
        assert len(items_with_cost) == 63, f"Expected 63 items with unit_cost, got {len(items_with_cost)}"
        
        # Check cost is reasonable for SHEIN (typically $1-$20)
        sample = items[0]
        assert 0.5 < sample["unit_cost"] < 50, f"Unit cost seems unreasonable: ${sample['unit_cost']}"
        print(f"✓ All items have unit_cost (sample: ${sample['unit_cost']})")


class TestPdfUploadEndpoint:
    """Tests for the PDF upload endpoint"""
    
    def test_upload_pdf_requires_auth(self):
        """Verify PDF upload requires authentication"""
        response = requests.post(
            f"{BASE_URL}/api/intake/sessions/{SHEIN_SESSION_ID}/upload-pdf",
            files={"file": ("test.pdf", b"fake pdf content", "application/pdf")}
        )
        assert response.status_code == 401
        print("✓ PDF upload requires authentication (401)")
    
    def test_upload_non_pdf_returns_400(self, auth_headers):
        """Verify uploading non-PDF file returns 400 error"""
        # Create a new test session first
        session_response = requests.post(
            f"{BASE_URL}/api/intake/sessions",
            headers=auth_headers,
            json={"source_store": "TEST_PDF_Error", "order_id": "TEST-NON-PDF"}
        )
        assert session_response.status_code == 200
        test_session_id = session_response.json()["id"]
        
        try:
            # Try uploading a text file as PDF
            response = requests.post(
                f"{BASE_URL}/api/intake/sessions/{test_session_id}/upload-pdf",
                headers=auth_headers,
                files={"file": ("test.txt", b"This is not a PDF", "text/plain")}
            )
            assert response.status_code == 400
            assert "PDF" in response.json().get("detail", "")
            print("✓ Non-PDF file upload returns 400 error")
        finally:
            # Cleanup
            requests.delete(f"{BASE_URL}/api/intake/sessions/{test_session_id}", headers=auth_headers)
    
    def test_upload_pdf_to_nonexistent_session_returns_404(self, auth_headers):
        """Verify uploading to nonexistent session returns 404"""
        response = requests.post(
            f"{BASE_URL}/api/intake/sessions/nonexistent-session-id/upload-pdf",
            headers=auth_headers,
            files={"file": ("test.pdf", b"%PDF-1.4 fake", "application/pdf")}
        )
        assert response.status_code == 404
        print("✓ Upload to nonexistent session returns 404")


class TestDuplicateCheckOnPdfItems:
    """Tests for duplicate checking on PDF-imported items"""
    
    def test_check_duplicates_on_pdf_item(self, auth_headers):
        """Verify duplicate check works on PDF-imported items"""
        # Get first item from SHEIN session
        response = requests.get(
            f"{BASE_URL}/api/intake/sessions/{SHEIN_SESSION_ID}",
            headers=auth_headers
        )
        assert response.status_code == 200
        items = response.json()["items"]
        assert len(items) > 0
        
        item_id = items[0]["id"]
        
        # Check duplicates
        dup_response = requests.get(
            f"{BASE_URL}/api/intake/items/{item_id}/check-duplicates",
            headers=auth_headers
        )
        assert dup_response.status_code == 200
        data = dup_response.json()
        
        assert "item_id" in data
        assert "duplicate_flags" in data
        assert "count" in data
        assert data["item_id"] == item_id
        print(f"✓ Duplicate check works on PDF item (found {data['count']} potential duplicates)")
    
    def test_duplicate_flags_saved_to_item(self, auth_headers):
        """Verify duplicate flags are saved to the item after check"""
        # Get first item
        response = requests.get(
            f"{BASE_URL}/api/intake/sessions/{SHEIN_SESSION_ID}",
            headers=auth_headers
        )
        items = response.json()["items"]
        item_id = items[0]["id"]
        
        # Check duplicates
        requests.get(
            f"{BASE_URL}/api/intake/items/{item_id}/check-duplicates",
            headers=auth_headers
        )
        
        # Verify flags saved
        item_response = requests.get(
            f"{BASE_URL}/api/intake/items/{item_id}",
            headers=auth_headers
        )
        assert item_response.status_code == 200
        item = item_response.json()
        
        assert "duplicate_flags" in item
        print(f"✓ Duplicate flags saved to item ({len(item.get('duplicate_flags', []))} flags)")


class TestPdfUploadWithRealPdf:
    """Tests for uploading the real SHEIN PDF to a new session"""
    
    def test_create_session_and_upload_pdf(self, auth_headers):
        """Create a new session and upload the SHEIN PDF"""
        # Download the test PDF
        pdf_response = requests.get(TEST_PDF_URL, timeout=60)
        if pdf_response.status_code != 200:
            pytest.skip(f"Could not download test PDF: {pdf_response.status_code}")
        
        pdf_content = pdf_response.content
        assert len(pdf_content) > 100000, f"PDF seems too small: {len(pdf_content)} bytes"
        print(f"✓ Downloaded test PDF ({len(pdf_content)} bytes)")
        
        # Create a new test session
        session_response = requests.post(
            f"{BASE_URL}/api/intake/sessions",
            headers=auth_headers,
            json={"source_store": "TEST_PDF_Upload", "order_id": "TEST-PDF-UPLOAD"}
        )
        assert session_response.status_code == 200
        test_session_id = session_response.json()["id"]
        print(f"✓ Created test session: {test_session_id}")
        
        try:
            # Upload the PDF
            upload_response = requests.post(
                f"{BASE_URL}/api/intake/sessions/{test_session_id}/upload-pdf",
                headers=auth_headers,
                files={"file": ("shein_order.pdf", pdf_content, "application/pdf")},
                timeout=120
            )
            
            assert upload_response.status_code == 200, f"Upload failed: {upload_response.text}"
            result = upload_response.json()
            
            # Verify response structure
            assert "uploaded_count" in result
            assert "filename" in result
            assert "total_pages" in result
            assert "product_pages" in result
            assert "raw_item_count" in result
            assert "duplicate_count" in result
            assert "detected_vendor" in result
            assert "items" in result
            
            # Verify counts
            assert result["uploaded_count"] > 50, f"Expected >50 items, got {result['uploaded_count']}"
            assert result["total_pages"] > 40, f"Expected >40 pages, got {result['total_pages']}"
            assert result["duplicate_count"] > 10, f"Expected >10 duplicates merged, got {result['duplicate_count']}"
            assert result["detected_vendor"] == "SHEIN", f"Expected vendor SHEIN, got {result['detected_vendor']}"
            
            print(f"✓ PDF upload successful:")
            print(f"  - Total pages: {result['total_pages']}")
            print(f"  - Product pages: {result['product_pages']}")
            print(f"  - Raw items found: {result['raw_item_count']}")
            print(f"  - Duplicates merged: {result['duplicate_count']}")
            print(f"  - Unique items imported: {result['uploaded_count']}")
            print(f"  - Detected vendor: {result['detected_vendor']}")
            
            # Verify items have correct structure
            if result["items"]:
                sample_item = result["items"][0]
                assert sample_item.get("source_type") == "pdf_upload"
                assert sample_item.get("extraction_evidence")
                assert sample_item.get("attribute_suggestions", {}).get("sku")
                print(f"✓ Sample item has correct structure (SKU: {sample_item['attribute_suggestions']['sku']})")
            
        finally:
            # Cleanup - delete the test session
            requests.delete(f"{BASE_URL}/api/intake/sessions/{test_session_id}", headers=auth_headers)
            print(f"✓ Cleaned up test session")


class TestIntakeSourceTypes:
    """Tests for INTAKE_SOURCE_TYPES including pdf_upload"""
    
    def test_pdf_upload_in_source_types(self, auth_headers):
        """Verify pdf_upload is a valid source type"""
        # Create session and item with pdf_upload source type
        session_response = requests.post(
            f"{BASE_URL}/api/intake/sessions",
            headers=auth_headers,
            json={"source_store": "TEST_Source_Type", "order_id": "TEST-ST"}
        )
        assert session_response.status_code == 200
        test_session_id = session_response.json()["id"]
        
        try:
            # Create item with pdf_upload source type
            item_response = requests.post(
                f"{BASE_URL}/api/intake/sessions/{test_session_id}/items",
                headers=auth_headers,
                json={
                    "source_type": "pdf_upload",
                    "source_title": "Test PDF Item",
                    "unit_cost": 5.99
                }
            )
            assert item_response.status_code == 200
            item = item_response.json()
            assert item["source_type"] == "pdf_upload"
            print("✓ pdf_upload is a valid source type")
        finally:
            requests.delete(f"{BASE_URL}/api/intake/sessions/{test_session_id}", headers=auth_headers)


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
