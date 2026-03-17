# ADR 0072: Unified Secrets Management with SOPS and age

**Date:** 2026-03-17
**Status:** Accepted (rollout in progress)
**Supersedes:** ADR 0051 (secret storage sections), ADR 0054 (secret-bearing local inputs)

---

## Context

The repository currently uses multiple inconsistent mechanisms for secret storage:

| Mechanism | Location | Use Case | Problems |
|-----------|----------|----------|----------|
| Ansible Vault | `ansible/group_vars/*/vault.yml` | Ansible secrets | Separate workflow and key material |
| local/ directory | `local/terraform/*.tfvars` | Terraform credentials | Not versioned, not portable |
| .gitignore patterns | Various | Ad-hoc secret exclusion | No encryption, data-loss risk |
| Placeholder values | `v5/topology/instances/` | Hardware identities | Blocks production deployment |

This creates operational problems:

1. No single source of truth for secret management.
2. Key management fragmentation across tools.
3. Hardware identities cannot be committed in plaintext.
4. Local-only secret files are not portable.

### Cross-Platform Gap

The current secret workflow examples are mostly POSIX shell (`bash`, `/tmp`, `grep`, `shred`, `chmod`).
That is not sufficient for operators on Windows PowerShell.

Cross-platform operation is required for this repository:

- Linux/macOS (POSIX shell)
- Windows (PowerShell)
- CI runners (GitHub Actions Ubuntu)

---

## Decision

### 1. Adopt SOPS + age as the single secret management solution

All secrets in the repository are stored as SOPS-encrypted YAML and encrypted with age recipients.

### 2. Standardize on repository-tracked encrypted keys (dev + recovery)

We use a two-key model:

- `devkey.age`: daily operations (regular unlock)
- `masterkey.age`: recovery-only key

Both files are tracked in git **encrypted with passphrase**.
Passphrases are never stored in git.

### 3. Enforce cross-platform secret workflows

Secret operations must be runnable on Linux/macOS and Windows.

Normative rule:

- Required operator workflows must provide either:
  - dual wrappers (`.sh` and `.ps1`), or
  - one Python CLI entrypoint.

Bash-only commands in this ADR are illustrative unless an equivalent PowerShell path is defined.

### 4. Integrate secrets directly into `topology-tools`

Hardware secrets are resolved during compile in plugin-first pipeline.
The integration point is `InstanceRowsCompiler`, which resolves decrypted secret values before final row normalization.

### 5. Side-car encrypted files with placeholder merge

Policy:

- Instance files in `v5/topology/instances/` contain human-readable placeholders (`<TODO_*>`) for secret fields.
- Encrypted secret values are stored in side-car files under `secrets/instances/{instance_id}.yaml`.
- Compiler merges decrypted side-car values into instance rows, replacing placeholders only.
- Non-placeholder fields in instance files are preserved unchanged.
- No additional indirection fields (`hardware_identity_secret_ref`) required.

---

## Repository Secret Structure

```text
secrets/
├── .sops.yaml
├── devkey.age
├── devkey.pub
├── masterkey.age
├── masterkey.pub
├── instances/                    # Instance-level secrets (side-car files)
│   ├── rtr-mikrotik-chateau.yaml
│   ├── rtr-slate.yaml
│   ├── srv-gamayun.yaml
│   └── srv-orangepi5.yaml
├── terraform/                    # Terraform credentials
│   ├── proxmox.yaml
│   └── mikrotik.yaml
├── ansible/                      # Ansible playbook secrets
│   └── vault.yaml
└── bootstrap/                    # Bootstrap secrets
```

Each file in `secrets/instances/` corresponds to an instance in `v5/topology/instances/` by matching `instance` ID.

### SOPS configuration

```yaml
# secrets/.sops.yaml
creation_rules:
  - path_regex: \.yaml$
    age: >-
      age1xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx,
      age1yyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyy
```

`age[0]` is dev recipient, `age[1]` is recovery recipient.

---

## Key Management Workflow

### 1) Key generation

Canonical repository key files:

- `secrets/devkey.age`, `secrets/devkey.pub`
- `secrets/masterkey.age`, `secrets/masterkey.pub`

### 2) Unlock for active session

Use `SOPS_AGE_KEY_FILE` explicitly to avoid OS-specific path ambiguity.

Recommended defaults:

| Platform | Default key file |
|----------|------------------|
| Linux/macOS | `$HOME/.config/sops/age/keys.txt` |
| Windows | `$env:APPDATA\sops\age\keys.txt` |

