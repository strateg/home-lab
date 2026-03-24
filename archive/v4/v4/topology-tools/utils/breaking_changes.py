#!/usr/bin/env python3
"""
Breaking Changes Detector - Detect breaking changes in tool versions

Usage:
    python breaking_changes.py --tool terraform --from 1.5.0 --to 1.6.0
    python breaking_changes.py --all
"""

import sys
from pathlib import Path
from typing import Dict, List, Optional

try:
    import yaml
except ImportError:
    print("[ERROR] PyYAML not installed. Run: pip install pyyaml")
    sys.exit(1)


class BreakingChangesDetector:
    """Detect breaking changes between tool versions"""

    def __init__(self, db_path: str = "topology-tools/data/breaking-changes.yaml"):
        """Load breaking changes database"""
        self.db_path = Path(db_path)

        if not self.db_path.exists():
            print(f"[ERROR] Breaking changes DB not found: {db_path}")
            sys.exit(1)

        with open(self.db_path) as f:
            self.db = yaml.safe_load(f)

    def detect(self, tool: str, from_version: str, to_version: str) -> Dict:
        """
        Detect breaking changes between versions

        Returns: {
            'has_breaking_changes': bool,
            'breaking_changes': [list of breaking changes],
            'migration_strategy': migration steps,
            'risk': 'LOW' | 'MEDIUM' | 'HIGH'
        }
        """
        result = {
            "tool": tool,
            "from_version": from_version,
            "to_version": to_version,
            "has_breaking_changes": False,
            "breaking_changes": [],
            "severity": "NONE",
            "migration_strategy": None,
            "risk": "LOW",
        }

        # Find tool in database
        if tool not in self.db["breaking_changes"]:
            return result

        tool_changes = self.db["breaking_changes"][tool]

        # Find breaking changes that affect this version path
        for version, change_info in tool_changes.items():
            # Check if this version is in the upgrade path
            if self._is_in_upgrade_path(from_version, version):
                if change_info.get("breaking", False):
                    result["has_breaking_changes"] = True
                    result["breaking_changes"].append(
                        {
                            "version": version,
                            "severity": change_info.get("severity", "UNKNOWN"),
                            "changes": change_info.get("changes", []),
                        }
                    )

                    # Update overall severity (highest wins)
                    if self._severity_level(change_info.get("severity")) > self._severity_level(result["severity"]):
                        result["severity"] = change_info.get("severity")

        # Find migration strategy if available
        migration_key = (
            f"{tool.replace('-provider-', '')}-{from_version.replace('.', '-')}-to-{to_version.replace('.', '-')}"
        )
        if migration_key in self.db.get("migration_strategies", {}):
            result["migration_strategy"] = self.db["migration_strategies"][migration_key]
            result["risk"] = result["migration_strategy"].get("risk", "MEDIUM")

        return result

    def detect_all(self, from_l0: str, to_l0: str) -> List[Dict]:
        """
        Detect breaking changes when upgrading all tools

        Args:
            from_l0: Path to old L0 config
            to_l0: Path to new L0 config

        Returns: List of breaking changes detected
        """
        results = []

        # Load both L0 configs
        with open(from_l0) as f:
            old_tools = yaml.safe_load(f).get("tools", {})

        with open(to_l0) as f:
            new_tools = yaml.safe_load(f).get("tools", {})

        # Check each tool
        for category, tools in old_tools.items():
            if isinstance(tools, dict):
                for tool_name, version_info in tools.items():
                    if isinstance(version_info, dict) and "core" in version_info:
                        old_version = version_info["core"]
                        new_version = new_tools.get(category, {}).get(tool_name, {}).get("core")

                        if new_version and old_version != new_version:
                            result = self.detect(
                                f"{category}-{tool_name}".rstrip("-"),
                                self._normalize_version(old_version),
                                self._normalize_version(new_version),
                            )

                            if result["has_breaking_changes"]:
                                results.append(result)

        return results

    def print_report(self, result: Dict):
        """Print breaking changes report"""
        print("=" * 70)
        print(f"BREAKING CHANGES: {result['tool']} {result['from_version']} → {result['to_version']}")
        print("=" * 70)

        if not result["has_breaking_changes"]:
            print("✓ No breaking changes detected")
            return

        print(f"\n✗ BREAKING CHANGES DETECTED ({len(result['breaking_changes'])})")
        print(f"Severity: {result['severity']}")
        print(f"Risk: {result['risk']}")

        for change in result["breaking_changes"]:
            print(f"\n[{change['severity']}] In version {change['version']}:")
            for change_item in change["changes"]:
                if isinstance(change_item, dict):
                    if "resource_renamed" in change_item:
                        rc = change_item["resource_renamed"]
                        print(f"  - Resource renamed: {rc['old']} → {rc['new']}")
                    elif "field_renamed" in change_item:
                        fc = change_item["field_renamed"]
                        print(f"  - Field renamed: {fc['resource']}.{fc['old']} → {fc['new']}")
                    elif "field_removed" in change_item:
                        fr = change_item["field_removed"]
                        print(f"  - Field removed: {fr['resource']}.{fr['field']}")
                    elif "module_renamed" in change_item:
                        mr = change_item["module_renamed"]
                        print(f"  - Module renamed: {mr['old']} → {mr['new']}")
                    else:
                        print(f"  - {change_item}")
                else:
                    print(f"  - {change_item}")

        if result["migration_strategy"]:
            print(f"\n[MIGRATION STRATEGY]")
            ms = result["migration_strategy"]
            print(f"Description: {ms.get('description', 'N/A')}")

            if "changes" in ms:
                print(f"\nChanges to make:")
                for change in ms["changes"]:
                    print(
                        f"  - {change.get('target', 'N/A')}: {change.get('find', 'N/A')} → {change.get('replace', 'N/A')}"
                    )

            if "validation" in ms:
                print(f"\nValidation steps:")
                for step in ms["validation"]:
                    print(f"  - {step}")

            print(f"\nRisk: {ms.get('risk', 'UNKNOWN')}")

    # Helper methods

    def _is_in_upgrade_path(self, from_version: str, to_check_version: str) -> bool:
        """Check if to_check_version is in upgrade path from from_version"""
        from_major = int(from_version.split(".")[0])
        check_major = int(to_check_version.split(".")[0])

        # If same major version, it's in the path
        if from_major == check_major:
            return True

        # If check is higher major version, could be in path
        if check_major > from_major:
            return True

        return False

    def _severity_level(self, severity: str) -> int:
        """Convert severity string to numeric level"""
        levels = {"NONE": 0, "MINOR": 1, "MAJOR": 2, "CRITICAL": 3}
        return levels.get(severity, 0)

    def _normalize_version(self, version_spec: str) -> str:
        """Normalize version spec to plain version"""
        # Remove ~> prefix
        if version_spec.startswith("~> "):
            return version_spec[3:]
        elif version_spec.startswith(">= "):
            return version_spec[3:]
        return version_spec


