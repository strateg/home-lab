# ADR 0052: Deploy Package Assembly Over Accepted Ansible Runtime

- Status: Accepted
- Date: 2026-03-01

## Context

ADR 0051 is now accepted and implemented. The repository already has:
- a stable Ansible runtime root in `ansible/`
- explicit ownership between topology-generated inventory and manual overrides
- deterministic runtime inventory assembly under `generated/ansible/runtime/production/`
- deployment entrypoints that use the assembled runtime inventory

That changes the risk profile of the next migration step.

The remaining problem is not Ansible runtime semantics anymore. The remaining problem is deploy assembly:
- deploy inputs still live across several source roots
- there is no explicit assembled `dist/` tree for operator-facing deployment use
- Terraform, bootstrap, and Ansible outputs are still inspected through their native source/generation directories
- CI does not yet have a precise release-safe artifact boundary

The main lesson from the earlier combined design still holds: packaging must be built on top of stable runtime contracts, not used to discover them.

## Decision

### 1. ADR 0052 Depends On ADR 0051

ADR 0052 builds on the accepted runtime contract from ADR 0051:
- Ansible runtime inventory is already assembled deterministically
- tracked inventory source is already separated from runtime output
- `deploy/` already uses the runtime inventory contract from ADR 0051

ADR 0052 must not reopen those decisions.

### 2. Current Source Roots Remain Canonical During ADR 0052

ADR 0052 does not move manual source into `src/`.

The canonical source roots for this ADR remain the existing repository roots:
- `ansible/`
- `bootstrap/`
- `configs/`
- `manual-scripts/`
- `scripts/`
- `generated/`

`dist/` is introduced as assembled output only. It is not a new source-of-truth and it does not imply a source-layout migration.

If a future repository cleanup still wants `src/`, it must be decided by a separate ADR after `dist/` assembly is proven stable.

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
    ├── local-inputs.json
    ├── release-safe.json
    └── sources.json
```

This keeps:
- bootstrap device-centric
- Terraform and Ansible control-plane centric

### 4. Ansible Packaging Consumes The Assembled Runtime Inventory From ADR 0051

`dist/control/ansible/inventory/` must be copied from the already-stabilized runtime inventory produced by ADR 0051, not reassembled from raw inventory sources and not rebuilt via multi-`-i` layering during packaging.

That means ADR 0052 does not reopen:
- deep-merge semantics
- secret placement
- generated vs manual inventory ownership

Package-local `group_vars` at the Ansible package root must stay minimal:
- runtime defaults and operator overrides come from the assembled runtime inventory
- local secret scaffolding such as `vault.yml.example` may be included
- legacy `group_vars/all/vars.yml` style deploy defaults must not be used to create a second competing configuration layer

Those questions are already decided by ADR 0051.

### 5. Package Classes Are Explicit

ADR 0052 defines two package classes:
- `release-safe`
- `local-input-required`

`release-safe` means:
- safe to publish in CI artifacts
- contains no `local-secret` material as defined by ADR 0051
- may contain templates, examples, manifests, and assembled public config

`local-input-required` means:
- usable for real deployment only after the operator provides local environment inputs
- may reference required local files or values
- must not embed those local inputs into a publishable artifact by default

Examples of local inputs that are not release-safe:
- `terraform.tfvars`
- `.vault_pass`
- private keys
- production `answer.toml`
- any generated file containing environment-specific live secret values

The package assembler must emit manifests that describe required local inputs instead of embedding them into release-safe output.

### 6. Build Pipeline Is Explicit

The packaging pipeline becomes:

```text
topology/ + existing source roots
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
2. `python3 topology-tools/assemble-deploy.py`
3. `python3 topology-tools/validate-dist.py`
4. package manifests accurately declare package class, source roots, required local inputs, and validation commands
5. `release-safe.json` publishes only `release-safe` packages
6. release-safe checks confirm that no `local-secret` files enter published artifacts
7. external validators can run either directly when installed or in strict mode in CI

These conditions are now implemented in repository tooling:
- `topology-tools/assemble-deploy.py`
- `topology-tools/validate-dist.py`
- `deploy/Makefile` targets `assemble-dist` and `validate-dist`
- explicit bootstrap packages for `rtr-mikrotik-chateau`, `srv-gamayun`, and `srv-orangepi5`

### 8. Bootstrap Packaging Uses Explicit Source Maps And May Be Skipped

Bootstrap packaging must not auto-discover inputs from `bootstrap/` or `manual-scripts/`.

Bootstrap packages are declared explicitly by canonical generated source roots such as:
- `generated/bootstrap/rtr-mikrotik-chateau/`
- `generated/bootstrap/srv-gamayun/`
- `generated/bootstrap/srv-orangepi5/`

If a canonical generated source root does not exist yet or has no assembled payload, the package must still appear in `dist/manifests/packages.json` with:
- `status = skipped`
- its canonical `source_roots`
- no published payload

This keeps the source map explicit without pretending that legacy manual bootstrap assets are already safe deploy packages.

### 9. Explicitly Out Of Scope

ADR 0052 does not perform:
- `src/` repository restructuring
- topology device ID renaming
- topology semantic cleanup unrelated to packaging
- secret-manager redesign beyond the boundaries already established in ADR 0051
- changes to the accepted Ansible inventory ownership model from ADR 0051

## Consequences

### Positive

1. Deploy assembly is introduced without destabilizing the accepted Ansible runtime
2. `dist/` becomes an explicit operator-facing output layer
3. Deploy packages match execution boundaries
4. CI artifact policy becomes enforceable through package classes and manifests
5. A future source-layout migration can be evaluated separately with lower risk

### Negative / Trade-offs

1. The repository keeps existing top-level source roots for now
2. Packaging assembly adds another explicit build step to maintain
3. Some operators may still prefer native source directories during the transition period
4. A future `src/` migration, if still desired, requires another ADR instead of being bundled here

## References

- ADR 0050: Generated Directory Restructuring
- ADR 0051: Ansible Runtime, Inventory, and Secret Boundaries
- `deploy/Makefile`
- `topology-tools/assemble-ansible-runtime.py`
