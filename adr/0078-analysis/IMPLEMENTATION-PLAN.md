# ADR0078 Implementation Plan

**Date:** 2026-03-21
**ADR:** `adr/0078-object-module-local-template-layout.md`
**Status:** Completed for generator scope; Phase 6-7 added for boundary enforcement
**Amended:** 2026-03-22 (compilers/validators/generators unified rules)
**Amended:** 2026-03-22 (instance isolation, cross-object boundaries, dynamic discovery)

---

## 1. Objective

Reach ADR0078 target state for `v5`:

1. Object-specific generator code is located only in `object-modules/<object-id>/plugins`.
2. Object-specific templates are located only in `object-modules/<object-id>/templates/<generator-id>`.
3. Object-specific generator registration is owned by module manifests (`object-modules/**/plugins.yaml`).
4. Transitional shims in `v5/topology-tools/plugins/generators` are removed after compatibility gate.

Amended objective (2026-03-22):

1. Apply one architecture contract to all plugin families:
   - compilers;
   - validators;
   - generators.
2. Prepare v5 refactoring backlog and gates so unified rules are enforced in active migration work.

---

## 2. Scope

In scope (object-specific generators):

1. `base.generator.terraform_mikrotik`
2. `base.generator.bootstrap_mikrotik`
3. `base.generator.terraform_proxmox`
4. `base.generator.bootstrap_proxmox`
5. `base.generator.bootstrap_orangepi`

Out of scope (shared/global generators):

1. `base.generator.effective_json`
2. `base.generator.effective_yaml`
3. `base.generator.ansible_inventory`

---

## 3. Baseline (2026-03-21)

Already implemented:

1. Object-specific generator implementations exist in:
   - `v5/topology/object-modules/mikrotik/plugins/`
   - `v5/topology/object-modules/proxmox/plugins/`
   - `v5/topology/object-modules/orangepi/plugins/`
2. Central manifest points to moved generator files:
   - `v5/topology-tools/plugins/plugins.yaml`
3. MikroTik terraform templates are already co-located:
   - `v5/topology/object-modules/mikrotik/templates/terraform/`

Open gaps:

1. `proxmox` and `orangepi` do not yet own generator registration in local `plugins.yaml`.
2. Object-specific templates still remain in `v5/topology-tools/templates` for proxmox/bootstrap flows.
3. Compatibility shims still exist for moved generators in `v5/topology-tools/plugins/generators/`.
4. Authoring/operational docs still describe central-registration-first flow.

Implementation status update (2026-03-21):

1. Wave 1 completed: object-specific templates moved to object modules.
2. Wave 2 completed: object-specific generator registration moved to module manifests.
3. Wave 3 completed: compatibility shims removed from tools generator package.
4. Wave 4 completed: docs updated and release preflight includes explicit ADR0078 ownership check.
5. Wave 5 completed: object-specific projection builders moved out of shared tools module.

Closure note:

1. ADR0078 scope in this plan is fully closed (Waves 1-5).

---

## 4. Execution Plan

### Wave 1: Complete Template Co-location

Changes:

1. Move `v5/topology-tools/templates/terraform/proxmox/*` to:
   - `v5/topology/object-modules/proxmox/templates/terraform/*`
2. Move `v5/topology-tools/templates/bootstrap/proxmox/*` to:
   - `v5/topology/object-modules/proxmox/templates/bootstrap/*`
3. Move `v5/topology-tools/templates/bootstrap/mikrotik/*` to:
   - `v5/topology/object-modules/mikrotik/templates/bootstrap/*`
4. Move `v5/topology-tools/templates/bootstrap/orangepi/*` to:
   - `v5/topology/object-modules/orangepi/templates/bootstrap/*`
5. Add/adjust generator `template_root()` resolution for proxmox/orangepi/bootstrap generators to prefer object-local templates.
6. Update `v5/topology-tools/templates/TEMPLATE-INVENTORY.md`.

Exit criteria:

1. No object-specific templates are required from `v5/topology-tools/templates`.
2. Generator integration checks pass.

### Wave 2: Move Registration Ownership to Module Manifests

Changes:

