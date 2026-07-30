# ADR 0114: TAIGA Architecture Harmonization across Toolchain, Library, Extension, and Project Planes

- Status: Proposed
- Date: 2026-07-30
- Related: ADR-0063 (Plugin Microkernel), ADR-0069 (Compile/Commit Contract), ADR-0075 (Monorepo Framework/Project Boundary), ADR-0076 (Framework Distribution and Multi-Repository Extraction), ADR-0078 (Object-Module Local Template Layout), ADR-0080 (6-Stage Pipeline), ADR-0081 (Framework Runtime Artifact and 1:N Project Repository Model), ADR-0082 (Plugin Module-Pack Composition and Index-First Discovery), ADR-0106 (Capability-Driven Plugin Architecture), ADR-0113 (Kernel Runtime Decomposition)

## Context

The next development step is to split framework engineering from project engineering into
separate Git repositories while keeping AI-assisted development able to work on both at once.

Tooling for that split already exists and is not the blocker: `topology-tools/utils/bootstrap-framework-repo.py`
(`--preserve-history`), `topology-tools/utils/init-project-repo.py` (submodule or dist-zip),
`topology-tools/utils/bootstrap-project-repo.py` (`--framework-root`), and the
`task framework:release-*` family. Path resolution is already mount-agnostic:
`framework_lock.py:47-49` accepts both the monorepo layout (`topology/framework.yaml`) and the
extracted layout (`framework.yaml`), and `resolve_repo_path` (`compile-topology.py:117`) is a
plain join against the repo root.

The actual blocker is that **each artifact kind has its own, separately invented extension
mechanism**, so "what a project may add to the framework" has four different answers:

| Artifact kind | How a project extends it today | State |
|---------------|--------------------------------|-------|
| Plugins | `framework → project` chain via `project_plugins_root` (`plugin_manifest_discovery.py:191-251`, wired at `compile-topology.py:1125`); boundary validated by `plugins/discoverers/discover_boundary.py` | works |
| Templates | single root, `FileSystemLoader(str(root))` (`plugins/generators/base_generator.py:61-121`); only an object-module fallback exists (`object_template_root:90-107`, ADR 0078) | no project layer |
| Classes / objects | one root each (`compile-topology.py:465,596,1088,1123`); project bootstrap points both at the mounted framework (`bootstrap-project-repo.py:228-244`) | a project cannot declare its own class or object |
| Product catalog | resolved from `repo_root` (`compiler_plugin_context.py:82-83`), absent from `distribution.include` in `topology/framework.yaml`, copied into the project at bootstrap (`bootstrap-project-repo.py:194`) | contract drift between framework and projects |

Two further mismatches surfaced during analysis:

1. **The framework is distributed as one monolithic blob.** `topology/framework.yaml`
   `distribution.include` ships the executable toolchain and the topology libraries as a single
   payload with a single version, although they have different consumers, different change rates,
   and different compatibility semantics. ADR 0082 deliberately deferred module-pack assembly and
   per-module versioning "until explicit growth gates are hit"; the repository split is that gate.
2. **Capability namespaces are disjoint.** `PluginSpec` already carries `capabilities`,
   `requires_capabilities`, and `when` (`kernel/specs.py:63-67`), and the scheduler already emits
   E4010 when a plugin's required capabilities are unsatisfied
   (`kernel/scheduler/preflight.py:151-201`). But `available_capabilities` there is collected
   **only from plugin declarations** (`preflight.py:166-174`), while model-level capabilities are
   derived by `base.compiler.capabilities` from `topology/class-modules/capability-catalog.yaml`
   (ADR 0106). The two sets never meet, and no framework manifest declares
   `requires_capabilities` today — only tests do. Consequently a topology that describes
   functionality with no plugin able to serve it compiles silently.

The mental model to harmonize against is a programming-language ecosystem: an executable base
(compiler, runtime, builders), a standard library (classes, objects, strata), separately packaged
extensions, and an application that pins its dependencies and adds its own modules and data.
Most of the machinery for that model already exists in the runtime; it is simply not consistent
across artifact kinds and does not reach the project side.

This ADR fixes the target architecture **before** the physical repository split, so the new
repositories are created against a harmonized contract instead of being reworked afterwards.

## Decision

### 1. Framework identity

1. The framework is named **TAIGA** — *Topology Artifacts for Infrastructure Governance and
   Automation*. `framework_id: taiga`, repository `strateg/taiga`, project mount point `framework/`.
2. **Stratum / strata** becomes the normative term for the model layers L0–L7 in
   `topology/layer-contract.yaml` and documentation, replacing the generic word "layer".
3. Renaming `infra-topology-framework` → `taiga` touches 39 files / 139 occurrences and MUST be
   executed as a single migration inside the repository split, because framework locks are
   regenerated there anyway (`task framework:lock-refresh`).

### 2. Four planes replace one undifferentiated "framework"

