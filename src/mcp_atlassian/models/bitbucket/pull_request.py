"""Bitbucket Data Center pull request models."""

from typing import Any

from pydantic import Field

from mcp_atlassian.models.base import ApiModel

from .common import format_veto, iso_from_millis, self_link


class BitbucketUser(ApiModel):
    """A Bitbucket user account."""

    slug: str | None = None
    name: str | None = None
    display_name: str | None = None
    email: str | None = None

    @classmethod
    def from_api_response(cls, data: dict[str, Any], **kwargs: Any) -> "BitbucketUser":
        """Build from a Bitbucket ``RestApplicationUser``."""
        return cls(
            slug=data.get("slug"),
            name=data.get("name"),
            display_name=data.get("displayName"),
            email=data.get("emailAddress"),
        )


class BitbucketParticipant(ApiModel):
    """A pull request reviewer or participant with their reviewer status."""

    slug: str | None = None
    display_name: str | None = None
    role: str | None = None
    # Reviewer status: approved, needs_work or unapproved.
    status: str | None = None

    @classmethod
    def from_api_response(
        cls, data: dict[str, Any], **kwargs: Any
    ) -> "BitbucketParticipant":
        """Build from a Bitbucket ``RestPullRequestParticipant``."""
        user = data.get("user") or {}
        status = data.get("status")
        return cls(
            slug=user.get("slug"),
            display_name=user.get("displayName"),
            role=data.get("role"),
            status=str(status).lower() if status else None,
        )


class BitbucketPullRequestRef(ApiModel):
    """The source or target branch of a pull request."""

    branch: str | None = None
    latest_commit: str | None = None
    project_key: str | None = None
    repo_slug: str | None = None

    @classmethod
    def from_api_response(
        cls, data: dict[str, Any], **kwargs: Any
    ) -> "BitbucketPullRequestRef":
        """Build from a Bitbucket ``RestPullRequestRef``."""
        repository = data.get("repository") or {}
        return cls(
            branch=data.get("displayId"),
            latest_commit=data.get("latestCommit"),
            project_key=(repository.get("project") or {}).get("key"),
            repo_slug=repository.get("slug"),
        )


class BitbucketMergeStatus(ApiModel):
    """Whether a pull request can be merged, and what blocks it."""

    can_merge: bool = False
    conflicted: bool = False
    outcome: str | None = None
    vetoes: list[str] = Field(default_factory=list)

    @classmethod
    def from_api_response(
        cls, data: dict[str, Any], **kwargs: Any
    ) -> "BitbucketMergeStatus":
        """Build from a Bitbucket ``RestPullRequestMergeability`` response."""
        return cls(
            can_merge=bool(data.get("canMerge", False)),
            conflicted=bool(data.get("conflicted", False)),
            outcome=data.get("outcome"),
            vetoes=[
                format_veto(v) for v in data.get("vetoes") or [] if isinstance(v, dict)
            ],
        )


class BitbucketPullRequest(ApiModel):
    """A request to merge a source branch into a target branch."""

    id: int
    version: int | None = None
    title: str | None = None
    description: str | None = None
    state: str | None = None
    draft: bool | None = None
    author: BitbucketUser | None = None
    source: BitbucketPullRequestRef | None = None
    target: BitbucketPullRequestRef | None = None
    reviewers: list[BitbucketParticipant] = Field(default_factory=list)
    created: str | None = None
    updated: str | None = None
    comment_count: int | None = None
    open_task_count: int | None = None
    resolved_task_count: int | None = None
    url: str | None = None
    merge_status: BitbucketMergeStatus | None = None

    @classmethod
    def from_api_response(
        cls, data: dict[str, Any], **kwargs: Any
    ) -> "BitbucketPullRequest":
        """Build from a Bitbucket ``RestPullRequest``."""
        author = (data.get("author") or {}).get("user")
        props = data.get("properties") or {}
        return cls(
            id=int(data.get("id", 0)),
            version=data.get("version"),
            title=data.get("title"),
            description=data.get("description"),
            state=data.get("state"),
            draft=data.get("draft"),
            author=BitbucketUser.from_api_response(author)
            if isinstance(author, dict)
            else None,
            source=BitbucketPullRequestRef.from_api_response(data["fromRef"])
            if isinstance(data.get("fromRef"), dict)
            else None,
            target=BitbucketPullRequestRef.from_api_response(data["toRef"])
            if isinstance(data.get("toRef"), dict)
            else None,
            reviewers=[
                BitbucketParticipant.from_api_response(r)
                for r in data.get("reviewers") or []
                if isinstance(r, dict)
            ],
            created=iso_from_millis(data.get("createdDate")),
            updated=iso_from_millis(data.get("updatedDate")),
            comment_count=props.get("commentCount"),
            open_task_count=props.get("openTaskCount"),
            resolved_task_count=props.get("resolvedTaskCount"),
            url=self_link(data),
        )

    @property
    def project_key(self) -> str | None:
        """Project key of the target repository."""
        return self.target.project_key if self.target else None
