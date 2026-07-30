# ADR 0114 Analysis: Responsibility Zones (framework vs project)

- Status: Working analysis for ADR 0114 (Proposed)
- Date: 2026-07-30
- Scope: inventory of the current repository against the four planes defined in ADR 0114 §2,
  plus the open questions that must be answered before the physical repository split.

All statements below were verified against the tree at commit `59547602` (branch `development`).

---

## 1. Plane assignment map

| Artifact | Plane | Owner | Extension mechanism today | State |
|---|---|---|---|---|
| `topology-tools/kernel/**` (registry, scheduler, facade) | Toolchain | framework | none (closed runtime) | correct |
| 6-stage lifecycle, `STAGE_ORDER` | Toolchain | framework | plugins only | correct |
| TRE entrypoints (`compile-topology.py`, `generate-framework-lock.py`, `verify-framework-lock.py`, `assemble-ansible-runtime.py`, `check-capability-contract.py`) | Toolchain | framework | none | correct (ADR 0081 §2.3) |
| `topology/class-modules/**` (54 classes across L1–L7) | Library | framework | **single root** (`compile-topology.py:465,596,1088,1123`) | project cannot extend |
| `topology/object-modules/**` (136 yaml across 15 vendor/domain groups) | Library | framework | **single root** | project cannot extend |
| `object-modules/{proxmox,mikrotik,oracle,orangepi}/templates/**` | Library | framework | fallback to framework templates (`base_generator.py:90-107`, ADR 0078) | correct |
| `topology/layer-contract.yaml`, `semantic-keywords.yaml`, `profile-map.yaml`, `module-index.yaml`, `model.lock.yaml` | Library | framework | none | correct |
| `topology/product-profiles/**`, `topology/product-bundles/**` | Library | framework | **copied into project** (`bootstrap-project-repo.py:194`), absent from `distribution.include` | drift |
| `topology-tools/templates/**` (42 files: 20 docs, ansible, wireguard) | Extension defaults | framework | **single root** (`base_generator.py:61-121`) | no project layer |
| `topology-tools/plugins/**` (6 families + `manifests/`) | Extension | framework | chain `framework → project` (`plugin_manifest_discovery.py:191-251`) | works, unversioned |
| `topology-tools/schemas/`, `topology-tools/data/` (error catalog, policies) | Toolchain | framework | none | correct |
| `topology-tools/utils/**` (22 scripts: split, bootstrap, release, audit) | framework-dev only | framework | n/a | correct (ADR 0081 §2.3) |
| `projects/<id>/project.yaml`, `topology.yaml`, `framework.lock.yaml` | Project | project | n/a | correct |
| `projects/<id>/topology/instances/**` (151 instances) | Project | project | n/a | correct |
| `projects/<id>/secrets/**` (SOPS/age) | Project | project | n/a | correct |
| `projects/<id>/ansible/**` (roles with their own `templates/*.j2`, inventory-overrides, playbooks) | Project | project | n/a | correct |
| `projects/<id>/terraform/mikrotik`, `deploy/deploy-profile.yaml` | Project | project | n/a | correct |
| `generated/<id>/**`, `dist/<id>/**` | Project | project | regenerated | correct |
| `build/effective-topology.{json,yaml}` (IR) | Project output | project | — | **shared path, not project-qualified** |

## 2. Assets requiring per-item triage at split time

These are not resolvable by rule; each item needs an explicit owner decision.

### 2.1 `scripts/**` — 129 files

| Directory | Files | Likely plane | Note |
|---|---|---|---|
| `orchestration/` | 46 | Toolchain (dev + deploy plane) | contains `lane.py` (`validate-v5` entrypoint used by CLAUDE.md), `deploy/`, `mcp/`, `product/` |
| `validation/` | 31 | framework-dev | includes `check_adr_consistency.py`, `validate_plugin_manifests.py`, `validate_agent_rules.py` |
| `inspection/` | 19 | mixed | live-device inspection — generic adapters vs home-lab specifics |
| `secrets/` | 13 | mixed | SOPS/age tooling generic; key material and paths project-specific |
| `mikrotik/` | 5 | mixed | vendor adapters vs operations on specific devices |
| `terraform/` | 4 | mixed | |
| `wireguard/` | 2 | mixed | |
| `environment/`, `setup/` | 4 | framework-dev | dev environment bootstrap |
| `acceptance/`, `deploy/`, `docs/`, `maintenance/`, `model/` | 5 | framework-dev | |

### 2.2 Other unassigned assets

