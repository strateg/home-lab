# Changelog

All notable changes to this project are documented in this file.

## [Unreleased]

### Added

- Security workflow with CodeQL scanning.
- Blocking secret-scan job in Python CI.
- Repository boundary hygiene validator for changed files.
- Governance baseline files: `SECURITY.md`, `CONTRIBUTING.md`, `.github/CODEOWNERS`, `.github/dependabot.yml`.

### Changed

- CI security posture: dependency audit is now blocking (no bypass).
- Protected branches (`main`/`master`) now require secret-inject validation path.
- Python tooling baseline aligned to 3.13 across workflows and local toolchain marker.
- Toolchain container updated to Python 3.13.
- Coverage gate added for repository CI coverage task (`--cov-fail-under=75`).
- License model changed to proprietary with explicit author permission requirement.
