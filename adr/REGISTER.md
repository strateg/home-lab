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

## ADR 0118/0119 — enforcer/scope readiness record updated after implementation, 2026-09-28

- Marks readiness record section 5 (`matrix_by_enforcer` → `scopes_by_enforcer`,
  `E7010`/`E7011`/`W7012`) as done, referencing commit `c5f66c10` on branch
  `adr-0118-0119`, with its actual validation evidence replacing the earlier plan.
- Updates the section 4 sequencing table: V-13/N-05/plane-default done; V-09,
  V-10, V-14 (the projection/generator/template consumer chain) move from
  blocked-on-V-13 to the next implementable-now candidate.
- Adds section 5b: a sketch, not a specification, of the consumer chain's touch
  points and open questions (two-scope fixture, rendered shape, parity
  evidence) - explicitly not authorization to begin that change.
- Records an open, separately tracked finding: `pytest tests` shows 125 failures
  confined to `tests/plugin_integration/test_security_plan_validator.py`, which
  passes 77/77 in isolation. Bisected to somewhere among the ~100
  `plugin_integration` files collected before it; five other directories and the
  immediately adjacent file are individually cleared. Reasoned as unlikely to be
  caused by `c5f66c10` (disjoint files) but not yet confirmed by a rerun. Not
  part of the ADR 0118/0119 scope.
- No code, schema or artifact changed by this entry.

## ADR 0118/0119 — consumer-chain finding N-06, pollution investigation closed, 2026-09-28

- Corrects the readiness record's section 5b: "one rendered block per scope"
  was wrong. `zone_firewall.tf.j2` emits exactly one terminal-deny resource and
  `vpn.tf.j2` hardcodes two more references to it by name; RouterOS has one
  `forward` chain per device regardless of how many scopes it holds. New
  finding N-06 records this and redirects V-09/V-10/V-14 from a generate-stage
  rendering change to a compile-stage composition step: zones union safely
  (shared origin data), matrix cells and policy-override names do not and need
  explicit conflict diagnostics rather than a silent last-write-wins merge -
  the same defect class V-13 fixed for the enforcer index, one level deeper.
  Not started; this is corrected design work, not code.
- Closes the test-pollution investigation opened while validating `c5f66c10`.
  The original 125 failures in `test_security_plan_validator.py` were not
  reproduced: every preceding directory and both halves of the preceding
  `plugin_integration` files were cleared individually, and the decisive
  check - the exact natural collection order `pytest tests` itself uses,
  reconstructed and run through the target file inclusive - passed the target
  clean (1981 passed, 1 skipped, 1 unrelated failure explained by process
  timing relative to `1336c12f`). Closed as an investigated, not reproduced,
  anomaly, most likely resource exhaustion specific to the original
  2573-test run, not a code defect requiring a fix.
- No code, schema or artifact changed by this entry.

## ADR 0118/0119 — composition contract decided (D-COMP-1..4), 2026-09-28

- Resolves the two design questions N-06 left open, narrower in scope than
  N-02: how the MikroTik adapter composes several scopes on one enforcer, a
  case unexercised anywhere in the real topology today. Fulfils ADR 0119 D1's
  existing requirement that composition across scopes sharing an enforcer be
  validated rather than assumed; does not amend the ADR.
- D-COMP-1: scopes composed for one enforcer must have pairwise-disjoint
  `zone_refs`, refused on overlap. Deliberately stricter than an
  equal-cells-are-safe merge - it makes a matrix-cell collision between scopes
  structurally impossible rather than something to adjudicate, at the cost of
  refusing a legitimate future case (two scopes sharing a zone for different
  concerns) until that is its own reviewed decision.
- D-COMP-2: `policy_overrides` names must be unique per enforcer (not
  globally), refused on collision rather than silently disambiguated - the
  same reasoning D1.1 already applies to adapter resolution.
