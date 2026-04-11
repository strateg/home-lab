# SWOT Analysis: ADR 0095 Topology Inspection and Introspection Toolkit

**Analysis Date:** 2026-04-11  
**Scope:** Current ADR0095 inspection toolkit state after v1 implementation  
**Assessment Basis:** `adr/0095-topology-inspection-and-introspection-toolkit.md`, current `scripts/inspection/inspect_topology.py`, `taskfiles/inspect.yml`, `tests/test_inspect_topology.py`, and `build/effective-topology.json`

---

## Executive Summary

**Overall Assessment:** ADR0095 has a functioning and usable v1 inspection surface, but the optimization problem has shifted from “tool absent” to “tool surface and information architecture need consolidation.”

The toolkit already provides:
- unified `task inspect:*` namespace,
- a single canonical CLI entrypoint,
- working dependency inspection,
- class tree inspection,
- object and instance listings,
- capability-pack inspection,
- DOT export.

The main weaknesses are now concentrated in:
- semantic depth of dependency traceability,
- dedicated inheritance traceability,
- capability inspection spread across multiple entities,
- minimal direct automated coverage,
- high output volume for some commands,
- concentration of multiple concerns inside one CLI module.

---

## Strengths

### S1. Unified Inspection Surface Already Exists

ADR0095 already has a real operational surface rather than a paper design only:
- canonical CLI: `scripts/inspection/inspect_topology.py`
- public task namespace: `task inspect:*`
- implemented commands: `summary`, `classes`, `objects`, `instances`, `search`, `deps`, `deps-dot`, `capability-packs`

**Practical value:** operator and developer introspection is already scriptable and repeatable.

---

### S2. Canonical Data Contract Is Clear

The toolkit has one explicit default input:
- `build/effective-topology.json`

The capability-pack inspection path is also explicit:
- topology manifest → `framework.capability_packs` → pack catalog YAML

**Practical value:** the tool is not sourcing information from ad-hoc grep or generated artifacts with hidden precedence.

---

### S3. Existing Coverage of Core Inspection Domains

The current toolkit already covers the main inspection domains:
- hierarchy (`classes`)
- bindings (`objects`)
- runtime population (`instances`)
- search (`search`)
- instance dependencies (`deps`, `deps-dot`)
- capability-pack binding contract (`capability-packs`)

**Practical value:** optimization can focus on refinement and decomposition, not greenfield invention.

---

### S4. Real Topology Density Is Already Exposed

Current home-lab data shows the toolkit is operating against a non-trivial model:
- 45 classes
- 116 objects
- 151 instances
- 274 dependency edges
- 16 instance groups

**Practical value:** optimization can be grounded in real information density rather than hypothetical scale.

---

### S5. Read-Only Boundary Is Clean

ADR0095 explicitly keeps the toolkit:
- read-only,
- source-driven,
- non-invasive,
- outside of online system introspection.

**Practical value:** inspection improvements can be made without entangling topology authoring, runtime mutation, or deploy behavior.

---

## Weaknesses

### W1. Multiple Concerns Are Concentrated in One CLI Module

Current implementation facts:
- `scripts/inspection/inspect_topology.py`
- 578 lines
- 22 top-level functions

The same module currently contains:
- artifact loading,
- YAML loading,
- catalog resolution,
- dependency extraction,
- capability-pack aggregation,
- output formatting,
- CLI parsing.

**Observed weakness:** implementation concentration increases change surface and makes internal decomposition a real concern.

---

### W2. Dependency Traceability Is Heuristic, Not Semantic

Current dependency extraction relies on:
- fields ending with `_ref` / `_refs`
- scans of `instance_data` and runtime `instance`

Measured state on home-lab:
- 274 edges total
- 23 unresolved refs

**Observed weakness:** dependency relations are discoverable, but the model does not currently distinguish semantic relation types.

---

### W3. Inheritance Traceability Is Present but Indirect

Inheritance data exists:
- 9 class inheritance rows in effective topology

But dedicated inheritance-focused inspection is absent; current inheritance visibility is primarily through the general `classes` tree.

**Observed weakness:** inheritance is inspectable, but not isolated as its own question-oriented surface.

---

### W4. Capability Information Is Split Across Several Structures

Capability-related information is distributed across:
- class `required_capabilities`
- class `optional_capabilities`
- class `capability_packs`
- object `enabled_capabilities`
- object `enabled_packs`
- pack catalog YAML

Current direct inspect support is strongest for pack bindings, not for the broader descriptive capability model.

**Observed weakness:** capability traceability exists in data, but not yet as one compact unified inspection surface.

---

### W5. Output Volume Is Uneven

Measured output sizes on current topology:
- `summary`: 22 lines
- `classes`: 47 lines
- `objects`: 157 lines
- `instances`: 160 lines
- `search mikrotik`: 40 lines
- `deps rtr-mikrotik-chateau`: 42 lines
- `capability-packs`: 30 lines

