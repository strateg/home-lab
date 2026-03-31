# ADR 0083: State Model and Concurrency Analysis

## Purpose

Define the initialization state machine formally, specify file locking, atomic write guarantees, and conflict handling for concurrent operations.

---

## State Machine Definition

### States

| State | Description | Entry Condition |
|-------|-------------|-----------------|
| `pending` | Device registered but not yet bootstrapped | Initial state, or lifecycle reset |
| `bootstrapping` | Bootstrap execution in progress | `init-node.py --node` invoked |
| `initialized` | Bootstrap completed, handover not yet verified | Bootstrap script/process succeeded |
| `verified` | Handover checks passed, ready for Terraform/Ansible | All handover checks passed |
| `failed` | Bootstrap or handover failed | Any error during bootstrap or handover |

### Transitions

| From | To | Trigger | Guard |
|------|----|---------|-------|
| `pending` | `bootstrapping` | `init-node.py --node <id>` | Prerequisites pass |
| `bootstrapping` | `initialized` | Bootstrap script completes successfully | Exit code 0 |
| `bootstrapping` | `failed` | Bootstrap script fails | Exit code != 0 or timeout |
| `initialized` | `verified` | `init-node.py --verify-only` or auto-verify | All handover checks pass |
| `initialized` | `failed` | Handover checks fail after max retries | Timeout exceeded |
| `failed` | `bootstrapping` | `init-node.py --force --node <id>` | Explicit operator force |
| `verified` | `bootstrapping` | `init-node.py --force --node <id>` | Explicit operator force |
| `verified` | `pending` | `init-node.py --reset --node <id> --confirm-reset` | **See safety guard below** |
| Any | `pending` | Pipeline re-generates manifest with new node | Node not in state file |
| *(new)* | `verified` | `init-node.py --import --node <id>` | Handover checks pass, device already operational |

### Safety Guard for `verified → pending`

This transition is **dangerous** because:
1. Device may have Terraform state depending on it
2. Resetting loses audit history
3. Re-bootstrap may format storage

**Required guards:**

```python
def reset_to_pending(node_id, confirm_reset=False):
    if not confirm_reset:
        raise UserError("E9720: --confirm-reset flag required for verified→pending transition")

    # Check for Terraform state
    tf_state_dir = f"generated/{project}/terraform/{node.domain}/"
    if has_terraform_state(tf_state_dir, node_id):
        warn(f"W9721: Terraform state exists for {node_id}. Reset will not remove state.")
        warn("       Consider 'terraform state rm' before reset if intended.")

    # Log for audit
    log_audit(f"RESET: {node_id} from verified to pending by operator")

    # Perform transition
    update_state(node_id, status="pending", reset_at=now())
```

### Forbidden Transitions

| From | To | Reason |
|------|----|--------|
| `pending` | `initialized` | Cannot skip bootstrap |
| `pending` | `verified` | Cannot skip bootstrap + verify |
| `bootstrapping` | `verified` | Must go through initialized first |
| `failed` | `verified` | Must re-bootstrap first |
| `failed` | `initialized` | Must re-bootstrap first |

---

## State File Schema

### Location

`.work/deploy-state/<project>/nodes/INITIALIZATION-STATE.yaml`

**Rationale:** ADR 0085 D6 defines `.work/deploy-state/<project>/` as the mutable deploy-state root. Initialization state is a subset of deploy-state and MUST live under the same root for consistency. The previous `.work/native/bootstrap/` location is superseded.

### Schema

```yaml
version: "1.0"
updated_at: "2026-03-30T12:05:00Z"  # ISO 8601

nodes:
  - id: "rtr-mikrotik-chateau"       # Must match manifest node ID
    status: "verified"                 # pending|bootstrapping|initialized|verified|failed
    mechanism: "netinstall"            # From manifest, for display
    contract_hash: "sha256:a1b2c3..."  # Hash of initialization_contract for drift detection
    imported: false                    # true if node was imported via --import
    last_action: "verify"              # last operation performed
    last_action_at: "2026-03-30T12:05:00Z"
    last_error: null                   # null or error message string
    attempt_count: 1                   # Number of bootstrap attempts
    history:                           # Audit trail (last 10 entries)
      - timestamp: "2026-03-30T12:00:00Z"
        from_state: "pending"
        to_state: "bootstrapping"
        action: "bootstrap"
      - timestamp: "2026-03-30T12:02:30Z"
        from_state: "bootstrapping"
        to_state: "initialized"
        action: "bootstrap_complete"
      - timestamp: "2026-03-30T12:05:00Z"
        from_state: "initialized"
        to_state: "verified"
        action: "verify"
```

---

## Concurrency Model

### Single-Operator Assumption

This is a single-operator home lab. The primary concurrency scenario is:

1. Operator runs `init-node.py --node A` in terminal 1.
2. Operator runs `init-node.py --node B` in terminal 2.
3. Both update the same `INITIALIZATION-STATE.yaml` file.

### File Locking Strategy

**Approach:** Advisory file lock with `fcntl.flock()` (Unix) or `msvcrt.locking()` (Windows).

```python
import fcntl
import os
import sys

class StateFileLock:
    def __init__(self, state_file_path):
        self.lock_path = state_file_path + ".lock"
        self.lock_fd = None

    def acquire(self, timeout_seconds=30):
        self.lock_fd = open(self.lock_path, 'w')
        try:
            if sys.platform == 'win32':
                import msvcrt
                msvcrt.locking(self.lock_fd.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                fcntl.flock(self.lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except (IOError, OSError):
            raise RuntimeError(
                f"State file is locked by another init-node.py process. "
                f"Lock file: {self.lock_path}"
            )

    def release(self):
        if self.lock_fd:
            if sys.platform == 'win32':
                import msvcrt
                msvcrt.locking(self.lock_fd.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                fcntl.flock(self.lock_fd, fcntl.LOCK_UN)
            self.lock_fd.close()
            os.unlink(self.lock_path)
```

