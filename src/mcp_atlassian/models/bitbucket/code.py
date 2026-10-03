"""Bitbucket Data Center models for refs, commits and changed files."""

from typing import Any

from pydantic import Field

from mcp_atlassian.models.base import ApiModel

from .common import iso_from_millis


class BitbucketPerson(ApiModel):
    """A commit author or committer (a git identity, not necessarily a user)."""

    name: str | None = None
    email: str | None = None

    @classmethod
    def from_api_response(
        cls, data: dict[str, Any], **kwargs: Any
    ) -> "BitbucketPerson":
        """Build from a Bitbucket ``RestPerson``/``RestApplicationUser``."""
        return cls(
            name=data.get("displayName") or data.get("name"),
            email=data.get("emailAddress"),
        )


class BitbucketRef(ApiModel):
    """A branch or tag."""

    name: str
    id: str
    latest_commit: str | None = None
    is_default: bool | None = None

    @classmethod
    def from_api_response(cls, data: dict[str, Any], **kwargs: Any) -> "BitbucketRef":
        """Build from a Bitbucket ``RestBranch``/``RestTag``."""
        return cls(
            name=str(data.get("displayId", "")),
            id=str(data.get("id", "")),
            latest_commit=data.get("latestCommit") or data.get("latestChangeset"),
            is_default=data.get("isDefault") if data.get("type") == "BRANCH" else None,
        )


class BitbucketChange(ApiModel):
    """A file changed by a commit or pull request."""

    path: str
    type: str | None = None
    src_path: str | None = None

    @classmethod
    def from_api_response(
        cls, data: dict[str, Any], **kwargs: Any
    ) -> "BitbucketChange":
        """Build from a Bitbucket ``RestChange``."""
        src = data.get("srcPath") or {}
        return cls(
            path=str((data.get("path") or {}).get("toString", "")),
            type=data.get("type"),
            src_path=src.get("toString") if isinstance(src, dict) else None,
        )


class BitbucketCommit(ApiModel):
    """A git commit."""

    id: str
    display_id: str | None = None
    message: str | None = None
    author: BitbucketPerson | None = None
    author_timestamp: str | None = None
    committer: BitbucketPerson | None = None
    committer_timestamp: str | None = None
    parents: list[str] = Field(default_factory=list)
    changes: list[BitbucketChange] | None = None

    @classmethod
    def from_api_response(
        cls, data: dict[str, Any], **kwargs: Any
    ) -> "BitbucketCommit":
        """Build from a Bitbucket ``RestCommit``."""
        author = data.get("author")
        committer = data.get("committer")
        return cls(
            id=str(data.get("id", "")),
            display_id=data.get("displayId"),
            message=data.get("message"),
            author=BitbucketPerson.from_api_response(author)
            if isinstance(author, dict)
            else None,
            author_timestamp=iso_from_millis(data.get("authorTimestamp")),
            committer=BitbucketPerson.from_api_response(committer)
            if isinstance(committer, dict)
            else None,
            committer_timestamp=iso_from_millis(data.get("committerTimestamp")),
            parents=[
                str(p["id"])
                for p in data.get("parents") or []
                if isinstance(p, dict) and p.get("id")
            ],
        )

    def to_simplified_dict(self) -> dict[str, Any]:
        """Serialize; the committer is omitted when identical to the author."""
        result = super().to_simplified_dict()
        if (
            self.committer == self.author
            and self.committer_timestamp == self.author_timestamp
        ):
            result.pop("committer", None)
            result.pop("committer_timestamp", None)
        return result
