# Snapshot Propagation Mechanism Design

**ADR Reference:** 0105 (Extension)
**Date:** 2026-06-10
**Status:** Proposed

---

## Problem Statement

The deploy system must propagate topology snapshot identifiers (git commit SHA) to ALL managed devices so that:

1. Each device "knows" which topology snapshot it was configured from
2. System can verify all devices are on compatible/same snapshot
3. Before new deploy: "device X is on snapshot Y, deploying snapshot Z"
4. After deploy: device confirms "I am now on snapshot Z"

**Constraint C19:** Use industry best practices, no custom systems.

---

## Per-Platform Mechanism Analysis

### 1. MikroTik RouterOS

**Evaluated Options:**

| Mechanism | Pros | Cons | Selected |
|-----------|------|------|----------|
| `system identity` | Standard, single field | Only holds name, limited length | No |
| `system note` | Designed for notes, visible in UI | Not exposed via REST API, no terraform resource | No |
| `system script` with comment | Terraform supported, persistent | Requires script execution to read | No |
| **`routeros_system_script` as metadata store** | Persistent file, queryable via API | Slightly unconventional | **YES** |
| Global variable via script | Can store structured data | Volatile (lost on reboot) | No |

**Chosen Mechanism: `routeros_system_script` as Metadata Store**

Create a dedicated script resource that stores snapshot metadata as RouterOS script content. The script itself does nothing when executed - it serves purely as a persistent, API-queryable metadata store.

```hcl
# topology_metadata.tf (generated)
resource "routeros_system_script" "topology_metadata" {
  name   = "topology-metadata"
  source = <<-EOT
    # Topology Snapshot Metadata - DO NOT MODIFY MANUALLY
    # This script stores deployment metadata, not executable code.
    #
    # snapshot_sha:     ${var.topology_snapshot_sha}
    # snapshot_short:   ${substr(var.topology_snapshot_sha, 0, 8)}
    # deploy_timestamp: ${timestamp()}
    # project:          home-lab
    # generator:        terraform_mikrotik_generator
    #
    :log info "Topology metadata: ${substr(var.topology_snapshot_sha, 0, 8)}"
  EOT
  comment = "Topology snapshot: ${substr(var.topology_snapshot_sha, 0, 8)} - managed by topology"
}
```

**Query Mechanism:**

```bash
# Via REST API
curl -k -u "$USER:$PASS" \
  "https://192.168.88.1/rest/system/script?name=topology-metadata" \
  | jq -r '.[0].source'

# Via SSH
ssh admin@192.168.88.1 "/system/script/print where name=topology-metadata"

# Parse snapshot SHA
curl -k -u "$USER:$PASS" \
  "https://192.168.88.1/rest/system/script?name=topology-metadata" \
  | jq -r '.[0].source' \
  | grep "snapshot_sha:" \
  | awk '{print $2}'
```

**Alternative: Use comment field on multiple resources**

Every generated resource already has a `comment` field with topology metadata. We can standardize this to include snapshot SHA:

```hcl
resource "routeros_interface_vlan" "servers" {
  name      = "vlan30"
  vlan_id   = 30
  interface = "bridge"
  comment   = "inst.vlan.servers - snapshot:${substr(var.topology_snapshot_sha, 0, 8)} - managed by topology"
}
```

This provides defense-in-depth: even if metadata script is deleted, each resource carries its lineage.

---

### 2. Proxmox VE (VMs/LXC)

**Evaluated Options:**

| Mechanism | Pros | Cons | Selected |
|-----------|------|------|----------|
| `description` field | Human readable, visible in UI | Long text, may contain existing content | Partial |
| **`tags` list** | Machine parseable, visible in UI, Terraform native | Limited length per tag | **YES** |
| VM notes | Visible in UI | May interfere with user notes | No |
| Custom metadata in cloud-init | Available to guest OS | Not queryable from Proxmox API | Complement |

**Chosen Mechanism: `tags` list with snapshot prefix**

