"""Bitbucket Data Center FastMCP server instance and tool definitions."""

import json
import logging
from typing import Annotated, Any, Literal

from fastmcp import Context
from pydantic import Field

from mcp_atlassian.servers.dependencies import get_bitbucket_fetcher
from mcp_atlassian.servers.error_handling import ErrorPreservingFastMCP
from mcp_atlassian.utils.decorators import check_write_access

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


PullRequestIdParam = Annotated[int, Field(description="Pull request id.", ge=1)]
PrStateParam = Annotated[
    Literal["OPEN", "MERGED", "DECLINED", "ALL"],
    Field(description="Pull request state.", default="OPEN"),
]


@bitbucket_mcp.tool(
    tags={"bitbucket", "read", "toolset:bitbucket_pull_requests"},
    annotations={"title": "List Pull Requests", "readOnlyHint": True},
)
async def list_pull_requests(
    ctx: Context,
    project_key: ProjectKeyParam,
    repo_slug: RepoSlugParam,
    state: PrStateParam = "OPEN",
    direction: Annotated[
        Literal["INCOMING", "OUTGOING"],
        Field(
            description=(
                "INCOMING: pull requests into this repository; OUTGOING: from it."
            ),
            default="INCOMING",
        ),
    ] = "INCOMING",
    target_branch: Annotated[
        str | None,
        Field(
            description=(
                "(Optional) Only pull requests into this branch (from it when "
                "direction is OUTGOING)."
            ),
            default=None,
        ),
    ] = None,
    author: Annotated[
        str | None,
        Field(description="(Optional) Author user slug.", default=None),
    ] = None,
    reviewer: Annotated[
        str | None,
        Field(description="(Optional) Reviewer user slug.", default=None),
    ] = None,
    text: Annotated[
        str | None,
        Field(
            description="(Optional) Text contained in the title or description.",
            default=None,
        ),
    ] = None,
    start: StartParam = 0,
    limit: LimitParam = 25,
) -> str:
    """List pull requests of a repository, filtered by state, people and text.

    Args:
        ctx: The FastMCP context.
        project_key: Project key.
        repo_slug: Repository slug.
        state: Pull request state.
        direction: INCOMING or OUTGOING.
        target_branch: Branch filter.
        author: Author slug.
        reviewer: Reviewer slug.
        text: Title/description text filter.
        start: Index of the first pull request (paging).
        limit: Maximum number of pull requests.

    Returns:
        JSON with ``values`` (pull requests) and paging fields.
    """
    fetcher = await get_bitbucket_fetcher(ctx)
    page = fetcher.list_pull_requests(
        project_key,
        repo_slug,
        state=state,
        direction=direction,
        target_branch=target_branch,
        author=author,
        reviewer=reviewer,
        text=text,
        start=start,
        limit=limit,
    )
    return _to_json(page.to_simplified_dict())


@bitbucket_mcp.tool(
    tags={"bitbucket", "read", "toolset:bitbucket_pull_requests"},
    annotations={"title": "Get My Pull Requests", "readOnlyHint": True},
)
async def get_my_pull_requests(
    ctx: Context,
    role: Annotated[
        Literal["AUTHOR", "REVIEWER", "PARTICIPANT"] | None,
        Field(
            description="(Optional) Only pull requests where I have this role.",
            default=None,
        ),
    ] = None,
    state: PrStateParam = "OPEN",
    participant_status: Annotated[
        Literal["APPROVED", "UNAPPROVED", "NEEDS_WORK"] | None,
        Field(
            description="(Optional) Only pull requests where my reviewer status is this.",
            default=None,
        ),
    ] = None,
    start: StartParam = 0,
    limit: LimitParam = 25,
) -> str:
    """List my pull requests across repositories (the Bitbucket dashboard).

    Use role=REVIEWER with participant_status=UNAPPROVED to find reviews
    waiting on me.

    Args:
        ctx: The FastMCP context.
        role: AUTHOR, REVIEWER or PARTICIPANT.
        state: Pull request state.
        participant_status: My reviewer status filter.
        start: Index of the first pull request (paging).
        limit: Maximum number of pull requests.

    Returns:
        JSON with ``values`` (pull requests) and paging fields.
    """
    fetcher = await get_bitbucket_fetcher(ctx)
    page = fetcher.get_my_pull_requests(
        role=role,
        state=state,
        participant_status=participant_status,
        start=start,
        limit=limit,
    )
    return _to_json(page.to_simplified_dict())


