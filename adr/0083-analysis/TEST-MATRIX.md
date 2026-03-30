# ADR 0083: Test and Evidence Matrix

## Purpose

Define which checks can be CI-mocked vs require hardware. Establish release-blocking criteria per mechanism.

---

## Test Categories

| Category | Execution Environment | Blocks Release? |
|----------|----------------------|-----------------|
| Unit | CI (pytest) | Yes |
| Schema | CI (jsonschema) | Yes |
| Integration (mock) | CI (pytest + fixtures) | Yes |
| Integration (hardware) | Lab hardware | Yes (for validated mechanisms) |
| Smoke | Lab hardware | No (advisory) |

---

## 1. Schema and Validation Tests

| Test ID | Description | Category | Mock/HW | Blocks? |
|---------|-------------|----------|---------|---------|
| T-S01 | `initialization-contract.schema.json` meta-validation | Schema | Mock | Yes |
| T-S02 | Valid MikroTik contract passes schema | Schema | Mock | Yes |
| T-S03 | Valid Proxmox contract passes schema | Schema | Mock | Yes |
| T-S04 | Valid Orange Pi contract passes schema | Schema | Mock | Yes |
| T-S05 | Valid ansible_bootstrap contract passes schema | Schema | Mock | Yes |
| T-S06 | Missing `mechanism` fails schema | Schema | Mock | Yes |
| T-S07 | Missing `bootstrap.template` for netinstall fails | Schema | Mock | Yes |
| T-S08 | `unattended_install` without `post_install` fails schema | Schema | Mock | Yes |
| T-S09 | `cloud_init` without `outputs` (user-data + meta-data) fails schema | Schema | Mock | Yes |
| T-S10 | Unknown mechanism fails schema | Schema | Mock | Yes |
| T-S11 | Requirements structured object validation | Schema | Mock | Yes |
| T-S12 | Handover retry config validation | Schema | Mock | Yes |
| T-S13 | post_handover informational fields accepted | Schema | Mock | Yes |
| T-S14 | Version pattern validation (semver-like) | Schema | Mock | Yes |
| T-S15 | Object without initialization_contract is valid (implicit terraform-managed) | Schema | Mock | Yes |

---

## 2. Validator Plugin Tests

| Test ID | Description | Category | Mock/HW | Blocks? |
|---------|-------------|----------|---------|---------|
| T-V01 | `base.validator.initialization_contract` loads | Unit | Mock | Yes |
| T-V02 | Validator produces E9700 for missing contract on compute object | Unit | Mock | Yes |
| T-V03 | Validator produces E9701 for invalid mechanism | Unit | Mock | Yes |
| T-V04 | Validator produces E9702 for missing template | Unit | Mock | Yes |
| T-V05 | Validator produces E9703 for unknown check type | Unit | Mock | Yes |
| T-V06 | Validator produces E9705 for ownership overlap | Unit | Mock | Yes |
| T-V07 | Validator skips objects without compute/router class_ref | Unit | Mock | Yes |
| T-V08 | Validator accepts optional contract (MAY semantics) | Unit | Mock | Yes |

---

## 3. Generator Tests

| Test ID | Description | Category | Mock/HW | Blocks? |
|---------|-------------|----------|---------|---------|
| T-G01 | MikroTik bootstrap generator reads contract | Integration | Mock | Yes |
| T-G02 | MikroTik bootstrap produces init-terraform.rsc | Integration | Mock | Yes |
| T-G03 | Proxmox bootstrap produces answer.toml | Integration | Mock | Yes |
| T-G04 | Proxmox bootstrap produces post-install-minimal.sh (< 50 lines) | Integration | Mock | Yes |
| T-G05 | Orange Pi bootstrap produces user-data + meta-data | Integration | Mock | Yes |
| T-G06 | LXC terraform_managed produces no bootstrap artifacts | Integration | Mock | Yes |
| T-G07 | Manifest generator produces INITIALIZATION-MANIFEST.yaml | Integration | Mock | Yes |
| T-G08 | Manifest contains all nodes with contracts | Integration | Mock | Yes |
| T-G09 | Manifest requirements use structured objects | Integration | Mock | Yes |
| T-G10 | Generated artifacts are deterministic (stable output) | Integration | Mock | Yes |
| T-G11 | Generated artifacts contain no secret values | Integration | Mock | Yes |
| T-G12 | Bootstrap generator respects projection-first (ADR 0074) | Integration | Mock | Yes |

---

## 4. Assembler Tests

