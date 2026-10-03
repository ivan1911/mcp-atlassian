"""Bitbucket Data Center API integration module.

Bitbucket Cloud is not supported (see ADR-0001).
"""

from .client import BitbucketApiError, BitbucketClient
from .config import BitbucketConfig
from .projects import ProjectsMixin


class BitbucketFetcher(ProjectsMixin):
    """Main entry point for Bitbucket operations, composed from mixins.

    Available mixins:
    - ProjectsMixin: projects and repositories
    """


__all__ = [
    "BitbucketApiError",
    "BitbucketClient",
    "BitbucketConfig",
    "BitbucketFetcher",
]
