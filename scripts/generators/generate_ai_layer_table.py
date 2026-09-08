#!/usr/bin/env python3
"""Generate AI rule pack layer table from canonical layer-contract.yaml.

This script ensures single source of truth for layer semantics.
The generated table in docs/ai/rules/topology-model.md MUST match
the canonical layer-contract.yaml.

Usage:
    python scripts/generators/generate_ai_layer_table.py [--check] [--update]

Options:
    --check   Verify current table matches canonical source (exit 1 if mismatch)
    --update  Update topology-model.md with generated table
    (no args)  Print generated table to stdout
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

# Add repo root to path for imports
REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

try:
    import yaml
except ImportError:
    print("ERROR: PyYAML required. Install with: pip install pyyaml", file=sys.stderr)
    sys.exit(1)


LAYER_CONTRACT_PATH = REPO_ROOT / "topology" / "layer-contract.yaml"
AI_RULES_PATH = REPO_ROOT / "docs" / "ai" / "rules" / "topology-model.md"

# Canonical examples derived from layer-contract.yaml group_layers mapping
LAYER_EXAMPLES = {
    "L0": "Global defaults, version, policies",
    "L1": "Devices, routers, power, firmware, physical links",
    "L2": "Bridges, VLANs, firewall, QoS, tunnels",
    "L3": "Storage pools, volumes, data assets",
    "L4": "VMs, LXC, containers, workloads",
    "L5": "Services, applications, DNS, VPN",
    "L6": "Healthchecks, alerts, dashboards",
    "L7": "Backups, workflows, policies, schedules",
}

# Table markers in topology-model.md
TABLE_START_MARKER = "<!-- GENERATED:LAYER_TABLE:START -->"
TABLE_END_MARKER = "<!-- GENERATED:LAYER_TABLE:END -->"


def load_layer_contract() -> dict:
    """Load canonical layer-contract.yaml."""
    with LAYER_CONTRACT_PATH.open("r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def generate_layer_table(contract: dict) -> str:
    """Generate markdown table from layer contract."""
    layer_semantics = contract.get("layer_semantics", {})

    lines = [
        TABLE_START_MARKER,
        "",
        "| Layer | Scope | Examples |",
        "|-------|-------|----------|",
    ]

    for layer in ["L0", "L1", "L2", "L3", "L4", "L5", "L6", "L7"]:
        scope = layer_semantics.get(layer, "unknown")
        # Capitalize scope for display
        scope_display = scope.replace("_", " ").title()
        examples = LAYER_EXAMPLES.get(layer, "")
        lines.append(f"| {layer} | {scope_display} | {examples} |")

    lines.append("")
    lines.append(TABLE_END_MARKER)

    return "\n".join(lines)


def extract_current_table(content: str) -> str | None:
    """Extract current generated table from markdown content."""
    pattern = re.compile(
        rf"{re.escape(TABLE_START_MARKER)}.*?{re.escape(TABLE_END_MARKER)}",
        re.DOTALL,
    )
    match = pattern.search(content)
    return match.group(0) if match else None


def extract_legacy_table(content: str) -> tuple[int, int] | None:
    """Find legacy table boundaries (## Layer Boundaries section)."""
    lines = content.split("\n")
    start_idx = None
    end_idx = None

    for i, line in enumerate(lines):
        if line.strip() == "## Layer Boundaries (L0-L7)":
            start_idx = i
        elif start_idx is not None and line.startswith("## "):
            end_idx = i
            break
        elif start_idx is not None and line.startswith("| L7"):
            # Find end of table (next empty line or next section)
            for j in range(i + 1, len(lines)):
                if not lines[j].strip() or lines[j].startswith("##"):
                    end_idx = j
                    break
            else:
                end_idx = len(lines)
            break

    if start_idx is not None and end_idx is not None:
        return (start_idx, end_idx)
    return None


def update_ai_rules(generated_table: str) -> bool:
    """Update topology-model.md with generated table."""
    content = AI_RULES_PATH.read_text(encoding="utf-8")

    # Check if markers already exist
    if TABLE_START_MARKER in content:
        # Replace existing generated table
        pattern = re.compile(
            rf"{re.escape(TABLE_START_MARKER)}.*?{re.escape(TABLE_END_MARKER)}",
            re.DOTALL,
        )
        new_content = pattern.sub(generated_table, content)
    else:
        # Find and replace legacy table
        lines = content.split("\n")
        bounds = extract_legacy_table(content)

        if bounds is None:
            print("ERROR: Could not find layer table section in topology-model.md", file=sys.stderr)
            return False

        start_idx, end_idx = bounds

        # Build new content with section header + generated table
        new_lines = lines[:start_idx] + ["## Layer Boundaries (L0-L7)", "", generated_table, ""] + lines[end_idx:]
        new_content = "\n".join(new_lines)

    # Remove any double blank lines
    while "\n\n\n" in new_content:
        new_content = new_content.replace("\n\n\n", "\n\n")

    AI_RULES_PATH.write_text(new_content, encoding="utf-8")
    return True


def check_equivalence(generated_table: str) -> bool:
    """Check if current table matches generated table."""
    content = AI_RULES_PATH.read_text(encoding="utf-8")
    current = extract_current_table(content)

    if current is None:
        print("ERROR: No generated table markers found in topology-model.md", file=sys.stderr)
        print("Run with --update first to add markers.", file=sys.stderr)
        return False

    if current.strip() == generated_table.strip():
        print("OK: Layer table matches canonical source")
        return True
    else:
        print("MISMATCH: Layer table diverges from canonical source", file=sys.stderr)
        print("\n--- Expected (from layer-contract.yaml) ---", file=sys.stderr)
        print(generated_table, file=sys.stderr)
        print("\n--- Actual (in topology-model.md) ---", file=sys.stderr)
        print(current, file=sys.stderr)
        return False


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate AI rule pack layer table")
    parser.add_argument("--check", action="store_true", help="Verify table matches canonical source")
    parser.add_argument("--update", action="store_true", help="Update topology-model.md")
    args = parser.parse_args()

    if not LAYER_CONTRACT_PATH.exists():
        print(f"ERROR: Canonical source not found: {LAYER_CONTRACT_PATH}", file=sys.stderr)
        return 1

    contract = load_layer_contract()
    generated_table = generate_layer_table(contract)

    if args.check:
        return 0 if check_equivalence(generated_table) else 1
    elif args.update:
        if update_ai_rules(generated_table):
            print(f"OK: Updated {AI_RULES_PATH}")
            return 0
        return 1
    else:
        print(generated_table)
        return 0


if __name__ == "__main__":
    sys.exit(main())
