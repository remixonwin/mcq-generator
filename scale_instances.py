#!/usr/bin/env python3
"""
Dynamic instance scaling script for MCQ Generator
Manages multiple API instances on ports 7560+
"""

import argparse
import subprocess
import sys
import time
import requests
from typing import List, Dict

class MCQScaler:
    def __init__(self, base_port: int = 7560, max_instances: int = 10):
        self.base_port = base_port
        self.max_instances = max_instances
        self.compose_file = "docker-compose.yml"
    
    def get_running_instances(self) -> Dict[int, bool]:
        """Check which instances are currently running."""
        instances = {}
        for i in range(1, self.max_instances + 1):
            port = self.base_port + i - 1
            try:
                response = requests.get(f"http://localhost:{port}/health", timeout=2)
                instances[port] = response.status_code == 200
            except:
                instances[port] = False
        return instances
    
    def scale_up(self, count: int = 1) -> bool:
        """Scale up by adding new instances."""
        running = self.get_running_instances()
        current_count = sum(running.values())
        
        if current_count >= self.max_instances:
            print(f"❌ Maximum instances ({self.max_instances}) already running")
            return False
        
        # Find next available ports
        available_ports = []
        for i in range(1, self.max_instances + 1):
            port = self.base_port + i - 1
            if not running.get(port, False):
                available_ports.append(port)
                if len(available_ports) >= count:
                    break
        
        if not available_ports:
            print("❌ No available ports for new instances")
            return False
        
        # Start new instances
        for port in available_ports:
            instance_id = port - self.base_port + 1
            print(f"🚀 Starting instance {instance_id} on port {port}")
            
            cmd = [
                "docker", "compose", "up", "-d", 
                f"mcq-generator-{instance_id}"
            ]
            
            try:
                subprocess.run(cmd, check=True, capture_output=True)
                print(f"✅ Instance {instance_id} started on port {port}")
            except subprocess.CalledProcessError as e:
                print(f"❌ Failed to start instance {instance_id}: {e}")
                return False
        
        return True
    
    def scale_down(self, count: int = 1) -> bool:
        """Scale down by removing instances."""
        running = self.get_running_instances()
        running_ports = [port for port, is_running in running.items() if is_running]
        
        if not running_ports:
            print("❌ No instances are currently running")
            return False
        
        # Remove highest port instances first
        ports_to_stop = sorted(running_ports, reverse=True)[:count]
        
        for port in ports_to_stop:
            instance_id = port - self.base_port + 1
            print(f"🛑 Stopping instance {instance_id} on port {port}")
            
            cmd = [
                "docker", "compose", "stop", 
                f"mcq-generator-{instance_id}"
            ]
            
            try:
                subprocess.run(cmd, check=True, capture_output=True)
                print(f"✅ Instance {instance_id} stopped on port {port}")
            except subprocess.CalledProcessError as e:
                print(f"❌ Failed to stop instance {instance_id}: {e}")
                return False
        
        return True
    
    def get_status(self) -> None:
        """Display current status of all instances."""
        running = self.get_running_instances()
        
        print(f"\n{'='*60}")
        print(f"MCQ Generator Instance Status")
        print(f"{'='*60}")
        
        total_running = sum(running.values())
        print(f"Total Running: {total_running}/{self.max_instances}")
        print()
        
        for i in range(1, self.max_instances + 1):
            port = self.base_port + i - 1
            status = "🟢 RUNNING" if running.get(port, False) else "🔴 STOPPED"
            print(f"Instance {i:2d} (Port {port}): {status}")
        
        print(f"\nAPI Endpoints:")
        for i in range(1, self.max_instances + 1):
            port = self.base_port + i - 1
            if running.get(port, False):
                print(f"  • http://localhost:{port}/docs")
    
    def health_check(self) -> None:
        """Perform health check on all running instances."""
        running = self.get_running_instances()
        
        print(f"\n{'='*60}")
        print(f"Health Check Results")
        print(f"{'='*60}")
        
        for i in range(1, self.max_instances + 1):
            port = self.base_port + i - 1
            if running.get(port, False):
                try:
                    response = requests.get(f"http://localhost:{port}/health", timeout=5)
                    if response.status_code == 200:
                        data = response.json()
                        status = data.get("status", "unknown")
                        print(f"Instance {i} (Port {port}): ✅ {status.upper()}")
                    else:
                        print(f"Instance {i} (Port {port}): ❌ HTTP {response.status_code}")
                except Exception as e:
                    print(f"Instance {i} (Port {port}): ❌ {e}")

def main():
    parser = argparse.ArgumentParser(description="MCQ Generator Instance Scaler")
    parser.add_argument("action", choices=["up", "down", "status", "health"], 
                       help="Action to perform")
    parser.add_argument("--count", type=int, default=1, 
                       help="Number of instances to scale up/down (default: 1)")
    parser.add_argument("--base-port", type=int, default=7560,
                       help="Base port number (default: 7560)")
    parser.add_argument("--max-instances", type=int, default=10,
                       help="Maximum number of instances (default: 10)")
    
    args = parser.parse_args()
    
    scaler = MCQScaler(base_port=args.base_port, max_instances=args.max_instances)
    
    if args.action == "up":
        success = scaler.scale_up(args.count)
        sys.exit(0 if success else 1)
    
    elif args.action == "down":
        success = scaler.scale_down(args.count)
        sys.exit(0 if success else 1)
    
    elif args.action == "status":
        scaler.get_status()
    
    elif args.action == "health":
        scaler.health_check()

if __name__ == "__main__":
    main()
