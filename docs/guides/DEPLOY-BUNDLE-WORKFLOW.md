# Deploy Bundle Workflow

**Status:** Active
**Updated:** 2026-03-31
**Scope:** ADR 0085/0084 bundle-first deploy execution

---

## 1. Goal

Deploy execution must consume an explicit immutable bundle, not raw `generated/...` paths.

Canonical bundle location:

`\.work/deploy/bundles/<bundle_id>/`

---

## 2. Deploy Profile

Project deploy profile path:

`projects/home-lab/deploy/deploy-profile.yaml`

Core fields used by this workflow:

- `default_runner` (`native|wsl|docker|remote`)
- `timeouts.*` for deploy-domain command timeouts
- `bundle.retention_count` and `bundle.auto_cleanup`

Schema:

`schemas/deploy-profile.schema.json`

---

## 3. Create Bundle

Create bundle from current project generated artifacts:

```powershell
task framework:deploy-bundle-create
```

Create bundle with decrypted secrets included:

```powershell
task framework:deploy-bundle-create -- INJECT_SECRETS=1
```

Optional overrides:

- `GENERATED_ROOT=<path>`
- `SECRETS_ROOT=<path>`
- `BUNDLES_ROOT=<path>`

---

## 4. Inspect and List

List available bundles:

```powershell
task framework:deploy-bundle-list
```

Inspect one bundle:

```powershell
task framework:deploy-bundle-inspect -- BUNDLE=<bundle_id>
```

Inspect without checksum verification:

```powershell
task framework:deploy-bundle-inspect -- BUNDLE=<bundle_id> SKIP_CHECKSUMS=1
```

---

## 5. Execute Evidence Lanes from Bundle

Dry lane:

```powershell
task framework:service-chain-evidence-dry-bundle -- BUNDLE=<bundle_id>
```

Maintenance-check lane:

```powershell
task framework:service-chain-evidence-check-bundle -- BUNDLE=<bundle_id> CONTINUE_ON_FAILURE=1 ANSIBLE_VIA_WSL=1
```

Maintenance-apply lane:

```powershell
task framework:service-chain-evidence-apply-bundle -- ALLOW_APPLY=YES BUNDLE=<bundle_id> CONTINUE_ON_FAILURE=1 ANSIBLE_VIA_WSL=1
```

Notes:

- bundle id/path is passed via `--bundle` to `record-service-chain-evidence.py`
- runtime checks fail fast when bundle is missing
- checksum verification runs before runner staging

---

## 6. Runner Selection by Host

- **Windows operators:** use WSL-backed deploy execution (`ANSIBLE_VIA_WSL=1` or `DEPLOY_RUNNER=wsl`).
- **Linux operators:** native runner is the default deploy path (`DEPLOY_RUNNER=native` optional).
- **Remote control-node:** set `DEPLOY_RUNNER=remote` and configure remote profile (see `docs/guides/REMOTE-RUNNER-SETUP.md`).
- **Profile-driven default:** if `DEPLOY_RUNNER` is not set, `get_runner()` falls back to project deploy profile.

---

## 7. Delete Bundle

```powershell
task framework:deploy-bundle-delete -- BUNDLE=<bundle_id>
```

---

## 8. Operator Sequence (Recommended)

```powershell
task validate:v5-passthrough
task framework:deploy-bundle-create
task framework:deploy-bundle-list
task framework:service-chain-evidence-check-bundle -- BUNDLE=<bundle_id> CONTINUE_ON_FAILURE=1 ANSIBLE_VIA_WSL=1
```

For maintenance apply window:

```powershell
task framework:service-chain-evidence-apply-bundle -- ALLOW_APPLY=YES BUNDLE=<bundle_id> CONTINUE_ON_FAILURE=1 ANSIBLE_VIA_WSL=1
```