### 3) Lock after use

Delete the plaintext temporary key file on session end.

Security note:

- Do not rely on `shred` as a universal guarantee (filesystem/SSD dependent).
- Primary control is minimizing plaintext lifetime and location.

### 4) Rotation

Key rotation must re-encrypt all files in `secrets/{instances,terraform,ansible,bootstrap}`, then update `secrets/.sops.yaml`.

---

## `topology-tools` Integration

### Plugin registration

Secret resolution is configured on `base.compiler.instance_rows`.

```yaml
# v5/topology-tools/plugins/plugins.yaml
- id: base.compiler.instance_rows
  kind: compiler
  entry: compilers/instance_rows_compiler.py:InstanceRowsCompiler
  api_version: "1.x"
  stages: [compile]
  order: 40
  depends_on: []
  config:
    secrets_mode: passthrough  # inject | passthrough | strict
    secrets_root: secrets      # relative to repo root
    require_unlock: true
```

### Runtime behavior

- `inject`: find side-car file in `secrets/instances/`, decrypt, and merge values into instance row replacing placeholders.
- `passthrough`: skip side-car lookup, keep placeholders as-is in compiled output.
- `strict`: same as `inject`, but fail compile if any placeholder remains unresolved after merge.

In `inject`/`strict` modes, `ctx.compiled_json` MUST contain decrypted values merged from side-car files (no `<TODO_*>` placeholders for resolved secret paths).

### CLI contract

`compile-topology.py` must expose:

- `--secrets-mode inject|passthrough|strict`
- `--secrets-root <path>` (optional, defaults to `secrets`)

These values are passed into plugin context config and consumed by `base.compiler.instance_rows`.

### Side-car encrypted files

Secret values are stored in separate side-car files under `secrets/instances/`.
Each side-car file contains only the secret fields that should be merged into the corresponding instance.

**Instance file** (human-readable, tracked):
```yaml
# v5/topology/instances/l1_devices/rtr-mikrotik-chateau.yaml
schema_version: 1
instance: rtr-mikrotik-chateau
group: l1_devices
layer: L1
object_ref: obj.mikrotik.chateau_lte7_ax
hardware_identity:
  serial_number: <TODO_SERIAL_NUMBER>       # placeholder
  mac_addresses:
    ether1: "02:AA:20:00:00:01"             # non-secret, kept as-is
    ether2: <TODO_MAC_ETHER2>               # placeholder
```

**Side-car file** (encrypted, tracked):
```yaml
# secrets/instances/rtr-mikrotik-chateau.yaml (SOPS-encrypted)
instance: rtr-mikrotik-chateau
hardware_identity:
  serial_number: ENC[AES256_GCM,data:...,iv:...,tag:...]
  mac_addresses:
    ether2: ENC[AES256_GCM,data:...,iv:...,tag:...]
sops:
  age: [...]
  lastmodified: "2026-03-17T..."
  mac: ENC[...]
  version: 3.12.1
```

**After merge** (`--secrets-mode inject`):
```yaml
hardware_identity:
  serial_number: "REAL-SERIAL-123"          # decrypted from side-car
  mac_addresses:
    ether1: "02:AA:20:00:00:01"             # preserved from instance
    ether2: "AA:BB:CC:DD:EE:02"             # decrypted from side-car
```

### Merge algorithm

1. For each instance row, look for `secrets/instances/{instance_id}.yaml`.
2. If side-car exists, decrypt it with `sops -d`.
3. Deep-walk instance row: for each field with `<TODO_*>` placeholder, replace with corresponding value from decrypted side-car.
4. Fields without placeholders are never modified.
5. In `strict` mode, emit error if any `<TODO_*>` placeholder remains after merge.

---

## Ansible and Terraform Integration

### Ansible

Replace Ansible Vault payloads with SOPS-encrypted `secrets/ansible/vault.yaml`.
Playbooks must use SOPS decryption path (CLI or SOPS-aware plugin) and must not require `.vault_pass`.

### Terraform

Generate runtime `terraform.tfvars` from SOPS at apply time.

Target output path:

- `.work/native/terraform/<target>/terraform.tfvars`

Generated tfvars are ephemeral artifacts and must be removed after apply.

---

## CI/CD Integration

Canonical CI secret name:

- `DEVKEY_PASSPHRASE`

Canonical encrypted key file for routine CI jobs:

- `secrets/devkey.age`

GitHub Actions unlock step:

