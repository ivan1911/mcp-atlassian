"""Managing pull requests and creating branches."""

from typing import Any

from ..models.bitbucket import BitbucketPullRequest, BitbucketRef
from .client import qualify_branch, segment
from .projects import ProjectsMixin

DEFAULT_REVIEWERS_API = "rest/default-reviewers/latest"
BRANCH_UTILS_API = "rest/branch-utils/latest"


def _reviewers(names: list[str]) -> list[dict[str, Any]]:
    return [{"user": {"name": name}} for name in names]


class ManageMixin(ProjectsMixin):
    """Create, update, merge, decline and reopen pull requests; create branches."""

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
        key = self._project_key(project_key)
        users = self._get_json(
            f"{DEFAULT_REVIEWERS_API}/projects/{segment(key)}/repos/"
            f"{segment(repo_slug.strip())}/reviewers",
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
            "reviewers": _reviewers(reviewers),
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
        reviewers are always re-sent unless ``reviewers`` replaces them.
        """
        pr_path = self._pr_path(project_key, repo_slug, pull_request_id)
        current = self._get_json(pr_path) or {}
        body: dict[str, Any] = {
            "version": int(version)
            if version is not None
            else current.get("version", 0),
            "title": title if title is not None else current.get("title"),
            "description": description
            if description is not None
            else current.get("description"),
            "reviewers": _reviewers(reviewers)
            if reviewers is not None
            else [
                {"user": {"name": r["user"]["name"]}}
                for r in current.get("reviewers") or []
                if isinstance(r, dict) and (r.get("user") or {}).get("name")
            ],
        }
        if body["description"] is None:
            del body["description"]
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
        """Merge a pull request; a refusal reports Bitbucket's veto reasons."""
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
        """Decline a pull request, optionally with a comment."""
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
        """Reopen a declined pull request."""
        pr_path = self._pr_path(project_key, repo_slug, pull_request_id)
        params = {"version": self._pr_version(pr_path, version)}
        response = self._request("POST", f"{pr_path}/reopen", params=params)
        return BitbucketPullRequest.from_api_response(response.json())

    def create_branch(
        self, project_key: str, repo_slug: str, name: str, start_point: str
    ) -> BitbucketRef:
        """Create a branch from a branch, tag or commit."""
        repo = self._repo_path(project_key, repo_slug)
        response = self._request(
            "POST",
            f"{repo}/branches",
            json={"name": name, "startPoint": start_point},
        )
        return BitbucketRef.from_api_response(response.json())

    def delete_pull_request(
        self,
        project_key: str,
        repo_slug: str,
        pull_request_id: int,
        *,
        version: int | None = None,
    ) -> dict[str, Any]:
        """Permanently delete a pull request."""
        pr_path = self._pr_path(project_key, repo_slug, pull_request_id)
        body = {"version": self._pr_version(pr_path, version)}
        self._request("DELETE", pr_path, json=body)
        return {"deleted": True, "pull_request_id": int(pull_request_id)}

    def delete_branch(
        self, project_key: str, repo_slug: str, name: str
    ) -> dict[str, Any]:
        """Delete a branch."""
        self._repo_path(project_key, repo_slug)  # enforce the projects filter
        key = self._project_key(project_key)
        ref = qualify_branch(name)
        self._request(
            "DELETE",
            f"{BRANCH_UTILS_API}/projects/{segment(key)}/repos/"
            f"{segment(repo_slug.strip())}/branches",
            json={"name": ref, "dryRun": False},
        )
        return {"deleted": True, "branch": ref}
