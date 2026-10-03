"""Bitbucket project and repository operations."""

from mcp_atlassian.models.bitbucket import (
    BitbucketPage,
    BitbucketProject,
    BitbucketRepository,
)

from .client import API, BitbucketApiError, BitbucketClient, quote_segment


class ProjectsMixin(BitbucketClient):
    """Projects and repositories."""

    def list_projects(self, *, start: int = 0, limit: int = 25) -> BitbucketPage:
        """List projects visible to the token, within the projects filter.

        Args:
            start: Page start (use ``next_page_start`` from a previous page).
            limit: Page size.

        Returns:
            A page of projects.
        """
        data = self._get_page(f"{API}/projects", start=start, limit=limit)
        page = BitbucketPage.from_api_response(data, item_model=BitbucketProject)
        page.values = [p for p in page.values if self._is_project_allowed(p.key)]
        return page

    def list_repositories(
        self,
        *,
        project_key: str | None = None,
        name: str | None = None,
        start: int = 0,
        limit: int = 25,
    ) -> BitbucketPage:
        """List repositories of a project, or search them by name.

        Args:
            project_key: Restrict to this project.
            name: Case-insensitive repository name filter (searches all
                projects unless ``project_key`` is given).
            start: Page start.
            limit: Page size.

        Returns:
            A page of repositories within the projects filter.
        """
        key = self._project_key(project_key) if project_key else None
        if key and not name:
            path = f"{API}/projects/{quote_segment(key)}/repos"
            params: dict[str, str | None] = {}
        else:
            path = f"{API}/repos"
            params = {"name": name, "projectkey": key}
        data = self._get_page(path, start=start, limit=limit, params=params)
        page = BitbucketPage.from_api_response(data, item_model=BitbucketRepository)
        page.values = [
            r for r in page.values if self._is_project_allowed(r.project_key)
        ]
        return page

    def get_repository(self, project_key: str, repo_slug: str) -> BitbucketRepository:
        """Get a repository with its default branch and clone URLs.

        Args:
            project_key: Project key.
            repo_slug: Repository slug.

        Returns:
            The repository; ``default_branch`` is None for an empty repository.
        """
        path = self._repo_path(project_key, repo_slug)
        data = self._get_json(path)
        return BitbucketRepository.from_api_response(
            data, default_branch=self.get_default_branch(project_key, repo_slug)
        )

    def get_default_branch(self, project_key: str, repo_slug: str) -> str | None:
        """Return the default branch name, or None for an empty repository.

        Args:
            project_key: Project key.
            repo_slug: Repository slug.

        Returns:
            The default branch display name; None when Bitbucket has none
            (an empty body or a 404 for an empty repository).
        """
        path = self._repo_path(project_key, repo_slug)
        try:
            ref = self._get_json(f"{path}/default-branch")
        except BitbucketApiError as e:
            if e.status == 404:
                return None
            raise
        display_id = ref.get("displayId") if isinstance(ref, dict) else None
        return str(display_id) if display_id else None
