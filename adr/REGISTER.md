# ADR Register

| ADR | Title | Status | Date | Supersedes | Superseded By |
|-----|-------|--------|------|------------|---------------|
| [0001](0001-power-policy-layer-boundary.md) | Keep Physical Power in L1 and Outage Policies in L7 | Accepted | 2026-02-20 | - | - |
| [0002](0002-separate-data-and-power-links-in-l1.md) | Separate Data Links and Power Links in L1 | Accepted | 2026-02-20 | - | - |
| [0003](0003-data-links-naming-and-power-constraints.md) | Rename L1 Physical Links to Data Links and Constrain Data-Link Power | Accepted | 2026-02-20 | - | - |
| [0004](0004-l2-firewall-policy-references-and-validation.md) | Enforce Explicit L2 Firewall Policy References and Validation Semantics | Accepted | 2026-02-20 | - | - |
| [0005](0005-diagram-generation-determinism-and-binding-visibility.md) | Improve Diagram Generation Determinism and Firewall Binding Visibility | Accepted | 2026-02-20 | - | - |
| [0006](0006-mermaid-icon-mode-with-fallback.md) | Add Mermaid Icon Mode with Template Fallback | Superseded | 2026-02-20 | - | [0008](0008-mermaid-icon-node-default-and-runtime-pack-registration.md) |
| [0007](0007-icon-legend-and-complete-device-icon-coverage.md) | Add Icon Legend Page and Complete Device Icon Coverage | Superseded | 2026-02-20 | - | [0027](0027-mermaid-rendering-strategy-consolidation.md) |
| [0008](0008-mermaid-icon-node-default-and-runtime-pack-registration.md) | Make Mermaid Icon-Node the Default and Require Runtime Icon Pack Registration | Superseded | 2026-02-20 | [0006](0006-mermaid-icon-mode-with-fallback.md) | [0027](0027-mermaid-rendering-strategy-consolidation.md) |
| [0009](0009-robust-icon-pack-discovery-and-render-validation.md) | Robust Mermaid Icon Pack Discovery and Render Validation | Superseded | 2026-02-20 | - | [0027](0027-mermaid-rendering-strategy-consolidation.md) |
| [0010](0010-regeneration-pipeline-mermaid-quality-gate.md) | Add Mermaid Render Quality Gate to Regeneration Pipeline | Superseded | 2026-02-20 | - | [0027](0027-mermaid-rendering-strategy-consolidation.md) |
| [0011](0011-l1-physical-storage-taxonomy-and-l3-disk-binding.md) | L1 Physical Storage Taxonomy and L3 Disk Binding | Superseded | 2026-02-20 | - | [0029](0029-storage-taxonomy-and-layer-boundary-consolidation.md) |
| [0012](0012-separate-l1-physical-disk-specs-from-l3-logical-storage-mapping.md) | Separate L1 Physical Disk Specs from L3 Logical Storage Mapping | Superseded | 2026-02-21 | - | [0029](0029-storage-taxonomy-and-layer-boundary-consolidation.md) |
| [0013](0013-l1-storage-mount-taxonomy-soldered-replaceable-removable.md) | L1 Storage Mount Taxonomy for Soldered, Replaceable, and Removable Media | Superseded | 2026-02-21 | - | [0029](0029-storage-taxonomy-and-layer-boundary-consolidation.md) |
| [0014](0014-l1-storage-slots-preferred-model-with-legacy-compatibility.md) | Use L1 Storage Slots as Preferred Model with Legacy Compatibility | Superseded | 2026-02-21 | - | [0015](0015-drop-legacy-storage-compatibility-after-storage-slots-migration.md), [0029](0029-storage-taxonomy-and-layer-boundary-consolidation.md) |
| [0015](0015-drop-legacy-storage-compatibility-after-storage-slots-migration.md) | Drop Legacy L1 Storage Compatibility After Storage Slots Migration | Superseded | 2026-02-21 | [0014](0014-l1-storage-slots-preferred-model-with-legacy-compatibility.md) | [0029](0029-storage-taxonomy-and-layer-boundary-consolidation.md) |
| [0016](0016-l1-storage-media-registry-and-slot-attachments.md) | L1 Storage Media Registry and Slot Attachments | Superseded | 2026-02-21 | - | [0029](0029-storage-taxonomy-and-layer-boundary-consolidation.md) |
| [0017](0017-topology-tools-modular-refactor-validation-generation.md) | Modular Refactor of topology-tools into Validation and Generation Domains | Superseded | 2026-02-21 | - | [0028](0028-topology-tools-architecture-consolidation.md) |
| [0018](0018-generation-common-loader-and-output-preparation.md) | Shared Generation Common Module for Layered Topology Loading and Output Directory Preparation | Superseded | 2026-02-21 | - | [0028](0028-topology-tools-architecture-consolidation.md) |
| [0019](0019-proxmox-answer-layered-topology-only.md) | Proxmox Answer Generator Uses Layered Topology Only (No Legacy Root Sections) | Superseded | 2026-02-21 | - | [0028](0028-topology-tools-architecture-consolidation.md) |
| [0020](0020-topology-tools-scripts-domain-layout.md) | Co-locate Generation and Validation Under topology-tools/scripts | Superseded | 2026-02-21 | - | [0028](0028-topology-tools-architecture-consolidation.md) |
| [0021](0021-docs-generation-moved-to-scripts-generation-docs.md) | Move Documentation Generation Core into scripts/generation/docs | Superseded | 2026-02-21 | - | [0028](0028-topology-tools-architecture-consolidation.md) |
| [0022](0022-docs-diagram-module-canonical-location.md) | Use scripts/generation/docs/docs_diagram.py as Canonical Diagram Module | Superseded | 2026-02-21 | - | [0028](0028-topology-tools-architecture-consolidation.md) |
| [0023](0023-terraform-generators-and-templates-domain-layout.md) | Terraform Generators and Templates Domain Layout | Superseded | 2026-02-21 | - | [0028](0028-topology-tools-architecture-consolidation.md) |
| [0024](0024-validators-namespace-alignment.md) | Rename Validation Package Namespace to validators | Superseded | 2026-02-21 | - | [0028](0028-topology-tools-architecture-consolidation.md) |
| [0025](0025-generator-protocol-and-cli-base-class.md) | Generator Protocol and CLI Base Class | Superseded | 2026-02-21 | - | [0028](0028-topology-tools-architecture-consolidation.md) |
| [0026](0026-l3-l4-taxonomy-refactoring-storage-chain-and-platform-separation.md) | L3/L4 Taxonomy Refactoring - Storage Chain and Platform Separation | Accepted | 2026-02-21 | - | - |
| [0027](0027-mermaid-rendering-strategy-consolidation.md) | Consolidate Mermaid Rendering Strategy and Quality Gates | Accepted | 2026-02-22 | [0007](0007-icon-legend-and-complete-device-icon-coverage.md), [0008](0008-mermaid-icon-node-default-and-runtime-pack-registration.md), [0009](0009-robust-icon-pack-discovery-and-render-validation.md), [0010](0010-regeneration-pipeline-mermaid-quality-gate.md) | - |
| [0028](0028-topology-tools-architecture-consolidation.md) | Consolidate topology-tools Architecture and Module Boundaries | Accepted | 2026-02-22 | [0017](0017-topology-tools-modular-refactor-validation-generation.md), [0018](0018-generation-common-loader-and-output-preparation.md), [0019](0019-proxmox-answer-layered-topology-only.md), [0020](0020-topology-tools-scripts-domain-layout.md), [0021](0021-docs-generation-moved-to-scripts-generation-docs.md), [0022](0022-docs-diagram-module-canonical-location.md), [0023](0023-terraform-generators-and-templates-domain-layout.md), [0024](0024-validators-namespace-alignment.md), [0025](0025-generator-protocol-and-cli-base-class.md) | - |
| [0029](0029-storage-taxonomy-and-layer-boundary-consolidation.md) | Consolidate Storage Taxonomy and L1/L3 Boundary Contract | Accepted | 2026-02-22 | [0011](0011-l1-physical-storage-taxonomy-and-l3-disk-binding.md), [0012](0012-separate-l1-physical-disk-specs-from-l3-logical-storage-mapping.md), [0013](0013-l1-storage-mount-taxonomy-soldered-replaceable-removable.md), [0014](0014-l1-storage-slots-preferred-model-with-legacy-compatibility.md), [0015](0015-drop-legacy-storage-compatibility-after-storage-slots-migration.md), [0016](0016-l1-storage-media-registry-and-slot-attachments.md) | - |
| [0031](0031-layered-topology-toolchain-contract-alignment.md) | Layered Topology Toolchain Contract Alignment | Proposed | 2026-02-22 | - | - |
| [0032](0032-l3-data-modularization-and-layer-contracts.md) | L3 Data Modularization and Layer Contracts | Proposed | 2026-02-22 | - | - |
| [0033](0033-toolchain-contract-rebaseline-after-modularization.md) | Toolchain Contract Rebaseline After Modularization | Proposed | 2026-02-22 | - | - |
| [0034](0034-l4-platform-modularization-and-runtime-taxonomy.md) | L4 Platform Modularization (MVP) | Proposed | 2026-02-22 | - | - |
| [0035](0035-l4-host-os-foundation-and-runtime-substrates.md) | L4 Host OS Foundation and Runtime Substrate Contracts | Proposed | 2026-02-22 | - | - |
| [0036](0036-l2-host-os-reference-in-network-allocations.md) | Host OS Reference in Network Allocations | Proposed | 2026-02-22 | - | - |
| [0037](0037-l2-network-substrate-and-workload-binding-contracts.md) | L2 Network Substrate and Workload Binding Contracts | Superseded | 2026-02-22 | - | [0038](0038-network-binding-contracts-phase1.md) |
| [0038](0038-network-binding-contracts-phase1.md) | Network Binding Contracts Phase 1 (Gradual Evolution) | Accepted | 2026-02-22 | [0037](0037-l2-network-substrate-and-workload-binding-contracts.md) | - |
| [0039](0039-l4-host-os-installation-storage-contract-clarification.md) | Host OS Installation Storage Contract (Strict) | Accepted | 2026-02-23 | - | - |
| [0040](0040-l0-l5-canonical-ownership-and-refactoring-plan.md) | L0-L5 Canonical Ownership and Refactoring Plan | Accepted | 2026-02-23 | - | - |
| [0041](0041-l4-workload-network-attachment-typing.md) | L4 Workload Network Attachment Typing | Accepted | 2026-02-24 | - | - |
| [0042](0042-l5-services-modularization.md) | L5 Services Modularization | Accepted | 2026-02-24 | - | - |
| [0043](0043-l0-l5-harmonization-and-cognitive-load-reduction.md) | L0-L5 Harmonization and Cognitive Load Reduction | Accepted | 2026-02-24 | - | - |
| [0044](0044-ip-derivation-from-refs.md) | IP Derivation from Refs | Accepted | 2026-02-24 | - | - |
| [0045](0045-model-and-project-improvements.md) | Improvements to project model, development workflow and automation | Proposed | 2026-02-25 | - | - |
| [0046](0046-generators-architecture-refactoring.md) | Generators Architecture Refactoring | Approved | 2026-02-25 | - | - |
| [0047](0047-l6-observability-modularization.md) | L6 Observability Modularization | Partially Implemented | 2026-02-26 | - | - |
| [0048](0048-topology-v4-architecture-consolidation.md) | Topology v4 Architecture Consolidation | Accepted | 2026-02-28 | [0049](0049-mikrotik-bootstrap-automation.md), [0050](0050-generated-directory-restructuring.md) | - |
| [0049](0049-mikrotik-bootstrap-automation.md) | MikroTik Bootstrap Automation | Proposed | 2026-02-28 | - | [0048](0048-topology-v4-architecture-consolidation.md) |
| [0050](0050-generated-directory-restructuring.md) | Generated Directory Restructuring | Accepted | 2026-02-28 | - | [0048](0048-topology-v4-architecture-consolidation.md) |
| [0051](0051-ansible-runtime-and-secrets.md) | Ansible Runtime, Inventory, and Secret Boundaries | Accepted | 2026-03-01 | - | - |
| [0052](0052-build-pipeline-after-ansible.md) | Deploy Package Assembly Over Accepted Ansible Runtime | Accepted | 2026-03-01 | - | - |
| [0053](0053-dist-first-deploy-cutover.md) | Optional Dist-First Deploy Cutover | Proposed | 2026-03-01 | - | - |
| [0054](0054-local-inputs-directory.md) | Local Inputs Directory | Accepted | 2026-03-01 | - | - |
| [0055](0055-manual-terraform-extension-layer.md) | Manual Terraform Extension Layer | Accepted | 2026-03-01 | - | - |
| [0056](0056-native-execution-workspace.md) | Native Execution Workspace Outside Generated Roots | Accepted | 2026-03-01 | - | - |
| [0057](0057-mikrotik-netinstall-bootstrap-and-terraform-handover.md) | MikroTik Chateau Netinstall Bootstrap and Terraform Handover | Accepted | 2026-03-05 | - | - |
| [0058](0058-core-abstraction-layer.md) | Core Abstraction Layer and Device Module Architecture | Superseded | 2026-03-06 | - | [0059](0059-repository-split-and-class-object-instance-module-contract.md), [0062](0062-modular-topology-architecture-consolidation.md) |
| [0059](0059-repository-split-and-class-object-instance-module-contract.md) | Repository Split and Class-Object-Instance Module Contract | Superseded | 2026-03-06 | [0058](0058-core-abstraction-layer.md) | [0062](0062-modular-topology-architecture-consolidation.md) |
| [0060](0060-yaml-to-json-compiler-diagnostics-contract.md) | YAML-to-JSON Compiler and Diagnostics Contract | Superseded | 2026-03-06 | - | [0062](0062-modular-topology-architecture-consolidation.md) |
| [0061](0061-base-repo-versioned-class-object-instance-and-test-profiles.md) | Base Repo with Versioned Class-Object-Instance and Test Profiles | Superseded | 2026-03-06 | - | [0062](0062-modular-topology-architecture-consolidation.md) |
| [0062](0062-modular-topology-architecture-consolidation.md) | Topology v5 - Modular Class-Object-Instance Architecture | Accepted | 2026-03-06 | [0058](0058-core-abstraction-layer.md), [0059](0059-repository-split-and-class-object-instance-module-contract.md), [0060](0060-yaml-to-json-compiler-diagnostics-contract.md), [0061](0061-base-repo-versioned-class-object-instance-and-test-profiles.md) | - |
| [0063](0063-plugin-microkernel-for-compiler-validators-generators.md) | Plugin Microkernel for Compiler, Validators, and Generators | Implemented | 2026-03-06 | - | - |
| [0064](0064-os-taxonomy-object-property-model.md) | OS Taxonomy - Firmware and OS as Separate Entities | Implemented | 2026-03-08 | - | - |
| [0065](0065-plugin-api-contract-specification.md) | Plugin API Contract Specification | Proposed | 2026-03-09 | - | - |
| [0066](0066-plugin-testing-and-ci-strategy.md) | Plugin Testing and CI Strategy | Proposed | 2026-03-09 | - | - |
