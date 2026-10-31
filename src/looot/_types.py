"""Typed request and response shapes for the looot REST API.

Every response type is a ``TypedDict`` with ``total=False``. At runtime each one is a plain
``dict``: fields the gateway adds later are kept and reachable with ``run["newField"]``, and a
field the gateway leaves out is simply missing. Only the fields in the SDK contract are typed.

Status, outcome and error codes are typed as ``str``. The ``Literal`` aliases list the values
known today, but a new value from the gateway never breaks a client.
"""

from __future__ import annotations

from typing import Any, Dict, List, Literal, Optional, TypedDict, Union

JSON = Dict[str, Any]

Prefer = Literal["balanced", "cheapest", "reliable", "fastest"]
"""How a search or a fallback route orders providers."""

RunStatus = Literal[
    "queued",
    "running",
    "pending_provider",
    "completed",
    "failed",
    "blocked",
    "stopped",
    "reconciliation_pending",
]
"""Run lifecycle values known today. Read ``run["status"]`` as a ``str``."""

RunOutcome = Literal["hit", "weak", "miss", "error", "rejected", "skipped", "pending"]
"""Was the answer any good. A ``completed`` run can be a ``miss``."""

OverviewDepth = Literal["summary", "platforms", "jobs", "full"]

TERMINAL_STATUSES = frozenset(
    {"completed", "failed", "blocked", "stopped", "reconciliation_pending"}
)
"""Statuses after which polling a run stops."""


class FallbackOptions(TypedDict, total=False):
    """The ``fallback`` object on ``POST /v1/runs``. Every field is optional."""

    enabled: bool
    maxAttempts: int
    maxCostUsd: float
    prefer: Union[Prefer, str]
    exclude: List[str]
    stopAtFirstMiss: bool


Fallback = Union[bool, FallbackOptions, Dict[str, Any]]


# ---- catalog ----


class OverviewTotals(TypedDict, total=False):
    categories: int
    platforms: int
    jobs: int
    providers: int
    endpoints: int
    runnableEndpoints: int


class OverviewJob(TypedDict, total=False):
    id: str
    title: str
    category: str
    platform: str
    providerCount: int
    endpointCount: int
    runnableCount: int
    cheapestPerCall: Optional[float]
    cheapestPerResult: Optional[float]


class CatalogOverview(TypedDict, total=False):
    revision: str
    builtAt: str
    depth: str
    totals: OverviewTotals
    categories: List[JSON]
    topic: str
    matchCount: int
    truncated: bool
    jobs: List[OverviewJob]


class CatalogParameter(TypedDict, total=False):
    name: str
    location: str
    required: bool
    description: str


class CatalogPrice(TypedDict, total=False):
    """``state`` is ``known`` (with an amount) or ``unknown`` / ``uncomputable`` (with a reason)."""

    state: str
    amountMicros: int
    currency: str
    unit: str
    effectiveAt: str
    reason: str


class PublicCatalogItem(TypedDict, total=False):
    catalogItemId: str
    revision: Any
    providerId: str
    operationId: str
    title: str
    description: str
    categories: List[str]
    capabilities: List[str]
    parameters: List[CatalogParameter]
    price: CatalogPrice
    verification: Any
    publishedAt: str
    itemDigest: str
    provenanceTier: str


class PublicCatalogPage(TypedDict, total=False):
    items: List[PublicCatalogItem]
    catalogDigest: str
    nextCursor: Optional[str]
    unsuppliedJobs: List[Any]
    warnings: List[Any]


class Works(TypedDict, total=False):
    rate: Optional[float]
    runs: int
    p50Ms: Optional[float]
    thin: bool


class SearchRow(TypedDict, total=False):
    """One search row. The wire also has ``async`` (a Python keyword): read ``row["async"]``."""

    endpointId: str
    provider: str
    name: str
    capability: str
    sourceCapability: str
    category: str
    access: str
    estimatedPrice: Optional[float]
    priceBasis: str
    costPerSuccessUsd: Optional[float]
    works: Works
    credential: Any
    job: JSON


