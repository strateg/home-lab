"""Reference implementation of the ADR 0118/0119 target network model.

Development package. Nothing here runs in the compile pipeline, renders an
artifact or touches a device. Evidence produced by this package is
`offline-validated` and never upgrades itself to `backend-tested`.
"""

from __future__ import annotations

__all__ = ["domains", "snapshot"]