@bitbucket_mcp.tool(
    tags={"bitbucket", "read", "toolset:bitbucket_pull_requests"},
    annotations={"title": "Get Pull Request", "readOnlyHint": True},
)
async def get_pull_request(
    ctx: Context,
    project_key: ProjectKeyParam,
    repo_slug: RepoSlugParam,
    pull_request_id: PullRequestIdParam,
    include_merge_status: Annotated[
        bool,
        Field(
            description=(
                "Also check whether it can be merged and what blocks it "
                "(conflicts, vetoes such as missing approvals or open tasks)."
            ),
            default=False,
        ),
    ] = False,
) -> str:
    """Get a pull request: description, branches, author, reviewers, version.

    Args:
        ctx: The FastMCP context.
        project_key: Project key.
        repo_slug: Repository slug.
        pull_request_id: Pull request id.
        include_merge_status: Include mergeability.

    Returns:
        JSON pull request including ``version`` (pass it back to write tools)
        and reviewers with their reviewer status.
    """
    fetcher = await get_bitbucket_fetcher(ctx)
    pull_request = fetcher.get_pull_request(
        project_key,
        repo_slug,
        pull_request_id,
        include_merge_status=include_merge_status,
    )
    return _to_json(pull_request.to_simplified_dict())


@bitbucket_mcp.tool(
    tags={"bitbucket", "read", "toolset:bitbucket_pull_requests"},
    annotations={"title": "Get Pull Request Changes", "readOnlyHint": True},
)
async def get_pull_request_changes(
    ctx: Context,
    project_key: ProjectKeyParam,
    repo_slug: RepoSlugParam,
    pull_request_id: PullRequestIdParam,
    start: StartParam = 0,
    limit: Annotated[
        int,
        Field(description="Maximum number of files (1-500)", default=100, ge=1, le=500),
    ] = 100,
) -> str:
    """List the files a pull request changes, with their change type.

    Args:
        ctx: The FastMCP context.
        project_key: Project key.
        repo_slug: Repository slug.
        pull_request_id: Pull request id.
        start: Index of the first file (paging).
        limit: Maximum number of files.

    Returns:
        JSON with ``values`` (path, type, src_path for moves) and paging.
    """
    fetcher = await get_bitbucket_fetcher(ctx)
    page = fetcher.get_pull_request_changes(
        project_key, repo_slug, pull_request_id, start=start, limit=limit
    )
    return _to_json(page.to_simplified_dict())


@bitbucket_mcp.tool(
    tags={"bitbucket", "read", "toolset:bitbucket_pull_requests"},
    annotations={"title": "Get Pull Request Commits", "readOnlyHint": True},
)
async def get_pull_request_commits(
    ctx: Context,
    project_key: ProjectKeyParam,
    repo_slug: RepoSlugParam,
    pull_request_id: PullRequestIdParam,
    start: StartParam = 0,
    limit: LimitParam = 25,
) -> str:
    """List the commits of a pull request, newest first.

    Args:
        ctx: The FastMCP context.
        project_key: Project key.
        repo_slug: Repository slug.
        pull_request_id: Pull request id.
        start: Index of the first commit (paging).
        limit: Maximum number of commits.

    Returns:
        JSON with ``values`` (commits) and paging fields.
    """
    fetcher = await get_bitbucket_fetcher(ctx)
    page = fetcher.get_pull_request_commits(
        project_key, repo_slug, pull_request_id, start=start, limit=limit
    )
    return _to_json(page.to_simplified_dict())


