"""
Lead Magnet Minion Backend Tests
Tests for: CRUD, content generation, PDF generation, publish flow, version history, public download
"""
import pytest
import requests
import os
import time

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', 'https://minion-approval-test.preview.emergentagent.com')
PASSWORD = "TSFounder!Vault2026#Secure"


@pytest.fixture(scope="module")
def auth_token():
    """Get authentication token"""
    response = requests.post(
        f"{BASE_URL}/api/auth/login",
        json={"password": PASSWORD}
    )
    assert response.status_code == 200, f"Auth failed: {response.text}"
    return response.json()["access_token"]


@pytest.fixture(scope="module")
def auth_headers(auth_token):
    """Headers with auth token"""
    return {"Authorization": f"Bearer {auth_token}"}


@pytest.fixture(scope="module")
def created_magnet(auth_headers):
    """Create a test lead magnet for use in other tests"""
    payload = {
        "topic": "TEST_Beginner Guide to Wellness Products",
        "target_audience": "First-time buyers exploring self-care",
        "format_type": "Guide",
        "district_tag": "Education District",
        "content_direction": "Focus on safety and comfort",
        "length": "Standard (3-5 pages)",
        "include_disclaimer": True
    }
    response = requests.post(
        f"{BASE_URL}/api/lead-magnets",
        json=payload,
        headers=auth_headers
    )
    assert response.status_code == 200, f"Create failed: {response.text}"
    magnet = response.json()
    yield magnet
    # Cleanup - try to delete if not published
    try:
        requests.delete(f"{BASE_URL}/api/lead-magnets/{magnet['id']}", headers=auth_headers)
    except:
        pass


class TestLeadMagnetAuth:
    """Authentication tests for lead magnet endpoints"""
    
    def test_list_requires_auth(self):
        """GET /api/lead-magnets requires authentication"""
        response = requests.get(f"{BASE_URL}/api/lead-magnets")
        assert response.status_code == 401
        print("✓ List endpoint requires auth")
    
    def test_stats_requires_auth(self):
        """GET /api/lead-magnets/stats requires authentication"""
        response = requests.get(f"{BASE_URL}/api/lead-magnets/stats")
        assert response.status_code == 401
        print("✓ Stats endpoint requires auth")
    
    def test_create_requires_auth(self):
        """POST /api/lead-magnets requires authentication"""
        response = requests.post(
            f"{BASE_URL}/api/lead-magnets",
            json={"topic": "Test", "target_audience": "Test", "format_type": "Guide", "length": "Short (1-2 pages)"}
        )
        assert response.status_code == 401
        print("✓ Create endpoint requires auth")