class SearchResult(TypedDict, total=False):
    query: str
    total: int
    endpoints: List[SearchRow]
    nextOffset: Optional[int]
    prefer: str
    warnings: List[Any]
    priceHint: Any


class DiscoverResult(TypedDict, total=False):
    candidates: List[JSON]
    meta: JSON


class CatalogEndpointsPage(TypedDict, total=False):
    endpoints: List[JSON]
    nextCursor: Optional[str]
    facets: JSON


class Operation(TypedDict, total=False):
    """``GET /v1/operations/{endpointId}``: what an endpoint takes, returns and may cost."""

    endpoint: JSON
    estimatedMaxCost: Any
    priceRange: Any
    inputSchema: JSON
    requestBinding: Any
    uiSchema: Any
    outputFormat: Any
    usageHints: Any


# ---- runs ----


class RunError(TypedDict, total=False):
    """The ``error`` object on a failed or blocked run."""

    code: str
    message: str
    requestId: str
    providerStatus: Optional[int]
    whoseError: str
    retryable: bool
    retryHint: str


class RouteAttempt(TypedDict, total=False):
    n: int
    endpointId: str
    provider: str
    outcome: str
    status: str
    chargedUsd: float
    billed: bool
    ms: int
    reason: str
    verdict: str


class Route(TypedDict, total=False):
    servedBy: Optional[str]
    outcome: str
    chargedUsd: float
    capped: bool
    attempts: List[RouteAttempt]
    skipped: List[JSON]
    summary: str


class RequestedJob(TypedDict, total=False):
    id: str
    job: str
    prefer: str
    pickedEndpointId: Optional[str]
    reason: str
    skipped: List[JSON]


class Run(TypedDict, total=False):
    """One run. HTTP 201 is not success: read ``status``, ``outcome`` and ``error``."""

    runId: str
    status: Union[RunStatus, str]
    endpointId: str
    outcome: Union[RunOutcome, str]
    outcomeReason: str
    result: Any
    normalized: JSON
    estimatedCost: Optional[float]
    actualCost: Optional[float]
    pricing: JSON
    reservationId: str
    error: Optional[RunError]
    replayed: bool
    requestedJob: RequestedJob
    route: Route
    nextSteps: List[JSON]
    providerText: Any
    trimmed: Any


class RunSummary(TypedDict, total=False):
    runId: str
    endpointId: str
    job: str
    providerId: str
    status: Union[RunStatus, str]
    providerResponseStatus: Optional[int]
    createdAt: str
    completedAt: Optional[str]
    actualCost: Optional[float]
    error: Optional[RunError]
    resultBytes: int
    servedEndpointId: str
    servedProviderId: str


class RunList(TypedDict, total=False):
    runs: List[RunSummary]
    nextCursor: Optional[str]


class RunAttempts(TypedDict, total=False):
    attempts: List[JSON]


# ---- money and account ----


class TopUpLink(TypedDict, total=False):
    minimumUsd: float
    suggestedUsd: float
    checkoutUrl: Optional[str]
    dashboardUrl: str
    message: str
    reason: str


class Balance(TypedDict, total=False):
    workspaceId: str
    currency: str
    available: float
    reserved: float
    holds: Any
    trialCreditMicros: int
    recentSpendMicros: int
    topUpLink: TopUpLink


class TopUps(TypedDict, total=False):
    topUps: List[JSON]


class CapabilityRequest(TypedDict, total=False):
    requestId: str
    title: str
    description: str
    desiredInputs: List[str]
    desiredOutputs: List[str]
    status: str
    idempotencyKey: str
    createdAt: str


class MediaDownload:
    """Bytes of a run's stored file and their content type."""

    __slots__ = ("content", "content_type")

    def __init__(self, content: bytes, content_type: str) -> None:
        self.content = content
        self.content_type = content_type

    def __repr__(self) -> str:
        return f"MediaDownload(content_type={self.content_type!r}, bytes={len(self.content)})"
