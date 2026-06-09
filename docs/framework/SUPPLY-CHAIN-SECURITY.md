# Supply Chain Security Guide

**Status:** Active
**Updated:** 2026-06-09
**ADRs:** 0076, 0081

---

## Overview

The framework implements supply chain security through:

1. **Integrity verification** — SHA-256 hash of framework files
2. **Signature verification** — Cosign/Sigstore integration
3. **Provenance attestation** — SLSA-compatible provenance
4. **SBOM** — Software Bill of Materials (SPDX format)

---

## Security Model by Source Type

| Source | Integrity | Signature | Provenance | SBOM |
|--------|-----------|-----------|------------|------|
| `git` | SHA-256 | N/A | N/A | N/A |
| `package` | SHA-256 | Cosign | SLSA | SPDX |

- **git source**: Used in monorepo/submodule mode. Only integrity hash is verified.
- **package source**: Used when framework is distributed as zip/tarball. Full trust chain required.

---

## Verification Levels

### Level 1: Basic Integrity (Default)

```bash
task framework:verify-lock
# or
python topology-tools/verify-framework-lock.py --strict
```

Verifies:
- Lock file exists and is valid YAML
- Framework version compatibility
- SHA-256 integrity hash matches computed hash

### Level 2: Package Trust Metadata

```bash
task framework:verify-lock-package-trust
# or
python topology-tools/verify-framework-lock.py --strict --enforce-package-trust
```

Additional checks (for `source=package`):
- `framework.signature` mapping present
- `provenance` mapping present
- `sbom` mapping present
- No placeholder values in trust fields

### Level 3: Artifact File Verification

```bash
task framework:verify-lock-package-trust-artifacts
# or
python topology-tools/verify-framework-lock.py --strict --enforce-package-trust --verify-package-artifact-files
```

Additional checks:
- Trust artifact files exist on disk
- SHA-256 digests match declared values

### Level 4: Cryptographic Signature Verification

```bash
task framework:verify-lock-package-trust-signature
# or
python topology-tools/verify-framework-lock.py --strict --enforce-package-trust \
  --verify-package-artifact-files --verify-package-signature
```

Additional checks:
- Cosign `verify-blob` succeeds
- Certificate and signature are valid

---

## Error Codes

| Code | Severity | Description |
|------|----------|-------------|
| E7821 | error | Framework dependency not resolvable |
| E7822 | error | Framework lock missing in strict mode |
| E7823 | error | Lock revision mismatch |
| E7824 | error | Integrity hash mismatch |
| E7825 | error | Signature verification failed |
| E7826 | error | Provenance verification failed |
| E7827 | error | Lock contract violation |
| E7828 | error | SBOM missing |

---

## Release Artifacts

A compliant framework release includes:

```
dist/framework/<framework-id>/<version>/
├── infra-topology-framework-<version>.zip
├── infra-topology-framework-<version>.tar.gz
├── checksums.sha256           # SHA-256 digests
├── checksums.sha256.sig       # Cosign signature
├── checksums.sha256.crt       # Signing certificate
├── framework-dist-manifest.json
├── sbom.spdx.json             # SPDX SBOM
└── provenance/
    └── provenance.json        # SLSA provenance
```

---

## CI/CD Integration

### Release Workflow

See `docs/framework/templates/framework-release.yml`:

1. Build distribution artifacts
2. Generate SBOM
3. Generate provenance attestation
4. Sign checksums with Cosign
5. Verify package trust contract
6. Publish to GitHub Releases

### Consumer Workflow

When consuming a package release:

```bash
# Generate lock with package source
python topology-tools/generate-framework-lock.py \
  --source package \
  --package-trust-release-root ./release-artifacts \
  --force

# Verify full trust chain
python topology-tools/verify-framework-lock.py \
  --strict \
  --enforce-package-trust \
  --verify-package-artifact-files \
  --verify-package-signature
```

---

## Quick Reference

| Task | Description |
|------|-------------|
| `framework:verify-lock` | Basic integrity verification |
| `framework:verify-lock-package-trust` | + Trust metadata enforcement |
| `framework:verify-lock-package-trust-artifacts` | + Artifact file verification |
| `framework:verify-lock-package-trust-signature` | + Cosign signature verification |
| `framework:package-trust-gate` | Run package trust test suite |

---

## Troubleshooting

### E7824: Integrity Mismatch

Framework files changed since lock was generated.

```bash
# Dev mode: auto-regenerate
task build:compile-dev

# Manual regeneration
task framework:lock-refresh-all
```

### E7825: Signature Verification Failed

Cosign verification failed. Check:

1. Cosign is installed: `cosign version`
2. Certificate and signature files exist
3. Signature matches the signed blob

### E7826: Provenance Missing

Package source requires provenance attestation.

1. Verify provenance.json exists in release artifacts
2. Check provenance.uri and provenance.sha256 in lock

---

## Related Documents

- `docs/framework/FRAMEWORK-RELEASE-GUIDE.md`
- `docs/framework/OPERATOR-WORKFLOWS.md`
- `adr/0076-framework-distribution-and-multi-repository-extraction.md`