class TestLeadMagnetCRUD:
    """CRUD operations for lead magnets"""
    
    def test_create_lead_magnet(self, auth_headers):
        """POST /api/lead-magnets creates a new lead magnet"""
        payload = {
            "topic": "TEST_Quick Start Checklist",
            "target_audience": "New customers",
            "format_type": "Checklist",
            "district_tag": "Onboarding",
            "length": "Short (1-2 pages)",
            "include_disclaimer": False
        }
        response = requests.post(
            f"{BASE_URL}/api/lead-magnets",
            json=payload,
            headers=auth_headers
        )
        assert response.status_code == 200, f"Create failed: {response.text}"
        data = response.json()
        
        # Verify structure
        assert "id" in data
        assert "public_id" in data
        assert data["topic"] == payload["topic"]
        assert data["target_audience"] == payload["target_audience"]
        assert data["format_type"] == "Checklist"
        assert data["status"] == "Draft"
        assert data["has_pdf"] == False
        assert data["download_count"] == 0
        print(f"✓ Created lead magnet: {data['id']}")
        
        # Cleanup
        requests.delete(f"{BASE_URL}/api/lead-magnets/{data['id']}", headers=auth_headers)
    
    def test_create_validation_topic_length(self, auth_headers):
        """Topic must be 3-120 characters"""
        # Too short
        response = requests.post(
            f"{BASE_URL}/api/lead-magnets",
            json={"topic": "AB", "target_audience": "Test audience", "format_type": "Guide", "length": "Short (1-2 pages)"},
            headers=auth_headers
        )
        assert response.status_code == 400
        assert "Topic must be 3-120" in response.json()["detail"]
        print("✓ Topic validation works")
    
    def test_create_validation_format(self, auth_headers):
        """Format must be valid"""
        response = requests.post(
            f"{BASE_URL}/api/lead-magnets",
            json={"topic": "Test Topic", "target_audience": "Test audience", "format_type": "InvalidFormat", "length": "Short (1-2 pages)"},
            headers=auth_headers
        )
        assert response.status_code == 400
        assert "Invalid format" in response.json()["detail"]
        print("✓ Format validation works")
    
    def test_list_lead_magnets(self, auth_headers, created_magnet):
        """GET /api/lead-magnets returns list"""
        response = requests.get(
            f"{BASE_URL}/api/lead-magnets",
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        assert "lead_magnets" in data
        assert isinstance(data["lead_magnets"], list)
        print(f"✓ Listed {len(data['lead_magnets'])} lead magnets")
    
    def test_list_filter_by_status(self, auth_headers, created_magnet):
        """GET /api/lead-magnets?status=Draft filters by status"""
        response = requests.get(
            f"{BASE_URL}/api/lead-magnets?status=Draft",
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        for m in data["lead_magnets"]:
            assert m["status"] == "Draft"
        print("✓ Status filter works")
    
    def test_list_filter_by_format(self, auth_headers, created_magnet):
        """GET /api/lead-magnets?format_type=Guide filters by format"""
        response = requests.get(
            f"{BASE_URL}/api/lead-magnets?format_type=Guide",
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        for m in data["lead_magnets"]:
            assert m["format_type"] == "Guide"
        print("✓ Format filter works")
    
    def test_get_lead_magnet(self, auth_headers, created_magnet):
        """GET /api/lead-magnets/{id} returns single magnet"""
        response = requests.get(
            f"{BASE_URL}/api/lead-magnets/{created_magnet['id']}",
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == created_magnet["id"]
        assert data["topic"] == created_magnet["topic"]
        print(f"✓ Got lead magnet: {data['id']}")
    
    def test_get_nonexistent_magnet(self, auth_headers):
        """GET /api/lead-magnets/{id} returns 404 for nonexistent"""
        response = requests.get(
            f"{BASE_URL}/api/lead-magnets/nonexistent-id-12345",
            headers=auth_headers
        )
        assert response.status_code == 404
        print("✓ 404 for nonexistent magnet")
    
    def test_update_lead_magnet(self, auth_headers, created_magnet):
        """PUT /api/lead-magnets/{id} updates fields"""
        response = requests.put(
            f"{BASE_URL}/api/lead-magnets/{created_magnet['id']}",
            json={"title": "Updated Test Title", "subtitle": "A subtitle"},
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        assert data["title"] == "Updated Test Title"
        assert data["subtitle"] == "A subtitle"
        print("✓ Updated lead magnet")
    
    def test_delete_draft_magnet(self, auth_headers):
        """DELETE /api/lead-magnets/{id} deletes draft magnet"""
        # Create a magnet to delete
        create_resp = requests.post(
            f"{BASE_URL}/api/lead-magnets",
            json={
                "topic": "TEST_To Be Deleted",
                "target_audience": "Test",
                "format_type": "FAQ",
                "length": "Short (1-2 pages)"
            },
            headers=auth_headers
        )
        magnet_id = create_resp.json()["id"]
        
        # Delete it
        response = requests.delete(
            f"{BASE_URL}/api/lead-magnets/{magnet_id}",
            headers=auth_headers
        )
        assert response.status_code == 200
        
        # Verify deleted
        get_resp = requests.get(
            f"{BASE_URL}/api/lead-magnets/{magnet_id}",
            headers=auth_headers
        )
        assert get_resp.status_code == 404
        print("✓ Deleted draft magnet")


class TestLeadMagnetStats:
    """Stats endpoint tests"""
    
    def test_stats_structure(self, auth_headers):
        """GET /api/lead-magnets/stats returns correct structure"""
        response = requests.get(
            f"{BASE_URL}/api/lead-magnets/stats",
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        
        assert "total" in data
        assert "by_status" in data
        assert "by_format" in data
        assert "published_count" in data
        assert "draft_count" in data
        assert "total_downloads" in data
        
        assert isinstance(data["total"], int)
        assert isinstance(data["by_status"], dict)
        assert isinstance(data["by_format"], dict)
        print(f"✓ Stats: total={data['total']}, published={data['published_count']}, drafts={data['draft_count']}")


class TestContentGeneration:
    """Content generation tests (LLM calls - may take 15-30s)"""
    
    def test_generate_content(self, auth_headers, created_magnet):
        """POST /api/lead-magnets/{id}/generate creates content via LLM"""
        response = requests.post(
            f"{BASE_URL}/api/lead-magnets/{created_magnet['id']}/generate",
            headers=auth_headers,
            timeout=60  # LLM calls can take time
        )
        assert response.status_code == 200, f"Generation failed: {response.text}"
        data = response.json()
        
        # Verify content was generated
        assert data["markdown_content"], "No markdown content generated"
        assert data["title"], "No title generated"
        assert data["landing_headline"], "No landing headline generated"
        assert data["landing_body"], "No landing body generated"
        assert data["landing_cta"], "No landing CTA generated"
        assert data["current_version"] >= 1
        print(f"✓ Generated content: title='{data['title'][:50]}...'")
    
    def test_generate_requires_existing_magnet(self, auth_headers):
        """POST /api/lead-magnets/{id}/generate returns 404 for nonexistent"""
        response = requests.post(
            f"{BASE_URL}/api/lead-magnets/nonexistent-id/generate",
            headers=auth_headers
        )
        assert response.status_code == 404
        print("✓ Generate returns 404 for nonexistent magnet")


class TestPDFGeneration:
    """PDF generation and preview tests"""
    
    def test_generate_pdf_requires_content(self, auth_headers):
        """POST /api/lead-magnets/{id}/generate-pdf requires content first"""
        # Create a fresh magnet without content
        create_resp = requests.post(
            f"{BASE_URL}/api/lead-magnets",
            json={
                "topic": "TEST_PDF Test No Content",
                "target_audience": "Test",
                "format_type": "Guide",
                "length": "Short (1-2 pages)"
            },
            headers=auth_headers
        )
        magnet_id = create_resp.json()["id"]
        
        # Try to generate PDF without content
        response = requests.post(
            f"{BASE_URL}/api/lead-magnets/{magnet_id}/generate-pdf",
            headers=auth_headers
        )
        assert response.status_code == 400
        assert "Generate content before" in response.json()["detail"]
        print("✓ PDF generation requires content first")
        
        # Cleanup
        requests.delete(f"{BASE_URL}/api/lead-magnets/{magnet_id}", headers=auth_headers)
    
    def test_generate_pdf_success(self, auth_headers, created_magnet):
        """POST /api/lead-magnets/{id}/generate-pdf creates PDF"""
        # First ensure content exists
        get_resp = requests.get(
            f"{BASE_URL}/api/lead-magnets/{created_magnet['id']}",
            headers=auth_headers
        )
        if not get_resp.json().get("markdown_content"):
            # Generate content first
            requests.post(
                f"{BASE_URL}/api/lead-magnets/{created_magnet['id']}/generate",
                headers=auth_headers,
                timeout=60
            )
        
        # Generate PDF
        response = requests.post(
            f"{BASE_URL}/api/lead-magnets/{created_magnet['id']}/generate-pdf",
            headers=auth_headers
        )
        assert response.status_code == 200, f"PDF generation failed: {response.text}"
        data = response.json()
        assert data["has_pdf"] == True
        print("✓ PDF generated successfully")
    
    def test_preview_pdf(self, auth_headers, created_magnet):
        """GET /api/lead-magnets/{id}/preview-pdf returns PDF"""
        # Ensure PDF exists
        get_resp = requests.get(
            f"{BASE_URL}/api/lead-magnets/{created_magnet['id']}",
            headers=auth_headers
        )
        if not get_resp.json().get("has_pdf"):
            pytest.skip("PDF not generated yet")
        
        response = requests.get(
            f"{BASE_URL}/api/lead-magnets/{created_magnet['id']}/preview-pdf",
            headers=auth_headers
        )
        assert response.status_code == 200
        assert response.headers.get("content-type") == "application/pdf"
        print("✓ PDF preview works")


class TestPublishFlow:
    """Mark Ready, Publish, Archive flow tests"""
    
    def test_mark_ready_validation(self, auth_headers):
        """POST /api/lead-magnets/{id}/mark-ready validates requirements"""
        # Create a fresh magnet
        create_resp = requests.post(
            f"{BASE_URL}/api/lead-magnets",
            json={
                "topic": "TEST_Mark Ready Validation",
                "target_audience": "Test",
                "format_type": "Guide",
                "length": "Short (1-2 pages)"
            },
            headers=auth_headers
        )
        magnet_id = create_resp.json()["id"]
        
        # Try to mark ready without content
        response = requests.post(
            f"{BASE_URL}/api/lead-magnets/{magnet_id}/mark-ready",
            headers=auth_headers
        )
        assert response.status_code == 400
        detail = response.json()["detail"]
        assert "Title is required" in detail or "PDF must be generated" in detail
        print("✓ Mark ready validates requirements")
        
        # Cleanup
        requests.delete(f"{BASE_URL}/api/lead-magnets/{magnet_id}", headers=auth_headers)
    
    def test_publish_requires_ready_status(self, auth_headers):
        """POST /api/lead-magnets/{id}/publish requires Ready status"""
        # Create a fresh magnet
        create_resp = requests.post(
            f"{BASE_URL}/api/lead-magnets",
            json={
                "topic": "TEST_Publish Validation",
                "target_audience": "Test",
                "format_type": "Guide",
                "length": "Short (1-2 pages)"
            },
            headers=auth_headers
        )
        magnet_id = create_resp.json()["id"]
        
        # Try to publish without being Ready
        response = requests.post(
            f"{BASE_URL}/api/lead-magnets/{magnet_id}/publish",
            headers=auth_headers
        )
        assert response.status_code == 400
        assert "Ready status" in response.json()["detail"]
        print("✓ Publish requires Ready status")
        
        # Cleanup
        requests.delete(f"{BASE_URL}/api/lead-magnets/{magnet_id}", headers=auth_headers)
    
    def test_archive_magnet(self, auth_headers, created_magnet):
        """POST /api/lead-magnets/{id}/archive archives the magnet"""
        response = requests.post(
            f"{BASE_URL}/api/lead-magnets/{created_magnet['id']}/archive",
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "Archived"
        print("✓ Archived lead magnet")
    
    def test_cannot_delete_published(self, auth_headers):
        """DELETE /api/lead-magnets/{id} fails for published magnets"""
        # Create and fully publish a magnet
        create_resp = requests.post(
            f"{BASE_URL}/api/lead-magnets",
            json={
                "topic": "TEST_Cannot Delete Published",
                "target_audience": "Test audience for deletion test",
                "format_type": "Checklist",
                "length": "Short (1-2 pages)"
            },
            headers=auth_headers
        )
        magnet_id = create_resp.json()["id"]
        
        # Generate content
        requests.post(
            f"{BASE_URL}/api/lead-magnets/{magnet_id}/generate",
            headers=auth_headers,
            timeout=60
        )
        
        # Generate PDF
        requests.post(
            f"{BASE_URL}/api/lead-magnets/{magnet_id}/generate-pdf",
            headers=auth_headers
        )
        
        # Mark ready
        requests.post(
            f"{BASE_URL}/api/lead-magnets/{magnet_id}/mark-ready",
            headers=auth_headers
        )
        
        # Publish
        requests.post(
            f"{BASE_URL}/api/lead-magnets/{magnet_id}/publish",
            headers=auth_headers
        )
        
        # Try to delete
        response = requests.delete(
            f"{BASE_URL}/api/lead-magnets/{magnet_id}",
            headers=auth_headers
        )
        assert response.status_code == 400
        assert "Cannot delete a published" in response.json()["detail"]
        print("✓ Cannot delete published magnet")
        
        # Archive it instead for cleanup
        requests.post(f"{BASE_URL}/api/lead-magnets/{magnet_id}/archive", headers=auth_headers)


class TestVersionHistory:
    """Version history tests"""
    
    def test_list_versions(self, auth_headers, created_magnet):
        """GET /api/lead-magnets/{id}/versions returns version list"""
        response = requests.get(
            f"{BASE_URL}/api/lead-magnets/{created_magnet['id']}/versions",
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        
        assert "lead_magnet_id" in data
        assert "versions" in data
        assert isinstance(data["versions"], list)
        print(f"✓ Listed {len(data['versions'])} versions")
    
    def test_restore_version(self, auth_headers, created_magnet):
        """POST /api/lead-magnets/{id}/versions/{version_id}/restore restores version"""
        # Get versions
        versions_resp = requests.get(
            f"{BASE_URL}/api/lead-magnets/{created_magnet['id']}/versions",
            headers=auth_headers
        )
        versions = versions_resp.json().get("versions", [])
        
        if len(versions) < 1:
            pytest.skip("No versions to restore")
        
        version_id = versions[0]["id"]
        
        response = requests.post(
            f"{BASE_URL}/api/lead-magnets/{created_magnet['id']}/versions/{version_id}/restore",
            headers=auth_headers
        )
        assert response.status_code == 200
        print("✓ Version restore works")


class TestPublicDownload:
    """Public download endpoint tests (no auth required)"""
    
    def test_public_download_not_found(self):
        """GET /api/lm/{public_id}/download returns 404 for nonexistent"""
        response = requests.get(f"{BASE_URL}/api/lm/nonexistent-public-id/download")
        assert response.status_code == 404
        print("✓ Public download returns 404 for nonexistent")
    
    def test_public_download_requires_published(self, auth_headers):
        """GET /api/lm/{public_id}/download requires Published status"""
        # Create a draft magnet
        create_resp = requests.post(
            f"{BASE_URL}/api/lead-magnets",
            json={
                "topic": "TEST_Public Download Draft",
                "target_audience": "Test",
                "format_type": "Guide",
                "length": "Short (1-2 pages)"
            },
            headers=auth_headers
        )
        magnet = create_resp.json()
        
        # Try to download (should fail - not published)
        response = requests.get(f"{BASE_URL}/api/lm/{magnet['public_id']}/download")
        assert response.status_code == 404
        print("✓ Public download requires Published status")
        
        # Cleanup
        requests.delete(f"{BASE_URL}/api/lead-magnets/{magnet['id']}", headers=auth_headers)


class TestFullPublishFlow:
    """End-to-end publish flow test"""
    
    def test_full_flow_create_to_publish(self, auth_headers):
        """Full flow: Create -> Generate -> PDF -> Mark Ready -> Publish -> Download"""
        # 1. Create
        create_resp = requests.post(
            f"{BASE_URL}/api/lead-magnets",
            json={
                "topic": "TEST_Full Flow E2E Test",
                "target_audience": "Testing automation users",
                "format_type": "Checklist",
                "length": "Short (1-2 pages)",
                "include_disclaimer": True
            },
            headers=auth_headers
        )
        assert create_resp.status_code == 200
        magnet = create_resp.json()
        magnet_id = magnet["id"]
        public_id = magnet["public_id"]
        print(f"  1. Created magnet: {magnet_id}")
        
        # 2. Generate content
        gen_resp = requests.post(
            f"{BASE_URL}/api/lead-magnets/{magnet_id}/generate",
            headers=auth_headers,
            timeout=60
        )
        assert gen_resp.status_code == 200
        assert gen_resp.json()["markdown_content"]
        print("  2. Generated content")
        
        # 3. Generate PDF
        pdf_resp = requests.post(
            f"{BASE_URL}/api/lead-magnets/{magnet_id}/generate-pdf",
            headers=auth_headers
        )
        assert pdf_resp.status_code == 200
        assert pdf_resp.json()["has_pdf"] == True
        print("  3. Generated PDF")
        
        # 4. Mark Ready
        ready_resp = requests.post(
            f"{BASE_URL}/api/lead-magnets/{magnet_id}/mark-ready",
            headers=auth_headers
        )
        assert ready_resp.status_code == 200
        assert ready_resp.json()["status"] == "Ready"
        print("  4. Marked Ready")
        
        # 5. Publish
        pub_resp = requests.post(
            f"{BASE_URL}/api/lead-magnets/{magnet_id}/publish",
            headers=auth_headers
        )
        assert pub_resp.status_code == 200
        pub_data = pub_resp.json()
        assert pub_data["status"] == "Published"
        assert pub_data["embed_code"]
        print("  5. Published")
        
        # 6. Public download
        dl_resp = requests.get(f"{BASE_URL}/api/lm/{public_id}/download")
        assert dl_resp.status_code == 200
        assert dl_resp.headers.get("content-type") == "application/pdf"
        print("  6. Public download works")
        
        # 7. Verify download count incremented
        get_resp = requests.get(
            f"{BASE_URL}/api/lead-magnets/{magnet_id}",
            headers=auth_headers
        )
        assert get_resp.json()["download_count"] >= 1
        print("  7. Download count incremented")
        
        # Archive for cleanup (can't delete published)
        requests.post(f"{BASE_URL}/api/lead-magnets/{magnet_id}/archive", headers=auth_headers)
        print("✓ Full publish flow completed successfully")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
