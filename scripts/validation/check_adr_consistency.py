#!/usr/bin/env python3
"""Check ADR register/file consistency with pragmatic repository defaults."""

from __future__ import annotations

import argparse
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence

REGISTER_LINK_RE = re.compile(r"\[(\d{4})\]\(([^)]+)\)")
ADR_HEADING_RE = re.compile(r"^#\s*ADR[- ](\d{4}):\s*(.+?)\s*$")
DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


@dataclass(frozen=True)
class RegisterEntry:
    number: str
    rel_path: str
    title: str
    status: str
    date: str
    supersedes: list[str]
    superseded_by: list[str]
    line_no: int


@dataclass(frozen=True)
class AdrMeta:
    number: str
    title: str
    status: str | None
    date: str | None


def _normalize_status(raw: str) -> str:
    value = " ".join(raw.strip().split())
    lower = value.lower()
    if lower.startswith("superseded"):
        return "Superseded"
    if lower.startswith("accepted"):
        return "Accepted"
    if lower.startswith("proposed"):
        return "Proposed"
    if lower.startswith("deprecated"):
        return "Deprecated"
    if lower.startswith("implemented"):
        return "Implemented"
    if lower == "approved":
        return "Approved"
    if lower == "partially implemented":
        return "Partially Implemented"
    return value


def _normalize_title(raw: str) -> str:
    value = raw.strip().replace("—", "-").replace("–", "-")
    return re.sub(r"\s+", " ", value)


def _parse_status(lines: list[str]) -> str | None:
    for line in lines:
        match = re.match(r"^\*\*Status:\*\*\s*(.+)$", line.strip())
        if match:
            return _normalize_status(match.group(1))
        match = re.match(r"^-\s*Status:\s*(.+)$", line.strip())
        if match:
            return _normalize_status(match.group(1))
    for idx, line in enumerate(lines):
        if line.strip() != "## Status":
            continue
        for cursor in range(idx + 1, len(lines)):
            candidate = lines[cursor].strip()
            if candidate:
                return _normalize_status(candidate)
    return None


def _parse_date(lines: list[str]) -> str | None:
    for line in lines:
        match = re.match(r"^\*\*Date:\*\*\s*(.+)$", line.strip())
        if match:
            date_value = match.group(1).strip()
            if DATE_RE.match(date_value):
                return date_value
        match = re.match(r"^-\s*Date:\s*(.+)$", line.strip())
        if match:
            date_value = match.group(1).strip()
            if DATE_RE.match(date_value):
                return date_value
    for idx, line in enumerate(lines):
        if line.strip() != "## Date":
            continue
        for cursor in range(idx + 1, len(lines)):
            candidate = lines[cursor].strip()
            if not candidate:
                continue
            if DATE_RE.match(candidate):
                return candidate
            return None
    return None


def _parse_adr_meta(adr_file: Path) -> AdrMeta | None:
    lines = adr_file.read_text(encoding="utf-8").splitlines()
    heading_line = next((line for line in lines if line.startswith("#")), None)
    if heading_line is None:
        return None
    match = ADR_HEADING_RE.match(heading_line.strip())
    if not match:
        return None
    return AdrMeta(
        number=match.group(1),
        title=match.group(2).strip(),
        status=_parse_status(lines),
        date=_parse_date(lines),
    )


def _parse_link_cell(cell: str) -> list[tuple[str, str]]:
    stripped = cell.strip()
    if stripped == "-":
        return []
    return REGISTER_LINK_RE.findall(stripped)


def _parse_register(register_path: Path) -> tuple[dict[str, RegisterEntry], list[str]]:
    errors: list[str] = []
    entries: dict[str, RegisterEntry] = {}
    lines = register_path.read_text(encoding="utf-8").splitlines()

    for idx, line in enumerate(lines, start=1):
        if not line.startswith("| ["):
            continue
        columns = [part.strip() for part in line.strip().strip("|").split("|")]
        if len(columns) != 6:
            errors.append(f"REGISTER:{idx}: expected 6 columns, got {len(columns)}")
            continue
        link_match = REGISTER_LINK_RE.fullmatch(columns[0])
        if not link_match:
            errors.append(f"REGISTER:{idx}: invalid ADR link column: '{columns[0]}'")
            continue
        number, rel_path = link_match.group(1), link_match.group(2)
        if number in entries:
            errors.append(f"REGISTER:{idx}: duplicate ADR number {number}")
            continue
        status = _normalize_status(columns[2])
        date = columns[3].strip()
        if not DATE_RE.match(date):
            errors.append(f"REGISTER:{idx}: invalid date '{date}'")
        supersedes_links = _parse_link_cell(columns[4])
        superseded_by_links = _parse_link_cell(columns[5])

        entries[number] = RegisterEntry(
            number=number,
            rel_path=rel_path,
            title=columns[1].strip(),
            status=status,
            date=date,
            supersedes=[num for num, _ in supersedes_links],
            superseded_by=[num for num, _ in superseded_by_links],
            line_no=idx,
        )

    if list(entries.keys()) != sorted(entries.keys()):
        errors.append("REGISTER: ADR rows are not sorted by number")
    return entries, errors


