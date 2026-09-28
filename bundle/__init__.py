"""Bundle: a local-first multi-agent project execution system."""

__version__ = "0.1.0"

from .store import BundleError, ConflictError, Database, NotFoundError, ValidationError

__all__ = [
    "BundleError",
    "ConflictError",
    "Database",
    "NotFoundError",
    "ValidationError",
    "__version__",
]