```yaml
env:
  DEVKEY_PASSPHRASE: ${{ secrets.DEVKEY_PASSPHRASE }}

steps:
  - name: Unlock secrets
    run: |
      mkdir -p ~/.config/sops/age
      echo "$DEVKEY_PASSPHRASE" | age -d secrets/devkey.age > ~/.config/sops/age/keys.txt
      chmod 600 ~/.config/sops/age/keys.txt
```

Recovery key (`masterkey.age`) is excluded from routine CI usage.

---

## Consequences

### Positive

1. Single secret system across Ansible/Terraform/topology compile.
2. Encrypted secrets become versioned and portable.
3. Hardware identity placeholders can be removed safely.
4. CI configuration uses one routine passphrase secret.

### Negative

1. Operators must install `sops` and `age`.
2. Existing Vault/local workflows need migration.
3. Passphrase hygiene remains a critical operational dependency.
4. Cross-platform wrappers/tooling must be maintained.

### Risks and mitigations

| Risk | Mitigation |
|------|------------|
| Passphrase loss | Keep recovery procedure and offline backup policy |
| Passphrase compromise | Rotate recipients and re-encrypt immediately |
| Plaintext key left on disk | Lock workflow + explicit `SOPS_AGE_KEY_FILE` + short session lifetime |
| Shell drift (`bash` vs `pwsh`) | Require dual wrappers or Python entrypoint for required ops |
| Unresolved placeholders at deploy time | `--secrets-mode strict` for deploy pipelines |

---

## Migration Plan

### Phase 0: Tooling and cross-platform baseline

- [ ] Ensure `sops` + `age` install instructions for Linux/macOS/Windows.
- [ ] Standardize on `devkey.age` and `masterkey.age` naming in docs/scripts.
- [ ] Provide required unlock/lock workflows for both `sh` and `pwsh` (or Python CLI).
- [ ] Add pre-commit validation to block plaintext secrets.

### Phase 1: Side-car secrets + compiler integration

- [x] Create `secrets/instances/` directory for instance-level side-car secrets.
- [x] Implement side-car lookup and placeholder merge in `base.compiler.instance_rows`.
- [x] Add `--secrets-mode` and `--secrets-root` to `compile-topology.py`.
- [x] Migrate existing `secrets/hardware/*.yaml` to `secrets/instances/*.yaml`.
- [x] Keep placeholders (`<TODO_*>`) in instance files for unresolved secrets.
- [x] Remove `hardware_identity_secret_ref` field usage.

### Phase 2: Terraform secrets

- [ ] Migrate secret-bearing `local/terraform/*.tfvars` data to `secrets/terraform/*.yaml`.
- [ ] Keep `local/` only for non-secret operator preferences.

### Phase 3: Ansible secrets

- [ ] Convert Ansible Vault payloads to `secrets/ansible/vault.yaml`.
- [ ] Remove `.vault_pass` runtime dependency.

### Phase 4: Cleanup and ADR alignment

- [ ] Update ADR 0051 status to superseded by ADR 0072.
- [ ] Update ADR 0054 clarifying `local/` is non-secret.
- [ ] Align helper scripts, docs, and CI examples with this ADR naming.

---

## Validation Criteria

1. `sops -d secrets/instances/{instance_id}.yaml` works on Linux/macOS and Windows when unlocked.
2. `compile-topology.py --secrets-mode inject` merges decrypted side-car values, replacing `<TODO_*>` placeholders.
3. `compile-topology.py --secrets-mode passthrough` works without unlocking secrets; placeholders remain in output.
4. `compile-topology.py --secrets-mode strict` fails if any `<TODO_*>` placeholder remains unresolved.
5. `ctx.compiled_json` in inject/strict modes contains decrypted merged instance fields (no placeholder values for resolved secret paths).
6. Non-placeholder fields in instance files are never modified by side-car merge.
7. Terraform apply path consumes SOPS-derived tfvars and cleans ephemeral file.
8. Ansible runs without `.vault_pass`.
9. Pre-commit hook blocks plaintext secret artifacts in `secrets/`.
10. CI decrypts routine secrets via `DEVKEY_PASSPHRASE` and `secrets/devkey.age`.

---

## References

- [SOPS documentation](https://github.com/getsops/sops)
- [age encryption](https://github.com/FiloSottile/age)
- ADR 0051: Ansible Runtime, Inventory, and Secret Boundaries
- ADR 0054: Local Inputs Directory
- ADR 0068: Object YAML Template with Typed Placeholders