@bitbucket_mcp.tool(
    tags={"bitbucket", "read", "toolset:bitbucket_pull_requests"},
    annotations={"title": "Get Pull Request Diff", "readOnlyHint": True},
)
async def get_pull_request_diff(
    ctx: Context,
    project_key: ProjectKeyParam,
    repo_slug: RepoSlugParam,
    pull_request_id: PullRequestIdParam,
    path: DiffPathParam = None,
    context_lines: ContextLinesParam = None,
    ignore_whitespace: IgnoreWhitespaceParam = False,
) -> str:
    """Get a pull request's change as unified diff text, whole or per file.

    Hunk headers give the line numbers needed for inline comments: '+' lines
    are ADDED (new file side), '-' lines REMOVED (old side), ' ' CONTEXT.

    Args:
        ctx: The FastMCP context.
        project_key: Project key.
        repo_slug: Repository slug.
        pull_request_id: Pull request id.
        path: Only this file.
        context_lines: Lines of context around changes.
        ignore_whitespace: Ignore whitespace-only changes.

    Returns:
        A ``#`` header line (plus a truncation notice when Bitbucket cut the
        diff; then review file by file) followed by unified diff text.
    """
    fetcher = await get_bitbucket_fetcher(ctx)
    return fetcher.get_pull_request_diff(
        project_key,
        repo_slug,
        pull_request_id,
        path=path,
        context_lines=context_lines,
        ignore_whitespace=ignore_whitespace,
    )


@bitbucket_mcp.tool(
    tags={"bitbucket", "read", "toolset:bitbucket_pull_requests"},
    annotations={"title": "Get Pull Request Activity", "readOnlyHint": True},
)
async def get_pull_request_activity(
    ctx: Context,
    project_key: ProjectKeyParam,
    repo_slug: RepoSlugParam,
    pull_request_id: PullRequestIdParam,
    start: StartParam = 0,
    limit: LimitParam = 25,
) -> str:
    """Get pull request activity: comment threads, tasks, approvals, updates.

    Comments include replies, inline anchors (path, line, line_type,
    file_type), ``is_task`` and task ``state``. Newest first.

    Args:
        ctx: The FastMCP context.
        project_key: Project key.
        repo_slug: Repository slug.
        pull_request_id: Pull request id.
        start: Index of the first activity (paging).
        limit: Maximum number of activities.

    Returns:
        JSON with ``values`` (activities) and paging fields.
    """
    fetcher = await get_bitbucket_fetcher(ctx)
    page = fetcher.get_pull_request_activity(
        project_key, repo_slug, pull_request_id, start=start, limit=limit
    )
    return _to_json(page.to_simplified_dict())


