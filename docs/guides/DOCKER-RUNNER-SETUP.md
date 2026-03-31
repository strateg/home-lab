# Docker Runner Setup

**Status:** Active
**Updated:** 2026-03-31
**Scope:** ADR 0084 Docker deploy runner hardening follow-up

---

## 1. Build Toolchain Image

Default image tag in deploy profile:

`homelab-toolchain:latest`

Build locally:

```powershell
task framework:deploy-docker-toolchain-build
```

Build with explicit tag:

```powershell
task framework:deploy-docker-toolchain-build -- DOCKER_IMAGE=homelab-toolchain:dev
```

---

## 2. Smoke Check

Validate core tools inside the image:

```powershell
task framework:deploy-docker-toolchain-smoke
```

This checks:

- `terraform version`
- `ansible-playbook --version`

---

## 3. Enable Docker Runner

Set runner in profile:

`projects/home-lab/deploy/deploy-profile.yaml`

```yaml
default_runner: docker
runners:
  docker:
    image: homelab-toolchain:latest
    network: host
```

Or override per command:

```powershell
task framework:service-chain-evidence-dry-bundle -- BUNDLE=<bundle_id> DEPLOY_RUNNER=docker
```

---

## 4. Notes

- Docker runner mounts the selected bundle into container workspace `/workspace`.
- Runner execution is immutable-bundle based; no direct `generated/` execution path.
- For network-restricted environments, switch Docker network mode in deploy profile.
- If `docker run` fails with `invalid rootfs` on Docker Desktop Linux engine, remove Windows-style `data-root` from `%USERPROFILE%\\.docker\\daemon.json`, restart Docker Desktop, and verify `docker info` shows `Docker Root Dir: /var/lib/docker`.
