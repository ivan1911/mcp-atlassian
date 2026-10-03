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


def tag_ref(name: str, *, latest_commit: str = "b" * 40) -> dict[str, Any]:
    """Build a Bitbucket tag payload."""
    return {
        "id": f"refs/tags/{name}",
        "displayId": name,
        "type": "TAG",
        "latestCommit": latest_commit,
        "latestChangeset": latest_commit,
        "hash": "c" * 40,
    }


def user(name: str, email: str | None = None) -> dict[str, Any]:
    """Build a Bitbucket user payload."""
    return {
        "name": name,
        "emailAddress": email or f"{name}@example.com",
        "displayName": name.title(),
        "slug": name,
        "id": abs(hash(name)) % 10_000,
        "active": True,
        "type": "NORMAL",
    }


def commit(
    commit_id: str,
    message: str = "Fix the thing",
    *,
    author: str = "alice",
    parents: tuple[str, ...] = (),
    timestamp: int = 1_700_000_000_000,
) -> dict[str, Any]:
    """Build a Bitbucket commit payload."""
    return {
        "id": commit_id,
        "displayId": commit_id[:11],
        "message": message,
        "author": user(author),
        "authorTimestamp": timestamp,
        "committer": user(author),
        "committerTimestamp": timestamp,
        "parents": [{"id": p, "displayId": p[:11]} for p in parents],
    }


def change(path: str, change_type: str = "MODIFY", src_path: str | None = None):
    """Build a Bitbucket change (changed file) payload."""
    result: dict[str, Any] = {
        "path": {"toString": path, "name": path.rsplit("/", 1)[-1]},
        "type": change_type,
        "nodeType": "FILE",
    }
    if src_path:
        result["srcPath"] = {"toString": src_path}
    return result


def browse_directory(path: str, children: list[tuple[str, str, int | None]]):
    """Build a ``/browse`` response for a directory.

    ``children`` are ``(name, type, size)`` with type FILE/DIRECTORY/SUBMODULE.
    """
    values = []
    for name, node_type, size in children:
        child: dict[str, Any] = {
            "path": {"toString": name, "name": name},
            "type": node_type,
        }
        if size is not None:
            child["size"] = size
        values.append(child)
    return {
        "path": {"toString": path, "name": path.rsplit("/", 1)[-1] if path else ""},
        "revision": "main",
        "children": page(values),
    }


def hunk(
    source_line: int,
    destination_line: int,
    segments: list[tuple[str, list[str]]],
    *,
    truncated: bool = False,
) -> dict[str, Any]:
    """Build a diff hunk from ``(type, lines)`` segments.

    Line numbers are assigned like Bitbucket does: CONTEXT advances both
    sides, REMOVED the source, ADDED the destination.
    """
    src, dst = source_line, destination_line
    built = []
    for seg_type, lines in segments:
        seg_lines = []
        for text in lines:
            seg_lines.append({"source": src, "destination": dst, "line": text})
            if seg_type in ("CONTEXT", "REMOVED"):
                src += 1
            if seg_type in ("CONTEXT", "ADDED"):
                dst += 1
        built.append({"type": seg_type, "lines": seg_lines, "truncated": False})
    return {
        "sourceLine": source_line,
        "sourceSpan": src - source_line,
        "destinationLine": destination_line,
        "destinationSpan": dst - destination_line,
        "segments": built,
        "truncated": truncated,
    }


def file_diff(
    source: str | None,
    destination: str | None,
    hunks: list[dict[str, Any]] | None = None,
    *,
    truncated: bool = False,
    binary: bool = False,
) -> dict[str, Any]:
    """Build one file's diff; ``None`` source/destination means added/deleted."""
    result: dict[str, Any] = {
        "source": {"toString": source} if source else None,
        "destination": {"toString": destination} if destination else None,
        "hunks": hunks or [],
        "truncated": truncated,
    }
    if binary:
        result["binary"] = True
    return result


def diff(
    files: list[dict[str, Any]],
    *,
    from_hash: str = "1" * 40,
    to_hash: str = "2" * 40,
    truncated: bool = False,
) -> dict[str, Any]:
    """Build a Bitbucket JSON diff response."""
    return {
        "fromHash": from_hash,
        "toHash": to_hash,
        "contextLines": 10,
        "whitespace": "SHOW",
        "diffs": files,
        "truncated": truncated,
    }


def pr_ref(project_key: str, slug: str, branch: str, sha: str = "d" * 40):
    """Build a pull request source/target ref."""
    return {
        "id": f"refs/heads/{branch}",
        "displayId": branch,
        "latestCommit": sha,
        "repository": repository(project_key, slug),
    }


def participant(name: str, status: str = "UNAPPROVED", role: str = "REVIEWER"):
    """Build a pull request participant."""
    return {
        "user": user(name),
        "role": role,
        "approved": status == "APPROVED",
        "status": status,
    }


def pull_request(
    pr_id: int,
    title: str = "Add login",
    *,
    project_key: str = "PLAT",
    slug: str = "api",
    source: str = "feature/login",
    target: str = "main",
    version: int = 3,
    state: str = "OPEN",
    author: str = "alice",
    reviewers: list[dict[str, Any]] | None = None,
    **extra: Any,
) -> dict[str, Any]:
    """Build a Bitbucket pull request payload."""
    return {
        "id": pr_id,
        "version": version,
        "title": title,
        "description": f"Implements {title.lower()}",
        "state": state,
        "open": state == "OPEN",
        "closed": state != "OPEN",
        "draft": False,
        "createdDate": 1_700_000_000_000,
        "updatedDate": 1_700_000_360_000,
        "fromRef": pr_ref(project_key, slug, source),
        "toRef": pr_ref(project_key, slug, target, sha="e" * 40),
        "locked": False,
        "author": participant(author, role="AUTHOR"),
        "reviewers": reviewers if reviewers is not None else [],
        "participants": [],
        "properties": {"commentCount": 2, "openTaskCount": 1, "resolvedTaskCount": 0},
        "links": {
            "self": [
                {
                    "href": f"https://bitbucket.example.com/projects/{project_key}"
                    f"/repos/{slug}/pull-requests/{pr_id}"
                }
            ]
        },
        **extra,
    }


def comment_payload(
    comment_id: int,
    text: str,
    *,
    author: str = "bob",
    version: int = 0,
    severity: str = "NORMAL",
    state: str = "OPEN",
    replies: list[dict[str, Any]] | None = None,
    anchor: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build a Bitbucket pull request comment payload."""
    result: dict[str, Any] = {
        "id": comment_id,
        "version": version,
        "text": text,
        "author": user(author),
        "createdDate": 1_700_000_000_000,
        "updatedDate": 1_700_000_000_000,
        "severity": severity,
        "state": state,
        "comments": replies or [],
    }
    if anchor is not None:
        result["anchor"] = anchor
    return result


def inline_anchor(
    path: str, line: int, line_type: str = "ADDED", file_type: str = "TO"
) -> dict[str, Any]:
    """Build an inline comment anchor."""
    return {
        "path": path,
        "srcPath": path,
        "line": line,
        "lineType": line_type,
        "fileType": file_type,
        "diffType": "EFFECTIVE",
        "orphaned": False,
    }


def activity(activity_id: int, action: str, actor: str = "bob", **extra: Any):
    """Build a pull request activity entry."""
    return {
        "id": activity_id,
        "createdDate": 1_700_000_000_000,
        "user": user(actor),
        "action": action,
        **extra,
    }