```hcl
resource "proxmox_virtual_environment_vm" "docker_host" {
  name        = "docker-host"
  description = "Docker host for media services"

  # Standard tags + topology snapshot tag
  tags = [
    "topology",
    "snapshot-${substr(var.topology_snapshot_sha, 0, 8)}",
    "deployed-${formatdate("YYYYMMDD", timestamp())}"
  ]

  # ... rest of config
}

resource "proxmox_virtual_environment_container" "adguard" {
  # Same pattern for LXC
  tags = [
    "topology",
    "snapshot-${substr(var.topology_snapshot_sha, 0, 8)}"
  ]
}
```

**Query Mechanism:**

```bash
# Via Proxmox API
curl -k -H "Authorization: PVEAPIToken=..." \
  "https://proxmox:8006/api2/json/nodes/pve/qemu" \
  | jq '.data[] | {vmid, name, tags}'

# Via pvesh
pvesh get /nodes/pve/qemu --output-format json \
  | jq '.[] | select(.tags | contains("snapshot-8f85cfe4"))'

# Via Terraform data source
data "proxmox_virtual_environment_vms" "all" {
  node_name = "pve"
}

output "vm_snapshots" {
  value = {
    for vm in data.proxmox_virtual_environment_vms.all.vms :
    vm.name => [for tag in vm.tags : tag if startswith(tag, "snapshot-")]
  }
}
```

**Complement: Cloud-init metadata for guest OS awareness**

The guest OS can also know its topology lineage via cloud-init:

```yaml
# cloud-init user-data
write_files:
  - path: /etc/topology-snapshot
    content: |
      SNAPSHOT_SHA=${topology_snapshot_sha}
      SNAPSHOT_SHORT=${topology_snapshot_short}
      DEPLOY_TIMESTAMP=${deploy_timestamp}
      PROJECT=home-lab
    permissions: '0644'
```

---

### 3. Oracle Cloud (OCI) VPS

**Evaluated Options:**

| Mechanism | Pros | Cons | Selected |
|-----------|------|------|----------|
| **`freeform_tags`** | Unlimited key-value, queryable, Terraform native | None significant | **YES** |
| `defined_tags` | Namespace controlled | Requires tag namespace setup | No |
| Instance metadata | Available to instance | Limited to 32KB total | Complement |
| `display_name` | Visible | Too limited for metadata | No |

**Chosen Mechanism: `freeform_tags` map**

```hcl
resource "oci_core_instance" "vps_frankfurt" {
  # ... existing config ...

  freeform_tags = {
    "topology-project"    = "home-lab"
    "topology-snapshot"   = var.topology_snapshot_sha
    "topology-short"      = substr(var.topology_snapshot_sha, 0, 8)
    "topology-deployed"   = timestamp()
    "topology-managed"    = "true"
  }

  # Extended metadata for instance awareness
  metadata = {
    "ssh_authorized_keys"  = var.ssh_public_key
    "topology_snapshot"    = var.topology_snapshot_sha
  }
}
```

**Query Mechanism:**

```bash
# Via OCI CLI
oci compute instance list \
  --compartment-id $COMPARTMENT_ID \
  --query 'data[*].{"name":"display-name","snapshot":"freeform-tags"."topology-snapshot"}' \
  --output table

# Filter by snapshot
oci compute instance list \
  --compartment-id $COMPARTMENT_ID \
  --query 'data[?"freeform-tags"."topology-snapshot"==`8f85cfe4...`]'

# Via Terraform data source
data "oci_core_instances" "all" {
  compartment_id = var.compartment_id
}

output "instance_snapshots" {
  value = {
    for inst in data.oci_core_instances.all.instances :
    inst.display_name => inst.freeform_tags["topology-snapshot"]
  }
}
```

---

## Unified Snapshot Variable

All generated Terraform configurations must accept a common snapshot variable:

