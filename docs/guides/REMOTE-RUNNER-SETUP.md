# Remote Runner Setup

**Status:** Active
**Updated:** 2026-03-31
**Scope:** ADR 0084 remote deploy runner (`RemoteLinuxRunner`)

---

## 1. Goal

Run deploy-plane commands from a dedicated Linux control node over SSH while keeping bundle-first execution.

`RemoteLinuxRunner` uses:
- SSH for command execution
- `rsync` (default) or `scp` for bundle staging

---

## 2. Deploy Profile

Set remote runner in `projects/home-lab/deploy/deploy-profile.yaml`:

```yaml
default_runner: remote
runners:
  remote:
    host: control.example.com
    user: deploy
    sync_method: rsync # rsync | scp
```

---

## 3. Control Node Prerequisites

- Linux host reachable by SSH from operator machine
- SSH key-based auth configured for the deploy user
- Tools on control node: `terraform`, `ansible-playbook`, `bash`
- Local tools on operator machine:
  - `ssh` (required)
  - `rsync` for `sync_method: rsync` or `scp` for `sync_method: scp`

Quick checks:

```bash
ssh deploy@control.example.com true
rsync --version   # if using rsync mode
scp -V            # if using scp mode
```

---

## 4. Bundle-Based Execution

```powershell
task bundle:create
task deploy:service-chain-evidence-check-bundle -- BUNDLE=<bundle_id> DEPLOY_RUNNER=remote
```

For apply lane:

```powershell
task deploy:service-chain-evidence-apply-bundle -- ALLOW_APPLY=YES BUNDLE=<bundle_id> DEPLOY_RUNNER=remote CONTINUE_ON_FAILURE=1
```

---

## 5. Runtime Notes

- Remote workspace root defaults to `/tmp/home-lab-deploy/<bundle_id>`.
- Bundle is uploaded before execution and cleaned after run by default.
- Use per-run bundle IDs for deterministic and auditable execution.
