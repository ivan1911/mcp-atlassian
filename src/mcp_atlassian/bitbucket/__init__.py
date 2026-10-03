"""Bitbucket Data Center API integration module.

Bitbucket Cloud is not supported (see ADR-0001).
"""

from .client import BitbucketApiError, BitbucketClient
from .code import CodeMixin
from .config import BitbucketConfig
from .diff import DiffMixin
from .manage import ManageMixin
from .projects import ProjectsMixin
from .pull_requests import PullRequestsMixin
from .review import ReviewMixin
from .search import SearchMixin


class BitbucketFetcher(
    ManageMixin,
    ProjectsMixin,
    CodeMixin,
    PullRequestsMixin,
    DiffMixin,
    ReviewMixin,
    SearchMixin,
):
    """Main entry point for Bitbucket operations, composed from mixins.

    Available mixins:
    - ProjectsMixin: projects and repositories
    - CodeMixin: files, branches, tags and commits
    - DiffMixin: commit diffs as unified text
    - PullRequestsMixin: finding and reading pull requests
    - ReviewMixin: pull request comments and tasks
    - ManageMixin: create, update, merge, decline, reopen; create branches
    - SearchMixin: code search (unofficial endpoint)
    - PullRequestsMixin: finding and reading pull requests
    - ReviewMixin: pull request comments and tasks
    - ManageMixin: create, update, merge, decline, reopen; create branches
    - SearchMixin: code search (unofficial endpoint)
    """


__all__ = [
    "BitbucketApiError",
    "BitbucketClient",
    "BitbucketConfig",
    "BitbucketFetcher",
]
