"""Domain-oriented projection builders for generator plugins (ADR 0112).

Each module owns one projection domain; consumers import builders from the
domain modules directly (no re-exports). ``ProjectionError`` lives in
``plugins.generators.projection_core``.
"""
