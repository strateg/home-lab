"""A writer that exists only to prove the admission boundary stops a write.

The pipeline test used to assert that two directories did not exist after
running a compiler and a validator. No generator ran, so it passed whether or
not any control over writing existed - which the 2026-09-14 review recorded as
S3: "потенциальный writer вообще не выполняется".

This is that writer. It is deliberately trivial about what it writes - one
marker file - and deliberately exact about when: it asks `evaluate` with the
plan, the verification record the real validator published, and the approval it
subscribes to, and writes nothing unless the answer is admitted. It is the
consumer contract a real renderer will have to use, exercised at the stage where
writing actually happens.

It lives under `tests/` and is registered only by the fixture manifest beside it,
so it is never part of the distribution and never runs in a real pipeline.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

from kernel.plugin_base import (
    GeneratorPlugin,
    PluginContext,
    PluginDataExchangeError,
    PluginDiagnostic,
    PluginResult,
    Stage,
)
from plugins.validators.strict_admission import admitted_projection, evaluate

MARKER_ENV = "STRICT_WRITER_OUTPUT_DIR"
APPROVAL_ENV = "STRICT_WRITER_APPROVAL_FILE"
MARKER_NAME = "strict-rules.json"


class StrictMarkerGenerator(GeneratorPlugin):
    """Writes one marker file, and only for an admitted plan."""

    def execute(self, ctx: PluginContext, stage: Stage) -> PluginResult:
        diagnostics: list[PluginDiagnostic] = []

        output_dir = os.environ.get(MARKER_ENV)
        if not output_dir:
            # Not wired up by this test run. Writing somewhere of its own choosing
            # is exactly what a writer must not do.
            return self.make_result(diagnostics)

        plan = self._subscribe(ctx, "base.compiler.security_plan", "security_plan")
        verification = self._subscribe(
            ctx, "base.validator.security_plan", "security_plan_verification"
        )
        admission = evaluate(
            plan=plan, verification=verification, approved_intent=self._approval()
        )

        if not admission.admitted:
            # No file, no partial file, and no fallback to a legacy rendering.
            # The refusal is reported so the run says why nothing was written.
            return self.make_result(
                diagnostics,
                output_data={"strict_marker": None, "refusal": list(admission.reasons)},
            )

        # The projection, not the plan it was handed. Admission is per scope, and
        # a renderer that wrote the whole plan would write scopes no approval
        # covered.
        target = Path(output_dir) / MARKER_NAME
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(
            json.dumps(admitted_projection(plan, admission), indent=2, sort_keys=True),
            encoding="utf-8",
        )
        return self.make_result(diagnostics, output_data={"strict_marker": str(target)})

    @staticmethod
    def _subscribe(ctx: PluginContext, plugin_id: str, key: str):
        try:
            return ctx.subscribe(plugin_id, key)
        except PluginDataExchangeError:
            return None

    @staticmethod
    def _approval():
        """The approval, from wherever the deployment says it comes from.

        A file here; a declared channel in a real deployment. What matters for
        the boundary is that it is an input this plugin does not author - a
        writer that could write its own approval would be approving itself.
        """
        path = os.environ.get(APPROVAL_ENV)
        if not path or not Path(path).exists():
            return None
        try:
            return json.loads(Path(path).read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return None
