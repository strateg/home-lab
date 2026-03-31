# ADR 0085: Deploy Bundle and Runner Workspace Contract

- Status: Accepted (core bundle/profile/runner contract implemented; Docker/Remote backend completion deferred)
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

Applicability to ADR 0075 and ADR 0076 is mandatory:
- both the current main repository workflow and the separated framework/project repository workflow are first-class deploy-plane modes,
- under ADR 0075, deploy artifacts and runtime state must remain project-scoped rather than framework-scoped inside the monorepo,
- under ADR 0076, the same deploy-plane contract must continue to work when a project consumes the framework through submodule or package distribution,
- therefore deploy tooling MUST NOT depend on a single integrated repository layout beyond a resolved project workspace plus verified framework dependency.

## Decision

### D1. Introduce Deploy Bundle as the Canonical Execution Input

Deploy-time execution MUST consume a project-scoped immutable deploy bundle rather than reading directly from `generated/` or ad hoc execution roots.

Canonical host-side location, relative to the active project workspace root:
- `.work/deploy/bundles/<bundle_id>/`

The active project workspace MAY be:
- the current main-repository project root resolved per ADR 0075,
- an extracted project repository with framework dependency resolved per ADR 0076,
- a staging workspace assembled from either of those sources for backend execution.

Both repository topologies are first-class execution modes. Neither is a compatibility fallback.

Bundle contents:
- `manifest.yaml` — execution manifest derived from generated artifacts and deploy profile resolution
- `artifacts/<node_id>/...` — assembled secret-bearing execution artifacts
- `metadata.yaml` — provenance, bundle hash, source manifest references, backend-neutral metadata

`bundle_id` SHOULD be deterministic for a given topology snapshot plus resolved secret/material input set.

Bundle assembly MUST operate only after framework/project resolution and compatibility verification required by ADR 0075 and ADR 0076 have succeeded.

### D2. Keep `generated/` Inspectable and Secret-Free

The project-scoped generated tree remains the source-derived, inspectable artifact tree.

Examples:
- main-repository mode: `generated/<project>/...`
- extracted project-repo mode: project-local generated root with the same contract shape

It MAY contain:
- bootstrap templates and rendered secret-free outputs,
- Terraform/OpenTofu configs,
- Ansible inventory and docs,
- source-derived manifests such as `INITIALIZATION-MANIFEST.yaml`.

It MUST NOT be treated as the direct execution source for deploy-time tooling.
It MUST remain attributable to one resolved project workspace and one verified framework dependency state.

### D3. Separate Deploy Profile from Object Contracts

Operator-environment and backend-specific settings MUST live in a project-scoped deploy profile.

Examples:
- main-repository mode: `projects/<project>/deploy/deploy-profile.yaml`
- extracted project-repo mode: `deploy/deploy-profile.yaml`

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

Runner staging MUST consume a project-scoped bundle/workspace boundary and MUST NOT depend on framework sources being colocated with the project at execution time.

### D6. Runtime State and Logs Live Outside the Bundle

Deploy bundles are immutable and MUST NOT contain mutable runtime state.

Mutable operational data lives in a separate project-scoped runtime root, for example:
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
- the project-scoped generated root stays secret-free,
- deploy bundle may contain secret-bearing execution artifacts,
- runner workspaces are derived from the deploy bundle,
- secret-bearing material MUST remain outside tracked source trees.

In ADR 0076 package-distribution mode, deploy-bundle assembly MUST treat distributed framework artifacts as read-only inputs and MUST NOT mutate framework dependency content inside the project workspace.

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
- The deploy plane remains valid across ADR 0075 monorepo separation and ADR 0076 multi-repo distribution.
- Deploy tooling can be run from the current main repository or from a separated project repository without changing the core execution model.
- Secret materialization becomes centralized and auditable.
- Deploy execution becomes reproducible through explicit bundle selection.

What trade-offs or risks are introduced?
- One more boundary is added: generate -> assemble/build -> bundle -> execute.
- Deploy tooling must manage workspace staging explicitly.
- Bundle lifecycle and retention policy must be documented and implemented.

What migration or compatibility impact exists?
- Existing `generated/<project>/...` outputs remain for inspection and authoring workflows.
- Equivalent project-local generated roots in ADR 0076 project repositories MUST preserve the same contract shape.
- ADR 0084 runner abstraction should be expanded to support staging and capability reporting.
- Framework lock verification from ADR 0076 becomes a prerequisite input to deploy-bundle assembly, not a deploy-runner concern.
- ADR 0083 is not a prerequisite for adopting ADR 0085; it remains a later optional consumer of this contract.

## References

- `adr/0083-unified-node-initialization-contract.md`
- `adr/0084-cross-platform-dev-plane-and-linux-deploy-plane.md`
- `adr/0075-framework-project-separation.md`
- `adr/0076-framework-distribution-and-multi-repository-extraction.md`
- `docs/framework/FRAMEWORK-V5.md`
- `scripts/orchestration/deploy/runner.py`
- `scripts/orchestration/deploy/workspace.py`
- `topology-tools/utils/service_chain_evidence.py`
- `adr/0085-analysis/GAP-ANALYSIS.md` - Gap analysis and implementation progress
- `adr/0085-analysis/IMPLEMENTATION-PLAN.md` - Phased implementation plan
- `adr/0085-analysis/CUTOVER-CHECKLIST.md` - Migration gate checklist
