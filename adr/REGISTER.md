# ADR Register

| ADR | Title | Status | Date | Supersedes | Superseded By |
|-----|-------|--------|------|------------|---------------|
| [0001](0001-power-policy-layer-boundary.md) | Keep Physical Power in L1 and Outage Policies in L7 | Implemented | 2026-02-20 | - | - |
| [0002](0002-separate-data-and-power-links-in-l1.md) | Separate Data Links and Power Links in L1 | Implemented | 2026-02-20 | - | - |
| [0003](0003-data-links-naming-and-power-constraints.md) | Rename L1 Physical Links to Data Links and Constrain Data-Link Power | Implemented | 2026-02-20 | - | - |
| [0004](0004-l2-firewall-policy-references-and-validation.md) | Enforce Explicit L2 Firewall Policy References and Validation Semantics | Implemented | 2026-02-20 | - | - |
| [0005](0005-diagram-generation-determinism-and-binding-visibility.md) | Improve Diagram Generation Determinism and Firewall Binding Visibility | Implemented | 2026-02-20 | - | - |
| [0006](archive/0006-mermaid-icon-mode-with-fallback.md) | Add Mermaid Icon Mode with Template Fallback | Superseded | 2026-02-20 | - | [0008](archive/0008-mermaid-icon-node-default-and-runtime-pack-registration.md) |
| [0007](archive/0007-icon-legend-and-complete-device-icon-coverage.md) | Add Icon Legend Page and Complete Device Icon Coverage | Superseded | 2026-02-20 | - | [0027](0027-mermaid-rendering-strategy-consolidation.md) |
| [0008](archive/0008-mermaid-icon-node-default-and-runtime-pack-registration.md) | Make Mermaid Icon-Node the Default and Require Runtime Icon Pack Registration | Superseded | 2026-02-20 | [0006](archive/0006-mermaid-icon-mode-with-fallback.md) | [0027](0027-mermaid-rendering-strategy-consolidation.md) |
| [0009](archive/0009-robust-icon-pack-discovery-and-render-validation.md) | Robust Mermaid Icon Pack Discovery and Render Validation | Superseded | 2026-02-20 | - | [0027](0027-mermaid-rendering-strategy-consolidation.md) |
| [0010](archive/0010-regeneration-pipeline-mermaid-quality-gate.md) | Add Mermaid Render Quality Gate to Regeneration Pipeline | Superseded | 2026-02-20 | - | [0027](0027-mermaid-rendering-strategy-consolidation.md) |
| [0011](archive/0011-l1-physical-storage-taxonomy-and-l3-disk-binding.md) | L1 Physical Storage Taxonomy and L3 Disk Binding | Superseded | 2026-02-20 | - | [0029](0029-storage-taxonomy-and-layer-boundary-consolidation.md) |
| [0012](archive/0012-separate-l1-physical-disk-specs-from-l3-logical-storage-mapping.md) | Separate L1 Physical Disk Specs from L3 Logical Storage Mapping | Superseded | 2026-02-21 | - | [0029](0029-storage-taxonomy-and-layer-boundary-consolidation.md) |
| [0013](archive/0013-l1-storage-mount-taxonomy-soldered-replaceable-removable.md) | L1 Storage Mount Taxonomy for Soldered, Replaceable, and Removable Media | Superseded | 2026-02-21 | - | [0029](0029-storage-taxonomy-and-layer-boundary-consolidation.md) |
| [0014](archive/0014-l1-storage-slots-preferred-model-with-legacy-compatibility.md) | Use L1 Storage Slots as Preferred Model with Legacy Compatibility | Superseded | 2026-02-21 | - | [0015](archive/0015-drop-legacy-storage-compatibility-after-storage-slots-migration.md), [0029](0029-storage-taxonomy-and-layer-boundary-consolidation.md) |
| [0015](archive/0015-drop-legacy-storage-compatibility-after-storage-slots-migration.md) | Drop Legacy L1 Storage Compatibility After Storage Slots Migration | Superseded | 2026-02-21 | [0014](archive/0014-l1-storage-slots-preferred-model-with-legacy-compatibility.md) | [0029](0029-storage-taxonomy-and-layer-boundary-consolidation.md) |
| [0016](archive/0016-l1-storage-media-registry-and-slot-attachments.md) | L1 Storage Media Registry and Slot Attachments | Superseded | 2026-02-21 | - | [0029](0029-storage-taxonomy-and-layer-boundary-consolidation.md) |
| [0017](archive/0017-topology-tools-modular-refactor-validation-generation.md) | Modular Refactor of topology-tools into Validation and Generation Domains | Superseded | 2026-02-21 | - | [0028](0028-topology-tools-architecture-consolidation.md) |
| [0018](archive/0018-generation-common-loader-and-output-preparation.md) | Shared Generation Common Module for Layered Topology Loading and Output Directory Preparation | Superseded | 2026-02-21 | - | [0028](0028-topology-tools-architecture-consolidation.md) |
| [0019](archive/0019-proxmox-answer-layered-topology-only.md) | Proxmox Answer Generator Uses Layered Topology Only (No Legacy Root Sections) | Superseded | 2026-02-21 | - | [0028](0028-topology-tools-architecture-consolidation.md) |
| [0020](archive/0020-topology-tools-scripts-domain-layout.md) | Co-locate Generation and Validation Under topology-tools/scripts | Superseded | 2026-02-21 | - | [0028](0028-topology-tools-architecture-consolidation.md) |
| [0021](archive/0021-docs-generation-moved-to-scripts-generation-docs.md) | Move Documentation Generation Core into scripts/generation/docs | Superseded | 2026-02-21 | - | [0028](0028-topology-tools-architecture-consolidation.md) |
| [0022](archive/0022-docs-diagram-module-canonical-location.md) | Use scripts/generation/docs/docs_diagram.py as Canonical Diagram Module | Superseded | 2026-02-21 | - | [0028](0028-topology-tools-architecture-consolidation.md) |
| [0023](archive/0023-terraform-generators-and-templates-domain-layout.md) | Terraform Generators and Templates Domain Layout | Superseded | 2026-02-21 | - | [0028](0028-topology-tools-architecture-consolidation.md) |
| [0024](archive/0024-validators-namespace-alignment.md) | Rename Validation Package Namespace to validators | Superseded | 2026-02-21 | - | [0028](0028-topology-tools-architecture-consolidation.md) |
| [0025](archive/0025-generator-protocol-and-cli-base-class.md) | Generator Protocol and CLI Base Class | Superseded | 2026-02-21 | - | [0028](0028-topology-tools-architecture-consolidation.md) |
| [0026](0026-l3-l4-taxonomy-refactoring-storage-chain-and-platform-separation.md) | L3/L4 Taxonomy Refactoring - Storage Chain and Platform Separation | Implemented | 2026-02-21 | - | - |
| [0027](0027-mermaid-rendering-strategy-consolidation.md) | Consolidate Mermaid Rendering Strategy and Quality Gates | Implemented | 2026-02-22 | [0007](0007-icon-legend-and-complete-device-icon-coverage.md), [0008](0008-mermaid-icon-node-default-and-runtime-pack-registration.md), [0009](0009-robust-icon-pack-discovery-and-render-validation.md), [0010](0010-regeneration-pipeline-mermaid-quality-gate.md) | - |
| [0028](0028-topology-tools-architecture-consolidation.md) | Consolidate topology-tools Architecture and Module Boundaries | Implemented | 2026-02-22 | [0017](0017-topology-tools-modular-refactor-validation-generation.md), [0018](0018-generation-common-loader-and-output-preparation.md), [0019](0019-proxmox-answer-layered-topology-only.md), [0020](0020-topology-tools-scripts-domain-layout.md), [0021](0021-docs-generation-moved-to-scripts-generation-docs.md), [0022](0022-docs-diagram-module-canonical-location.md), [0023](0023-terraform-generators-and-templates-domain-layout.md), [0024](0024-validators-namespace-alignment.md), [0025](0025-generator-protocol-and-cli-base-class.md) | - |
| [0029](0029-storage-taxonomy-and-layer-boundary-consolidation.md) | Consolidate Storage Taxonomy and L1/L3 Boundary Contract | Implemented | 2026-02-22 | [0011](0011-l1-physical-storage-taxonomy-and-l3-disk-binding.md), [0012](0012-separate-l1-physical-disk-specs-from-l3-logical-storage-mapping.md), [0013](0013-l1-storage-mount-taxonomy-soldered-replaceable-removable.md), [0014](0014-l1-storage-slots-preferred-model-with-legacy-compatibility.md), [0015](0015-drop-legacy-storage-compatibility-after-storage-slots-migration.md), [0016](0016-l1-storage-media-registry-and-slot-attachments.md) | - |
| [0030](0030-l2-network-layer-enhancements.md) | L2 Network Layer Enhancements | Implemented | 2026-02-22 | - | - |
| [0031](archive/0031-layered-topology-toolchain-contract-alignment.md) | Layered Topology Toolchain Contract Alignment | Superseded | 2026-02-22 | - | [0062](0062-modular-topology-architecture-consolidation.md), [0069](0069-plugin-first-compiler-refactor-and-thin-orchestrator.md), [0080](0080-unified-build-pipeline-stage-phase-and-plugin-data-bus.md) |
| [0032](archive/0032-l3-data-modularization-and-layer-contracts.md) | L3 Data Modularization and Layer Contracts | Superseded | 2026-02-22 | - | [0062](0062-modular-topology-architecture-consolidation.md) |
| [0033](archive/0033-toolchain-contract-rebaseline-after-modularization.md) | Toolchain Contract Rebaseline After Modularization | Superseded | 2026-02-22 | - | [0062](0062-modular-topology-architecture-consolidation.md), [0080](0080-unified-build-pipeline-stage-phase-and-plugin-data-bus.md) |
| [0034](archive/0034-l4-platform-modularization-and-runtime-taxonomy.md) | L4 Platform Modularization (MVP) | Superseded | 2026-02-22 | - | [0062](0062-modular-topology-architecture-consolidation.md) |
| [0035](archive/0035-l4-host-os-foundation-and-runtime-substrates.md) | L4 Host OS Foundation and Runtime Substrate Contracts | Superseded | 2026-02-22 | - | [0039](0039-l4-host-os-installation-storage-contract-clarification.md), [0064](0064-os-taxonomy-object-property-model.md) |
| [0036](archive/0036-l2-host-os-reference-in-network-allocations.md) | Host OS Reference in Network Allocations | Superseded | 2026-02-22 | - | [0038](0038-network-binding-contracts-phase1.md) |
| [0037](archive/0037-l2-network-substrate-and-workload-binding-contracts.md) | L2 Network Substrate and Workload Binding Contracts | Superseded | 2026-02-22 | - | [0038](0038-network-binding-contracts-phase1.md) |
| [0038](0038-network-binding-contracts-phase1.md) | Network Binding Contracts Phase 1 (Gradual Evolution) | Implemented | 2026-02-22 | [0037](0037-l2-network-substrate-and-workload-binding-contracts.md) | - |
| [0039](0039-l4-host-os-installation-storage-contract-clarification.md) | Host OS Installation Storage Contract (Strict) | Implemented | 2026-02-23 | - | - |
| [0040](0040-l0-l5-canonical-ownership-and-refactoring-plan.md) | L0-L5 Canonical Ownership and Refactoring Plan | Implemented | 2026-02-23 | - | - |
| [0041](0041-l4-workload-network-attachment-typing.md) | L4 Workload Network Attachment Typing | Implemented | 2026-02-24 | - | - |
| [0042](0042-l5-services-modularization.md) | L5 Services Modularization | Implemented | 2026-02-24 | - | - |
| [0043](0043-l0-l5-harmonization-and-cognitive-load-reduction.md) | L0-L5 Harmonization and Cognitive Load Reduction | Implemented | 2026-02-24 | - | - |
| [0044](0044-ip-derivation-from-refs.md) | IP Derivation from Refs | Implemented | 2026-02-24 | - | - |
| [0045](archive/0045-model-and-project-improvements.md) | Improvements to project model, development workflow and automation | Superseded | 2026-02-25 | - | [0066](0066-plugin-testing-and-ci-strategy.md), [0075](0075-framework-project-separation.md), [0077](0077-go-task-developer-orchestration.md) |
| [0046](0046-generators-architecture-refactoring.md) | Generators Architecture Refactoring | Implemented (All 6 phases complete) | 2026-02-25 | - | - |
| [0047](0047-l6-observability-modularization.md) | L6 Observability Modularization | Implemented (Phase 1-2; trigger-gated) | 2026-02-26 | - | - |
| [0048](0048-topology-v4-architecture-consolidation.md) | Topology v4 Architecture Consolidation | Implemented (v4 archived) | 2026-02-28 | [0049](0049-mikrotik-bootstrap-automation.md), [0050](0050-generated-directory-restructuring.md) | - |
| [0049](archive/0049-mikrotik-bootstrap-automation.md) | MikroTik Bootstrap Automation | Superseded | 2026-02-28 | - | [0048](0048-topology-v4-architecture-consolidation.md), [0057](0057-mikrotik-netinstall-bootstrap-and-terraform-handover.md) |
| [0050](0050-generated-directory-restructuring.md) | Generated Directory Restructuring | Implemented | 2026-02-28 | - | [0048](0048-topology-v4-architecture-consolidation.md) |
| [0051](archive/0051-ansible-runtime-and-secrets.md) | Ansible Runtime, Inventory, and Secret Boundaries | Superseded | 2026-03-01 | - | [0072](0072-unified-secrets-management-sops-age.md) |
| [0052](0052-build-pipeline-after-ansible.md) | Deploy Package Assembly Over Accepted Ansible Runtime | Implemented | 2026-03-01 | - | - |
| [0053](archive/0053-dist-first-deploy-cutover.md) | Optional Dist-First Deploy Cutover | Superseded | 2026-03-01 | - | [0085](0085-deploy-bundle-and-runner-workspace-contract.md) |
| [0054](archive/0054-local-inputs-directory.md) | Local Inputs Directory | Superseded | 2026-03-01 | - | [0072](0072-unified-secrets-management-sops-age.md) |
| [0055](0055-manual-terraform-extension-layer.md) | Manual Terraform Extension Layer | Implemented | 2026-03-01 | - | - |
| [0056](0056-native-execution-workspace.md) | Native Execution Workspace Outside Generated Roots | Implemented | 2026-03-01 | - | - |
| [0057](0057-mikrotik-netinstall-bootstrap-and-terraform-handover.md) | MikroTik Chateau Netinstall Bootstrap and Terraform Handover | Implemented | 2026-03-05 | - | - |
| [0058](archive/0058-core-abstraction-layer.md) | Core Abstraction Layer and Device Module Architecture | Superseded | 2026-03-06 | - | [0059](archive/0059-repository-split-and-class-object-instance-module-contract.md), [0062](0062-modular-topology-architecture-consolidation.md) |
| [0059](archive/0059-repository-split-and-class-object-instance-module-contract.md) | Repository Split and Class-Object-Instance Module Contract | Superseded | 2026-03-06 | [0058](archive/0058-core-abstraction-layer.md) | [0062](0062-modular-topology-architecture-consolidation.md) |
| [0060](archive/0060-yaml-to-json-compiler-diagnostics-contract.md) | YAML-to-JSON Compiler and Diagnostics Contract | Superseded | 2026-03-06 | - | [0062](0062-modular-topology-architecture-consolidation.md) |
| [0061](archive/0061-base-repo-versioned-class-object-instance-and-test-profiles.md) | Base Repo with Versioned Class-Object-Instance and Test Profiles | Superseded | 2026-03-06 | - | [0062](0062-modular-topology-architecture-consolidation.md) |
| [0062](0062-modular-topology-architecture-consolidation.md) | Topology v5 - Modular Class-Object-Instance Architecture | Implemented (51 classes, 120 objects, 151 instances) | 2026-03-06 | [0058](0058-core-abstraction-layer.md), [0059](0059-repository-split-and-class-object-instance-module-contract.md), [0060](0060-yaml-to-json-compiler-diagnostics-contract.md), [0061](0061-base-repo-versioned-class-object-instance-and-test-profiles.md) | - |
| [0063](0063-plugin-microkernel-for-compiler-validators-generators.md) | Plugin Microkernel for Compiler, Validators, and Generators | Implemented (plugin-first runtime; legacy fallback removed) | 2026-03-06 | - | - |
| [0064](0064-os-taxonomy-object-property-model.md) | Software Stack Taxonomy - Firmware and OS as Separate Entities | Implemented - Two-Entity Model (Firmware + OS) | 2026-03-08 | - | - |
| [0065](0065-plugin-api-contract-specification.md) | Plugin API Contract Specification | Implemented | 2026-03-09 | - | - |
| [0066](0066-plugin-testing-and-ci-strategy.md) | Plugin Testing and CI Strategy | Implemented | 2026-03-09 | - | - |
| [0067](0067-entity-specific-identifier-keys-in-yaml-authoring.md) | Entity-Specific Identifier Keys in YAML Authoring | Implemented (Hard Cutover) | 2026-03-10 | - | - |
| [0068](0068-object-yaml-as-instance-template-with-explicit-overrides.md) | Object YAML Template with Typed Instance Placeholders | Implemented | 2026-03-10 | - | - |
| [0069](0069-plugin-first-compiler-refactor-and-thin-orchestrator.md) | Plugin-First Compiler Refactor and Thin Orchestrator | Implemented | 2026-03-10 | - | - |
| [0070](0070-acceptance-testing-tuc-framework.md) | Acceptance Testing TUC Framework | Implemented (4 TUCs) | 2026-03-11 | - | - |
| [0071](0071-sharded-instance-files-and-flat-instances-root.md) | Sharded Instance Files and Flat `instances` Root | Implemented (151 instance files) | 2026-03-11 | - | - |
| [0072](0072-unified-secrets-management-sops-age.md) | Unified Secrets Management with SOPS and age | Implemented | 2026-03-17 | [0051](0051-ansible-runtime-and-secrets.md), [0054](0054-local-inputs-directory.md) | - |
| [0073](0073-field-annotations-and-secret-conflict-resolution.md) | Field Annotation System and Secret Conflict Resolution | Implemented | 2026-03-18 | - | - |
| [0074](0074-v5-generator-architecture.md) | V5 Generator Architecture (Contract-First) | Final | 2026-03-19 | - | - |
| [0075](0075-framework-project-separation.md) | Monorepo Framework/Project Boundary (Stage 1) | Implemented | 2026-03-20 | - | - |
| [0076](0076-framework-distribution-and-multi-repository-extraction.md) | Framework Distribution and Multi-Repository Extraction (Stage 2) | Implemented (Stage 2 + Phase 13 cutover complete) | 2026-03-20 | - | - |
| [0077](0077-go-task-developer-orchestration.md) | Go-Task as Developer Orchestration Layer | Implemented (39 tasks) | 2026-03-21 | - | - |
| [0078](0078-object-module-local-template-layout.md) | Object-Module Local Plugin Ownership and Runtime Layout | Implemented | 2026-03-21 | - | - |
| [0079](0079-v5-documentation-and-diagram-generation-migration.md) | V5 Documentation and Diagram Generation Migration | Implemented | 2026-03-24 | - | - |
| [0080](0080-unified-build-pipeline-stage-phase-and-plugin-data-bus.md) | Unified Build Pipeline, Stage-Phase Lifecycle, and Contractual Plugin Data Bus | Implemented (6 stages, 98 plugins) | 2026-03-26 | - | - |
| [0081](0081-framework-runtime-artifact-and-1-n-project-repository-model.md) | Framework Runtime Artifact and 1:N Project Repository Model | Implemented (artifact-first canonical) | 2026-03-29 | - | - |
| [0082](0082-plugin-module-pack-composition-and-index-first-discovery-analysis.md) | Plugin Module-Pack Composition and Index-First Discovery Analysis | Implemented (A+ index governance) | 2026-03-29 | - | - |
| [0083](0083-unified-node-initialization-contract.md) | Unified Node Initialization Contract and Deploy-Domain Initialization Phase | Implemented (scaffold complete, hardware pending) | 2026-03-30 | - | - |
| [0084](0084-cross-platform-dev-plane-and-linux-deploy-plane.md) | Cross-Platform Dev Plane and Linux Deploy Plane | Implemented | 2026-03-31 | - | - |
| [0085](0085-deploy-bundle-and-runner-workspace-contract.md) | Deploy Bundle and Runner Workspace Contract | Implemented | 2026-03-31 | [0053](0053-dist-first-deploy-cutover.md) | - |
| [0086](0086-flatten-plugin-hierarchy-and-reduce-granularity.md) | Flatten Plugin Hierarchy and Reduce Plugin Granularity | Implemented | 2026-04-01 | ADR 0063 Section 4B | - |
| [0087](0087-unified-container-ontology-l4-l5.md) | Unified Container Ontology for L4/L5 | Implemented (Phase 1 PASSED) | 2026-04-03 | - | - |
| [0088](0088-semantic-keyword-registry-and-at-prefixed-meta-fields.md) | Semantic Keyword Registry and `@`-Prefixed Meta Fields | Implemented | 2026-04-05 | [0067](0067-entity-specific-identifier-keys-in-yaml-authoring.md) | - |
| [0089](0089-soho-product-profile-and-bundle-contract.md) | SOHO Product Profile and Bundle Contract | Implemented (complete) | 2026-04-05 | - | - |
| [0090](0090-soho-operator-lifecycle-and-task-ux-contract.md) | SOHO Operator Lifecycle and Task UX Contract | Implemented (complete) | 2026-04-05 | - | - |
| [0091](0091-soho-readiness-evidence-and-handover-artifacts.md) | SOHO Readiness Evidence and Handover Artifacts | Implemented (complete) | 2026-04-05 | - | - |
| [0092](0092-smart-artifact-generation-and-hybrid-rendering.md) | Smart Artifact Generation and Hybrid Rendering | Implemented (Waves 1-4 complete; AI extracted to ADR0094) | 2026-04-05 | - | - |
| [0093](0093-artifact-plan-schema-and-generator-runtime-integration.md) | ArtifactPlan Schema and Generator Runtime Integration | Implemented (Waves 1-5 complete; compatibility mode closed) | 2026-04-05 | - | - |
| [0094](0094-ai-advisory-mode-for-artifact-generation.md) | AI Advisory Mode for Artifact Generation | Implemented (Waves 1-4 complete; checklist closed) | 2026-04-06 | ADR 0092 D10 | - |
| [0095](0095-topology-inspection-and-introspection-toolkit.md) | Topology Inspection and Introspection Toolkit | Implemented (Waves 0-E complete, see `adr/0095-analysis/COMPLETION-REPORT.md`) | 2026-04-12 | - | - |
| [0096](0096-ai-agent-rulebook-and-adr-derived-context-contract.md) | AI Agent Rulebook and ADR-Derived Context Contract | Implemented (Waves 1-3 complete) | 2026-04-10 | - | - |
| [0097](0097-subinterpreter-parallel-plugin-execution.md) | Actor-Style Dataflow Execution for Plugins on Python 3.14 Subinterpreters | Implemented (PR1-PR5 complete) | 2026-04-15 | - | - |
| [0098](0098-python-3-14-platform-migration.md) | Python 3.14 Platform Migration | Implemented (Phase A+B Complete, Phase C Deferred) | 2026-04-13 | - | - |
| [0099](0099-refactor-test-architecture-for-snapshot-envelope-pipeline-runtime.md) | Refactor Test Architecture for Snapshot/Envelope Pipeline Runtime | Implemented | 2026-04-15 | [0097](0097-subinterpreter-parallel-plugin-execution.md) | - |
| [0100](0100-unified-topology-graph-generator-and-filter-contract.md) | Unified Topology Graph Generator and Filter Contract | Implemented | 2026-04-22 | - | - |
| [0101](0101-layer-harmonization-os-runtime-and-foundation-boundaries.md) | Layer Harmonization for OS Runtime and Foundation Boundaries | Implemented (Mode H active) | 2026-04-23 | - | - |
| [0102](0102-derived-instance-layer-semantics-and-path-decoupling.md) | Derived Instance Layer Semantics and Path-Decoupled Instance Layout | Implemented | 2026-04-23 | - | - |
| [0103](0103-runtime-reconciliation-status-replaces-static-instance-status.md) | Runtime Reconciliation Status Replaces Static Instance Status | Partially Implemented (Wave 3 only, Waves 1/2/4 Cancelled) | 2026-06-07 | - | - |
| [0104](0104-ansible-role-generation-from-topology.md) | Ansible Role Generation from Topology | Implemented | 2026-06-09 | - | - |
| [0105](0105-device-state-commit-and-rollback-contract.md) | Device State Management Using Industry Best Practices | Deferred | 2026-06-10 | - | - |
| [0106](0106-capability-driven-plugin-architecture.md) | Capability-Driven Plugin Architecture | Implemented | 2026-06-11 | - | - |
| [0107](0107-host-placement-defaults-and-on-directive.md) | Host Placement Defaults with `@on` Directive | Implemented | 2026-06-17 | 2026-06-18 | - |
| [0108](0108-specification-driven-development-contract.md) | Specification-Driven Development Contract | Deferred | 2026-06-19 | - | - |
| [0109](0109-network-segmentation-zone-based-architecture.md) | Network Segmentation with Zone-Based Architecture | Implemented | 2026-06-22 | - | - |
| [0110](0110-universal-network-zone-vlan-mechanism.md) | Security Matrix and Trust Zone Configuration | Implemented | 2026-06-22 | - | - |
| [0111](0111-ip-address-derivation-from-vlan.md) | IP Address Derivation from VLAN Instances | Implemented | 2026-06-22 | - | - |
| [0112](0112-projection-domain-package-refactor.md) | Projection Domain Package Refactor | Implemented | 2026-07-03 | 2026-07-04 | - |
| [0113](0113-kernel-runtime-decomposition-registry-scheduler-facade.md) | Kernel Runtime Decomposition into Registry, Scheduler, and Facade | Implemented | 2026-07-13 | - | - |
| [0114](0114-taiga-architecture-harmonization.md) | TAIGA Architecture Harmonization across Toolchain, Library, Extension, and Project Planes | Proposed | 2026-07-30 | - | - |
| [0115](0115-incremental-hash-based-deploy-idempotency.md) | Incremental Hash-Based Deploy Idempotency Contract | Proposed | 2026-08-02 | - | - |
| [0116](0116-peripheral-device-model-and-connection-type-hierarchy.md) | Peripheral Device Model and Connection-Type Hierarchy | Implemented | 2026-09-06 | - | - |
| [0117](0117-iot-endpoint-layer-mixing-technical-debt.md) | IoT Endpoint Layer Separation | Implemented | 2026-09-06 | - | - |
| [0118](0118-universal-container-network-model.md) | Universal Container Network Model | Accepted | 2026-09-09 | - | - |
| [0119](0119-firewall-rule-ordering-contract.md) | Firewall Rule Ordering Contract | Accepted | 2026-09-09 | - | - |

