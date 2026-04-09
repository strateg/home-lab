#!/usr/bin/env python3
"""Generate framework provenance attestation payload for release artifacts."""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path


def _default_repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _find_checksums(dist_root: Path) -> Path:
    hits = sorted(dist_root.rglob("checksums.sha256"))
    if not hits:
        raise FileNotFoundError(f"checksums.sha256 not found under: {dist_root}")
    return hits[0]


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate release provenance payload for framework distribution.")
    parser.add_argument("--dist-root", type=Path, default=Path("dist/framework"))
    parser.add_argument("--output", type=Path, default=Path("dist/framework/provenance/provenance.json"))
    parser.add_argument("--repo", default="")
    parser.add_argument("--revision", default="")
    parser.add_argument("--release-tag", default="")
    parser.add_argument("--builder-id", default="github-actions")
    parser.add_argument("--predicate-type", default="https://slsa.dev/provenance/v1")
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    repo_root = _default_repo_root()
    dist_root = args.dist_root if args.dist_root.is_absolute() else repo_root / args.dist_root
    output = args.output if args.output.is_absolute() else repo_root / args.output

    try:
        checksums_file = _find_checksums(dist_root)
    except FileNotFoundError as exc:
        print(f"ERROR: {exc}")
        return 2

    output.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "schema_version": 1,
        "predicate_type": str(args.predicate_type).strip() or "https://slsa.dev/provenance/v1",
        "generated_at_utc": datetime.now(UTC).isoformat(),
        "builder": {
            "id": str(args.builder_id).strip() or "unknown-builder",
        },
        "source": {
            "repository": str(args.repo).strip(),
            "revision": str(args.revision).strip(),
            "release_tag": str(args.release_tag).strip(),
        },
        "subject": [
            {
                "name": checksums_file.name,
                "uri": checksums_file.resolve().as_uri(),
                "digest": {
                    "sha256": _sha256_file(checksums_file),
                },
            }
        ],
    }
    output.write_text(json.dumps(payload, ensure_ascii=True, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"provenance_path": str(output), "subject": checksums_file.name}, ensure_ascii=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
