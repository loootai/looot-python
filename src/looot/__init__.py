"""Python client for the looot API: search, inspect and run data provider operations.

    from looot import Looot

    with Looot() as looot:            # reads LOOOT_TOKEN
        print(looot.balance()["available"])

``AsyncLooot`` has the same methods as coroutines. Docs: https://docs.looot.ai
"""

from ._async_client import AsyncLooot
from ._client import Looot
from ._core import DEFAULT_BASE_URL, DEFAULT_MAX_RETRIES, DEFAULT_TIMEOUT, USER_AGENT
from ._errors import LoootError, TopUp
from ._types import (
    TERMINAL_STATUSES,
    Balance,
    CapabilityRequest,
    CatalogEndpointsPage,
    CatalogOverview,
    CatalogParameter,
    CatalogPrice,
    DiscoverResult,
    Fallback,
    FallbackOptions,
    MediaDownload,
    Operation,
    OverviewJob,
    Prefer,
    PublicCatalogItem,
    PublicCatalogPage,
    RequestedJob,
    Route,
    RouteAttempt,
    Run,
    RunAttempts,
    RunError,
    RunList,
    RunOutcome,
    RunStatus,
    RunSummary,
    SearchResult,
    SearchRow,
    TopUpLink,
    TopUps,
)
from ._version import __version__

VERSION = __version__

__all__ = [
    "AsyncLooot",
    "Balance",
    "CapabilityRequest",
    "CatalogEndpointsPage",
    "CatalogOverview",
    "CatalogParameter",
    "CatalogPrice",
    "DEFAULT_BASE_URL",
    "DEFAULT_MAX_RETRIES",
    "DEFAULT_TIMEOUT",
    "DiscoverResult",
    "Fallback",
    "FallbackOptions",
    "Looot",
    "LoootError",
    "MediaDownload",
    "Operation",
    "OverviewJob",
    "Prefer",
    "PublicCatalogItem",
    "PublicCatalogPage",
    "RequestedJob",
    "Route",
    "RouteAttempt",
    "Run",
    "RunAttempts",
    "RunError",
    "RunList",
    "RunOutcome",
    "RunStatus",
    "RunSummary",
    "SearchResult",
    "SearchRow",
    "TERMINAL_STATUSES",
    "TopUp",
    "TopUpLink",
    "TopUps",
    "USER_AGENT",
    "VERSION",
    "__version__",
]
