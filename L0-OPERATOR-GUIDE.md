# L0 Operator Guide: Simple How-To

**For:** Everyone (no special knowledge needed)
**Time:** 5 minutes to understand L0

---

## What is L0?

L0 is the **configuration heart** of your topology.

Think of it like a car dashboard:
- **_index.yaml** = Main dashboard (version, environment, quick settings)
- **environments.yaml** = Different modes (eco, sport, off-road)
- **policies/** = Engine tuning (optional, don't touch unless expert)

---

## Start Here: _index.yaml

This is the **only file you need to understand** for 90% of tasks.

```yaml
# File: topology/L0-meta/_index.yaml

version: 4.0.0              # Topology version (rarely change)
environment: production     # <-- MOST IMPORTANT: prod, staging, or development

quick_settings:             # <-- MAIN SETTINGS (edit here!)
  primary_router: mikrotik-chateau
  primary_dns: 192.168.1.1
  security_level: baseline   # Options: baseline, strict, relaxed
  backup_enabled: true
  monitoring_enabled: true
  audit_logging: false
```

**That's it.** You understand L0.

---

## Common Tasks (How-To)

### Task 1: Switch Environment (prod → staging)

**Scenario:** You want to test topology in staging before production.

**What to do:**
1. Open: `topology/L0-meta/_index.yaml`
2. Find: `environment: production`
3. Change to: `environment: staging`
4. Regenerate: `python3 topology-tools/regenerate-all.py`

**Result:**
- All staging settings apply automatically
- Security uses baseline (not strict)
- Backups still enabled
- Audit logging disabled
- SLA target is 99% (not 99.9%)

---

### Task 2: Tighten Security in Production

**Scenario:** You want higher security standards.

**What to do:**
1. Open: `topology/L0-meta/_index.yaml`
2. Find: `security_level: baseline`
3. Change to: `security_level: strict`
4. Regenerate: `python3 topology-tools/regenerate-all.py`

**Result:**
- SSH password authentication disabled
- Longer password requirements
- Rate limiting enabled
- All audit logging turned on

---

### Task 3: Enable Audit Logging in Staging

**Scenario:** You want to track changes in staging.

**What to do:**
1. Open: `topology/L0-meta/environments.yaml`
2. Find the `staging:` section
3. Under `operations:`, find: `audit_logging: false`
4. Change to: `audit_logging: true`
5. Regenerate: `python3 topology-tools/regenerate-all.py`

**Result:** All changes in staging are logged.

---

### Task 4: Disable Backups in Development

**Scenario:** You don't need backups in development to save disk space.

**What to do:**
1. Open: `topology/L0-meta/environments.yaml`
2. Find the `development:` section
3. Under `operations:`, find: `backup_enabled: false`
4. (It's already disabled! No change needed)

**Result:** No backups in development.

---

### Task 5: Change Primary DNS Server

**Scenario:** You want to use 1.1.1.1 instead of 192.168.1.1

**What to do:**
1. Open: `topology/L0-meta/_index.yaml`
2. Find: `primary_dns: 192.168.1.1`
3. Change to: `primary_dns: 1.1.1.1`
4. Regenerate: `python3 topology-tools/regenerate-all.py`

**Result:** All devices use new DNS server.

---

## What Each Environment Means

### Production (production)
- **When:** Live infrastructure running real services
- **Security:** Strict (strongest)
- **Backups:** Yes, daily
- **Monitoring:** Detailed logs
- **SLA:** 99.9% uptime required
- **Changes:** One at a time, must be approved

### Staging (staging)
- **When:** Testing changes before production
- **Security:** Baseline (standard)
- **Backups:** Yes, weekly
- **Monitoring:** Basic logs
- **SLA:** 99% uptime OK
- **Changes:** Multiple changes at once OK

### Development (development)
- **When:** Local testing, experiments, learning
- **Security:** Relaxed (weakest)
- **Backups:** No (save disk space)
- **Monitoring:** None
- **SLA:** No requirement
- **Changes:** Anything goes, no approval needed

---

## Security Levels Explained

### Baseline
- **When:** Standard production use
- **SSH:** Key-based only
- **Passwords:** 16 characters, 90-day rotation
- **Firewall:** Drop by default
- **Use for:** Most production deployments

### Strict
- **When:** Sensitive data, compliance requirements
- **SSH:** Key-based only, non-standard port
- **Passwords:** 20 characters, 60-day rotation
- **Firewall:** Drop by default, geo-blocking
- **Use for:** Financial, medical, classified data

### Relaxed
- **When:** Development, testing, learning
- **SSH:** Password allowed
- **Passwords:** 8 characters, never expire
- **Firewall:** Accept by default
- **Use for:** Development environments only

---

## What You Should NEVER Edit

❌ **Don't edit this:**
- `policies/security.yaml` (unless you know what you're doing)
- Policy inheritance rules
- Regional policies

✅ **Only edit this:**
- `_index.yaml` (quick_settings section)
- `environments.yaml` (your environment settings)

---

## Quick Reference: Where to Find Things

| What I Want To Change | File | Location |
|----------------------|------|----------|
| Switch environment | `_index.yaml` | `environment: ` |
| Change DNS | `_index.yaml` | `primary_dns:` |
| Change router | `_index.yaml` | `primary_router:` |
| Change security | `_index.yaml` | `security_level:` |
| Enable/disable backup in staging | `environments.yaml` | `staging: → operations: → backup_enabled:` |
| Enable/disable monitoring | `environments.yaml` | `operations: → monitoring_enabled:` |
| Change SLA target | `environments.yaml` | `sla_target:` |
| Create custom policy | `policies/security.yaml` | (rare, don't do this) |

---

## After You Edit L0

**Always run this to apply changes:**

```bash
cd /path/to/home-lab
python3 topology-tools/regenerate-all.py
```

**Or specific generators:**
```bash
python3 topology-tools/generate-terraform-proxmox.py  # Update Terraform
python3 topology-tools/generate-ansible-inventory.py  # Update Ansible
python3 topology-tools/generate-docs.py               # Update docs
```

---

## Troubleshooting

### "I changed something but nothing happened"
- Did you regenerate? Run: `python3 topology-tools/regenerate-all.py`

### "I don't understand what a setting does"
- Read the comments in _index.yaml or environments.yaml
- They explain every setting

### "I want to customize something I don't see"
- Check `policies/security.yaml`
- Or ask your architect

### "I want to undo my changes"
- Use git: `git diff` (see what changed)
- Use git: `git checkout L0-meta/` (revert changes)

---

## One More Thing

**The simplest way to understand L0:**

1. Open `_index.yaml`
2. Read the version line
3. Look at quick_settings
4. That's L0! You understand it now.

**Everything else** is just optional customization.

---

**That's it. You're an L0 expert.** 🎉

No need to understand inheritance, policies, or complex structures.
Just edit the settings you need and regenerate.
