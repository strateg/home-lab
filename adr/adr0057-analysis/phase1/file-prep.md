# Workstream 1C: File Preparation - Status Report

**Date:** 2026-03-03
**Status:** ⚠️ ACTION REQUIRED
**Owner:** Engineer

---

## File Inventory

### Current Location (WRONG)
```
assets/mikrotik-chateau/
├── auto-before-reset.backup ✅ EXISTS
└── exported_config_safe.rsc ✅ EXISTS
```

### Target Location (CORRECT)
```
topology-tools/templates/bootstrap/mikrotik/
├── init-terraform.rsc.j2 ✅ EXISTS
├── auto-before-reset.backup ❌ MISSING (needs move)
└── exported_config_safe.rsc ❌ MISSING (needs move)
```

---

## Issues Found

### Issue 1: Files in Wrong Location
**Problem:** Backup and RSC files are in `assets/` instead of `topology-tools/templates/`
**Impact:** HIGH - Generator can't find them
**Reason:** Files were placed in assets during earlier work
**Fix Required:** Move files to correct location

### Issue 2: RSC File Security
**Problem:** RSC file may contain real passwords
**Impact:** CRITICAL - Passwords in git
**Status:** ⚠️ NEEDS VERIFICATION
**Fix Required:** Sanitize RSC file before moving

---

## Action Plan

### Step 1: Verify RSC File Safety ⏳ IN PROGRESS
```bash
# Check for password patterns
grep -E "(password=|secret=|private-key=)" assets/mikrotik-chateau/exported_config_safe.rsc
```

**Expected:** All passwords should be `<PLACEHOLDER_*>`
**If real passwords found:** MUST sanitize before moving

### Step 2: Move Files to Correct Location
```bash
# Move backup file
mv assets/mikrotik-chateau/auto-before-reset.backup \
   topology-tools/templates/bootstrap/mikrotik/

# Move RSC file (after sanitization)
mv assets/mikrotik-chateau/exported_config_safe.rsc \
   topology-tools/templates/bootstrap/mikrotik/
```

### Step 3: Update .gitignore (if needed)
Ensure `assets/` is not tracked or cleanup is noted

### Step 4: Verify Files in Place
```bash
ls -la topology-tools/templates/bootstrap/mikrotik/
```

Expected output:
- init-terraform.rsc.j2
- auto-before-reset.backup
- exported_config_safe.rsc

---

## RSC File Sanitization Checklist

**Before moving RSC file, verify:**

- [ ] No real passwords (`password=<PLACEHOLDER_*>`)
- [ ] No real private keys (`private-key=<PLACEHOLDER_*>`)
- [ ] No real secrets (`secret=<PLACEHOLDER_*>`)
- [ ] No real WiFi passphrases
- [ ] No internal sensitive hostnames
- [ ] File has existence checks (safe version)
- [ ] File has error handlers

**If any real secrets found:**
1. Replace with `<PLACEHOLDER_NAME>`
2. Document what was replaced
3. Add to security guidelines

---

## Timeline

| Task | Duration | Status |
|------|----------|--------|
| Verify RSC safety | 15 min | ⏳ Next |
| Sanitize if needed | 30 min | ⏳ Pending |
| Move files | 5 min | ⏳ Pending |
| Verify placement | 5 min | ⏳ Pending |
| **Total** | **~1 hour** | |

---

## Next Actions

### Immediate (Next 30 min)
1. ⏳ Read `exported_config_safe.rsc` and check for secrets
2. ⏳ Sanitize if passwords found
3. ⏳ Move both files to correct location
4. ✅ Update progress tracker

### After File Move
- [ ] Update documentation references
- [ ] Commit changes to git
- [ ] Test generator can find files
- [ ] Mark Workstream 1C complete

---

## Dependencies

**Blocks:**
- Phase 2: Generator updates (needs files in place)
- Phase 3: Ansible playbook (needs files for copy tasks)

**Blocked by:**
- RSC sanitization (security requirement)

---

**Status:** ⚠️ PAUSED - Awaiting RSC security verification
**Next:** Check RSC file for real passwords
