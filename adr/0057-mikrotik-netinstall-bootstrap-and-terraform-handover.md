# ADR 0057: MikroTik Chateau Netinstall Bootstrap and Terraform Handover

**Date:** 2026-03-05
**Status:** Accepted
**Related:** ADR 0049 (MikroTik Bootstrap Automation), ADR 0054 (Local Inputs Directory), ADR 0055 (Manual Terraform Extension Layer), ADR 0056 (Native Execution Workspace)

---

## Context

### Problem

MikroTik Chateau requires a day-0 bootstrap before the normal RouterOS automation flow can begin.

The repository already has a working Terraform-first RouterOS model:

- Terraform is the primary desired-state mechanism for MikroTik configuration
- generated bootstrap assets already prepare a Terraform handover
- operator documentation currently assumes manual import of `generated/bootstrap/rtr-mikrotik-chateau/init-terraform.rsc`

That current baseline is useful, but it is not a complete day-0 contract for reset or replacement hardware:

- it assumes the device is already reachable in a known running state
- it depends on manual WinBox or SSH-driven import behavior
- it does not target the intended device as explicitly as a MAC-bound reinstall path
- it does not provide a deterministic reinstall-from-known-baseline workflow

The project needs a more rigorous target contract for day-0 without changing the established post-bootstrap Terraform ownership.

### Current State

Current repository behavior is:

- `topology-tools/templates/bootstrap/mikrotik/init-terraform-minimal.rsc.j2` renders the canonical day-0 handover script
- compatibility templates exist for backup and export-assisted recovery:
  - `topology-tools/templates/bootstrap/mikrotik/backup-restore-overrides.rsc.j2`
  - `topology-tools/templates/bootstrap/mikrotik/exported-config-safe.rsc.j2`
- `generated/bootstrap/rtr-mikrotik-chateau/init-terraform.rsc` is the generated bootstrap artifact
- `generated/bootstrap/rtr-mikrotik-chateau/terraform.tfvars.example` and `generated/terraform/mikrotik/terraform.tfvars.example` support the post-bootstrap Terraform phase
- `deploy/phases/00-bootstrap.sh` and `make bootstrap-info` present Netinstall as default with fallback paths
- `topology-tools/scripts/deployers/mikrotik_bootstrap.py` remains a legacy SSH-first helper, not a true day-0 mechanism

### Desired State

The target model for this project is:

- day-0 install and bootstrap by `netinstall-cli`
- explicit device targeting by MAC address
- minimal bootstrap only for handover into Terraform
- Terraform remains the primary post-bootstrap RouterOS configuration system
- control-node wrappers such as shell or Ansible may exist, but they do not become the MikroTik source of truth

### Constraints

- Netinstall requires local installation-segment access
- Netinstall is not a universal solution for routed-only, cloud-only, or LTE-only recovery paths
- `netinstall-cli` and the required RouterOS `.npk` packages must be locally available
- secret-bearing rendered artifacts must remain outside tracked repository roots
- the migration should preserve the current manual import path until the Netinstall path is validated

### Options Considered

#### Option 1: Keep Manual Import As The Primary Path

Continue using WinBox or SSH import of `init-terraform.rsc` as the main bootstrap mechanism.

This keeps the current workflow simple, but it does not solve deterministic reinstall or explicit MAC-targeted day-0 provisioning.

#### Option 2: Use SSH-First Or MAC-Import Automation

Automate import of the current bootstrap script through SSH, WinBox, `mac-telnet`, or similar helpers.

This improves convenience in some scenarios, but it still depends on the router already being in a usable intermediate state.

#### Option 3: Use Netinstall With A Minimal Pre-Configuration Script

Use `netinstall-cli` to reinstall RouterOS, target the device by MAC address, and apply a minimal pre-configuration script during installation.

This is more invasive, but it is the most deterministic day-0 contract and preserves the existing Terraform-first post-bootstrap model.

---

## Decision

### 1. Adopt A Two-Phase MikroTik Lifecycle

MikroTik Chateau automation is split into two phases:

1. day-0 installation and bootstrap
2. day-1 and day-2 configuration by Terraform

The day-0 phase exists only to establish the minimum handover state required by Terraform.

### 2. Standardize On `netinstall-cli` As The Target Day-0 Mechanism

The target automatable day-0 mechanism is `netinstall-cli` executed from the control node.

The target install pattern is:

- place the device into Etherboot or Netinstall mode
- invoke `netinstall-cli` from the control node
- restrict installation to the intended device by MAC address
- apply a minimal RouterOS bootstrap script during installation
- hand over into the normal Terraform workflow after install completes

