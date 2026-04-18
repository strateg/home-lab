from __future__ import annotations

from pathlib import Path


def test_runtime_plugin_code_limits_legacy_publish_registry_access() -> None:
    repo_root = Path(__file__).resolve().parents[2]
    plugins_root = repo_root / "topology-tools" / "plugins"
    token = "get_published_data("

    allowlist = {
        Path("topology-tools/plugins/assemblers/artifact_contract_assembler.py"),
        Path("topology-tools/plugins/generators/artifact_manifest_generator.py"),
    }

    offenders: list[str] = []
    for path in sorted(plugins_root.rglob("*.py")):
        rel = path.relative_to(repo_root)
        text = path.read_text(encoding="utf-8")
        if token in text and rel not in allowlist:
            offenders.append(str(rel))

    assert offenders == [], (
        "Only allowlisted transitional aggregators may access legacy publish registry; "
        f"unexpected usage in: {offenders}"
    )
