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
    - PullRequestsMixin: finding and reading pull requests, their diffs and
      activity
    - ReviewMixin: comments, tasks, reviewer status and pending review
    - ManageMixin: create, update, merge, decline, reopen and delete pull
      requests; create and delete branches
    - SearchMixin: code search (unofficial endpoint)
    """


__all__ = [
    "BitbucketApiError",
    "BitbucketClient",
    "BitbucketConfig",
    "BitbucketFetcher",
]
