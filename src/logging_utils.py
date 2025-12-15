"""Centralized logging utilities for consistent output across modules."""

# Module-level verbose flag
_verbose = False


def set_verbose(enabled: bool) -> None:
    """Set verbose logging mode for all modules.
    
    Args:
        enabled: If True, detailed logs are shown. If False, only minimal logs.
    """
    global _verbose
    _verbose = enabled


def is_verbose() -> bool:
    """Check if verbose mode is enabled."""
    return _verbose


def log_info(message: str) -> None:
    """Log a message that is always shown (errors, warnings)."""
    print(message)


def log_verbose(message: str) -> None:
    """Log a message only when verbose mode is enabled."""
    if _verbose:
        print(message)


def log_error(message: str, detail: str = "") -> None:
    """Log an error message. Detail is only shown in verbose mode.
    
    Args:
        message: The main error message (always shown).
        detail: Additional detail (only shown in verbose mode).
    """
    if _verbose and detail:
        print(f"{message}: {detail}")
    else:
        print(message)

