# ADR 0097 PR5 Execution Checklist — Documentation Updates

**Date:** 2026-04-21
**Status:** ✅ COMPLETE
**Branch:** `adr0097-envelope-pr1`
**Depends on:** PR4 (✅ COMPLETE)

---

## Objective

Update all project documentation to reflect the ADR 0097 actor-style dataflow execution model:
- Document `execution_mode` manifest field
- Update plugin development guidance for envelope model
- Remove references to deprecated `subinterpreter_compatible` field
- Add ADR 0097 to relevant rule packs

---

## A. Documentation Inventory

### A1. Files requiring updates

| File | Priority | Update Type | Status |
|------|----------|-------------|--------|
| `docs/ai/rules/plugin-runtime.md` | HIGH | Add ADR 0097, execution_mode rules | ✅ |
| `CLAUDE.md` | MEDIUM | Update Plugin Contract section | ✅ |
| `docs/ai/AGENT-RULEBOOK.md` | LOW | Reference ADR 0097 if applicable | ⏭️ Skip |

### A2. Schema files

| File | Priority | Update Type | Status |
|------|----------|-------------|--------|
| Plugin manifest schema | MEDIUM | Document execution_mode enum | ⏭️ Deferred |

### A3. New documentation to create

| File | Priority | Purpose | Status |
|------|----------|---------|--------|
| `docs/guides/PLUGIN-ENVELOPE-MODEL.md` | HIGH | Developer guide for envelope semantics | ✅ Created |

---

## B. Task Details

### B1. Update `docs/ai/rules/plugin-runtime.md` — HIGH PRIORITY

**Current state:**
- Missing ADR 0097 in ADR Sources
- No mention of `execution_mode` field
- No mention of envelope semantics

**Required changes:**
- [ ] Add ADR 0097 to ADR Sources section
- [ ] Add rule for `execution_mode` declaration
- [ ] Add rules for snapshot/envelope semantics
- [ ] Add guidance on subinterpreter vs main_interpreter selection

**Draft rules to add:**

```markdown
## Execution Mode (ADR 0097)

8. Declare `execution_mode` explicitly in plugin manifests:
   - `subinterpreter`: Default for new plugins. Isolated parallel execution.
   - `main_interpreter`: Required for plugins that mutate context fields or access plugin_registry.
   - `thread_legacy`: Deprecated. Migration-only compatibility mode.

9. Follow envelope semantics:
   - Plugins receive immutable `PluginInputSnapshot`
   - Plugins return `PluginExecutionEnvelope` with proposed outputs
   - Main interpreter validates and commits envelope contents
   - Workers must not directly mutate pipeline-global state

10. Use `subinterpreter` mode unless plugin requires:
    - Direct `ctx` field mutation (ctx.model_lock, ctx.workspace_root, etc.)
    - Access to `ctx.config.get("plugin_registry")`
    - Dynamic module loading with `importlib.util`
```

### B2. Update `CLAUDE.md` — MEDIUM PRIORITY

**Current state:**
- Plugin Contract section references ADR0086
- No mention of execution_mode or envelope model

**Required changes:**
- [ ] Add ADR 0097 reference to Plugin Contract section
- [ ] Add execution_mode guidance
- [ ] Update "Working with Claude Code" section if needed

### B3. Create `docs/guides/PLUGIN-ENVELOPE-MODEL.md` — HIGH PRIORITY

**Purpose:** Developer guide for understanding and implementing plugins using envelope semantics.

**Outline:**
1. Overview of ADR 0097 changes
2. Execution modes explained
3. Snapshot input contract
4. Envelope output contract
5. Migration guide (legacy to envelope)
6. Compatibility checklist
7. Examples

---

## C. Validation

### C1. Documentation consistency check

```bash
# Verify no references to deprecated subinterpreter_compatible
grep -rn "subinterpreter_compatible" docs/ CLAUDE.md

# Verify ADR 0097 is referenced where relevant
grep -rn "ADR.?0097" docs/ CLAUDE.md
```

### C2. Link validation

```bash
# Check for broken internal references
# TBD - depends on documentation tooling
```

---

## D. Definition of Done

PR5 is complete when:

- [x] `docs/ai/rules/plugin-runtime.md` updated with ADR 0097 rules
- [x] `CLAUDE.md` Plugin Contract section updated
- [x] `docs/guides/PLUGIN-ENVELOPE-MODEL.md` created (353 lines)
- [x] No documentation references deprecated `subinterpreter_compatible`
- [x] ADR 0097 referenced in relevant rule packs
- [x] All commits follow project conventions
- [x] ADR 0097 main file updated with PR5 COMPLETE status

---

## E. Execution Plan

### Phase 1: Core Documentation (This Session)
1. Update `docs/ai/rules/plugin-runtime.md`
2. Update `CLAUDE.md` Plugin Contract section

### Phase 2: Developer Guide (This Session)
3. Create `docs/guides/PLUGIN-ENVELOPE-MODEL.md`

### Phase 3: Verification & Commit
4. Run validation checks
5. Update ADR 0097 status
6. Create commit(s)

---

## F. Notes

- PR5 builds on PR4 fleet migration results (74/84 plugins in subinterpreter mode)
- Documentation should reference `adr/0097-analysis/` evidence files where appropriate
- Keep documentation concise and actionable for AI agents and developers
