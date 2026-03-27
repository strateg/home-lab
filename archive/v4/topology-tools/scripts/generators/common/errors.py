"""Production-ready error handling and validation (Phase 6).

Comprehensive error handling, validation, and recovery strategies.
"""

from __future__ import annotations

import sys
import traceback
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Optional


class ErrorSeverity(Enum):
    """Error severity levels."""

    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


@dataclass
class GeneratorError:
    """Structured error information."""

    severity: ErrorSeverity
    message: str
    component: str
    details: Optional[str] = None
    exception: Optional[Exception] = None
    traceback_str: Optional[str] = None
    recoverable: bool = True

    def __str__(self) -> str:
        """Format error for display."""
        parts = [f"[{self.severity.value.upper()}] {self.component}: {self.message}"]
        if self.details:
            parts.append(f"  Details: {self.details}")
        if self.exception:
            parts.append(f"  Exception: {type(self.exception).__name__}: {self.exception}")
        return "\n".join(parts)


@dataclass
class ErrorHandler:
    """Production error handler with recovery strategies."""

    continue_on_error: bool = False
    verbose: bool = False
    errors: list[GeneratorError] = field(default_factory=list)
    warnings: list[GeneratorError] = field(default_factory=list)

    def handle_error(
        self,
        severity: ErrorSeverity,
        message: str,
        component: str,
        details: Optional[str] = None,
        exception: Optional[Exception] = None,
        recoverable: bool = True,
    ) -> bool:
        """Handle an error.

        Args:
            severity: Error severity
            message: Error message
            component: Component that raised error
            details: Additional details
            exception: Original exception if any
            recoverable: Whether error is recoverable

        Returns:
            True if execution should continue, False if should stop
        """
        tb_str = None
        if exception and self.verbose:
            tb_str = "".join(traceback.format_exception(type(exception), exception, exception.__traceback__))

        error = GeneratorError(
            severity=severity,
            message=message,
            component=component,
            details=details,
            exception=exception,
            traceback_str=tb_str,
            recoverable=recoverable,
        )

        if severity in (ErrorSeverity.ERROR, ErrorSeverity.CRITICAL):
            self.errors.append(error)
            print(f"\n❌ {error}", file=sys.stderr)

            if self.verbose and tb_str:
                print(f"\nTraceback:\n{tb_str}", file=sys.stderr)

            # Critical errors always stop execution
            if severity == ErrorSeverity.CRITICAL or not recoverable:
                return False

            # For other errors, respect continue_on_error setting
            return self.continue_on_error

        elif severity == ErrorSeverity.WARNING:
            self.warnings.append(error)
            print(f"\n⚠️  {error}")
            return True

        else:  # INFO
            print(f"\nℹ️  {error}")
            return True

    def has_errors(self) -> bool:
        """Check if any errors occurred."""
        return len(self.errors) > 0

    def has_warnings(self) -> bool:
        """Check if any warnings occurred."""
        return len(self.warnings) > 0

    def get_summary(self) -> str:
        """Get error summary."""
        parts = []

        if self.errors:
            parts.append(f"Errors: {len(self.errors)}")
            for error in self.errors:
                parts.append(f"  - {error.component}: {error.message}")

        if self.warnings:
            parts.append(f"Warnings: {len(self.warnings)}")
            if self.verbose:
                for warning in self.warnings:
                    parts.append(f"  - {warning.component}: {warning.message}")

        if not parts:
            parts.append("No errors or warnings")

        return "\n".join(parts)

    def raise_if_critical(self) -> None:
        """Raise exception if critical errors occurred."""
        critical_errors = [e for e in self.errors if e.severity == ErrorSeverity.CRITICAL]
        if critical_errors:
            messages = [f"{e.component}: {e.message}" for e in critical_errors]
            raise RuntimeError(f"Critical errors occurred:\n" + "\n".join(messages))


def safe_execute(
    func: Callable,
    error_handler: ErrorHandler,
    component: str,
    operation: str,
    *args,
    **kwargs,
) -> tuple[bool, Any]:
    """Safely execute function with error handling.

    Args:
        func: Function to execute
        error_handler: Error handler instance
        component: Component name
        operation: Operation description
        *args: Function arguments
        **kwargs: Function keyword arguments

    Returns:
        Tuple of (success, result)

    Example:
        >>> handler = ErrorHandler()
        >>> success, result = safe_execute(
        ...     load_topology,
        ...     handler,
        ...     "topology_loader",
        ...     "Load topology file",
        ...     "topology.yaml"
        ... )
    """
    try:
        result = func(*args, **kwargs)
        return True, result

    except FileNotFoundError as e:
        should_continue = error_handler.handle_error(
            ErrorSeverity.CRITICAL,
            f"File not found during: {operation}",
            component,
            details=str(e),
            exception=e,
            recoverable=False,
        )
        return should_continue, None

    except ValueError as e:
        should_continue = error_handler.handle_error(
            ErrorSeverity.ERROR,
            f"Validation error during: {operation}",
            component,
            details=str(e),
            exception=e,
            recoverable=True,
        )
        return should_continue, None

    except Exception as e:
        should_continue = error_handler.handle_error(
            ErrorSeverity.ERROR,
            f"Unexpected error during: {operation}",
            component,
            details=str(e),
            exception=e,
            recoverable=True,
        )
        return should_continue, None


def validate_required_fields(
    data: dict[str, Any],
    required_fields: list[str],
    component: str,
    error_handler: Optional[ErrorHandler] = None,
) -> bool:
    """Validate that required fields exist.

    Args:
        data: Dictionary to validate
        required_fields: List of required field names
        component: Component name for error reporting
        error_handler: Optional error handler

    Returns:
        True if all fields present, False otherwise
    """
    missing = [field for field in required_fields if field not in data]

    if missing:
        message = f"Missing required fields: {', '.join(missing)}"

        if error_handler:
            error_handler.handle_error(
                ErrorSeverity.ERROR,
                message,
                component,
                recoverable=False,
            )
        else:
            raise ValueError(f"{component}: {message}")

        return False

    return True


def validate_file_exists(
    file_path: Path | str,
    component: str,
    error_handler: Optional[ErrorHandler] = None,
) -> bool:
    """Validate that file exists.

    Args:
        file_path: Path to check
        component: Component name for error reporting
        error_handler: Optional error handler

    Returns:
        True if file exists, False otherwise
    """
    path = Path(file_path)

    if not path.exists():
        message = f"File not found: {path}"

        if error_handler:
            error_handler.handle_error(
                ErrorSeverity.CRITICAL,
                message,
                component,
                recoverable=False,
            )
        else:
            raise FileNotFoundError(str(path))

        return False

    return True