1. Extend `v5/topology/object-modules/mikrotik/plugins.yaml` with generator entries.
2. Add `v5/topology/object-modules/proxmox/plugins.yaml` with proxmox generator entries.
3. Add `v5/topology/object-modules/orangepi/plugins.yaml` with orangepi generator entry.
4. Remove object-specific generator entries from:
   - `v5/topology-tools/plugins/plugins.yaml`
5. Keep plugin IDs stable (no renames), preserve ordering/dependency semantics.

Exit criteria:

1. `discover_plugin_manifests()` remains deterministic.
2. No duplicate plugin IDs (`E4001`).
3. Compile/generate uses module-owned generator registration only.

### Wave 3: Remove Compatibility Shims

Changes:

1. Remove shim files:
   - `v5/topology-tools/plugins/generators/terraform_mikrotik_generator.py`
   - `v5/topology-tools/plugins/generators/bootstrap_mikrotik_generator.py`
   - `v5/topology-tools/plugins/generators/terraform_proxmox_generator.py`
   - `v5/topology-tools/plugins/generators/bootstrap_proxmox_generator.py`
   - `v5/topology-tools/plugins/generators/bootstrap_orangepi_generator.py`
2. Update tests/imports that still reference shim modules.
3. Add guard check (test or CI grep) preventing reintroduction of object-specific shims.

Exit criteria:

1. No runtime/import dependency on shim modules.
2. Projection/template/publish contract tests pass without shims.

### Wave 4: Docs and Release Alignment

Changes:

1. Update:
   - `v5/topology-tools/docs/PLUGIN_AUTHORING.md`
   - `v5/topology-tools/docs/MANUAL-ARTIFACT-BUILD.md`
2. Update release checklists/guides with ADR0078 gates:
   - no object-specific entries in central generator manifest,
   - no object-specific templates under `topology-tools/templates`.
3. Regenerate lock:
   - `v5/projects/home-lab/framework.lock.yaml`

Exit criteria:

1. Docs reflect module-owned registration model.
2. Release preflight includes explicit ADR0078 verification.

### Wave 5: Projection Ownership Split

Goal:

1. Move object-specific projection builders out of:
   - `v5/topology-tools/plugins/generators/projections.py`

Changes:

1. Move object-specific projection builders to object-owned modules:
   - `v5/topology/object-modules/proxmox/plugins/projections.py`
   - `v5/topology/object-modules/mikrotik/plugins/projections.py`
   - `v5/topology/object-modules/_shared/plugins/bootstrap_projections.py`
2. Keep only shared/global projection builder(s) in:
   - `v5/topology-tools/plugins/generators/projections.py`
3. Add ownership guard checks so object-specific projection builders are not reintroduced in shared tools module.

Exit criteria:

1. Object generators resolve projection helpers from object-owned modules.
2. Shared `projections.py` contains only shared/global projection helpers.

---

## 5. Verification Matrix

Required after each wave batch:

1. `python -m pytest -o addopts= v5/tests/plugin_integration/test_terraform_mikrotik_generator.py -q`
2. `python -m pytest -o addopts= v5/tests/plugin_integration/test_terraform_proxmox_generator.py -q`
3. `python -m pytest -o addopts= v5/tests/plugin_integration/test_bootstrap_generators.py -q`
4. `python -m pytest -o addopts= v5/tests/plugin_integration/test_generator_projection_contract.py -q`
5. `python -m pytest -o addopts= v5/tests/plugin_integration/test_generator_template_and_publish_contract.py -q`
6. `python -m pytest -o addopts= v5/tests/plugin_integration/test_module_manifest_discovery.py -q`
7. `python -m pytest -o addopts= v5/tests/plugin_integration/test_strict_runtime_entrypoint_audit.py -q`
8. `python v5/topology-tools/compile-topology.py --topology v5/topology/topology.yaml --strict-model-lock --secrets-mode passthrough`

Release smoke gate (mandatory):

1. Build framework distribution zip.
2. Initialize a fresh project from distribution zip.
3. Run strict compile in that initialized project.

---

## 6. Risks and Controls

