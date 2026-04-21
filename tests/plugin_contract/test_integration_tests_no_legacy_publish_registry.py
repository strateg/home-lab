from __future__ import annotations

from pathlib import Path


def test_plugin_integration_suite_avoids_legacy_publish_registry_access() -> None:
    repo_root = Path(__file__).resolve().parents[2]
    integration_root = repo_root / "tests" / "plugin_integration"
    banned_tokens = (
        "get_published_data(",
        "_published_data[",
        "._published_data",
    )

    offenders: list[str] = []
    for path in sorted(integration_root.rglob("test_*.py")):
        text = path.read_text(encoding="utf-8")
        for token in banned_tokens:
            if token in text:
                offenders.append(f"{path.relative_to(repo_root)}: contains '{token}'")

    assert offenders == [], "plugin_integration tests must avoid legacy publish registry access:\n" + "\n".join(
        offenders
    )