| Plane | Contents | Language analogy | Versioned by |
|-------|----------|------------------|--------------|
| **Toolchain** (executable base) | `topology-tools/kernel/**` (registry, scheduler, facade — ADR 0113), the 6-stage lifecycle (ADR 0080), TRE entrypoints (ADR 0081 §2.3) | compiler + build driver | `framework_api_version` |
| **Library** (topology standard library) | `topology/class-modules/**`, `topology/object-modules/**` with their local templates (ADR 0078), `layer-contract.yaml`, `semantic-keywords.yaml`, `profile-map.yaml`, `product-profiles/**`, `product-bundles/**` | standard library | `model.lock.yaml` |
| **Extension** (plugin packs) | `topology-tools/plugins/**` as separately packaged, individually versioned packs | third-party packages | pack version |
| **Project** | `project.yaml`, `topology.yaml`, `topology/instances/**`, project classes/objects, `templates/**`, `plugins/**`, `secrets/**`, `generated/**`, deploy and control state | application | `framework.lock.yaml` (lockfile) |

Consequence: `distribution.include` stops being a single list. There are three artifact families
(toolchain, library, packs), each with its own version and integrity entry in
`framework.lock.yaml`, which becomes a true lockfile over three dependencies rather than one blob
hash.

### 3. One uniform extension chain for every artifact kind

All four artifact kinds MUST resolve through the same order, with one collision policy and one
diagnostic surface:

```
project → object-module (where applicable) → framework
```

1. **Classes and objects.** `class_modules_root` and `object_modules_root` become **lists of
   roots**. `module-index.yaml` is assembled as a union (the `class_modules` array already exists
   and is currently empty). A project MAY declare new classes and objects and combine them with
   library ones; compatibility is enforced at compile time. Framework identifiers MUST NOT be
   shadowed; project-defined classes MUST live in a project namespace (`class.<project>.*`).
   Project module versions are recorded in a separate `project.model.lock.yaml` so that the
   framework `model.lock.yaml` stays immutable on the project side.
2. **Templates.** `FileSystemLoader` becomes a `ChoiceLoader` over
   `<project>/templates` → `object-modules/<id>/templates` → `framework/topology-tools/templates`.
   Override by identical template name IS permitted and MUST be reported in compiler diagnostics.
   This differs deliberately from the plugin rule (ADR 0081 §3.3, extend-but-not-override): a
   project owns the presentation of its own artifacts, while plugin behaviour stays framework-owned.
3. **Product catalog.** `product-profiles/**` and `product-bundles/**` belong to the library plane,
   MUST be shipped in the framework artifact (`distribution.include` plus `_REQUIRED_PATHS` in
   `verify-framework-artifact-contents.py:10-20`), and MUST NOT be copied into project
   repositories (`bootstrap-project-repo.py:194` is retired). A project only selects `profile_id`
   and its `product_bundles` list in `project.yaml`.
4. **Plugins.** The chain already exists and is retained; it is aligned to the shared terminology
   and diagnostics introduced here.

### 4. Plugin packs as versioned artifacts with capability-driven activation

1. ADR 0082 Option B is **unfrozen**: a plugin pack is a directory with a manifest (`id`,
   `version`, `api_version`, `stage`, `depends_on`, `consumes`, `produces`), its own packaging, and
   an integrity entry in the lock. Pack-to-module binding already exists —
   `module-index.yaml` lists `object_modules[].plugins_manifest` (index-first discovery) — what is
   missing is versioning and packaging.
2. Capability-based activation reuses the existing kernel mechanism (`requires_capabilities`,
   `when`, E4010) rather than inventing a parallel one.
3. **A single capability namespace is declared.** Model-level capabilities (ADR 0106, derived from
   the class/object catalog) and kernel-level plugin capabilities become one namespace, or are
   bound by an explicit, validated mapping.
4. **A new inverse gate is required.** Where E4010 answers "a plugin requires a capability nobody
   provides", the pipeline MUST also answer "the topology requires a capability no installed plugin
   provides". This is a new diagnostic (proposed code E4013), raised in the `validate` stage,
   fail-fast, modelled on `validate_required_capabilities` (`preflight.py:151-201`). Missing
   functionality declared in topology becomes a compile error instead of silent omission.
5. Stage affinity (`discover→discoverers` … `build→builders`) and the prohibition on coupling
   outside `depends_on` / `consumes` / `produces` remain in force (CORE-004, ADR 0063, ADR 0080).

### 5. Assembly mechanics are normative as they already are, with a bounded delta

1. **Packs attach during `discover`, before `compile`.** The two-step bootstrap is preserved:
   `_bootstrap_phase()` (`compile-topology.py:921-1045`) validates the topology manifest, loads
   only the base manifest required to run discover
   (`_load_base_manifest_for_discover_bootstrap:418`), and resolves the framework lock; then
   `base.discover.manifest_loader` (`_bootstrap_discover_manifest_loader:654-676`) publishes
   `discovered_plugin_manifests` by walking `module-index.yaml` plus `project_plugins_root`.
   Registry construction (`kernel/specs.py`), dependency resolution
   (`kernel/registry/dependency_resolver.py`), preflight gates, and `STAGE_ORDER` follow. Delta:
   packs gain version and integrity and are recorded in the lock; the phase order does not change.
