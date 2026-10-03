"""Bitbucket Data Center API integration module.

Bitbucket Cloud is not supported (see ADR-0001).
"""

from .client import BitbucketApiError, BitbucketClient
from .code import CodeMixin
from .config import BitbucketConfig
from .diff import DiffMixin
from .projects import ProjectsMixin
from .pull_requests import PullRequestsMixin
from .review import ReviewMixin


class BitbucketFetcher(
    ProjectsMixin, CodeMixin, PullRequestsMixin, DiffMixin, ReviewMixin
):
    """Main entry point for Bitbucket operations, composed from mixins.

    Available mixins:
    - ProjectsMixin: projects and repositories
    - CodeMixin: files, branches, tags and commits
    - DiffMixin: commit diffs as unified text
    - PullRequestsMixin: finding and reading pull requests
    - ReviewMixin: pull request comments and tasks
    - PullRequestsMixin: finding and reading pull requests
    - ReviewMixin: pull request comments and tasks
    """


__all__ = [
    "BitbucketApiError",
    "BitbucketClient",
    "BitbucketConfig",
    "BitbucketFetcher",
]