## ADR 0118/0119 revision — 2026-09-10

- ADR 0118 remains **Proposed**: one attachment/publication/policy model replaces
  the contradictory earlier D1-D21; capability-qualified scope and explicit legacy boundary.
- ADR 0119 remains **Proposed**: one authorization-preserving plan replaces
  producer priorities; formal obligations, safe transition and observed-state contract.
- ADR 0110 remains **Implemented** for its existing R1-R6 behavior; added an
  explicit cross-reference to the unimplemented strict-profile proposal.
- Supporting contracts: [migration and acceptance](0118-analysis/MIGRATION-AND-ACCEPTANCE.md),
  [formal obligations](0119-analysis/FORMAL-CONTRACT.md),
  [assurance profile](0119-analysis/ASSURANCE-PROFILE.md).
- No topology migration, backend qualification or compliance approval is implied.

## ADR 0118/0119 revision 2 — 2026-09-10 (SPC rebuild)

- ADR 0118 stays **Proposed**: adds D4.1 legacy-to-strict translation, a
  derived-field contract and D8 making the authoring surface a measured property.
- ADR 0119 stays **Proposed**: states plan ownership against ADR 0110's M1-B
  enforcer ownership and restores the explicit terminal-deny obligation.
- ADR 0110 stays **Implemented**; its R1-R6 behavior and `managed_by_ref`
  semantics are unchanged and now referenced explicitly by the proposal.
