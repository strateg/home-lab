#!/usr/bin/env python3
"""
MikroTik Bootstrap Deployer

Deploy bootstrap script to MikroTik router via SSH.

Usage:
    python deploy-mikrotik-bootstrap.py [--router IP] [--user USER] [--password PASS]
"""

import argparse
import shutil
import subprocess
import sys
import time
from pathlib import Path
from typing import Optional

# Add topology-tools to path
SCRIPT_DIR = Path(__file__).resolve().parent
TOPOLOGY_TOOLS_DIR = SCRIPT_DIR.parent.parent
PROJECT_ROOT = TOPOLOGY_TOOLS_DIR.parent
sys.path.insert(0, str(TOPOLOGY_TOOLS_DIR))


class MikrotikBootstrapDeployer:
    """Deploy bootstrap script to MikroTik via SSH."""

    def __init__(
        self,
        router_ip: str = "192.168.88.1",
        ssh_user: str = "admin",
        ssh_password: str = "",
        ssh_port: int = 22,
        bootstrap_script: Optional[Path] = None,
    ):
        self.router_ip = router_ip
        self.ssh_user = ssh_user
        self.ssh_password = ssh_password
        self.ssh_port = ssh_port
        self.bootstrap_script = bootstrap_script or (
            PROJECT_ROOT / "generated" / "bootstrap" / "rtr-mikrotik-chateau" / "init-terraform.rsc"
        )

    def check_connectivity(self) -> bool:
        """Check if router is reachable."""
        print(f"Checking connectivity to {self.router_ip}...")
        result = subprocess.run(
            ["ping", "-c", "1", "-W", "2", self.router_ip],
            capture_output=True,
        )
        if result.returncode == 0:
            print(f"OK Router {self.router_ip} is reachable")
            return True
        else:
            print(f"ERROR Router {self.router_ip} is not reachable")
            return False

    def check_ssh(self) -> bool:
        """Check if SSH is available."""
        print(f"Checking SSH on {self.router_ip}:{self.ssh_port}...")

        # Use nc (netcat) to check port
        nc_path = shutil.which("nc") or shutil.which("netcat")
        if nc_path:
            result = subprocess.run(
                [nc_path, "-z", "-w", "2", self.router_ip, str(self.ssh_port)],
                capture_output=True,
            )
            if result.returncode == 0:
                print(f"OK SSH port {self.ssh_port} is open")
                return True

        # Fallback: try ssh command
        print("WARN netcat not found, trying SSH directly...")
        return True  # Assume it works

    def deploy_via_ssh(self) -> bool:
        """Deploy bootstrap script via SSH."""
        if not self.bootstrap_script.exists():
            print(f"ERROR Bootstrap script not found: {self.bootstrap_script}")
            return False

        print(f"Deploying {self.bootstrap_script} to {self.router_ip}...")

        # Read script content
        script_content = self.bootstrap_script.read_text()

        # Build SSH command
        ssh_cmd = self._build_ssh_command()

        try:
            # Execute script via SSH
            result = subprocess.run(
                ssh_cmd,
                input=script_content,
                capture_output=True,
                text=True,
                timeout=60,
            )

            if result.returncode == 0:
                print("OK Bootstrap script executed successfully")
                print()
                print("--- Router Output ---")
                print(result.stdout)
                if result.stderr:
                    print("--- Warnings ---")
                    print(result.stderr)
                return True
            else:
                print(f"ERROR SSH command failed with code {result.returncode}")
                print(result.stderr)
                return False

        except subprocess.TimeoutExpired:
            print("ERROR SSH command timed out")
            return False
        except Exception as e:
            print(f"ERROR SSH failed: {e}")
            return False

    def _build_ssh_command(self) -> list:
        """Build SSH command with options."""
        cmd = [
            "ssh",
            "-o",
            "StrictHostKeyChecking=no",
            "-o",
            "UserKnownHostsFile=/dev/null",
            "-o",
            "ConnectTimeout=10",
            "-p",
            str(self.ssh_port),
        ]

        # Add password via sshpass if available and password provided
        if self.ssh_password:
            sshpass = shutil.which("sshpass")
            if sshpass:
                cmd = [sshpass, "-p", self.ssh_password] + cmd
            else:
                print("WARN sshpass not installed, SSH will prompt for password")

        cmd.append(f"{self.ssh_user}@{self.router_ip}")

        return cmd

    def verify_api(self, api_port: int = 8443, max_retries: int = 3) -> bool:
        """Verify REST API is accessible after bootstrap."""
        print(f"Verifying REST API on https://{self.router_ip}:{api_port}...")

        curl_path = shutil.which("curl")
        if not curl_path:
            print("WARN curl not found, skipping API verification")
            return True

        for attempt in range(max_retries):
            result = subprocess.run(
                [
                    curl_path,
                    "-k",  # Allow self-signed cert
                    "-s",  # Silent
                    "-o",
                    "/dev/null",
                    "-w",
                    "%{http_code}",
                    "--connect-timeout",
                    "5",
                    f"https://{self.router_ip}:{api_port}/rest/system/identity",
                ],
                capture_output=True,
                text=True,
            )

            if result.stdout.strip() in ("200", "401"):  # 401 = auth required = API working
                print("OK REST API is accessible")
                return True

            print(f"WAIT API not ready (attempt {attempt + 1}/{max_retries})...")
            time.sleep(2)

        print("ERROR REST API verification failed")
        return False

    def deploy(self) -> bool:
        """Full deployment workflow."""
        print("=" * 70)
        print("MikroTik Bootstrap Deployer")
        print("=" * 70)
        print()

        # Step 1: Check connectivity
        if not self.check_connectivity():
            print()
            print("ERROR Cannot reach router. Check:")
            print("  - Router is powered on")
            print("  - You are connected to the same network")
            print("  - IP address is correct")
            return False

        # Step 2: Check SSH
        if not self.check_ssh():
            print()
            print("ERROR SSH not available. After soft reset, SSH should be enabled.")
            return False

        # Step 3: Deploy script
        print()
        if not self.deploy_via_ssh():
            return False

        # Step 4: Verify API
        print()
        time.sleep(2)  # Wait for services to restart
        if not self.verify_api():
            print("WARN API verification failed, but bootstrap may have succeeded")

        print()
        print("=" * 70)
        print("Bootstrap Complete!")
        print("=" * 70)
        print()
        print(f"REST API: https://{self.router_ip}:8443")
        print()
        print("Next steps:")
        print("  1. Copy terraform.tfvars to local/terraform/mikrotik/terraform.tfvars")
        print("  2. Run: cd deploy && make assemble-native")
        print("  3. Run: cd .work/native/terraform/mikrotik && terraform apply")
        print()

        return True


