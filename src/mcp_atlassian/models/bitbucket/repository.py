"""Bitbucket Data Center repository model."""

from typing import Any

from pydantic import Field

from ..base import ApiModel
from .common import self_link


class BitbucketRepository(ApiModel):
    """A git repository inside a project, addressed by project key + slug."""

    project_key: str
    slug: str
    name: str | None = None
    description: str | None = None
    project_name: str | None = None
    state: str | None = None
    public: bool = False
    archived: bool = False
    forkable: bool | None = None
    default_branch: str | None = None
    url: str | None = None
    clone_urls: dict[str, str] = Field(default_factory=dict)

    @classmethod
    def from_api_response(
        cls, data: dict[str, Any], **kwargs: Any
    ) -> "BitbucketRepository":
        """Build from a Bitbucket ``RestRepository`` payload.

        Args:
            data: The repository payload.
            **kwargs: ``default_branch`` (display name) if already resolved.
        """
        project = data.get("project") or {}
        clone_links = (data.get("links") or {}).get("clone") or []
        clone_urls = {
            str(link["name"]): str(link["href"])
            for link in clone_links
            if isinstance(link, dict) and link.get("name") and link.get("href")
        }
        return cls(
            project_key=str(project.get("key", "")),
            slug=str(data.get("slug", "")),
            name=data.get("name"),
            description=data.get("description"),
            project_name=project.get("name"),
            state=data.get("state"),
            public=bool(data.get("public", False)),
            archived=bool(data.get("archived", False)),
            forkable=data.get("forkable"),
            default_branch=kwargs.get("default_branch"),
            url=self_link(data),
            clone_urls=clone_urls,
        )

    def to_simplified_dict(self) -> dict[str, Any]:
        """Serialize, dropping empty clone URLs."""
        result = super().to_simplified_dict()
        if not self.clone_urls:
            result.pop("clone_urls", None)
        return result