### Atomic Write Strategy

State file updates MUST be atomic to prevent corruption:

```python
import tempfile
import os

def write_state_atomic(state_file_path, content):
    dir_name = os.path.dirname(state_file_path)
    with tempfile.NamedTemporaryFile(
        mode='w', dir=dir_name, suffix='.tmp',
        delete=False
    ) as tmp:
        tmp.write(content)
        tmp_path = tmp.name
    os.replace(tmp_path, state_file_path)  # Atomic on POSIX and Windows
```

### Read-Modify-Write Pattern

```python
def update_node_state(state_file, node_id, new_status, action, error=None):
    with StateFileLock(state_file):
        # Read current state
        state = yaml_load(state_file) if os.path.exists(state_file) else default_state()

        # Find or create node entry
        node = find_or_create_node(state, node_id)

        # Validate transition
        validate_transition(node["status"], new_status)

        # Update
        old_status = node["status"]
        node["status"] = new_status
        node["last_action"] = action
        node["last_action_at"] = now_iso8601()
        node["last_error"] = error
        if new_status == "bootstrapping":
            node["attempt_count"] += 1
        node["history"].append({
            "timestamp": now_iso8601(),
            "from_state": old_status,
            "to_state": new_status,
            "action": action
        })
        # Keep only last 10 history entries
        node["history"] = node["history"][-10:]

        state["updated_at"] = now_iso8601()

        # Write atomically
        write_state_atomic(state_file, yaml_dump(state))
```

---

## Edge Cases

### E1: Manifest Regenerated with New Nodes

When the pipeline regenerates `INITIALIZATION-MANIFEST.yaml` and a new node appears:

- `init-node.py` compares manifest nodes with state file nodes.
- New nodes (in manifest but not in state) are added with `status: pending`.
- Removed nodes (in state but not in manifest) are kept with a `stale: true` flag.

### E2: Manifest Regenerated with Changed Contract (Drift Detection)

When a node's `initialization_contract` changes (e.g., mechanism changed, requirements added):

**Detection mechanism (per D18):**
1. State file stores `contract_hash` (SHA256 of initialization_contract YAML)
2. On each `init-node.py` run, compute current hash from manifest
3. Compare hashes

**Behavior:**
- State file retains the old status
- `init-node.py` warns about drift
- Operator must explicitly handle:
  - `--force`: Re-bootstrap with new contract
  - `--acknowledge-drift`: Update hash without re-bootstrap (for non-breaking changes)

**Example:**

```
$ init-node.py --status

Node Initialization Status (2026-03-30T12:05:00Z)
==================================================
rtr-mikrotik-chateau  verified  ⚠ CONTRACT DRIFT DETECTED
  Previous hash: sha256:abc123...
  Current hash:  sha256:def456...
  Changes: +1 requirement, handover timeout changed

To resolve:
  --force               Re-bootstrap with new contract
  --acknowledge-drift   Accept changes without re-bootstrap
```

### E3: Stale Lock File

If `init-node.py` crashes, the lock file may remain:

- Lock file older than 10 minutes is considered stale.
- `init-node.py` removes stale lock files with a warning.
- `--break-lock` flag forces lock removal.

### E4: Concurrent init-node.py for Same Node

If two processes try to bootstrap the same node:

- First process acquires lock, sets status to `bootstrapping`.
- Second process reads `bootstrapping` status, refuses to start.
- Error: "Node X is currently being bootstrapped by another process."

### E5: Pipeline Runs During Bootstrap

If the pipeline regenerates while `init-node.py` is running:

- Pipeline writes to `generated/` (read-only for init-node.py).
- `init-node.py` reads from the selected immutable deploy bundle (`.work/deploy/bundles/<bundle_id>/`).
- No conflict: pipeline and deploy domain use different directories, and the bundle is immutable once assembled.
- A new bundle can be assembled from the updated generated artifacts; the running `init-node.py` continues using its selected bundle.

---

## State File Location Rationale

| Location | Pros | Cons | Decision |
|----------|------|------|----------|
| `generated/` | Co-located with manifest | Mutable state in immutable root | Rejected |
| `.work/native/bootstrap/` | Deploy domain, already ignored | Local-path-centric, not project-scoped | Superseded |
| `.work/deploy-state/<project>/` | Project-scoped, aligned with ADR 0085 D6 | Separate from manifest | **Selected** |
| `projects/<project>/` | Tracked | Runtime state in source control | Rejected |

---

## Monitoring and Observability

### State File Health Check

`init-node.py --status` prints a summary:

```
Node Initialization Status (2026-03-30T12:05:00Z)
==================================================
rtr-mikrotik-chateau  verified       (1 attempt,  last: 2026-03-30T12:05)
hv-proxmox-xps        pending        (0 attempts)
sbc-orangepi5          failed         (2 attempts, last: 2026-03-30T11:45)
                                      Error: SSH unreachable after 300s timeout
sbc-orangepi5-b        pending        (0 attempts)
```

### Exit Codes

| Code | Meaning |
|------|---------|
| 0 | Success (all requested nodes initialized/verified) |
| 1 | Partial failure (some nodes failed) |
| 2 | All nodes failed |
| 3 | Prerequisites check failed |
| 4 | Lock contention (another process running) |
| 5 | Manifest not found (pipeline not run) |