- Change record: [SPC rebuild](0118-analysis/SPC-REBUILD-2026-09-10.md).
- Still no migration, backend qualification, deployment or compliance approval.

## ADR 0118/0119 implementation analysis — 2026-09-10

- [Final implementation proposal](0118-analysis/FINAL-IMPLEMENTATION-PROPOSAL.md)
  and [reproducible evidence](0118-analysis/FINAL-PROPOSAL-EVIDENCE-2026-09-10.md).
- Recommends named source mappings, explicit binding lifecycle, two compiler
  plugins and a qualified transaction-based pilot; records baseline failures.
- Analysis only: these refinements are not adopted into normative rev 2 yet.
  Both ADRs remain **Proposed**; no runtime change, migration or deployment.

## ADR 0118/0119 revision 3 — final architecture proposal, 2026-09-10

- Both ADRs remain **Proposed**; [final architecture proposal](0118-analysis/FINAL-ARCHITECTURE-PROPOSAL.md)
  is the current design review target, with synchronized examples/formal contract.
- Resolves named identity/inheritance, allocation ownership, binding lifecycle,
  original/frontend coordinate semantics, bounded profile and writer responsibilities.
- Supersedes rev 2 array authoring sketches and blanket consumer/domain input
  confusion. Earlier implementation exploration is historical and not adopted.
