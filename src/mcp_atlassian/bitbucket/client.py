"""Base client module for Bitbucket Data Center API interactions."""

import logging
import os
from typing import Any
from urllib.parse import quote

from atlassian import Bitbucket
from requests import Response

from ..utils.http import (
    configure_circuit_breaker,
    configure_concurrency,
    configure_rate_limit,
    configure_retry,
    format_rate_limit_error,
)
from ..utils.logging import log_config_param, mask_sensitive
from ..utils.proxy import apply_proxy_configuration
from ..utils.ssl import configure_ssl_verification
from ..utils.ssrf_adapter import mount_ssrf_pinning
from ..utils.urls import make_ssrf_redirect_hook
from ..utils.user_agent import get_default_user_agent
from .config import BitbucketConfig

logger = logging.getLogger("mcp-atlassian.bitbucket")

API = "rest/api/latest"

_STATUS_HINTS = {
    401: (
        "Bitbucket rejected the request (401): the token is invalid or expired, "
        "or it lacks permission for this resource."
    ),
    403: "Bitbucket denied access (403): the token lacks permission.",
    404: "Bitbucket resource not found (404).",
    409: "Bitbucket reported a conflict (409).",
}


class BitbucketApiError(Exception):
    """An HTTP error returned by Bitbucket, with its own messages preserved."""

    def __init__(self, status: int, message: str) -> None:
        super().__init__(message)
        self.status = status


OUT_OF_DATE_MESSAGE = (
    "Bitbucket reported a conflict (409): the pull request changed since it "
    "was read (version conflict). Re-read it with bitbucket_get_pull_request "
    "and retry with the current version."
)


def _bitbucket_errors(response: Response) -> list[dict[str, Any]]:
    """Return the ``errors`` list of a Bitbucket error body."""
    try:
        body = response.json()
    except ValueError:
        return []
    errors = body.get("errors") if isinstance(body, dict) else None
    if not isinstance(errors, list):
        return []
    return [e for e in errors if isinstance(e, dict)]


def _bitbucket_messages(errors: list[dict[str, Any]]) -> list[str]:
    """Error messages, plus merge veto reasons where Bitbucket gives them."""
    messages = []
    for error in errors:
        if error.get("message"):
            messages.append(str(error["message"]))
        for veto in error.get("vetoes") or []:
            summary = veto.get("summaryMessage") or ""
            detail = veto.get("detailedMessage") or ""
            reason = f"{summary}: {detail}" if summary and detail else summary or detail
            if reason:
                messages.append(f"veto: {reason}")
    return messages


def _raise_for_status(response: Response) -> None:
    status = response.status_code
    if status < 400:
        return
    if status == 429:
        raise BitbucketApiError(
            status, format_rate_limit_error(_HttpErr(response), service="Bitbucket")
        )
    errors = _bitbucket_errors(response)
    if status == 409 and any(
        "OutOfDate" in str(e.get("exceptionName", "")) for e in errors
    ):
        raise BitbucketApiError(status, OUT_OF_DATE_MESSAGE)
    hint = _STATUS_HINTS.get(status, f"Bitbucket API error ({status}).")
    details = "; ".join(_bitbucket_messages(errors))
    raise BitbucketApiError(status, f"{hint} {details}".strip())


class _HttpErr:
    """Adapter giving ``format_rate_limit_error`` the ``.response`` it expects."""

    def __init__(self, response: Response) -> None:
        self.response = response


def segment(value: str) -> str:
    """Quote a value for use as a single URL path segment."""
    return quote(value, safe="")


def file_path(path: str) -> str:
    """Quote a repository file path, keeping ``/`` separators."""
    return quote(path.strip("/"), safe="/")


def qualify_branch(ref: str) -> str:
    """Expand a short branch name to ``refs/heads/<name>``.

    Fully qualified refs (``refs/...``) are returned unchanged.
    """
    ref = ref.strip()
    return ref if ref.startswith("refs/") else f"refs/heads/{ref}"


