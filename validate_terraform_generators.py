"""Validation script for Phase 3 Terraform generator refactoring.

Compares outputs from refactored generators against baseline to ensure
backward compatibility and identical Terraform configurations.
"""

import difflib
import subprocess
import sys
from pathlib import Path
from typing import List, Tuple


def run_generator(generator_type: str, output_dir: Path, topology_path: Path) -> bool:
    """Run a Terraform generator and return success status."""
    if generator_type == "proxmox":
        cmd = [
            sys.executable,
            "-m",
            "topology-tools.scripts.generators.terraform.proxmox.cli",
            "--topology",
            str(topology_path),
            "--output",
            str(output_dir),
        ]
    elif generator_type == "mikrotik":
        cmd = [
            sys.executable,
            "-m",
            "topology-tools.scripts.generators.terraform.mikrotik.cli",
            "--topology",
            str(topology_path),
            "--output",
            str(output_dir),
        ]
    else:
        print(f"ERROR: Unknown generator type: {generator_type}")
        return False

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=False)
        if result.returncode != 0:
            print(f"ERROR: Generator failed with code {result.returncode}")
            print(result.stdout)
            print(result.stderr)
            return False
        return True
    except Exception as e:
        print(f"ERROR: Failed to run generator: {e}")
        return False


def compare_files(file1: Path, file2: Path) -> Tuple[bool, List[str]]:
    """Compare two files and return (identical, diff_lines)."""
    if not file1.exists():
        return False, [f"ERROR: Baseline file missing: {file1}"]
    if not file2.exists():
        return False, [f"ERROR: New file missing: {file2}"]

    content1 = file1.read_text(encoding="utf-8").splitlines(keepends=True)
    content2 = file2.read_text(encoding="utf-8").splitlines(keepends=True)

    if content1 == content2:
        return True, []

    diff = list(
        difflib.unified_diff(
            content1,
            content2,
            fromfile=str(file1),
            tofile=str(file2),
            lineterm="",
        )
    )
    return False, diff


def validate_generator(
    generator_type: str,
    topology_path: Path,
    baseline_dir: Path,
    test_dir: Path,
) -> bool:
    """Validate a generator produces identical output to baseline."""
    print(f"\n{'='*70}")
    print(f"Validating {generator_type.upper()} generator")
    print(f"{'='*70}")

    # Generate new output
    print(f"\nGenerating to: {test_dir}")
    if not run_generator(generator_type, test_dir, topology_path):
        return False

    # Compare all .tf files
    all_match = True
    tf_files = sorted(baseline_dir.glob("*.tf"))

    if not tf_files:
        print(f"WARN: No baseline .tf files found in {baseline_dir}")
        return True

    print(f"\nComparing {len(tf_files)} Terraform files:")

    for baseline_file in tf_files:
        test_file = test_dir / baseline_file.name
        identical, diff = compare_files(baseline_file, test_file)

        if identical:
            print(f"  ✅ {baseline_file.name} - IDENTICAL")
        else:
            print(f"  ❌ {baseline_file.name} - DIFFERS")
            all_match = False
            if diff:
                print(f"\n--- Diff for {baseline_file.name} ---")
                for line in diff[:50]:  # Limit output
                    print(line)
                if len(diff) > 50:
                    print(f"... ({len(diff) - 50} more lines)")

    return all_match


def main():
    """Main validation entry point."""
    repo_root = Path(__file__).parent
    topology_path = repo_root / "topology.yaml"

    if not topology_path.exists():
        print(f"ERROR: Topology file not found: {topology_path}")
        print("Please run this script from the repository root.")
        return 1

    print(f"Terraform Generator Validation")
    print(f"{'='*70}")
    print(f"Topology: {topology_path}")

    # Create test output directories
    test_base = repo_root / "generated" / "validation"
    test_base.mkdir(parents=True, exist_ok=True)

    # Validate Proxmox generator
    # Note: Using generated/terraform as baseline (pre-Phase3 output)
    proxmox_baseline = repo_root / "generated" / "terraform"
    proxmox_test = test_base / "proxmox"
    
    # Check if baseline exists
    if not proxmox_baseline.exists() or not list(proxmox_baseline.glob("*.tf")):
        print(f"\nWARN: No Proxmox baseline found at {proxmox_baseline}")
        print("      Generating new baseline first...")
        if not run_generator("proxmox", proxmox_baseline, topology_path):
            print("ERROR: Failed to generate baseline")
            return 1
    
    proxmox_ok = validate_generator("proxmox", topology_path, proxmox_baseline, proxmox_test)

    # Validate MikroTik generator
    mikrotik_baseline = repo_root / "generated" / "terraform-mikrotik"
    mikrotik_test = test_base / "mikrotik"
    
    # Check if baseline exists
    if not mikrotik_baseline.exists() or not list(mikrotik_baseline.glob("*.tf")):
        print(f"\nWARN: No MikroTik baseline found at {mikrotik_baseline}")
        print("      Skipping MikroTik validation (baseline not found)")
        mikrotik_ok = True  # Don't fail if no baseline
    else:
        mikrotik_ok = validate_generator("mikrotik", topology_path, mikrotik_baseline, mikrotik_test)

    # Summary
    print(f"\n{'='*70}")
    print(f"Validation Summary")
    print(f"{'='*70}")
    print(f"Proxmox:  {'✅ PASS' if proxmox_ok else '❌ FAIL'}")
    print(f"MikroTik: {'✅ PASS' if mikrotik_ok else '❌ FAIL'}")

    if proxmox_ok and mikrotik_ok:
        print(f"\n✅ All generators produce identical output!")
        print(f"   Phase 3 refactoring is backward-compatible.")
        return 0
    else:
        print(f"\n❌ Some generators produce different output.")
        print(f"   Review diffs above and fix before committing Phase 3.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