| Asset | Observation |
|---|---|
| `acceptance-testing/**` (TUC-0001…0004 + TEMPLATE) | The TUC *framework* is framework-owned (ADR 0070), but TUC evidence targets home-lab devices; `tests/plugin_integration/test_tuc*.py` couples framework CI to home-lab data |
| `configs/` | only 2 files: `quality/adr0088-governance-policy.yaml` (framework) and `services/adguardhome-config.yaml` (project) |
| `Заметки/` | working notes, patches, prompts — project/personal |
| `manuals/{dev,deploy,distribution}-plane/**` | dev + distribution plane are framework-owned; deploy plane documents operating a concrete network and splits |
| `archive/**`, `adr/**`, `docs/**`, `tests/**`, `taskfiles/**` | framework repository only (ADR 0081 §1.1) |
| `.claude/`, `.codex/`, `AGENTS.md`, `CLAUDE.md`, `docs/ai/**` | framework repository per ADR 0081 §1.1 — **but** the project repository needs its own agent instructions once AI development spans both repositories; currently unaddressed |

## 3. Verified findings behind ADR 0114

| # | Finding | Evidence |
|---|---|---|
| F1 | Templates have no project layer; a single `FileSystemLoader` root | `plugins/generators/base_generator.py:61-121` |
| F2 | Classes/objects have a single root each; project bootstrap points them at the mounted framework | `compile-topology.py:465,596,1088,1123`; `bootstrap-project-repo.py:228-244` |
| F3 | Product catalog is compile-time input resolved from `repo_root`, missing from the artifact, copied into projects | `compiler_plugin_context.py:82-83`; `topology/framework.yaml`; `bootstrap-project-repo.py:194`; `plugins/validators/soho_product_profile_validator.py` |
| F4 | Plugin chain is the only implemented uniform extension mechanism, and a boundary discoverer enforces it | `plugin_manifest_discovery.py:191-251`; `compile-topology.py:1125`; `plugins/discoverers/discover_boundary.py` |
| F5 | Capability gate machinery exists in the kernel (`capabilities`, `requires_capabilities`, `when`, E4010) with tests | `kernel/specs.py:63-67`; `kernel/scheduler/preflight.py:151-201`; `tests/kernel/scheduler/test_execute_stage_gates.py:64,76`; `tests/plugin_api/test_stage_executor_invariants.py:255` |
| F6 | Available capabilities are collected only from plugin declarations, so topology-derived capabilities cannot gate anything; no framework manifest declares `requires_capabilities` | `kernel/scheduler/preflight.py:166-174`; grep over `plugins/manifests/*.yaml` |
| F7 | A single IR already exists and all terminal generators depend on it | `plugins/manifests/compilers.yaml:521-541`; `generators.yaml:14,37,64,107,152,277,385`; `generated/home-lab/artifact-manifest.json:8-15` |
| F8 | Plugin packs are already bound per object module (index-first), but unversioned and unpackaged | `topology/module-index.yaml` (`object_modules[].plugins_manifest`); ADR 0082 Decision item 4 (deferred) |
| F9 | Path resolution is already mount-agnostic | `framework_lock.py:47-49`; `compile-topology.py:117` |
| F10 | Residual home-lab coupling in framework assets | `plugins/manifests/compilers.yaml` (5×`secrets_root`); `plugins/compilers/instance_rows_compiler.py:765`; `templates/ansible/playbooks/vpn-gateway.yml.j2:19`; `templates/ansible/host_vars/wireguard_gateway.yml.j2:25,30` |
| F11 | The declared integration fixture leaves with the project; the replacement is not ready | ADR 0081:57; `projects/test-lab/` (no `topology.yaml`, thin instances); `tests/plugin_integration/test_tuc*.py` |

## 4. Open questions (blocking the split, not blocking ADR 0114)

1. **Dev mount mechanism.** Submodule at `framework/` (single working tree, pointer bump per change,
   works on Windows), sibling checkouts plus a gitignored symlink/junction (independent histories,
   mount not reproducible from clone), or an umbrella workspace repository with two submodules.
   ADR 0114 §6 requires all three to keep working; the *default* development mode is unchosen.
2. **Repository identity and history.** Either rename `strateg/home-lab` to `strateg/taiga` (full
   framework history preserved in place, GitHub redirect, new empty project repository created and
   populated by `git filter-repo`), or keep `strateg/home-lab` as the project repository and create
   `strateg/taiga` via `bootstrap-framework-repo.py --preserve-history` (framework history
   duplicated across both repositories). Note `framework.lock.yaml` currently records
   `repository: git@github.com:strateg/home-lab.git` as the *framework* source.
3. **TUC ownership.** Whether `acceptance-testing/**` stays framework-side with `test-lab` as its
   fixture, or moves to the project with framework-side TUCs rebuilt on synthetic data.
4. **Agent instructions for the project repository.** `.claude/`, `AGENTS.md`, `CLAUDE.md`, and
   `docs/ai/**` are framework-repo-only by ADR 0081 §1.1, yet AI-assisted development must operate
   in the project repository too. Options: duplicate a thin adapter, or make the rulebook part of
   the distributed artifact.
5. **Capability namespace unification.** Whether model capabilities and plugin capabilities merge
   into one namespace or stay separate with a validated mapping table (ADR 0114 §4.3).
