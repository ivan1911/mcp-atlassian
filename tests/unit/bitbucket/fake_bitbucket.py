"""In-memory fake of the Bitbucket Data Center HTTP boundary.

Mounted on a real Bitbucket client's ``requests.Session`` so tests drive MCP
tools end to end and assert on tool output plus the HTTP requests that reached
"Bitbucket". Response bodies are shaped after the Bitbucket 10.x OpenAPI spec.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any
from urllib.parse import parse_qs, unquote, urlsplit

from requests import PreparedRequest, Response
from requests.adapters import BaseAdapter
from requests.structures import CaseInsensitiveDict


@dataclass
class RecordedRequest:
    """One HTTP request that reached the fake Bitbucket."""

    method: str
    path: str
    query: dict[str, str]
    headers: CaseInsensitiveDict[str]
    body: Any


@dataclass
class _Route:
    status: int
    body: Any
    headers: dict[str, str] = field(default_factory=dict)


class FakeBitbucket(BaseAdapter):
    """Transport adapter serving canned responses keyed by method and path."""

    def __init__(self) -> None:
        super().__init__()
        self._routes: dict[tuple[str, str], list[_Route]] = {}
        self.requests: list[RecordedRequest] = []

    def add(
        self,
        method: str,
        path: str,
        body: Any = None,
        *,
        status: int = 200,
        headers: dict[str, str] | None = None,
    ) -> None:
        """Queue a response for ``method`` + ``path`` (path without query).

        Several responses for the same route are served in order; the last
        one repeats once the queue is exhausted.
        """
        self._routes.setdefault((method.upper(), path), []).append(
            _Route(status=status, body=body, headers=headers or {})
        )

    def error(self, method: str, path: str, status: int, message: str) -> None:
        """Queue a Bitbucket-style error response."""
        self.add(
            method,
            path,
            {"errors": [{"context": None, "message": message, "exceptionName": None}]},
            status=status,
        )

    def requests_to(self, method: str, path: str) -> list[RecordedRequest]:
        """Return the recorded requests for one route."""
        return [
            r for r in self.requests if r.method == method.upper() and r.path == path
        ]

    def send(  # type: ignore[override]
        self, request: PreparedRequest, **kwargs: Any
    ) -> Response:
        split = urlsplit(request.url or "")
        path = unquote(split.path)
        query = {k: v[-1] for k, v in parse_qs(split.query).items()}
        method = (request.method or "GET").upper()
        self.requests.append(
            RecordedRequest(
                method=method,
                path=path,
                query=query,
                headers=CaseInsensitiveDict(request.headers),
                body=_decode_body(request.body),
            )
        )

        routes = self._routes.get((method, path))
        response = Response()
        response.request = request
        response.url = request.url or ""
        if not routes:
            response.status_code = 404
            body: Any = {
                "errors": [{"message": f"FakeBitbucket: no route {method} {path}"}]
            }
            route_headers: dict[str, str] = {}
        else:
            route = routes.pop(0) if len(routes) > 1 else routes[0]
            response.status_code = route.status
            body = route.body
            route_headers = route.headers

        if isinstance(body, bytes | str):
            raw = body.encode() if isinstance(body, str) else body
            content_type = "text/plain;charset=UTF-8"
        else:
            raw = json.dumps(body).encode() if body is not None else b""
            content_type = "application/json;charset=UTF-8"
        response._content = raw  # noqa: SLF001
        response.headers = CaseInsensitiveDict(
            {"Content-Type": content_type, **route_headers}
        )
        response.encoding = "utf-8"
        return response

    def close(self) -> None:
        """Nothing to release."""


def _decode_body(body: Any) -> Any:
    if body is None:
        return None
    if isinstance(body, bytes):
        body = body.decode()
    try:
        return json.loads(body)
    except (TypeError, ValueError):
        return body


def page(
    values: list[dict[str, Any]],
    *,
    start: int = 0,
    limit: int = 25,
    next_page_start: int | None = None,
) -> dict[str, Any]:
    """Build a Bitbucket paged response."""
    result: dict[str, Any] = {
        "size": len(values),
        "limit": limit,
        "start": start,
        "isLastPage": next_page_start is None,
        "values": values,
    }
    if next_page_start is not None:
        result["nextPageStart"] = next_page_start
    return result


def project(key: str, name: str | None = None, **extra: Any) -> dict[str, Any]:
    """Build a Bitbucket project payload."""
    return {
        "key": key,
        "id": abs(hash(key)) % 10_000,
        "name": name or key.title(),
        "description": f"{key} project",
        "public": False,
        "type": "NORMAL",
        "links": {"self": [{"href": f"https://bitbucket.example.com/projects/{key}"}]},
        **extra,
    }


def repository(project_key: str, slug: str, **extra: Any) -> dict[str, Any]:
    """Build a Bitbucket repository payload."""
    base = "https://bitbucket.example.com"
    return {
        "slug": slug,
        "id": abs(hash((project_key, slug))) % 10_000,
        "name": slug.replace("-", " ").title(),
        "description": f"{slug} repository",
        "state": "AVAILABLE",
        "forkable": True,
        "public": False,
        "archived": False,
        "scmId": "git",
        "project": project(project_key),
        "links": {
            "self": [{"href": f"{base}/projects/{project_key}/repos/{slug}/browse"}],
            "clone": [
                {
                    "href": f"{base}/scm/{project_key.lower()}/{slug}.git",
                    "name": "http",
                },
                {
                    "href": f"ssh://git@bitbucket.example.com:7999/"
                    f"{project_key.lower()}/{slug}.git",
                    "name": "ssh",
                },
            ],
        },
        **extra,
    }


def branch_ref(name: str, *, latest_commit: str = "a" * 40, default: bool = False):
    """Build a Bitbucket branch payload."""
    return {
        "id": f"refs/heads/{name}",
        "displayId": name,
        "type": "BRANCH",
        "latestCommit": latest_commit,
        "latestChangeset": latest_commit,
        "isDefault": default,
    }
