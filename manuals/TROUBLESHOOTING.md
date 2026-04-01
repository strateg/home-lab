# Deploy Plane Troubleshooting Guide

Error codes, diagnostics, and solutions.

---

## Error Code Reference

### Environment Errors (E9700-E9709)

| Code | Message | Cause | Resolution |
|------|---------|-------|------------|
| `E9700` | Deploy environment check failed | Runner not available or missing tools | Install required tools in runner environment |
| `E9701` | Runner initialization failed | Invalid runner config or unavailable | Check deploy-profile.yaml or runner availability |
| `E9702` | Runner bundle staging failed | Cannot stage bundle in runner | Verify bundle path and runner permissions |
| `E9703` | Runner workspace cleanup failed | Cleanup error (warning only) | Manual cleanup may be required |

### Bundle Errors (E9710-E9719)

| Code | Message | Cause | Resolution |
|------|---------|-------|------------|
| `E9710` | Bundle not found | Bundle ID/path doesn't exist | Run `task framework:deploy-bundle-list` |
| `E9711` | Bundle checksum mismatch | Bundle integrity compromised | Delete and recreate bundle |
| `E9712` | Bundle already exists | Duplicate bundle creation | Use existing bundle or wait for hash change |
| `E9713` | Bundle manifest validation failed | Invalid manifest structure | Regenerate bundle from valid artifacts |

### Reset/State Errors (E9720-E9729)

| Code | Message | Cause | Resolution |
|------|---------|-------|------------|
| `E9720` | Reset requires confirm flag | Missing `--confirm-reset` | Add `CONFIRM_RESET=true` to command |
| `E9721` | Illegal state transition | Invalid state machine transition | Check current state with `--status` |

### Adapter Errors (E9730-E9749)

| Code | Message | Cause | Resolution |
|------|---------|-------|------------|
| `E9730` | Adapter execution not implemented | Scaffold-only adapter | Adapter requires implementation |
| `E9731` | State transition error | Transition not allowed | Reset node or check state machine |
| `E9732` | Unknown mechanism | Unsupported initialization mechanism | Check node initialization contract |
| `E9733` | Preflight checks failed | Missing artifacts or prerequisites | Run bundle inspect, check artifacts |
| `E9734` | Node state row missing | Node not in state file | Ensure node is in bundle manifest |
| `E9735` | Node status not executable | Status requires reset | Use `--reset --confirm-reset` |
| `E9736` | Empty handover checks | Adapter has no handover checks | Adapter implementation issue |
| `E9737` | Invalid status for verify | Node not in initialized/verified state | Initialize node first |
| `E9738` | Handover checks failed | Post-bootstrap verification failed | Check node connectivity and state |
| `E9739` | Node not in bundle | Node ID not in bundle manifest | Verify node ID or recreate bundle |

### Netinstall Adapter Errors (E9740-E9749)

| Code | Message | Cause | Resolution |
|------|---------|-------|------------|
| `E9740` | No netinstall script | Missing .rsc bootstrap script | Check generated/bootstrap/<node>/*.rsc |
| `E9741` | Artifacts missing in bundle | Bootstrap files not in bundle | Regenerate bundle after build |

---

## Common Issues

### WSL Runner Issues

#### WSL not found

```
Runner 'wsl' is not available on this system.
```

**Solution:**
```powershell
# Install WSL
wsl --install -d Ubuntu

# Verify
wsl -l -q
```

#### Wrong distro

```
WSL distro 'Ubuntu' not found
```

**Solution:**
```bash
# Check available distros
wsl -l -q

# Update deploy-profile.yaml
runners:
  wsl:
    distro: Ubuntu-22.04  # Use actual distro name
```

### Docker Runner Issues

#### Docker not running

```
Runner 'docker' is not available on this system.
```

**Solution:**
```bash
# Check Docker daemon
docker info

# Start Docker
sudo systemctl start docker  # Linux
# Or start Docker Desktop on Windows/Mac
```

#### Toolchain image not found

```
Unable to find image 'homelab-toolchain:latest'
```

**Solution:**
```bash
# Build the toolchain image
task framework:deploy-docker-toolchain-build

# Verify
docker images | grep homelab-toolchain
```

### Remote Runner Issues

#### SSH connection failed

```
Runner 'remote' is not available on this system.
```

**Solution:**
```bash
# Test SSH connection
ssh deploy@control.example.com true

# Check SSH key
ssh-add -l

# Update deploy-profile.yaml with correct host
runners:
  remote:
    host: actual-host.example.com
    user: deploy
```

#### Rsync not available

```
Remote runner sync_method=rsync requires rsync in PATH
```

**Solution:**
```bash
# Install rsync on local machine
sudo apt install rsync  # Debian/Ubuntu
brew install rsync      # macOS

# Or switch to scp
runners:
  remote:
    sync_method: scp
```

### Bundle Issues

#### Bundle already exists

```json
{
  "error": "Bundle already exists and is immutable"
}
```

**Cause:** Bundle with same content hash exists.

**Solution:**
```bash
# Use existing bundle
task framework:deploy-bundle-list

# Or delete old bundle first
task framework:deploy-bundle-delete -- BUNDLE=b-existing
```

#### Checksum verification failed

```json
{
  "checksums_ok": false,
  "checksum_mismatches": ["mismatch:artifacts/generated/terraform/main.tf"]
}
```

**Cause:** Bundle was modified after creation.

**Solution:**
```bash
# Delete corrupted bundle
task framework:deploy-bundle-delete -- BUNDLE=b-corrupted

# Recreate
task framework:deploy-bundle-create
```

### State Machine Issues

#### Illegal state transition

```
Illegal state transition: verified -> initialized
```

**Cause:** Attempted invalid state change.

**Solution:**
```bash
# Check current state
task framework:deploy-init-status

# Reset if needed
task framework:deploy-init-node-run -- \
  BUNDLE=b-123 NODE=node1 RESET=true CONFIRM_RESET=true
```

#### Node stuck in bootstrapping

```json
{
  "status": "bootstrapping",
  "last_error": "Adapter execution failed"
}
```

**Solution:**
```bash
# Force re-execution
task framework:deploy-init-node-run -- \
  BUNDLE=b-123 NODE=node1 FORCE=true

# Or reset and retry
task framework:deploy-init-node-run -- \
  BUNDLE=b-123 NODE=node1 RESET=true CONFIRM_RESET=true
```

### Preflight Check Failures

#### Artifacts not present

```json
{
  "preflight_checks": [
    {"name": "artifacts_present", "ok": false, "details": "artifacts=0"}
  ]
}
```

**Cause:** No bootstrap artifacts for node in bundle.

**Solution:**
```bash
# Check bundle contents
task framework:deploy-bundle-inspect -- BUNDLE=b-123 | jq '.manifest.nodes'

# Verify generated artifacts exist
ls generated/home-lab/bootstrap/<node_id>/

# Rebuild if missing
task build:default
task framework:deploy-bundle-create
```

#### Script not present

```json
{
  "preflight_checks": [
    {"name": "netinstall_script_present", "ok": false, "details": "scripts=0"}
  ]
}
```

**Cause:** Missing .rsc script for MikroTik node.

**Solution:**
```bash
# Check for .rsc files
ls generated/home-lab/bootstrap/rtr-*/