This ADR defines the target architecture. It does not claim that the repository has already completed the cutover from the current manual import path.

### 3. Preserve Terraform As The Post-Bootstrap Owner

Terraform remains the primary desired-state system for MikroTik after bootstrap.

Control-node shell wrappers or Ansible plays may orchestrate:

- prerequisite checks
- rendering of execution artifacts
- invocation of `netinstall-cli`
- first-pass verification after install

Those wrappers are implementation detail. They do not change the ownership boundary:

- day-0 bootstrap prepares the device for Terraform
- Terraform owns ongoing RouterOS configuration

### 4. Keep Legacy SSH-First Helpers Only As Compatibility Tools

Legacy SSH-first helpers such as `topology-tools/scripts/deployers/mikrotik_bootstrap.py` may remain for manual recovery or compatibility scenarios.

They are explicitly not the canonical ADR 0057 implementation path.

### 5. Define A Minimal Handover Contract

The day-0 bootstrap script must stay limited to the minimum state required for Terraform handover:

- system identity if needed
- management IP on the intended interface or bridge
- REST API and related service configuration required by Terraform
- Terraform automation user and bootstrap credential
- minimum firewall allowance for API-based management from the intended LAN
- optional SSH only when justified for recovery or operator fallback

The bootstrap script must not carry day-1 or day-2 desired state.

Full network policy, services, VPN, containers, and steady-state RouterOS configuration belong to Terraform.

### 6. Preserve Current Artifact Compatibility During Migration

This ADR does not require an immediate rename of existing bootstrap artifacts.

During migration, the logical day-0 script may continue to be materialized as:

- `generated/bootstrap/rtr-mikrotik-chateau/init-terraform.rsc`
- `.work/native/bootstrap/rtr-mikrotik-chateau/init-terraform.rsc`

If the project later chooses to rename that artifact to `bootstrap.rsc`, that is an implementation cutover step, not a prerequisite for adopting this ADR.

### 7. Keep Tracked Sources Release-Safe

Tracked sources must remain secret-free and reviewable.

The repository may track:

- the bootstrap template under `topology-tools/templates/bootstrap/mikrotik/`
- generated release-safe bootstrap output under `generated/bootstrap/rtr-mikrotik-chateau/`
- generated release-safe examples such as `terraform.tfvars.example`

Secret-bearing rendered execution artifacts must be materialized only into ignored execution roots such as:

- `local/bootstrap/rtr-mikrotik-chateau/` when justified as an operator-local bridge
- `.work/native/bootstrap/rtr-mikrotik-chateau/`
- `dist/bootstrap/rtr-mikrotik-chateau/` when explicitly assembling a local-input package

This stays consistent with ADR 0054 and ADR 0056.

### 8. Keep The Current Secret Contract For Now

Bootstrap secrets remain in the current repository secret model until a later ADR changes that contract.

This includes:

- Terraform bootstrap passwords
- optional SSH recovery credentials
- any other secret values required by the bootstrap script

The current contract is:

- tracked templates remain secret-free
- secret values come from `ansible/group_vars/all/vault.yml` or another explicitly approved current path
- local-only bridges are allowed only where there is a documented justification
- the final secret-bearing RouterOS script is rendered only into ignored execution roots

`Ansible Vault` therefore remains the current system of record for tracked bootstrap secrets.

### 9. Treat Netinstall Readiness As A Hard Gate

The Netinstall path may run only when prerequisites have passed.

At minimum, the control-node workflow must verify:

- `netinstall-cli` is installed and available in `PATH`
- the correct RouterOS package files are available locally
- the RouterOS package checksum is verified when an expected checksum is supplied
- the intended install interface is known
- the control node is on the correct installation segment
- the rendered bootstrap artifact exists at the expected execution path

If these checks fail, the workflow must stop before installation begins.

The default restore profile is `minimal`.
`backup` and `rsc` profiles are compatibility-only and require explicit operator opt-in.

---

## Bootstrap Contract

### Minimum Successful Stage-1 Result

After successful bootstrap, the router must expose:

- management IP reachable from the intended operator LAN
- RouterOS API reachable on the intended port
- Terraform automation credentials
- minimum firewall allowance for API-based management
- optional SSH only if intentionally retained for recovery

### Logical Bootstrap Inputs

The logical bootstrap input set is:

- public topology-derived values such as identity, management IP, LAN CIDR, DNS domain, and API port
- bootstrap secret values such as the Terraform password
- local execution parameters such as package path, Netinstall interface, client IP, and target MAC address

