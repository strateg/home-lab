# Universal AI Agent Rulebook

**Status:** Initial v1 for ADR 0096  
**Audience:** Claude Code, Codex, GitHub Copilot, Cursor-like agents, future MCP/resource-based agents  
**Purpose:** Compact ADR-derived rule layer for low-token, repeatable project development

---

## How To Use

1. Load this file before making code, topology, task, deploy, or ADR changes.
2. Use `docs/ai/ADR-RULE-MAP.yaml` to select scoped rule packs.
3. Read full ADRs only when the compact rules are ambiguous or the change alters architecture.
4. Treat ADRs as final authority when a rule conflicts with an ADR.

---

## Always-Load Rules

| Rule | Trigger | Must | Never | Validate | Source |
|---|---|---|---|---|---|
| CORE-001 | Any repository change | Work in active root layout: `topology/`, `topology-tools/`, `projects/`, `tests/`, `scripts/`, `taskfiles/` | Do not create root `v4/` or `v5/`; do not modify `archive/v4/` unless explicitly requested | `task validate:workspace-layout` | ADR0075, ADR0080, ADR0086 |
| CORE-002 | Any generated output request | Modify sources, then regenerate | Do not edit `generated/` by hand | `task validate:default` or relevant generator test | ADR0074, ADR0075, ADR0080 |
| CORE-003 | Any topology/model change | Preserve `Class -> Object -> Instance` source-of-truth model | Do not bypass topology with generated/manual artifacts | `task validate:default` | ADR0062, ADR0071, ADR0088 |
| CORE-004 | Any plugin/runtime change | Preserve stage affinity and manifest contracts | Do not add hidden plugin coupling outside `depends_on`, `consumes`, `produces` | `task validate:plugin-manifests`, `task test:plugin-contract` | ADR0063, ADR0065, ADR0080, ADR0086 |
| CORE-005 | Any framework/runtime change | Refresh and verify `framework.lock` when framework integrity changes | Do not leave strict lock stale | `task framework:lock-refresh`, `task framework:strict` | ADR0076, ADR0081 |
| CORE-006 | Any secrets-sensitive change | Keep secrets encrypted and resolved only through approved SOPS/age and bundle injection paths | Do not commit plaintext secrets | `task validate:default`, relevant secrets tests | ADR0072, ADR0073, ADR0085 |
| CORE-007 | Any architectural change | Add or update ADR/register/analysis artifacts | Do not treat architecture changes as complete without ADR governance | `task validate:adr-consistency` | ADR policy, ADR0080 |
| CORE-008 | Any substantial code change | Run targeted tests plus the narrowest relevant task gate; run `task ci` before integration-level closure when feasible | Do not claim validation without command evidence | targeted pytest, `task ci` | ADR0066, ADR0077 |
| CORE-009 | Any AI-assisted commit | Include commit metadata: `AI-Agent: <agent_name>` and `AI-Tokens: <tokens_used_for_commit_work>` | Do not finalize AI-assisted commits without both metadata fields | `git log -1 --pretty=%B` | ADR0096 |

---

## Scoped Rule Packs

| Domain | Load When | Rule Pack |
|---|---|---|
| Plugin runtime | `topology-tools/plugins/**`, `topology/**/plugins.yaml`, `plugin_manifest*`, kernel contracts | `docs/ai/rules/plugin-runtime.md` |
| Topology model | `topology/**`, `projects/*/topology/**`, class/object/instance files | `docs/ai/rules/topology-model.md` |
| Deploy domain | `scripts/orchestration/deploy/**`, `taskfiles/deploy.yml`, bundle/runner/init-node changes | `docs/ai/rules/deploy-domain.md` |
| Generator artifacts | generators, projections, templates, `generated/` behavior | `docs/ai/rules/generator-artifacts.md` |
| Secrets | `projects/*/secrets/**`, secret annotations, bundle injection, tfvars generation | `docs/ai/rules/secrets.md` |
| ADR governance | `adr/**`, `docs/ai/**`, architecture plans | `docs/ai/rules/adr-governance.md` |
| Testing/CI | `tests/**`, `taskfiles/**`, `.github/workflows/**` | `docs/ai/rules/testing-ci.md` |
| Acceptance TUC | `acceptance-testing/**`, `tests/plugin_integration/test_tuc*.py`, `taskfiles/acceptance.yml` | `docs/ai/rules/acceptance-tuc.md` |

---

## Decision Heuristics

### Adding A Plugin

1. Load `plugin-runtime.md`.
2. Place implementation in the correct stage family.
3. Register manifest entry with explicit stage, order, `depends_on`, `consumes`, and `produces`.
4. Add contract and integration tests.
5. Run plugin manifest and relevant plugin tests.

### Changing Topology

1. Load `topology-model.md`.
2. Edit source topology/class/object/project instance files only.
3. Preserve canonical semantic keys and layer boundaries.
4. Regenerate/validate via `task validate:default`.

### Changing Deploy Flow

1. Load `deploy-domain.md`.
2. Keep immutable bundle and runner workspace boundaries.
3. Use `--bundle` based entrypoints for execution flows.
4. Add runner/bundle workflow tests.

### Changing Generated Artifacts

1. Load `generator-artifacts.md`.
2. Change generator/projection/template sources, not `generated/`.
3. Update golden snapshots only when the stable projection/output contract intentionally changes.
4. Run targeted generator tests and syntax validation where applicable.

### Changing ADR/Rules

1. Load `adr-governance.md`.
2. Update ADR file, `adr/REGISTER.md`, and relevant analysis/index docs.
3. If changing rulebook semantics, update `docs/ai/ADR-RULE-MAP.yaml` and scoped rule packs.
4. Run ADR consistency validation.

### Adding Or Updating A TUC

1. Load `acceptance-tuc.md`.
2. Use `acceptance-testing/TUC-TEMPLATE/` as the baseline.
3. Keep all use-case contract, plan, matrix, evidence, quality gate, and logs inside the TUC folder.
4. Add or update `tests/plugin_integration/test_tuc*.py` for executable regression coverage.
5. Run the specific quality gate, TUC tests, and compile evidence task when the TUC requires compiled artifacts.