def main():
    parser = argparse.ArgumentParser(description="Deploy MikroTik bootstrap script via SSH")
    parser.add_argument(
        "--router",
        default="192.168.88.1",
        help="Router IP address (default: 192.168.88.1)",
    )
    parser.add_argument(
        "--user",
        default="admin",
        help="SSH username (default: admin)",
    )
    parser.add_argument(
        "--password",
        default="",
        help="SSH password (default: empty for fresh router)",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=22,
        help="SSH port (default: 22)",
    )
    parser.add_argument(
        "--script",
        default=None,
        help="Path to bootstrap script (default: generated/bootstrap/rtr-mikrotik-chateau/init-terraform.rsc)",
    )
    parser.add_argument(
        "--generate",
        action="store_true",
        help="Generate bootstrap script before deploying",
    )
    parser.add_argument(
        "--topology",
        default="topology.yaml",
        help="Topology file for generation (default: topology.yaml)",
    )

    args = parser.parse_args()

    # Generate if requested
    if args.generate:
        print("Generating bootstrap script from topology...")
        from topology_loader import load_topology

        from scripts.generators.bootstrap.mikrotik.generator import MikrotikBootstrapGenerator

        topology = load_topology(args.topology)
        generator = MikrotikBootstrapGenerator(topology)
        result = generator.generate()
        print(f"OK Generated: {result['bootstrap_script']}")
        print()
        script_path = Path(result["bootstrap_script"])
    else:
        script_path = Path(args.script) if args.script else None

    # Deploy
    deployer = MikrotikBootstrapDeployer(
        router_ip=args.router,
        ssh_user=args.user,
        ssh_password=args.password,
        ssh_port=args.port,
        bootstrap_script=script_path,
    )

    success = deployer.deploy()
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
