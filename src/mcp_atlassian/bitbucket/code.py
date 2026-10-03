"""Bitbucket repository content: files, branches, tags and commits."""

from typing import Any

from ..models.bitbucket import (
    BitbucketChange,
    BitbucketCommit,
    BitbucketPage,
    BitbucketRef,
)
from .client import BitbucketClient, file_path, segment

DEFAULT_FILE_LINE_LIMIT = 1000
# Bytes inspected when deciding whether a file is binary.
_BINARY_SNIFF_BYTES = 8192


def _join(base: str, name: str) -> str:
    base = base.strip("/")
    return f"{base}/{name}" if base else name


class CodeMixin(BitbucketClient):
    """Read repository content at any branch, tag or commit."""

    def list_files(
        self,
        project_key: str,
        repo_slug: str,
        *,
        path: str = "",
        at: str | None = None,
        recursive: bool = False,
        start: int = 0,
        limit: int = 25,
    ) -> BitbucketPage:
        """List a directory, or every file below it when ``recursive``.

        Args:
            project_key: Project key.
            repo_slug: Repository slug.
            path: Directory path; empty for the repository root.
            at: Branch, tag or commit (default: the default branch).
            recursive: List all files below ``path`` instead of one level.
            start: Page start.
            limit: Page size.

        Returns:
            A page of entries ``{"path", "type", "size"?}`` with paths relative
            to the repository root.

        Raises:
            ValueError: If ``path`` is a file rather than a directory.
        """
        repo = self._repo_path(project_key, repo_slug)
        suffix = f"/{file_path(path)}" if path.strip("/") else ""
        params = {"at": at}
        if recursive:
            data = self._get_page(
                f"{repo}/files{suffix}", start=start, limit=limit, params=params
            )
            page = BitbucketPage.from_api_response(data)
            page.values = [
                {"path": _join(path, str(name)), "type": "file"} for name in page.values
            ]
            return page

        data = self._get_page(
            f"{repo}/browse{suffix}", start=start, limit=limit, params=params
        )
        children = data.get("children") if isinstance(data, dict) else None
        if not isinstance(children, dict):
            raise ValueError(
                f"'{path}' is a file, not a directory; "
                "use bitbucket_get_file_content to read it."
            )
        page = BitbucketPage.from_api_response(children)
        entries = []
        for child in page.values:
            entry: dict[str, Any] = {
                "path": _join(path, str((child.get("path") or {}).get("toString", ""))),
                "type": str(child.get("type", "")).lower(),
            }
            if child.get("size") is not None:
                entry["size"] = child["size"]
            entries.append(entry)
        page.values = entries
        return page

    def get_file_content(
        self,
        project_key: str,
        repo_slug: str,
        path: str,
        *,
        at: str | None = None,
        start_line: int = 1,
        limit: int = DEFAULT_FILE_LINE_LIMIT,
    ) -> dict[str, Any]:
        """Read a line range of a file.

        Args:
            project_key: Project key.
            repo_slug: Repository slug.
            path: File path.
            at: Branch, tag or commit (default: the default branch).
            start_line: First line to return (1-based).
            limit: Maximum number of lines.

        Returns:
            ``path``, ``at``, ``start_line``, ``end_line``, ``total_lines``,
            ``truncated`` and ``content``; binary files return ``binary`` and
            ``size_bytes`` instead of content.
        """
        repo = self._repo_path(project_key, repo_slug)
        response = self._request(
            "GET", f"{repo}/raw/{file_path(path)}", params={"at": at}, accept="*/*"
        )
        raw = response.content
        result: dict[str, Any] = {"path": path.strip("/")}
        if at:
            result["at"] = at
        text: str | None = None
        if b"\x00" not in raw[:_BINARY_SNIFF_BYTES]:
            try:
                text = raw.decode("utf-8")
            except UnicodeDecodeError:
                text = None
        if text is None:
            return {**result, "binary": True, "size_bytes": len(raw)}

        lines = text.splitlines(keepends=True)
        first = max(start_line, 1)
        selected = lines[first - 1 : first - 1 + limit]
        end_line = first - 1 + len(selected)
        return {
            **result,
            "start_line": first,
            "end_line": end_line,
            "total_lines": len(lines),
            "truncated": end_line < len(lines),
            "content": "".join(selected),
        }

    def list_branches(
        self,
        project_key: str,
        repo_slug: str,
        *,
        filter_text: str | None = None,
        start: int = 0,
        limit: int = 25,
    ) -> BitbucketPage:
        """List branches, most recently modified first."""
        repo = self._repo_path(project_key, repo_slug)
        data = self._get_page(
            f"{repo}/branches",
            start=start,
            limit=limit,
            params={"filterText": filter_text, "orderBy": "MODIFICATION"},
        )
        return BitbucketPage.from_api_response(data, item_model=BitbucketRef)

    def list_tags(
        self,
        project_key: str,
        repo_slug: str,
        *,
        filter_text: str | None = None,
        start: int = 0,
        limit: int = 25,
    ) -> BitbucketPage:
        """List tags, most recently modified first."""
        repo = self._repo_path(project_key, repo_slug)
        data = self._get_page(
            f"{repo}/tags",
            start=start,
            limit=limit,
            params={"filterText": filter_text, "orderBy": "MODIFICATION"},
        )
        return BitbucketPage.from_api_response(data, item_model=BitbucketRef)

    def list_commits(
        self,
        project_key: str,
        repo_slug: str,
        *,
        at: str | None = None,
        path: str | None = None,
        since: str | None = None,
        start: int = 0,
        limit: int = 25,
    ) -> BitbucketPage:
        """List commits reachable from ``at``, newest first.

        Args:
            project_key: Project key.
            repo_slug: Repository slug.
            at: Branch, tag or commit to list from (default: default branch).
            path: Only commits touching this path.
            since: Exclude commits reachable from this ref or commit.
            start: Page start.
            limit: Page size.

        Returns:
            A page of commits.
        """
        repo = self._repo_path(project_key, repo_slug)
        data = self._get_page(
            f"{repo}/commits",
            start=start,
            limit=limit,
            params={"until": at, "path": path, "since": since},
        )
        return BitbucketPage.from_api_response(data, item_model=BitbucketCommit)

    def get_commit(
        self,
        project_key: str,
        repo_slug: str,
        commit_id: str,
        *,
        max_changes: int = 500,
    ) -> BitbucketCommit:
        """Get a commit with the files it changed.

        Args:
            project_key: Project key.
            repo_slug: Repository slug.
            commit_id: Commit hash (or a ref resolving to a commit).
            max_changes: Maximum number of changed files to include.

        Returns:
            The commit with ``changes``.
        """
        repo = self._repo_path(project_key, repo_slug)
        commit_path = f"{repo}/commits/{segment(commit_id.strip())}"
        commit = BitbucketCommit.from_api_response(self._get_json(commit_path))
        changes = self._get_page(f"{commit_path}/changes", limit=max_changes)
        commit.changes = [
            BitbucketChange.from_api_response(c) for c in changes.get("values") or []
        ]
        return commit
