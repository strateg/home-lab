# Framework 5.0.0 — Operator Handoff (Publish + Post-Migration Actions)

- Status: **PUBLISHED 2026-07-05** (agent key unlock by operator; pushes executed from session).
  Remaining: verify CI release assets (§3.3), WireGuard key rotation (§3.5).
- Date: 2026-07-05
- Owner/Approver: Dmitri (strateg, single-operator per ADR 0090)
- Related: ADR 0075, ADR 0076, ADR 0081; `adr/plan/v5-production-readiness.md` (Phase 13);
  migration close commit `feb29698` on `development`

## 1. What is already done (no action needed)

| Item | Evidence |
|------|----------|
| v4→v5 migration closed | commit `feb29698` (789 files, archive/v4 + `_legacy` + phase1 tooling removed) |
| v4 baseline preserved | local branch `archive/v4-baseline` |
| Release channel promoted | `topology/framework.yaml` `framework_release_channel: stable` |
| Release preflight | PASS (strict + lock refresh + 475 release tests + validate:passthrough) |
| Dist archives built + verified | `dist/framework/infra-topology-framework/5.0.0/` (491 files, ADR 0081 boundary check ok) |
| Bootstrap candidate finalized | `build/infra-topology-framework-bootstrap/` @ `49da72cb`, annotated tag `v5.0.0`, `origin` → `git@github.com:strateg/infra-topology-framework.git`, clean tree |
| Full validation | lane validate-v5 PASS, test-lab compile errors=0, split-rehearsal 5/5 rc=0, pytest 1631 passed |

Dist checksums (sha256):

```
5d02cdbe9462c36cdb5162cacde70eb7e8e35a40e5ede308b54bc75db013c540  infra-topology-framework-5.0.0.zip
88eb7c54affe4dca14a50089315b7249bca97b9e87b90caf572dca4a38ae6ebd  infra-topology-framework-5.0.0.tar.gz
```

## 2. Why publish is blocked from the build environment

- Both SSH keys (`~/.ssh/id_ed25519`, `~/.ssh/atb9admin_github`) are passphrase-protected;
  no ssh-agent running; non-interactive session cannot unlock them.
- `gh` CLI is not installed.
- `strateg/infra-topology-framework` is private (anonymous HTTPS read denied).

Everything below requires an interactive terminal on this machine.

## 3. Operator steps

### 3.1 Unlock SSH key

```bash
eval "$(ssh-agent -s)"
ssh-add ~/.ssh/id_ed25519        # or ~/.ssh/atb9admin_github
ssh -T git@github.com            # expect: "Hi <user>! ..."
```

### 3.2 Push bootstrap candidate + tag v5.0.0

The candidate preserves full home-lab history (`preserve_history: true`); the existing
`strateg/infra-topology-framework` (currently v1.0.7) has diverged history from the previous
extraction, so a plain push will be rejected as non-fast-forward.

Option A — replace history (artifact-first per ADR 0081, recommended):

```bash
cd ~/workspaces/home-lab/build/infra-topology-framework-bootstrap
git push --force-with-lease origin development
git push origin v5.0.0
# If the repo default branch is main:
#   git push --force-with-lease origin development:main
```

Option B — review before replacing:

```bash
git push origin development:release/5.0.0-candidate
git push origin v5.0.0
# inspect on GitHub, then fast-forward/replace the default branch manually
```

### 3.3 Create GitHub release with dist assets

Via `gh` (after `gh auth login`), from home-lab root:

```bash
gh release create v5.0.0 \
  --repo strateg/infra-topology-framework \
  --title "infra-topology-framework 5.0.0" \
  --notes "First stable v5 release. See framework-dist-manifest.json for contents." \
  dist/framework/infra-topology-framework/5.0.0/infra-topology-framework-5.0.0.tar.gz \
  dist/framework/infra-topology-framework/5.0.0/infra-topology-framework-5.0.0.zip \
  dist/framework/infra-topology-framework/5.0.0/checksums.sha256 \
  dist/framework/infra-topology-framework/5.0.0/framework-dist-manifest.json
```

Or via web UI: Releases → Draft new release → tag `v5.0.0` → upload the same 4 files.

### 3.4 Push home-lab branches

```bash
cd ~/workspaces/home-lab
git push origin development            # migration close (feb29698) + this handoff
git push origin archive/v4-baseline    # optional: remote preservation of v4 baseline
```

### 3.5 Rotate the compromised WireGuard keypair (SECURITY)

The WireGuard private key was committed under `archive/v4/` and remains in git history and
on branch `archive/v4-baseline`. Treat it as compromised regardless of publish decisions.

```bash
wg genkey | tee privatekey | wg pubkey > publickey   # on the affected host
```

Then: update the peer config on every device using the old public key, deploy, and confirm
handshakes before revoking the old key. Do NOT commit the new private key; store it in the
secrets flow (SOPS/age), never in the topology tree.

## 4. Done criteria

- [x] `git ls-remote --tags git@github.com:strateg/infra-topology-framework.git` shows `v5.0.0`
      (2026-07-05: tag `8bb0c168` → commit `49da72cb`)
- [ ] GitHub release `v5.0.0` exists with assets — CI workflow `Framework Release` triggered by
      tag push (contents:write); verify in Actions, upload local dist as fallback if run failed
- [x] Extracted repo default branch contains `49da72cb` — `main` replaced via
      `--force-with-lease` (f77867d8 → 49da72cb), `development` pushed alongside (2026-07-05)
- [x] `origin/archive/v4-baseline` exists (= `01b9f9ca`, home-lab `development` = `1e35baf1`)
- [ ] Old WireGuard public key removed from all peers; new handshakes verified
