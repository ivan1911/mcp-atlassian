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


ProjectKeyParam = Annotated[
    str,
    Field(description="Project key, e.g. 'PLAT' (case-insensitive)."),
]
RepoSlugParam = Annotated[
    str,
    Field(description="Repository slug, e.g. 'billing-api'."),
]


@bitbucket_mcp.tool(
    tags={"bitbucket", "read", "toolset:bitbucket_projects"},
    annotations={"title": "List Repositories", "readOnlyHint": True},
)
async def list_repositories(
    ctx: Context,
    project_key: Annotated[
        str | None,
        Field(
            description="(Optional) Only repositories of this project key.",
            default=None,
        ),
    ] = None,
    name: Annotated[
        str | None,
        Field(
            description=(
                "(Optional) Case-insensitive repository name filter. Without "
                "project_key it searches across all projects."
            ),
            default=None,
        ),
    ] = None,
    start: StartParam = 0,
    limit: LimitParam = 25,
) -> str:
    """List repositories in a project, or find repositories by name.

    Args:
        ctx: The FastMCP context.
        project_key: Restrict to this project.
        name: Repository name filter.
        start: Index of the first repository (paging).
        limit: Maximum number of repositories.

    Returns:
        JSON with ``values`` (repositories with project_key, slug, name) and
        paging fields.
    """
    fetcher = await get_bitbucket_fetcher(ctx)
    page = fetcher.list_repositories(
        project_key=project_key, name=name, start=start, limit=limit
    )
    return _to_json(page.to_simplified_dict())


@bitbucket_mcp.tool(
    tags={"bitbucket", "read", "toolset:bitbucket_projects"},
    annotations={"title": "Get Repository", "readOnlyHint": True},
)
async def get_repository(
    ctx: Context,
    project_key: ProjectKeyParam,
    repo_slug: RepoSlugParam,
) -> str:
    """Get repository details, including its default branch and clone URLs.

    Args:
        ctx: The FastMCP context.
        project_key: Project key.
        repo_slug: Repository slug.

    Returns:
        JSON repository with project_key, slug, default_branch and clone_urls.
    """
    fetcher = await get_bitbucket_fetcher(ctx)
    return _to_json(fetcher.get_repository(project_key, repo_slug).to_simplified_dict())


AtParam = Annotated[
    str | None,
    Field(
        description=(
            "(Optional) Branch name, tag, fully qualified ref (refs/heads/...) "
            "or commit hash. Defaults to the repository's default branch."
        ),
        default=None,
    ),
]


@bitbucket_mcp.tool(
    tags={"bitbucket", "read", "toolset:bitbucket_code"},
    annotations={"title": "List Files", "readOnlyHint": True},
)
async def list_files(
    ctx: Context,
    project_key: ProjectKeyParam,
    repo_slug: RepoSlugParam,
    path: Annotated[
        str,
        Field(description="Directory path; empty for the repository root.", default=""),
    ] = "",
    at: AtParam = None,
    recursive: Annotated[
        bool,
        Field(
            description=(
                "List every file below the directory (recursively) instead of "
                "one level of files and directories."
            ),
            default=False,
        ),
    ] = False,
    start: StartParam = 0,
    limit: LimitParam = 25,
) -> str:
    """List files and directories in a repository at a branch, tag or commit.

    Args:
        ctx: The FastMCP context.
        project_key: Project key.
        repo_slug: Repository slug.
        path: Directory path.
        at: Branch, tag or commit.
        recursive: List all files recursively.
        start: Index of the first entry (paging).
        limit: Maximum number of entries.

    Returns:
        JSON with ``values`` (``path`` from the repository root, ``type`` and
        ``size``) and paging fields.
    """
    fetcher = await get_bitbucket_fetcher(ctx)
    page = fetcher.list_files(
        project_key,
        repo_slug,
        path=path,
        at=at,
        recursive=recursive,
        start=start,
        limit=limit,
    )
    return _to_json(page.to_simplified_dict())