```hcl
# variables.tf (added to all device configs)
variable "topology_snapshot_sha" {
  description = "Git commit SHA of topology used to generate this configuration"
  type        = string

  validation {
    condition     = can(regex("^[a-f0-9]{40}$", var.topology_snapshot_sha))
    error_message = "topology_snapshot_sha must be a valid 40-character git SHA"
  }
}

variable "topology_snapshot_short" {
  description = "Short (8 char) git commit SHA"
  type        = string
  default     = ""
}

# Computed short if not provided
locals {
  snapshot_short = var.topology_snapshot_short != "" ? var.topology_snapshot_short : substr(var.topology_snapshot_sha, 0, 8)
}
```

**Injection at apply time:**

```bash
# Get current snapshot
SNAPSHOT=$(git rev-parse HEAD)

# Apply with snapshot
terraform apply \
  -var="topology_snapshot_sha=$SNAPSHOT" \
  -var="topology_snapshot_short=$(echo $SNAPSHOT | cut -c1-8)"
```

---

## Verification Workflow

### Pre-Deploy Check Script

```bash
#!/bin/bash
# scripts/verify-snapshot-consistency.sh

set -euo pipefail

DEPLOYING_SNAPSHOT=$(git rev-parse HEAD)
DEPLOYING_SHORT=${DEPLOYING_SNAPSHOT:0:8}

echo "=== Topology Snapshot Verification ==="
echo "Deploying: $DEPLOYING_SHORT ($DEPLOYING_SNAPSHOT)"
echo ""

# Check MikroTik
echo "--- MikroTik rtr-mikrotik-chateau ---"
MIKROTIK_SNAPSHOT=$(curl -sk -u "$MIKROTIK_USER:$MIKROTIK_PASS" \
  "https://$MIKROTIK_HOST/rest/system/script?name=topology-metadata" \
  | jq -r '.[0].source // "NOT_FOUND"' \
  | grep -o 'snapshot_sha:[[:space:]]*[a-f0-9]*' \
  | awk '{print $2}' || echo "NOT_FOUND")

if [ "$MIKROTIK_SNAPSHOT" = "$DEPLOYING_SNAPSHOT" ]; then
  echo "  Status: CURRENT (no changes needed)"
elif [ "$MIKROTIK_SNAPSHOT" = "NOT_FOUND" ]; then
  echo "  Status: NO METADATA (first deploy or metadata missing)"
else
  echo "  Status: OUTDATED"
  echo "  Current: ${MIKROTIK_SNAPSHOT:0:8}"
  echo "  Target:  $DEPLOYING_SHORT"
fi
echo ""

# Check Proxmox VMs
echo "--- Proxmox VMs ---"
PROXMOX_VMS=$(curl -sk -H "Authorization: PVEAPIToken=$PROXMOX_TOKEN" \
  "https://$PROXMOX_HOST:8006/api2/json/nodes/pve/qemu" \
  | jq -r '.data[] | select(.tags != null) | "\(.name):\(.tags)"')

for vm in $PROXMOX_VMS; do
  NAME=$(echo "$vm" | cut -d: -f1)
  TAGS=$(echo "$vm" | cut -d: -f2)
  VM_SNAPSHOT=$(echo "$TAGS" | tr ';' '\n' | grep "snapshot-" | sed 's/snapshot-//' || echo "NOT_FOUND")

  if [ "$VM_SNAPSHOT" = "$DEPLOYING_SHORT" ]; then
    echo "  $NAME: CURRENT"
  elif [ "$VM_SNAPSHOT" = "NOT_FOUND" ]; then
    echo "  $NAME: NO TAG"
  else
    echo "  $NAME: OUTDATED ($VM_SNAPSHOT -> $DEPLOYING_SHORT)"
  fi
done
echo ""

# Check OCI
echo "--- Oracle Cloud VPS ---"
OCI_INSTANCES=$(oci compute instance list \
  --compartment-id "$OCI_COMPARTMENT_ID" \
  --lifecycle-state RUNNING \
  --query 'data[*].{"name":"display-name","snapshot":"freeform-tags"."topology-snapshot"}' \
  --output json 2>/dev/null || echo "[]")

echo "$OCI_INSTANCES" | jq -r '.[] | "\(.name): \(.snapshot // "NOT_FOUND")"' | while read line; do
  NAME=$(echo "$line" | cut -d: -f1)
  SNAP=$(echo "$line" | cut -d: -f2 | tr -d ' ')

  if [ "$SNAP" = "$DEPLOYING_SNAPSHOT" ]; then
    echo "  $NAME: CURRENT"
  elif [ "$SNAP" = "NOT_FOUND" ]; then
    echo "  $NAME: NO TAG"
  else
    echo "  $NAME: OUTDATED (${SNAP:0:8} -> $DEPLOYING_SHORT)"
  fi
done

echo ""
echo "=== Verification Complete ==="
```

