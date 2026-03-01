# ADR 0051: Build Pipeline and Deploy Packages

- Status: Proposed
- Date: 2026-03-01

## Context

### Current Problems

The repository currently mixes three different kinds of artifacts:

1. Manual source files edited by humans:
   - `ansible/`
   - `bootstrap/`
   - `manual-scripts/`
   - `configs/`
   - `scripts/`

2. Generated output produced from topology:
   - `generated/terraform/`
   - `generated/ansible/`
   - `generated/bootstrap/`
   - `generated/docs/`

3. Runtime entrypoints and orchestration:
   - `deploy/Makefile`
   - `deploy/phases/*.sh`
   - `topology/L7-operations.yaml`

This creates three classes of problems:

#### 1. Source Layout Is Hard To Understand

Manual inputs are spread across unrelated top-level directories. It is not obvious which files are:
- canonical source
- generated output
- deploy-time runtime material

#### 2. Some Artifacts Exist In Both Manual And Generated Form

Examples already present in the repository:

| Artifact | Manual / legacy path | Generated path |
|----------|----------------------|----------------|
| MikroTik bootstrap init script | `bootstrap/mikrotik/init-terraform.rsc` | `generated/bootstrap/rtr-mikrotik-chateau/init-terraform.rsc` |
| Ansible inventory `hosts.yml` | `ansible/inventory/production/hosts.yml` | `generated/ansible/inventory/production/hosts.yml` |
| Ansible `group_vars/all.yml` | `ansible/inventory/production/group_vars/all.yml` | `generated/ansible/inventory/production/group_vars/all.yml` |
| Proxmox `answer.toml` | `manual-scripts/bare-metal/answer.toml` | generated from topology by `topology-tools/generate-proxmox-answer.py` |

The repository does not currently define a safe merge or ownership rule for these overlaps.

#### 3. Deployment Boundaries Do Not Match Execution Boundaries

ADR 0050 intentionally organized generated output by tool and root module:
- Terraform runs from a control machine against external APIs
- Ansible runs from a control machine against multiple hosts
- Bootstrap artifacts are device-local and imperative

That means not every artifact can be meaningfully packaged as "everything for one target device":
- Proxmox Terraform manages VMs and LXCs beyond the physical host
- Ansible playbooks target `all`, `proxmox`, and `lxc_containers`, not a single device
- Some artifacts are cross-target by design

### Requirements

1. Separate manual sources, generated output, and deploy artifacts clearly
2. Preserve ADR 0050 execution model and Terraform state boundaries
3. Provide target-centric discoverability without pretending every tool is single-target
4. Eliminate ambiguous ownership of duplicated artifacts
5. Avoid packaging secrets into CI artifacts
6. Migrate without breaking existing `deploy/` and Ansible workflows mid-flight

## Decision

### 1. Consolidate Manual Sources Under `src/`

Manual, human-maintained inputs move under `src/`:

```text
src/
├── ansible/
│   ├── ansible.cfg
│   ├── requirements.yml
│   ├── playbooks/
│   ├── roles/
│   ├── group_vars/
│   ├── inventory-overrides/
│   │   ├── group_vars/
│   │   └── host_vars/
│   └── README.md
├── bootstrap/
│   ├── mikrotik/
│   ├── proxmox/
│   ├── opi5/
│   └── openwrt/
├── configs/
└── scripts/
```

Notes:
- `src/` contains only manual source artifacts
- generated output remains in `generated/`
- deploy-ready output is assembled into `dist/`

### 2. Classify Artifacts Explicitly

Every deploy-related artifact must belong to one of these classes:

| Class | Meaning | Example | CI artifact eligible |
|-------|---------|---------|----------------------|
| `manual-source` | Human-maintained source in git | `src/ansible/playbooks/site.yml` | Yes |
| `generated` | Deterministic output from topology | `generated/ansible/inventory/production/hosts.yml` | Yes |
| `assembled` | Runtime package built from manual + generated inputs | `dist/control/ansible/` | Yes, if release-safe |
| `secret-local` | Local materialization containing secrets or machine-local values | `terraform.tfvars`, `.vault_pass`, production `answer.toml` | No |

Rules:
- `terraform.tfvars` is never a committed or release-safe artifact
- `.vault_pass`, private keys, provider credentials, and production password-bearing `answer.toml` are never included in CI-uploaded packages
- CI may publish only release-safe `dist/` output

### 3. Use Execution-Scope Packages, Not Fake Per-Target Packages

`dist/` packages are assembled by how they are executed:

```text
dist/
├── bootstrap/
│   ├── rtr-mikrotik-chateau/
│   │   ├── init-terraform.rsc
│   │   ├── bootstrap.rsc
│   │   └── README.md
│   ├── srv-gamayun/
│   │   ├── answer.toml.example
│   │   ├── create-uefi-autoinstall-proxmox-usb.sh
│   │   ├── post-install/
│   │   └── README.md
│   └── srv-orangepi5/
│       ├── cloud-init/
│       ├── install.sh
│       └── README.md
├── control/
│   ├── terraform/
│   │   ├── mikrotik/
│   │   └── proxmox/
│   └── ansible/
│       ├── ansible.cfg
│       ├── requirements.yml
│       ├── inventory/
│       ├── playbooks/
│       └── roles/
└── manifests/
    ├── targets/
    │   ├── rtr-mikrotik-chateau.md
    │   ├── srv-gamayun.md
    │   └── srv-orangepi5.md
    └── release-manifest.json
```

