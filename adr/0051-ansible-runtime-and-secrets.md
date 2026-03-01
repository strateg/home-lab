# ADR 0051: Ansible Runtime, Inventory, and Secret Boundaries

- Status: Proposed
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

### 4. Effective Runtime Inventory Is Assembled

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
4. manual `host_vars/*.yml` are copied as overlays
5. precedence is determined by filenames, not custom recursive deep merge logic

The goal is deterministic runtime behavior without inventing a YAML merge engine.

### 5. Secret-Bearing Data Must Not Live In Tracked Inventory Source

Tracked inventory source files must not contain:
- raw passwords
- live password hashes
- API tokens
- private keys
- vault password material
- environment-specific secrets that should be local-only

Allowed destinations for secret values:
- vault-managed files under `ansible/group_vars/` or `ansible/host_vars/`
- local-only files excluded by `.gitignore`
- `.example` templates that contain placeholders only

Tracked inventory may reference vault variables, but must not embed live secret values directly.

### 6. `ansible.cfg` Must Target The Assembled Runtime Inventory

After cutover, the default inventory in `ansible/ansible.cfg` must point to:

```text
../generated/ansible/runtime/production/
```

The raw generator output under `generated/ansible/inventory/production/` remains an intermediate artifact, not the operator-facing runtime target.

### 7. Validation Requirements

ADR 0051 is complete only when all of the following pass:
1. `python3 topology-tools/regenerate-all.py`
2. runtime inventory assembly completes successfully
3. `ansible-inventory -i generated/ansible/runtime/production --list`
4. playbook syntax checks succeed against the assembled runtime inventory
5. tracked inventory source no longer carries raw secret values

### 8. Explicitly Out Of Scope

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
5. ADR 0052 can build on a stable Ansible contract

### Negative / Trade-offs

1. The overall migration becomes intentionally two-stage
2. The repository temporarily keeps both raw generated inventory and assembled runtime inventory
3. Some tracked values may need manual extraction into vault-managed or local-only files

## References

- ADR 0050: Generated Directory Restructuring
- `ansible/ansible.cfg`
- `deploy/phases/03-services.sh`
- `generated/ansible/inventory/production/`
- ADR 0052
