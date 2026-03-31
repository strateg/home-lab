# ADR 0085: Implementation Plan

**Priority note:** This is the primary deploy-domain implementation track.
ADR 0084 follows it, and ADR 0083 is an optional later consumer.

**Sequencing:** ADR 0085 first → ADR 0084 second → ADR 0083 later (if justified).

---

## Phase 1: Deploy Bundle Contract Definition

**Goal:** Establish the canonical deploy bundle layout, project deploy profile, and mutable deploy-state root so that ADR 0084 runner evolution has a stable input boundary.

### Tasks

| ID | Task | Output | Acceptance Criteria |
|----|------|--------|---------------------|
| 1.1 | Define deploy bundle directory layout | `docs/contracts/DEPLOY-BUNDLE.md` | Layout documented: `manifest.yaml`, `artifacts/<node_id>/`, `metadata.yaml` |
| 1.2 | Define `manifest.yaml` schema | `schemas/deploy-bundle-manifest.schema.json` | JSON Schema validates a sample manifest |
| 1.3 | Define `metadata.yaml` schema | `schemas/deploy-bundle-metadata.schema.json` | Provenance, bundle hash, source refs |
| 1.4 | Define project deploy profile shape | `schemas/deploy-profile.schema.json` | Runner selection, backend config, staging policy, toolchain expectations |
| 1.5 | Define mutable deploy-state root layout | `docs/contracts/DEPLOY-STATE.md` | Documented: `.work/deploy-state/<project>/nodes/`, `.work/deploy-state/<project>/logs/` |
| 1.6 | Create sample deploy profile | `projects/home-lab/deploy/deploy-profile.yaml` | Validates against 1.4 schema |
| 1.7 | Align ADR 0083 terminology | ADR 0083 edits | All references to `.work/native/bootstrap/` replaced with deploy-state root |
| 1.8 | Align ADR 0084 terminology | ADR 0084 edits | Runner contract references bundle/workspace model consistently |

### Test Matrix (Phase 1)

| Test ID | Description | Category |
|---------|-------------|----------|
| T-B01 | `manifest.yaml` sample validates against schema | Unit |
| T-B02 | `metadata.yaml` sample validates against schema | Unit |
| T-B03 | `deploy-profile.yaml` validates against schema | Unit |
| T-B04 | Bundle directory structure matches documented layout | Unit |
| T-B05 | Bundle ID is deterministic for fixed inputs | Unit |
| T-B06 | Deploy-state directory layout matches documented contract | Unit |

### Gate

- [ ] Deploy bundle layout documented
- [ ] Manifest and metadata schemas created and validated
- [ ] Deploy profile schema created and sample validates
- [ ] Deploy-state root layout documented
- [ ] ADR 0083 and 0084 aligned to ADR 0085 terminology
- [ ] Phase 1 tests pass

---

## Phase 2: Bundle Assembly Pipeline

**Goal:** Implement the assemble/build step that produces an immutable deploy bundle from generated artifacts + secrets.

### Tasks

| ID | Task | Output | Acceptance Criteria |
|----|------|--------|---------------------|
| 2.1 | Create bundle assembly entry point | `scripts/orchestration/deploy/assemble-bundle.py` | CLI produces bundle from generated + secrets |
| 2.2 | Implement `manifest.yaml` emission | Part of 2.1 | Manifest derived from generated manifests + deploy profile |
| 2.3 | Implement `metadata.yaml` emission | Part of 2.1 | Provenance hash, timestamp, source refs |
| 2.4 | Secret join point implementation | Part of 2.1 | SOPS decrypt → inject into bundle artifacts |
| 2.5 | Bundle immutability enforcement | Part of 2.1 | Assembled bundle is read-only after creation |
| 2.6 | Framework lock verification gate | Part of 2.1 | ADR 0075/0076 lock check runs before assembly |

### Test Matrix (Phase 2)

| Test ID | Description | Category |
|---------|-------------|----------|
| T-B10 | Assembly produces valid bundle from sample generated tree | Integration |
| T-B11 | Assembly fails if framework lock verification fails | Integration |
| T-B12 | Assembled bundle contains no unencrypted secrets outside artifacts/ | Security |
| T-B13 | Bundle metadata hash is deterministic for fixed inputs | Unit |
| T-B14 | Assembly rejects re-assembly into existing bundle (immutability) | Unit |
| T-B15 | generated/ tree remains secret-free after assembly | Security |

