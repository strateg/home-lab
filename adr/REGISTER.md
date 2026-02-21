# ADR Register

| ADR | Title | Status | Date | Supersedes | Superseded By |
|-----|-------|--------|------|------------|---------------|
| [0001](0001-power-policy-layer-boundary.md) | Keep Physical Power in L1 and Outage Policies in L7 | Accepted | 2026-02-20 | - | - |
| [0002](0002-separate-data-and-power-links-in-l1.md) | Separate Data Links and Power Links in L1 | Accepted | 2026-02-20 | - | - |
| [0003](0003-data-links-naming-and-power-constraints.md) | Rename L1 Physical Links to Data Links and Constrain Data-Link Power | Accepted | 2026-02-20 | - | - |
| [0004](0004-l2-firewall-policy-references-and-validation.md) | Enforce Explicit L2 Firewall Policy References and Validation Semantics | Accepted | 2026-02-20 | - | - |
| [0005](0005-diagram-generation-determinism-and-binding-visibility.md) | Improve Diagram Generation Determinism and Firewall Binding Visibility | Accepted | 2026-02-20 | - | - |
| [0006](0006-mermaid-icon-mode-with-fallback.md) | Add Mermaid Icon Mode with Template Fallback | Superseded | 2026-02-20 | - | [0008](0008-mermaid-icon-node-default-and-runtime-pack-registration.md) |
| [0007](0007-icon-legend-and-complete-device-icon-coverage.md) | Add Icon Legend Page and Complete Device Icon Coverage | Accepted | 2026-02-20 | - | - |
| [0008](0008-mermaid-icon-node-default-and-runtime-pack-registration.md) | Make Mermaid Icon-Node the Default and Require Runtime Icon Pack Registration | Accepted | 2026-02-20 | [0006](0006-mermaid-icon-mode-with-fallback.md) | - |
| [0009](0009-robust-icon-pack-discovery-and-render-validation.md) | Robust Mermaid Icon Pack Discovery and Render Validation | Accepted | 2026-02-20 | - | - |
| [0010](0010-regeneration-pipeline-mermaid-quality-gate.md) | Add Mermaid Render Quality Gate to Regeneration Pipeline | Accepted | 2026-02-20 | - | - |
| [0011](0011-l1-physical-storage-taxonomy-and-l3-disk-binding.md) | L1 Physical Storage Taxonomy and L3 Disk Binding | Accepted | 2026-02-20 | - | - |
| [0012](0012-separate-l1-physical-disk-specs-from-l3-logical-storage-mapping.md) | Separate L1 Physical Disk Specs from L3 Logical Storage Mapping | Accepted | 2026-02-21 | - | - |
| [0013](0013-l1-storage-mount-taxonomy-soldered-replaceable-removable.md) | L1 Storage Mount Taxonomy for Soldered, Replaceable, and Removable Media | Accepted | 2026-02-21 | - | - |
| [0014](0014-l1-storage-slots-preferred-model-with-legacy-compatibility.md) | Use L1 Storage Slots as Preferred Model with Legacy Compatibility | Superseded | 2026-02-21 | - | [0015](0015-drop-legacy-storage-compatibility-after-storage-slots-migration.md) |
| [0015](0015-drop-legacy-storage-compatibility-after-storage-slots-migration.md) | Drop Legacy L1 Storage Compatibility After Storage Slots Migration | Accepted | 2026-02-21 | [0014](0014-l1-storage-slots-preferred-model-with-legacy-compatibility.md) | - |
| [0016](0016-l1-storage-media-registry-and-slot-attachments.md) | Separate L1 Storage Media Registry from Device Slot Attachments | Accepted | 2026-02-21 | - | - |
| [0017](0017-topology-tools-modular-refactor-validation-generation.md) | Modular Refactor of topology-tools into Validation and Generation Domains | Accepted | 2026-02-21 | - | - |
| [0018](0018-generation-common-loader-and-output-preparation.md) | Shared Generation Common Module for Layered Topology Loading and Output Directory Preparation | Accepted | 2026-02-21 | - | - |
| [0019](0019-proxmox-answer-layered-topology-only.md) | Proxmox Answer Generator Uses Layered Topology Only (No Legacy Root Sections) | Accepted | 2026-02-21 | - | - |
| [0020](0020-topology-tools-scripts-domain-layout.md) | Co-locate Generation and Validation Under topology-tools/scripts | Accepted | 2026-02-21 | - | - |
| [0021](0021-docs-generation-moved-to-scripts-generation-docs.md) | Move Documentation Generation Core into scripts/generation/docs | Accepted | 2026-02-21 | - | - |
| [0022](0022-docs-diagram-module-canonical-location.md) | Use scripts/generation/docs/docs_diagram.py as Canonical Diagram Module | Accepted | 2026-02-21 | - | - |
| [0023](0023-terraform-generators-and-templates-domain-layout.md) | Terraform Generators and Templates Domain Layout | Accepted | 2026-02-21 | - | - |
| [0024](0024-validators-namespace-alignment.md) | Rename Validation Package Namespace to validators | Accepted | 2026-02-21 | - | - |
| [0025](0025-generator-protocol-and-cli-base-class.md) | Generator Protocol and CLI Base Class | Accepted | 2026-02-21 | - | - |
| [0026](0026-l3-l4-taxonomy-refactoring-storage-chain-and-platform-separation.md) | L3/L4 Taxonomy Refactoring — Storage Chain and Platform Separation | Proposed | 2026-02-21 | - | - |
