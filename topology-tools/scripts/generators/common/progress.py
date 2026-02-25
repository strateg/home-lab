"""Progress tracking for generators (Phase 5).

Provides progress indicators and structured status reporting.
"""

from __future__ import annotations

import sys
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class ProgressTracker:
    """Track generation progress with visual feedback."""

    total_steps: int
    current_step: int = 0
    verbose: bool = False
    dry_run: bool = False
    step_names: dict[int, str] = field(default_factory=dict)

    def start(self, message: str = "Starting generation...") -> None:
        """Start progress tracking."""
        print(f"╔{'═' * 68}╗")
        print(f"║ {message:<66} ║")
        print(f"╚{'═' * 68}╝")
        print()

    def step(self, name: str, description: str = "") -> None:
        """Mark a step as started."""
        self.current_step += 1
        self.step_names[self.current_step] = name

        prefix = "DRYRUN" if self.dry_run else f"[{self.current_step}/{self.total_steps}]"
        print(f"{prefix} {name}...", end="")

        if self.verbose and description:
            print(f"\n      {description}")

        sys.stdout.flush()

    def step_complete(self, success: bool = True, details: str = "") -> None:
        """Mark current step as complete."""
        if success:
            print(f" ✓")
            if details and self.verbose:
                print(f"      {details}")
        else:
            print(f" ✗")
            if details:
                print(f"      ERROR: {details}")

        sys.stdout.flush()

    def step_skip(self, reason: str = "") -> None:
        """Mark current step as skipped."""
        print(f" ○ (skipped)")
        if reason and self.verbose:
            print(f"      {reason}")
        sys.stdout.flush()

    def finish(self, success: bool = True, summary: Optional[str] = None) -> None:
        """Finish progress tracking."""
        print()
        print(f"╔{'═' * 68}╗")

        if success:
            status = "✓ COMPLETE" if not self.dry_run else "✓ DRY-RUN COMPLETE"
            print(f"║ {status:<66} ║")
        else:
            print(f"║ {'✗ FAILED':<66} ║")

        if summary:
            print(f"╟{'─' * 68}╢")
            for line in summary.splitlines():
                print(f"║ {line:<66} ║")

        print(f"╚{'═' * 68}╝")
        print()


@dataclass
class StatusReporter:
    """Structured status reporting for generators."""

    verbose: bool = False
    dry_run: bool = False
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)

    def info(self, message: str) -> None:
        """Log info message."""
        print(f"INFO  {message}")

    def verbose_info(self, message: str) -> None:
        """Log verbose info message (only if verbose mode)."""
        if self.verbose:
            print(f"DEBUG {message}")

    def warn(self, message: str) -> None:
        """Log warning message."""
        print(f"WARN  {message}")
        self.warnings.append(message)

    def error(self, message: str) -> None:
        """Log error message."""
        print(f"ERROR {message}")
        self.errors.append(message)

    def success(self, message: str) -> None:
        """Log success message."""
        print(f"OK    {message}")

    def dry_run_info(self, message: str) -> None:
        """Log dry-run specific info."""
        if self.dry_run:
            print(f"DRYRUN {message}")

    def has_errors(self) -> bool:
        """Check if any errors were reported."""
        return len(self.errors) > 0

    def has_warnings(self) -> bool:
        """Check if any warnings were reported."""
        return len(self.warnings) > 0

    def get_summary(self) -> str:
        """Get summary of status."""
        lines = []
        if self.errors:
            lines.append(f"Errors: {len(self.errors)}")
        if self.warnings:
            lines.append(f"Warnings: {len(self.warnings)}")
        if not self.errors and not self.warnings:
            lines.append("No issues")
        return " | ".join(lines)