### Gate

- [ ] `assemble-bundle.py` produces valid bundles
- [ ] Secret injection works with SOPS+age (ADR 0072)
- [ ] Framework lock verification blocks assembly when lock fails
- [ ] Phase 2 tests pass

---

## Phase 3: Runner Evolution (co-owned with ADR 0084)

**Goal:** Evolve `DeployRunner` contract from process-centric to workspace-aware execution that consumes deploy bundles.

This phase is jointly specified in `adr/0084-analysis/IMPLEMENTATION-PLAN.md` Phase 0a.
ADR 0085 defines the contract requirements; ADR 0084 implements the runner code.

### ADR 0085 Requirements for Runner Contract

| Requirement | Source Decision |
|-------------|-----------------|
| Runner MUST stage deploy bundle into backend workspace | D5 |
| Runner MUST execute commands inside staged workspace | D5 |
| Runner MUST report backend capabilities | D9 |
| Runner MUST clean up temporary workspaces | D5 |
| Runner staging MUST NOT depend on framework sources at execution time | D5 |
| Runner MUST consume project-scoped bundle/workspace boundary | D5 |

### Gate

- [ ] Runner contract implements all D5/D9 requirements
- [ ] Runner contract tests pass (see ADR 0084 test matrix T-R01–T-R12)
- [ ] At least `NativeRunner` and `WSLRunner` implement new contract

---

## Phase 4: Deploy Tooling Integration

**Goal:** Update deploy-domain entry points to consume explicit `bundle_id` inputs.

### Tasks

| ID | Task | Output | Acceptance Criteria |
|----|------|--------|---------------------|
| 4.1 | Update `init-node.py` design | Updated ADR 0083 D6 | Requires `--bundle <bundle_id>` |
| 4.2 | Move runtime state to deploy-state root | Code changes | State lives in `.work/deploy-state/<project>/` |
| 4.3 | Update logging/audit flow | Code changes | Bundle identifier included in all audit records |
| 4.4 | Prepare Terraform entry point | `scripts/orchestration/deploy/apply-terraform.py` | Consumes `--bundle <bundle_id>` |
| 4.5 | Prepare Ansible entry point | `scripts/orchestration/deploy/run-ansible.py` | Consumes `--bundle <bundle_id>` |
| 4.6 | Remove legacy `.work/native/` execution assumptions | Code + ADR edits | No active code references `.work/native/` as architectural contract |

### Test Matrix (Phase 4)

| Test ID | Description | Category |
|---------|-------------|----------|
| T-B20 | `init-node.py --bundle <id>` resolves bundle correctly | Integration |
| T-B21 | Deploy entry points reject missing `--bundle` argument | Unit |
| T-B22 | Runtime state written to `.work/deploy-state/<project>/` | Integration |
| T-B23 | Audit log entries include bundle_id | Unit |
| T-B24 | Legacy `.work/native/` paths are not referenced in active code | Static analysis |

### Gate

- [ ] Deploy entry points require explicit bundle selection
- [ ] Runtime state lives in deploy-state root, not `.work/native/`
- [ ] Audit logging includes bundle provenance
- [ ] Phase 4 tests pass
- [ ] No active deploy ADR references `.work/native/` as execution contract

---

## Cross-Phase Dependencies

```
Phase 1: Contract Definition
    │
    ├──► Phase 2: Bundle Assembly (needs schemas from Phase 1)
    │
    └──► Phase 3: Runner Evolution (needs bundle layout from Phase 1)
              │
              └──► Phase 4: Deploy Tooling (needs runner + bundle from Phase 2+3)
```

ADR 0084 Phase 0a runs in parallel with ADR 0085 Phase 3.
ADR 0083 implementation is deferred until Phases 1–4 are complete.

---

## Acceptance Criteria (Overall)

- Deploy bundle layout is documented, schema-validated, and stable
- Bundle assembly produces immutable bundles with secret injection
- Runner contract is explicitly workspace-aware (co-owned with ADR 0084)
- All deploy entry points consume `--bundle <bundle_id>`
- Mutable runtime state lives in `.work/deploy-state/<project>/`
- ADR 0083 and ADR 0084 are terminologically consistent with ADR 0085
- No deploy ADR references `.work/native/...` as the architectural execution contract
- All test matrices pass