### Post-Deploy Confirmation Script

```bash
#!/bin/bash
# scripts/confirm-deployment.sh

set -euo pipefail

EXPECTED_SNAPSHOT=$1
DEVICE=$2

case "$DEVICE" in
  mikrotik)
    ACTUAL=$(curl -sk -u "$MIKROTIK_USER:$MIKROTIK_PASS" \
      "https://$MIKROTIK_HOST/rest/system/script?name=topology-metadata" \
      | jq -r '.[0].source' \
      | grep -o 'snapshot_sha:[[:space:]]*[a-f0-9]*' \
      | awk '{print $2}')
    ;;
  proxmox-*)
    VMNAME=${DEVICE#proxmox-}
    ACTUAL=$(curl -sk -H "Authorization: PVEAPIToken=$PROXMOX_TOKEN" \
      "https://$PROXMOX_HOST:8006/api2/json/nodes/pve/qemu" \
      | jq -r ".data[] | select(.name==\"$VMNAME\") | .tags" \
      | tr ';' '\n' | grep "snapshot-" | sed 's/snapshot-//')
    ;;
  oracle-*)
    INSTNAME=${DEVICE#oracle-}
    ACTUAL=$(oci compute instance list \
      --compartment-id "$OCI_COMPARTMENT_ID" \
      --display-name "$INSTNAME" \
      --query 'data[0]."freeform-tags"."topology-snapshot"' \
      --raw-output)
    ;;
esac

if [ "${ACTUAL:0:8}" = "${EXPECTED_SNAPSHOT:0:8}" ]; then
  echo "CONFIRMED: $DEVICE is on snapshot ${EXPECTED_SNAPSHOT:0:8}"
  exit 0
else
  echo "MISMATCH: $DEVICE has ${ACTUAL:0:8}, expected ${EXPECTED_SNAPSHOT:0:8}"
  exit 1
fi
```

---

## Generator Changes Required

### 1. MikroTik Generator

Add to `/home/nixos/workspaces/home-lab/topology/object-modules/mikrotik/templates/terraform/`:

**New file: `topology_metadata.tf.j2`**

```jinja2
# Topology snapshot metadata - managed by generator
# This script stores deployment lineage, not executable code.

resource "routeros_system_script" "topology_metadata" {
  name   = "topology-metadata"
  source = <<-EOT
    # Topology Snapshot Metadata
    # Generated: {{ generation_timestamp }}
    # Generator: terraform_mikrotik_generator
    #
    # snapshot_sha:     $${var.topology_snapshot_sha}
    # snapshot_short:   $${local.snapshot_short}
    # deploy_timestamp: $${timestamp()}
    # project:          {{ project_id }}
    # routers:          {{ routers_list_expr }}
    #
    :log info "Topology: $${local.snapshot_short}"
  EOT
  comment = "Topology snapshot metadata - managed by topology"
}
```

**Update `variables.tf.j2`** to add:

```jinja2
variable "topology_snapshot_sha" {
  description = "Git commit SHA of topology used to generate this configuration"
  type        = string
  default     = "0000000000000000000000000000000000000000"
}

locals {
  snapshot_short = substr(var.topology_snapshot_sha, 0, 8)
}
```

