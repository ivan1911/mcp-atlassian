"""Value types shared by the Bitbucket fetcher and its MCP tools."""

from typing import Literal

PullRequestState = Literal["OPEN", "MERGED", "DECLINED", "ALL"]
PullRequestDirection = Literal["INCOMING", "OUTGOING"]
PullRequestRole = Literal["AUTHOR", "REVIEWER", "PARTICIPANT"]
ParticipantStatus = Literal["APPROVED", "UNAPPROVED", "NEEDS_WORK"]
ReviewerStatus = Literal["approved", "needs_work", "unapproved"]
TaskState = Literal["open", "resolved"]
# Kind of the diff line an inline comment is anchored to.
LineType = Literal["ADDED", "REMOVED", "CONTEXT"]
# Side of the diff: FROM (old file) or TO (new file).
FileType = Literal["FROM", "TO"]
