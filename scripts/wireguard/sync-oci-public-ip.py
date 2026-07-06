#!/usr/bin/env python3
"""Sync OCI VPS public IP to WireGuard tunnel secrets.

Fetches the current public IP from OCI CLI and updates the tunnel secrets file.
Run before compiling topology to ensure WireGuard configs have correct endpoint.

Usage:
    python scripts/wireguard/sync-oci-public-ip.py
    python scripts/wireguard/sync-oci-public-ip.py --dry-run

Requirements:
    - OCI CLI configured (`oci setup config`)
    - SOPS for secrets encryption
    - yq for YAML manipulation
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path


def run_cmd(cmd: list[str], check: bool = True) -> str:
    """Run command and return stdout."""
    result = subprocess.run(cmd, capture_output=True, text=True, check=check)
    return result.stdout.strip()


def get_oci_instance_public_ip(instance_id: str, compartment_id: str) -> str | None:
    """Fetch public IP for OCI instance via VNIC attachments."""
    # Get VNIC attachments for the instance
    vnic_cmd = [
        "oci",
        "compute",
        "vnic-attachment",
        "list",
        "--compartment-id",
        compartment_id,
        "--instance-id",
        instance_id,
        "--output",
        "json",
    ]

    try:
        output = run_cmd(vnic_cmd)
        attachments = json.loads(output).get("data", [])
    except (subprocess.CalledProcessError, json.JSONDecodeError) as e:
        print(f"Error fetching VNIC attachments: {e}", file=sys.stderr)
        return None

    if not attachments:
        print("No VNIC attachments found", file=sys.stderr)
        return None

    # Get the primary VNIC
    vnic_id = attachments[0].get("vnic-id")
    if not vnic_id:
        print("No VNIC ID found in attachment", file=sys.stderr)
        return None

    # Get VNIC details to find public IP
    vnic_cmd = ["oci", "network", "vnic", "get", "--vnic-id", vnic_id, "--output", "json"]

    try:
        output = run_cmd(vnic_cmd)
        vnic_data = json.loads(output).get("data", {})
        public_ip = vnic_data.get("public-ip")
        return public_ip
    except (subprocess.CalledProcessError, json.JSONDecodeError) as e:
        print(f"Error fetching VNIC details: {e}", file=sys.stderr)
        return None


def decrypt_sops_file(path: Path) -> str:
    """Decrypt SOPS file and return content."""
    return run_cmd(["sops", "-d", str(path)])


def encrypt_sops_file(path: Path, content: str) -> None:
    """Encrypt content and write to SOPS file."""
    # Write to temp file, then encrypt in place
    temp_path = path.with_suffix(".yaml.tmp")
    temp_path.write_text(content)
    run_cmd(["sops", "-e", "-i", str(temp_path)])
    temp_path.rename(path)


def update_tunnel_secrets(secrets_path: Path, public_ip: str, dry_run: bool = False) -> bool:
    """Update tunnel secrets with public IP."""
    import yaml

    # Decrypt existing secrets
    try:
        content = decrypt_sops_file(secrets_path)
        secrets = yaml.safe_load(content)
    except Exception as e:
        print(f"Error reading secrets: {e}", file=sys.stderr)
        return False

    # Check if public_ip already exists and matches
    current_ip = secrets.get("vps", {}).get("public_ip")
    if current_ip == public_ip:
        print(f"Public IP already up to date: {public_ip}")
        return True

    # Update or add public_ip
    if "vps" not in secrets:
        secrets["vps"] = {}

    old_ip = secrets["vps"].get("public_ip", "not set")
    secrets["vps"]["public_ip"] = public_ip

    print(f"Updating public_ip: {old_ip} → {public_ip}")

    if dry_run:
        print("Dry run - no changes written")
        return True

    # Write updated secrets
    try:
        # Format YAML with comments preserved (simplified)
        content = decrypt_sops_file(secrets_path)

        # Simple approach: add public_ip line after vps: section
        lines = content.split("\n")
        updated_lines = []
        in_vps_section = False
        ip_updated = False

        for line in lines:
            if line.strip().startswith("vps:"):
                in_vps_section = True
                updated_lines.append(line)
            elif in_vps_section and line.strip().startswith("public_ip:"):
                updated_lines.append(f"    public_ip: {public_ip}")
                ip_updated = True
            elif in_vps_section and not line.startswith(" ") and not line.startswith("\t") and line.strip():
                # End of vps section
                if not ip_updated:
                    updated_lines.append(f"    public_ip: {public_ip}")
                    ip_updated = True
                in_vps_section = False
                updated_lines.append(line)
            else:
                updated_lines.append(line)

        # If vps section was at end without public_ip
        if in_vps_section and not ip_updated:
            updated_lines.append(f"    public_ip: {public_ip}")

        new_content = "\n".join(updated_lines)
        encrypt_sops_file(secrets_path, new_content)
        print(f"Updated {secrets_path}")
        return True

    except Exception as e:
        print(f"Error writing secrets: {e}", file=sys.stderr)
        return False


def main() -> int:
    parser = argparse.ArgumentParser(description="Sync OCI public IP to tunnel secrets")
    parser.add_argument("--dry-run", action="store_true", help="Show changes without writing")
    parser.add_argument("--project", default="home-lab", help="Project ID")
    args = parser.parse_args()

    # Paths
    repo_root = Path(__file__).resolve().parents[2]
    project_root = repo_root / "projects" / args.project
    secrets_path = project_root / "secrets" / "tunnels" / "wg-home-to-oci.yaml"
    instance_secrets_path = project_root / "secrets" / "instances" / "vps-oracle-frankfurt.yaml"

    if not secrets_path.exists():
        print(f"Tunnel secrets not found: {secrets_path}", file=sys.stderr)
        return 1

    # Load OCI credentials from instance secrets
    try:
        instance_content = decrypt_sops_file(instance_secrets_path)
        import yaml

        instance_secrets = yaml.safe_load(instance_content)
    except Exception as e:
        print(f"Error reading instance secrets: {e}", file=sys.stderr)
        return 1

    compartment_id = instance_secrets.get("compartment_id")
    if not compartment_id:
        print("compartment_id not found in instance secrets", file=sys.stderr)
        return 1

    # Load instance_id from topology (handle @ markers)
    topology_path = project_root / "topology" / "instances" / "vm" / "cloud" / "vps-oracle-frankfurt.yaml"
    try:
        import yaml

        # Filter out lines starting with @ (topology markers)
        content = topology_path.read_text()
        filtered_lines = [line for line in content.split("\n") if not line.strip().startswith("@")]
        topology = yaml.safe_load("\n".join(filtered_lines))
        instance_id = topology.get("oci", {}).get("instance_id")
    except Exception as e:
        print(f"Error reading topology: {e}", file=sys.stderr)
        return 1

    if not instance_id:
        print("instance_id not found in topology", file=sys.stderr)
        return 1

    print(f"Fetching public IP for OCI instance: {instance_id[:30]}...")

    # Fetch public IP from OCI
    public_ip = get_oci_instance_public_ip(instance_id, compartment_id)

    if not public_ip:
        print("Failed to fetch public IP from OCI", file=sys.stderr)
        return 1

    print(f"OCI public IP: {public_ip}")

    # Update tunnel secrets
    if not update_tunnel_secrets(secrets_path, public_ip, args.dry_run):
        return 1

    if not args.dry_run:
        print("\nNext steps:")
        print("  1. Recompile topology: task compile:default")
        print("  2. Verify generated config: cat generated/home-lab/wireguard/mikrotik-wg0.rsc | grep endpoint")

    return 0


if __name__ == "__main__":
    sys.exit(main())