- No plugin count, backend priority, execution tool, code change or deployment
  is approved by this design revision. Human architectural acceptance is pending.

## ADR 0118/0119 revision 3.1 — applicability corrections, 2026-09-10

- [Final proposal](0118-analysis/FINAL-ARCHITECTURE-PROPOSAL.md) updated from the
  [rev 3 applicability review](../docs/reports/2026-09-10-adr0118-0119-rev3-applicability-review.md).
- [Review response and evidence](0118-analysis/REV3-APPLICABILITY-RESPONSE.md)
  records accepted conditions, qualified claims and fresh static counts.
- Adds route/tunnel/interface-NAT ownership, downward runtime realization,
  framework/core semantic authority and the existing Terraform/Ansible boundary.
- Clarifies scoped network version keys, local-key grammar, zone migration,
  planned-intent visibility, shared-chain composition and OOB prerequisites.
- Runtime, topology and generated artifacts are unchanged by the revision itself.

## ADR 0118/0119 architecture acceptance — 2026-09-10 (gate G0a)

- Both ADRs move from **Proposed** to **Accepted**: the architecture contract
  AD-01..AD-10 is adopted as the project's target network model.
- Basis: [rev 3.1 applicability review](../docs/reports/2026-09-10-adr0118-0119-rev31-applicability-review.md),
  which found all five rev 3 conditions closed, plus the
  [SPC acceptability review](../docs/reports/2026-09-10-adr0118-0119-spc-acceptability-review.md).