@bitbucket_mcp.tool(
    tags={"bitbucket", "write", "toolset:bitbucket_pr_review"},
    annotations={"title": "Add Pull Request Comment", "destructiveHint": False},
)
@check_write_access
async def add_pull_request_comment(
    ctx: Context,
    project_key: ProjectKeyParam,
    repo_slug: RepoSlugParam,
    pull_request_id: PullRequestIdParam,
    text: Annotated[
        str, Field(description="Comment text in Bitbucket markdown.", min_length=1)
    ],
    path: Annotated[
        str | None,
        Field(
            description=(
                "(Optional) File path: comments on the file, or on a line of it "
                "together with 'line'."
            ),
            default=None,
        ),
    ] = None,
    line: Annotated[
        int | None,
        Field(
            description=(
                "(Optional) Line number in the diff for an inline comment: the "
                "new-file line for ADDED/CONTEXT lines, the old-file line for "
                "REMOVED lines (see the hunk headers of the pull request diff)."
            ),
            default=None,
            ge=1,
        ),
    ] = None,
    line_type: Annotated[
        Literal["ADDED", "REMOVED", "CONTEXT"] | None,
        Field(
            description="(Optional) Kind of the commented diff line (default ADDED).",
            default=None,
        ),
    ] = None,
    file_type: Annotated[
        Literal["FROM", "TO"] | None,
        Field(
            description=(
                "(Optional) Diff side: FROM (old) or TO (new). Inferred from "
                "line_type when omitted."
            ),
            default=None,
        ),
    ] = None,
    parent_comment_id: Annotated[
        int | None,
        Field(description="(Optional) Reply to this comment id.", default=None),
    ] = None,
    as_task: Annotated[
        bool,
        Field(
            description="Create a task: a blocking comment that must be resolved.",
            default=False,
        ),
    ] = False,
) -> str:
    """Comment on a pull request: general, file, inline line, reply, or task.

    Args:
        ctx: The FastMCP context.
        project_key: Project key.
        repo_slug: Repository slug.
        pull_request_id: Pull request id.
        text: Comment text.
        path: File path.
        line: Diff line number.
        line_type: ADDED, REMOVED or CONTEXT.
        file_type: FROM or TO.
        parent_comment_id: Comment to reply to.
        as_task: Create a task.

    Returns:
        JSON of the created comment.
    """
    fetcher = await get_bitbucket_fetcher(ctx)
    comment = fetcher.add_pull_request_comment(
        project_key,
        repo_slug,
        pull_request_id,
        text,
        path=path,
        line=line,
        line_type=line_type,
        file_type=file_type,
        parent_comment_id=parent_comment_id,
        as_task=as_task,
    )
    return _to_json(comment.to_simplified_dict())


@bitbucket_mcp.tool(
    tags={"bitbucket", "write", "toolset:bitbucket_pr_review"},
    annotations={"title": "Update Pull Request Comment", "destructiveHint": False},
)
@check_write_access
async def update_pull_request_comment(
    ctx: Context,
    project_key: ProjectKeyParam,
    repo_slug: RepoSlugParam,
    pull_request_id: PullRequestIdParam,
    comment_id: Annotated[int, Field(description="Comment or task id.", ge=1)],
    text: Annotated[
        str | None,
        Field(description="(Optional) New comment text.", default=None, min_length=1),
    ] = None,
    task_state: Annotated[
        Literal["open", "resolved"] | None,
        Field(
            description="(Optional) For a task: 'resolved' or 'open' (reopen).",
            default=None,
        ),
    ] = None,
) -> str:
    """Edit a pull request comment's text, or resolve / reopen a task.

    Args:
        ctx: The FastMCP context.
        project_key: Project key.
        repo_slug: Repository slug.
        pull_request_id: Pull request id.
        comment_id: Comment id.
        text: New text.
        task_state: New task state.

    Returns:
        JSON of the updated comment.
    """
    fetcher = await get_bitbucket_fetcher(ctx)
    comment = fetcher.update_pull_request_comment(
        project_key,
        repo_slug,
        pull_request_id,
        comment_id,
        text=text,
        task_state=task_state,
    )
    return _to_json(comment.to_simplified_dict())


VersionParam = Annotated[
    int | None,
    Field(
        description=(
            "(Optional) Pull request version from bitbucket_get_pull_request. "
            "Pass it to have the change refused if the pull request changed "
            "since you read it; omit it to use the current version."
        ),
        default=None,
        ge=0,
    ),
]


