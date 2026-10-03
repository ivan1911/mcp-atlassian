"""Bitbucket project and repository operations."""

from ..models.bitbucket import BitbucketPage, BitbucketProject
from .client import API, BitbucketClient


class ProjectsMixin(BitbucketClient):
    """Projects and repositories."""

    def list_projects(self, *, start: int = 0, limit: int = 25) -> BitbucketPage:
        """List projects visible to the token.

        Args:
            start: Page start (use ``next_page_start`` from a previous page).
            limit: Page size.

        Returns:
            A page of projects.
        """
        data = self._get_page(f"{API}/projects", start=start, limit=limit)
        return BitbucketPage.from_api_response(data, item_model=BitbucketProject)