@bitbucket_mcp.tool(
    tags={"bitbucket", "read", "toolset:bitbucket_code"},
    annotations={"title": "Get File Content", "readOnlyHint": True},
)
async def get_file_content(
    ctx: Context,
    project_key: ProjectKeyParam,
    repo_slug: RepoSlugParam,
    path: Annotated[str, Field(description="File path from the repository root.")],
    at: AtParam = None,
    start_line: Annotated[
        int,
        Field(description="First line to return (1-based).", default=1, ge=1),
    ] = 1,
    limit: Annotated[
        int,
        Field(
            description="Maximum number of lines to return (1-5000).",
            default=1000,
            ge=1,
            le=5000,
        ),
    ] = 1000,
) -> str:
    """Read a file (or a line range of it) at a branch, tag or commit.

    Args:
        ctx: The FastMCP context.
        project_key: Project key.
        repo_slug: Repository slug.
        path: File path.
        at: Branch, tag or commit.
        start_line: First line to return.
        limit: Maximum number of lines.

    Returns:
        JSON with ``content``, ``start_line``, ``end_line``, ``total_lines`` and
        ``truncated`` (read further with a later ``start_line``). Binary files
        return ``binary`` and ``size_bytes`` without content.
    """
    fetcher = await get_bitbucket_fetcher(ctx)
    return _to_json(
        fetcher.get_file_content(
            project_key, repo_slug, path, at=at, start_line=start_line, limit=limit
        )
    )


FilterParam = Annotated[
    str | None,
    Field(description="(Optional) Only names containing this text.", default=None),
]


@bitbucket_mcp.tool(
    tags={"bitbucket", "read", "toolset:bitbucket_code"},
    annotations={"title": "List Branches", "readOnlyHint": True},
)
async def list_branches(
    ctx: Context,
    project_key: ProjectKeyParam,
    repo_slug: RepoSlugParam,
    filter: FilterParam = None,
    start: StartParam = 0,
    limit: LimitParam = 25,
) -> str:
    """List branches, most recently modified first; the default is marked.

    Args:
        ctx: The FastMCP context.
        project_key: Project key.
        repo_slug: Repository slug.
        filter: Branch name filter.
        start: Index of the first branch (paging).
        limit: Maximum number of branches.

    Returns:
        JSON with ``values`` (name, id, latest_commit, is_default) and paging.
    """
    fetcher = await get_bitbucket_fetcher(ctx)
    page = fetcher.list_branches(
        project_key, repo_slug, filter_text=filter, start=start, limit=limit
    )
    return _to_json(page.to_simplified_dict())


@bitbucket_mcp.tool(
    tags={"bitbucket", "read", "toolset:bitbucket_code"},
    annotations={"title": "List Tags", "readOnlyHint": True},
)
async def list_tags(
    ctx: Context,
    project_key: ProjectKeyParam,
    repo_slug: RepoSlugParam,
    filter: FilterParam = None,
    start: StartParam = 0,
    limit: LimitParam = 25,
) -> str:
    """List tags, most recently modified first.

    Args:
        ctx: The FastMCP context.
        project_key: Project key.
        repo_slug: Repository slug.
        filter: Tag name filter.
        start: Index of the first tag (paging).
        limit: Maximum number of tags.

    Returns:
        JSON with ``values`` (name, id, latest_commit) and paging fields.
    """
    fetcher = await get_bitbucket_fetcher(ctx)
    page = fetcher.list_tags(
        project_key, repo_slug, filter_text=filter, start=start, limit=limit
    )
    return _to_json(page.to_simplified_dict())


