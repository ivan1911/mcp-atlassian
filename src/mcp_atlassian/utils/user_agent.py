"""User-Agent helpers for HTTP sessions."""

from mcp_atlassian.utils.package import get_package_version


def get_default_user_agent() -> str:
    """Return the default ``User-Agent`` string for outbound requests.

    Some WAFs in front of Jira/Confluence Server/DC instances block requests
    carrying the default ``python-requests/X.Y`` User-Agent, returning 403 even
    when the bearer token is valid. Setting an explicit, identifiable
    ``User-Agent`` avoids that class of false-positive auth errors.
    """
    return f"mcp-atlassian/{get_package_version()}"