# Regenerate bootstrap artifacts
task build:default
```

---

## Diagnostic Commands

### Check Environment

```bash
# Full environment report
python -c "
from scripts.orchestration.deploy.environment import check_deploy_environment
from pathlib import Path
report = check_deploy_environment(
    repo_root=Path('.'),
    project_id='home-lab',
    required_tools=['bash', 'terraform', 'ansible']
)
print(f'Ready: {report.ready}')
print(f'Platform: {report.platform}')
print(f'Runner: {report.runner}')
print(f'Issues: {report.issues}')
print(f'Tools: {report.tools}')
"
```

### Check Bundle Integrity

```bash
# Full bundle verification
task framework:deploy-bundle-inspect -- BUNDLE=b-123

# List all checksums
cat .work/deploy/bundles/b-123/checksums.sha256
```

### Check Node State

```bash
# State summary
task framework:deploy-init-status

# Raw state file
cat .work/deploy-state/home-lab/nodes/INITIALIZATION-STATE.yaml
```

### Check Audit Logs

```bash
# Recent logs
tail -20 .work/deploy-state/home-lab/logs/*.jsonl

# Filter by node
grep '"node":"rtr-mikrotik-chateau"' .work/deploy-state/home-lab/logs/*.jsonl

# Filter by event
grep '"event":"node-execute-failed"' .work/deploy-state/home-lab/logs/*.jsonl
```

### Test Runner Availability

```bash
# Native runner
python -c "
from scripts.orchestration.deploy.runner import NativeRunner
r = NativeRunner()
print(f'Available: {r.is_available()}')
print(f'Bash: {r.check_tool(\"bash\")}')
"

# WSL runner
python -c "
from scripts.orchestration.deploy.runner import WSLRunner
r = WSLRunner()
print(f'Available: {r.is_available()}')
print(f'Distros: {r.get_available_distros()}')
"

# Docker runner
python -c "
from scripts.orchestration.deploy.runner import DockerRunner
r = DockerRunner()
print(f'Available: {r.is_available()}')
"
```

---

## Recovery Procedures

### Full State Reset

```bash
# 1. Delete state file (CAUTION: loses all history)
rm .work/deploy-state/home-lab/nodes/INITIALIZATION-STATE.yaml

# 2. Delete bundles
rm -rf .work/deploy/bundles/*

# 3. Regenerate
task build:default
task framework:deploy-bundle-create

# 4. Check status (should show all pending)
task framework:deploy-init-status
```

### Single Node Recovery

```bash
# 1. Reset node state
task framework:deploy-init-node-run -- \
  BUNDLE=b-123 \
  NODE=problem-node \
  RESET=true \
  CONFIRM_RESET=true

# 2. Re-run initialization
task framework:deploy-init-node-run -- \
  BUNDLE=b-123 \
  NODE=problem-node
```

### Import Existing Infrastructure

```bash
# Mark node as already bootstrapped externally
task framework:deploy-init-node-run -- \
  BUNDLE=b-123 \
  NODE=existing-node \
  IMPORT_EXISTING=true
```

---

## Log Analysis

### JSON Log Parsing with jq

```bash
# All errors
cat .work/deploy-state/home-lab/logs/*.jsonl | \
  jq -r 'select(.level == "error") | "\(.timestamp) \(.event): \(.message)"'

# Failures by node
cat .work/deploy-state/home-lab/logs/*.jsonl | \
  jq -r 'select(.status == "failed") | "\(.node): \(.error_code) - \(.message)"'

# Timeline for specific node
cat .work/deploy-state/home-lab/logs/*.jsonl | \
  jq -r 'select(.node == "rtr-mikrotik-chateau") | "\(.timestamp) \(.event)"'
```

### State History Analysis

```bash
# Node history
cat .work/deploy-state/home-lab/nodes/INITIALIZATION-STATE.yaml | \
  yq '.nodes[] | select(.id == "rtr-mikrotik-chateau") | .history'
```

---

## Contact and Support

- **ADR Documentation**: `adr/0083-*.md`, `adr/0084-*.md`, `adr/0085-*.md`
- **Guides**: `docs/guides/DEPLOY-BUNDLE-WORKFLOW.md`
- **Issues**: GitHub repository issues
