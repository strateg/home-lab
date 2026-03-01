# ADR 0051: Ansible Runtime, Inventory, and Secret Boundaries

- Status: Accepted
- Date: 2026-03-01

## Context

The repository currently has one high-risk coupling area: Ansible runtime, topology-derived inventory, manual overrides, and secret-bearing values are mixed together while live deployment entrypoints still depend on them.

Current facts:
- `deploy/phases/03-services.sh` changes into `ansible/` and expects playbooks and runtime config there
- `ansible/ansible.cfg` uses relative paths tied to the current `ansible/` layout
- `generated/ansible/inventory/production/` contains topology-derived inventory
- `ansible/inventory/production/` still contains tracked manual inventory data
- tracked inventory files currently act as a mix of host model, operator overrides, and sometimes secret-adjacent operational data

This makes a broad repository migration unsafe:
1. Runtime can break from path changes alone
2. Ownership between generated and manual data is unclear
3. Secret handling is not explicit enough
4. Any later `src/` or `dist/` migration would inherit unstable Ansible semantics

## Decision

### 1. ADR 0051 Scope Is Limited To Ansible

ADR 0051 is only about:
- Ansible runtime root
- inventory ownership
- topology-to-Ansible linkage
- secret boundaries
- deterministic runtime inventory assembly

It does not decide broader `src/` / `dist/` packaging.

### 2. `ansible/` Remains The Canonical Runtime Root During This ADR

Until this ADR is complete, `ansible/` remains the canonical runtime root for:
- `ansible.cfg`
- playbooks
- roles
- vault helper scripts
- operator workflows that currently `cd ansible`

This is an explicit compatibility rule, not a permanent design endorsement.

### 3. Inventory Ownership Is Split Explicitly

Generated topology-derived inventory remains authoritative for hosts and groups:

```text
generated/ansible/inventory/production/
├── hosts.yml
├── group_vars/
└── host_vars/
```

Tracked manual non-secret overrides move to:

```text
ansible/inventory-overrides/production/
├── group_vars/
│   └── all.yml
└── host_vars/
    └── *.yml
```

Rules:
1. `generated/ansible/inventory/production/hosts.yml` is the source of truth for topology-derived host structure
2. tracked manual overrides may extend runtime behavior, but must not redefine generated host topology
3. service-level and operator-level overrides belong in `inventory-overrides`, not in generated inventory

### 4. Topology-Owned Service Hosts Must Be Generated

For topology-modeled workloads and services, tracked manual inventory is treated as a legacy or planning artifact, not as a canonical source of runtime truth.

This applies in particular to first-party LXC service hosts such as:
- `lxc-postgresql`
- `lxc-redis`

Rules:
1. canonical `inventory_hostname` must match the topology workload or device ID, e.g. `lxc-postgresql` and `lxc-redis`
2. generated inventory must provide topology-owned runtime facts such as:
   - connection user
   - host address
   - service port
   - resource profile values such as cores and RAM
   - service group membership
   - playbook binding metadata
3. if a host is still present only in legacy manual inventory, it must be added to topology before cutover
4. `inventory-overrides` must not be used to introduce durable host definitions that are missing from topology
5. display-oriented names such as `postgresql-db` or `redis-cache` may exist as metadata, but they must not replace the canonical inventory hostname

The intent is to move modeled infrastructure facts into generation, not to preserve them as tracked handwritten inventory.

### 5. Manual Authored Ansible Remains First-Class

This ADR does not reduce the role of handwritten Ansible. Manual Ansible remains the right place for:
- playbooks
- roles
- templates
- handlers
- maintenance workflows
- recovery scenarios
- one-off migration or remediation tasks

These manual assets must integrate with generated runtime inventory rather than duplicate topology-owned service facts.

Tracked `inventory-overrides` should remain minimal and focused on operator preferences or temporary, explicit exceptions such as:
- SSH client arguments
- feature flags
- environment-specific log level

If a value is expected to be stable, topology-owned, and required for normal service operation, it should be generated from topology instead of being maintained in overrides.

### 6. Manual Extension Patterns

Ansible developers may extend generated configurations without modifying generated files. The following patterns are supported:

#### 6.1 Layered Inventory

Ansible natively merges multiple inventory sources. During development or comparison work, maintainers may inspect behavior using:

```bash
# Debugging/comparison pattern only
ansible-inventory -i generated/ansible/inventory/production \
                  -i ansible/inventory-overrides/production
```

Variables from later sources override earlier ones according to Ansible variable precedence.

This is not the canonical production runtime contract. The operator-facing runtime target remains the assembled inventory under `generated/ansible/runtime/production/`.

