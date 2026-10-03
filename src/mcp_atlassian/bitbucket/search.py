"""Code search through Bitbucket's unofficial search endpoint.

Bitbucket Data Center has no public REST API for code search
(BSERV-11632); its UI uses ``POST /rest/search/latest/search``, which needs a
configured search server and may change between versions.
"""

import html
import re
from typing import Any

from .client import BitbucketApiError, BitbucketClient

SEARCH_API = "rest/search/latest/search"

UNAVAILABLE_MESSAGE = (
    "Bitbucket code search is unavailable on this instance (it relies on an "
    "unofficial endpoint and a configured search server). Browse instead with "
    "bitbucket_list_files (recursive=true) and bitbucket_get_file_content."
)

_HIGHLIGHT = re.compile(r"</?em>")


def _plain(text: str) -> str:
    """Strip Bitbucket's ``<em>`` highlighting and unescape HTML entities."""
    return html.unescape(_HIGHLIGHT.sub("", text))


class SearchMixin(BitbucketClient):
    """Code search."""

    def search_code(
        self,
        query: str,
        *,
        project_key: str | None = None,
        repo_slug: str | None = None,
        start: int = 0,
        limit: int = 25,
    ) -> dict[str, Any]:
        """Search code across permitted projects.

        Args:
            query: Search terms; Bitbucket modifiers such as ``lang:python`` or
                ``ext:sql`` may be included.
            project_key: Only this project.
            repo_slug: Only this repository (needs ``project_key``).
            start: Index of the first file hit.
            limit: Maximum number of file hits.

        Returns:
            ``values`` (one entry per file with matching lines) and paging.

        Raises:
            ValueError: If search is unavailable, or ``repo_slug`` is given
                without ``project_key``.
        """
        if repo_slug and not project_key:
            raise ValueError("repo_slug needs project_key.")
        terms = [query.strip()]
        allowed = self.config.allowed_project_keys
        if project_key:
            terms.append(f"project:{self._project_key(project_key)}")
            if repo_slug:
                terms.append(f"repo:{repo_slug.strip()}")
        elif allowed is not None and len(allowed) == 1:
            terms.append(f"project:{next(iter(allowed))}")

        body = {
            "query": " ".join(terms),
            "entities": {"code": {"start": start, "limit": limit}},
            "limits": {"primary": limit, "secondary": 10},
        }
        try:
            data = self._request("POST", SEARCH_API, json=body).json()
        except BitbucketApiError as e:
            if e.status in (404, 405, 501, 503):
                raise ValueError(f"{UNAVAILABLE_MESSAGE} ({e})") from e
            raise
        code = data.get("code") if isinstance(data, dict) else None
        if not isinstance(code, dict):
            raise ValueError(UNAVAILABLE_MESSAGE)

        values = []
        for file_hit in code.get("values") or []:
            repository = file_hit.get("repository") or {}
            hit_project = (repository.get("project") or {}).get("key")
            if not self._is_project_allowed(hit_project):
                continue
            matches = [
                {"line": line.get("line"), "text": _plain(str(line.get("text", "")))}
                for context in file_hit.get("hitContexts") or []
                for line in context
            ]
            values.append(
                {
                    "project_key": hit_project,
                    "repo_slug": repository.get("slug"),
                    "path": file_hit.get("file"),
                    "hit_count": file_hit.get("hitCount"),
                    "matches": matches,
                }
            )
        result: dict[str, Any] = {
            "values": values,
            "start": code.get("start", start),
            "is_last_page": bool(code.get("isLastPage", True)),
        }
        if not result["is_last_page"] and code.get("nextStart") is not None:
            result["next_page_start"] = code["nextStart"]
        return result
