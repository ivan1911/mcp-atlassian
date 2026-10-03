"""Shared Bitbucket Data Center models: paged results and links."""

from datetime import datetime, timezone
from typing import Any

from pydantic import Field

from mcp_atlassian.models.base import ApiModel


def iso_from_millis(value: Any) -> str | None:
    """Convert a Bitbucket epoch-milliseconds timestamp to ISO 8601 (UTC)."""
    if not isinstance(value, int | float):
        return None
    return datetime.fromtimestamp(value / 1000, tz=timezone.utc).isoformat()


def format_veto(veto: dict[str, Any]) -> str:
    """Render a merge veto as ``summary: detail`` (either part may be absent)."""
    summary = veto.get("summaryMessage") or ""
    detail = veto.get("detailedMessage") or ""
    return f"{summary}: {detail}" if summary and detail else summary or detail


def self_link(data: dict[str, Any]) -> str | None:
    """Return the first ``links.self[].href`` of a Bitbucket entity."""
    links = data.get("links")
    if not isinstance(links, dict):
        return None
    selves = links.get("self")
    if isinstance(selves, list) and selves and isinstance(selves[0], dict):
        href = selves[0].get("href")
        return href if isinstance(href, str) else None
    return None


class BitbucketPage(ApiModel):
    """One page of a Bitbucket paged collection.

    Paging always follows Bitbucket's ``nextPageStart``; ids are not
    contiguous, so ``start + size`` is never used.
    """

    values: list[Any] = Field(default_factory=list)
    start: int = 0
    limit: int = 25
    is_last_page: bool = True
    next_page_start: int | None = None

    @classmethod
    def from_api_response(cls, data: dict[str, Any], **kwargs: Any) -> "BitbucketPage":
        """Build a page, converting each value with ``item_model`` if given."""
        item_model: type[ApiModel] | None = kwargs.get("item_model")
        raw_values = data.get("values") or []
        values = (
            [item_model.from_api_response(v) for v in raw_values]
            if item_model
            else list(raw_values)
        )
        is_last = bool(data.get("isLastPage", True))
        return cls(
            values=values,
            start=int(data.get("start", 0) or 0),
            limit=int(data.get("limit", 25) or 25),
            is_last_page=is_last,
            next_page_start=None if is_last else data.get("nextPageStart"),
        )

    def to_simplified_dict(self) -> dict[str, Any]:
        """Serialize values with their own simplified form plus paging info."""
        result: dict[str, Any] = {
            "values": [
                v.to_simplified_dict() if isinstance(v, ApiModel) else v
                for v in self.values
            ],
            "start": self.start,
            "limit": self.limit,
            "is_last_page": self.is_last_page,
        }
        if self.next_page_start is not None:
            result["next_page_start"] = self.next_page_start
        return result