@bitbucket_mcp.tool(
    tags={"bitbucket", "write", "toolset:bitbucket_pr_manage"},
    annotations={"title": "Create Pull Request", "destructiveHint": False},
)
@check_write_access
async def create_pull_request(
    ctx: Context,
    project_key: ProjectKeyParam,
    repo_slug: RepoSlugParam,
    title: Annotated[str, Field(description="Pull request title.", min_length=1)],
    source_branch: Annotated[
        str, Field(description="Branch with the changes, e.g. 'feature/login'.")
    ],
    target_branch: Annotated[
        str | None,
        Field(
            description=(
                "(Optional) Branch to merge into. Defaults to the repository's "
                "default branch."
            ),
            default=None,
        ),
    ] = None,
    description: Annotated[
        str | None,
        Field(description="(Optional) Description in markdown.", default=None),
    ] = None,
    reviewers: Annotated[
        list[str] | None,
        Field(
            description=(
                "(Optional) Reviewer usernames. When omitted, the repository's "
                "default reviewers for this branch pair are added."
            ),
            default=None,
        ),
    ] = None,
    draft: Annotated[
        bool, Field(description="Create as a draft pull request.", default=False)
    ] = False,
) -> str:
    """Create a pull request from a source branch to a target branch.

    Args:
        ctx: The FastMCP context.
        project_key: Project key.
        repo_slug: Repository slug.
        title: Title.
        source_branch: Source branch.
        target_branch: Target branch.
        description: Description.
        reviewers: Reviewer usernames.
        draft: Draft flag.

    Returns:
        JSON of the created pull request.
    """
    fetcher = await get_bitbucket_fetcher(ctx)
    pull_request = fetcher.create_pull_request(
        project_key,
        repo_slug,
        title,
        source_branch,
        target_branch=target_branch,
        description=description,
        reviewers=reviewers,
        draft=draft,
    )
    return _to_json(pull_request.to_simplified_dict())


@bitbucket_mcp.tool(
    tags={"bitbucket", "write", "toolset:bitbucket_pr_manage"},
    annotations={"title": "Update Pull Request", "destructiveHint": False},
)
@check_write_access
async def update_pull_request(
    ctx: Context,
    project_key: ProjectKeyParam,
    repo_slug: RepoSlugParam,
    pull_request_id: PullRequestIdParam,
    title: Annotated[
        str | None, Field(description="(Optional) New title.", default=None)
    ] = None,
    description: Annotated[
        str | None, Field(description="(Optional) New description.", default=None)
    ] = None,
    reviewers: Annotated[
        list[str] | None,
        Field(
            description=(
                "(Optional) Full new list of reviewer usernames (replaces the "
                "current reviewers). Omit to keep them."
            ),
            default=None,
        ),
    ] = None,
    target_branch: Annotated[
        str | None, Field(description="(Optional) New target branch.", default=None)
    ] = None,
    draft: Annotated[
        bool | None,
        Field(description="(Optional) Set or clear the draft flag.", default=None),
    ] = None,
    version: VersionParam = None,
) -> str:
    """Update a pull request's title, description, reviewers, target or draft flag.

    Fields that are not given keep their current values.

    Args:
        ctx: The FastMCP context.
        project_key: Project key.
        repo_slug: Repository slug.
        pull_request_id: Pull request id.
        title: New title.
        description: New description.
        reviewers: New reviewer list.
        target_branch: New target branch.
        draft: Draft flag.
        version: Expected pull request version.

    Returns:
        JSON of the updated pull request.
    """
    fetcher = await get_bitbucket_fetcher(ctx)
    pull_request = fetcher.update_pull_request(
        project_key,
        repo_slug,
        pull_request_id,
        title=title,
        description=description,
        reviewers=reviewers,
        target_branch=target_branch,
        draft=draft,
        version=version,
    )
    return _to_json(pull_request.to_simplified_dict())


