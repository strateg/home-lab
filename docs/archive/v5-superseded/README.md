# V5 Superseded Documentation

**Archived:** 2026-04-01
**Reason:** Documentation superseded by v5 architecture and ADR 0072/0083/0084/0085

---

## Archived Files

| File | Superseded By | Notes |
|------|---------------|-------|
| `ANSIBLE-VAULT-GUIDE.md` | ADR 0072, `docs/secrets-management.md` | v5 uses SOPS+age instead of Ansible Vault |
| `DEPLOYMENT-STRATEGY.md` | ADR 0085, `docs/guides/DEPLOY-BUNDLE-WORKFLOW.md` | v5 uses bundle-based deploy instead of dist/ phases |
| `DEVELOPERS_GUIDE_GENERATORS.md` | ADR 0074, `docs/PLUGIN_AUTHORING_GUIDE.md` | v5 uses plugin architecture instead of script-based generators |
| `CHANGELOG-GENERATED-DIR.md` | Historical | Documents v4 generated/ structure changes |

---

## Migration References

### Secrets Management (ADR 0072)

**Old:** Ansible Vault with `ansible/group_vars/all/vault.yml`
**New:** SOPS+age with `projects/<project>/secrets/`

See: `docs/secrets-management.md`

### Deploy Workflow (ADR 0085)

**Old:** `dist/` packages with shell-script phases
**New:** Immutable deploy bundles at `.work/deploy/bundles/<bundle_id>/`

See: `docs/guides/DEPLOY-BUNDLE-WORKFLOW.md`

### Generator Architecture (ADR 0074)

**Old:** Script-based generators in `topology-tools/scripts/generators/`
**New:** Plugin-based generators in `topology-tools/plugins/generators/`

See: `docs/PLUGIN_AUTHORING_GUIDE.md`

---

## Historical Context

These documents describe the v4 architecture patterns that were replaced during the v5 migration:

- v4 used Ansible Vault for secrets → v5 uses SOPS+age
- v4 used `dist/` deploy packages → v5 uses immutable bundles
- v4 used script generators → v5 uses plugin microkernel
- v4 used flat topology layers → v5 uses Class-Object-Instance hierarchy
