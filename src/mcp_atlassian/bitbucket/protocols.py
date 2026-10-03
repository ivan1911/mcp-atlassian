"""Protocols for cross-mixin calls in the Bitbucket fetcher."""

from abc import abstractmethod
from typing import Protocol


class RepositoryOperationsProto(Protocol):
    """Repository operations used by other mixins."""

    @abstractmethod
    def get_default_branch(self, project_key: str, repo_slug: str) -> str | None:
        """Return the default branch name, or None for an empty repository.

        Args:
            project_key: Project key.
            repo_slug: Repository slug.

        Returns:
            The default branch display name, or None.
        """
