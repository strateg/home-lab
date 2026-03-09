# 📋 Analysis Document Organization Rules

**Effective Date:** 9 марта 2026

---

## 🎯 Directory Structure for Analysis Documents

### Rule 1: ADR Analysis Goes to `adr/00XX-analysis/`

All analysis, proposals, and supporting documents for an ADR go into a subdirectory named after that ADR.

**Format:** `adr/00XX-analysis/`

**Examples:**
```
adr/0063-analysis/          ← Analysis for ADR 0063
adr/0064-analysis/          ← Analysis for ADR 0064 (existing)
adr/0065-analysis/          ← Analysis for ADR 0065 (when created)
```

### Rule 2: Each Analysis Directory Contains

**Required:**
- `INDEX.md` - Directory index and overview

**Optional:**
- Analysis documents (proposals, specifications)
- Detailed planning docs
- Spike/research results
- Implementation guides

**Example: `adr/0063-analysis/`**
```
adr/0063-analysis/
├── INDEX.md                                           ← Directory guide
├── PLAN.md                                           ← Original (existing)
├── 0064-plugin-api-contract-specification.md         ← Analysis
├── 0065-plugin-testing-and-ci-strategy.md           ← Analysis
└── ... other analysis documents
```

### Rule 3: ADR Core Files Stay in `adr/`

The main ADR files stay in root `adr/` directory.

**Example:**
```
adr/
├── 0063-plugin-microkernel-for-compiler-validators-generators.md  ← Main ADR
├── 0064-os-taxonomy-object-property-model.md                      ← Main ADR
├── 0063-analysis/  ← Analysis subdirectory
│   ├── INDEX.md
│   ├── ... analysis documents
│   └── ...
└── 0064-analysis/  ← Analysis subdirectory (existing)
    ├── INDEX.md
    ├── ... analysis documents
    └── ...
```

### Rule 4: Developer Guides Stay in `docs/`

Developer guides, tutorials, and quick references stay in `docs/`.

**Files in `docs/`:**
- `PLUGIN_AUTHORING_GUIDE.md` - How to write plugins
- `PLUGIN_IMPLEMENTATION_EXAMPLES.md` - Code examples
- `ADR0063_QUICK_REFERENCE.md` - Quick lookup
- `ADR0063_DOCUMENTATION_INDEX.md` - Navigation
- Other how-to guides

### Rule 5: When to Use Each Location

| Type | Location | Example |
|------|----------|---------|
| **Main ADR** | `adr/00XX-*.md` | `adr/0063-plugin-microkernel-...md` |
| **Analysis** | `adr/00XX-analysis/` | `adr/0063-analysis/api-proposal.md` |
| **Planning** | `adr/00XX-analysis/PLAN.md` | `adr/0063-analysis/PLAN.md` |
| **Developer Guide** | `docs/*.md` | `docs/PLUGIN_AUTHORING_GUIDE.md` |
| **Quick Ref** | `docs/ADR00XX_*.md` | `docs/ADR0063_QUICK_REFERENCE.md` |
| **Examples** | `docs/PLUGIN_*.md` | `docs/PLUGIN_IMPLEMENTATION_EXAMPLES.md` |

---

## 📝 Naming Conventions

### ADR Main Files
**Format:** `00XX-kebab-case-description.md`

**Examples:**
- `0063-plugin-microkernel-for-compiler-validators-generators.md`
- `0064-os-taxonomy-object-property-model.md`

### Analysis Directory Files
**Format:** `00XX-kebab-case-description.md` or descriptive name

**Examples:**
- `0064-plugin-api-contract-specification.md`
- `0065-plugin-testing-and-ci-strategy.md`
- `PLAN.md`
- `IMPLEMENTATION-GUIDE.md`

### Documentation Files
**Format:** `ADR00XX_KEBAB_OR_TITLE.md` or `descriptive-name.md`

**Examples:**
- `ADR0063_QUICK_REFERENCE.md`
- `ADR0063_DOCUMENTATION_INDEX.md`
- `PLUGIN_AUTHORING_GUIDE.md`
- `00-START-HERE.md`

---

## 📊 Content Guidelines

### In `adr/00XX-analysis/`

