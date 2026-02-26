#!/usr/bin/env python3
"""
Simple endpoint verification script for MCQ Generator API
"""

import json
import time

import requests

BASE_URL = "http://localhost:7560"

def test_endpoint(endpoint, description):
    """Test a single endpoint and report results."""
    print(f"\n{'='*60}")
    print(f"Testing: {description}")
    print(f"Endpoint: {endpoint}")
    print(f"{'='*60}")

    try:
        response = requests.get(f"{BASE_URL}{endpoint}", timeout=10)

        print(f"Status Code: {response.status_code}")
        print(f"Content-Type: {response.headers.get('content-type', 'N/A')}")

        if response.status_code == 200:
            try:
                data = response.json()
                print(f"Response (JSON): {json.dumps(data, indent=2)[:500]}...")
            except Exception:
                print(f"Response (text): {response.text[:500]}...")
            print("✅ SUCCESS")
        else:
            print(f"❌ FAILED - Status: {response.status_code}")
            print(f"Response: {response.text[:500]}...")

    except requests.exceptions.RequestException as e:
        print(f"❌ ERROR - {e}")

    return response.status_code == 200

def main():
    """Run all endpoint tests."""
    print("MCQ Generator API Endpoint Verification")
    print("=" * 60)
    print(f"Base URL: {BASE_URL}")

    # Wait a moment for services to be ready
    print("\nWaiting for services to be ready...")
    time.sleep(2)

    # Test endpoints
    tests = [
        ("/health", "Health Check"),
        ("/ready", "Readiness Probe"),
        ("/metrics", "Metrics Endpoint"),
        ("/docs", "API Documentation"),
        ("/openapi.json", "OpenAPI Schema"),
        ("/api/v1/jobs", "Jobs List"),
        ("/api/v1/datasets/search", "Dataset Search"),
        ("/api/v1/exports/formats", "Export Formats"),
    ]

    results = []
    for endpoint, description in tests:
        success = test_endpoint(endpoint, description)
        results.append((endpoint, description, success))
        time.sleep(0.5)  # Small delay between requests

    # Summary
    print(f"\n{'='*60}")
    print("SUMMARY")
    print(f"{'='*60}")

    passed = sum(1 for _, _, success in results if success)
    total = len(results)

    print(f"Total Tests: {total}")
    print(f"Passed: {passed}")
    print(f"Failed: {total - passed}")
    print(f"Success Rate: {passed/total*100:.1f}%")

    print("\nDetailed Results:")
    for endpoint, description, success in results:
        status = "✅ PASS" if success else "❌ FAIL"
        print(f"  {status} {endpoint} - {description}")

    if passed == total:
        print("\n🎉 All endpoints are working correctly!")
        return 0
    else:
        print("\n⚠️  Some endpoints are not working properly.")
        return 1

if __name__ == "__main__":
    exit(main())
