"""Shared content and file policy helpers for deploy assembly scripts."""

from __future__ import annotations

from fnmatch import fnmatch
from pathlib import Path

SECRET_CONTENT_PATTERNS = [
    "password:",
    "token:",
    "private_key:",
    "root_password_hash:",
    "lookup('file'",
    'lookup("file',
    "vault_pass",
]

FORBIDDEN_TOPOLOGY_OVERRIDE_PATTERNS = [
    "ansible_user:",
    "ansible_host:",
    "vmid:",
    "service_port:",
    "cores:",
    "memory_mb:",
]

LOCAL_SECRET_PATH_PATTERNS = [
    ".terraform",
    ".terraform/*",
    ".vault_pass",
    "*.pem",
    "*.key",
    "id_rsa",
    "id_ed25519",
    "terraform.tfvars",
    "terraform.tfstate",
    "terraform.tfstate.*",
    "answer.toml",
]


def validate_file_does_not_contain_patterns(
    path: Path,
    forbidden_patterns: list[str],
    violation_label: str,
) -> list[str]:
    """Check file content for forbidden patterns and return violations."""
    if not path.exists():
        return []

    violations = []
    content = path.read_text()
    for pattern in forbidden_patterns:
        if pattern in content:
            violations.append(f"{path}: contains {violation_label} pattern '{pattern}'")
    return violations


def validate_no_secret_content(path: Path) -> list[str]:
    """Check tracked file content for secret-like patterns."""
    return validate_file_does_not_contain_patterns(
        path=path,
        forbidden_patterns=SECRET_CONTENT_PATTERNS,
        violation_label="secret",
    )


def validate_no_forbidden_topology_overrides(path: Path, allowlist: list[str] | None = None) -> list[str]:
    """Check host_vars for forbidden topology-owned fact overrides."""
    if not path.exists():
        return []

    allowlist = allowlist or []
    if path.name in allowlist:
        return []

    return validate_file_does_not_contain_patterns(
        path=path,
        forbidden_patterns=FORBIDDEN_TOPOLOGY_OVERRIDE_PATTERNS,
        violation_label="topology-owned fact override",
    )


def is_local_secret_path(path: Path) -> bool:
    """Return True if path matches a local-secret file pattern."""
    candidates = {path.name, path.as_posix()}
    for pattern in LOCAL_SECRET_PATH_PATTERNS:
        if any(fnmatch(candidate, pattern) for candidate in candidates):
            return True
    return False


def find_local_secret_paths(root: Path) -> list[Path]:
    """Return local-secret path violations under a directory tree."""
    violations: list[Path] = []
    if not root.exists():
        return violations

    for path in sorted(root.rglob("*")):
        if is_local_secret_path(path.relative_to(root)):
            violations.append(path)
    return violations


def validate_release_safe_tree(root: Path) -> list[str]:
    """Validate that a tree does not contain local-secret path violations."""
    return [f"{path}: matches local-secret path policy" for path in find_local_secret_paths(root)]