@bitbucket_mcp.tool(
    tags={"bitbucket", "read", "toolset:bitbucket_code"},
    annotations={"title": "List Commits", "readOnlyHint": True},
)
async def list_commits(
    ctx: Context,
    project_key: ProjectKeyParam,
    repo_slug: RepoSlugParam,
    at: AtParam = None,
    path: Annotated[
        str | None,
        Field(description="(Optional) Only commits touching this path.", default=None),
    ] = None,
    since: Annotated[
        str | None,
        Field(
            description=(
                "(Optional) Exclude commits reachable from this branch, tag or "
                "commit, e.g. 'v1.0' to list what changed after a release."
            ),
            default=None,
        ),
    ] = None,
    start: StartParam = 0,
    limit: LimitParam = 25,
) -> str:
    """List commits reachable from a branch, tag or commit, newest first.

    Args:
        ctx: The FastMCP context.
        project_key: Project key.
        repo_slug: Repository slug.
        at: Branch, tag or commit to list from.
        path: Only commits touching this path.
        since: Exclude commits reachable from this ref.
        start: Index of the first commit (paging).
        limit: Maximum number of commits.

    Returns:
        JSON with ``values`` (id, message, author, timestamps, parents) and
        paging fields.
    """
    fetcher = await get_bitbucket_fetcher(ctx)
    page = fetcher.list_commits(
        project_key, repo_slug, at=at, path=path, since=since, start=start, limit=limit
    )
    return _to_json(page.to_simplified_dict())


CommitIdParam = Annotated[str, Field(description="Commit hash (full or abbreviated).")]


@bitbucket_mcp.tool(
    tags={"bitbucket", "read", "toolset:bitbucket_code"},
    annotations={"title": "Get Commit", "readOnlyHint": True},
)
async def get_commit(
    ctx: Context,
    project_key: ProjectKeyParam,
    repo_slug: RepoSlugParam,
    commit_id: CommitIdParam,
) -> str:
    """Get a commit with its message, author, parents and changed files.

    Args:
        ctx: The FastMCP context.
        project_key: Project key.
        repo_slug: Repository slug.
        commit_id: Commit hash.

    Returns:
        JSON commit with ``changes`` (path, type, src_path for moves/copies).
    """
    fetcher = await get_bitbucket_fetcher(ctx)
    commit = fetcher.get_commit(project_key, repo_slug, commit_id)
    return _to_json(commit.to_simplified_dict())


DiffPathParam = Annotated[
    str | None,
    Field(
        description=(
            "(Optional) Only the diff of this file. Use it when the full diff "
            "is truncated."
        ),
        default=None,
    ),
]
ContextLinesParam = Annotated[
    int | None,
    Field(
        description="(Optional) Lines of context around each change (0-100).",
        default=None,
        ge=0,
        le=100,
    ),
]
IgnoreWhitespaceParam = Annotated[
    bool,
    Field(description="Ignore whitespace-only changes.", default=False),
]


@bitbucket_mcp.tool(
    tags={"bitbucket", "read", "toolset:bitbucket_code"},
    annotations={"title": "Get Commit Diff", "readOnlyHint": True},
)
async def get_commit_diff(
    ctx: Context,
    project_key: ProjectKeyParam,
    repo_slug: RepoSlugParam,
    commit_id: CommitIdParam,
    path: DiffPathParam = None,
    context_lines: ContextLinesParam = None,
    ignore_whitespace: IgnoreWhitespaceParam = False,
) -> str:
    """Get what a commit changed, as unified diff text.

    Args:
        ctx: The FastMCP context.
        project_key: Project key.
        repo_slug: Repository slug.
        commit_id: Commit hash.
        path: Only this file.
        context_lines: Lines of context around changes.
        ignore_whitespace: Ignore whitespace-only changes.

    Returns:
        A ``#`` header line (plus a truncation notice when Bitbucket cut the
        diff) followed by unified diff text.
    """
    fetcher = await get_bitbucket_fetcher(ctx)
    return fetcher.get_commit_diff(
        project_key,
        repo_slug,
        commit_id,
        path=path,
        context_lines=context_lines,
        ignore_whitespace=ignore_whitespace,
    )