- Two remaining documentation defects were corrected before acceptance: the legacy
  upward `container_ref` inventory is 6 files, not 4, and authored `routing_mark`
  appears in 9 files, both now in the migration plan section 2C; acceptance scenario
  A24 makes single-source derivation of zone membership and `vlan_cidr_map` checkable.
- **What acceptance does not mean.** Gate G0b (named owners for HA-01..HA-10 and the
  tailoring record) is **not** closed. Gates G1-G8 are open, A01-A24 are unclosed, no
  backend is qualified, and no deployment, migration or device change is authorized.
  Compliance claims remain bounded by the assurance profile.
- ADR 0110 stays **Implemented**; its R1-R6 legacy behavior is unchanged, and the
  strict profile is not active anywhere.
- Implementation planning followed in the same SPC cycle: the gate-by-gate
  [implementation plan](0118-analysis/IMPLEMENTATION-PLAN.md) derives structure
  from AD-01..AD-10, uses the gate as its unit, and records four open decisions
  with owners. It authorizes no code, migration or deployment.

## ADR 0118/0119 implementation-plan review — 2026-09-11

- [Plan revision 2](0118-analysis/IMPLEMENTATION-PLAN.md) replaces the unsupported
  independent-prework claim and missing I01-I41 registry with W01-W12 dependencies.
