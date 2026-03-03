# Template Audit: init-terraform.rsc.j2

**Date:** 2026-03-03
**Template:** `topology-tools/templates/bootstrap/mikrotik/init-terraform.rsc.j2`
**Total Lines:** 116
**Status:** ✅ AUDIT COMPLETE

---

## Executive Summary

**Template Quality:** ⚠️ NEEDS REFACTORING
**Day-0 Content:** ~40% (lines 20-65)
**Day-1/2 Content:** ~35% (lines 67-96)
**Dead/Unnecessary:** ~25% (lines 24-34, 39, 78-92, 94-100)

**Verdict:** Template contains significant day-1/2 logic that should move to Terraform. Refactoring recommended.

---

## Line-by-Line Classification

| Lines | Section | Category | Keep/Move/Remove | Priority | Notes |
|-------|---------|----------|------------------|----------|-------|
| 1-18 | Header/Comments | Documentation | KEEP | Low | Harmless, can simplify |
| 20-22 | System Identity | **Day-0 REQUIRED** | **KEEP** | **HIGH** | Essential for Terraform |
| 24-34 | SSL Certificate | Day-1/2 Logic | **MOVE** | HIGH | Should be Terraform resource |
| 36-40 | REST API Enable | **Day-0 REQUIRED** | **KEEP** | **HIGH** | Essential for Terraform |
| 41-45 | Disable Services | **Day-0 REQUIRED** | **KEEP** | **HIGH** | Security hardening |
| 47-55 | Terraform Group | **Day-0 REQUIRED** | **KEEP** | **HIGH** | User permissions |
| 57-65 | Terraform User | **Day-0 REQUIRED** | **KEEP** | **HIGH** | Terraform credentials |
| 67-76 | Firewall: REST API | **Day-0 REQUIRED** | **KEEP** | **HIGH** | API access required |
| 78-84 | Firewall: WinBox | Day-1/2 Logic | **MOVE** | MEDIUM | Should be Terraform |
| 86-92 | Firewall: SSH | Day-1/2 Logic | **MOVE** | MEDIUM | Should be Terraform |
| 94-96 | DNS Configuration | Day-1/2 Logic | **MOVE** | MEDIUM | Should be Terraform |
| 98-100 | Backup Creation | Utility | REMOVE | LOW | Can be manual |
| 102-116 | Summary/Output | Documentation | SIMPLIFY | LOW | Reduce verbosity |

---

## Detailed Analysis

### ✅ Day-0 REQUIRED (KEEP - 8 sections, ~45 lines)

#### 1. System Identity (Lines 20-22)
```jinja2
/system identity set name="{{ router_name }}"
```
**Verdict:** **KEEP** - Essential for device identification
**Reason:** Terraform needs to know device identity

#### 2. REST API Enable (Lines 36-40)
```jinja2
/ip service set www-ssl certificate=rest-api-cert disabled=no port={{ api_port }}
/ip service set www disabled=no port=80
```
**Verdict:** **PARTIAL KEEP** - Line 38 essential, line 39 questionable
**Reason:** REST API required for Terraform provider
**Issue:** Line 39 (www on port 80) may not be needed
**Recommendation:** Remove line 39 or make conditional

#### 3. Disable Insecure Services (Lines 41-45)
```jinja2
/ip service set telnet disabled=yes
/ip service set ftp disabled=yes
/ip service set api disabled=yes
/ip service set api-ssl disabled=yes
```
**Verdict:** **KEEP** - Security hardening
**Reason:** Reduces attack surface before Terraform takes over
**Note:** Line 45 (api-ssl disabled) conflicts with line 38 - BUG!

#### 4. Terraform Group (Lines 47-55)
```jinja2
:if ([:len [/user group find where name="{{ terraform_group }}"]] = 0) do={
    /user group add name={{ terraform_group }} policy=api,local,policy,read,reboot,sensitive,ssh,test,write
}
```
**Verdict:** **KEEP** - Required for user permissions
**Reason:** Terraform user needs appropriate group

