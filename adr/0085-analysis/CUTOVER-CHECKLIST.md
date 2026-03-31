# ADR 0085: Cutover Checklist

## Phase 1: Contract Definition

### ADR Alignment

- [ ] `adr/0085-deploy-bundle-and-runner-workspace-contract.md` approved
- [x] `adr/0083-unified-node-initialization-contract.md` aligned to deploy bundle model
- [x] `adr/0084-cross-platform-dev-plane-and-linux-deploy-plane.md` aligned to workspace-aware runner model
- [x] All three ADRs use consistent terminology (bundle, workspace, deploy-state root)
- [x] ADR 0083 no longer references `.work/native/bootstrap/` as state location
- [x] Sequencing (0085 → 0084 → 0083) is declared in all three ADRs

### Schema and Documentation

- [ ] `schemas/deploy-bundle-manifest.schema.json` created and validated
- [ ] `schemas/deploy-bundle-metadata.schema.json` created and validated
- [ ] `schemas/deploy-profile.schema.json` created and validated
- [ ] `docs/contracts/DEPLOY-BUNDLE.md` documents bundle layout
- [ ] `docs/contracts/DEPLOY-STATE.md` documents mutable state root
- [ ] Sample `projects/home-lab/deploy/deploy-profile.yaml` validates against schema

### Evidence

- [ ] A sample deploy bundle can be manually assembled and passes schema validation
- [ ] Phase 1 tests (T-B01–T-B06) pass

---

## Phase 2: Bundle Assembly

- [ ] `scripts/orchestration/deploy/assemble-bundle.py` produces valid bundles
- [ ] Secret injection via SOPS+age works end-to-end
- [ ] Framework lock verification gates assembly
- [ ] `generated/` remains secret-free after assembly
- [ ] Phase 2 tests (T-B10–T-B15) pass

---

## Phase 3: Runner Evolution (co-owned with ADR 0084)

- [ ] `DeployRunner` contract implements `stage_bundle()`, `run()`, `capabilities()`, `cleanup_workspace()`
- [ ] `NativeRunner` passes workspace-aware tests
- [ ] `WSLRunner` passes workspace-aware tests
- [ ] Runner capability negotiation validates required capabilities before execution
- [ ] ADR 0084 Phase 0a tests (T-R01–T-R12) pass

---

## Phase 4: Deploy Tooling Integration

- [ ] `init-node.py` requires `--bundle <bundle_id>`
- [ ] `apply-terraform.py` requires `--bundle <bundle_id>`
- [ ] `run-ansible.py` requires `--bundle <bundle_id>`
- [ ] Runtime state lives in `.work/deploy-state/<project>/`
- [ ] Audit log entries include `bundle_id`
- [ ] No active code references `.work/native/` as architectural execution contract
- [ ] Phase 4 tests (T-B20–T-B24) pass

---

## Documentation and Validation

- [ ] Operator docs clearly distinguish dev plane vs deploy plane
- [ ] Deploy runbooks describe bundle/workspace expectations
- [ ] Related ADR links resolve correctly
- [ ] ADR 0085 status can be promoted to Accepted

---

## Rollback Triggers

- Deploy bundle model cannot express required execution scenarios
- Bundle assembly creates secret leaks into tracked source trees
- Runner workspace staging breaks existing NativeRunner or WSLRunner functionality
- Bundle model forces ADR 0083 redesign beyond terminology alignment