### 2. Proxmox Generator

Update VM/LXC templates to include snapshot tags.

### 3. Oracle Generator

Update instance template to include `freeform_tags` with snapshot.

### 4. Deploy Scripts

Update `scripts/mikrotik-safe-apply.sh` to pass snapshot variable:

```bash
SNAPSHOT=$(git rev-parse HEAD)
terraform apply \
  -var="topology_snapshot_sha=$SNAPSHOT" \
  -auto-approve
```

---

## Decisions for ADR 0105

### D8. Snapshot Propagation per Device Type

Each device class uses its native metadata mechanism:

| Device Class | Mechanism | Field/Resource |
|--------------|-----------|----------------|
| MikroTik | Script as metadata store | `routeros_system_script.topology_metadata` |
| Proxmox VM/LXC | Tags | `tags = ["snapshot-XXXXXXXX"]` |
| Oracle OCI | Freeform tags | `freeform_tags.topology-snapshot` |

All mechanisms are:
- Native to each platform (no custom systems)
- Queryable via API
- Managed by Terraform
- Visible in platform UI

### D9. Unified Snapshot Variable Contract

All generated Terraform configurations accept:

```hcl
variable "topology_snapshot_sha" {
  type = string
  # 40-character git SHA
}
```

Generators embed this in platform-appropriate metadata.

### D10. Verification Workflow

Pre-deploy and post-deploy scripts query each device API to:
1. Report current snapshot per device
2. Compare against deploying snapshot
3. Confirm deployment success

Scripts use only native APIs (REST, OCI CLI, Proxmox API).

---

## Implementation Phases

### Phase 1: Variable and Template Updates

| Task | File |
|------|------|
| Add `topology_snapshot_sha` variable | All `variables.tf.j2` templates |
| Create `topology_metadata.tf.j2` | MikroTik templates |
| Add tags to VM/LXC resources | Proxmox templates |
| Add freeform_tags | Oracle templates |

### Phase 2: Generator Updates

| Task | File |
|------|------|
| Add metadata template to template list | `terraform_mikrotik_generator.py` |
| Pass `project_id` to render context | All generators |
| Update projection to include snapshot field | Projection modules |

### Phase 3: Deploy Scripts

| Task | File |
|------|------|
| Create verification script | `scripts/verify-snapshot-consistency.sh` |
| Create confirmation script | `scripts/confirm-deployment.sh` |
| Update safe-apply to pass snapshot | `scripts/mikrotik-safe-apply.sh` |
| Add Taskfile integration | `taskfiles/deploy.yaml` |

---

## Summary

This design satisfies all requirements while adhering to C19 (no custom systems):

1. **MikroTik**: Uses `routeros_system_script` as persistent, API-queryable metadata store
2. **Proxmox**: Uses native `tags` field, visible in UI and queryable via API
3. **Oracle OCI**: Uses native `freeform_tags`, queryable via OCI CLI and API
4. **Verification**: Bash scripts query each platform's native API
5. **Confirmation**: Same scripts verify post-deploy state matches expected snapshot

All mechanisms are industry-standard, tool-native, and require no custom state management infrastructure.

---

## References

- [Terraform RouterOS Provider](https://registry.terraform.io/providers/terraform-routeros/routeros/latest/docs)
- [BPG Proxmox Provider - VM Resource](https://github.com/bpg/terraform-provider-proxmox/blob/main/docs/resources/virtual_environment_vm.md)
- [OCI Terraform Provider - Instance Resource](https://registry.terraform.io/providers/oracle/oci/latest/docs/resources/core_instance)
- [OCI Tagging Best Practices](https://docs.oracle.com/en-us/iaas/Content/API/SDKDocs/terraformbestpractices_topic-Tagging_Resources.htm)
- [MikroTik REST API](https://help.mikrotik.com/docs/spaces/ROS/pages/47579229/Scripting)
