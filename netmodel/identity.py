"""Identity and inheritance for embedded records.

Attachments, publications and bindings are named mappings, not lists. The name is
the identity: a record does not repeat it in an `id` field, and two records with
the same name are the same record at different levels of Class -> Object ->
Instance, never two records.

That choice is not cosmetic. Merging lists by position or by a nested `id` needs
an algorithm nobody has written and a delete semantics nobody has agreed; merging
mappings by key is what the repository's inheritance already does. The rules below
are the ones the accepted model states, expressed so they can be tested rather
than remembered:

* nested mappings merge, so an object supplies shape and an instance supplies
  placement;
* a list of values replaces as a whole, because a selector list that silently
  grew by inheritance would widen access without anyone writing the widening;
* dropping an override restores what was inherited, which means absence and an
  explicit null are different things;
* `enabled: false` disables an inherited record without deleting it, so a
  dangling reference to it is an error rather than silence;
* renaming a key is a delete and a create, so nothing about the old record -
  its address, its approval - transfers to the new one by accident.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Iterable, Mapping

# Baseline local-key grammar: no dot, no hyphen, no @. Dots would make a
# reference path ambiguous, and @ belongs to the semantic metadata namespace.
# Existing instance identifiers are a different namespace and keep their hyphens.
LOCAL_KEY_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")

# Absent and null are different inputs and must stay distinguishable, so a
# sentinel is needed: None is a legitimate authored value meaning "explicitly
# nothing", not "not mentioned".
_ABSENT = object()


class IdentityError(ValueError):
    """Raised when a record identity or an inheritance operation is invalid."""


@dataclass(frozen=True, slots=True)
class RecordIdentity:
    """What makes one embedded record distinct from every other.

    Scope is explicit rather than encoded in a dotted string. `docker-adguard.dns`
    cannot be split back into owner and key without guessing where the boundary
    is, and instance identifiers contain both dots and hyphens.
    """

    project: str
    owner: str
    kind: str
    local_key: str

    def __post_init__(self) -> None:
        for field_name in ("project", "owner", "kind"):
            if not str(getattr(self, field_name) or "").strip():
                raise IdentityError(f"record identity requires a non-empty {field_name}")
        validate_local_key(self.local_key)

    @property
    def reference(self) -> tuple[str, str, str, str]:
        """A comparable form that never needs parsing."""
        return (self.project, self.owner, self.kind, self.local_key)


def validate_local_key(key: str) -> str:
    if not isinstance(key, str) or not LOCAL_KEY_RE.match(key):
        raise IdentityError(f"invalid local key {key!r}: expected {LOCAL_KEY_RE.pattern}, " "without dot, hyphen or @")
    return key


def validate_collection_keys(collection: Mapping[str, Any]) -> None:
    """Every key in an authored collection must be a valid local key."""
    for key in collection:
        validate_local_key(key)


def merge_inherited(base: Any, override: Any) -> Any:
    """Apply one level of Class -> Object -> Instance inheritance.

    Mappings merge key by key; everything else, lists included, replaces.
    """
    if isinstance(base, Mapping) and isinstance(override, Mapping):
        merged = dict(base)
        for key, value in override.items():
            merged[key] = merge_inherited(merged.get(key, _ABSENT), value) if key in merged else value
        return merged
    if base is _ABSENT:
        return override
    return override


def merge_collection(
    base: Mapping[str, Any] | None,
    override: Mapping[str, Any] | None,
) -> dict[str, Any]:
    """Merge two named collections of records.

    A key present in both merges. A key present only in the override is a new
    record. A key present only in the base is inherited unchanged: an instance
    that says nothing about a record keeps it.
    """
    base = base or {}
    override = override or {}
    validate_collection_keys(base)
    validate_collection_keys(override)

    merged: dict[str, Any] = {key: dict(value) if isinstance(value, Mapping) else value for key, value in base.items()}
    for key, value in override.items():
        if key in merged and isinstance(merged[key], Mapping) and isinstance(value, Mapping):
            merged[key] = merge_inherited(merged[key], value)
        else:
            merged[key] = dict(value) if isinstance(value, Mapping) else value
    return merged


def is_enabled(record: Mapping[str, Any]) -> bool:
    """A record is active unless it says otherwise.

    Only an explicit `false` disables. A null does not: null is not a shorthand
    for off, for deletion or for restoring a default.
    """
    value = record.get("enabled", True)
    if value is None:
        raise IdentityError("`enabled: null` is not a value; use true, false, or omit the key")
    if not isinstance(value, bool):
        raise IdentityError(f"`enabled` must be a boolean, got {value!r}")
    return value


def active_records(collection: Mapping[str, Any]) -> dict[str, Any]:
    """Records that participate in desired intent.

    A disabled record is excluded here but still exists, which is what makes a
    reference to it an error rather than a silent miss.
    """
    return {key: value for key, value in collection.items() if isinstance(value, Mapping) and is_enabled(value)}


def resolve_reference(collection: Mapping[str, Any], local_key: str) -> Mapping[str, Any]:
    """Resolve a reference to a record, refusing missing and disabled alike."""
    validate_local_key(local_key)
    record = collection.get(local_key)
    if record is None:
        raise IdentityError(f"reference to unknown record {local_key!r}")
    if not isinstance(record, Mapping):
        raise IdentityError(f"record {local_key!r} is not a mapping")
    if not is_enabled(record):
        raise IdentityError(f"reference to disabled record {local_key!r}")
    return record


def rejected_derived_overrides(record: Mapping[str, Any], derived_fields: Iterable[str]) -> list[str]:
    """Derived fields an author must not restate on a consumer record."""
    return sorted(field for field in derived_fields if field in record)
