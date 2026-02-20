# ADR 0010: Add Mermaid Render Quality Gate to Regeneration Pipeline

- Status: Accepted
- Date: 2026-02-20

## Context

Diagram generation now defaults to Mermaid icon-node output and relies on runtime icon pack support.
Even when docs are generated successfully, regressions can still appear at render time (for example parser/runtime mismatches).

The existing regeneration flow did not enforce Mermaid render validation as a first-class quality gate.
Also, cross-platform checkouts may convert shell scripts to CRLF and break Bash execution.

## Decision

1. Extend `topology-tools/regenerate-all.py` with an explicit Mermaid render validation step after documentation generation.
2. Make Mermaid validation enabled by default in regeneration workflow, with opt-out via `--skip-mermaid-validate`.
3. Add `--mermaid-icon-mode` option to control validation mode (`auto`, `icon-nodes`, `compat`, `none`).
4. Update `topology-tools/test-regeneration.sh`:
   - fix project root detection;
   - add Mermaid render validation test;
   - include docs regeneration in idempotency check.
5. Enforce LF for shell scripts via `.gitattributes` (`*.sh text eol=lf`) to avoid Bash syntax failures on Windows checkouts.

## Consequences

Benefits:

- Rendering errors are detected in the standard regeneration path, not only during manual review.
- CI/local workflows are more deterministic across icon modes.
- Shell-based validation scripts remain runnable in mixed Windows/Linux environments.

Trade-offs:

- Regeneration now takes additional time due to Mermaid CLI validation.
- Workstations/CI need Node tooling (`npx`/`npm`) for full render checks.

## References

- Files:
  - `topology-tools/regenerate-all.py`
  - `topology-tools/test-regeneration.sh`
  - `topology-tools/README.md`
  - `topology-tools/GENERATORS-README.md`
  - `.gitattributes`
