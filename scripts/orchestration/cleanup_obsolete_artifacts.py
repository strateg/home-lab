#!/usr/bin/env python3
"""
Cleanup obsolete artifacts identified by artifact plans.

Reads .state/artifact-plans/*.json files, identifies obsolete artifacts,
and prompts for confirmation before deletion.

Usage:
    python scripts/orchestration/cleanup_obsolete_artifacts.py [--dry-run] [--yes]

Options:
    --dry-run    Show what would be deleted without actually deleting
    --yes        Skip confirmation prompt (use with caution)
"""

import argparse
import json
import sys
from pathlib import Path
from typing import List, Dict, Any

# Project root
PROJECT_ROOT = Path(__file__).resolve().parents[2]
ARTIFACT_PLANS_DIR = PROJECT_ROOT / ".state" / "artifact-plans"


def load_artifact_plans() -> List[Dict[str, Any]]:
    """Load all artifact plan JSON files."""
    if not ARTIFACT_PLANS_DIR.exists():
        print(f"❌ Artifact plans directory not found: {ARTIFACT_PLANS_DIR}")
        sys.exit(1)

    plans = []
    for plan_file in ARTIFACT_PLANS_DIR.glob("*.json"):
        try:
            with open(plan_file, encoding="utf-8") as f:
                plan = json.load(f)
                plan["_source_file"] = plan_file.name
                plans.append(plan)
        except json.JSONDecodeError as e:
            print(f"⚠️  Failed to parse {plan_file.name}: {e}")
        except Exception as e:
            print(f"⚠️  Error reading {plan_file.name}: {e}")

    return plans


def collect_obsolete_artifacts(plans: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Collect obsolete artifacts from all plans."""
    obsolete = []

    for plan in plans:
        plugin_id = plan.get("plugin_id", "unknown")
        for candidate in plan.get("obsolete_candidates", []):
            if candidate.get("action") == "warn" and candidate.get("reason") == "obsolete-shadowed":
                obsolete.append({
                    "path": candidate["path"],
                    "plugin_id": plugin_id,
                    "ownership_proven": candidate.get("ownership_proven", False),
                    "source_plan": plan["_source_file"],
                })

    return obsolete


def display_obsolete_artifacts(artifacts: List[Dict[str, Any]]) -> None:
    """Display obsolete artifacts grouped by plugin."""
    if not artifacts:
        print("✅ No obsolete artifacts found.")
        return

    print(f"\n📋 Found {len(artifacts)} obsolete artifact(s):\n")

    # Group by plugin
    by_plugin: Dict[str, List[str]] = {}
    for artifact in artifacts:
        plugin_id = artifact["plugin_id"]
        if plugin_id not in by_plugin:
            by_plugin[plugin_id] = []
        by_plugin[plugin_id].append(artifact["path"])

    # Display grouped
    for plugin_id, paths in sorted(by_plugin.items()):
        print(f"  {plugin_id}:")
        for path in sorted(paths):
            exists_marker = "✓" if (PROJECT_ROOT / path).exists() else "✗"
            print(f"    [{exists_marker}] {path}")
        print()


def delete_artifacts(artifacts: List[Dict[str, Any]], dry_run: bool = False) -> None:
    """Delete obsolete artifacts."""
    deleted = 0
    not_found = 0
    errors = 0

    for artifact in artifacts:
        file_path = PROJECT_ROOT / artifact["path"]

        if dry_run:
            if file_path.exists():
                print(f"  [DRY-RUN] Would delete: {artifact['path']}")
                deleted += 1
            else:
                print(f"  [DRY-RUN] Would skip (not found): {artifact['path']}")
                not_found += 1
            continue

        # Actual deletion
        if not file_path.exists():
            not_found += 1
            continue

        try:
            file_path.unlink()
            print(f"  ✓ Deleted: {artifact['path']}")
            deleted += 1
        except Exception as e:
            print(f"  ✗ Failed to delete {artifact['path']}: {e}")
            errors += 1

    # Summary
    print(f"\n{'[DRY-RUN] ' if dry_run else ''}Summary:")
    print(f"  Deleted: {deleted}")
    if not_found > 0:
        print(f"  Not found: {not_found}")
    if errors > 0:
        print(f"  Errors: {errors}")


def confirm_deletion(artifacts: List[Dict[str, Any]]) -> bool:
    """Prompt user for confirmation."""
    existing_count = sum(1 for a in artifacts if (PROJECT_ROOT / a["path"]).exists())

    if existing_count == 0:
        print("ℹ️  No files exist on disk (already cleaned up).")
        return False

    print(f"\n⚠️  This will delete {existing_count} file(s) from disk.")
    response = input("Proceed with deletion? [y/N]: ").strip().lower()
    return response in ("y", "yes")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Cleanup obsolete artifacts identified by artifact plans"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be deleted without actually deleting",
    )
    parser.add_argument(
        "--yes",
        action="store_true",
        help="Skip confirmation prompt (use with caution)",
    )
    args = parser.parse_args()

    print("🔍 Loading artifact plans...")
    plans = load_artifact_plans()
    print(f"   Loaded {len(plans)} plan(s)")

    print("\n🔍 Collecting obsolete artifacts...")
    obsolete = collect_obsolete_artifacts(plans)

    # Display findings
    display_obsolete_artifacts(obsolete)

    if not obsolete:
        sys.exit(0)

    # Confirm or skip
    if args.dry_run:
        print("\n🧪 Dry-run mode enabled (no files will be deleted)")
        delete_artifacts(obsolete, dry_run=True)
    elif args.yes or confirm_deletion(obsolete):
        print("\n🗑️  Deleting obsolete artifacts...")
        delete_artifacts(obsolete, dry_run=False)
    else:
        print("\n❌ Deletion cancelled by user.")
        sys.exit(1)


if __name__ == "__main__":
    main()