def main():
    """CLI interface"""
    import argparse

    parser = argparse.ArgumentParser(description="Detect breaking changes in tool versions")
    parser.add_argument("--tool", help="Tool name (e.g., terraform, terraform-provider-proxmox)")
    parser.add_argument("--from", dest="from_version", help="Source version")
    parser.add_argument("--to", dest="to_version", help="Target version")
    parser.add_argument("--all", action="store_true", help="Check all tools between two L0 configs")
    parser.add_argument("--from-l0", default="topology/L0-meta/_index.yaml", help="Old L0 config path")
    parser.add_argument("--to-l0", default="topology/L0-meta/_index.yaml.new", help="New L0 config path")
    parser.add_argument(
        "--db", default="topology-tools/data/breaking-changes.yaml", help="Breaking changes database path"
    )

    args = parser.parse_args()

    # Create detector
    detector = BreakingChangesDetector(args.db)

    if args.all:
        # Check all tools between L0 configs
        print("[*] Checking all tools for breaking changes...")
        results = detector.detect_all(args.from_l0, args.to_l0)

        if not results:
            print("✓ No breaking changes detected between L0 configs")
        else:
            for result in results:
                detector.print_report(result)

    elif args.tool and args.from_version and args.to_version:
        # Check specific tool
        result = detector.detect(args.tool, args.from_version, args.to_version)
        detector.print_report(result)

    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
