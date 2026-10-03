"""Bitbucket Data Center project model."""

from typing import Any

from mcp_atlassian.models.base import ApiModel

from .common import self_link


class BitbucketProject(ApiModel):
    """A named container of repositories, addressed by its key."""

    key: str
    name: str | None = None
    description: str | None = None
    public: bool = False
    type: str | None = None
    url: str | None = None

    @classmethod
    def from_api_response(
        cls, data: dict[str, Any], **kwargs: Any
    ) -> "BitbucketProject":
        """Build from a Bitbucket ``RestProject`` payload."""
        return cls(
            key=str(data.get("key", "")),
            name=data.get("name"),
            description=data.get("description"),
            public=bool(data.get("public", False)),
            type=data.get("type"),
            url=self_link(data),
        )
