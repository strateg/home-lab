#!/usr/bin/env python3
"""Render ADR0083 reactivation readiness evidence to Markdown."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(f"Missing diagnostics JSON: {path}")
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"Diagnostics JSON must be an object: {path}")
    return payload


def _resolve_path(repo_root: Path, value: str) -> Path:
    path = Path(value)
    if not path.is_absolute():
        path = repo_root / path
    return path


def _safe_bool(value: Any) -> str:
    return "yes" if bool(value) else "no"


def _render_markdown(
    *,
    generated_at: str,
    bundle: str,
    reactivation: dict[str, Any],
    trigger: dict[str, Any],
    module_growth: dict[str, Any],
) -> str:
    adr_status = reactivation.get("adr_status", {})
    scaffold = reactivation.get("scaffold", {})
    env = reactivation.get("environment", {})
    blockers = reactivation.get("blocking_issues", [])

    lines: list[str] = []
    lines.append("# ADR0083 Reactivation Evidence")
    lines.append("")
    lines.append(f"- Generated at (UTC): `{generated_at}`")
    lines.append(f"- Bundle: `{bundle}`")
    lines.append("")
    lines.append("## Readiness Snapshot")
    lines.append("")
    lines.append("| Check | Value |")
    lines.append("|------|-------|")
    lines.append(f"| Ready for reactivation | `{_safe_bool(reactivation.get('ready_for_reactivation'))}` |")
    lines.append(f"| ADR status baseline OK | `{_safe_bool(adr_status.get('ok'))}` |")
    lines.append(f"| Scaffold files OK | `{_safe_bool(scaffold.get('ok'))}` |")
    lines.append(f"| ADR0047 trigger gate | `{trigger.get('gate', '')}` |")
    lines.append(f"| ADR0082 module growth gate | `{module_growth.get('gate', '')}` |")
    lines.append("")
    lines.append("## ADR Statuses")
    lines.append("")
    lines.append("| ADR | Status |")
    lines.append("|-----|--------|")
    lines.append(f"| 0083 | `{adr_status.get('0083', '')}` |")
    lines.append(f"| 0084 | `{adr_status.get('0084', '')}` |")
    lines.append(f"| 0085 | `{adr_status.get('0085', '')}` |")
    lines.append("")
    lines.append("## Capacity Signals")
    lines.append("")
    lines.append("| Metric | Value | Threshold |")
    lines.append("|--------|-------|-----------|")
    lines.append(f"| Alerts count | `{trigger.get('alerts_count', '')}` | `{trigger.get('alerts_threshold', '')}` |")
    lines.append(
        f"| Services count | `{trigger.get('services_count', '')}` | `{trigger.get('services_threshold', '')}` |"
    )
    lines.append(
        f"| Active module manifests | `{module_growth.get('active_module_manifests', '')}` | `{module_growth.get('active_module_manifest_threshold', '')}` |"
    )
    lines.append("")
    lines.append("## Environment")
    lines.append("")
    lines.append(f"- Platform: `{env.get('platform', '')}`")
    lines.append(f"- WSL detected: `{_safe_bool(env.get('is_wsl'))}`")
    lines.append(f"- Paramiko installed: `{_safe_bool(env.get('paramiko_installed'))}`")
    lines.append("")
    lines.append("## Blocking Issues")
    lines.append("")
    if isinstance(blockers, list) and blockers:
        for item in blockers:
            lines.append(f"- {item}")
    else:
        lines.append("- none")
    lines.append("")
    lines.append("## Smoke Pack Commands")
    lines.append("")
    lines.append("```bash")
    lines.append("task validate:adr0083-reactivation-gate")
    lines.append(f"task deploy:init-reactivation-smoke BUNDLE={bundle} SKIP_ENVIRONMENT_CHECK=true")
    lines.append("```")
    lines.append("")
    lines.append("## Notes")
    lines.append("")
    lines.append("- This file is generated for evidence capture.")
    lines.append("- Promote to `adr/0083-analysis/HARDWARE-EVIDENCE-YYYY-MM-DD.md` after hardware run.")
    lines.append("")
    return "\n".join(lines)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Render ADR0083 reactivation evidence markdown.")
    parser.add_argument(
        "--reactivation-json",
        default="build/diagnostics/adr0083-reactivation.json",
        help="Path to ADR0083 readiness JSON.",
    )
    parser.add_argument(
        "--trigger-json",
        default="build/diagnostics/adr0047-trigger.json",
        help="Path to ADR0047 trigger JSON.",
    )
    parser.add_argument(
        "--module-growth-json",
        default="build/diagnostics/module-growth.json",
        help="Path to ADR0082 module growth JSON.",
    )
    parser.add_argument(
        "--output-md",
        default="build/diagnostics/adr0083-reactivation-evidence.md",
        help="Output markdown path.",
    )
    parser.add_argument("--bundle", default="", help="Bundle ID used for smoke-run evidence.")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    repo_root = _repo_root()

    reactivation_path = _resolve_path(repo_root, args.reactivation_json)
    trigger_path = _resolve_path(repo_root, args.trigger_json)
    module_path = _resolve_path(repo_root, args.module_growth_json)
    output_path = _resolve_path(repo_root, args.output_md)

    reactivation = _load_json(reactivation_path)
    trigger = _load_json(trigger_path)
    module_growth = _load_json(module_path)
    generated_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    bundle = args.bundle.strip() or "<bundle_id>"

    markdown = _render_markdown(
        generated_at=generated_at,
        bundle=bundle,
        reactivation=reactivation,
        trigger=trigger,
        module_growth=module_growth,
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(markdown, encoding="utf-8")
    print(f"Rendered evidence markdown: {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