#### 5. Terraform User (Lines 57-65)
```jinja2
:if ([:len [/user find where name="{{ terraform_user }}"]] = 0) do={
    /user add name={{ terraform_user }} group={{ terraform_group }} password="{{ terraform_password }}"
}
```
**Verdict:** **KEEP** - Essential credentials
**Reason:** Terraform needs authentication
**Security:** Password in template OK (rendered to ignored workspace)

#### 6. Firewall: REST API (Lines 67-76)
```jinja2
/ip firewall filter add chain=input action=accept protocol=tcp dst-port={{ api_port }} src-address={{ lan_network }} comment="Allow REST API from LAN"
```
**Verdict:** **KEEP** - Required for API access
**Reason:** Without this, Terraform can't connect

---

### ⚠️ Day-1/2 Logic (MOVE to Terraform - 5 sections, ~30 lines)

#### 7. SSL Certificate Creation (Lines 24-34)
```jinja2
:if ([:len [/certificate find where name="rest-api-cert"]] = 0) do={
    /certificate add name=rest-api-cert ...
    /certificate sign rest-api-cert
}
```
**Verdict:** **MOVE** to Terraform
**Reason:** Certificate management is day-1/2 infrastructure
**Impact:** HIGH - Referenced by line 38
**Recommendation:** Use self-signed or Let's Encrypt via Terraform
**Alternative:** Keep minimal self-signed for bootstrap, replace via Terraform

#### 8. Firewall: WinBox (Lines 78-84)
```jinja2
/ip firewall filter add chain=input action=accept protocol=tcp dst-port=8291 src-address={{ lan_network }} comment="Allow WinBox from LAN"
```
**Verdict:** **MOVE** to Terraform
**Reason:** Non-essential for day-0, WinBox is management tool
**Impact:** MEDIUM - Convenience feature, not required

#### 9. Firewall: SSH (Lines 86-92)
```jinja2
/ip firewall filter add chain=input action=accept protocol=tcp dst-port=22 src-address={{ lan_network }} comment="Allow SSH from LAN"
```
**Verdict:** **MOVE** to Terraform
**Reason:** SSH is optional recovery, not required for Terraform
**Impact:** MEDIUM - Can be added later via Terraform
**Note:** ADR 0057 mentions "optional SSH recovery" - could be conditional

#### 10. DNS Configuration (Lines 94-96)
```jinja2
/ip dns set servers={{ dns_servers | join(',') }} allow-remote-requests=yes
```
**Verdict:** **MOVE** to Terraform
**Reason:** Network configuration is day-1/2
**Impact:** LOW - Not required for API connectivity

---

### 🗑️ Dead/Unnecessary (REMOVE - 3 sections, ~15 lines)

#### 11. Backup Creation (Lines 98-100)
```jinja2
:do { /export file=pre-terraform-backup } on-error={ :log warning "Could not create backup" }
```
**Verdict:** **REMOVE** or make optional
**Reason:** Not part of handover contract, can be manual
**Alternative:** Operator can create backup before bootstrap

#### 12. Verbose Summary (Lines 102-116)
```jinja2
:log info "========================================"
:put "MikroTik Bootstrap Complete!"
```
**Verdict:** **SIMPLIFY**
**Reason:** Too verbose, 15 lines just for output
**Recommendation:** Reduce to 2-3 lines max

---

## Critical Issues Found

### 🔴 Issue 1: API-SSL Conflict (Line 45)
```jinja2
/ip service set api-ssl disabled=yes  # Line 45
:do { /ip service set www-ssl disabled=no ... }  # Line 38
```
**Problem:** Disables api-ssl, then tries to use www-ssl
**Impact:** HIGH - May break REST API
**Fix:** Remove line 45 or change to enable www-ssl properly

### 🔴 Issue 2: Certificate Dependency
**Problem:** Line 38 depends on certificate from lines 24-34
**Impact:** HIGH - If cert creation removed, API breaks
**Fix:** Either keep minimal cert creation or use built-in cert

### ⚠️ Issue 3: Port 80 HTTP (Line 39)
```jinja2
/ip service set www disabled=no port=80
```
**Problem:** Enables insecure HTTP
**Impact:** MEDIUM - Security concern
**Fix:** Remove or make conditional with justification

---

## Refactoring Recommendations