**Analysis documents contain:**
- Detailed specifications
- Proposals for core decisions
- Research findings
- Technical deep-dives
- Spike/POC results
- Implementation details

**Example:**
- `0064-plugin-api-contract-specification.md` - Detailed API contracts
- `0065-plugin-testing-and-ci-strategy.md` - Full testing strategy

### In `docs/`

**Developer guides contain:**
- Step-by-step instructions
- How-to guides
- Quick references
- Examples with code
- Troubleshooting
- Getting started guides

**Example:**
- `PLUGIN_AUTHORING_GUIDE.md` - How to write plugins
- `PLUGIN_IMPLEMENTATION_EXAMPLES.md` - Working examples

---

## 🔍 Structure for ADR with Analysis

When creating analysis for an ADR:

### Step 1: Create Analysis Directory
```bash
mkdir adr/00XX-analysis/
```

### Step 2: Create INDEX.md
```bash
touch adr/00XX-analysis/INDEX.md
```

In `INDEX.md`:
- Overview of analysis documents
- Links to all files
- Purpose of each document
- Recommendations for next steps

### Step 3: Add Analysis Documents
```bash
adr/00XX-analysis/
├── INDEX.md                         ← Required
├── PLAN.md                          ← From project (if exists)
├── 00YY-proposal-name.md           ← New proposals
├── analysis-research.md             ← Research/spikes
├── implementation-guide.md          ← How to implement
└── ...
```

### Step 4: Link from Main ADR
In the main ADR (`adr/00XX-*.md`), add:

```markdown
**Analysis Documents:** See `adr/00XX-analysis/INDEX.md`

**Related Analysis:**
- `adr/00XX-analysis/0064-plugin-api-contract-specification.md`
- `adr/00XX-analysis/0065-plugin-testing-and-ci-strategy.md`
```

---

## ✅ Checklist: ADR with Analysis

- [ ] Main ADR file created: `adr/00XX-kebab-case-description.md`
- [ ] Analysis directory created: `adr/00XX-analysis/`
- [ ] INDEX.md created in analysis directory
- [ ] All analysis documents in `adr/00XX-analysis/`
- [ ] Main ADR links to analysis directory
- [ ] Developer guides in `docs/` (if applicable)
- [ ] Quick references in `docs/` (if applicable)
- [ ] All files follow naming conventions
- [ ] INDEX files have clear descriptions

---

## 🎯 Benefits of This Organization

1. **Clear Separation** - Main decisions vs. supporting analysis
2. **Easy Navigation** - Subdirectories group related docs
3. **Scalability** - Works as more ADRs get analysis
4. **Developer Friendly** - Guides stay in docs/
5. **Audit Trail** - All analysis preserved for history
6. **Version Control** - Clean git history

---

## 📚 Example: Full ADR 0063 Organization

```
adr/
├── 0063-plugin-microkernel-for-compiler-validators-generators.md
│   ↓ Links to analysis
├── 0063-analysis/
│   ├── INDEX.md
│   ├── PLAN.md
│   ├── 0064-plugin-api-contract-specification.md
│   ├── 0065-plugin-testing-and-ci-strategy.md
│   └── ... (other analysis)
│
└── docs/
    ├── 00-START-HERE.md
    ├── PLUGIN_AUTHORING_GUIDE.md
    ├── PLUGIN_IMPLEMENTATION_EXAMPLES.md
    ├── ADR0063_QUICK_REFERENCE.md
    ├── ADR0063_DOCUMENTATION_INDEX.md
    ├── ADR0063_ENHANCEMENT_SUMMARY.md
    ├── ... (other guides)
    └── 00-ANALYSIS-DIRECTORY-INDEX.md
```

---

## 🔗 References

**Related Documents:**
- `adr/0063-analysis/INDEX.md` - ADR 0063 analysis index
- `docs/00-ANALYSIS-DIRECTORY-INDEX.md` - Documentation directory rules
- `docs/ADR0063_DOCUMENTATION_INDEX.md` - Documentation navigation

---

**Created:** 9 марта 2026
**Type:** Organization Rules
**Status:** Active

*These rules apply to all future ADR analysis documents.*