- [Review](0118-analysis/IMPLEMENTATION-PLAN-REVIEW-2026-09-11.md) records findings,
  baseline evidence and corrections: numeric diagnostics at G1, pre-validation
  specialization, immutable bundle closure at G4, scoped conformance and safe ownership.
- ADRs remain **Accepted**, implementation unimplemented; G0b/G1-G8 and A01-A24
  are not closed by this documentation review. No source migration or deployment.

## ADR 0118/0119 revision 3.2 — capability satisfaction, 2026-09-11

- Both ADRs remain **Accepted**, implementation **not implemented**. At the user's
  direction the [architecture proposal](0118-analysis/FINAL-ARCHITECTURE-PROPOSAL.md)
  adds AD-11: derived requirements, scoped offers and evidence-relative resolution.
- [Shared capability contract](0119-analysis/CAPABILITY-SATISFACTION-CONTRACT.md)
  reuses ADR 0106 catalog/packs/derivation. No second intent database, runtime stage,
  automatic topology fallback, grant or transfer of resource ownership is introduced.
- [Formal contract](0119-analysis/FORMAL-CONTRACT.md) adds SEC-CAP; selected
  versions/strategies/conditions and evidence bind to intent/plan/bundle digests.
  Offline candidate readiness remains distinct from fresh live activation evidence.