1. Risk: template not found after relocation.
   - Control: wave-local test matrix + inventory update in same commit.
2. Risk: manifest split introduces duplicate IDs/load regressions.
   - Control: manifest-discovery and duplicate-ID diagnostics checks.
3. Risk: hidden dependencies on shim modules.
   - Control: explicit shim-removal wave + anti-regression guard.
4. Risk: distribution/lock drift.
   - Control: lock regeneration + distribution smoke gate.

---

## 7. Rollback

If acceptance fails in any wave:

1. Restore prior manifest ownership in `v5/topology-tools/plugins/plugins.yaml`.
2. Restore shims for failed scope.
3. Restore prior template roots for affected generators.
4. Re-run full verification matrix before retry.

---

## 8. Definition of Done (ADR0078)

All must be true:

1. Object-specific generator code exists only in `object-modules/<object-id>/plugins`.
2. Object-specific templates exist only in `object-modules/<object-id>/templates`.
3. Object-specific registration is owned by module manifests.
4. Central `v5/topology-tools/plugins/plugins.yaml` contains only shared/global plugins.
5. Object-specific compatibility shims are removed.
6. Verification matrix and release smoke gate pass.

---

## 9. Compatibility Gate Evidence (2026-03-21)

Recorded one full local release cycle after shim removal:

1. Full v5 tests:
   - `python -m pytest -o addopts= v5/tests -q`
   - Result: `317 passed, 3 skipped`
2. Framework release preflight chain:
   - strict framework gates (`verify-framework-lock`, rollback rehearsal, compatibility matrix, strict runtime audit)
   - ADR0078 ownership contract (`v5/tests/plugin_contract/test_object_generator_ownership.py`)
   - v5 lane validate (`V5_SECRETS_MODE=passthrough python v5/scripts/orchestration/lane.py validate-v5`)
   - Result: PASS
3. Framework distribution build:
   - `python v5/topology-tools/build-framework-distribution.py --repo-root . --framework-manifest v5/topology/framework.yaml --output-root v5-dist/framework --version 1.0.8 --archive-format both`
   - Result: PASS (`infra-topology-framework-1.0.8.zip` / `.tar.gz`)
4. Zip bootstrap smoke:
   - `python v5/topology-tools/init-project-repo.py --output-root v5-build/adr0078-cycle-project --project-id adr0078-cycle --framework-dist-zip ...infra-topology-framework-1.0.8.zip --framework-dist-version 1.0.8 --framework-submodule-path framework --force`
   - Result: `Compile check: PASS`

Conclusion:

1. Compatibility gate objective ("one full release cycle without shim-origin failures") remains satisfied; Wave 5 applies ownership hardening on top.

---

## 10. Unified v5 Refactor Preparation (2026-03-22)

Preparation goal:

1. Start next v5 refactor cycle with explicit scope for compilers/validators/generators under common ADR0078 rules.

Prepared work packages:

1. **WP1: Unified inventory**
   - Build catalog of all active plugins by family and level (core/class/object/instance).
   - Mark ownership root and manifest owner for each plugin.
2. **WP2: Violation map**
   - Detect direct cross-level coupling and high-level leakage of object/instance specifics.
   - Mark global plugins that contain specific class/object semantics and require promotion/split.
3. **WP3: Interface extraction plan**
   - Define interface contracts where global plugins orchestrate specific plugins.
   - Replace direct concrete dependencies with contract-driven integration.
4. **WP4: Execution gates**
   - Keep `v5/tests/plugin_contract/test_plugin_level_boundaries.py` mandatory.
   - Keep `task test:parity-v4-v5` mandatory for affected domains.
   - Keep full `v5/tests/plugin_integration` and strict compile in each refactor batch.
5. **WP5: Anti-regression controls**
   - Add ownership and boundary checks to prevent reintroduction of violations during migration.

Ready-to-start sequence:

1. Finalize inventory + violation map.
2. Approve batch order (core -> class -> object -> instance).
3. Execute refactor in small batches with lock refresh and cutover-readiness evidence per batch.

---

## 11. Phase 6: Instance Isolation and Cross-Object Boundary Enforcement (2026-03-22)