This preserves two important properties:
- bootstrap remains device-centric
- Terraform and Ansible remain control-plane centric

Target-centric usability is provided by `dist/manifests/targets/*.md`, which points a human to the correct bootstrap and control-plane artifacts for that target.

### 4. Build Pipeline

```text
topology/ + src/
      |
      | [1] generate
      v
 generated/
      |
      | [2] assemble
      v
    dist/
      |
      | [3] validate
      v
 release-safe packages
```

Canonical commands during ADR 0051 migration:
- `cd deploy && make generate`
- `cd deploy && make assemble`
- `cd deploy && make validate-dist`

During this ADR, `deploy/Makefile` remains the canonical entrypoint. A root-level wrapper Makefile is optional and out of scope.

### 5. Ansible Overlay Uses Layered Files, Not YAML Deep Merge

The assembler must not implement custom recursive merge semantics for `group_vars/all.yml`.

Instead it assembles layered Ansible vars:

```text
dist/control/ansible/inventory/production/
├── hosts.yml                         # generated
├── group_vars/
│   └── all/
│       ├── 10-generated.yml         # from generated inventory
│       └── 90-manual.yml            # from src/ansible/inventory-overrides/group_vars/all.yml
└── host_vars/
    ├── lxc-postgresql.yml           # generated or copied by explicit rule
    └── srv-gamayun.yml              # manual override, if present
```

Rules:
1. `hosts.yml` comes only from generated topology output
2. generated `group_vars/all.yml` is copied as `group_vars/all/10-generated.yml`
3. manual `src/ansible/inventory-overrides/group_vars/all.yml` becomes `group_vars/all/90-manual.yml`
4. manual `host_vars/*.yml` are copied as overlays
5. filename ordering, not custom YAML merge code, determines precedence

This keeps precedence explicit and debuggable and avoids special handling for lists, Jinja expressions, and mixed scalar types.

### 6. `answer.toml` Is Generated, Not Manual Source

`answer.toml` is produced from topology and may contain secret material.

Therefore:
- the source of truth is the generator plus topology
- `src/bootstrap/proxmox/` stores the scripts and templates around USB creation
- assembled `dist/bootstrap/srv-gamayun/answer.toml.example` may be release-safe
- any production `answer.toml` with real password material is `secret-local`

### 7. Compatibility Strategy

Migration must preserve working entrypoints until cutover is complete.

Compatibility requirements:
- `deploy/phases/*.sh` must continue to work during intermediate commits
- Ansible runtime must keep a valid `ansible.cfg` plus working relative paths
- `topology/L7-operations.yaml` and `topology-tools/regenerate-all.py` must be updated in the same cutover window as the runtime paths they describe
- legacy paths may remain temporarily as wrappers, sync copies, or clearly marked compatibility shims

### 8. Validation Requirements

Assembler output is valid only if all of the following pass:

1. `python3 topology-tools/regenerate-all.py`
2. `ansible-inventory -i dist/control/ansible/inventory/production --list`
3. `terraform validate` for each assembled Terraform root
4. required bootstrap files exist for each declared target
5. release-safe validation confirms no `secret-local` files are included in CI artifacts

### 9. Explicitly Out Of Scope

This ADR does not perform:
- topology device ID renaming such as `mikrotik-chateau` to `rtr-mikrotik-chateau`
- Terraform state migration policy changes beyond ADR 0050
- root-level Makefile introduction
- full CI release automation for secret-bearing deploy bundles

If device identity cleanup is desired, it must be handled by a separate ADR and migration plan.

## Consequences

### Positive

1. Manual, generated, and assembled artifacts become distinct and auditable
2. Packaging matches real execution boundaries
3. Ansible precedence becomes deterministic without a custom merge engine
4. CI artifact policy becomes compatible with secret hygiene
5. Target-centric discoverability is preserved via manifests and bootstrap folders

### Negative / Trade-offs

1. `dist/` is slightly less visually simple than "one directory per target"
2. Migration requires temporary compatibility shims
3. The assembler must understand both release-safe and local-only outputs
4. Documentation and runbooks must be updated in lockstep with runtime paths

## Implementation Outline

### Phase 1: Prepare Source Tree

1. Create `src/` structure
2. Move manual sources with `git mv`
3. Keep existing runtime entrypoints working

### Phase 2: Implement Assembler

1. Create `topology-tools/assemble-deploy.py`
2. Assemble execution-scope packages in `dist/`
3. Generate target manifests
4. Add release-safe validation

### Phase 3: Cut Over Runtime Paths

1. Update `deploy/Makefile`
2. Update `deploy/phases/*.sh`
3. Update `topology/L7-operations.yaml`
4. Update `topology-tools/regenerate-all.py`

### Phase 4: Validate

1. Regenerate all outputs
2. Validate assembled Terraform roots
3. Validate assembled Ansible inventory
4. Verify bootstrap artifacts and manifests

### Phase 5: Cleanup

1. Remove deprecated duplicates after cutover
2. Remove temporary compatibility shims
3. Update documentation and ADR status

## References

- ADR 0050: Generated Directory Restructuring
- ADR 0028: topology-tools Architecture Consolidation
- `deploy/Makefile`
- `deploy/phases/03-services.sh`
- `topology/L7-operations.yaml`
