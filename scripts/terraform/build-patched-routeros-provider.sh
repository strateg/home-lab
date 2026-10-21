#!/usr/bin/env bash
# Build terraform-provider-routeros from the pinned upstream release plus the
# tracked patches in configs/terraform/patches/, and publish it into a local
# filesystem mirror that Terraform can install from.
#
# WHY THIS EXISTS (ADR 0120)
#
# On RouterOS >= 7.21 the released provider cannot update any
# routeros_ip_address at all: RouterOS assigns VRF membership per interface, so
# `vrf` on an address row is derived and its SET endpoint has no such
# parameter, while the provider declares `vrf` writable and sends it on every
# PATCH. RouterOS answers 400 `unknown parameter vrf`. Upstream issue #944 is
# open, the fix (PR #984) is open and unreleased, and upstream's newest tag is
# the version we pin. So the choice was: leave a whole resource type
# unmanageable, trust a fork's binary, or build the upstream release with the
# upstream patch ourselves and keep the recipe in the repository.
#
# This is the third. Everything that decides the output is tracked: the pinned
# tag, its expected commit, the patch files, and the mirror layout. The binary
# itself is not - it lands in .work/ and is rebuilt by running this script.
#
# USAGE
#   scripts/terraform/build-patched-routeros-provider.sh            # build + publish
#   scripts/terraform/build-patched-routeros-provider.sh --verify   # check an existing build
#
# Then, in the Terraform workspace:
#   export TF_CLI_CONFIG_FILE="$REPO/.work/providers/terraform.rc"
#   terraform init -upgrade      # records our build's hash in .terraform.lock.hcl
#
# TO GO BACK to the registry build: unset TF_CLI_CONFIG_FILE, delete the
# provider's entry from .terraform.lock.hcl, and run `terraform init -upgrade`.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
PROVIDER_NAMESPACE="terraform-routeros"
PROVIDER_TYPE="routeros"
# The pinned upstream release. Keep in step with the constraint the generated
# provider.tf renders; bump both together, deliberately.
UPSTREAM_TAG="v1.99.1"
# `git rev-parse v1.99.1^{commit}` at the time this script was written. A tag
# can be moved; a commit cannot, so the build refuses a surprise.
UPSTREAM_COMMIT="492725d"
PROVIDER_VERSION="${UPSTREAM_TAG#v}"
# Delete the patch and this script when upstream ships a release above this.
FIX_EXPECTED_IN="a release above ${PROVIDER_VERSION} that contains PR #984"

PATCH_DIR="${REPO_ROOT}/configs/terraform/patches"
WORK_DIR="${REPO_ROOT}/.work/providers"
SRC_DIR="${WORK_DIR}/src"
MIRROR_DIR="${WORK_DIR}/mirror"
CLI_CONFIG="${WORK_DIR}/terraform.rc"

log() { printf '[provider-build] %s\n' "$*"; }
die() { printf '[provider-build] ERROR: %s\n' "$*" >&2; exit 1; }

platform() {
  local os arch
  os="$(go env GOOS)"
  arch="$(go env GOARCH)"
  printf '%s_%s' "$os" "$arch"
}

target_binary() {
  printf '%s/registry.terraform.io/%s/%s/%s/%s/terraform-provider-%s_v%s' \
    "$MIRROR_DIR" "$PROVIDER_NAMESPACE" "$PROVIDER_TYPE" "$PROVIDER_VERSION" \
    "$(platform)" "$PROVIDER_TYPE" "$PROVIDER_VERSION"
}

verify() {
  local binary
  binary="$(target_binary)"
  [[ -x "$binary" ]] || die "no build at ${binary} - run this script without --verify"
  log "binary:   ${binary}"
  log "size:     $(stat -c %s "$binary") bytes"
  log "sha256:   $(sha256sum "$binary" | cut -d' ' -f1)"
  # The patch is only useful if it is actually in the binary. `vrf` must no
  # longer be settable on ip_address, and this is the cheapest honest check
  # short of running Terraform: the Computed-only schema has no DiffSuppressFunc
  # reference for that key.
  if ! grep -q "PropVrfRo" "${SRC_DIR}/routeros/resource_ip_address.go" 2>/dev/null; then
    die "source tree at ${SRC_DIR} does not carry the patch; the binary may be unpatched"
  fi
  log "source carries the patch (PropVrfRo wired into resource_ip_address.go)"
  log "fix upstream in: ${FIX_EXPECTED_IN}"
}

