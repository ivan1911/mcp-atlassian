"""Managing pull requests and branches."""

from typing import Any

from mcp_atlassian.models.bitbucket import BitbucketPullRequest, BitbucketRef

from .client import BitbucketClient, qualify_branch
from .protocols import RepositoryOperationsProto

DEFAULT_REVIEWERS_API = "rest/default-reviewers/latest"
BRANCH_UTILS_API = "rest/branch-utils/latest"


def _reviewers_body(names: list[str]) -> list[dict[str, Any]]:
    """Reviewer list in the shape Bitbucket expects in pull request bodies."""
    return [{"user": {"name": name}} for name in names]


class ManageMixin(BitbucketClient, RepositoryOperationsProto):
    """Create, update, merge, decline, reopen and delete pull requests; branches."""

    def _repo_ref(self, project_key: str, repo_slug: str) -> dict[str, Any]:
        return {
            "slug": repo_slug.strip(),
            "project": {"key": self._project_key(project_key)},
        }

    def _default_reviewers(
        self, project_key: str, repo_slug: str, source_ref: str, target_ref: str
    ) -> list[str]:
        """Usernames of the repository's default reviewers for this branch pair."""
        repo = self._get_json(self._repo_path(project_key, repo_slug)) or {}
        repo_id = repo.get("id")
        users = self._get_json(
            f"{self._repo_path(project_key, repo_slug, api=DEFAULT_REVIEWERS_API)}"
            "/reviewers",
            {
                "sourceRepoId": repo_id,
                "targetRepoId": repo_id,
                "sourceRefId": source_ref,
                "targetRefId": target_ref,
            },
        )
        return [
            str(u["name"]) for u in users or [] if isinstance(u, dict) and u.get("name")
        ]

    def create_pull_request(
        self,
        project_key: str,
        repo_slug: str,
        title: str,
        source_branch: str,
        *,
        target_branch: str | None = None,
        description: str | None = None,
        reviewers: list[str] | None = None,
        draft: bool = False,
    ) -> BitbucketPullRequest:
        """Create a pull request within one repository.

        Args:
            project_key: Project key.
            repo_slug: Repository slug.
            title: Title.
            source_branch: Branch with the changes.
            target_branch: Branch to merge into (default: default branch).
            description: Description (markdown).
            reviewers: Reviewer usernames; when None, the repository's default
                reviewers for this branch pair are added.
            draft: Create as a draft.

        Returns:
            The created pull request.

        Raises:
            ValueError: If no target branch is given and the repository has no
                default branch.
        """
        repo = self._repo_path(project_key, repo_slug)
        if target_branch is None:
            target_branch = self.get_default_branch(project_key, repo_slug)
            if not target_branch:
                raise ValueError(
                    "The repository has no default branch; pass target_branch."
                )
        source_ref = qualify_branch(source_branch)
        target_ref = qualify_branch(target_branch)
        if reviewers is None:
            reviewers = self._default_reviewers(
                project_key, repo_slug, source_ref, target_ref
            )
        repo_ref = self._repo_ref(project_key, repo_slug)
        body: dict[str, Any] = {
            "title": title,
            "fromRef": {"id": source_ref, "repository": repo_ref},
            "toRef": {"id": target_ref, "repository": repo_ref},
            "reviewers": _reviewers_body(reviewers),
            "draft": draft,
        }
        if description is not None:
            body["description"] = description
        response = self._request("POST", f"{repo}/pull-requests", json=body)
        return BitbucketPullRequest.from_api_response(response.json())

    def update_pull_request(
        self,
        project_key: str,
        repo_slug: str,
        pull_request_id: int,
        *,
        title: str | None = None,
        description: str | None = None,
        reviewers: list[str] | None = None,
        target_branch: str | None = None,
        draft: bool | None = None,
        version: int | None = None,
    ) -> BitbucketPullRequest:
        """Update a pull request; unspecified fields keep their current values.

        Bitbucket drops reviewers missing from an update, so the current
        pull request is always read and its reviewers re-sent unless
        ``reviewers`` replaces them.

        Args:
            project_key: Project key.
            repo_slug: Repository slug.
            pull_request_id: Pull request id.
            title: New title.
            description: New description.
            reviewers: Full new list of reviewer usernames.
            target_branch: New target branch.
            draft: Set or clear the draft flag.
            version: Expected version; the current one is used when omitted.

        Returns:
            The updated pull request.
        """
        pr_path = self._pr_path(project_key, repo_slug, pull_request_id)
        current = self._get_json(pr_path) or {}
        if reviewers is None:
            reviewers = [
                r["user"]["name"]
                for r in current.get("reviewers") or []
                if isinstance(r, dict) and (r.get("user") or {}).get("name")
            ]
        body: dict[str, Any] = {
            "version": int(version)
            if version is not None
            else current.get("version", 0),
            "title": title if title is not None else current.get("title"),
            "reviewers": _reviewers_body(reviewers),
        }
        new_description = (
            description if description is not None else current.get("description")
        )
        if new_description is not None:
            body["description"] = new_description
        if target_branch is not None:
            body["toRef"] = {
                "id": qualify_branch(target_branch),
                "repository": self._repo_ref(project_key, repo_slug),
            }
        if draft is not None:
            body["draft"] = draft
        response = self._request("PUT", pr_path, json=body)
        return BitbucketPullRequest.from_api_response(response.json())

    def merge_pull_request(
        self,
        project_key: str,
        repo_slug: str,
        pull_request_id: int,
        *,
        strategy: str | None = None,
        message: str | None = None,
        version: int | None = None,
    ) -> BitbucketPullRequest:
        """Merge a pull request.

        Args:
            project_key: Project key.
            repo_slug: Repository slug.
            pull_request_id: Pull request id.
            strategy: Merge strategy id (repository default when omitted).
            message: Merge commit message.
            version: Expected version; the current one is read when omitted.

        Returns:
            The merged pull request.

        Raises:
            BitbucketApiError: If Bitbucket refuses the merge; the message
                lists its veto reasons.
        """
        pr_path = self._pr_path(project_key, repo_slug, pull_request_id)
        params = {"version": self._pr_version(pr_path, version)}
        body: dict[str, Any] = {}
        if strategy:
            body["strategyId"] = strategy
        if message:
            body["message"] = message
        response = self._request(
            "POST", f"{pr_path}/merge", params=params, json=body or None
        )
        return BitbucketPullRequest.from_api_response(response.json())

    def decline_pull_request(
        self,
        project_key: str,
        repo_slug: str,
        pull_request_id: int,
        *,
        comment: str | None = None,
        version: int | None = None,
    ) -> BitbucketPullRequest:
        """Decline a pull request.

        Args:
            project_key: Project key.
            repo_slug: Repository slug.
            pull_request_id: Pull request id.
            comment: Reason, added as a comment.
            version: Expected version; the current one is read when omitted.

        Returns:
            The declined pull request.
        """
        pr_path = self._pr_path(project_key, repo_slug, pull_request_id)
        params = {"version": self._pr_version(pr_path, version)}
        body = {"comment": comment} if comment else None
        response = self._request("POST", f"{pr_path}/decline", params=params, json=body)
        return BitbucketPullRequest.from_api_response(response.json())

    def reopen_pull_request(
        self,
        project_key: str,
        repo_slug: str,
        pull_request_id: int,
        *,
        version: int | None = None,
    ) -> BitbucketPullRequest:
        """Reopen a declined pull request.

        Args:
            project_key: Project key.
            repo_slug: Repository slug.
            pull_request_id: Pull request id.
            version: Expected version; the current one is read when omitted.

        Returns:
            The reopened pull request.
        """
        pr_path = self._pr_path(project_key, repo_slug, pull_request_id)
        params = {"version": self._pr_version(pr_path, version)}
        response = self._request("POST", f"{pr_path}/reopen", params=params)
        return BitbucketPullRequest.from_api_response(response.json())

    def delete_pull_request(
        self,
        project_key: str,
        repo_slug: str,
        pull_request_id: int,
        *,
        version: int | None = None,
    ) -> dict[str, Any]:
        """Permanently delete a pull request.

        Args:
            project_key: Project key.
            repo_slug: Repository slug.
            pull_request_id: Pull request id.
            version: Expected version; the current one is read when omitted.

        Returns:
            ``{"deleted": True, "pull_request_id": ...}``.
        """
        pr_path = self._pr_path(project_key, repo_slug, pull_request_id)
        body = {"version": self._pr_version(pr_path, version)}
        self._request("DELETE", pr_path, json=body)
        return {"deleted": True, "pull_request_id": int(pull_request_id)}

    def create_branch(
        self, project_key: str, repo_slug: str, name: str, start_point: str
    ) -> BitbucketRef:
        """Create a branch.

        Args:
            project_key: Project key.
            repo_slug: Repository slug.
            name: New branch name.
            start_point: Branch, tag or commit to start from.

        Returns:
            The created branch.
        """
        repo = self._repo_path(project_key, repo_slug)
        response = self._request(
            "POST",
            f"{repo}/branches",
            json={"name": name, "startPoint": start_point},
        )
        return BitbucketRef.from_api_response(response.json())

    def delete_branch(
        self, project_key: str, repo_slug: str, name: str
    ) -> dict[str, Any]:
        """Delete a branch.

        Args:
            project_key: Project key.
            repo_slug: Repository slug.
            name: Branch name or fully qualified ref.

        Returns:
            ``{"deleted": True, "branch": <ref>}``.
        """
        ref = qualify_branch(name)
        self._request(
            "DELETE",
            f"{self._repo_path(project_key, repo_slug, api=BRANCH_UTILS_API)}/branches",
            json={"name": ref, "dryRun": False},
        )
        return {"deleted": True, "branch": ref}
