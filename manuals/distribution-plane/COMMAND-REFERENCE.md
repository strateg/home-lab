# Distribution Plane Command Reference

Быстрая справка по командам distribution-plane.

---

## Release / Build

```bash
# Preflight (lock refresh + strict + validate + release tests)
task framework:release-preflight

# Build distribution archive
task framework:release-build FRAMEWORK_VERSION=5.0.0-rc1

# Full release candidate bundle
task framework:release-candidate FRAMEWORK_VERSION=5.0.0-rc1
```

---

## Trust Verification

```bash
# Strict lock verification (package trust enforced)
task framework:verify-lock-package-trust-signature

# Verify package trust artifacts and sha256
task framework:verify-lock-package-trust-artifacts
```

---

## Project Bootstrap (Artifact-First)

```bash
# New standalone project from distribution zip
task project:init-from-dist -- \
  PROJECT_ROOT=build/project-bootstrap/home-lab \
  PROJECT_ID=home-lab \
  FRAMEWORK_DIST_ZIP=dist/framework/infra-topology-framework-5.0.0-rc1.zip \
  FRAMEWORK_DIST_VERSION=5.0.0-rc1
```

---

## Project Upgrade (Distribution Update)

```bash
# Regenerate framework.lock for new dist version
.venv/bin/python topology-tools/generate-framework-lock.py \
  --topology topology/topology.yaml \
  --project-root . \
  --framework-dist-zip dist/framework/infra-topology-framework-5.0.0-rc2.zip \
  --framework-dist-version 5.0.0-rc2

# Verify lock and trust metadata
.venv/bin/python topology-tools/verify-framework-lock.py --strict
.venv/bin/python topology-tools/verify-framework-lock.py --strict --enforce-package-trust --verify-package-artifact-files --verify-package-signature
```

---

## Cutover Evidence

```bash
# Evidence bundle and GO/NO-GO
task framework:cutover-evidence
task framework:cutover-go-no-go
```

---

## Product Task Surface (SOHO)

```bash
task product:init

task product:doctor

task product:plan

task product:apply BUNDLE=<bundle_id> ALLOW_APPLY=YES

task product:backup

task product:restore

task product:handover
```
