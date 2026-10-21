#!/usr/bin/env python3
"""Validate device-configuration provenance over the rendered Terraform roots (ADR 0120).

Two obligations, both checkable offline against `generated/`:

1. **Provenance marker.** Every rendered resource that creates an object on a
   device carries the canonical marker in its comment, so an operator reading the
   device - or, later, a reconciliation builder reading an inventory - can tell
   what the topology owns. Exemptions are declared per resource type in
   `configs/quality/device-provenance-policy.yaml`, each with a stated reason.

2. **Rule placement.** Every rendered permit in a chain that ends with an
   unconditional drop declares its placement before that terminal rule. A permit
   without it is rendered correctly and dead on the device, which is exactly the
   defect recorded in docs/reports/2026-10-21-chateau-dead-rules.md.

The checks read the rendered `.tf` text rather than a provider or a device: they
must run in CI, offline, with no credentials, and stay a pure function of what
the generators produced.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
TOOLS_ROOT = ROOT / "topology-tools"
sys.path.insert(0, str(TOOLS_ROOT))

from yaml_loader import load_yaml_file  # noqa: E402

DEFAULT_POLICY_PATH = ROOT / "configs" / "quality" / "device-provenance-policy.yaml"
DEFAULT_ARTIFACTS_ROOT = ROOT / "generated"
DEFAULT_OUTPUT_JSON = ROOT / "build" / "diagnostics" / "device-provenance-report.json"
SUPPORTED_MODES = {"warn", "enforce"}

RESOURCE_RE = re.compile(r'(?m)^resource\s+"(?P<type>[A-Za-z0-9_]+)"\s+"(?P<name>[A-Za-z0-9_\-]+)"\s*\{')
ATTR_RE = re.compile(r'(?m)^\s*(?P<key>[a-z0-9_]+)\s*=\s*(?P<value>.+?)\s*$')


class Finding(dict):
    """A diagnostic, shaped like the rest of the repo's report artifacts."""

    def __init__(self, *, code: str, path: str, message: str) -> None:
        super().__init__(code=code, path=path, message=message)


def _load_policy(path: Path) -> dict[str, Any]:
    payload = load_yaml_file(path) or {}
    if not isinstance(payload, dict):
        raise ValueError(f"policy root must be a mapping: {path}")
    return payload


def _iter_resource_blocks(text: str) -> list[tuple[str, str, str]]:
    """Return (type, name, body) for each top-level resource block in a .tf file.

    The body ends at the first line that is exactly a closing brace, which is how
    every template in this repository terminates a resource. Nested blocks are
    indented, so they do not end it.
    """
    blocks: list[tuple[str, str, str]] = []
    matches = list(RESOURCE_RE.finditer(text))
    for index, match in enumerate(matches):
        start = match.end()
        end = len(text) if index + 1 >= len(matches) else matches[index + 1].start()
        segment = text[start:end]
        closing = re.search(r"(?m)^\}", segment)
        body = segment[: closing.start()] if closing else segment
        blocks.append((match.group("type"), match.group("name"), body))
    return blocks


def _attributes(body: str) -> dict[str, str]:
    attrs: dict[str, str] = {}
    for match in ATTR_RE.finditer(body):
        attrs.setdefault(match.group("key"), match.group("value").strip())
    return attrs


def _tf_files(policy: dict[str, Any], artifacts_root: Path) -> list[Path]:
    """Rendered .tf files under the roots the policy puts in force.

    Scoping is deliberate: a root that has no provenance contract yet - another
    device family, a cloud provider, or a stale directory left by a frozen track
    - must not be policed by accident, and must not be silently exempt either.
    Opting a family in is an edit to the policy, which is reviewable.
    """
    roots = [str(item) for item in ((policy.get("rendered") or {}).get("roots") or [])]
    if not roots:
        return []
    files: list[Path] = []
    for root in roots:
        base = (ROOT / root).resolve() if not Path(root).is_absolute() else Path(root)
        try:
            base.relative_to(artifacts_root)
        except ValueError:
            # The root lives outside the scanned tree (an explicit --artifacts-root
            # narrower than the policy); nothing to scan for it.
            continue
        if not base.exists():
            continue
        files.extend(path for path in base.rglob("*.tf") if path.is_file())
    return sorted(set(files))