**Goal:** Enforce strict boundaries identified during code analysis.

### Wave 6: Instance Literal Cleanup

**Problem:** Object-level generators contain hardcoded instance-specific data.

**Known violations:**

1. `v5/topology/object-modules/mikrotik/plugins/terraform_mikrotik_generator.py:64`:
   ```python
   mikrotik_host = "https://192.168.88.1:8443"
   ```

2. `v5/topology/object-modules/proxmox/plugins/terraform_proxmox_generator.py:65`:
   ```python
   proxmox_api_url = "https://proxmox.local:8006/api2/json"
   ```

**Changes:**

1. Refactor generators to derive API URLs from projection data:
   ```python
   # Before
   mikrotik_host = "https://192.168.88.1:8443"
   if routers:
       mikrotik_host = f"https://{routers[0]}:8443"

   # After
   def _resolve_api_url(self, projection: dict, ctx: PluginContext) -> str:
       """Derive API URL from projection or config."""
       if projection.get("routers"):
           host = projection["routers"][0]
       else:
           host = ctx.config.get("default_api_host", "${MIKROTIK_HOST}")
       port = ctx.config.get("api_port", 8443)
       return f"https://{host}:{port}"
   ```

2. Add `api_host` and `api_port` to plugin manifest config schema.

3. Create `v5/tests/plugin_contract/test_instance_literal_isolation.py`:
   ```python
   """Test that object-level plugins don't contain instance-specific literals."""

   import re
   from pathlib import Path

   # Patterns for instance-specific literals
   IP_PATTERN = re.compile(r'\b(?:192\.168|10\.0|172\.(?:1[6-9]|2\d|3[01]))\.\d{1,3}\.\d{1,3}\b')
   HOSTNAME_PATTERN = re.compile(r'\b[a-z][\w-]*\.(local|home|lan|internal)\b', re.I)

   def test_no_hardcoded_ips_in_object_generators():
       object_plugins = Path("v5/topology/object-modules").rglob("plugins/*.py")
       violations = []
       for plugin_file in object_plugins:
           if plugin_file.name.startswith("_"):
               continue
           content = plugin_file.read_text()
           for match in IP_PATTERN.finditer(content):
               violations.append(f"{plugin_file}:{match.group()}")
       assert not violations, f"Hardcoded IPs found: {violations}"

   def test_no_hardcoded_hostnames_in_object_generators():
       object_plugins = Path("v5/topology/object-modules").rglob("plugins/*.py")
       violations = []
       for plugin_file in object_plugins:
           if plugin_file.name.startswith("_"):
               continue
           content = plugin_file.read_text()
           for match in HOSTNAME_PATTERN.finditer(content):
               violations.append(f"{plugin_file}:{match.group()}")
       assert not violations, f"Hardcoded hostnames found: {violations}"
   ```

**Exit criteria:**

1. No hardcoded IPs in object-level generator code.
2. No hardcoded hostnames in object-level generator code.
3. `test_instance_literal_isolation.py` passes in CI.

---

### Wave 7: Cross-Object Import Prohibition

**Problem:** No enforcement prevents object modules from importing each other.

**Changes:**

1. Add test to `v5/tests/plugin_contract/test_plugin_level_boundaries.py`:
   ```python
   def test_object_modules_do_not_cross_import():
       """Verify object modules don't import from each other."""
       import ast
       from pathlib import Path

       object_modules_root = Path("v5/topology/object-modules")
       violations = []

       for obj_dir in object_modules_root.iterdir():
           if not obj_dir.is_dir() or obj_dir.name.startswith("_"):
               continue

           for py_file in (obj_dir / "plugins").rglob("*.py"):
               content = py_file.read_text()
               tree = ast.parse(content)

               for node in ast.walk(tree):
                   if isinstance(node, (ast.Import, ast.ImportFrom)):
                       module = getattr(node, "module", None) or ""
                       for alias in getattr(node, "names", []):
                           full_name = f"{module}.{alias.name}" if module else alias.name
                           # Check for cross-object imports
                           if "object_modules." in full_name or "object-modules/" in full_name:
                               for other_obj in object_modules_root.iterdir():
                                   if other_obj.name != obj_dir.name and other_obj.name in full_name:
                                       violations.append(
                                           f"{py_file}: imports from {other_obj.name}"
                                       )

       assert not violations, f"Cross-object imports found:\n" + "\n".join(violations)
   ```

