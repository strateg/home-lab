# ADR 0085: Deploy Bundle and Runner Workspace Contract

- Status: Proposed (Primary deploy-domain priority)
- Date: 2026-03-31

## Context

ADR 0083 proposes topology-driven node initialization and deploy-domain orchestration, but that work is optional and intentionally sequenced later.
ADR 0084 defines the Linux-backed deploy plane and `DeployRunner`, but it needs a stable execution-input contract.

The missing piece is the execution handoff between generated artifacts and deploy-time execution.

Today the model still assumes direct execution from repository-local paths such as:
- `generated/<project>/bootstrap/...`
- `.work/native/bootstrap/...`

That is workable for a purely local flow, but it is not a stable architectural contract for:
- `WSLRunner`, where host paths require translation,
- `DockerRunner`, where artifacts must be mounted or copied into a container workspace,
- `RemoteLinuxRunner`, where artifacts must be staged onto a remote control node.

The current shape also risks leaking operator-environment details into object-level contracts, which conflicts with the framework/project/runtime boundary defined by ADR 0075 and `docs/framework/FRAMEWORK-V5.md`.

The deploy domain needs:
- an immutable execution input,
- a project-scoped deploy profile for operator/backend settings,
- and a runner workspace contract that works across all supported backends.

This ADR is therefore the foundational deploy-domain ADR for the current sequence:
1. ADR 0085 defines what deploy tooling executes
2. ADR 0084 defines where and how that execution runs
3. ADR 0083 may later decide whether to adopt that model for node initialization

## Decision

### D1. Introduce Deploy Bundle as the Canonical Execution Input

Deploy-time execution MUST consume a project-scoped immutable deploy bundle rather than reading directly from `generated/` or ad hoc execution roots.

Canonical host-side location:
- `.work/deploy/bundles/<bundle_id>/`

Bundle contents:
- `manifest.yaml` — execution manifest derived from generated artifacts and deploy profile resolution
- `artifacts/<node_id>/...` — assembled secret-bearing execution artifacts
- `metadata.yaml` — provenance, bundle hash, source manifest references, backend-neutral metadata

`bundle_id` SHOULD be deterministic for a given topology snapshot plus resolved secret/material input set.

### D2. Keep `generated/` Inspectable and Secret-Free

`generated/<project>/...` remains the source-derived, inspectable artifact tree.

It MAY contain:
- bootstrap templates and rendered secret-free outputs,
- Terraform/OpenTofu configs,
- Ansible inventory and docs,
- source-derived manifests such as `INITIALIZATION-MANIFEST.yaml`.

It MUST NOT be treated as the direct execution source for deploy-time tooling.

### D3. Separate Deploy Profile from Object Contracts

Operator-environment and backend-specific settings MUST live in a project-scoped deploy profile, for example:
- `projects/<project>/deploy/deploy-profile.yaml`

Deploy profile owns:
- default runner/backend selection,
- backend-specific configuration,
- toolchain expectations,
- staging policy,
- environment-specific timeouts/retries,
- logical input resolution such as installer images or firmware bundles.

Object modules MUST NOT encode:
- host-local absolute paths,
- WSL distro names,
- Docker image names,
- remote control-node hostnames,
- backend-specific workspace paths.

### D4. Narrow Object-Level Initialization Contract Scope

`initialization_contract` remains object-scoped but is limited to device/bootstrap semantics:
- mechanism,
- required logical inputs,
- artifact templates and outputs,
- handover channel,
- handover checks,
- destructive-operation semantics.

This contract describes what the device needs and what constitutes successful handover. It does not describe where those inputs live on the operator machine or how they are staged by a backend.

### D5. Runner Contract Is Workspace-Aware

`DeployRunner` MUST evolve from simple command execution to workspace-aware execution.

Conceptual responsibilities:
- stage deploy bundle into backend workspace,
- execute commands inside that workspace,
- report backend capabilities,
- optionally fetch outputs/logs when backend execution is non-local,
- clean up temporary backend workspaces when appropriate.

Backends map this differently:
- `NativeRunner`: direct local workspace
- `WSLRunner`: translated workspace path inside WSL
- `DockerRunner`: mounted or copied workspace inside container
- `RemoteLinuxRunner`: staged workspace on remote Linux host

### D6. Runtime State and Logs Live Outside the Bundle

Deploy bundles are immutable and MUST NOT contain mutable runtime state.

Mutable operational data lives in a separate runtime root, for example:
- `.work/deploy-state/<project>/nodes/<node_id>.yaml`
- `.work/deploy-state/<project>/logs/<run_id>.jsonl`

This includes:
- initialization state,
- drift acknowledgements,
- handover verification outcomes,
- audit logs,
- operator confirmations.

### D7. Bundle Assembly Is the Secret Join Point

The only sanctioned join point between source-derived artifacts and decrypted secrets is deploy-bundle assembly.

Therefore:
- `generated/` stays secret-free,
- deploy bundle may contain secret-bearing execution artifacts,
- runner workspaces are derived from the deploy bundle,
- secret-bearing material MUST remain outside tracked source trees.

### D8. Deploy Entry Points Consume `bundle_id`

Deploy-domain entry points MUST operate on an explicit bundle selection.

Examples:
- `init-node.py --bundle <bundle_id> --node <node_id>`
- `apply-terraform.py --bundle <bundle_id> --lane proxmox`
- `run-ansible.py --bundle <bundle_id> --inventory production`

This makes execution deterministic, auditable, and backend-neutral.

### D9. Runner Capability Negotiation Must Be Explicit

Each runner SHOULD report capabilities needed by deploy tooling, such as:
- interactive confirmation support,
- host-network access,
- path translation support,
- persistent workspace support,
- artifact upload/download support.

Deploy tooling MUST fail fast when the requested operation requires capabilities that the selected runner does not provide.

## Consequences

What improves?
- ADR 0083 gains a clean execution handoff instead of relying on repository-local runtime paths.
- ADR 0084 becomes credible for `wsl`, `docker`, and `remote` backends.
- Framework/project/runtime boundaries become clearer and easier to validate.
- Secret materialization becomes centralized and auditable.
- Deploy execution becomes reproducible through explicit bundle selection.

What trade-offs or risks are introduced?
- One more boundary is added: generate -> assemble/build -> bundle -> execute.
- Deploy tooling must manage workspace staging explicitly.
- Bundle lifecycle and retention policy must be documented and implemented.

What migration or compatibility impact exists?
- Existing `generated/<project>/...` outputs remain for inspection and authoring workflows.
- ADR 0084 runner abstraction should be expanded to support staging and capability reporting.
- ADR 0083 is not a prerequisite for adopting ADR 0085; it remains a later optional consumer of this contract.

## References

- `adr/0083-unified-node-initialization-contract.md`
- `adr/0084-cross-platform-dev-plane-and-linux-deploy-plane.md`
- `adr/0075-framework-project-separation.md`
- `docs/framework/FRAMEWORK-V5.md`
- `scripts/orchestration/deploy/runner.py`
- `topology-tools/utils/service_chain_evidence.py`