| Test ID | Description | Category | Mock/HW | Blocks? |
|---------|-------------|----------|---------|---------|
| T-A01 | `base.assembler.bootstrap_secrets` loads | Unit | Mock | Yes |
| T-A02 | Assembler consumes manifest data from data bus | Integration | Mock | Yes |
| T-A03 | Assembler renders secrets into .work/native/ | Integration | Mock | Yes |
| T-A04 | Assembler skips terraform_managed nodes | Integration | Mock | Yes |
| T-A05 | Assembler verify detects secrets leaked into generated/ | Integration | Mock | Yes |
| T-A06 | Assembled artifacts contain resolved secret values | Integration | Mock | Yes |
| T-A07 | SOPS decryption failure produces clear error | Integration | Mock | Yes |

---

## 5. Orchestrator Tests (init-node.py)

| Test ID | Description | Category | Mock/HW | Blocks? |
|---------|-------------|----------|---------|---------|
| T-O01 | `init-node.py --help` exits cleanly | Unit | Mock | Yes |
| T-O02 | `--node` reads manifest and finds node | Integration | Mock | Yes |
| T-O03 | `--all-pending` filters by state file | Integration | Mock | Yes |
| T-O04 | `--verify-only` runs handover checks only | Integration | Mock | Yes |
| T-O05 | `--force` transitions from verified to bootstrapping | Integration | Mock | Yes |
| T-O06 | State file created in .work/native/bootstrap/ | Integration | Mock | Yes |
| T-O07 | State transitions follow legal state machine | Unit | Mock | Yes |
| T-O08 | Illegal state transition raises error | Unit | Mock | Yes |
| T-O09 | Prerequisites check failure blocks bootstrap | Integration | Mock | Yes |
| T-O10 | Handover retry with backoff works correctly | Integration | Mock | Yes |
| T-O11 | Timeout exceeded transitions to failed | Integration | Mock | Yes |
| T-O12 | State file uses atomic writes | Unit | Mock | Yes |
| T-O13 | Stale artifact warning (>24h) triggers | Integration | Mock | Yes |
| T-O14 | `--import` creates state with `imported: true` | Integration | Mock | Yes |
| T-O15 | `--reset` requires `--confirm-reset` flag | Unit | Mock | Yes |
| T-O16 | `--reset` warns if Terraform state exists | Integration | Mock | Yes |
| T-O17 | Contract drift detection compares hashes | Unit | Mock | Yes |
| T-O18 | `--acknowledge-drift` updates hash without re-bootstrap | Integration | Mock | Yes |
| T-O19 | Adapter loaded via factory matches mechanism | Unit | Mock | Yes |
| T-O20 | Unknown mechanism in factory raises ValueError | Unit | Mock | Yes |
| T-O21 | Adapter ABC enforces all abstract methods | Unit | Mock | Yes |
| T-O22 | Adapter cleanup() is no-op by default | Unit | Mock | Yes |
| T-O23 | Adapter validate_template() returns True by default | Unit | Mock | Yes |

---

## 5a. Adapter Contract Tests (D19)

| Test ID | Description | Category | Mock/HW | Blocks? |
|---------|-------------|----------|---------|---------|
| T-A19-01 | PreflightCheck remediation_hint populated on failure | Unit | Mock | Yes |
| T-A19-02 | BootstrapResult.is_success() matches AdapterStatus.SUCCESS | Unit | Mock | Yes |
| T-A19-03 | Adapter returns BootstrapResult on failure (no exception) | Unit | Mock | Yes |
| T-A19-04 | HandoverCheckResult tracks attempt/total_attempts | Unit | Mock | Yes |
| T-A19-05 | Orchestrator transitions state based on adapter return, not adapter mutation | Integration | Mock | Yes |

---

## 5b. Logging and Observability Tests (D20)

| Test ID | Description | Category | Mock/HW | Blocks? |
|---------|-------------|----------|---------|---------|
| T-L01 | Console output includes timestamp, level, node_id | Unit | Mock | Yes |
| T-L02 | JSONL file written to .work/native/bootstrap/ | Integration | Mock | Yes |
| T-L03 | Each JSONL line is valid JSON with mandatory fields | Unit | Mock | Yes |
| T-L04 | Destructive operation emits WARN-level audit event | Unit | Mock | Yes |
| T-L05 | State transition logged with from/to states | Unit | Mock | Yes |
| T-L06 | Error events include error_code (E97xx) | Unit | Mock | Yes |
| T-L07 | Log file survives adapter failure (not corrupted) | Integration | Mock | Yes |

---

## 6. Pre-Validation Tests (D16)

