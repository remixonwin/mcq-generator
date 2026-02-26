#!/usr/bin/env python3
"""
Multi-port testing script for MCQ Generator instances
Tests all instances running on ports 7560+
"""

import requests
import json
import time
import concurrent.futures
from typing import List, Dict, Tuple

def test_instance(port: int) -> Tuple[int, Dict[str, bool]]:
    """Test a single instance on a specific port."""
    base_url = f"http://localhost:{port}"
    results = {
        "health": False,
        "docs": False,
        "openapi": False,
        "jobs": False,
        "datasets": False
    }
    
    endpoints = {
        "health": "/health",
        "docs": "/docs",
        "openapi": "/openapi.json",
        "jobs": "/api/v1/jobs",
        "datasets": "/api/v1/datasets/search?q=test"
    }
    
    for endpoint_name, endpoint_path in endpoints.items():
        try:
            response = requests.get(f"{base_url}{endpoint_path}", timeout=5)
            results[endpoint_name] = response.status_code == 200
        except:
            results[endpoint_name] = False
    
    return port, results

def test_all_instances(base_port: int = 7560, max_instances: int = 10) -> Dict[int, Dict[str, bool]]:
    """Test all instances concurrently."""
    ports = [base_port + i for i in range(max_instances)]
    
    all_results = {}
    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
        future_to_port = {executor.submit(test_instance, port): port for port in ports}
        
        for future in concurrent.futures.as_completed(future_to_port):
            port, results = future.result()
            all_results[port] = results
    
    return all_results

def print_results(results: Dict[int, Dict[str, bool]], base_port: int = 7560):
    """Print test results in a formatted table."""
    print(f"\n{'='*80}")
    print(f"MCQ Generator Multi-Port Test Results")
    print(f"{'='*80}")
    
    # Header
    print(f"{'Port':<6} {'Instance':<10} {'Health':<7} {'Docs':<7} {'API':<7} {'Jobs':<7} {'Data':<7} {'Status':<10}")
    print(f"{'-'*80}")
    
    total_running = 0
    total_healthy = 0
    
    for i in range(len(results)):
        port = base_port + i
        instance_results = results.get(port, {})
        
        instance_id = i + 1
        health = "✅" if instance_results.get("health", False) else "❌"
        docs = "✅" if instance_results.get("docs", False) else "❌"
        api = "✅" if instance_results.get("openapi", False) else "❌"
        jobs = "✅" if instance_results.get("jobs", False) else "❌"
        data = "✅" if instance_results.get("datasets", False) else "❌"
        
        # Determine overall status
        if instance_results.get("health", False):
            status = "🟢 RUNNING"
            total_running += 1
            if all(instance_results.values()):
                status = "🟢 HEALTHY"
                total_healthy += 1
        else:
            status = "🔴 STOPPED"
        
        print(f"{port:<6} {instance_id:<10} {health:<7} {docs:<7} {api:<7} {jobs:<7} {data:<7} {status:<10}")
    
    print(f"{'-'*80}")
    print(f"Summary: {total_running}/{len(results)} instances running, {total_healthy}/{len(results)} fully healthy")
    
    # Show accessible endpoints
    print(f"\nAccessible API Endpoints:")
    for i in range(len(results)):
        port = base_port + i
        if results.get(port, {}).get("health", False):
            print(f"  • Instance {i+1}: http://localhost:{port}/docs")

def main():
    """Run multi-port tests."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Test MCQ Generator instances on multiple ports")
    parser.add_argument("--base-port", type=int, default=7560, help="Base port number (default: 7560)")
    parser.add_argument("--max-instances", type=int, default=10, help="Maximum instances to test (default: 10)")
    parser.add_argument("--watch", action="store_true", help="Watch mode - continuously test")
    parser.add_argument("--interval", type=int, default=5, help="Watch interval in seconds (default: 5)")
    
    args = parser.parse_args()
    
    if args.watch:
        print(f"🔍 Watching MCQ Generator instances (ports {args.base_port}-{args.base_port + args.max_instances - 1})")
        print(f"   Testing every {args.interval} seconds. Press Ctrl+C to stop.")
        
        try:
            while True:
                results = test_all_instances(args.base_port, args.max_instances)
                print("\033[2J\033[H", end="")  # Clear screen
                print_results(results, args.base_port)
                time.sleep(args.interval)
        except KeyboardInterrupt:
            print(f"\n👋 Stopped watching")
    else:
        print(f"🧪 Testing MCQ Generator instances (ports {args.base_port}-{args.base_port + args.max_instances - 1})")
        results = test_all_instances(args.base_port, args.max_instances)
        print_results(results, args.base_port)

if __name__ == "__main__":
    main()
