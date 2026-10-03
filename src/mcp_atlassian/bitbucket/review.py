"""Taking part in pull request review: comments and tasks."""

from typing import Any, Literal

from ..models.bitbucket import BitbucketComment
from .client import BitbucketClient

LineType = Literal["ADDED", "REMOVED", "CONTEXT"]
FileType = Literal["FROM", "TO"]


def build_anchor(
    path: str | None,
    line: int | None,
    line_type: LineType | None,
    file_type: FileType | None,
) -> dict[str, Any] | None:
    """Build an inline comment anchor for the pull request's effective diff.

    Removed lines live on the old (FROM) side of the diff; added and context
    lines are addressed on the new (TO) side unless ``file_type`` says
    otherwise.

    Raises:
        ValueError: If ``line`` is given without ``path``.
    """
    if line is not None and not path:
        raise ValueError("An inline comment on a line also needs the file 'path'.")
    if not path:
        return None
    anchor: dict[str, Any] = {"path": path.strip("/")}
    if line is not None:
        effective_line_type = line_type or "ADDED"
        anchor["line"] = line
        anchor["lineType"] = effective_line_type
        anchor["fileType"] = file_type or (
            "FROM" if effective_line_type == "REMOVED" else "TO"
        )
    anchor["diffType"] = "EFFECTIVE"
    return anchor


class ReviewMixin(BitbucketClient):
    """Pull request comments and tasks."""

    def add_pull_request_comment(
        self,
        project_key: str,
        repo_slug: str,
        pull_request_id: int,
        text: str,
        *,
        path: str | None = None,
        line: int | None = None,
        line_type: LineType | None = None,
        file_type: FileType | None = None,
        parent_comment_id: int | None = None,
        as_task: bool = False,
        pending: bool = False,
    ) -> BitbucketComment:
        """Add a general, inline or reply comment, or a task.

        Args:
            project_key: Project key.
            repo_slug: Repository slug.
            pull_request_id: Pull request id.
            text: Comment text (Bitbucket markdown).
            path: File path for a file or inline comment.
            line: Diff line for an inline comment (needs ``path``).
            line_type: ADDED, REMOVED or CONTEXT (default ADDED).
            file_type: FROM or TO (inferred from ``line_type``).
            parent_comment_id: Reply to this comment.
            as_task: Create a task (blocking comment).
            pending: Create a pending comment, visible only to its author
                until the review is published.

        Returns:
            The created comment.
        """
        pr_path = self._pr_path(project_key, repo_slug, pull_request_id)
        body: dict[str, Any] = {"text": text}
        anchor = build_anchor(path, line, line_type, file_type)
        if anchor:
            body["anchor"] = anchor
        if parent_comment_id is not None:
            body["parent"] = {"id": int(parent_comment_id)}
        if as_task:
            body["severity"] = "BLOCKER"
        if pending:
            body["state"] = "PENDING"
        response = self._request("POST", f"{pr_path}/comments", json=body)
        return BitbucketComment.from_api_response(response.json())

    def update_pull_request_comment(
        self,
        project_key: str,
        repo_slug: str,
        pull_request_id: int,
        comment_id: int,
        *,
        text: str | None = None,
        task_state: Literal["open", "resolved"] | None = None,
    ) -> BitbucketComment:
        """Edit a comment's text and/or resolve or reopen a task.

        The comment's current version is read first, as Bitbucket requires it.

        Raises:
            ValueError: If neither ``text`` nor ``task_state`` is given.
        """
        if text is None and task_state is None:
            raise ValueError("Provide 'text' and/or 'task_state' to update.")
        pr_path = self._pr_path(project_key, repo_slug, pull_request_id)
        comment_path = f"{pr_path}/comments/{int(comment_id)}"
        current = self._get_json(comment_path) or {}
        body: dict[str, Any] = {"version": current.get("version", 0)}
        if text is not None:
            body["text"] = text
        if task_state is not None:
            body["state"] = task_state.upper()
        response = self._request("PUT", comment_path, json=body)
        return BitbucketComment.from_api_response(response.json())
