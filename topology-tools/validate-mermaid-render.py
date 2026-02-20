#!/usr/bin/env python3
"""
Validate Mermaid rendering for generated markdown documentation.

This script bundles all markdown docs into a single temporary markdown file
and runs Mermaid CLI (mmdc) against it. It is intended for CI/regression checks.
"""

import argparse
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path


def detect_icon_mode(doc_files):
    has_icon_nodes = False
    has_inline_icons = False
    for doc_file in doc_files:
        text = doc_file.read_text(encoding="utf-8", errors="ignore")
        if "@{ icon:" in text:
            has_icon_nodes = True
        if "data:image/svg+xml;base64," in text or "<img src=" in text:
            has_inline_icons = True

    if has_icon_nodes:
        return "icon-nodes"
    if has_inline_icons:
        return "compat"
    return "none"


def build_bundle(doc_files, bundle_path: Path):
    with bundle_path.open("w", encoding="utf-8") as handle:
        for doc_file in doc_files:
            handle.write(f"\n\n<!-- FILE: {doc_file.name} -->\n")
            handle.write(doc_file.read_text(encoding="utf-8", errors="ignore"))


def resolve_mmdc_runner():
    """
    Resolve command prefix for Mermaid CLI.
    Prefer npx package invocation, fallback to npm exec package invocation.
    """
    npx_exec = shutil.which("npx.cmd") or shutil.which("npx")
    if npx_exec:
        return [npx_exec, "--yes", "@mermaid-js/mermaid-cli"]

    npm_exec = shutil.which("npm.cmd") or shutil.which("npm")
    if npm_exec:
        return [npm_exec, "exec", "--yes", "@mermaid-js/mermaid-cli", "--"]

    raise FileNotFoundError("Neither 'npx(.cmd)' nor 'npm(.cmd)' is available in PATH.")


def run_mmdc(bundle_path: Path, assets_dir: Path, icon_mode: str, icon_packs):
    cmd = [
        *resolve_mmdc_runner(),
        "-i",
        str(bundle_path),
        "-o",
        str(bundle_path.with_suffix(".rendered.md")),
        "-a",
        str(assets_dir),
        "-q",
    ]
    if icon_mode == "icon-nodes":
        cmd.extend(["--iconPacks", *icon_packs])

    return subprocess.run(cmd, capture_output=True, text=True, check=False)


def main():
    parser = argparse.ArgumentParser(description="Validate Mermaid rendering in generated markdown docs.")
    parser.add_argument(
        "--docs-dir",
        default="generated/docs",
        help="Directory containing generated markdown docs (default: generated/docs)",
    )
    parser.add_argument(
        "--icon-mode",
        choices=("auto", "icon-nodes", "compat", "none"),
        default="auto",
        help="Icon mode for validation. auto detects mode from docs (default: auto)",
    )
    parser.add_argument(
        "--icon-packs",
        nargs="+",
        default=["@iconify-json/simple-icons", "@iconify-json/mdi", "@iconify-json/logos"],
        help="Iconify packs passed to mmdc for icon-node mode",
    )
    parser.add_argument(
        "--keep-temp",
        action="store_true",
        help="Keep temporary bundle and rendered files for debugging",
    )
    args = parser.parse_args()

    docs_dir = Path(args.docs_dir)
    if not docs_dir.exists():
        print(f"ERROR docs directory not found: {docs_dir}")
        return 1

    doc_files = sorted(docs_dir.glob("*.md"))
    if not doc_files:
        print(f"ERROR no markdown docs found in: {docs_dir}")
        return 1

    icon_mode = args.icon_mode
    if icon_mode == "auto":
        icon_mode = detect_icon_mode(doc_files)

    temp_root = Path(tempfile.mkdtemp(prefix="mermaid-validate-"))
    bundle_path = temp_root / "all-diagrams.md"
    assets_dir = temp_root / "assets"
    assets_dir.mkdir(parents=True, exist_ok=True)

    try:
        build_bundle(doc_files, bundle_path)
        result = run_mmdc(bundle_path, assets_dir, icon_mode, args.icon_packs)

        if result.returncode != 0:
            print(f"ERROR Mermaid render validation failed (mode={icon_mode}).")
            if result.stdout:
                print(result.stdout.strip())
            if result.stderr:
                print(result.stderr.strip())
            if args.keep_temp:
                print(f"INFO temp artifacts kept in: {temp_root}")
            return result.returncode

        print(
            f"OK Mermaid render validation passed: {len(doc_files)} docs "
            f"(mode={icon_mode})."
        )
        return 0
    except FileNotFoundError as err:
        print(f"ERROR {err}")
        return 2
    finally:
        if not args.keep_temp:
            shutil.rmtree(temp_root, ignore_errors=True)


if __name__ == "__main__":
    sys.exit(main())
