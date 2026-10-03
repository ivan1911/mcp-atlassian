"""Toolset definitions and filtering utilities for MCP Atlassian.

Groups the MCP tools into named toolsets controlled via the TOOLSETS env var.
Supports 'all', 'default', and comma-separated toolset names.
"""

import logging
import os
from dataclasses import dataclass

logger = logging.getLogger(__name__)

TOOLSET_TAG_PREFIX = "toolset:"


@dataclass(frozen=True)
class ToolsetDefinition:
    """Metadata for a named toolset group."""

    name: str
    description: str
    default: bool
    # Enabled only when named in TOOLSETS; never via unset/empty/'all'/'default'.
    explicit_only: bool = False


# --- Jira toolsets (16) ---

JIRA_TOOLSETS: dict[str, ToolsetDefinition] = {
    "jira_issues": ToolsetDefinition(
        name="jira_issues",
        description="Core issue operations: CRUD, search, batch, changelogs",
        default=True,
    ),
    "jira_fields": ToolsetDefinition(
        name="jira_fields",
        description="Field search and option retrieval",
        default=True,
    ),
    "jira_comments": ToolsetDefinition(
        name="jira_comments",
        description="Issue comment operations",
        default=True,
    ),
    "jira_transitions": ToolsetDefinition(
        name="jira_transitions",
        description="Workflow transition operations",
        default=True,
    ),
    "jira_projects": ToolsetDefinition(
        name="jira_projects",
        description="Project, version, and component management",
        default=False,
    ),
    "jira_agile": ToolsetDefinition(
        name="jira_agile",
        description="Agile boards, sprints, and related operations",
        default=False,
    ),
    "jira_links": ToolsetDefinition(
        name="jira_links",
        description="Issue links, epic links, and remote links",
        default=False,
    ),
    "jira_worklog": ToolsetDefinition(
        name="jira_worklog",
        description="Time tracking and worklog operations",
        default=False,
    ),
    "jira_attachments": ToolsetDefinition(
        name="jira_attachments",
        description="Attachment download and image retrieval",
        default=False,
    ),
    "jira_users": ToolsetDefinition(
        name="jira_users",
        description="User profile operations",
        default=False,
    ),
    "jira_watchers": ToolsetDefinition(
        name="jira_watchers",
        description="Issue watcher operations",
        default=False,
    ),
    "jira_service_desk": ToolsetDefinition(
        name="jira_service_desk",
        description="Jira Service Management requests, queues, and service desks",
        default=False,
    ),
    "jira_forms": ToolsetDefinition(
        name="jira_forms",
        description="ProForma form operations",
        default=False,
    ),
    "jira_metrics": ToolsetDefinition(
        name="jira_metrics",
        description="Issue dates and SLA metrics",
        default=False,
    ),
    "jira_development": ToolsetDefinition(
        name="jira_development",
        description="Development info (branches, PRs, commits)",
        default=False,
    ),
    "jira_project_analysis": ToolsetDefinition(
        name="jira_project_analysis",
        description="Project epic hierarchy and cross-project dependencies",
        default=False,
    ),
}

# --- Confluence toolsets (8) ---

CONFLUENCE_TOOLSETS: dict[str, ToolsetDefinition] = {
    "confluence_pages": ToolsetDefinition(
        name="confluence_pages",
        description="Page CRUD, search, children, and history",
        default=True,
    ),
    "confluence_comments": ToolsetDefinition(
        name="confluence_comments",
        description="Page comment operations",
        default=True,
    ),
    "confluence_labels": ToolsetDefinition(
        name="confluence_labels",
        description="Page label operations",
        default=False,
    ),
    "confluence_users": ToolsetDefinition(
        name="confluence_users",
        description="User search operations",
        default=False,
    ),
    "confluence_analytics": ToolsetDefinition(
        name="confluence_analytics",
        description="Page view analytics",
        default=False,
    ),
    "confluence_attachments": ToolsetDefinition(
        name="confluence_attachments",
        description="Attachment upload, download, and management",
        default=False,
    ),
    "confluence_templates": ToolsetDefinition(
        name="confluence_templates",
        description="Cloud page template listing and page creation from templates",
        default=False,
    ),
    "confluence_permissions": ToolsetDefinition(
        name="confluence_permissions",
        description="Content and space permission checking",
        default=False,
    ),
}

# --- Bitbucket Data Center toolsets ---

BITBUCKET_TOOLSETS: dict[str, ToolsetDefinition] = {
    "bitbucket_projects": ToolsetDefinition(
        name="bitbucket_projects",
        description="Bitbucket projects and repositories",
        default=True,
    ),
    "bitbucket_code": ToolsetDefinition(
        name="bitbucket_code",
        description="Bitbucket files, branches, tags, commits and commit diffs",
        default=True,
    ),
    "bitbucket_pull_requests": ToolsetDefinition(
        name="bitbucket_pull_requests",
        description="Find and read Bitbucket pull requests, diffs and activity",
        default=True,
    ),
    "bitbucket_pr_review": ToolsetDefinition(
        name="bitbucket_pr_review",
        description="Review Bitbucket pull requests: comments, tasks, reviewer status",
        default=True,
    ),
    "bitbucket_pr_manage": ToolsetDefinition(
        name="bitbucket_pr_manage",
        description="Create, update, merge, decline, reopen pull requests; branches",
        default=True,
    ),
    "bitbucket_search": ToolsetDefinition(
        name="bitbucket_search",
        description="Bitbucket code search (unofficial endpoint, opt-in)",
        default=False,
    ),
    "bitbucket_destructive": ToolsetDefinition(
        name="bitbucket_destructive",
        description="Delete Bitbucket pull requests and branches (named opt-in only)",
        default=False,
        explicit_only=True,
    ),
}

