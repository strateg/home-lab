# Common Workflows

This guide contains common developer workflows extracted from adapter files for token efficiency.

## Compile and Generate

```bash
# Validate and compile topology
.venv/bin/python scripts/orchestration/lane.py validate-v5

# Run full compilation
.venv/bin/python topology-tools/compile-topology.py

# Parallel plugin execution (default)
.venv/bin/python topology-tools/compile-topology.py

# Sequential mode (troubleshooting only)
.venv/bin/python topology-tools/compile-topology.py --no-parallel-plugins
```

## Development Profile

During development, framework file changes invalidate `framework.lock.yaml` integrity hashes.

```bash
# Auto-regenerate with dev profile
.venv/bin/python topology-tools/compile-topology.py --profile dev

# Manual batch regeneration
task framework:lock-refresh-all
```

**Runtime profiles:**
- `production` (default) — strict validation
- `dev` — auto-regenerates framework.lock on integrity mismatch
- `modeled` — for model testing scenarios
- `test-real` — for integration tests with real data

## Lane Orchestrator

```bash
# Full validation
V5_SECRETS_MODE=passthrough .venv/bin/python scripts/orchestration/lane.py validate-v5

# Run specific phase
python scripts/orchestration/lane.py <phase-name>
```

## Deploy Bundle Workflow

```bash
# Build immutable deploy bundle
task bundle:create
task bundle:list

# Execute service-chain lanes
task deploy:service-chain-evidence-check-bundle -- BUNDLE=<bundle_id>
task deploy:service-chain-evidence-apply-bundle -- ALLOW_APPLY=YES BUNDLE=<bundle_id>
```

## Node Initialization

```bash
# Check init state
task deploy:init-status

# Plan node initialization
task deploy:init-node-plan -- BUNDLE=<bundle_id> NODE=<node_id>
```

## Run Tests

```bash
# All tests
python -m pytest tests -q

# Specific test module
python -m pytest tests/plugin_integration/ -v

# Full CI
task ci
```

## State File Locations

| Path | Purpose |
|------|---------|
| `.work/deploy/bundles/<id>/` | Immutable deploy bundles |
| `.work/deploy-state/<project>/nodes/` | Initialization state |
| `.work/deploy-state/<project>/logs/` | Audit logs (JSONL) |

## Add LXC Instance (ADR 0107)

New LXC instances inherit host-scoped defaults via `@on` directive:

```yaml
# projects/home-lab/topology/instances/lxc/srv-gamayun/lxc-myapp.yaml
@instance: lxc-myapp
@extends: obj.proxmox.lxc.debian12.base
@version: 1.0.0

host_ref: srv-gamayun           # Required for @on resolution
vmid: 210
hostname: myapp

# Instance-specific values (not inherited)
network:
  ip: 10.0.30.50/24
storage:
  rootfs:
    size_gb: 10
cloudinit:
  user: myapp
ansible:
  playbook: myapp.yml
```

**Inherited from host via @on** (defined in object template):
- `trust_zone_ref`, `network.vlan_ref`, `network.bridge_ref`, `network.gateway`
- `dns.nameserver`, `dns.searchdomain`
- `storage.rootfs.pool_ref`, `cloudinit.enabled`, `ansible.enabled`, `boot.onboot`

See `docs/ai/rules/host-placement.md` for full @on directive reference.

## Build The Patched RouterOS Provider (ADR 0120)

The released `terraform-routeros/routeros` provider **cannot update any
`routeros_ip_address`** on RouterOS >= 7.21: it sends the derived `vrf` field on
every PATCH and RouterOS answers `400 unknown parameter vrf`. Upstream issue
#944 is open, the fix (PR #984) is open and unreleased. Until it ships, this
workspace uses the pinned upstream release built with that patch.

```bash
scripts/terraform/build-patched-routeros-provider.sh          # clone, patch, build, publish
scripts/terraform/build-patched-routeros-provider.sh --verify # check an existing build

cd .work/native/home-lab/terraform/mikrotik
export TF_CLI_CONFIG_FILE="$PWD/../../../providers/terraform.rc"   # .work/providers/terraform.rc
terraform init -upgrade
```

`init` installs from the mirror only if the provider's entry is absent from
`.terraform.lock.hcl` and its cached plugin is gone - otherwise it keeps what it
has and nothing changes. The registry lock is preserved as
`.terraform.lock.hcl.registry-backup`.

Confirm the build is actually in use before trusting a plan:

```bash
terraform providers schema -json \
  | jq '.provider_schemas["registry.terraform.io/terraform-routeros/routeros"].resource_schemas.routeros_ip_address.block.attributes.vrf'
# patched build: { "computed": true, ... }   registry build: { "optional": true, ... }
```

**Going back** when upstream releases the fix: delete the patch and the script,
unset `TF_CLI_CONFIG_FILE`, remove the provider entry from the lock, and
`terraform init -upgrade`.

---

## Record A Hand-Made Device Change (ADR 0120 D7)

A deliberate tweak made directly on a device is legitimate. An *unmarked* one is
indistinguishable from garbage, and the next reconciliation will treat it as
such. Two steps, both required:

1. **Mark it on the device.** The comment begins with `manual:` and carries an
   owner and a date:

   ```
   /ip firewall filter set 0 comment="manual: AWG proxy test egress owner=platform-owner since=2026-10-21 ref=docs/reports/2026-10-21-chateau-dead-rules.md"
   ```

   `owner=` and `since=` are required; `ref=` is optional and strongly
   preferred. The canonical form lives in
   `configs/quality/device-provenance-policy.yaml`.

2. **Register it in the repository** (manual-exception registry, ADR 0120
   option C — not implemented yet). Until it exists, add the object to the
   triage table in `docs/reports/2026-10-21-chateau-dead-rules.md` so it is not
   lost.

The intended end state of every manual entry is its removal: either topology
learns to render it, or it leaves the device. A marker is a staging label with a
clock, not a permanent exemption.

**Never** put `manual:` in a template or generator. A rendered object claiming
to be hand-made would be spared by the reconciliation that owns it; the
validation refuses it as `E8402`.

To check what the rendered roots claim:

```bash
.venv/bin/python scripts/validation/validate_device_provenance.py --mode enforce
```

It runs in the `validate-v5` lane; `DEVICE_PROVENANCE_MODE=warn` relaxes it for
a local experiment.

---

## References

- `docs/guides/DEPLOY-BUNDLE-WORKFLOW.md`
- `docs/guides/NODE-INITIALIZATION.md`
- `docs/guides/OPERATOR-ENVIRONMENT-SETUP.md`
- `docs/ai/rules/host-placement.md` (ADR 0107)