- [Plan revision 4](0118-analysis/IMPLEMENTATION-PLAN.md) extends W03/W04/W06/W07/
  W08/W10/W11 without discarding revision 3 diagnostic, governance, stop/reversibility
  or entry-condition provisions. [Acceptance](0118-analysis/MIGRATION-AND-ACCEPTANCE.md)
  adds A25-A32; existing A01-A24 remain unchanged.
- G0a base acceptance and its historical reviews are retained; those reviews are
  not independent review evidence for rev 3.2. G0b/G1-G8 and A01-A32 remain open.
  No catalog/runtime/schema implementation, device change, qualification or deploy.

## ADR 0118/0119 rev 3.2a — capability amendment supplement, 2026-09-11

- SPC review of rev 3.2. Both ADRs remain **Accepted**, implementation **not
  implemented**. No decision is withdrawn; three under-specified points in AD-11
  are corrected and the amendment's repository-level premises are re-grounded.
- **Determinism:** rev 3.2 required offer content to be hash-bound while listing
  qualification evidence references as offer content, which contradicts its own
  claim that a fresh identical observation leaves the semantic plan unchanged.
  [Contract §4.1](0119-analysis/CAPABILITY-SATISFACTION-CONTRACT.md) now splits the
  offer into a digest-bearing semantic core and a separately hashed evidence annex;
  [formal contract](0119-analysis/FORMAL-CONTRACT.md) binds the split to `W_g`.
- **Inventory:** `complete(R_g, Omega_g)` was self-referential. Omega_g now has an
  external lower bound anchored to the ADR 0118 D6 path list, shared with SEC-PATH.
- **Status vocabulary:** the tri-state is mapped one-directionally onto the
  pre-existing `unsupported` flow verdict, so neither collapses into the other.
- **Corrected premises:** `E8020`/`E8021`/`E3202` are raised in code but are not
  registered in `topology-tools/data/error-catalog.yaml`, so rev 3.2's instruction
  to preserve their meaning had no registered subject; the capability catalog
  reaches runtime as identifiers only and is a closed vocabulary, so offers cannot
  live in it; the acceptance baseline pointer was five commits stale.
- **Vocabulary debt:** six recorded enforcement gaps (acceleration/FastTrack, the
  Docker `DOCKER-USER` versus nftables hook, IPv6 family, the Proxmox generator
  STUB, the nine unrendered LXC attachments, `untracked` admission) are mapped onto
  existing A-cases; four still lack any catalog identifier and are therefore
  unverified by construction until W03 registers one.
- A25-A32 gain terminal evidence levels. Registers are unchanged: A01-A32 for
  acceptance, W01-W12 for work. No new ADR, gate, plugin, catalog entry, runtime
  change, test result, qualification or deployment authorization.

## ADR 0118 D7 amendment — authoritative-field contract, 2026-09-11

- Adds the inverse of the derived-field contract: an object supplies reusable
  shape and defaults and must not author a value that identifies or classifies
  one concrete entity.
- Established by two findings, not by argument. `obj.network.vlan.vpn_tunnel`
  declared a VLAN id and prefix that all four instances overrode; the values were
  reachable by none of them and a fifth VLAN would have inherited a collision.
  `obj.network.trust_zone.vpn_tunnel` declared a security level and isolation
  flag correct for one of its two zones and wrong for the other.
- Both were corrected as parity-preserving layering moves: effective values and
  rendered artifacts unchanged, verified byte-for-byte.
- Open and deliberately not folded in: `inst.trust_zone.vpn_exit` still renders
  as "VPN Tunnel Zone" because it inherited that name. Correcting it changes
  rendered comments and is a separate reviewed change.
- No gate closed, nothing qualified, no deployment implied.

## ADR0118/0119 — approval producer implementation proposal, 2026-09-15

- Adds [proposed approval producer contract](0119-analysis/APPROVAL-PRODUCER-CONTRACT-PROPOSAL.md): L7 signed review, separately pinned authority/context, exact validate-stage manifest channel and admission binding.
- Keeps approval separate from semantic verification, source promotion and activation. A real signed decision cannot relabel a legacy plan.
- Status: Proposed implementation contract, not accepted or implemented; parent ADR statuses unchanged. No G3 closure, backend qualification, actual approver assignment or deployment authorization.

## ADR 0118/0119 rev 3.3 — enforcer type and enforcer instance, 2026-09-15

- ADR 0119 stays **Accepted**; adds **D1.1**. An enforcer has a type, resolved
  from the device's declared enforcement capability under ADR 0106, never from an
  identifier and never from which object module owns a generator. One type, one
  renderer. Artifacts are produced per enforcer instance: two enforcers of one
  type are two scopes, two projections and two independent artifact sets with
  their own connection identity and applied state. Enforcement plane stays a
  third, orthogonal axis. D2 adds enforcer type to the execution context; D3
  states the generate stage renders one artifact set per instance.
- ADR 0118 stays **Accepted**; D6 now says its table lists runtime targets, not
  enforcers - a workload's runtime does not select the enforcer covering its
  paths, and one runtime may be covered by several enforcers of different types.
- ADR 0110 stays **Implemented**. An erratum corrects the §1.1 transcription
  against the implemented class schema: `enforcement_plane` is required,
  `address_space` exists, `device_assignments` does not, and `managed_by_ref`
  carries no `target_class` - `class.router` was dropped because an enforcer need
  not be a router. R1-R6 behaviour and M1-B are unchanged.
- [W07 decision](0118-analysis/W07-BACKEND-SPECIALIZATION-DECISION.md) is amended:
  the seam is parameterised by enforcer type rather than by backend, and a second
  time by enforcer instance. Records the chosen Terraform layout
  `terraform/<backend>/<enforcer instance id>/` as an implementation choice, and
  states that adopting it is a reviewed behaviour change affecting 24 of 163
  emitted paths, not a refactor.