# --- Combined registry ---

ALL_TOOLSETS: dict[str, ToolsetDefinition] = {
    **JIRA_TOOLSETS,
    **CONFLUENCE_TOOLSETS,
    **BITBUCKET_TOOLSETS,
    "legacy": ToolsetDefinition(
        name="legacy",
        description="Deprecated tools retained for migration compatibility",
        default=False,
    ),
}

DEFAULT_TOOLSETS: set[str] = {
    name
    for name, defn in ALL_TOOLSETS.items()
    if defn.default and not defn.explicit_only
}


def _implicit_toolsets() -> set[str]:
    """Return every toolset that 'all' (or an unset TOOLSETS) enables."""
    return {name for name, defn in ALL_TOOLSETS.items() if not defn.explicit_only}


def _warn_default_will_change() -> None:
    logger.warning(
        "TOOLSETS is not set — currently defaults to all toolsets. "
        f"In v0.22.0, the default will change to {len(DEFAULT_TOOLSETS)} core "
        "toolsets only. Set TOOLSETS=all explicitly to preserve current behavior."
    )


def get_enabled_toolsets() -> set[str]:
    """Parse the TOOLSETS env var into a set of enabled toolset names.

    Supports keywords 'all' (every toolset not marked ``explicit_only``) and
    'default' (DEFAULT_TOOLSETS), plus comma-separated specific toolset names.
    Case-insensitive for keywords.

    When TOOLSETS is unset or empty, returns all toolsets with a deprecation
    warning. In v0.22.0 the default will change to DEFAULT_TOOLSETS.
    Set ``TOOLSETS=all`` explicitly to preserve current behavior.

    Toolsets marked ``explicit_only`` are never enabled by an unset TOOLSETS,
    'all' or 'default'; they must be named, e.g. ``TOOLSETS=all,<name>``.

    Returns:
        A set of valid toolset names. Defaults to all toolsets when unset.
        Unknown names are silently dropped with a warning. If only unknown
        names are given, returns an empty set (fail-closed).

    Examples:
        TOOLSETS unset -> all toolsets (with deprecation warning)
        TOOLSETS="" -> all toolsets (with deprecation warning)
        TOOLSETS="all" -> all toolset names
        TOOLSETS="default" -> DEFAULT_TOOLSETS
        TOOLSETS="default,jira_agile" -> defaults + jira_agile
        TOOLSETS="typo_name" -> set() (fail-closed)
    """
    toolsets_str = os.getenv("TOOLSETS")
    if not toolsets_str:
        logger.info("TOOLSETS not set — all toolsets enabled.")
        _warn_default_will_change()
        return _implicit_toolsets()

    # Split by comma and strip whitespace, filter empty tokens
    tokens = [t.strip() for t in toolsets_str.split(",")]
    tokens = [t for t in tokens if t]

    if not tokens:
        logger.info("TOOLSETS empty — all toolsets enabled.")
        _warn_default_will_change()
        return _implicit_toolsets()

    result: set[str] = set()

    for token in tokens:
        normalized = token.lower()
        if normalized == "all":
            logger.info("TOOLSETS: 'all' keyword — enabling all toolsets.")
            result |= _implicit_toolsets()
        elif normalized == "default":
            logger.info("TOOLSETS: 'default' keyword — adding default toolsets.")
            result |= DEFAULT_TOOLSETS
        elif token in ALL_TOOLSETS:
            result.add(token)
        else:
            logger.warning(f"TOOLSETS: unknown toolset name '{token}' — ignoring.")

    if result:
        logger.info(f"TOOLSETS: enabled toolsets: {sorted(result)}")
    else:
        logger.warning(
            "TOOLSETS: no valid toolset names found — all tools will be blocked (fail-closed)."
        )

    return result


def should_include_tool_by_toolset(
    tool_tags: set[str], enabled_toolsets: set[str] | None
) -> bool:
    """Check if a tool should be included based on toolset filtering.

    Args:
        tool_tags: The tool's tag set (e.g. {"jira", "read", "toolset:jira_issues"}).
        enabled_toolsets: Set of enabled toolset names, or None to include all tools.

    Returns:
        True if the tool should be included, False otherwise.
        Tools without a toolset tag are always included (graceful fallback).
    """
    if enabled_toolsets is None:
        return True

    toolset_name = get_toolset_tag(tool_tags)
    if toolset_name is None:
        logger.warning(
            f"Tool has no toolset tag in {tool_tags} — including by default."
        )
        return True

    return toolset_name in enabled_toolsets


def get_toolset_tag(tags: set[str]) -> str | None:
    """Extract the toolset name from a tool's tag set.

    Args:
        tags: The tool's tag set.

    Returns:
        The toolset name (without prefix) if found, None otherwise.
    """
    for tag in tags:
        if tag.startswith(TOOLSET_TAG_PREFIX):
            return tag[len(TOOLSET_TAG_PREFIX) :]
    return None
