# ADR 0045: Improvements to project model, development workflow and automation

- Status: Proposed
- Date: 2026-02-25

## Context

The `home-lab` project has a mature architecture (topology-as-data, layered generators and validators) but several operational gaps were found during recent repository scans (2026-02-24 / 2026-02-25):

- `pyproject.toml` exists and declares runtime + dev dependencies, but automated dependency security scanning is not configured.
- Unit tests exist for validators, but coverage for codegen/generators and top-level scripts is incomplete.
- CI provides topology validation and fixture matrix (`topology-matrix.yml`) but lacks dedicated code-quality and coverage workflows.
- Type hints are present partially; mypy is listed in dev extras but not enforced in CI.

Constraints and forces:

- Keep backward compatibility of generated outputs (`generated/`) — CI must ensure outputs do not drift unintentionally.
- Low friction for contributors — development setup should be reproducible in < 15 minutes.
- Security and supply-chain concerns: dependencies must be monitored and remediated.

## Decision

1. CI and workflows
   - Add a dedicated GitHub Actions workflow `python-checks.yml` with jobs:
     - `lint`: run `black --check`, `isort --check-only`, `pylint` (or `ruff`) and `yamllint` on relevant directories.
     - `typecheck`: run `mypy --config-file pyproject.toml` against `topology-tools` and `scripts` packages.
     - `test`: run `pytest tests/ --cov=topology-tools --cov-report=xml` and upload coverage to Codecov or store as artifact.
     - `dependency-scan` (scheduled): run `pip-audit` and fail on high severity findings; open Dependabot/renovate for upgrade PRs.

2. Tests and coverage
   - Expand test suite with `tests/unit/generators/` and `tests/integration/`.
   - Maintain fixtures in `tests/fixtures/` and ensure `topology-tools/run-fixture-matrix.py` is reproducible locally.
   - Add coverage thresholds (e.g., 40% for now, raised over time) in CI to fail builds below threshold.

3. Type system
   - Introduce `topology-tools/types.py` with `TypedDict` and dataclass definitions for L0–L7 major structures.
   - Adopt `mypy` strictness profile incrementally. Enforce `mypy` in CI with baseline-ignore for legacy third-party imports.

4. Developer experience
   - Add `DEVELOPER_SETUP.md` updates and `docs/QUICKSTART.md` describing `pip install -e .[dev]`, running tests, running `regenerate-all.py` and debug tips.
   - Provide a Dockerfile / docker-compose for reproducible environment (optional, low priority).

5. Observability and logging
   - Standardize logging: use structured logging with file+console handlers for `regenerate-all.py` and key generators. Logs stored under `.logs/` with rotation.

6. ADR and documentation
   - Register this ADR (0045) and update `docs/github_analysis` with an actionable checklist and milestones.

## Consequences

Positive:
- Stronger CI gating reduces regressions and increases code quality.
- Better developer onboarding and repeatable environments.
- Faster detection and automated remediation of vulnerable dependencies.

Trade-offs / Risks:
- More CI runtime and maintenance cost (workflows to keep updated).
- Additional developer overhead to satisfy linters/mypy — may require incremental adoption to avoid churn.

Migration / compatibility
- Start with non-blocking `mypy` and `pylint` runs (warnings only). After initial fixes, promote to blocking checks.
- Add coverage gates incrementally: set low thresholds then raise them over months.

## Implementation plan (short)

Week 1:
- Add `.github/workflows/python-checks.yml` (lint, typecheck), and `tests/integration/` skeleton.
- Update `DEVELOPER_SETUP.md` with `pip install -e .[dev]` and `pytest` examples.

Week 2–4:
- Expand tests for generators and critical scripts.
- Integrate `mypy` fixes and enable CI enforcement progressively.
- Add scheduled `dependency-scan` job.

Week 5–8:
- Harden coverage thresholds and enable blocking lint/type checks.
- Optionally publish developer Docker image and add QUICKSTART docs.

## References

- pyproject.toml
- tests/unit/validators/test_storage.py
- .github/workflows/topology-matrix.yml
- docs/github_analysis/PROJECT_ANALYSIS.md

***

Registered-by: automatic analysis updater