### Option A: Minimal Refactor (Conservative)
**Keep:** Lines 20-22, 36, 41-45, 47-65, 67-76
**Remove:** Lines 24-34, 39, 78-92, 94-100, 102-116 (simplify)
**Result:** ~55 lines → ~35 lines
**Timeline:** 1 day

**Pros:**
- Less disruptive
- Maintains most functionality
- Quick to implement

**Cons:**
- Still has some day-1/2 logic
- Certificate issue unresolved

### Option B: Strict Day-0 Only (Recommended)
**Keep:** Lines 20-22, 47-65, 67-76
**Add:** Minimal self-signed cert (3 lines)
**Add:** www-ssl enable (1 line)
**Remove:** Everything else
**Result:** ~55 lines → ~25 lines
**Timeline:** 2 days

**Pros:**
- Clean separation of concerns
- Matches ADR 0057 specification
- Forces Terraform ownership

**Cons:**
- More changes
- Requires Terraform resources for removed features

### Option C: Keep Current + Document (Lazy)
**Keep:** All lines as-is
**Add:** Comments marking day-1/2 sections
**Fix:** Critical bugs (lines 39, 45)
**Result:** 116 lines → 118 lines
**Timeline:** 2 hours

**Pros:**
- No disruption
- Quick fix

**Cons:**
- Doesn't follow ADR 0057 principle
- Technical debt remains

---

## Decision Matrix

| Aspect | Option A | Option B | Option C |
|--------|----------|----------|----------|
| **Alignment with ADR** | Medium | **High** | Low |
| **Risk** | Low | Medium | Low |
| **Effort** | 1 day | 2 days | 2 hours |
| **Technical Debt** | Some | **None** | High |
| **Recommended** | If rushed | **YES** | No |

---

## Recommended Action: Option B

**Decision:** Create new minimal template based on ADR 0057 specification

**New Template:** `init-terraform-minimal.rsc.j2` (~25 lines)

**Contents:**
1. System identity
2. Minimal self-signed certificate
3. Enable www-ssl API
4. Disable insecure services
5. Create Terraform group
6. Create Terraform user
7. Firewall: Allow API from LAN

**Migrate Day-1/2 to Terraform:**
- WinBox firewall rule → Terraform resource
- SSH firewall rule → Terraform resource (optional)
- DNS configuration → Terraform resource
- Full certificate management → Terraform resource

---

## Variables Analysis

### Template Variables Used
| Variable | Purpose | Source | Required |
|----------|---------|--------|----------|
| `router_name` | System identity | Topology | ✅ Yes |
| `router_ip` | Management IP | Topology | ✅ Yes |
| `router_hostname` | Certificate CN | Topology | ⚠️ If cert kept |
| `dns_domain` | Certificate CN | Topology | ⚠️ If cert kept |
| `api_port` | REST API port | Topology | ✅ Yes |
| `terraform_user` | Username | Topology | ✅ Yes |
| `terraform_password` | Password | **Vault/SOPS** | ✅ Yes |
| `terraform_group` | Group name | Topology | ✅ Yes |
| `lan_network` | Firewall CIDR | Topology | ✅ Yes |
| `dns_servers` | DNS list | Topology | ⚠️ If kept |

**Secrets:** Only `terraform_password` - correctly handled

---

## Next Steps

### Immediate (Today)
1. ✅ Template audit complete
2. ⏳ Decision: Choose Option B (minimal template)
3. ⏳ Create `init-terraform-minimal.rsc.j2`
4. ⏳ Update generator to use new template

### Week 1
- [ ] Implement minimal template
- [ ] Test minimal template on lab device
- [ ] Document Terraform migrations needed
- [ ] Update ADR 0057 with findings

### Phase 2 (Week 3-6)
- [ ] Create Terraform resources for moved features
- [ ] Implement generator support
- [ ] Test complete workflow

---

## Audit Summary

✅ **Template audited:** 116 lines analyzed
⚠️ **Issues found:** 3 critical bugs
📊 **Classification complete:** Day-0 (40%), Day-1/2 (35%), Dead (25%)
✅ **Recommendation:** Option B - Create minimal template
✅ **Timeline impact:** +1 day to Phase 1 (acceptable)

---

**Status:** ✅ WORKSTREAM 1A COMPLETE
**Next:** Present findings to team, approve Option B
