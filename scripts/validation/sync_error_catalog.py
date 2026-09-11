#!/usr/bin/env python3
"""Sync and validate error catalog against source code usage.

This script:
1. Parses error-catalog.yaml for defined codes
2. Scans source files for diagnostic code usage (E/W/Ixxxx patterns)
3. Reports undefined codes (used but not in catalog)
4. Reports unused codes (in catalog but not used)
5. Reports code collisions: one code emitted with unrelated meanings
6. Generates coverage statistics

A collision is the defect the governance rules exist to prevent, and it is not
the same thing as a shared code. Several modules emitting E4102 "plugin crashed"
share one meaning and are fine. Two modules emitting one code for a VLAN ID
collision and for a service dependency error are not: the code no longer
identifies anything, and every report, filter and runbook keyed on it is wrong.

Sharing is detected structurally - by the emitted message text per module - so
the check needs no list of blessed exceptions to maintain.

Usage:
    python scripts/validation/sync_error_catalog.py [--fix] [--verbose]

Exit codes:
    0 - All codes synchronized
    1 - Undefined codes found (codes used but not in catalog)
"""

from __future__ import annotations

import argparse
import ast
import re
import sys
from pathlib import Path
from typing import Any

import yaml

# Diagnostic code pattern: E/W/I followed by 4 digits
CODE_PATTERN = re.compile(r"\b([EWI]\d{4})\b")

# Directories to scan for code usage
# Corrected 2026-09-11: the top level of topology-tools was missing, so every code
# emitted by compile-topology.py, compiler_runtime.py, framework_lock.py and
# compiler_framework_lock.py was invisible to this check - including E7808 and the
# E7821..E7827 framework-lock family, which collide with network validators. A
# registry check that does not read the compiler itself measures the wrong system.
SCAN_DIRS = [
    "topology-tools",
    "topology/class-modules",
    "topology/object-modules",
    "scripts/orchestration",
    "scripts/validation",
]

