"""Finding and reading Bitbucket pull requests."""

from typing import Any

from ..models.bitbucket import (
    BitbucketChange,
    BitbucketCommit,
    BitbucketPage,
    BitbucketPullRequest,
    activity_from_api,
    merge_status_from_api,
)
from .client import API, qualify_branch
from .diff import DiffMixin


class PullRequestsMixin(DiffMixin):
    """Pull request listing and reading."""

    def list_pull_requests(
        self,
        project_key: str,
        repo_slug: str,
        *,
        state: str = "OPEN",
        direction: str = "INCOMING",
        target_branch: str | None = None,
        author: str | None = None,
        reviewer: str | None = None,
        text: str | None = None,
        start: int = 0,
        limit: int = 25,
    ) -> BitbucketPage:
        """List pull requests of a repository.

        Args:
            project_key: Project key.
            repo_slug: Repository slug.
            state: OPEN, MERGED, DECLINED or ALL.
            direction: INCOMING (into this repository) or OUTGOING.
            target_branch: Only pull requests into (INCOMING) or from
                (OUTGOING) this branch.
            author: Only pull requests authored by this user (slug).
            reviewer: Only pull requests with this reviewer (slug).
            text: Only pull requests whose title or description contains it.
            start: Page start.
            limit: Page size.

        Returns:
            A page of pull requests.
        """
        repo = self._repo_path(project_key, repo_slug)
        params: dict[str, Any] = {
            "state": state,
            "direction": direction,
            "at": qualify_branch(target_branch) if target_branch else None,
            "filterText": text,
        }
        index = 1
        for username, role in ((author, "AUTHOR"), (reviewer, "REVIEWER")):
            if username:
                params[f"username.{index}"] = username
                params[f"role.{index}"] = role
                index += 1
        data = self._get_page(
            f"{repo}/pull-requests", start=start, limit=limit, params=params
        )
        return BitbucketPage.from_api_response(data, item_model=BitbucketPullRequest)

    def get_my_pull_requests(
        self,
        *,
        role: str | None = None,
        state: str = "OPEN",
        participant_status: str | None = None,
        start: int = 0,
        limit: int = 25,
    ) -> BitbucketPage:
        """List the token user's pull requests from the dashboard.

        Args:
            role: AUTHOR, REVIEWER or PARTICIPANT (default: any).
            state: OPEN, MERGED, DECLINED or ALL.
            participant_status: APPROVED, UNAPPROVED or NEEDS_WORK.
            start: Page start.
            limit: Page size.

        Returns:
            A page of pull requests within the projects filter.
        """
        params = {
            "role": role,
            "state": None if state == "ALL" else state,
            "participantStatus": participant_status,
        }
        data = self._get_page(
            f"{API}/dashboard/pull-requests", start=start, limit=limit, params=params
        )
        page = BitbucketPage.from_api_response(data, item_model=BitbucketPullRequest)
        page.values = [
            pr for pr in page.values if self._is_project_allowed(pr.project_key)
        ]
        return page

    def get_pull_request(
        self,
        project_key: str,
        repo_slug: str,
        pull_request_id: int,
        *,
        include_merge_status: bool = False,
    ) -> BitbucketPullRequest:
        """Get a pull request, optionally with its mergeability.

        Args:
            project_key: Project key.
            repo_slug: Repository slug.
            pull_request_id: Pull request id.
            include_merge_status: Also check whether it can be merged.

        Returns:
            The pull request.
        """
        path = self._pr_path(project_key, repo_slug, pull_request_id)
        pull_request = BitbucketPullRequest.from_api_response(self._get_json(path))
        if include_merge_status:
            pull_request.merge_status = merge_status_from_api(
                self._get_json(f"{path}/merge") or {}
            )
        return pull_request

    def get_pull_request_changes(
        self,
        project_key: str,
        repo_slug: str,
        pull_request_id: int,
        *,
        start: int = 0,
        limit: int = 100,
    ) -> BitbucketPage:
        """List the files a pull request changes."""
        path = self._pr_path(project_key, repo_slug, pull_request_id)
        data = self._get_page(f"{path}/changes", start=start, limit=limit)
        return BitbucketPage.from_api_response(data, item_model=BitbucketChange)

    def get_pull_request_commits(
        self,
        project_key: str,
        repo_slug: str,
        pull_request_id: int,
        *,
        start: int = 0,
        limit: int = 25,
    ) -> BitbucketPage:
        """List the commits of a pull request, newest first."""
        path = self._pr_path(project_key, repo_slug, pull_request_id)
        data = self._get_page(f"{path}/commits", start=start, limit=limit)
        return BitbucketPage.from_api_response(data, item_model=BitbucketCommit)

    def get_pull_request_diff(
        self,
        project_key: str,
        repo_slug: str,
        pull_request_id: int,
        *,
        path: str | None = None,
        context_lines: int | None = None,
        ignore_whitespace: bool = False,
    ) -> str:
        """Unified diff of a pull request (target branch to source branch).

        Args:
            project_key: Project key.
            repo_slug: Repository slug.
            pull_request_id: Pull request id.
            path: Only this file.
            context_lines: Lines of context around changes.
            ignore_whitespace: Ignore whitespace-only changes.

        Returns:
            A header line (with a truncation notice when Bitbucket cut the
            diff) followed by unified diff text.
        """
        path_prefix = self._pr_path(project_key, repo_slug, pull_request_id)
        return self._render_diff(
            f"{path_prefix}/diff",
            f"Diff of pull request #{int(pull_request_id)}",
            path=path,
            context_lines=context_lines,
            ignore_whitespace=ignore_whitespace,
        )

    def get_pull_request_activity(
        self,
        project_key: str,
        repo_slug: str,
        pull_request_id: int,
        *,
        start: int = 0,
        limit: int = 25,
    ) -> BitbucketPage:
        """List pull request activity, newest first.

        Comment activities carry the whole thread (replies, anchor, task
        state). Unknown activity kinds are passed through raw.
        """
        path = self._pr_path(project_key, repo_slug, pull_request_id)
        data = self._get_page(f"{path}/activities", start=start, limit=limit)
        page = BitbucketPage.from_api_response(data)
        page.values = [activity_from_api(a) for a in page.values if isinstance(a, dict)]
        return page