2. Document allowed import patterns in `PLUGIN_AUTHORING.md`:
   - `from topology.object_modules._shared.plugins import ...` ✓
   - `from plugins.generators.base_generator import ...` ✓
   - `from topology.object_modules.proxmox.plugins import ...` ✗ (in mikrotik module)

**Exit criteria:**

1. No cross-object imports in any object module.
2. Test added to `test_plugin_level_boundaries.py`.
3. Documentation updated.

---

### Wave 8: Dynamic Object Discovery

**Problem:** `object_projection_loader.py` contains hardcoded object module paths.

**Known violation:**

```python
# v5/topology-tools/plugins/generators/object_projection_loader.py:14-18
OBJECT_PROJECTION_PATHS: dict[str, Path] = {
    "proxmox": OBJECT_MODULES_ROOT / "proxmox" / "plugins" / "projections.py",
    "mikrotik": OBJECT_MODULES_ROOT / "mikrotik" / "plugins" / "projections.py",
}
```

**Changes:**

1. Replace static dict with discovery function:
   ```python
   from functools import lru_cache
   from pathlib import Path

   OBJECT_MODULES_ROOT = Path(__file__).parent.parent.parent.parent / "topology" / "object-modules"

   @lru_cache(maxsize=1)
   def discover_object_projection_modules() -> dict[str, Path]:
       """Dynamically discover projection modules from filesystem."""
       result = {}
       for obj_dir in OBJECT_MODULES_ROOT.iterdir():
           if not obj_dir.is_dir():
               continue
           if obj_dir.name.startswith("_"):
               continue
           projection_path = obj_dir / "plugins" / "projections.py"
           if projection_path.exists():
               result[obj_dir.name] = projection_path
       return result

   def load_object_projection_module(object_id: str):
       """Load projection module for given object ID."""
       available = discover_object_projection_modules()
       if object_id not in available:
           raise ValueError(
               f"Unknown object_id '{object_id}'. "
               f"Available: {list(available.keys())}"
           )
       # ... rest of loading logic
   ```

2. Add test `v5/tests/plugin_contract/test_dynamic_object_discovery.py`:
   ```python
   def test_no_hardcoded_object_module_paths():
       """Verify framework code uses dynamic discovery."""
       from pathlib import Path

       loader_path = Path("v5/topology-tools/plugins/generators/object_projection_loader.py")
       content = loader_path.read_text()

       # Check for hardcoded object IDs
       assert "\"proxmox\":" not in content, "Hardcoded 'proxmox' mapping found"
       assert "\"mikrotik\":" not in content, "Hardcoded 'mikrotik' mapping found"

   def test_discovery_finds_all_modules():
       """Verify discovery finds all expected object modules."""
       from v5.topology_tools.plugins.generators.object_projection_loader import (
           discover_object_projection_modules
       )

       discovered = discover_object_projection_modules()
       expected = {"proxmox", "mikrotik"}  # Add new modules here

       assert expected.issubset(set(discovered.keys())), \
           f"Missing modules: {expected - set(discovered.keys())}"
   ```

**Exit criteria:**

1. `OBJECT_PROJECTION_PATHS` dict replaced with discovery function.
2. No hardcoded object IDs in loader code.
3. Discovery test passes.

---

### Wave 9: Capability-Template Externalization

**Problem:** Generators contain hardcoded capability-to-template mappings.

**Known violation:**

```python
# v5/topology/object-modules/mikrotik/plugins/terraform_mikrotik_generator.py:106-111
if has_qos:
    templates["qos.tf"] = "terraform/qos.tf.j2"
if has_wireguard:
    templates["vpn.tf"] = "terraform/vpn.tf.j2"
if has_containers:
    templates["containers.tf"] = "terraform/containers.tf.j2"
```

**Changes:**