# Files to exclude (tests use codes for assertions)
EXCLUDE_PATTERNS = [
    "test_",
    "_test.py",
    "conftest.py",
]


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def load_catalog(catalog_path: Path) -> dict[str, dict[str, Any]]:
    """Load error catalog and return code definitions."""
    with catalog_path.open("r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    return data.get("codes", {})


def scan_source_files(repo_root: Path) -> dict[str, list[tuple[Path, int]]]:
    """Scan source files for diagnostic code usage.

    Returns:
        Dictionary mapping code to list of (file_path, line_number) tuples.
    """
    usage: dict[str, list[tuple[Path, int]]] = {}

    for scan_dir in SCAN_DIRS:
        dir_path = repo_root / scan_dir
        if not dir_path.exists():
            continue

        for path in dir_path.rglob("*.py"):
            # Skip test files
            if any(pattern in path.name for pattern in EXCLUDE_PATTERNS):
                continue

            try:
                content = path.read_text(encoding="utf-8")
            except Exception:
                continue

            for lineno, line in enumerate(content.splitlines(), start=1):
                # Skip comments
                stripped = line.lstrip()
                if stripped.startswith("#"):
                    continue

                for match in CODE_PATTERN.finditer(line):
                    code = match.group(1)
                    if code not in usage:
                        usage[code] = []
                    usage[code].append((path, lineno))

    return usage


def _message_literal(node: ast.AST) -> str:
    """Best-effort static text of a message argument, formatting holes removed."""
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    if isinstance(node, ast.JoinedStr):
        return "".join(part.value for part in node.values if isinstance(part, ast.Constant))
    if isinstance(node, ast.BinOp):
        return _message_literal(node.left) + _message_literal(node.right)
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr == "format":
        return _message_literal(node.func.value)
    return ""


def scan_emissions(repo_root: Path) -> dict[str, dict[str, set[str]]]:
    """Map each emitted code to the message text each module emits it with.

    Only actual emissions count - a `code=` keyword or a constant whose name
    contains CODE. A mention in a docstring is documentation, and treating it as
    an emission would report the module that documents a code as an owner of it.
    """
    emissions: dict[str, dict[str, set[str]]] = {}

    for scan_dir in SCAN_DIRS:
        dir_path = repo_root / scan_dir
        if not dir_path.exists():
            continue
        for path in dir_path.rglob("*.py"):
            if any(pattern in path.name for pattern in EXCLUDE_PATTERNS):
                continue
            try:
                tree = ast.parse(path.read_text(encoding="utf-8"))
            except (OSError, SyntaxError):
                continue

            module = path.relative_to(repo_root).as_posix()
            for node in ast.walk(tree):
                if not isinstance(node, ast.Call):
                    continue
                keywords = {kw.arg: kw.value for kw in node.keywords if kw.arg}
                code_node = keywords.get("code")
                if not (isinstance(code_node, ast.Constant) and isinstance(code_node.value, str)):
                    continue
                code = code_node.value
                if not CODE_PATTERN.fullmatch(code):
                    continue
                message = _message_literal(keywords.get("message") or keywords.get("msg") or ast.Constant(""))
                emissions.setdefault(code, {}).setdefault(module, set()).add(message.strip()[:120])

    return emissions


# Words that carry no meaning for telling two diagnostics apart.
_STOPWORDS = frozenset(
    """a an and are as at be but by cannot for from got has have in is it its must
    no not of on or requires set the to when with without""".split()
)


def _meaning_tokens(message: str) -> set[str]:
    return {word for word in re.findall(r"[a-z_]{3,}", message.lower())} - _STOPWORDS


def find_collisions(emissions: dict[str, dict[str, set[str]]]) -> dict[str, dict[str, set[str]]]:
    """Codes emitted by several modules whose messages share no subject.

    Comparing message text exactly is too strict to be useful. Eleven generators
    emitting "compiled_json is empty; cannot generate X artifacts" state one
    meaning with a different tail each time, and calling that a collision would
    bury the real ones. Comparing the vocabulary instead asks the question that
    matters: do these messages talk about the same thing at all?

    Two shared meaningful words is the threshold. Below it a code has been given
    two jobs - a VLAN id clash and a service dependency error, say - and nothing
    downstream can tell which one a report refers to.
    """
    collisions: dict[str, dict[str, set[str]]] = {}
    for code, by_module in emissions.items():
        if len(by_module) < 2:
            continue
        per_module = [
            set().union(*(_meaning_tokens(message) for message in messages)) for messages in by_module.values()
        ]
        if any(not tokens for tokens in per_module):
            continue  # a message we could not read statically proves nothing
        if len(set.intersection(*per_module)) < 2:
            collisions[code] = by_module
    return collisions


def analyze_sync(
    catalog_codes: dict[str, dict[str, Any]],
    source_usage: dict[str, list[tuple[Path, int]]],
) -> tuple[set[str], set[str], set[str]]:
    """Analyze synchronization between catalog and source usage.

    Returns:
        Tuple of (undefined_codes, unused_codes, synced_codes)
    """
    defined = set(catalog_codes.keys())
    used = set(source_usage.keys())

    undefined = used - defined  # Used but not in catalog
    unused = defined - used  # In catalog but not used
    synced = defined & used  # Both defined and used

    return undefined, unused, synced


def print_report(
    catalog_codes: dict[str, dict[str, Any]],
    source_usage: dict[str, list[tuple[Path, int]]],
    undefined: set[str],
    unused: set[str],
    synced: set[str],
    repo_root: Path,
    verbose: bool = False,
) -> None:
    """Print synchronization report."""
    total_defined = len(catalog_codes)
    total_used = len(source_usage)

    print("=" * 60)
    print("ERROR CATALOG SYNCHRONIZATION REPORT")
    print("=" * 60)
    print()
    print(f"Defined in catalog: {total_defined}")
    print(f"Used in source:     {total_used}")
    print(f"Synchronized:       {len(synced)}")
    print()

    # Undefined codes (ERROR)
    if undefined:
        print(f"UNDEFINED CODES ({len(undefined)}) - Used but not in catalog:")
        for code in sorted(undefined):
            locations = source_usage.get(code, [])
            print(f"  {code}:")
            for path, lineno in locations[:3]:
                rel_path = path.relative_to(repo_root)
                print(f"    - {rel_path}:{lineno}")
            if len(locations) > 3:
                print(f"    ... and {len(locations) - 3} more")
        print()

    # Unused codes (WARNING)
    if unused:
        print(f"UNUSED CODES ({len(unused)}) - In catalog but not used:")
        for code in sorted(unused):
            entry = catalog_codes.get(code, {})
            title = entry.get("title", "")
            stage = entry.get("stage", "")
            print(f"  {code}: [{stage}] {title}")
        print()

    # Coverage statistics
    if total_defined > 0:
        coverage = len(synced) / total_defined * 100
        print(f"Coverage: {coverage:.1f}% ({len(synced)}/{total_defined})")
    print()

    # Verbose: show all synced codes grouped by severity
    if verbose and synced:
        print("SYNCED CODES BY SEVERITY:")
        for severity in ["error", "warning", "info"]:
            codes_of_severity = [
                code for code in sorted(synced) if catalog_codes.get(code, {}).get("severity") == severity
            ]
            if codes_of_severity:
                print(f"  {severity.upper()} ({len(codes_of_severity)}):")
                for code in codes_of_severity:
                    title = catalog_codes[code].get("title", "")
                    print(f"    {code}: {title}")
        print()


def generate_stub_entries(
    undefined: set[str],
    source_usage: dict[str, list[tuple[Path, int]]],
) -> str:
    """Generate YAML stub entries for undefined codes."""
    lines = []
    for code in sorted(undefined):
        severity = "error" if code.startswith("E") else "warning" if code.startswith("W") else "info"
        locations = source_usage.get(code, [])
        first_file = locations[0][0].name if locations else "unknown"

        lines.append(f"  {code}:")
        lines.append(f"    severity: {severity}")
        lines.append(f"    stage: unknown  # TODO: determine stage from {first_file}")
        lines.append(f"    title: TODO")
        lines.append(f"    hint: TODO")
        lines.append("")

    return "\n".join(lines)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Sync error catalog with source code usage.")
    parser.add_argument(
        "--fix",
        action="store_true",
        help="Generate stub entries for undefined codes (prints to stdout).",
    )
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Show detailed output including all synced codes.",
    )
    parser.add_argument(
        "--warn-unused",
        action="store_true",
        help="Exit with error if unused codes are found.",
    )
    parser.add_argument(
        "--fail-on-collision",
        action="store_true",
        help="Exit with error if one code is emitted with unrelated meanings.",
    )
    parser.add_argument(
        "--output-json",
        type=Path,
        help="Write report as JSON to specified file.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    repo_root = _repo_root()

    catalog_path = repo_root / "topology-tools" / "data" / "error-catalog.yaml"
    if not catalog_path.exists():
        print(f"ERROR: Catalog not found: {catalog_path}")
        return 1

    print(f"Loading catalog: {catalog_path.relative_to(repo_root)}")
    catalog_codes = load_catalog(catalog_path)

    print(f"Scanning source directories...")
    source_usage = scan_source_files(repo_root)

    undefined, unused, synced = analyze_sync(catalog_codes, source_usage)
    emissions = scan_emissions(repo_root)
    collisions = find_collisions(emissions)

    print_report(
        catalog_codes,
        source_usage,
        undefined,
        unused,
        synced,
        repo_root,
        verbose=args.verbose,
    )

    if collisions:
        print("\n" + "=" * 60)
        print(f"CODE COLLISIONS ({len(collisions)}) - one code, unrelated meanings:")
        print("=" * 60)
        for code in sorted(collisions):
            print(f"  {code}:")
            for module, messages in sorted(collisions[code].items()):
                sample = sorted(m for m in messages if m)
                shown = sample[0] if sample else "(message not a literal)"
                print(f"    {module}")
                print(f"        {shown}")

    # JSON output
    if args.output_json:
        import json

        report = {
            "total_defined": len(catalog_codes),
            "total_used": len(source_usage),
            "synced_count": len(synced),
            "undefined_codes": sorted(undefined),
            "unused_codes": sorted(unused),
            "synced_codes": sorted(synced),
            "collisions": {
                code: {module: sorted(messages) for module, messages in sorted(by_module.items())}
                for code, by_module in sorted(collisions.items())
            },
        }
        args.output_json.parent.mkdir(parents=True, exist_ok=True)
        args.output_json.write_text(json.dumps(report, indent=2))
        print(f"Report written to {args.output_json}")

    # Generate stubs if requested
    if args.fix and undefined:
        print("\n" + "=" * 60)
        print("STUB ENTRIES (add to error-catalog.yaml):")
        print("=" * 60)
        print(generate_stub_entries(undefined, source_usage))

    # Exit code
    if args.fail_on_collision and collisions:
        print(f"FAILED: {len(collisions)} codes are emitted with unrelated meanings")
        return 1

    if undefined:
        print("FAILED: Undefined codes must be added to error-catalog.yaml")
        return 1

    if args.warn_unused and unused:
        print("FAILED: Unused codes found (--warn-unused enabled)")
        return 1

    print("OK: Error catalog is synchronized")
    return 0


if __name__ == "__main__":
    sys.exit(main())
