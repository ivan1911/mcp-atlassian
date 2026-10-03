"""Taking part in pull request review: comments and tasks."""

from typing import Any, Literal

from ..models.bitbucket import BitbucketComment, BitbucketParticipant
from .client import API, BitbucketClient, segment

ReviewerStatus = Literal["approved", "needs_work", "unapproved"]
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

    _current_user_slug: str | None = None

    def get_current_user_slug(self) -> str:
        """Slug of the token's user, resolved once per fetcher.

        Bitbucket reports the authenticated username in the ``X-AUSERNAME``
        response header; the slug used in URLs is looked up from it.
        """
        if self._current_user_slug:
            return self._current_user_slug
        response = self._request("GET", f"{API}/application-properties")
        username = response.headers.get("X-AUSERNAME")
        if not username:
            raise ValueError(
                "Could not determine the Bitbucket user of the token "
                "(no X-AUSERNAME header)."
            )
        users = self._get_json(f"{API}/users", {"filter": username, "limit": 100})
        for candidate in (users or {}).get("values") or []:
            if str(candidate.get("name", "")).lower() == username.lower():
                self._current_user_slug = str(candidate["slug"])
                return self._current_user_slug
        raise ValueError(f"Bitbucket user '{username}' not found.")

    def set_reviewer_status(
        self,
        project_key: str,
        repo_slug: str,
        pull_request_id: int,
        status: ReviewerStatus,
        *,
        version: int | None = None,
    ) -> BitbucketParticipant:
        """Set the token user's reviewer status on a pull request.

        Args:
            project_key: Project key.
            repo_slug: Repository slug.
            pull_request_id: Pull request id.
            status: approved, needs_work or unapproved.
            version: Expected pull request version (read when omitted).

        Returns:
            The updated participant.
        """
        pr_path = self._pr_path(project_key, repo_slug, pull_request_id)
        slug = self.get_current_user_slug()
        params = {"version": self._pr_version(pr_path, version)}
        response = self._request(
            "PUT",
            f"{pr_path}/participants/{segment(slug)}",
            params=params,
            json={"status": status.upper()},
        )
        return BitbucketParticipant.from_api_response(response.json())

    def publish_review(
        self,
        project_key: str,
        repo_slug: str,
        pull_request_id: int,
        *,
        status: ReviewerStatus | None = None,
        comment: str | None = None,
    ) -> dict[str, Any]:
        """Publish the token user's pending comments as one review.

        Args:
            project_key: Project key.
            repo_slug: Repository slug.
            pull_request_id: Pull request id.
            status: Optionally set the reviewer status at the same time.
            comment: Optional summary comment.

        Returns:
            ``{"published": True, "status": ...}``.
        """
        pr_path = self._pr_path(project_key, repo_slug, pull_request_id)
        body: dict[str, Any] = {}
        if status:
            body["participantStatus"] = status.upper()
        if comment:
            body["commentText"] = comment
        response = self._request("PUT", f"{pr_path}/review", json=body)
        participant = (
            BitbucketParticipant.from_api_response(response.json())
            if response.content
            else None
        )
        return {
            "published": True,
            "status": participant.status if participant else status,
        }
