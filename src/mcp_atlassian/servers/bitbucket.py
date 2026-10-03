"""Bitbucket Data Center FastMCP server instance and tool definitions."""

import json
import logging
from typing import Annotated, Any

from fastmcp import Context
from pydantic import Field

from mcp_atlassian.servers.dependencies import get_bitbucket_fetcher
from mcp_atlassian.servers.error_handling import ErrorPreservingFastMCP

logger = logging.getLogger(__name__)

bitbucket_mcp = ErrorPreservingFastMCP(
    name="Bitbucket MCP Service",
    instructions=(
        "Provides tools for Bitbucket Data Center: projects, repositories, "
        "code and pull requests. Repositories are addressed by project key "
        "plus repository slug."
    ),
)

StartParam = Annotated[
    int,
    Field(
        description=(
            "Index of the first item to return. Pass next_page_start from a "
            "previous response to get the next page."
        ),
        default=0,
        ge=0,
    ),
]
LimitParam = Annotated[
    int,
    Field(description="Maximum number of items (1-100)", default=25, ge=1, le=100),
]


def _to_json(data: Any) -> str:
    return json.dumps(data, indent=2, ensure_ascii=False)


@bitbucket_mcp.tool(
    tags={"bitbucket", "read", "toolset:bitbucket_projects"},
    annotations={"title": "List Projects", "readOnlyHint": True},
)
async def list_projects(
    ctx: Context,
    start: StartParam = 0,
    limit: LimitParam = 25,
) -> str:
    """List Bitbucket projects the token can access.

    Args:
        ctx: The FastMCP context.
        start: Index of the first project (paging).
        limit: Maximum number of projects.

    Returns:
        JSON with ``values`` (projects with key, name, description, url) and
        paging fields ``is_last_page`` / ``next_page_start``.
    """
    fetcher = await get_bitbucket_fetcher(ctx)
    page = fetcher.list_projects(start=start, limit=limit)
    return _to_json(page.to_simplified_dict())
