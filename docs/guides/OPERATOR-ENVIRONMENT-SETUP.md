# Operator Environment Setup (ADR0084/ADR0083)

## Purpose

Deploy-domain commands (`service_chain_evidence.py`, `init-node.py`) require a Linux-backed execution plane.
This guide defines the supported operator setups and quick verification steps.

---

## Supported Modes

| Host OS | Recommended runner | Notes |
|---------|--------------------|-------|
| Windows 11 | `wsl` | Canonical mode for local operators |
| Linux | `native` | Canonical mode for CI/control nodes |
| macOS | `docker` or `remote` | No native Linux deploy plane |

---

## Windows: WSL Setup

1. Install WSL (PowerShell as Administrator):

```powershell
wsl --install -d Ubuntu
```

2. Reboot if requested, then initialize Ubuntu user.

3. Install required tools inside WSL:

```bash
sudo apt update
sudo apt install -y bash git rsync ansible opentofu
```

4. Verify WSL distro availability from Windows:

```powershell
wsl -l -q
```

5. Run repo commands with WSL-backed runner:

```powershell
task deploy:service-chain-evidence-apply-bundle -- BUNDLE=<bundle_id> DEPLOY_RUNNER=wsl
task deploy:init-node-plan -- BUNDLE=<bundle_id> NODE=<node_id> DEPLOY_RUNNER=wsl
```

---

## Linux: Native Setup

Install required tools in host environment:

```bash
sudo apt update
sudo apt install -y bash git rsync ansible opentofu
```

Run with `DEPLOY_RUNNER=native` (or omit runner to auto-detect native on Linux).

---

## macOS / Non-Linux Hosts

Use one of:

- `DEPLOY_RUNNER=docker` with a prepared toolchain image
- `DEPLOY_RUNNER=remote` with configured SSH control node

Remote mode details: `docs/guides/REMOTE-RUNNER-SETUP.md`.

---

## Quick Validation

1. Service-chain dry run:

```powershell
task deploy:service-chain-evidence-dry-bundle -- BUNDLE=<bundle_id> DEPLOY_RUNNER=<runner>
```

2. Init-node plan-only run:

```powershell
task deploy:init-node-plan -- BUNDLE=<bundle_id> NODE=<node_id> DEPLOY_RUNNER=<runner>
```

If environment precheck fails, `init-node.py` returns:

- exit code `2`
- JSON status `environment-error`
- `issues` with remediation hints.