class BitbucketClient:
    """Base client for Bitbucket Data Center API interactions."""

    def __init__(self, config: BitbucketConfig | None = None) -> None:
        """Initialize the client with the given or environment config.

        Args:
            config: Bitbucket configuration. Loaded from env when None.

        Raises:
            ValueError: If the configuration is invalid or incomplete.
        """
        self.config = config or BitbucketConfig.from_env()
        transport_url = self.config.url

        logger.debug(
            "Initializing Bitbucket client with PAT auth. URL: %s, Token: %s",
            self.config.url,
            mask_sensitive(str(self.config.personal_token)),
        )
        self.bitbucket = Bitbucket(
            url=self.config.url,
            token=self.config.personal_token,
            cloud=False,
            verify_ssl=self.config.ssl_verify,
            timeout=self.config.timeout,
        )
        session = self.bitbucket._session  # noqa: SLF001
        # Prevent .netrc from overriding the explicit token (#860).
        session.trust_env = False

        if self.config.no_proxy and isinstance(self.config.no_proxy, str):
            os.environ["NO_PROXY"] = self.config.no_proxy
            log_config_param(logger, "Bitbucket", "NO_PROXY", self.config.no_proxy)

        configure_ssl_verification(
            service_name="Bitbucket",
            url=transport_url,
            session=session,
            ssl_verify=self.config.ssl_verify,
            client_cert=self.config.client_cert,
            client_key=self.config.client_key,
            client_key_password=self.config.client_key_password,
            no_proxy=self.config.no_proxy,
        )

        # Same ordering contract as the Jira/Confluence clients: SSRF redirect
        # hook and DNS pinning first, then the HTTP hardening wrappers (which
        # patch the adapters mounted at this point), then proxies.
        session.hooks["response"].append(make_ssrf_redirect_hook())
        mount_ssrf_pinning(session, transport_url)
        self.bitbucket.retry_with_header = False
        configure_retry(session, service="Bitbucket")
        configure_concurrency(session, service="Bitbucket")
        configure_rate_limit(session, service="Bitbucket")
        configure_circuit_breaker(session, service="Bitbucket")

        self.bitbucket._session = apply_proxy_configuration(  # noqa: SLF001
            logger=logger,
            service_name="Bitbucket",
            session=session,
            config=self.config,
            target_url=transport_url,
        )
        self.bitbucket._session.headers["User-Agent"] = get_default_user_agent()  # noqa: SLF001
        for header_name, header_value in (self.config.custom_headers or {}).items():
            self.bitbucket._session.headers[header_name] = header_value  # noqa: SLF001

    def _project_key(self, project_key: str) -> str:
        """Normalize a project key and enforce BITBUCKET_PROJECTS_FILTER.

        Args:
            project_key: Project key in any case (keys are case-insensitive).

        Returns:
            The upper-cased project key.

        Raises:
            ValueError: If the key is empty or outside the projects filter.
                Raised before any request is made.
        """
        key = project_key.strip().upper()
        if not key:
            raise ValueError("project_key must not be empty.")
        allowed = self.config.allowed_project_keys
        if allowed is not None and key not in allowed:
            raise ValueError(
                f"Project '{key}' is not allowed by BITBUCKET_PROJECTS_FILTER "
                f"(allowed: {', '.join(sorted(allowed))})."
            )
        return key

    def _is_project_allowed(self, project_key: str | None) -> bool:
        """Return whether list results from ``project_key`` may be shown."""
        allowed = self.config.allowed_project_keys
        return allowed is None or (project_key or "").upper() in allowed

    def _repo_path(self, project_key: str, repo_slug: str) -> str:
        """API path of a repository, after enforcing the projects filter."""
        key = self._project_key(project_key)
        slug = repo_slug.strip()
        if not slug:
            raise ValueError("repo_slug must not be empty.")
        return f"{API}/projects/{segment(key)}/repos/{segment(slug)}"

    def _pr_path(self, project_key: str, repo_slug: str, pull_request_id: int) -> str:
        """API path of a pull request, after enforcing the projects filter."""
        repo = self._repo_path(project_key, repo_slug)
        return f"{repo}/pull-requests/{int(pull_request_id)}"

    def _pr_version(self, pr_path: str, version: int | None) -> int:
        """Return ``version`` as given, or read the pull request's current one.

        Passing the version that was read earlier makes Bitbucket refuse the
        change (409) if the pull request moved on in between.
        """
        if version is not None:
            return int(version)
        current = self._get_json(pr_path) or {}
        return int(current.get("version", 0))

    def _request(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        json: Any = None,
        accept: str = "application/json",
    ) -> Response:
        """Send a request to ``{url}/{path}`` and raise on HTTP errors.

        Args:
            method: HTTP method.
            path: Path relative to the instance URL, e.g. ``rest/api/latest/...``.
            params: Query parameters; ``None`` values are dropped.
            json: JSON request body.
            accept: Value for the Accept header.

        Returns:
            The successful response.

        Raises:
            BitbucketApiError: When Bitbucket answers with a 4xx/5xx status.
        """
        clean_params = {k: v for k, v in (params or {}).items() if v is not None}
        headers = {"Accept": accept, "Content-Type": "application/json"}
        response = self.bitbucket.request(
            method=method,
            path=path,
            params=clean_params or None,
            json=json,
            headers=headers,
            advanced_mode=True,
        )
        _raise_for_status(response)
        return response

    def _get_json(self, path: str, params: dict[str, Any] | None = None) -> Any:
        """GET ``path`` and return the decoded JSON body (None when empty)."""
        response = self._request("GET", path, params=params)
        if response.status_code == 204 or not response.content:
            return None
        return response.json()

    def _get_page(
        self,
        path: str,
        *,
        start: int = 0,
        limit: int = 25,
        params: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """GET one page of a paged Bitbucket collection."""
        return self._get_json(path, {**(params or {}), "start": start, "limit": limit})