2. **One intermediate representation is mandatory and already exists.**
   `base.compiler.effective_model` (`plugins/manifests/compilers.yaml:521-541`) compiles topology
   together with the libraries into `effective_model_candidate`, committed in the main interpreter
   (ADR 0069 WS4); every terminal generator declares
   `depends_on: base.compiler.effective_model` (`generators.yaml:14,37,64,107,152,277,385`); it is
   materialized as `build/effective-topology.{json,yaml}` and tracked in
   `generated/<project>/artifact-manifest.json`. Final configuration artifacts MUST be generated
   from this IR only. Delta: the IR path becomes project-qualified (a shared `build/` root is
   invalid once projects live in their own repositories), and the IR MUST include the contribution
   of project-defined classes and objects per §3.1.
3. **Compilation MUST fail on missing extensions.** Already covered: missing dependency and unknown
   producer (`dependency_resolver.py:71,118-120`), api/model version incompatibility, E4010, and
   the E40xx family in `topology-tools/data/error-catalog.yaml:180-230`. Added by this ADR: the
   E4013 gate of §4.4.

### 6. Framework mounting is an implementation detail, not architecture

A project sees the framework at `framework/`. Whether that path is a Git submodule, a symlink or
junction to a sibling checkout, or an unpacked distribution zip is a development-process choice.
All three modes MUST remain supported, and project CI MUST verify the dist-zip mode independently
of whichever mode local development uses.

### 7. Recorded debt (not resolved by this ADR)

1. Residual project coupling inside framework assets: five `secrets_root: projects/home-lab/secrets`
   defaults in `plugins/manifests/compilers.yaml`, the same fallback at
   `plugins/compilers/instance_rows_compiler.py:765`, the path
   `../../../../projects/home-lab/secrets` in
   `templates/ansible/playbooks/vpn-gateway.yml.j2:19`, and comments in
   `templates/ansible/host_vars/wireguard_gateway.yml.j2:25,30`.
2. ADR 0081:57 designates `projects/home-lab` a required integration fixture of the framework
   repository. Once the project moves out, that role transfers to `projects/test-lab`, which is not
   ready (no `topology.yaml`, thin instances), while
   `tests/plugin_integration/test_tuc*.py` still reference home-lab data.

## Consequences

Improvements:

1. One extension model instead of four: a project extends classes, objects, templates, and plugins
   through the same chain, the same collision policy, and the same diagnostics.
2. Projects become genuinely extensible — declaring a new class or object no longer requires a
   framework change, which removes the main reason to fork the framework per deployment.
3. Missing functionality fails loudly at compile time instead of producing incomplete artifacts.
4. Three independently versioned artifact families make framework upgrades partial and auditable:
   a library bump no longer implies a toolchain bump.
5. The repository split becomes mechanical, because every cross-boundary reference resolves through
   declared roots rather than implicit monorepo paths.

Trade-offs and risks:

1. Unfreezing ADR 0082 introduces per-pack versioning, which is real ongoing release overhead;
   it is accepted because the split makes the monolithic artifact untenable.
2. Root lists and a `ChoiceLoader` chain add resolution ambiguity; it is contained by mandatory
   diagnostics that report which root served each artifact.
3. Template override permits project drift from framework defaults, deliberately, in exchange for
   project ownership of its own output.
4. Unifying capability namespaces touches ADR 0106 and ADR 0063 surfaces simultaneously and needs
   its own migration with contract tests.
5. `class.<project>.*` namespacing is a breaking convention for any project class introduced before
   it lands.

Migration and compatibility:

1. This ADR is architecture only; no implementation is included. Rule packs and
   `docs/ai/ADR-RULE-MAP.yaml` are updated when the status moves from Proposed to Accepted, per
   `docs/ai/rules/adr-governance.md`.
2. Sequencing: (1) this ADR, (2) uniform extension chains plus the E4013 gate with tests,
   (3) artifact-family split with lock schema change, (4) physical repository split and the
   `taiga` rename, (5) fixture role transfer to `projects/test-lab`.
3. Step 2 must land before step 4, otherwise the new project repository is created against the
   current inconsistent contract and has to be rebuilt.

## References

- Commit: (pending)
- Analysis: `adr/0114-analysis/responsibility-zones.md`
- Schema: `topology/framework.yaml` (`distribution.include`), `topology/module-index.yaml`,
  `topology/model.lock.yaml`, `projects/*/framework.lock.yaml`, `topology-tools/kernel/specs.py`
- Code: `topology-tools/compile-topology.py`, `topology-tools/kernel/scheduler/preflight.py`,
  `topology-tools/plugin_manifest_discovery.py`, `topology-tools/plugins/generators/base_generator.py`,
  `topology-tools/compiler_plugin_context.py`, `topology-tools/utils/bootstrap-project-repo.py`,
  `topology-tools/utils/verify-framework-artifact-contents.py`
- Docs: `docs/framework/FRAMEWORK-V5.md`, `docs/framework/PROJECT-BOOTSTRAP-AND-FRAMEWORK-INTEGRATION.md`,
  `docs/ai/AGENT-RULEBOOK.md`