1. Add capability mappings to `v5/topology/object-modules/mikrotik/plugins.yaml`:
   ```yaml
   generators:
     - id: obj_mikrotik.generator.terraform
       # ... existing config ...
       config:
         capability_templates:
           - capability: capabilities.qos
             template: terraform/qos.tf.j2
             output: qos.tf
           - capability: capabilities.wireguard
             template: terraform/vpn.tf.j2
             output: vpn.tf
           - capability: capabilities.containers
             template: terraform/containers.tf.j2
             output: containers.tf
   ```

2. Refactor generator to read from config:
   ```python
   def _get_capability_templates(
       self, projection: dict, ctx: PluginContext
   ) -> dict[str, str]:
       """Resolve templates based on projection capabilities and config."""
       templates = {}
       cap_configs = ctx.config.get("capability_templates", [])

       for cap_config in cap_configs:
           capability_path = cap_config["capability"]
           if self._check_capability(projection, capability_path):
               templates[cap_config["output"]] = cap_config["template"]

       return templates

   def _check_capability(self, projection: dict, capability_path: str) -> bool:
       """Check if capability is enabled in projection."""
       parts = capability_path.split(".")
       value = projection
       for part in parts:
           if isinstance(value, dict):
               value = value.get(part)
           else:
               return False
       return bool(value)
   ```

3. Add test `v5/tests/plugin_contract/test_capability_template_config.py`:
   ```python
   def test_generators_use_config_for_capability_templates():
       """Verify generators don't hardcode capability-template mappings."""
       from pathlib import Path
       import re

       # Pattern for hardcoded capability checks
       HARDCODED_PATTERN = re.compile(
           r'if\s+has_(qos|wireguard|containers|vpn):\s*\n\s*templates\[',
           re.MULTILINE
       )

       violations = []
       for gen_file in Path("v5/topology/object-modules").rglob("*_generator.py"):
           content = gen_file.read_text()
           if HARDCODED_PATTERN.search(content):
               violations.append(str(gen_file))

       assert not violations, f"Hardcoded capability templates in: {violations}"
   ```

**Exit criteria:**

1. Capability-template mappings moved to plugin config.
2. Generators read mappings from config.
3. No hardcoded `if has_*:` patterns in generator code.
4. Config schema validates capability mappings.

---

## 12. Verification Matrix (Phase 6-7)

Required after each wave:

1. Instance isolation:
   - `python -m pytest v5/tests/plugin_contract/test_instance_literal_isolation.py -q`

2. Cross-object import:
   - `python -m pytest v5/tests/plugin_contract/test_plugin_level_boundaries.py::test_object_modules_do_not_cross_import -q`

3. Dynamic discovery:
   - `python -m pytest v5/tests/plugin_contract/test_dynamic_object_discovery.py -q`

4. Capability templates:
   - `python -m pytest v5/tests/plugin_contract/test_capability_template_config.py -q`

5. Full plugin contract suite:
   - `python -m pytest v5/tests/plugin_contract -q`

6. Regression check:
   - `python -m pytest v5/tests/plugin_integration -q`
   - `python v5/topology-tools/compile-topology.py --topology v5/topology/topology.yaml --strict-model-lock --secrets-mode passthrough`

---

## 13. Risks and Controls (Phase 6-7)

1. Risk: refactoring breaks existing generator output.
   - Control: snapshot tests for generated artifacts.
   - Control: run full parity suite before/after each wave.

2. Risk: dynamic discovery misses new modules.
   - Control: explicit test for expected module set.
   - Control: CI failure on discovery mismatch.

3. Risk: config schema changes break existing manifests.
   - Control: backwards-compatible schema evolution.
   - Control: validate all manifests in CI.

4. Risk: regex patterns have false positives.
   - Control: explicit allowlist for legitimate patterns.
   - Control: review flagged patterns manually.

---

## 14. Definition of Done (Phase 6-7)

All must be true:

1. No hardcoded IPs or hostnames in object-level generators.
2. No cross-object imports in object modules.
3. Object module discovery is fully dynamic.
4. Capability-template mappings are in config, not code.
5. All new tests pass in CI.
6. Full regression suite passes.
7. Framework lock regenerated and validated.
