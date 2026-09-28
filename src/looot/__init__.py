"""Python client for the looot API: search, inspect and run data provider operations."""

from ._client import DEFAULT_BASE_URL, Looot
from ._errors import LoootError

__version__ = "0.1.0"
__all__ = ["Looot", "LoootError", "DEFAULT_BASE_URL", "__version__"]
