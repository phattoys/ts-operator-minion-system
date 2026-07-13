import requests
import sys
import json
from datetime import datetime

class TSOperatorAPITester:
    def __init__(self, base_url="https://page-queue-hub.preview.emergentagent.com/api"):
        self.base_url = base_url
        self.token = None
        self.tests_run = 0
        self.tests_passed = 0
        self.test_results = []

    def log_test(self, name, success, details=""):
        """Log test result"""
        self.tests_run += 1
        if success:
            self.tests_passed += 1
        
        result = {
            "test": name,
            "success": success,
            "details": details,
            "timestamp": datetime.now().isoformat()
        }
        self.test_results.append(result)
        
        status = "✅ PASS" if success else "❌ FAIL"
        print(f"{status} - {name}: {details}")

    def run_test(self, name, method, endpoint, expected_status, data=None, headers=None, timeout=30):
        """Run a single API test"""
        url = f"{self.base_url}/{endpoint}"
        test_headers = {'Content-Type': 'application/json'}
        
        if self.token:
            test_headers['Authorization'] = f'Bearer {self.token}'
        if headers:
            test_headers.update(headers)

        try:
            if method == 'GET':
                response = requests.get(url, headers=test_headers, timeout=timeout)
            elif method == 'POST':
                response = requests.post(url, json=data, headers=test_headers, timeout=timeout)
            elif method == 'PUT':
                response = requests.put(url, json=data, headers=test_headers, timeout=timeout)
            elif method == 'DELETE':
                response = requests.delete(url, headers=test_headers, timeout=timeout)

            success = response.status_code == expected_status
            details = f"Status: {response.status_code}"
            
            if not success:
                details += f" (Expected {expected_status})"
                try:
                    error_data = response.json()
                    details += f" - {error_data.get('detail', 'Unknown error')}"
                except:
                    details += f" - {response.text[:100]}"
            
            self.log_test(name, success, details)
            return success, response.json() if success and response.content else {}

        except Exception as e:
            self.log_test(name, False, f"Error: {str(e)}")
            return False, {}

    def test_auth_flow(self):
        """Test authentication endpoints"""
        print("\n🔐 Testing Authentication...")
        
        # Test login with correct password
        success, response = self.run_test(
            "Login with correct password",
            "POST",
            "auth/login",
            200,
            data={"password": "FounderOps2024!"}
        )
        
        if success and 'access_token' in response:
            self.token = response['access_token']
            
            # Test auth verification
            self.run_test(
                "Verify authentication",
                "GET",
                "auth/verify",
                200
            )
            
            # Test logout
            self.run_test(
                "Logout",
                "POST",
                "auth/logout",
                200
            )
            
            return True
        else:
            self.log_test("Authentication setup", False, "Failed to get token")
            return False

    def test_stats_endpoint(self):
        """Test stats endpoint"""
        print("\n📊 Testing Stats...")
        self.run_test(
            "Get dashboard stats",
            "GET",
            "stats",
            200
        )

    def test_pages_endpoints(self):
        """Test page management endpoints"""
        print("\n📄 Testing Page Management...")
        
        # Get all pages
        success, pages_data = self.run_test(
            "Get all pages",
            "GET",
            "pages",
            200
        )
        
        # Get recommended pages
        self.run_test(
            "Get recommended pages",
            "GET",
            "pages/recommended?limit=5",
            200
        )
        
        # Test page creation
        test_page = {
            "page_name": "Test Page API",
            "page_family": "Core Hub",
            "page_type": "Landing",
            "district_or_pillar": "Test",
            "audience": "Test users",
            "purpose": "API testing",
            "CTA_type": "Learn More",
            "notes": "Created by API test"
        }
        
        success, created_page = self.run_test(
            "Create new page",
            "POST",
            "pages",
            201,
            data=test_page
        )
        
        if success and 'id' in created_page:
            page_id = created_page['id']
            
            # Test get specific page
            self.run_test(
                "Get specific page",
                "GET",
                f"pages/{page_id}",
                200
            )
            
            # Test page update
            update_data = {
                "notes": "Updated by API test",
                "status": "Planned"
            }
            self.run_test(
                "Update page",
                "PUT",
                f"pages/{page_id}",
                200,
                data=update_data
            )
            
            # Test content generation (may take time)
            print("  🤖 Testing content generation (may take 30+ seconds)...")
            success, gen_response = self.run_test(
                "Generate page content",
                "POST",
                f"pages/{page_id}/generate",
                200,
                data={"tone": "professional", "additional_instructions": "Keep it brief for testing"}
            )
            
            if success:
                # Test content scoring (may take time)
                print("  🎯 Testing content scoring (may take 30+ seconds)...")
                self.run_test(
                    "Score page content",
                    "POST",
                    f"pages/{page_id}/score",
                    200
                )
                
                # Test approval actions
                self.run_test(
                    "Approve page",
                    "POST",
                    f"pages/{page_id}/approve",
                    200
                )
                
                self.run_test(
                    "Send to rewrite",
                    "POST",
                    f"pages/{page_id}/rewrite",
                    200
                )
                
                self.run_test(
                    "Defer page",
                    "POST",
                    f"pages/{page_id}/defer",
                    200
                )
            
            # Test page deletion
            self.run_test(
                "Delete page",
                "DELETE",
                f"pages/{page_id}",
                200
            )

    def test_settings_endpoints(self):
        """Test settings endpoints"""
        print("\n⚙️ Testing Settings...")
        
        # Get settings
        success, settings_data = self.run_test(
            "Get settings",
            "GET",
            "settings",
            200
        )
        
        if success:
            # Test settings update
            update_settings = {
                "scoring_threshold_strong": 85,
                "scoring_threshold_usable": 70,
                "default_tone": "professional",
                "default_cta": "Learn More"
            }
            self.run_test(
                "Update settings",
                "PUT",
                "settings",
                200,
                data=update_settings
            )

    def test_ecosystem_endpoints(self):
        """Test ecosystem data endpoints"""
        print("\n🌐 Testing Ecosystem Data...")
        
        self.run_test(
            "Get page families",
            "GET",
            "ecosystem/families",
            200
        )
        
        self.run_test(
            "Get page types",
            "GET",
            "ecosystem/types",
            200
        )
        
        self.run_test(
            "Get statuses",
            "GET",
            "ecosystem/statuses",
            200
        )

    def test_activity_endpoint(self):
        """Test activity logging endpoint"""
        print("\n📝 Testing Activity...")
        
        self.run_test(
            "Get activity logs",
            "GET",
            "activity?limit=10",
            200
        )

    def test_seed_endpoint(self):
        """Test seed data endpoint"""
        print("\n🌱 Testing Seed Data...")
        
        self.run_test(
            "Seed ecosystem data",
            "POST",
            "seed",
            200
        )

    def test_new_features(self):
        """Test new features from review request"""
        print("\n🆕 Testing New Features...")
        
        # Test brand voice endpoint
        self.run_test(
            "Get brand voice configuration",
            "GET",
            "brand-voice",
            200
        )
        
        # Test dependency map endpoint
        self.run_test(
            "Get dependency map",
            "GET",
            "pages/dependency-map",
            200
        )
        
        # Test batch generate endpoint
        batch_data = {
            "count": 2,  # Small count for testing
            "tone": "professional",
            "auto_score": True,
            "score_threshold": 70
        }
        print("  🚀 Testing batch generation (may take 60+ seconds)...")
        success, batch_response = self.run_test(
            "Batch generate pages",
            "POST",
            "pages/batch-generate",
            200,
            data=batch_data,
            timeout=120  # Increased timeout for batch generation
        )
        
        if success:
            print(f"    Batch result: {batch_response.get('total_processed', 0)} processed, {batch_response.get('successful', 0)} successful")
        
        # Test export functionality - first get a page to export
        success, pages_data = self.run_test(
            "Get pages for export test",
            "GET",
            "pages?limit=1",
            200
        )
        
        if success and pages_data:
            page_id = pages_data[0]['id']
            
            # Test single page export
            self.run_test(
                "Export single page (markdown)",
                "GET",
                f"pages/{page_id}/export?format=markdown",
                200
            )
            
            self.run_test(
                "Export single page (text)",
                "GET",
                f"pages/{page_id}/export?format=text",
                200
            )
            
            self.run_test(
                "Export single page (json)",
                "GET",
                f"pages/{page_id}/export?format=json",
                200
            )
        
        # Test export all approved pages
        self.run_test(
            "Export all approved pages",
            "GET",
            "pages/export-approved?format=markdown",
            200
        )

    def run_all_tests(self):
        """Run complete test suite"""
        print("🚀 Starting TS Operator Minion v1 API Tests")
        print(f"Testing against: {self.base_url}")
        print("=" * 60)
        
        # Test authentication first
        if not self.test_auth_flow():
            print("❌ Authentication failed - stopping tests")
            return False
        
        # Re-login for subsequent tests
        success, response = self.run_test(
            "Re-login for testing",
            "POST",
            "auth/login",
            200,
            data={"password": "FounderOps2024!"}
        )
        
        if success and 'access_token' in response:
            self.token = response['access_token']
        else:
            print("❌ Re-authentication failed")
            return False
        
        # Run all test suites
        self.test_stats_endpoint()
        self.test_pages_endpoints()
        self.test_settings_endpoints()
        self.test_ecosystem_endpoints()
        self.test_activity_endpoint()
        self.test_seed_endpoint()
        self.test_new_features()  # Add new features test
        
        # Print summary
        print("\n" + "=" * 60)
        print(f"📊 Test Summary: {self.tests_passed}/{self.tests_run} tests passed")
        
        if self.tests_passed == self.tests_run:
            print("🎉 All tests passed!")
            return True
        else:
            print(f"⚠️  {self.tests_run - self.tests_passed} tests failed")
            return False

def main():
    tester = TSOperatorAPITester()
    success = tester.run_all_tests()
    
    # Save detailed results
    with open('/app/backend_test_results.json', 'w') as f:
        json.dump({
            "summary": {
                "total_tests": tester.tests_run,
                "passed_tests": tester.tests_passed,
                "success_rate": f"{(tester.tests_passed/tester.tests_run*100):.1f}%" if tester.tests_run > 0 else "0%",
                "timestamp": datetime.now().isoformat()
            },
            "detailed_results": tester.test_results
        }, f, indent=2)
    
    return 0 if success else 1

if __name__ == "__main__":
    sys.exit(main())