def _check_symmetry(entries: dict[str, RegisterEntry]) -> list[str]:
    errors: list[str] = []
    for number, entry in entries.items():
        for target in entry.supersedes:
            if target not in entries:
                errors.append(f"ADR {number}: Supersedes references missing ADR {target}")
                continue
            if number not in entries[target].superseded_by:
                errors.append(f"ADR {number}: Supersedes->{target} is not mirrored by ADR {target} Superseded By")
        for target in entry.superseded_by:
            if target not in entries:
                errors.append(f"ADR {number}: Superseded By references missing ADR {target}")
                continue
            if number not in entries[target].supersedes:
                errors.append(f"ADR {number}: Superseded By->{target} is not mirrored by ADR {target} Supersedes")
    return errors


def check_consistency(
    *,
    adr_dir: Path,
    register_path: Path,
    strict_titles: bool,
    require_symmetry: bool,
) -> tuple[list[str], list[str]]:
    errors: list[str] = []
    warnings: list[str] = []
    entries, parse_errors = _parse_register(register_path)
    errors.extend(parse_errors)
    if not entries:
        return errors, warnings

    if require_symmetry:
        errors.extend(_check_symmetry(entries))

    for number, entry in entries.items():
        adr_file = adr_dir / entry.rel_path
        if not adr_file.exists():
            errors.append(f"ADR {number}: file not found: {entry.rel_path}")
            continue
        meta = _parse_adr_meta(adr_file)
        if meta is None:
            errors.append(f"ADR {number}: cannot parse ADR heading from {entry.rel_path}")
            continue
        if meta.number != number:
            errors.append(f"ADR {number}: heading number mismatch, file declares ADR {meta.number} ({entry.rel_path})")

        register_title = _normalize_title(entry.title)
        file_title = _normalize_title(meta.title)
        if register_title != file_title:
            message = f"ADR {number}: title mismatch register='{entry.title}' file='{meta.title}'"
            if strict_titles:
                errors.append(message)
            else:
                warnings.append(message)

        if meta.status is None:
            warnings.append(f"ADR {number}: status not found in file {entry.rel_path}")
        elif _normalize_status(meta.status) != _normalize_status(entry.status):
            errors.append(f"ADR {number}: status mismatch register='{entry.status}' file='{meta.status}'")

        if meta.date is None:
            warnings.append(f"ADR {number}: date not found in file {entry.rel_path}")
        elif meta.date != entry.date:
            errors.append(f"ADR {number}: date mismatch register='{entry.date}' file='{meta.date}'")

    return errors, warnings


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Check ADR consistency between register and ADR files.")
    parser.add_argument("--adr-dir", default="adr", help="ADR directory path.")
    parser.add_argument("--register", default="adr/REGISTER.md", help="ADR register path.")
    parser.add_argument("--strict-titles", action="store_true", help="Fail on title mismatch.")
    parser.add_argument(
        "--require-symmetry",
        action="store_true",
        help="Fail when supersedence links are not mirrored in both directions.",
    )
    parser.add_argument("--fail-on-warnings", action="store_true", help="Return non-zero when warnings are present.")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    errors, warnings = check_consistency(
        adr_dir=Path(args.adr_dir),
        register_path=Path(args.register),
        strict_titles=bool(args.strict_titles),
        require_symmetry=bool(args.require_symmetry),
    )
    if errors:
        print("ADR consistency check: FAILED")
        for item in errors:
            print(f"ERROR {item}")
    else:
        print("ADR consistency check: OK")
    for item in warnings:
        print(f"WARN  {item}")
    print(
        f"Summary: errors={len(errors)} warnings={len(warnings)} "
        f"strict_titles={'on' if args.strict_titles else 'off'} "
        f"require_symmetry={'on' if args.require_symmetry else 'off'}"
    )
    if errors:
        return 1
    if warnings and args.fail_on_warnings:
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
