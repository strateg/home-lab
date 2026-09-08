"""Contract test: AI rules layer table MUST match canonical layer-contract.yaml.

This test enforces semantic equivalence between:
- Source: topology/layer-contract.yaml (canonical)
- Target: docs/ai/rules/topology-model.md (AI rule pack)

Finding: F.P2 from architecture review identified that AI rules diverged
from canonical model, causing agents to select wrong layers.

Solution: Generate table from canonical source + contract test guard.
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
LAYER_CONTRACT_PATH = REPO_ROOT / "topology" / "layer-contract.yaml"
AI_RULES_PATH = REPO_ROOT / "docs" / "ai" / "rules" / "topology-model.md"
GENERATOR_PATH = REPO_ROOT / "scripts" / "generators" / "generate_ai_layer_table.py"

TABLE_START_MARKER = "<!-- GENERATED:LAYER_TABLE:START -->"
TABLE_END_MARKER = "<!-- GENERATED:LAYER_TABLE:END -->"


@pytest.fixture
def layer_contract() -> dict:
    """Load canonical layer contract."""
    with LAYER_CONTRACT_PATH.open("r", encoding="utf-8") as f:
        return yaml.safe_load(f)


@pytest.fixture
def ai_rules_content() -> str:
    """Load AI rules markdown content."""
    return AI_RULES_PATH.read_text(encoding="utf-8")


def extract_table_from_markdown(content: str) -> list[dict]:
    """Extract layer table rows from markdown content."""
    # Find generated table block
    pattern = re.compile(
        rf"{re.escape(TABLE_START_MARKER)}(.*?){re.escape(TABLE_END_MARKER)}",
        re.DOTALL,
    )
    match = pattern.search(content)
    if not match:
        pytest.fail(f"Generated table markers not found in {AI_RULES_PATH}")

    table_content = match.group(1)

    # Parse markdown table rows
    rows = []
    for line in table_content.strip().split("\n"):
        if line.startswith("|") and not line.startswith("|--") and "Layer" not in line:
            parts = [p.strip() for p in line.split("|")[1:-1]]
            if len(parts) >= 2:
                rows.append({"layer": parts[0], "scope": parts[1].lower()})

    return rows


class TestLayerTableContract:
    """Contract tests for AI rules layer table."""

    def test_generated_markers_present(self, ai_rules_content: str) -> None:
        """Generated table markers MUST be present."""
        assert TABLE_START_MARKER in ai_rules_content, f"Missing start marker: {TABLE_START_MARKER}"
        assert TABLE_END_MARKER in ai_rules_content, f"Missing end marker: {TABLE_END_MARKER}"

    def test_all_layers_present(self, ai_rules_content: str) -> None:
        """All L0-L7 layers MUST be present in table."""
        rows = extract_table_from_markdown(ai_rules_content)
        layers_found = {row["layer"] for row in rows}
        expected_layers = {"L0", "L1", "L2", "L3", "L4", "L5", "L6", "L7"}

        assert layers_found == expected_layers, f"Layer mismatch. Expected: {expected_layers}, Found: {layers_found}"

    def test_layer_semantics_match_canonical(self, layer_contract: dict, ai_rules_content: str) -> None:
        """Layer scope names MUST match canonical layer_semantics."""
        canonical_semantics = layer_contract.get("layer_semantics", {})
        rows = extract_table_from_markdown(ai_rules_content)

        mismatches = []
        for row in rows:
            layer = row["layer"]
            ai_scope = row["scope"].replace(" ", "_")
            canonical_scope = canonical_semantics.get(layer, "")

            if ai_scope != canonical_scope:
                mismatches.append(f"{layer}: AI='{ai_scope}' vs Canonical='{canonical_scope}'")

        assert not mismatches, f"Layer semantics mismatch:\n" + "\n".join(mismatches)

    def test_generator_check_passes(self) -> None:
        """Generator --check MUST pass (table matches canonical source)."""
        result = subprocess.run(
            [sys.executable, str(GENERATOR_PATH), "--check"],
            capture_output=True,
            text=True,
            cwd=REPO_ROOT,
        )

        assert result.returncode == 0, f"Generator check failed:\n{result.stderr}\n{result.stdout}"

    def test_adr_reference_valid(self, ai_rules_content: str) -> None:
        """AI rules MUST reference ADR 0062 (layer taxonomy source)."""
        # Extract @adr line from frontmatter (supports both quoted and unquoted keys)
        adr_match = re.search(r'"?@adr"?:\s*\[([^\]]+)\]', ai_rules_content)
        assert adr_match, "Missing @adr reference in frontmatter"

        # Parse ADR numbers (handle leading zeros as strings, not octal)
        adr_refs = [int(x.strip().lstrip("0") or "0") for x in adr_match.group(1).split(",")]
        assert 62 in adr_refs, f"ADR 0062 (layer taxonomy) MUST be in @adr references. Found: {adr_refs}"


class TestLayerContractIntegrity:
    """Integrity tests for canonical layer-contract.yaml."""

    def test_layer_contract_has_all_layers(self, layer_contract: dict) -> None:
        """Canonical contract MUST define all L0-L7 semantics."""
        semantics = layer_contract.get("layer_semantics", {})
        expected = {"L0", "L1", "L2", "L3", "L4", "L5", "L6", "L7"}
        found = set(semantics.keys())

        assert found == expected, f"layer_semantics incomplete. Missing: {expected - found}"

    def test_layer_contract_schema_version(self, layer_contract: dict) -> None:
        """Canonical contract MUST have schema_version >= 2."""
        version = layer_contract.get("schema_version", 0)
        assert version >= 2, f"schema_version {version} < 2"
