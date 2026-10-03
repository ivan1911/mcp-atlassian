"""Bitbucket Data Center API integration module.

Bitbucket Cloud is not supported (see ADR-0001).
"""

from .client import BitbucketApiError, BitbucketClient
from .code import CodeMixin
from .config import BitbucketConfig
from .diff import DiffMixin
from .projects import ProjectsMixin
from .pull_requests import PullRequestsMixin


class BitbucketFetcher(ProjectsMixin, CodeMixin, DiffMixin, PullRequestsMixin):
    """Main entry point for Bitbucket operations, composed from mixins.

    Available mixins:
    - ProjectsMixin: projects and repositories
    - CodeMixin: files, branches, tags and commits
    - DiffMixin: commit diffs as unified text
    - PullRequestsMixin: finding and reading pull requests
    - PullRequestsMixin: finding and reading pull requests
    """


__all__ = [
    "BitbucketApiError",
    "BitbucketClient",
    "BitbucketConfig",
    "BitbucketFetcher",
]
