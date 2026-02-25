"""Quick Proxmox validation for Phase 3.

Compares current Proxmox generator output against existing baseline.
"""

import subprocess
import sys
from pathlib import Path


def main():
    """Quick validation entry point."""
    repo_root = Path(__file__).parent
    topology_path = repo_root / "topology.yaml"
    
    if not topology_path.exists():
        print(f"ERROR: Topology file not found: {topology_path}")
        return 1
    
    print("="*70)
    print("Phase 3 Proxmox Generator Quick Validation")
    print("="*70)
    print(f"Topology: {topology_path}")
    
    # Baseline and test paths
    baseline_dir = repo_root / "generated" / "terraform"
    test_dir = repo_root / "generated" / "validation" / "proxmox"
    
    # Check baseline
    baseline_files = sorted(baseline_dir.glob("*.tf"))
    if not baseline_files:
        print(f"\nERROR: No baseline .tf files found in {baseline_dir}")
        print("       Generate baseline first:")
        print("       python -m topology-tools.scripts.generators.terraform.proxmox.cli \\")
        print(f"         --topology {topology_path} \\")
        print(f"         --output {baseline_dir}")
        return 1
    
    print(f"\nBaseline: {baseline_dir} ({len(baseline_files)} files)")
    
    # Generate test output
    print(f"Test output: {test_dir}")
    print("\nGenerating test output with refactored generator...")
    
    cmd = [
        sys.executable,
        "-m",
        "topology-tools.scripts.generators.terraform.proxmox.cli",
        "--topology",
        str(topology_path),
        "--output",
        str(test_dir),
    ]
    
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=False)
        if result.returncode != 0:
            print(f"ERROR: Generator failed with code {result.returncode}")
            print(result.stdout)
            print(result.stderr)
            return 1
        print("✅ Generator completed successfully")
    except Exception as e:
        print(f"ERROR: Failed to run generator: {e}")
        return 1
    
    # Compare files
    print(f"\nComparing {len(baseline_files)} Terraform files...")
    all_match = True
    
    for baseline_file in baseline_files:
        test_file = test_dir / baseline_file.name
        
        if not test_file.exists():
            print(f"  ❌ {baseline_file.name} - MISSING in test output")
            all_match = False
            continue
        
        baseline_content = baseline_file.read_text(encoding="utf-8")
        test_content = test_file.read_text(encoding="utf-8")
        
        if baseline_content == test_content:
            print(f"  ✅ {baseline_file.name} - IDENTICAL")
        else:
            print(f"  ❌ {baseline_file.name} - DIFFERS")
            all_match = False
            
            # Show brief diff
            baseline_lines = baseline_content.splitlines()
            test_lines = test_content.splitlines()
            
            if len(baseline_lines) != len(test_lines):
                print(f"     Line count: baseline={len(baseline_lines)}, test={len(test_lines)}")
            
            # Find first difference
            for i, (bl, tl) in enumerate(zip(baseline_lines, test_lines)):
                if bl != tl:
                    print(f"     First diff at line {i+1}:")
                    print(f"       Baseline: {bl[:80]}")
                    print(f"       Test:     {tl[:80]}")
                    break
    
    # Summary
    print("\n" + "="*70)
    if all_match:
        print("✅ VALIDATION PASSED")
        print("   All files identical - Phase 3 is backward-compatible!")
        print("\nNext steps:")
        print("  1. Review output above")
        print("  2. Commit Phase 3: git commit -F COMMIT_MESSAGE_PHASE3.md")
        return 0
    else:
        print("❌ VALIDATION FAILED")
        print("   Some files differ - review diffs above")
        print("\nTroubleshooting:")
        print("  1. Check terraform/base.py and terraform/resolvers.py")
        print("  2. Check proxmox/generator.py refactor")
        print("  3. Run unit tests: pytest tests/unit/generators/")
        print("  4. Review TERRAFORM_VALIDATION.md for details")
        return 1


if __name__ == "__main__":
    sys.exit(main())