@bitbucket_mcp.tool(
    tags={"bitbucket", "write", "toolset:bitbucket_pr_manage"},
    annotations={"title": "Merge Pull Request", "destructiveHint": True},
)
@check_write_access
async def merge_pull_request(
    ctx: Context,
    project_key: ProjectKeyParam,
    repo_slug: RepoSlugParam,
    pull_request_id: PullRequestIdParam,
    strategy: Annotated[
        str | None,
        Field(
            description=(
                "(Optional) Merge strategy id configured for the repository, "
                "e.g. 'no-ff', 'ff', 'ff-only', 'squash', 'squash-ff-only', "
                "'rebase-no-ff', 'rebase-ff-only'. Defaults to the repository's."
            ),
            default=None,
        ),
    ] = None,
    message: Annotated[
        str | None,
        Field(description="(Optional) Merge commit message.", default=None),
    ] = None,
    version: VersionParam = None,
) -> str:
    """Merge a pull request. If Bitbucket refuses, the error lists why.

    Check first with bitbucket_get_pull_request(include_merge_status=true).

    Args:
        ctx: The FastMCP context.
        project_key: Project key.
        repo_slug: Repository slug.
        pull_request_id: Pull request id.
        strategy: Merge strategy id.
        message: Merge commit message.
        version: Expected pull request version.

    Returns:
        JSON of the merged pull request.
    """
    fetcher = await get_bitbucket_fetcher(ctx)
    pull_request = fetcher.merge_pull_request(
        project_key,
        repo_slug,
        pull_request_id,
        strategy=strategy,
        message=message,
        version=version,
    )
    return _to_json(pull_request.to_simplified_dict())


@bitbucket_mcp.tool(
    tags={"bitbucket", "write", "toolset:bitbucket_pr_manage"},
    annotations={"title": "Decline Pull Request", "destructiveHint": False},
)
@check_write_access
async def decline_pull_request(
    ctx: Context,
    project_key: ProjectKeyParam,
    repo_slug: RepoSlugParam,
    pull_request_id: PullRequestIdParam,
    comment: Annotated[
        str | None,
        Field(description="(Optional) Reason, added as a comment.", default=None),
    ] = None,
    version: VersionParam = None,
) -> str:
    """Decline a pull request (it can be reopened later).

    Args:
        ctx: The FastMCP context.
        project_key: Project key.
        repo_slug: Repository slug.
        pull_request_id: Pull request id.
        comment: Reason.
        version: Expected pull request version.

    Returns:
        JSON of the declined pull request.
    """
    fetcher = await get_bitbucket_fetcher(ctx)
    pull_request = fetcher.decline_pull_request(
        project_key, repo_slug, pull_request_id, comment=comment, version=version
    )
    return _to_json(pull_request.to_simplified_dict())


@bitbucket_mcp.tool(
    tags={"bitbucket", "write", "toolset:bitbucket_pr_manage"},
    annotations={"title": "Reopen Pull Request", "destructiveHint": False},
)
@check_write_access
async def reopen_pull_request(
    ctx: Context,
    project_key: ProjectKeyParam,
    repo_slug: RepoSlugParam,
    pull_request_id: PullRequestIdParam,
    version: VersionParam = None,
) -> str:
    """Reopen a declined pull request.

    Args:
        ctx: The FastMCP context.
        project_key: Project key.
        repo_slug: Repository slug.
        pull_request_id: Pull request id.
        version: Expected pull request version.

    Returns:
        JSON of the reopened pull request.
    """
    fetcher = await get_bitbucket_fetcher(ctx)
    pull_request = fetcher.reopen_pull_request(
        project_key, repo_slug, pull_request_id, version=version
    )
    return _to_json(pull_request.to_simplified_dict())


@bitbucket_mcp.tool(
    tags={"bitbucket", "write", "toolset:bitbucket_pr_manage"},
    annotations={"title": "Create Branch", "destructiveHint": False},
)
@check_write_access
async def create_branch(
    ctx: Context,
    project_key: ProjectKeyParam,
    repo_slug: RepoSlugParam,
    name: Annotated[str, Field(description="New branch name, e.g. 'fix/login'.")],
    start_point: Annotated[
        str,
        Field(description="Branch, tag or commit hash to create the branch from."),
    ],
) -> str:
    """Create a branch from a branch, tag or commit.

    Args:
        ctx: The FastMCP context.
        project_key: Project key.
        repo_slug: Repository slug.
        name: Branch name.
        start_point: Branch, tag or commit.

    Returns:
        JSON of the created branch.
    """
    fetcher = await get_bitbucket_fetcher(ctx)
    branch = fetcher.create_branch(project_key, repo_slug, name, start_point)
    return _to_json(branch.to_simplified_dict())