The first class may remain tracked.
The second and third classes are execution-time inputs and must not leak into tracked outputs unless they are explicitly non-secret examples.

### Example Minimal Bootstrap

```routeros
/user add name=terraform password=StrongPass group=full ; pragma: allowlist secret
/ip service set www-ssl disabled=no port=8443
/ip address add address=192.168.88.1/24 interface=bridge
/ip firewall filter add chain=input action=accept protocol=tcp dst-port=8443 src-address=192.168.88.0/24
```

The real template should additionally:

- be idempotent where practical
- avoid unnecessary service exposure
- prefer LAN-scoped management access
- prepare only the minimum state required for the first Terraform plan or apply

### Example Target Invocation Shape

```bash
netinstall-cli \
  -e \
  --mac 00:11:22:33:44:55 \
  -i enp3s0 \
  -a 192.168.88.3 \
  -s .work/native/bootstrap/rtr-mikrotik-chateau/init-terraform.rsc \
  /srv/routeros/routeros-7.20.8-arm64.npk
```

### Example Control-Node Wrapper Shape

```yaml
- name: Bootstrap MikroTik for Terraform handover
  hosts: localhost
  connection: local
  gather_facts: false
  tasks:
    - name: Check netinstall-cli is installed
      ansible.builtin.command: which netinstall-cli
      changed_when: false

    - name: Check RouterOS package exists
      ansible.builtin.stat:
        path: "{{ mikrotik_routeros_package }}"
      register: mikrotik_routeros_package_stat

    - name: Fail when RouterOS package is missing
      ansible.builtin.fail:
        msg: "RouterOS package not found: {{ mikrotik_routeros_package }}"
      when: not mikrotik_routeros_package_stat.stat.exists

    - name: Run Netinstall for the target MAC address
      ansible.builtin.command:
        argv:
          - netinstall-cli
          - -e
          - --mac
          - "{{ mikrotik_bootstrap_mac }}"
          - -i
          - "{{ mikrotik_netinstall_interface }}"
          - -a
          - "{{ mikrotik_netinstall_client_ip }}"
          - -s
          - ".work/native/bootstrap/rtr-mikrotik-chateau/init-terraform.rsc"
          - "{{ mikrotik_routeros_package }}"
```

This example illustrates one possible wrapper shape only.

### Example Secret Flow

```yaml
# ansible/group_vars/all/vault.yml
vault_mikrotik_terraform_password: "REDACTED"  # pragma: allowlist secret
```

```yaml
- name: Render bootstrap script from Vault-backed values
  ansible.builtin.template:
    src: templates/bootstrap/mikrotik/init-terraform-minimal.rsc.j2
    dest: .work/native/bootstrap/rtr-mikrotik-chateau/init-terraform.rsc
    mode: "0600"
```

In this flow, the template is tracked, the secret remains in the current Vault-backed contract, and the final plaintext RouterOS script exists only in the ignored execution workspace.

---

## Implementation Notes

Rollout sequencing, cutover gates, and compatibility cleanup are defined in:

- `adr/0057-migration-plan.md`

The implementation must explicitly manage three states:

1. current state: manual import of `init-terraform.rsc`
2. transition state: current manual path plus new Netinstall path
3. target state: Netinstall is the default documented and supported day-0 path

---

## Consequences

### Positive

1. Day-0 provisioning becomes more deterministic than import into an unknown running state.
2. Explicit MAC targeting reduces ambiguity about which device is being installed.
3. The ADR remains consistent with the repository's Terraform-first MikroTik model.
4. The migration can happen incrementally without breaking the existing manual import workflow immediately.
5. Secret-bearing execution artifacts remain outside tracked repository roots.
6. Legacy SSH helpers can still serve recovery use cases without distorting the target architecture.

### Negative And Trade-Offs

1. Netinstall is more invasive than importing a script into an already running device.
2. Operators need local installation-segment access and package management discipline.
3. The project temporarily carries two bootstrap paths during the transition window.
4. The final rendered bootstrap script contains plaintext secrets at execution time.
5. The cutover requires documentation, tooling, and operator workflow updates across multiple existing files.

---

## References

- ADR 0049: MikroTik Bootstrap Automation
- ADR 0054: Local Inputs Directory
- ADR 0055: Manual Terraform Extension Layer
- ADR 0056: Native Execution Workspace Outside Generated Roots
- `adr/0057-migration-plan.md`
- `topology-tools/templates/bootstrap/mikrotik/init-terraform-minimal.rsc.j2`
- `topology-tools/scripts/deployers/mikrotik_bootstrap.py`
- `deploy/phases/00-bootstrap.sh`
