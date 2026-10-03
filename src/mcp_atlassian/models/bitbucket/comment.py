"""Bitbucket pull request comments, tasks and activity."""

from typing import Any

from pydantic import Field

from mcp_atlassian.models.base import ApiModel

from .common import iso_from_millis


class BitbucketCommentAnchor(ApiModel):
    """Where an inline comment is anchored in the diff."""

    path: str | None = None
    line: int | None = None
    line_type: str | None = None  # ADDED, REMOVED or CONTEXT
    file_type: str | None = None  # FROM (old side) or TO (new side)
    src_path: str | None = None
    diff_type: str | None = None
    orphaned: bool | None = None

    @classmethod
    def from_api_response(
        cls, data: dict[str, Any], **kwargs: Any
    ) -> "BitbucketCommentAnchor":
        """Build from a Bitbucket ``RestCommentThreadDiffAnchor``.

        Defaults are dropped (src_path equal to path, EFFECTIVE diff type,
        non-orphaned) to keep output compact.
        """
        path = data.get("path")
        src_path = data.get("srcPath")
        diff_type = data.get("diffType")
        return cls(
            path=path,
            line=data.get("line"),
            line_type=data.get("lineType"),
            file_type=data.get("fileType"),
            src_path=src_path if src_path and src_path != path else None,
            diff_type=diff_type if diff_type and diff_type != "EFFECTIVE" else None,
            orphaned=True if data.get("orphaned") else None,
        )


class BitbucketComment(ApiModel):
    """A pull request comment; a task when ``is_task`` (blocker severity)."""

    id: int
    version: int | None = None
    text: str | None = None
    author: str | None = None  # user slug
    created: str | None = None
    updated: str | None = None
    is_task: bool = False
    state: str | None = None  # open, resolved or pending
    anchor: BitbucketCommentAnchor | None = None
    replies: list["BitbucketComment"] = Field(default_factory=list)

    @classmethod
    def from_api_response(
        cls, data: dict[str, Any], **kwargs: Any
    ) -> "BitbucketComment":
        """Build from a Bitbucket ``RestComment`` (with nested replies)."""
        anchor = data.get("anchor")
        state = data.get("state")
        created = data.get("createdDate")
        updated = data.get("updatedDate")
        return cls(
            id=int(data.get("id", 0)),
            version=data.get("version"),
            text=data.get("text"),
            author=(data.get("author") or {}).get("slug"),
            created=iso_from_millis(created),
            updated=iso_from_millis(updated) if updated != created else None,
            is_task=data.get("severity") == "BLOCKER",
            state=str(state).lower() if state else None,
            anchor=BitbucketCommentAnchor.from_api_response(anchor)
            if isinstance(anchor, dict)
            else None,
            replies=[
                cls.from_api_response(reply)
                for reply in data.get("comments") or []
                if isinstance(reply, dict)
            ],
        )

    def to_simplified_dict(self) -> dict[str, Any]:
        """Serialize, omitting an empty reply list."""
        result = super().to_simplified_dict()
        if not self.replies:
            result.pop("replies", None)
        return result


_KNOWN_ACTIONS = {
    "APPROVED",
    "UNAPPROVED",
    "REVIEWED",
    "COMMENTED",
    "RESCOPED",
    "MERGED",
    "DECLINED",
    "REOPENED",
    "OPENED",
    "UPDATED",
    "DELETED",
}


def activity_from_api(data: dict[str, Any]) -> dict[str, Any]:
    """Simplify one pull request activity entry.

    Unknown activity kinds (from plugins or newer Bitbucket versions) are
    returned with their raw payload instead of failing.
    """
    action = str(data.get("action", ""))
    result: dict[str, Any] = {"id": data.get("id"), "action": action}
    user = data.get("user")
    if isinstance(user, dict) and user.get("slug"):
        result["user"] = user["slug"]
    created = iso_from_millis(data.get("createdDate"))
    if created:
        result["created"] = created
    if action not in _KNOWN_ACTIONS:
        result["raw"] = data
        return result

    if action == "COMMENTED" and isinstance(data.get("comment"), dict):
        if data.get("commentAction"):
            result["comment_action"] = data["commentAction"]
        comment = BitbucketComment.from_api_response(data["comment"])
        # Some versions put the inline anchor on the activity, not the comment.
        activity_anchor = data.get("commentAnchor")
        if comment.anchor is None and isinstance(activity_anchor, dict):
            comment.anchor = BitbucketCommentAnchor.from_api_response(activity_anchor)
        result["comment"] = comment.to_simplified_dict()
    elif action == "RESCOPED":
        for side in ("added", "removed"):
            commits = (data.get(side) or {}).get("commits") or []
            result[f"{side}_commits"] = [c.get("id") for c in commits]
    elif action == "MERGED" and isinstance(data.get("commit"), dict):
        result["merge_commit"] = data["commit"].get("id")
    return result
