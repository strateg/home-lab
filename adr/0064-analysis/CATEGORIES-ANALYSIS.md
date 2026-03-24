# ADR 0064: Categories Field Analysis

**Date:** 8 March 2026
**Status:** Analysis Complete
**Issue:** Missing `categories` field in class definitions

---

## Problem

ADR 0064 class definitions (firmware, os) do NOT include a `categories` field, which could be useful for:
1. Categorizing entities by functional role
2. Enabling filtering and queries
3. Documenting entity purpose
4. Supporting future taxonomy extensions

### Current State

```yaml
# Current class definition (NO categories)
class: class.firmware
version: 1.0.0

properties:
  vendor: mikrotik | apple | generic
  # ...
```

### Comparison with ADR 0058

ADR 0058 does NOT define `categories` either. It uses `capabilities` instead:

```yaml
# From ADR 0058
device_types:
  router:
    description: "Layer 3 packet forwarding device"
    capabilities:
      - routing
      - nat
      - firewall
```

**Key difference:**
- `capabilities` = what the entity CAN DO (functional)
- `categories` = what the entity IS (taxonomic)

---

## Analysis

### Option 1: Add `categories` field

```yaml
# Class definition WITH categories
class: class.firmware
version: 1.0.0
categories: [infrastructure, prerequisite, hardware-bound]

properties:
  vendor: mikrotik | apple | generic
  # ...
```

```yaml
# Class definition WITH categories
class: class.os
version: 1.0.0
categories: [infrastructure, prerequisite, runtime]

properties:
  family: linux | windows | macos
  # ...
```

**Pros:**
- Clear taxonomic classification
- Enables filtering: "all infrastructure entities"
- Supports documentation generation
- Aligns with common metadata patterns

**Cons:**
- Additional metadata to maintain
- Overlaps with capabilities in some cases
- Not strictly necessary for compilation

### Option 2: Keep current design (no categories)

**Pros:**
- Simpler class definition
- Less metadata to maintain
- Capabilities are sufficient for most use cases

**Cons:**
- No taxonomic metadata
- Harder to query "all infrastructure entities"
- Less self-documenting

---

## Recommendation

**✅ ADD `categories` field** to class definitions for the following reasons:

### 1. Taxonomic Clarity

Categories answer "WHAT IS THIS?" while capabilities answer "WHAT CAN IT DO?":

| Entity | Categories | Capabilities |
|--------|-----------|-------------|
| Firmware | [infrastructure, prerequisite, hardware-bound] | [cap.firmware.{vendor}, cap.firmware.boot.{type}] |
| OS | [infrastructure, prerequisite, runtime] | [cap.os.{family}, cap.os.init.{system}] |
| Device | [compute, network, storage] | [cap.device.virtualization, cap.device.routing] |

### 2. Query Support

```python
# Find all infrastructure entities
infrastructure_classes = [
    cls for cls in all_classes
    if "infrastructure" in cls.categories
]

# Find all prerequisite entities
prereqs = [
    cls for cls in all_classes
    if "prerequisite" in cls.categories
]
```

### 3. Documentation Generation

```markdown
## Infrastructure Entities

### Prerequisites
- **firmware** (hardware-bound) - Low-level device software
- **os** (runtime) - Operating system layer
```

### 4. Future Extensions

Categories support future taxonomy needs:
- `[virtual]` for virtual entities (VM firmware)
- `[deprecated]` for deprecated entities
- `[experimental]` for beta features

---

## Proposed Categories

### For `class.firmware`

```yaml
categories: [infrastructure, prerequisite, hardware-bound]
```

**Rationale:**
- `infrastructure` - Core system component
- `prerequisite` - Required before OS/workloads
- `hardware-bound` - Tied to physical/virtual hardware

### For `class.os`

```yaml
categories: [infrastructure, prerequisite, runtime]
```

**Rationale:**
- `infrastructure` - Core system component
- `prerequisite` - Required before services
- `runtime` - Provides execution environment

### For `class.compute` (future)

```yaml
categories: [infrastructure, host]
```

**Rationale:**
- `infrastructure` - Core system component
- `host` - Hosts workloads/services

### For `class.network` (future)

```yaml
categories: [infrastructure, connectivity]
```

**Rationale:**
- `infrastructure` - Core system component
- `connectivity` - Provides network services

---

## Standard Categories

Recommend defining a standard set of categories:

### Structural Categories
- `infrastructure` - Core infrastructure component
- `application` - Application-level entity
- `service` - Service entity

### Functional Categories
- `prerequisite` - Required before other entities
- `runtime` - Provides execution environment
- `host` - Hosts other entities
- `connectivity` - Provides network services
- `storage` - Provides storage services

### Deployment Categories
- `hardware-bound` - Tied to physical hardware
- `virtual` - Virtual/software entity
- `container` - Containerized entity

### Lifecycle Categories
- `stable` - Production-ready
- `experimental` - Beta/testing
- `deprecated` - Scheduled for removal

---

## Implementation

### 1. Update ADR 0064

Add `categories` field to all class definitions:

```yaml
# Firmware class
class: class.firmware
version: 1.0.0
categories: [infrastructure, prerequisite, hardware-bound]

# OS class
class: class.os
version: 1.0.0
categories: [infrastructure, prerequisite, runtime]
```

### 2. Document Categories

Add section to ADR 0064 explaining:
- Purpose of categories
- Standard category set
- How to choose categories

### 3. Update Schema

Add categories to JSON schema:

```json
{
  "type": "object",
  "properties": {
    "class": {"type": "string"},
    "version": {"type": "string"},
    "categories": {
      "type": "array",
      "items": {
        "type": "string",
        "enum": [
          "infrastructure", "application", "service",
          "prerequisite", "runtime", "host",
          "hardware-bound", "virtual", "container",
          "stable", "experimental", "deprecated"
        ]
      }
    }
  }
}
```

### 4. Add Validation

Compiler should validate:
- Categories are from allowed set
- Categories make sense for entity type
- No conflicting categories (e.g., `hardware-bound` + `virtual`)

---

## Examples

### Firmware with Categories

```yaml
# Physical firmware
object: obj.firmware.generic-uefi-x86
class_ref: class.firmware

# Class has: categories: [infrastructure, prerequisite, hardware-bound]

# Virtual firmware
object: obj.firmware.kvm-ovmf
class_ref: class.firmware

properties:
  virtual: true

# Could have: categories: [infrastructure, prerequisite, virtual]
```

### OS with Categories

```yaml
# Full OS
object: obj.os.debian-12
class_ref: class.os

# Class has: categories: [infrastructure, prerequisite, runtime]

# Container "OS"
object: obj.runtime.alpine-docker
class_ref: class.runtime

# Could have: categories: [infrastructure, runtime, container]
```

---

## Conclusion

**Recommendation:** ✅ **ADD `categories` field** to ADR 0064

**Changes needed:**
1. Update class definitions to include `categories`
2. Add "Categories" section to ADR explaining purpose
3. Define standard category set
4. Update schema and validation

**Benefits:**
- Clearer entity taxonomy
- Better documentation
- Query support
- Future extensibility

**Risks:**
- Minimal - categories are optional metadata
- Easy to add without breaking changes
- Can evolve over time

---

**Status:** ✅ READY TO IMPLEMENT
**Priority:** Medium (nice-to-have, not blocking)
**Effort:** Low (1-2 hours to update ADR and examples)
