"""Bitbucket Data Center API integration module.

Bitbucket Cloud is not supported (see ADR-0001).
"""

from .client import BitbucketApiError, BitbucketClient
from .code import CodeMixin
from .config import BitbucketConfig
from .projects import ProjectsMixin


class BitbucketFetcher(ProjectsMixin, CodeMixin):
    """Main entry point for Bitbucket operations, composed from mixins.

    Available mixins:
    - ProjectsMixin: projects and repositories
    - CodeMixin: files, branches, tags and commits
    """


__all__ = [
    "BitbucketApiError",
    "BitbucketClient",
    "BitbucketConfig",
    "BitbucketFetcher",
]