if [[ "${1:-}" == "--verify" ]]; then
  verify
  exit 0
fi

command -v go >/dev/null || die "go toolchain not found"
command -v git >/dev/null || die "git not found"
[[ -d "$PATCH_DIR" ]] || die "patch directory missing: ${PATCH_DIR}"

log "upstream ${PROVIDER_NAMESPACE}/${PROVIDER_TYPE} ${UPSTREAM_TAG} -> ${MIRROR_DIR}"
rm -rf "$SRC_DIR"
mkdir -p "$SRC_DIR" "$MIRROR_DIR"

log "cloning ${UPSTREAM_TAG}"
git clone --quiet --depth 1 --branch "$UPSTREAM_TAG" \
  "https://github.com/${PROVIDER_NAMESPACE}/terraform-provider-${PROVIDER_TYPE}.git" "$SRC_DIR"

actual_commit="$(git -C "$SRC_DIR" rev-parse --short HEAD)"
[[ "$actual_commit" == "$UPSTREAM_COMMIT" ]] || \
  die "tag ${UPSTREAM_TAG} resolves to ${actual_commit}, expected ${UPSTREAM_COMMIT}. A moved tag is not a build input - investigate before trusting it."
log "commit:   ${actual_commit} (as pinned)"

shopt -s nullglob
patches=("${PATCH_DIR}"/routeros-"${PROVIDER_VERSION}"-*.patch)
shopt -u nullglob
[[ ${#patches[@]} -gt 0 ]] || die "no patches for ${PROVIDER_VERSION} in ${PATCH_DIR}"

for patch in "${patches[@]}"; do
  log "applying $(basename "$patch") (sha256 $(sha256sum "$patch" | cut -c1-12))"
  git -C "$SRC_DIR" apply --verbose "$patch" 2>&1 | sed 's/^/[provider-build]   /'
done

# The patch has to have landed where it matters, or a green build would ship an
# unpatched provider under a patched name.
grep -q 'KeyVrf: PropVrfRo' "${SRC_DIR}/routeros/resource_ip_address.go" || \
  die "post-patch check failed: ip_address still does not use PropVrfRo"
grep -q 'PropVrfRo = &schema.Schema' "${SRC_DIR}/routeros/provider_schema_helpers.go" || \
  die "post-patch check failed: PropVrfRo is not declared"
log "post-patch checks pass"

log "building (go $(go env GOVERSION), $(platform))"
binary="$(target_binary)"
mkdir -p "$(dirname "$binary")"
( cd "$SRC_DIR" && CGO_ENABLED=0 go build -trimpath -ldflags="-s -w" -o "$binary" . )
chmod +x "$binary"

cat > "$CLI_CONFIG" <<EOF
# Generated by scripts/terraform/build-patched-routeros-provider.sh
#
# Point Terraform at the locally built ${PROVIDER_NAMESPACE}/${PROVIDER_TYPE}
# ${PROVIDER_VERSION} (upstream release + configs/terraform/patches/). Every
# other provider still comes from the registry.
#
#   export TF_CLI_CONFIG_FILE="${CLI_CONFIG}"
#   terraform init -upgrade
provider_installation {
  filesystem_mirror {
    path    = "${MIRROR_DIR}"
    include = ["registry.terraform.io/${PROVIDER_NAMESPACE}/${PROVIDER_TYPE}"]
  }
  direct {
    exclude = ["registry.terraform.io/${PROVIDER_NAMESPACE}/${PROVIDER_TYPE}"]
  }
}
EOF

verify
log "cli config: ${CLI_CONFIG}"
log "next: export TF_CLI_CONFIG_FILE=\"${CLI_CONFIG}\" && terraform init -upgrade"
