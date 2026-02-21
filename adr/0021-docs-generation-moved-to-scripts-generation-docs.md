# ADR 0021: Move Documentation Generation Core into scripts/generation/docs

- Status: Accepted
- Date: 2026-02-21

## Context

`topology-tools/generate-docs.py` contained both CLI orchestration and full documentation generation logic
(core pages, icon handling, diagram integration). This made the top-level script heavy and inconsistent with the
modular direction introduced for `scripts/generation`.

The target is to keep top-level files as entrypoints and place generation implementation inside the generation domain.

## Decision

1. Move documentation generation implementation to `topology-tools/scripts/generation/docs/`:
   - `generator.py` for `DocumentationGenerator`
   - `diagrams.py` for diagram-specific generation (`DiagramDocumentationGenerator`)
   - `cli.py` for docs CLI orchestration
2. Keep `topology-tools/generate-docs.py` as a thin compatibility wrapper that delegates to
   `scripts.generation.docs.cli.main`.
3. Keep `topology-tools/docs_diagrams.py` as a compatibility shim exporting
   `DiagramDocumentationGenerator` from the new location.
4. Refactor core docs generation internals by introducing a shared helper
   (`_render_core_document`) to remove duplicated template render/write blocks.

## Consequences

Benefits:

- Clear separation of concerns: entrypoint, CLI orchestration, and generation core.
- Lower cognitive load in top-level tooling scripts.
- Better extensibility for further docs-generation decomposition.

Trade-offs:

- More modules/files for docs generation flow.
- Requires keeping compatibility wrappers until all external imports are migrated.

Compatibility:

- Existing command remains unchanged: `python topology-tools/generate-docs.py ...`
- Output format and generated docs filenames remain unchanged.

## References

- New module path:
  - `topology-tools/scripts/generation/docs/`
- Compatibility wrappers:
  - `topology-tools/generate-docs.py`
  - `topology-tools/docs_diagrams.py`
