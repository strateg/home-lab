# ADR 0118/0119 revision evidence — 2026-09-10

## Scope

WSL NixOS repository: `/home/nixos/workspaces/home-lab`.
Base HEAD: `ce8018754db0bd28d67568a8f7fb755236c9d8a9`.

This change rewrites proposed architecture and its supporting governance only.
No topology, compiler, generator, deploy code, secret, framework lock or live
device configuration was changed. Build diagnostics produced by validation are
not source-of-truth edits. This evidence snapshot preceded the version-freeze
commit requested later by the user. No deployment was performed.

The pre-existing untracked joint review
`docs/reports/2026-09-09-adr0118-0119-joint-security-mathematics-review.md`
was retained with Markdown hard-break whitespace normalized (content unchanged).
It is included with the version-freeze commit as
historical evidence so the ADR links remain resolvable. Its old test counts
are not results of this revision.

## Executed checks

| Command / check | Result |
|---|---|
| `task validate:adr-consistency` | PASS; 0 errors, 0 warnings, strict titles |
| `task validate:agent-rules` | PASS; 0 errors/warnings; layer table matches source |
| `task validate:agent-rules-strict` | PASS; 20 rules, 12 registered packs |
| `task validate:layers` | PASS; 62 classes, 140 objects, 189 instances, 29 runtime edges |
| `task validate:workspace-layout` | PASS |
| `task framework:verify-lock` | PASS; no lock refresh required for this documentation change |
| `.venv/bin/python -m pytest tests/test_validate_agent_rules.py tests/test_agent_instruction_sync.py tests/test_agent_rule_map_schema_policy.py -q` | PASS; 9 tests, Python 3.14.3 |
| Local Markdown links, fences and proposed YAML fragment syntax | PASS; 10 Markdown files checked, 23 local links resolved, 2 YAML fragments parsed; not validation against an implemented topology schema |
| `git diff --check` | PASS |

Existing targeted pytest entrypoints were used directly because the available
Task test targets run whole plugin suites, not these three governance files.

## Not run / not established

- Full `task ci` and whole-project compile: not run for documentation-only scope.
- New strict-profile compiler or reference interpreter tests: not implemented.
- Backend differential/property tests, live packet tests, fault injection and
  deployment/read-back: not run.
- Address/lease migration, new policy approval and runtime remediation: not done.
- Product/version-specific STIG checklist and DoD compliance assessment: not done.
- Independent human acceptance of the proposed architecture: pending.

Therefore A01-A20 and G1-G8 remain unclosed; the checks above establish only
documentation/governance consistency and unchanged layer/lock validation.

## Review handoff

1. Review ADR 0118 D4 policy binding/profile semantics and ADR 0119 D6 transitions.
2. Approve or revise the bounded threat model, mandatory properties and availability
   objectives; assign the assurance roles.
3. Start G1-G4 with a single backend pilot before changing project instances.
4. Record subsequent executable evidence under the TUC workflow, with plan,
   source/backend versions and explicit scope.