#### 6.2 Hook Pattern (Pre/Post Tasks)

Playbooks may include optional hook files for custom pre- and post-processing:

```yaml
# ansible/playbooks/postgresql.yml
- hosts: lxc-postgresql
  tasks:
    - name: Include pre-tasks hook
      include_tasks: "{{ item }}"
      with_first_found:
        - files:
            - "hooks/postgresql-pre.yml"
          skip: true

    # Main tasks here...

    - name: Include post-tasks hook
      include_tasks: "{{ item }}"
      with_first_found:
        - files:
            - "hooks/postgresql-post.yml"
          skip: true
```

Hook files live in `ansible/playbooks/hooks/` and are manually authored.

Hook naming contract:
- `ansible/playbooks/hooks/<playbook>-pre.yml`
- `ansible/playbooks/hooks/<playbook>-post.yml`

Rules:
1. hook files are optional
2. baseline playbook execution must succeed when no hook files exist
3. hook files may extend behavior, but must not become required sources of topology-owned runtime facts

#### 6.3 Custom Roles

Manual roles extend or wrap generated behavior:

```text
ansible/roles/
├── postgresql/              # Base role (manual)
├── postgresql-extensions/   # Custom extensions (manual)
└── common/                  # Shared utilities (manual)
```

Playbooks compose roles as needed:

```yaml
- hosts: lxc-postgresql
  roles:
    - postgresql
    - postgresql-extensions
```

#### 6.4 Conditional Custom Tasks

Roles may conditionally include custom task files defined via inventory:

```yaml
# In role tasks/main.yml
- name: Include custom tasks if defined
  include_tasks: "{{ ansible_extensions.postgresql.custom_tasks }}"
  when:
    - ansible_extensions is defined
    - ansible_extensions.postgresql is defined
    - ansible_extensions.postgresql.custom_tasks is defined
```

```yaml
# In inventory-overrides/production/host_vars/lxc-postgresql.yml
ansible_extensions:
  postgresql:
    custom_tasks: "custom/postgresql-replication.yml"
```

#### 6.5 vars_files With Optional Includes

Playbooks may include optional variable files that override defaults:

```yaml
- hosts: lxc-postgresql
  vars_files:
    - vars/postgresql-defaults.yml
    - "{{ lookup('first_found', params, errors='ignore') | default(omit) }}"
  vars:
    params:
      files:
        - vars/custom/postgresql.yml
```

#### 6.6 Extension Directory Structure

```text
ansible/
├── playbooks/
│   ├── site.yml                    # Main entry (manual)
│   ├── postgresql.yml              # Service playbook (manual)
│   └── hooks/
│       ├── postgresql-pre.yml      # Pre-tasks hook (manual)
│       └── postgresql-post.yml     # Post-tasks hook (manual)
├── roles/
│   ├── common/                     # Shared role (manual)
│   ├── postgresql/                 # Base role (manual)
│   └── postgresql-extensions/      # Extension role (manual)
├── inventory-overrides/
│   └── production/
│       ├── group_vars/
│       │   └── all.yml             # Operator preferences
│       └── host_vars/
│           └── lxc-postgresql.yml  # Per-host extension flags
└── vars/
    └── custom/                     # Manual variable files
        └── postgresql.yml
```

#### 6.7 Extension Rules

1. Manual extensions must not duplicate topology-owned facts
2. Hook files are optional; playbooks must handle their absence gracefully
3. Custom roles should extend, not replace, base functionality
4. Per-host overrides in `inventory-overrides/` should be minimal and intentional
5. Extension patterns should be documented in playbook headers
6. Extension-specific variables should live under a dedicated namespace such as `ansible_extensions.*`
7. Base roles must run before extension roles
8. Extension roles must not redefine topology-owned defaults or host identity

Allowed extension data examples:
- `ansible_extensions.postgresql.custom_tasks`
- `ansible_extensions.postgresql.pre_hook_enabled`
- `ansible_extensions.redis.post_hook_enabled`
- operator-only feature toggles

Forbidden extension data examples:
- `ansible_user`
- `ansible_host`
- `vmid`
- `service_port`
- `cores`
- `ram`
- service configuration that already belongs to topology

### 7. Effective Runtime Inventory Is Assembled

An explicit assembly step produces the effective inventory used by Ansible runtime:

```text
generated/ansible/runtime/production/
├── hosts.yml
├── group_vars/
│   └── all/
│       ├── 10-generated.yml
│       └── 90-manual.yml
└── host_vars/
```