- D-COMP-3/D-COMP-4: the composed shape (zones/matrix union, overrides
  concatenated) and its determinism (scopes processed in
  `scopes_by_enforcer`'s existing sorted order).
- New diagnostics `E7013`/`E7014`, collision-checked clean in the 7009-7019
  sub-band of the existing ADR 0118/0119 allocation.
- Not implemented: `security_matrix_compiler.py` does not yet compose, no test
  exercises D-COMP-1..4. Removes the design blockers section 5b listed for
  V-09/V-10/V-14; a two-scope fixture and parity evidence remain open before
  that chain can be specified the way section 5 was for V-13.

## ADR 0118/0119 — V-09/V-10/V-14 landed, readiness record closed out, 2026-09-29

- `e868abbe`: `_extract_security_matrix` in the MikroTik projection reads the
  compiler's `composed_matrices_by_enforcer` instead of re-deriving zone
  membership and R1-R6 itself. Finding N-07 (recorded first, before coding)
  characterized that local computation as a third independent derivation of
  the same fact, diverged from the compiler in three ways found by reading
  both implementations side by side - none active on the real topology's data.
  `security_matrices` retired entirely as a MikroTik consume (manifest,
  generator, projection signature) rather than left accepted-but-unread.
  `tests/test_backend_specialization_boundary.py`'s line budget lowered
  1518 -> 1399, matching the function's 209 -> 94 line shrink; the W07
  decision document's migration-order step 3 marked Done.
- `168b4f27`: the two-scope composed-plan fixture section 5b/5d called for,
  in `test_projection_helpers.py` - exercises `build_mikrotik_projection`
  with a genuinely multi-scope composed plan, which the real topology (one
  enabled scope) cannot exercise on its own.
- Real-topology parity verified: `generated/` byte-identical after a clean
  recompile, `errors=0 warnings=2` matching the recorded baseline.
- Readiness record reconciled: V-09/V-10/V-14 marked Done in section 4;
  sections 5b/5d's now-resolved open items struck through; evidence for both
  commits added to section 7; the status banner lists all five landed changes
  (`c5f66c10`, `1336c12f`, `e72d0099`, `e868abbe`, `168b4f27`).
- No design decision changes in this entry - implementation and bookkeeping
  only, against the design section 5c already decided.

## ADR 0118/0119 — enforcer type/adapter resolution designed (D-TYPE-1..3), 2026-09-29

- Resolves the capability-axis question section 4 named as the single
  highest-value blocked item, larger than first framed. Before designing a
  replacement, checked whether either capability engine could express
  "enforced by RouterOS OR Proxmox" as written: `capability_contract_validator.py`
  and `netmodel/capability.py`'s `Offer.applies_to` both match capability
  identifiers exactly, with no prefix/hierarchy semantics and no `any_of`/`one_of`
  construct anywhere in the schemas. `required_capabilities` on a class is a
  conjunction; it cannot express dispatch among mutually exclusive adapters.
  The earlier "recommended framing" (device axis = `cap.net.l3.security.
  firewall.*`) is retired along with the namespace question it was answering -
  a namespace choice does not fix a conjunction-only engine being asked to do
  selection.
- D-TYPE-1: enforcer type (perimeter/internal/none) is derived from exactly one
  of two mutually exclusive device-kind capabilities:
  `cap.net.l3.security.firewall.zone_policy` (existing, router-side) or a new
  registration, `cap.compute.security.firewall.zone_policy` (hypervisor-side;
  no such L1 capability existed for Proxmox before this, which is a second,
  independent reason the router-only framing could not have worked).
- D-TYPE-2: adapter is derived from type × the already-derived `cap.os.*`
  family (`cap.os.routeros` -> `.routeros` adapter, `cap.os.proxmox` -> `.pve`),
  not a third declared capability. Zero matching OS families refuses as
  unsupported; more than one refuses as ambiguous with no priority order -
  matching ADR 0119 D1.1's explicit dispatch contract. This makes
  `cap.firewall.security_matrix.routeros`/`.pve` derived outputs, like
  `cap.role.*` already are, closing N-03 without a redundant declaration.
- D-TYPE-3: the generic `cap.firewall.security_matrix` (zero declarers, zero
  consumers) is retired rather than repurposed as a `required_capabilities`
  entry - resolution answers "is this a valid enforcer" directly, which is
  N-01's `managed_by_ref` target-check replacement.
- `E7015`-`E7018` allocated in the existing 7009-7019 sub-band, collision
  check clean. Placement: an extension of `capability_compiler.py`'s existing
  per-object derivation pass, not a new plugin family.
- N-04 (`enabled_packs`) stays deferred, confirmed independently: only two
  objects declare non-empty packs (Chateau, GL.iNet), and the real enforcer
  does not need pack expansion to gain `.zone_policy` - a direct declaration
  is narrower and sufficient. Fixing pack expansion has a wider blast radius
  (Chateau's enabled `pack.router.enterprise` also lists BGP/OSPF/VRF
  capabilities) and is not required for this decision.
- Not implemented: no code, schema or catalogue entry changed. `enforcer_resolution`
  does not exist yet.

## ADR 0118/0119 — enforcer type/adapter resolution, SPC MODE review (two passes), 2026-09-29

- The design entered at commit `8dd9a3a3` (previous entry) went through the
  formal `docs/ai/spc-contract.md` 7-step protocol rather than being accepted
  as written. **Correction to the previous entry:** its D-TYPE-3 bullet
  ("the generic `cap.firewall.security_matrix` ... is retired") is
  superseded by this entry - the SPC review's first pass found that
  `CAPABILITY-SATISFACTION-CONTRACT.md` §5 forbids exactly that action
  ("Legacy catalog entries are not reclassified by this amendment"), and its
  §7 already treats `.pve` as the correct identifier with an unimplemented
  generator as the actual gap. All three pre-registered identifiers
  (`cap.firewall.security_matrix`, `.routeros`, `.pve`) are kept.
- First pass, second finding: D-TYPE-2 had no rule for a device already
  carrying a direct `.routeros`/`.pve` declaration alongside the
  newly-resolved one - ADR 0119 D1.1's "generic capability alongside a
  specific one... inputs to the resolution, not answers" case. Fixed with an
  explicit reconciliation rule: agreement confirms, disagreement is a
  distinct refusal (`E7019`), no priority order between the two inputs.
- Second pass (STEP 7 compliance matrix run to completion) found two further
  Critical gaps the first pass missed: (1) ADR 0119 D1.1 requires adapter
  identity *and* version; only identity had been resolved. (2) The chosen
  type values (`perimeter`/`internal`) are the exact strings
  `class.network.security_matrix.yaml`'s `enforcement_plane` field already
  uses for an axis ADR 0119 D1.1 states is independent of enforcer type.
- Resolution, both user-confirmed: (1) the resolving generator plugin's
  existing `api_version` manifest field (already `1.x` on both MikroTik and
  Proxmox generators) is bound to the resolved adapter identity as a partial
  version signal; full D2 execution-context binding remains this record's
  pre-existing V-07 row, not newly closed. (2) type values renamed to
  `network`/`compute` (naming the producing capability namespace), with
  `perimeter`/`internal` reserved exclusively for `enforcement_plane`.
- `E7015`-`E7019` (5, not 4) in the same sub-band, collision check re-run
  clean. Still design-only: not registered in `error-catalog.yaml` or
  `docs/diagnostics-catalog.md`, `enforcer_resolution` does not exist.
- Verification: `check_adr_consistency.py --strict-titles` clean; diagnostic
  sub-band grep shows the five codes referenced only in this design record.

## ADR 0118/0119 — enforcer type/adapter resolution, implemented, 2026-09-29

- Implemented the design from the previous two entries. Building it against
  the real topology found three things the SPC review itself had not:
  1. The real enforcer of record, `rtr-mikrotik-chateau`, declared no
     `cap.net.l3.security.firewall.zone_policy` at all, despite its
     security-matrix instance being explicitly zone-based. Fixed as a
     topology-data correction (`obj.mikrotik.chateau_lte7_ax.yaml`), not by
     weakening the D-TYPE-1 gate.
  2. The approved `adapter_version` mechanism (binding the resolving
     generator's `api_version`) was wrong: `api_version: 1.x` is identical
     across every plugin in the entire framework (the kernel-API
     compatibility marker, not an adapter revision) - a repo-wide grep during
     implementation found this, not the review. `adapter_version` ships as
     `None`, honestly, rather than a misleading constant.
  3. Device-kind capabilities live on the hardware object;
     `cap.os.*` capabilities live on a *different* object under ADR 0064's
     embedded-OS model, joined only at the instance level via `os_refs`.
     `capability_compiler.py` (the design's chosen home) iterates objects and
     can never see both facts for one entity. Moved to
     `effective_model_compiler.py`, which already performs this exact join
     for OS/firmware capabilities; `enforcer_resolution` is published keyed
     by **instance id**, not object id.
- Severity corrected during implementation: an eager `error` severity on
  every resolution (not only referenced ones) broke the real compile for
  `rtr-slate` (GL.iNet, OpenWrt - type resolves, no adapter exists, and
  nothing points `managed_by_ref` at it). Renamed and downgraded four of the
  five codes to warnings (`W7015`, `W7016`, `W7017`, `W7019`); `E7018` stays
  the one hard error, since it only fires for an instance an actual
  security_matrix scope depends on.
- New capability registered: `cap.compute.security.firewall.zone_policy`
  (`capability-catalog.yaml`). N-01 replaced in both
  `declarative_reference_validator.py` and `network_core_refs_validator.py`
  (kept in parity per `test_declarative_reference_validator_parity.py`).
- Verified against the real topology: `check_adr_consistency.py
  --strict-titles` clean; full compile is `errors=0 warnings=3`, the third
  warning being the expected `W7016` for `rtr-slate`; `git status` shows no
  diff under `generated/` (purely additive); manifests
  (`compilers.yaml`/`validators.yaml`) and `framework.lock.yaml` updated for
  the new `enforcer_resolution` produces/consumes wiring.
- Tests: 13 new cases in `test_effective_model_compiler.py` (object-level and
  cross-object/os_refs resolution, contradiction, unsupported, reconciliation
  disagreement, non-enforcer omission) and 3 new cases in
  `test_network_core_refs_validator.py` (E7018 accept/reject paths), all
  passing, plus the targeted suites (`test_security_matrix_compiler.py`,
  `test_declarative_reference_validator_parity.py`,
  `test_backend_specialization_boundary.py`, `test_data_bus_contracts.py`,
  `test_manifest.py`, `test_capability_contract_validator.py`,
  `test_capability_contract_loader_compiler.py`), all clean.

## W07 migration order item 1 — capability-flag derivation moved to compile stage, 2026-09-29

- `_derive_mikrotik_capability_flags` and `_extract_capabilities` moved verbatim
  from `topology/object-modules/mikrotik/plugins/projections.py` (generate
  stage) to a new plugin, `object.mikrotik.compiler.capability_flags`
  (`topology/object-modules/mikrotik/plugins/compilers/
  capability_flags_compiler.py`, compile stage) - the first compile-stage
  compiler plugin an object module has registered in this framework,
  establishing the `object.<module>.compiler.plan -> backend_plan` seam
  `adr/0118-analysis/W07-BACKEND-SPECIALIZATION-DECISION.md`'s Shape section
  already specified.
- Root cause found during implementation, not anticipated by the decision
  document: `phase: finalize` plugins are dispatched through an `on_finalize`
  hook, not `execute()` directly - `effective_model_compiler.py` already does
  this via a one-line delegation, which the new plugin now mirrors. Diagnosed
  by direct-execute vs full-stage-execute comparison after the plugin was
  silently skipped (`skip_reason: "phase 'finalize' not implemented"`) despite
  correct manifest registration and scheduling order.
- `build_mikrotik_projection` gains `capability_flags` as a required argument
  (the same "required, refuse `None`" contract `composed_matrices_by_enforcer`/
  `vlan_cidr_map` already use); the generator's manifest `depends_on`/`consumes`
  updated to match. `I4210` registered for the new plugin's per-run info
  diagnostic.
- Verified against the real topology: `check_adr_consistency.py
  --strict-titles` clean; full compile is `errors=0 warnings=3`, unchanged
  from the pre-existing baseline; `git status` shows no diff under
  `generated/` (purely additive).
- Tests: 9 files updated for the new required parameter and consumer wiring
  (`test_mikrotik_capability_driven.py` - unit tests for the derivation logic
  itself now import from the new module;
  `tests/helpers/mikrotik_security_channels.py` - the shared fixture helper
  now derives real `capability_flags` from `ctx.compiled_json` rather than
  publishing empty, since capability-driven template-selection tests depend
  on real content; `test_projection_helpers.py`, `test_projection_snapshots.py`,
  `test_terraform_mikrotik_generator.py`, `test_generator_template_and_
  publish_contract.py`, `test_tuc0002_terraform_v2.py`,
  `test_tuc0003_mikrotik_v2.py`, `test_backend_specialization_boundary.py` -
  the last one's function/line budget lowered to 13/1361 and its migration
  parametrize lists updated). Full `tests/plugin_integration` +
  `tests/plugin_contract` + `tests/kernel` run confirmed clean.

## W07 migration order item 4a — WireGuard tunnel derivation moved to compile stage, 2026-09-29

- `_extract_wireguard_tunnels` moved verbatim from `projections.py` (generate
  stage) to a new plugin, `object.mikrotik.compiler.wireguard_tunnels`
  (`topology/object-modules/mikrotik/plugins/compilers/
  wireguard_tunnels_compiler.py`, compile stage) - the second compile-stage
  compiler plugin an object module has registered, after item 1's
  `capability_flags`. Uses the `on_finalize` delegation pattern from the
  start (item 1's root-cause finding applied directly, no rediscovery
  needed).
- Consumes `base.compiler.effective_model`'s `effective_model_candidate`
  (router ids, network rows) and `base.compiler.security_matrix`'s
  `vlan_cidr_map`. `build_mikrotik_projection` gains `wireguard_tunnels` as a
  required argument, the same "required, refuse `None`" contract the other
  three channels already use.
- Characterization (required before migrating, per the W05/N-07 lesson)
  found no divergence to fix first: the function reads only topology
  instance data plus the already-compiler-sourced `vlan_cidr_index`, not a
  second derivation of a compiler-owned fact - lower risk than items 1-3.
- Verified against the real topology: `check_adr_consistency.py
  --strict-titles` clean; full compile is `errors=0 warnings=3`, unchanged
  from baseline; `git status` shows no diff under `generated/`.
- `projections.py` now 12 functions / 1179 lines (down from 13/1361);
  `test_backend_specialization_boundary.py` budget lowered to match,
  `_extract_wireguard_tunnels` added to the "migrated, gone rather than
  dormant" list.
- Same nine-file test-wiring pattern as item 1 applied again: the shared
  helper `tests/helpers/mikrotik_security_channels.py` now derives
  `wireguard_tunnels` from `ctx.compiled_json` the same way it already does
  `capability_flags`; all `consumes_keys`/`allowed_dependencies` sets
  extended to the new plugin id. Full targeted mikrotik/projection/
  terraform/tuc slice (120 tests) and the boundary suite confirmed passing.
- `adr/0118-analysis/W07-BACKEND-SPECIALIZATION-DECISION.md`'s migration
  order item 4a marked done, with a note that this confirms the "dedicated
  plugin per specialization" choice item 1 first established, rather than
  one plugin accreting every concern.

## W07 migration order item 4b — container derivation moved to compile stage, 2026-09-29

- `_extract_containers` moved verbatim from `projections.py` (generate
  stage) to a new plugin, `object.mikrotik.compiler.containers`
  (`topology/object-modules/mikrotik/plugins/compilers/containers_compiler.py`,
  compile stage) - the third dedicated compile-stage compiler plugin an
  object module has registered, after item 1's `capability_flags` and item
  4a's `wireguard_tunnels`.
- Consumes only `base.compiler.effective_model`'s `effective_model_candidate`
  (router ids, `routeros_container`-group rows) - no dependency on
  `base.compiler.security_matrix`, since container derivation touches no
  zone/CIDR fact. `build_mikrotik_projection` gains `containers` as a
  required argument (a plain list; `[]` is already the correct empty shape,
  unlike the dict-shaped channels).
- Characterization found no divergence to fix first, same as item 4a - but
  also caught a real hazard: the projection already had an unrelated local
  variable also named `containers` (observed-runtime bridge-interface
  config, a different meaning entirely), which would have silently shadowed
  the new parameter for the rest of the function and corrupted rendered
  output if migrated without reading the whole function body first. Found
  by grepping the function for the parameter name before finalizing, not by
  a test; renamed to `observed_containers`.
- Verified against the real topology: `check_adr_consistency.py
  --strict-titles` clean; full compile is `errors=0 warnings=3`, unchanged
  from baseline; `git status` shows no diff under `generated/`; the real
  topology's 6 containers derived correctly with the rename in place.
- `projections.py` now 11 functions / 1000 lines (down from 12/1179);
  `test_backend_specialization_boundary.py` budget lowered to match,
  `_extract_containers` added to the "migrated, gone rather than dormant"
  list.
- Same nine-file test-wiring pattern as items 1/4a applied again. Targeted
  mikrotik/projection/terraform/tuc slice: 118 passed (2 unrelated errors in
  `test_tuc0001_router_data_link.py`, root-caused to CPU contention from a
  concurrently-running full-suite background job - every one of the ~30
  underlying timeouts hit completely unrelated validators, dns_refs through
  vm_refs, none touching MikroTik/containers/wireguard; a clean non-strict
  compile immediately prior showed zero errors).
- `adr/0118-analysis/W07-BACKEND-SPECIALIZATION-DECISION.md`'s migration
  order item 4b marked done, naming the naming-collision finding explicitly
  since it is the kind of thing the characterization step exists to catch.

## W07 migration order item 4c — WiFi config derivation moved to compile stage, 2026-09-29

- `_extract_wifi_config` moved verbatim from `projections.py` (generate
  stage) to a new plugin, `object.mikrotik.compiler.wifi_config`
  (`topology/object-modules/mikrotik/plugins/compilers/wifi_config_compiler.py`,
  compile stage) - the fourth dedicated compile-stage compiler plugin an
  object module has registered.
- Consumes only `base.compiler.effective_model`'s `effective_model_candidate`
  (router rows) - no dependency on `base.compiler.security_matrix`, same as
  item 4b. `build_mikrotik_projection` gains `wifi_config` as a required
  argument. `_extract_bridge_vlans` (item 4f, still in the projection) takes
  this function's output as its own argument; the projection now threads
  the `wifi_config` parameter into it locally, so 4f's eventual migration
  will need `wifi_config` already in scope.
- Characterization found no divergence and, checked explicitly this time
  given item 4b's finding, no naming collision either: grepped the whole
  function body for every generic-sounding name (`interfaces`, `datapaths`,
  `configurations`, `securities`) before concluding it was safe.
- Surfaced a test-infrastructure gap instead: `test_projection_helpers.py`'s
  `build_mikrotik_projection` wrapper always defaulted the new required
  channels to empty, silently breaking
  `test_mikrotik_projection_extracts_wifi_interfaces` (a test that builds
  real WiFi `instance_data` and expects it derived). Fixed by making that
  wrapper auto-derive all four channels from the fixture's own rows, the
  same way `test_mikrotik_capability_driven.py`'s wrapper already did.
- Verified against the real topology: `check_adr_consistency.py
  --strict-titles` clean; full compile is `errors=0 warnings=3`, unchanged
  from baseline; `git status` shows no diff under `generated/`; the real
  topology's 5 WiFi interface bindings derived correctly.
- `projections.py` now 10 functions / 877 lines (down from 11/1000);
  `test_backend_specialization_boundary.py` budget lowered to match,
  `_extract_wifi_config` added to the "migrated, gone rather than dormant"
  list.
- Same test-wiring pattern as items 1/4a/4b applied again, plus the
  `test_projection_helpers.py` wrapper fix above. Targeted mikrotik/
  projection/terraform/tuc slice: 120 passed, clean.
- `adr/0118-analysis/W07-BACKEND-SPECIALIZATION-DECISION.md`'s migration
  order item 4c marked done, naming both findings (no collision this time,
  found by checking; the test-wrapper gap, found by a real content test
  failing) and noting the forward dependency onto item 4f.

## W07 migration order item 4d — routing-policy derivation moved to compile stage, 2026-09-29

- `_build_routing_policy_entry` moved verbatim from `projections.py`
  (generate stage) to a new plugin, `object.mikrotik.compiler.
  routing_policies` (`topology/object-modules/mikrotik/plugins/compilers/
  routing_policies_compiler.py`, compile stage) - the fifth dedicated
  compile-stage compiler plugin an object module has registered.
- Unlike items 4a-4c, the source function was a per-row builder called from
  inside a larger shared loop (over `network` rows) that also builds vlans
  and bridges in the same iteration, not an independent top-level extractor.
  Migrating it required replicating the loop's row-selection and
  `managed_by_ref`-resolution logic for `routing_policy` rows specifically -
  checked against the original by reading the surrounding loop in full, not
  just the builder function - while leaving the vlan/bridge branches of that
  same loop untouched in the projection.
- Consumes `base.compiler.effective_model`'s `effective_model_candidate`
  (router ids, network rows) and `base.compiler.security_matrix`'s
  `vlan_cidr_map`, same as item 4a. `build_mikrotik_projection` gains
  `routing_policies` as a required argument.
- Characterization found no divergence and, checked given 4b's and 4c's
  findings, no naming collision.
- Verified against the real topology: `check_adr_consistency.py
  --strict-titles` clean; full compile is `errors=0 warnings=3`, unchanged
  from baseline; `git status` shows no diff under `generated/`; the real
  topology's 5 routing policies derived correctly.
- `projections.py` now 9 functions / 774 lines (down from 10/877);
  `test_backend_specialization_boundary.py` budget lowered to match,
  `_build_routing_policy_entry` added to the "migrated, gone rather than
  dormant" list.
- Same test-wiring pattern as items 1/4a/4b/4c applied again, including
  extending both `test_projection_helpers.py`'s auto-deriving wrapper and
  `test_mikrotik_capability_driven.py`'s wrapper with a routing-policy
  derivation helper that replicates the plugin's row-selection loop.
  Targeted mikrotik/projection/terraform/tuc slice: 120 passed, clean.
- `adr/0118-analysis/W07-BACKEND-SPECIALIZATION-DECISION.md`'s migration
  order item 4d marked done, naming the new kind of migration this item
  represents (extracting a slice of a shared loop, not an independent
  function) for the benefit of items 4e-4i.

## W07 migration order item 4e — MAC-to-VLAN assignment derivation moved to compile stage, 2026-09-29

- `_extract_mac_vlan_assignments` moved verbatim from `projections.py`
  (generate stage) to a new plugin, `object.mikrotik.compiler.
  mac_vlan_assignments` (`topology/object-modules/mikrotik/plugins/
  compilers/mac_vlan_assignments_compiler.py`, compile stage) - the sixth
  dedicated compile-stage compiler plugin an object module has registered.
- It needed a VLAN `instance_id -> vlan_id` index the projection used to
  build from its own already-filtered `vlans` list - itself a slice of the
  same shared per-`network`-row loop item 4d's migration already drew from,
  the same "per-row builder/index fed by a shared loop" shape 4d named.
  Rather than replicate the whole VLAN branch (still generate-stage, item
  4g), the plugin replicates only the row-selection, `managed_by_ref`-
  resolution and `vlan_id`-fallback logic needed to build the index itself -
  checked against the full network-row loop in `build_mikrotik_projection`,
  not only the removed function.
- This is also the first migration whose derivation needs object-level
  properties (`_get_object_properties`'s `objects_map` fallback for
  `vlan_id`), which `base.compiler.effective_model` already publishes under
  `effective_model_candidate["objects"]` - confirmed by reading the
  compiler's own `objects_index` construction, not assumed present.
- Consumes only `base.compiler.effective_model`'s `effective_model_candidate`
  (router ids, network rows, objects) - no `base.compiler.security_matrix`
  dependency, same as items 4b/4c. `build_mikrotik_projection` gains
  `mac_vlan_assignments` as a required argument.
- Characterization found no divergence and, checked given 4b's and 4c's
  findings, no naming collision.
- Verified against the real topology: full compile is `errors=0 warnings=3`,
  unchanged from baseline; `git status` shows no diff under `generated/`;
  the real topology's 3 MAC-to-VLAN assignments derived correctly (I4215).
- `projections.py` now 8 functions / 720 lines (down from 9/774);
  `test_backend_specialization_boundary.py` budget lowered to match,
  `_extract_mac_vlan_assignments` added to the "migrated, gone rather than
  dormant" list.
- Same test-wiring pattern as items 1/4a/4b/4c/4d applied again, including
  extending `mikrotik_security_channels.py`, `test_projection_helpers.py`
  and `test_mikrotik_capability_driven.py` with a MAC-VLAN derivation helper
  that replicates the plugin's own vlan_id_index-building loop slice.
  Targeted mikrotik/projection/terraform/tuc slice plus the full boundary
  test file: 121 + 15 passed, clean.
- `adr/0118-analysis/W07-BACKEND-SPECIALIZATION-DECISION.md`'s migration
  order item 4e marked done, naming the two new lessons this item adds
  (an index fed by a shared-loop slice, and a migrated function's data need
  satisfied by a channel another compiler already publishes rather than a
  new one) for the benefit of items 4f-4i.

## W07 migration order item 4f — bridge-VLAN derivation moved to compile stage, 2026-09-29

- `_extract_bridge_vlans` moved verbatim from `projections.py` (generate
  stage) to a new plugin, `object.mikrotik.compiler.bridge_vlans`
  (`topology/object-modules/mikrotik/plugins/compilers/
  bridge_vlans_compiler.py`, compile stage) - the seventh dedicated
  compile-stage compiler plugin an object module has registered.
- Confirms the forward dependency item 4c's entry recorded: this plugin
  subscribes to `wifi_config` (item 4c) from `object.mikrotik.compiler.
  wifi_config` as a published channel, rather than the local variable the
  projection used to thread into it. It also consumes
  `base.compiler.effective_model`'s `effective_model_candidate` for the
  router-row side of the derivation. No shared-loop slice or extra channel
  was needed this time - both inputs were already either a top-level router
  list or another compiler's published output.
- Characterization found no divergence and, checked given 4b's and 4c's
  findings, no naming collision.
- Verified against the real topology: `check_adr_consistency.py
  --strict-titles` clean; full compile is `errors=0 warnings=3`, unchanged
  from baseline; `git status` shows no diff under `generated/`; the real
  topology's 1 bridge VLAN entry derived correctly (I4216).
- `projections.py` now 7 functions / 632 lines (down from 8/720);
  `test_backend_specialization_boundary.py` budget lowered to match,
  `_extract_bridge_vlans` added to the "migrated, gone rather than dormant"
  list.
- Same test-wiring pattern as items 1/4a/4b/4c/4d/4e applied again,
  including extending `mikrotik_security_channels.py`,
  `test_projection_helpers.py` and `test_mikrotik_capability_driven.py`
  with a bridge-VLAN derivation helper that depends on the wifi_config
  derivation helper, the same forward dependency the real plugin has.
  Targeted mikrotik/projection/terraform/tuc slice plus the full boundary
  test file: 121 + 16 passed, clean.
- `adr/0118-analysis/W07-BACKEND-SPECIALIZATION-DECISION.md`'s migration
  order item 4f marked done, updating the guidance for items 4g-4i to
  describe subscribing to an earlier item's channel once it migrates,
  rather than threading a still-local variable into a not-yet-migrated
  function.