| Test ID | Description | Category | Mock/HW | Blocks? |
|---------|-------------|----------|---------|---------|
| T-P01 | Proxmox answer.toml TOML syntax validation | Unit | Mock | Yes |
| T-P02 | Proxmox answer.toml missing [global] produces E9710 | Unit | Mock | Yes |
| T-P03 | Proxmox answer.toml missing [network] produces E9711 | Unit | Mock | Yes |
| T-P04 | Proxmox answer.toml missing [disk-setup] produces E9712 | Unit | Mock | Yes |
| T-P05 | Proxmox answer.toml invalid disk path produces E9713 | Unit | Mock | Yes |
| T-P06 | Proxmox answer.toml network mismatch produces W9714 | Unit | Mock | Yes |
| T-P07 | Destructive mechanism requires `--confirm-destructive` | Integration | Mock | Yes |
| T-P08 | cloud-init user-data YAML validation | Unit | Mock | Yes |

---

## 7. Handover Verification Tests

| Test ID | Description | Category | Mock/HW | Blocks? |
|---------|-------------|----------|---------|---------|
| T-H01 | `api_reachable` check with mock HTTP server | Integration | Mock | Yes |
| T-H02 | `ssh_reachable` check with mock SSH | Integration | Mock | Yes |
| T-H03 | `credential_valid` check with mock API | Integration | Mock | Yes |
| T-H04 | `python_installed` check with mock SSH | Integration | Mock | Yes |
| T-H05 | `terraform_plan_succeeds` check with mock terraform | Integration | Mock | Yes |
| T-H06 | Check timeout handling | Integration | Mock | Yes |
| T-H07 | Retry backoff timing (linear) | Unit | Mock | Yes |
| T-H08 | Retry backoff timing (exponential) | Unit | Mock | Yes |

---

## 7. Hardware E2E Tests

| Test ID | Description | Category | Device | Blocks? | Gate |
|---------|-------------|----------|--------|---------|------|
| T-E01 | MikroTik full netinstall + handover | Hardware | MikroTik Chateau | Yes | Release gate |
| T-E02 | MikroTik Terraform plan after handover | Hardware | MikroTik Chateau | Yes | Release gate |
| T-E03 | Proxmox answer.toml validation | Hardware | Dell XPS (if possible) | No | Advisory |
| T-E04 | Orange Pi cloud-init boot | Hardware | Orange Pi 5 | No | Advisory |
| T-E05 | LXC container creation via Terraform | Hardware | Proxmox + LXC | No | Advisory |
| T-E06 | Full pipeline: generate + assemble + init-node | Hardware | Any device | Yes | Release gate |

**Note:** Hardware E2E tests T-E01 and T-E06 are release-blocking. Proxmox and Orange Pi E2E tests are advisory because re-installation is destructive and time-consuming.

---

## Release Gate Summary

| Gate | Criteria | Evidence |
|------|----------|----------|
| Schema gate | All T-S* tests pass | CI green |
| Validator gate | All T-V* tests pass | CI green |
| Generator gate | All T-G* tests pass, artifacts deterministic | CI green |
| Assembler gate | All T-A* tests pass, no secret leaks | CI green |
| Orchestrator gate | All T-O* tests pass | CI green |
| Handover gate | All T-H* tests pass | CI green |
| Hardware gate | T-E01 + T-E06 pass | Manual test report |
| Documentation gate | NODE-INITIALIZATION.md reviewed | Review approval |

---

## CI Test Configuration

```yaml
# pytest markers for test categorization
markers:
  schema: Schema validation tests
  validator: Validator plugin tests
  generator: Generator plugin tests
  assembler: Assembler plugin tests
  orchestrator: Orchestrator (init-node.py) tests
  handover: Handover verification tests
  hardware: Hardware E2E tests (skip in CI)

# Run in CI
# python -m pytest tests/ -m "not hardware" -q

# Run hardware tests manually
# python -m pytest tests/ -m "hardware" -v --hardware-config=tests/hardware.yaml
```

---

## Test File Layout

```
tests/
  plugin_integration/
    test_initialization_contract_validator.py   # T-V01..T-V08
    test_bootstrap_generators.py                # T-G01..T-G12
    test_initialization_manifest_generator.py   # T-G07..T-G12
    test_bootstrap_secrets_assembler.py         # T-A01..T-A07
  orchestration/
    test_init_node.py                           # T-O01..T-O12
    test_handover_checks.py                     # T-H01..T-H08
    test_state_machine.py                       # T-O07..T-O08
  schemas/
    test_initialization_contract_schema.py      # T-S01..T-S14
  hardware/
    test_mikrotik_e2e.py                        # T-E01..T-E02
    test_proxmox_e2e.py                         # T-E03
    test_orangepi_e2e.py                        # T-E04
    test_lxc_e2e.py                             # T-E05
    test_full_pipeline_e2e.py                   # T-E06
```