**Observed weakness:** some commands are compact, but `objects` and `instances` already exceed first-screen density by a wide margin.

---

### W6. Direct Test Coverage Is Minimal

Current dedicated inspect test facts:
- 1 test in `tests/test_inspect_topology.py`
- coverage currently focused on `capability-packs`

No direct command-contract tests were found for:
- `summary`
- `classes`
- `objects`
- `instances`
- `search`
- `deps`
- `deps-dot`

**Observed weakness:** regression confidence for most inspection surface is low relative to current command breadth.

---

## Opportunities

### O1. Consolidate Inspection Around Question Types

The current surface already exposes several question classes:
- What exists?
- What inherits from what?
- What depends on what?
- What capabilities are declared or enabled?

**Opportunity:** the toolkit can be optimized around stable inspection questions rather than around raw entity dumps.

---

### O2. Reuse One Normalized Internal Index Layer

Current facts show repeated dependence on:
- class hierarchy
- object/class binding
- instance alias resolution
- dependency graph extraction
- capability-pack catalog loading

**Opportunity:** inspection behavior can be expressed over shared normalized indexes rather than repeated ad-hoc traversal paths.

---

### O3. Add Compact and Structured Views Without Breaking Public Contract

ADR0095 already fixes:
- one canonical CLI,
- one task namespace.

It does **not** require only one presentation style.

**Opportunity:** compact summaries, focused trace views, and machine-readable modes can be added without changing the public entrypoint contract.

---

### O4. Expand Capability Inspection Beyond Packs

Current model already holds enough data to inspect:
- class intent,
- object enabled functionality,
- pack aggregation,
- class/object mismatches.

**Opportunity:** broader capability traceability can be surfaced without introducing a new source-of-truth model.

---

### O5. Add Stronger Contract Testing with Small Fixtures

The existing `capability-packs` test already demonstrates a workable fixture pattern:
- local topology manifest
- local capability catalog
- local effective topology JSON

**Opportunity:** the same pattern can be reused to cover dependency extraction, inheritance representation, search behavior, and compact output invariants.

---

## Threats

### T1. Surface Growth Without Internal Structure

If more commands or modes are added into the same undivided CLI module, the tool may become harder to maintain than the inspection problem it tries to solve.

**Threat form:** structural complexity growth inside the implementation.

---

### T2. Information Expansion Can Defeat Compactness

The user goal explicitly combines:
- more traceability,
- more capability visibility,
- more relationship detail,
- compact display.

These goals are naturally in tension.

**Threat form:** every added traceability axis can increase output breadth faster than operator readability.

---

### T3. Heuristic Dependencies Can Be Interpreted as Ground Truth

Current dependency extraction is functional, but heuristic.

**Threat form:** operators may over-trust relation output as fully semantic even when it is currently syntax-derived.

---

### T4. Capability Scope Can Drift from “packs” to “everything” Without Clear Boundaries

Capability information spans classes, objects, and pack catalog definitions.

**Threat form:** capability inspection can become an overloaded catch-all surface unless bounded by stable inspection questions and consistent terminology.

---

### T5. Sparse Test Coverage Increases Refactor Risk

Current implementation already has meaningful internal surface area:
- 578 lines
- 22 functions
- 8 subcommands

**Threat form:** optimization/refactoring can unintentionally change output semantics without early regression detection.

---

## SWOT Matrix

| Strengths | Weaknesses |
|-----------|------------|
| S1. Unified inspection surface already exists | W1. Multiple concerns concentrated in one CLI module |
| S2. Canonical data contract is clear | W2. Dependency traceability is heuristic, not semantic |
| S3. Existing coverage of core inspection domains | W3. Inheritance traceability is present but indirect |
| S4. Real topology density is already exposed | W4. Capability information is split across several structures |
| S5. Read-only boundary is clean | W5. Output volume is uneven |
|  | W6. Direct test coverage is minimal |

| Opportunities | Threats |
|---------------|---------|
| O1. Consolidate inspection around question types | T1. Surface growth without internal structure |
| O2. Reuse one normalized internal index layer | T2. Information expansion can defeat compactness |
| O3. Add compact and structured views without breaking public contract | T3. Heuristic dependencies can be interpreted as ground truth |
| O4. Expand capability inspection beyond packs | T4. Capability scope can drift without clear boundaries |
| O5. Add stronger contract testing with small fixtures | T5. Sparse test coverage increases refactor risk |

---

## Concluding SWOT Statement

ADR0095 is not blocked by missing tooling anymore.  
The present state is a **working v1 toolkit with a design-optimization problem**, not a bootstrap problem.

The strongest available assets are:
- canonical entrypoint,
- stable task namespace,
- real compiled data source,
- already implemented inspection commands.

The main pressure points are:
- semantics and compactness of traceability,
- decomposition of concerns,
- capability-view unification,
- regression safety during optimization.
