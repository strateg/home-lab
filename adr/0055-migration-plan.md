# ADR 0055: Migration Plan

План для введения tracked manual Terraform extension layer без смешения с local inputs.

## Goal

Добавить reviewable Terraform exception layer поверх generated baseline, не ломая контракты ADR 0052, ADR 0054 и текущего deploy-контракта ADR 0085 (historically ADR 0053).

## Preconditions

1. ADR 0054 local-input strategy is accepted or stable enough to use as dependency
2. generated Terraform roots remain canonical topology-derived baselines
3. no secrets are moved into tracked extension files

## Non-Goals

В рамках этого плана не выполняется:

1. перенос `terraform.tfvars` в tracked files
2. ручное редактирование `generated/terraform/*`
3. redesign package classes
4. broad topology ownership changes

## Phase 0: Inventory Existing Manual Terraform Exceptions

Проверить, какие manual Terraform changes уже существуют неявно:
- ad hoc local `.tf` files near execution roots
- docs telling operators to patch generated files
- provider gaps currently handled outside topology
- legacy generated roots that may hide prior manual workflows, such as `generated/terraform-mikrotik/`

Result:
- explicit backlog of real extension use cases
- no speculative override layer without a concrete need

## Phase 1: Introduce `terraform-overrides/`

Create:

```text
terraform-overrides/
├── mikrotik/
└── proxmox/
```

Initial policy:
- tracked in Git
- empty by default is acceptable
- optional `README.md` per target may document allowed usage

## Phase 2: Update Assembly Contract

Update native and dist assembly so Terraform execution roots are built from:

1. `generated/terraform/<target>/`
2. `terraform-overrides/<target>/`
3. `local/terraform/<target>/terraform.tfvars`

Validation gate:

```text
make assemble-dist
make validate-dist
make check-parity
```

Parity must compare fully assembled execution roots, not only generated baseline.

## Phase 3: Add Guardrails

Introduce checks or conventions that reject:
- `terraform.tfvars` under `terraform-overrides/`
- `.tfstate`
- `.terraform/`
- obvious secret-bearing tracked files
- file-name shadowing of generated baseline files
- copied baseline `.tf` files edited under `terraform-overrides/`

Preferably also require a short rationale comment or README for non-trivial overrides.

## Phase 4: Migrate Legitimate Existing Exceptions

Only after the layer exists:
- move justified manual `.tf` exceptions into `terraform-overrides/`
- leave local environment values in `local/`
- remove any docs that suggest patching `generated/terraform/*` directly

## Phase 5: Review And Reduce

After real use:
- revisit overrides periodically
- move stable repeated patterns into topology/generator logic
- keep `terraform-overrides/` narrow and exceptional

## Phase 6: Post-Acceptance Documentation And Onboarding

After ADR 0054 and ADR 0055 are accepted and implemented:
- update `CLAUDE.md` directory structure to include both `local/` and `terraform-overrides/`
- add a short onboarding diagram to `CLAUDE.md` that shows the three Terraform layers:
  - generated baseline
  - tracked overrides
  - local inputs
- make that diagram explain how those layers assemble into the final execution root

## Future Follow-Up

If Terraform overrides prove useful and a similar need emerges for configuration-management code beyond the current Ansible model, consider a separate future ADR for an Ansible extension layer.

That future ADR should be justified by concrete use cases rather than created preemptively.

## Completion Criteria

1. Terraform manual exceptions have a tracked home outside `generated/`
2. local inputs remain in `local/`
3. assembled execution roots explicitly include overrides
4. docs stop teaching direct edits of `generated/terraform/*`
5. overrides remain reviewable, narrow, and non-secret
