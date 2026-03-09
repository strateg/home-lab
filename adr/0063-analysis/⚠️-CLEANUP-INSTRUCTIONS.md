# ⚠️ Cleanup Instructions

**Date:** 9 марта 2026
**Status:** Manual Cleanup Needed

---

## 🗑️ Files to Remove

The following files were created with WRONG ADR numbers - **DELETE them:**

### In root `adr/` directory
- ❌ `adr/0064-plugin-api-contract-specification.md`
  - This file uses wrong number (conflicts with existing ADR 0064)
  - The correct version is in `adr/0063-analysis/0065-plugin-api-contract-specification.md`

- ❌ `adr/0065-plugin-testing-and-ci-strategy.md`
  - This file uses wrong number
  - The correct version is in `adr/0063-analysis/0066-plugin-testing-and-ci-strategy.md`

### In root `docs/` directory (optional cleanup if moving to analysis/)
These are in the right place and can stay, but they duplicate analysis in `adr/0063-analysis/`:

- ⚠️ These are development guides, so they can stay in `docs/`
  - `docs/PLUGIN_AUTHORING_GUIDE.md` ✅ KEEP (development guide)
  - `docs/PLUGIN_IMPLEMENTATION_EXAMPLES.md` ✅ KEEP (examples for developers)

### In root directory
- ⚠️ `ADR0063-DOCUMENTATION-COMPLETE.md` - Navigation file (can keep)
- ⚠️ `📋-COMPLETE-FILE-LIST.md` - List file (can keep or delete)

---

## 🔧 What to Do

### Option 1: Git Remove (Preferred)
```bash
cd c:\Users\Dmitri\PycharmProjects\home-lab\

# Remove incorrect ADR files with wrong numbers
git rm adr/0065-plugin-api-contract-specification.md
git rm adr/0065-plugin-testing-and-ci-strategy.md

# Commit
git commit -m "fix: remove ADRs with wrong numbers, keep correct versions (0065, 0066) in adr/0063-analysis/"
```

### Option 2: Manual Delete
In file explorer:
1. Delete `adr/0064-plugin-api-contract-specification.md`
2. Delete `adr/0065-plugin-testing-and-ci-strategy.md`

---

## ✅ Correct File Structure After Cleanup

```
adr/
├── 0063-plugin-microkernel-for-compiler-validators-generators.md  ← Main ADR
├── 0064-os-taxonomy-object-property-model.md                      ← Main ADR
├── 0063-analysis/                                                   ← Analysis directory
│   ├── INDEX.md                                                    ✅
│   ├── 0065-plugin-api-contract-specification.md                 ✅ CORRECT NUMBER
│   ├── 0066-plugin-testing-and-ci-strategy.md                    ✅ CORRECT NUMBER
│   ├── PLAN.md                                                     ✅
│   └── ...
└── 0064-analysis/                                                   ← Existing analysis
    └── ...

docs/
├── 00-START-HERE.md                                                ✅
├── 00-ANALYSIS-ORGANIZATION-RULES.md                              ✅
├── 00-ANALYSIS-DIRECTORY-INDEX.md                                 ✅
├── PLUGIN_AUTHORING_GUIDE.md                                      ✅
├── PLUGIN_IMPLEMENTATION_EXAMPLES.md                              ✅
├── ADR0063_QUICK_REFERENCE.md                                     ✅
├── ADR0063_DOCUMENTATION_INDEX.md                                 ✅
├── ADR0063_ENHANCEMENT_SUMMARY.md                                 ✅
├── 🎯-EXECUTIVE-SUMMARY.md                                        ✅
├── ✅-ADR0063-ANALYSIS-COMPLETE.md                               ✅
├── ✅-COMPLETION-CHECKLIST.md                                    ✅
├── 📦-DELIVERABLES-COMPLETE.md                                   ✅
└── ...
```

---

## 📝 Summary

**Incorrect files to remove (WRONG NUMBERS):**
- ❌ `adr/0064-plugin-api-contract-specification.md` (should be 0065)
- ❌ `adr/0065-plugin-testing-and-ci-strategy.md` (should be 0066)

**Correct locations (RIGHT NUMBERS):**
- ✅ `adr/0063-analysis/0065-plugin-api-contract-specification.md`
- ✅ `adr/0063-analysis/0066-plugin-testing-and-ci-strategy.md`

---

## 🎯 Next Steps

1. Remove the 2 incorrect files
2. Verify structure matches "Correct File Structure" above
3. All analysis documentation will be properly organized

---

**After cleanup:**
- ✅ Correct file organization
- ✅ No duplicate files
- ✅ All rules followed
- ✅ Clean git history