- Basis: SPC analysis of 2026-09-15 in this session. Measured: four devices with
  four distinct OS declared in the topology; `cap.firewall.security_matrix`,
  `.routeros` and `.pve` registered in the catalogue with zero consumers; a
  published `matrix_by_enforcer` index with zero subscribers; and a single
  unaliased `provider "routeros"` in one Terraform root.
- No code, schema or artifact changed. No gate closed, nothing qualified, no
  deployment implied.

## ADR 0118/0119 rev 3.4 — enforcer axes corrected after review, 2026-09-15

- Corrects rev 3.3 against the [rev 3.3 review](../docs/reports/2026-09-15-adr0118-0119-rev33-review-0202f253.md).
  Both ADRs stay **Accepted**; ADR 0110 stays **Implemented**. No gate closed.
- **Cardinality (R1).** ADR 0119 D1 now states the direction: one scope names
  exactly one enforcer, one enforcer may hold several scopes on several planes. A
  scope carries its own identity and is never keyed by its `managed_by_ref`. An
  enforcer-to-scope index must carry every scope in a deterministic order or refuse
  the multiplicity with a diagnostic. Plane separation is semantic and is not
  evidence that shared chains or resources are isolated.
- **Separation (R2).** D1.1 no longer demands one address, credential set and state
  per enforcer. It states six distinctions - enforcer identity, scope/context,
  connection binding, resource identity and writer, state namespace, apply unit -
  and requires unambiguous target selection with a single writer per resource.
  Several targets may share a management endpoint; sharing a binding, state
  namespace or apply unit is allowed where the coupling is declared and its
  reconciliation and recovery validated. Scope attribution is not a failure domain.
- **Dispatch (R3).** "One type, one renderer" is replaced. A type names a family of
  enforcement semantics; for each target context exactly one compatible versioned
  adapter is resolved, zero is unsupported, more than one blocks with no priority or
  first-match fallback. Resolution carries provenance, and the adapter's identity
  and version are pinned before validation and enter the plan's verifiable identity.
- **Layout justification (R4).** The W07 claim that a Terraform root holds one
  unaliased provider configuration is withdrawn: Terraform supports several
  configurations of one provider through `alias`. Root-per-instance is justified
  instead by state, writer and transaction boundaries, the aliased alternative is
  named and its rejection reasoned, each adapter's selected layout is tabulated, and
  moving roots now requires a resource/state/consumer inventory and a
  no-unintended-recreation plan rather than a path rename.
- **Erratum authority (R5).** ADR 0110's erratum separates the stale transcription
  from the normative amendment that dropped `target_class: class.router`, states the
  reason, requires the replacement to check an enforcement-capable target rather
  than accept any `instance_ref`, and no longer says the implemented file is the
  authority over an accepted contract.
- **Harmonization and evidence (R6).** AD-01 and AD-08 in the
  [architecture proposal](0118-analysis/FINAL-ARCHITECTURE-PROPOSAL.md) carry the
  cardinality and the ownership distinctions. The findings matrix is published as
  [enforcer axis conformance](0118-analysis/ENFORCER-AXIS-CONFORMANCE.md) instead of
  living only in a commit message.
- The index defect is reproduced in that record: two matrices on one enforcer
  compile SUCCESS with no diagnostics and `matrix_by_enforcer` keeps whichever came
  last, which is also a D4 permutation violation.
- No code, schema or artifact changed. Ten implementation gaps remain open and
  are listed in section 2 of the conformance record.

### Rev 3.4 editorial consolidation

- Removes remaining enforcer=scope and per-instance-artifact wording from D1.1
  and the W07 stage diagram; scope attribution and declared apply units are retained.
- Synchronizes the design annex header, enforcement-plane terminology, current
  implementation-plan entrypoint, capability supplement and scoped AI rule packs/map.
- Separates W07 layout goals from proven state/resource/failure isolation; the root
  migration remains a future reviewed change, not an authorization or completed work.
- Corrects the conformance count to ten open implementation rows; distinguishes
  corpus coverage, feasibility observations and planned regression tests.
- Corrects rev 3.4 document dates to 2026-09-15, matching both author and committer
  timestamps of `48a7ac3f`. No new revision, implementation gate or qualification
  status is introduced by this consolidation.

## ADR 0118/0119 — enforcer/scope implementation readiness, 2026-09-28

- Adds [readiness record](0118-analysis/ENFORCER-SCOPE-IMPLEMENTATION-READINESS.md):
  a re-measured baseline, an independent reproduction of the V-13 index defect, and
  a bounded specification for the next code change. Both ADRs stay **Accepted**;
  ADR 0110 stays **Implemented**. No gate closed, nothing qualified.
- Corrects two conformance rows from measurement rather than from restatement:
  `security_matrices` is complete in membership but permutation-sensitive in order,
  and V-09 is a singular return type across projection, generator and template
  rather than one dropped row.
- Records five new findings, `N-01`..`N-05`. The load-bearing one is that V-04/V-05
  is blocked on a namespace decision, not on adding a declaration: the three
  `cap.firewall.security_matrix*` identifiers are registered at L2 with device
  summaries while the catalogue reserves that namespace for policy objects and
  already carries an L1 device slot, `cap.net.l3.security.firewall.zone_policy`.
  The enforcer of record declares neither, `enabled_packs` never reach the
  effective capability set, and an unattributed scope compiles clean and is
  enforced by nobody.
- Sequences the ten open rows into implementable-now, blocked-on-V-13 and
  blocked-on-a-decision. The capability-axis decision is raised as a proposal
  requiring review; it is not taken there.
- Proposes `E7010`, `E7011` and `W7012` inside the existing ADR 0118/0119
  allocation, with the collision check recorded. No code, schema, manifest or
  artifact changed; no code has been written against this specification.
