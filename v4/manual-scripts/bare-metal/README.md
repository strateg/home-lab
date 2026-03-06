# Proxmox Bootstrap Source Assets

This directory is no longer the canonical operator-facing Proxmox bootstrap workflow.

Current model:
- generate the operator package with `python topology-tools/generate-proxmox-bootstrap.py`
- use `generated/bootstrap/srv-gamayun/` as the canonical bootstrap package root

This directory remains only as a source-asset layer for generated Proxmox bootstrap packages:
- `create-uefi-autoinstall-proxmox-usb.sh`
- `post-install/`

Legacy operator-facing docs, wrappers, diagnostics, and tracked `answer.toml` material were moved to:
- `Migrated_and_archived/archive/proxmox-bare-metal-legacy/`

If you want the active workflow, start from:
- `generated/bootstrap/srv-gamayun/README.md`
- `docs/guides/PROXMOX-USB-AUTOINSTALL.md`
