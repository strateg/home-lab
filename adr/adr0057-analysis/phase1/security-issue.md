# 🚨 Phase 1 - CRITICAL SECURITY ISSUE FOUND

**Date:** 2026-03-03 10:15
**Status:** 🔴 SECURITY ISSUE - IMMEDIATE ACTION REQUIRED

---

## 🔴 CRITICAL: Real Secrets Found in RSC File

### Location
`assets/mikrotik-chateau/exported_config_safe.rsc`

### Secrets Found

1. **WiFi Passphrase** (Lines 21, 28)
   ```routeros
   .passphrase=HX3F66WQYW
   ```
   **Status:** 🔴 REAL PASSWORD IN GIT

2. **WireGuard Private Key** (Line 40-41)
   ```routeros
   private-key="iFjypYY48CnGSH6UJtDzlvmp9vZIZjrNdX+iFHc8oUE="  # pragma: allowlist secret
   ```
   **Status:** 🔴 REAL PRIVATE KEY IN GIT

3. **SMB Password** (Line 49)
   ```routeros
   smb-server-password=""
   ```
   **Status:** ✅ OK - Empty string

---

## ⚠️ Security Impact

### HIGH RISK
- **WiFi Password:** Compromises wireless network security
- **WireGuard Key:** Compromises VPN security
- **Git History:** Secrets are permanent in git history even after removal

### Immediate Actions Required

1. **DO NOT move files as-is** ❌
2. **Sanitize RSC file first** ⏳
3. **Consider key rotation** ⚠️

---

## 🔧 Sanitization Plan

### Step 1: Create Sanitized Version
Replace real secrets with placeholders:

```bash
# Create sanitized copy
cp assets/mikrotik-chateau/exported_config_safe.rsc \
   assets/mikrotik-chateau/exported_config_safe_SANITIZED.rsc

# Replace secrets
sed -i 's/passphrase=HX3F66WQYW/passphrase=<PLACEHOLDER_WIFI_PASSPHRASE>/g' \
    assets/mikrotik-chateau/exported_config_safe_SANITIZED.rsc

sed -i 's/private-key="iFjypYY48CnGSH6UJtDzlvmp9vZIZjrNdX+iFHc8oUE="/private-key=<PLACEHOLDER_WG_PRIVATE_KEY>/g' \  # pragma: allowlist secret
    assets/mikrotik-chateau/exported_config_safe_SANITIZED.rsc
```

### Step 2: Verify Sanitization
```bash
# Check no real secrets remain
grep -E "(HX3F66WQYW|iFjypYY48CnGSH6UJtDzlvmp9vZIZjrNdX)" \
    assets/mikrotik-chateau/exported_config_safe_SANITIZED.rsc
# Should return: no matches

# Check placeholders present
grep "<PLACEHOLDER_" assets/mikrotik-chateau/exported_config_safe_SANITIZED.rsc
# Should show placeholders
```

### Step 3: Move Sanitized File
```bash
# Move sanitized version to correct location
mv assets/mikrotik-chateau/exported_config_safe_SANITIZED.rsc \
   topology-tools/templates/bootstrap/mikrotik/exported_config_safe.rsc

# Also move backup file
mv assets/mikrotik-chateau/auto-before-reset.backup \
   topology-tools/templates/bootstrap/mikrotik/
```

### Step 4: Remove Original from Git
```bash
# Remove original with secrets
git rm assets/mikrotik-chateau/exported_config_safe.rsc

# Add sanitized version
git add topology-tools/templates/bootstrap/mikrotik/exported_config_safe.rsc
git add topology-tools/templates/bootstrap/mikrotik/auto-before-reset.backup

# Commit with note
git commit -m "fix: sanitize RSC file - remove real WiFi/WireGuard secrets

- Replaced real WiFi passphrase with placeholder
- Replaced real WireGuard private key with placeholder
- Moved files to correct location (topology-tools/templates)
- See ADR 0057 security guidelines"
```

---

## 🔐 Post-Sanitization: Key Rotation Recommendation

### Recommended Actions (Security Best Practice)

1. **WiFi Passphrase**
   - ✅ Already in git history
   - ⚠️ Recommend rotation if network is production
   - Action: Generate new passphrase, update via Terraform

2. **WireGuard Private Key**
   - ✅ Already in git history
   - 🔴 **MUST rotate** - private key compromise
   - Action: Generate new keypair, update via Terraform

### Rotation Timeline
- **Immediate:** Sanitize and commit
- **This week:** Rotate WireGuard keys
- **Optional:** Rotate WiFi if production network

---

## 📋 Updated Workstream 1C Checklist

### File Preparation Tasks
- [x] Locate bootstrap files
- [x] Identify security issues
- [ ] **Sanitize RSC file** ⏳ IN PROGRESS
- [ ] Verify sanitization complete
- [ ] Move files to correct location
- [ ] Remove originals from assets/
- [ ] Commit sanitized versions
- [ ] Test files are accessible
- [ ] Mark workstream complete

---

## 🚦 Blocking Status

**Current Status:** 🔴 BLOCKED - Security issue must be fixed first

**Blocks:**
- ❌ Cannot move files until sanitized
- ❌ Cannot commit unsanitized RSC to new location
- ❌ Phase 2 generator updates (needs clean files)

**Unblocks when:**
- ✅ RSC file sanitized
- ✅ Files moved to correct location
- ✅ Committed to git

---

## 📊 Phase 1 Progress Update

### Workstream Status

| Workstream | Progress | Status | Blocker |
|-----------|----------|--------|---------|
| 1A: Template Audit | 100% | ✅ COMPLETE | None |
| 1B: Tool Selection | 0% | ⏳ Not Started | None |
| 1C: File Preparation | 50% | 🔴 BLOCKED | Security issue |
| 1D: Secret Integration | 0% | ⏳ Pending Week 2 | None |

**Phase 1 Status:** ⚠️ ON HOLD - Security issue must be resolved

---

## ⏱️ Time Estimate

| Task | Duration | Status |
|------|----------|--------|
| Create sanitized copy | 5 min | ⏳ Next |
| Run sanitization script | 2 min | ⏳ Next |
| Verify sanitization | 5 min | ⏳ Next |
| Move files | 2 min | ⏳ Next |
| Git operations | 5 min | ⏳ Next |
| Document rotation needs | 10 min | ⏳ Next |
| **Total** | **~30 min** | |

---

## 🎯 Next Actions

### IMMEDIATE (Next 30 min)
1. ⏳ Create sanitization script
2. ⏳ Run sanitization
3. ⏳ Verify no secrets remain
4. ⏳ Move files to correct location
5. ⏳ Commit sanitized versions

### After Sanitization
- [ ] Document rotation requirements
- [ ] Continue Workstream 1B (tool selection)
- [ ] Resume Phase 1 progress

### This Week
- [ ] Rotate WireGuard keys (security)
- [ ] Update production config with new keys
- [ ] Complete Phase 1

---

**Priority:** 🔴 CRITICAL - Must sanitize before continuing
**Next Step:** Create and run sanitization script
**Estimated Fix:** 30 minutes
