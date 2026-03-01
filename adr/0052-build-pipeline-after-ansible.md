# ADR 0052: Build Pipeline and Deploy Packages After Ansible Stabilization

- Status: Proposed
- Date: 2026-03-01

## Context

After ADR 0051, the repository is expected to have:
- a stable Ansible runtime root
- explicit ownership between generated inventory and manual overrides
- tracked secret values removed from inventory source
- a deterministic assembled Ansible runtime inventory

Only after that cleanup does it become safe to perform the broader repository restructuring that was previously attempted in one step.

The remaining problems are broader than Ansible:
- manual source files are still scattered across top-level directories
- deploy-time material is still not assembled explicitly
- bootstrap, Terraform, and Ansible artifacts are still hard to inspect as one deploy workflow
- CI has no clean notion of release-safe assembled packages

The key lesson from the earlier combined approach is that packaging must be built on stable runtime contracts, not used to discover them mid-migration.

## Decision

### 1. ADR 0052 Depends On ADR 0051

ADR 0052 must not be implemented until ADR 0051 is complete enough that:
- Ansible runtime inventory is already assembled deterministically
- tracked inventory source is free of raw secrets
- `deploy/` no longer depends on legacy manual inventory coupling

### 2. Manual Source Consolidates Under `src/`

Once the Ansible contract is clean, manual source can be moved safely:

```text
src/
├── ansible/
├── bootstrap/
├── configs/
└── scripts/
```

`src/` contains manual source only.

Generated topology output remains in `generated/`.

Assembled deploy-ready output is materialized in `dist/`.

### 3. `dist/` Uses Execution-Scope Packaging

Deploy artifacts are assembled by execution boundary:

```text
dist/
├── bootstrap/
│   └── <device-id>/
├── control/
│   ├── terraform/
│   │   ├── mikrotik/
│   │   └── proxmox/
│   └── ansible/
│       ├── ansible.cfg
│       ├── playbooks/
│       ├── roles/
│       └── inventory/
└── manifests/
    └── targets/
```

This keeps:
- bootstrap device-centric
- Terraform and Ansible control-plane centric

### 4. Ansible Packaging Consumes The Assembled Runtime Inventory From ADR 0051

`dist/control/ansible/inventory/` must be assembled from the already-stabilized runtime inventory produced by ADR 0051, not from raw legacy inventory files.

That means ADR 0052 does not reopen:
- deep-merge semantics
- secret placement
- generated vs manual inventory ownership

Those questions are already decided by ADR 0051.

### 5. Secret-Local Artifacts Are Explicitly Excluded From Release-Safe Packages

The following are not release-safe:
- `terraform.tfvars`
- `.vault_pass`
- private keys
- production `answer.toml`
- any generated file containing environment-specific secret values

Release-safe bootstrap output may include templates or examples, but only if they are generated from scrubbed inputs and cannot accidentally embed live secret material.

### 6. Build Pipeline Is Explicit

The packaging pipeline becomes:

```text
topology/ + src/
      |
      | [1] generate
      v
 generated/
      |
      | [2] assemble-ansible-runtime
      v
 generated/ansible/runtime/
      |
      | [3] assemble-deploy
      v
 dist/
```

Canonical commands remain under `deploy/Makefile` unless a later ADR changes that intentionally.

### 7. Validation Requirements

ADR 0052 is complete only when all of the following pass:

1. `python3 topology-tools/regenerate-all.py`
2. Ansible runtime assembly from ADR 0051
3. deploy package assembly
4. `ansible-inventory -i dist/control/ansible/inventory --list`
5. `terraform init -backend=false && terraform validate` for each assembled Terraform root
6. release-safe checks confirm that no secret-local files enter published artifacts

### 8. Explicitly Out Of Scope

ADR 0052 still does not perform:
- topology device ID renaming
- topology semantic cleanup unrelated to packaging
- secret manager redesign beyond the boundaries already established in ADR 0051

## Consequences

### Positive

1. The broad repository migration is now staged on a safer foundation
2. `src/`, `generated/`, and `dist/` gain clear roles
3. Deploy packages match execution boundaries
4. CI packaging policy becomes enforceable

### Negative / Trade-offs

1. The migration is slower because it is intentionally staged
2. There is a temporary period where both legacy and new source layouts coexist
3. Packaging now depends on the successful completion of ADR 0051

## References

- ADR 0050: Generated Directory Restructuring
- ADR 0051: Ansible Runtime, Inventory, and Secret Boundaries
- `deploy/Makefile`