Assembly rules:
1. generated `hosts.yml` is copied unchanged
2. generated `group_vars/all.yml` becomes `10-generated.yml`
3. manual `inventory-overrides/production/group_vars/all.yml` becomes `90-manual.yml`
4. generated `host_vars/*.yml` are copied into the runtime inventory first
5. manual `inventory-overrides/production/host_vars/*.yml` are copied as overlays
6. if a manual `host_vars/<name>.yml` conflicts with a generated file of the same name, the assembler must:
   - fail by default, or
   - allow the override only via an explicit allowlist or `intentional_override` rule
7. precedence is determined by filenames and copy order, not custom recursive deep merge logic
8. extension variables under the approved extension namespace may be layered without redefining topology-owned facts

The goal is deterministic runtime behavior without inventing a YAML merge engine.

### 8. Secret-Bearing Data Must Not Live In Tracked Inventory Source

Tracked inventory source files must not contain:
- raw passwords
- live password hashes
- API tokens
- private keys
- vault password material
- environment-specific secrets that should be local-only

The repository must classify Ansible-related data into three explicit classes:

| Class | Description | Tracked |
|-------|-------------|---------|
| `tracked-public` | non-secret generated or manual configuration | Yes |
| `tracked-encrypted` | encrypted values intended for version control, e.g. Ansible Vault payloads | Yes |
| `local-secret` | live secret values, vault passwords, private keys, environment-local credentials | No |

Allowed destinations for secret values:
- `tracked-encrypted` vault files under `ansible/group_vars/` or `ansible/host_vars/`
- `local-secret` files excluded by `.gitignore`
- `.example` templates that contain placeholders only

Tracked inventory may reference vault variables, but must not embed live secret values directly.

Examples:
- `ansible/group_vars/all/vars.yml` should be `tracked-public`
- encrypted vault content is allowed as `tracked-encrypted`
- `.vault_pass` must remain `local-secret`

### 9. `ansible.cfg` Must Target The Assembled Runtime Inventory

After cutover, the default inventory in `ansible/ansible.cfg` must point to the runtime inventory directory, not a single `hosts.yml` file:

```text
../generated/ansible/runtime/production/
```

The raw generator output under `generated/ansible/inventory/production/` remains an intermediate artifact, not the operator-facing runtime target.

All operator-facing entrypoints must resolve inventory from one canonical place:
- `ansible/ansible.cfg`, or
- a shared helper variable used by `deploy/Makefile` and `deploy/phases/*.sh`

Runtime code must not duplicate ad hoc inventory path logic in multiple places.

### 10. Validation Requirements

ADR 0051 is complete only when all of the following pass:
1. `python3 topology-tools/regenerate-all.py`
2. runtime inventory assembly completes successfully
3. `ansible-inventory -i generated/ansible/runtime/production --list`
4. playbook syntax checks succeed against the assembled runtime inventory
5. tracked inventory source no longer carries raw secret values
6. dry-run comparison shows that old and new runtime inventories are equivalent for:
   - host list
   - group membership
   - selected hostvars on representative hosts
7. topology-owned service hosts no longer depend on tracked manual inventory for normal runtime facts

### 11. Rollback And Safety Rules

If assembled runtime inventory causes playbook regressions:
1. `ansible/ansible.cfg` must be switchable back to the previous inventory target in one revertable commit
2. `deploy/phases/03-services.sh` must retain a temporary compatibility path until the new runtime target is proven stable
3. legacy manual inventory files must not be deleted before the comparison and cutover gates are passed
4. rollback must not require reconstructing deleted tracked files from memory or external state

### 12. Explicitly Out Of Scope

ADR 0051 does not decide:
- `src/` repository restructuring
- `dist/` deploy package structure
- Terraform package assembly
- bootstrap package assembly
- target-centric release artifacts
- topology identity renaming

Those concerns are deferred to ADR 0052.

## Consequences

### Positive

1. The highest-risk migration surface is reduced first
2. Ansible runtime becomes explicit and testable
3. Topology-derived data and manual overrides get separate ownership
4. Secret handling is clarified before broader packaging work
5. Rollback becomes simpler because cutover and cleanup are separated
6. ADR 0052 can build on a stable Ansible contract
7. Manual Ansible scenarios stay supported without serving as a shadow inventory source

### Negative / Trade-offs

1. The overall migration becomes intentionally two-stage
2. The repository temporarily keeps both raw generated inventory and assembled runtime inventory
3. Some tracked values may need manual extraction into vault-managed or local-only files
4. The assembler needs explicit conflict handling for `host_vars` overrides
5. Generator coverage must improve before some legacy manual inventory can be removed

## References

- ADR 0050: Generated Directory Restructuring
- `ansible/ansible.cfg`
- `deploy/phases/03-services.sh`
- `generated/ansible/inventory/production/`
- ADR 0052
