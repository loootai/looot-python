"""Shared helpers. Every offline test answers HTTP locally: nothing leaves the machine."""

from __future__ import annotations

import json
from typing import Any, Callable, List, Optional, Union

import httpx
import pytest

from looot import Looot

Answer = Union[httpx.Response, Callable[[httpx.Request], httpx.Response]]


class Recorder:
    """An httpx transport that records requests and plays back queued answers."""

    def __init__(self, *answers: Answer) -> None:
        self.answers: List[Answer] = list(answers)
        self.requests: List[httpx.Request] = []

    def handler(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        answer = self.answers.pop(0) if len(self.answers) > 1 else (self.answers[0] if self.answers else httpx.Response(200, json={}))
        return answer(request) if callable(answer) else answer

    @property
    def last(self) -> httpx.Request:
        return self.requests[-1]

    def body(self, index: int = -1) -> Any:
        return json.loads(self.requests[index].content)


@pytest.fixture(autouse=True)
def no_env_token(monkeypatch):
    """Tests never pick up a real token from the shell."""
    monkeypatch.delenv("LOOOT_TOKEN", raising=False)
    monkeypatch.delenv("LOOOT_API_KEY", raising=False)


def make(
    *answers: Answer,
    token: Optional[str] = "t",
    sleeps: Optional[list] = None,
    **kwargs: Any,
):
    """A Looot client over a Recorder. ``sleeps`` collects every retry or poll wait."""
    rec = Recorder(*answers)
    waits = sleeps if sleeps is not None else []
    client = Looot(token, transport=httpx.MockTransport(rec.handler), sleep=waits.append, **kwargs)
    return client, rec