def _rel(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def _check_marker(
    *,
    policy: dict[str, Any],
    resource_type: str,
    resource_name: str,
    body: str,
    file_path: Path,
    errors: list[Finding],
    stats: dict[str, int],
) -> None:
    marker_cfg = policy.get("marker") or {}
    rendered_cfg = policy.get("rendered") or {}
    canonical = str(marker_cfg.get("canonical") or "").strip()
    retired = [str(item) for item in (marker_cfg.get("retired") or [])]
    exempt = rendered_cfg.get("exempt_types") or {}

    if resource_type in exempt:
        stats["exempt"] += 1
        return

    manual_cfg = policy.get("manual_marker") or {}
    manual_prefix = str(manual_cfg.get("prefix") or "").strip()
    if manual_cfg.get("forbidden_in_rendered") and manual_prefix and manual_prefix in body:
        stats["claims_manual"] += 1
        errors.append(
            Finding(
                code="E8402",
                path=f"{_rel(file_path)}:{resource_type}.{resource_name}",
                message=(
                    f"rendered resource claims the manual marker {manual_prefix!r}. A generated object must "
                    "not read as a sanctioned hand-made exception, or reconciliation will spare the very "
                    "thing it owns."
                ),
            )
        )
        return

    found_retired = [spelling for spelling in retired if spelling in body]
    if found_retired:
        stats["retired_marker"] += 1
        errors.append(
            Finding(
                code="E8401",
                path=f"{_rel(file_path)}:{resource_type}.{resource_name}",
                message=(
                    f"rendered resource carries a retired provenance marker {found_retired[0]!r}; "
                    f"the canonical marker is {canonical!r}. Three spellings made provenance "
                    "unreadable to any mechanical check."
                ),
            )
        )
        return

    if canonical and canonical in body:
        stats["marked"] += 1
        return

    stats["unmarked"] += 1
    errors.append(
        Finding(
            code="E8400",
            path=f"{_rel(file_path)}:{resource_type}.{resource_name}",
            message=(
                f"rendered resource has no provenance marker. Add {canonical!r} to its comment, "
                "or declare the type in rendered.exempt_types with a reason "
                "(no_comment_attribute / singleton_settings / not_a_device_object)."
            ),
        )
    )


def _terminals_for(policy: dict[str, Any], *, resource_type: str, chain: str) -> list[dict[str, Any]]:
    cfg = policy.get("rule_placement") or {}
    out: list[dict[str, Any]] = []
    for item in cfg.get("terminals") or []:
        if not isinstance(item, dict):
            continue
        if item.get("resource_type") != resource_type:
            continue
        if str(item.get("chain") or "") != chain:
            continue
        out.append(item)
    return out


def _check_placement(
    *,
    policy: dict[str, Any],
    resource_type: str,
    resource_name: str,
    attrs: dict[str, str],
    terminal_bodies: dict[tuple[str, str], str],
    file_path: Path,
    errors: list[Finding],
    warnings: list[Finding],
    stats: dict[str, int],
) -> None:
    cfg = policy.get("rule_placement") or {}
    if not cfg.get("enforced"):
        return
    if resource_type not in set(cfg.get("resource_types") or []):
        return

    chain = attrs.get("chain", "").strip('"')
    terminals = _terminals_for(policy, resource_type=resource_type, chain=chain)
    if not terminals:
        return
    if any(resource_name == terminal.get("name") for terminal in terminals):
        stats["terminal"] += 1
        return

    action = attrs.get("action", "").strip('"')
    if action not in set(cfg.get("guarded_actions") or []):
        return

    attribute = str(cfg.get("placement_attribute") or "place_before")
    placement = attrs.get(attribute, "")
    names = [str(terminal.get("name")) for terminal in terminals]

    # Proof 1: the permit names the terminal.
    if any(name in placement for name in names):
        stats["placed"] += 1
        return

    # Proof 2: the terminal names the permit in depends_on, which fixes creation
    # order and therefore device order, without rendering a device attribute.
    for terminal in terminals:
        terminal_body = terminal_bodies.get((resource_type, str(terminal.get("name"))))
        # The reference must be the full `type.name`, not a substring of it:
        # `depends_on = [..other_permit]` must not prove placement for `permit`.
        reference = re.escape(f"{resource_type}.{resource_name}")
        if terminal_body and re.search(rf"\bdepends_on\b.*?\b{reference}\b", terminal_body, re.S):
            stats["placed_by_depends_on"] += 1
            return

    unconditional = any(bool(terminal.get("unconditional")) for terminal in terminals)
    finding = Finding(
        code="E8410" if unconditional else "W8410",
        path=f"{_rel(file_path)}:{resource_type}.{resource_name}",
        message=(
            f"rendered '{action}' rule in chain '{chain}' proves no placement relative to the chain's "
            f"terminal rule ({', '.join(names)}). "
            + (
                "That terminal matches everything, so a rule created after it is dead. "
                if unconditional
                else "That terminal is conditional, so the order is unspecified rather than wrong. "
            )
            + f"Declare {attribute} on this rule, or depends_on it from the terminal."
        ),
    )
    if unconditional:
        stats["unplaced"] += 1
        errors.append(finding)
    else:
        stats["unspecified_order"] += 1
        warnings.append(finding)


def run_provenance(*, policy_path: Path, artifacts_root: Path, mode: str) -> dict[str, Any]:
    if mode not in SUPPORTED_MODES:
        raise ValueError(f"unsupported mode: {mode}")
    policy = _load_policy(policy_path)
    errors: list[Finding] = []
    warnings: list[Finding] = []
    stats = {
        "resources": 0,
        "marked": 0,
        "unmarked": 0,
        "retired_marker": 0,
        "claims_manual": 0,
        "exempt": 0,
        "placed": 0,
        "placed_by_depends_on": 0,
        "unplaced": 0,
        "unspecified_order": 0,
        "terminal": 0,
    }

    files = _tf_files(policy, artifacts_root)

    # Pass 1: the terminal rules' bodies, so a permit can be proven by the
    # terminal's own depends_on no matter which file either lives in.
    parsed: list[tuple[Path, str, str, str, dict[str, str]]] = []
    terminal_bodies: dict[tuple[str, str], str] = {}
    terminal_keys = {
        (str(item.get("resource_type")), str(item.get("name")))
        for item in ((policy.get("rule_placement") or {}).get("terminals") or [])
        if isinstance(item, dict)
    }
    for file_path in files:
        text = file_path.read_text(encoding="utf-8", errors="ignore")
        for resource_type, resource_name, body in _iter_resource_blocks(text):
            parsed.append((file_path, resource_type, resource_name, body, _attributes(body)))
            if (resource_type, resource_name) in terminal_keys:
                terminal_bodies[(resource_type, resource_name)] = body

    # Pass 2: the obligations.
    for file_path, resource_type, resource_name, body, attrs in parsed:
        stats["resources"] += 1
        _check_marker(
            policy=policy,
            resource_type=resource_type,
            resource_name=resource_name,
            body=body,
            file_path=file_path,
            errors=errors,
            stats=stats,
        )
        _check_placement(
            policy=policy,
            resource_type=resource_type,
            resource_name=resource_name,
            attrs=attrs,
            terminal_bodies=terminal_bodies,
            file_path=file_path,
            errors=errors,
            warnings=warnings,
            stats=stats,
        )

    reported_errors = errors if mode == "enforce" else []
    reported_warnings = warnings + ([] if mode == "enforce" else errors)

    return {
        "schema_version": 1,
        "generated_at": datetime.now(UTC).isoformat(),
        "mode": mode,
        "policy_path": str(policy_path),
        "artifacts_root": str(artifacts_root),
        "files_scanned": len(files),
        "statistics": stats,
        "errors": reported_errors,
        "warnings": reported_warnings,
        "summary": {"errors": len(reported_errors), "warnings": len(reported_warnings)},
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__ or "")
    parser.add_argument("--policy", type=Path, default=DEFAULT_POLICY_PATH)
    parser.add_argument("--artifacts-root", type=Path, default=DEFAULT_ARTIFACTS_ROOT)
    parser.add_argument("--output-json", type=Path, default=DEFAULT_OUTPUT_JSON)
    parser.add_argument("--mode", choices=sorted(SUPPORTED_MODES), default="enforce")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    policy_path = args.policy if args.policy.is_absolute() else args.policy.resolve()
    artifacts_root = args.artifacts_root if args.artifacts_root.is_absolute() else args.artifacts_root.resolve()
    output_json = args.output_json if args.output_json.is_absolute() else args.output_json.resolve()

    report = run_provenance(policy_path=policy_path, artifacts_root=artifacts_root, mode=args.mode)
    output_json.parent.mkdir(parents=True, exist_ok=True)
    output_json.write_text(json.dumps(report, ensure_ascii=True, indent=2) + "\n", encoding="utf-8")
    print(f"[device-provenance] report: {output_json}")
    stats = report["statistics"]
    print(
        "[device-provenance] resources={resources} marked={marked} exempt={exempt} "
        "placed={placed} terminal={terminal}".format(**stats)
    )

    for item in report["warnings"]:
        print(f"[device-provenance] WARN {item['code']} {item['path']}: {item['message']}")
    for item in report["errors"]:
        print(f"[device-provenance] ERROR {item['code']} {item['path']}: {item['message']}")

    if report["summary"]["errors"] > 0:
        print("[device-provenance] FAIL")
        return 1
    print("[device-provenance] PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
