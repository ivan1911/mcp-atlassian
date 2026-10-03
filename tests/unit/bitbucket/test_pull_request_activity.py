"""Pull request diff and activity, driven through MCP."""

from __future__ import annotations

import dataclasses

import pytest

from .fake_bitbucket import (
    activity,
    comment_payload,
    diff,
    file_diff,
    hunk,
    inline_anchor,
    page,
)

pytestmark = pytest.mark.anyio

PR = "/rest/api/latest/projects/PLAT/repos/api/pull-requests/7"


def args(**extra):
    return {"project_key": "PLAT", "repo_slug": "api", "pull_request_id": 7, **extra}


class TestPullRequestDiff:
    async def test_renders_unified_diff(self, bb, fake_bitbucket):
        fake_bitbucket.add(
            "GET",
            f"{PR}/diff",
            diff([file_diff("a.py", "a.py", [hunk(1, 1, [("ADDED", ["x = 1"])])])]),
        )

        text = await bb.call("bitbucket_get_pull_request_diff", **args())

        assert text == (
            "# Diff of pull request #7 (1 file)\n"
            "diff --git a/a.py b/a.py\n"
            "--- a/a.py\n"
            "+++ b/a.py\n"
            "@@ -1,0 +1,1 @@\n"
            "+x = 1\n"
        )

    async def test_one_file_with_options_and_truncation_notice(
        self, bb, fake_bitbucket
    ):
        fake_bitbucket.add(
            "GET",
            f"{PR}/diff/src/big.sql",
            diff(
                [file_diff("src/big.sql", "src/big.sql", truncated=True)],
                truncated=True,
            ),
        )

        text = await bb.call(
            "bitbucket_get_pull_request_diff",
            **args(path="src/big.sql", context_lines=0, ignore_whitespace=True),
        )

        assert "truncated" in text.splitlines()[1].lower()
        (request,) = fake_bitbucket.requests_to("GET", f"{PR}/diff/src/big.sql")
        assert request.query == {"contextLines": "0", "whitespace": "ignore-all"}


class TestPullRequestActivity:
    async def test_threads_tasks_anchors_and_approvals(self, bb, fake_bitbucket):
        fake_bitbucket.add(
            "GET",
            f"{PR}/activities",
            page(
                [
                    activity(
                        3,
                        "COMMENTED",
                        commentAction="ADDED",
                        comment=comment_payload(
                            41,
                            "Why not a dict?",
                            anchor=inline_anchor("src/app.py", 12),
                            replies=[comment_payload(42, "Fair point", author="alice")],
                        ),
                        commentAnchor=inline_anchor("src/app.py", 12),
                    ),
                    activity(
                        2,
                        "COMMENTED",
                        commentAction="ADDED",
                        comment=comment_payload(
                            40, "Add tests", severity="BLOCKER", state="RESOLVED"
                        ),
                    ),
                    activity(1, "APPROVED", actor="carol"),
                ]
            ),
        )

        result = await bb.call("bitbucket_get_pull_request_activity", **args())

        thread, task, approval = result["values"]
        assert thread["action"] == "COMMENTED"
        assert thread["comment"]["id"] == 41
        assert thread["comment"]["text"] == "Why not a dict?"
        assert thread["comment"]["anchor"] == {
            "path": "src/app.py",
            "line": 12,
            "line_type": "ADDED",
            "file_type": "TO",
        }
        assert [(r["id"], r["author"]) for r in thread["comment"]["replies"]] == [
            (42, "alice")
        ]
        assert task["comment"]["is_task"] is True
        assert task["comment"]["state"] == "resolved"
        assert approval == {
            "id": 1,
            "action": "APPROVED",
            "user": "carol",
            "created": "2023-11-14T22:13:20+00:00",
        }

    async def test_anchor_from_activity_when_comment_has_none(self, bb, fake_bitbucket):
        fake_bitbucket.add(
            "GET",
            f"{PR}/activities",
            page(
                [
                    activity(
                        4,
                        "COMMENTED",
                        commentAction="ADDED",
                        comment=comment_payload(43, "Off by one"),
                        commentAnchor=inline_anchor(
                            "src/loop.py", 7, "REMOVED", "FROM"
                        ),
                    )
                ]
            ),
        )

        result = await bb.call("bitbucket_get_pull_request_activity", **args())

        (entry,) = result["values"]
        assert entry["comment"]["anchor"] == {
            "path": "src/loop.py",
            "line": 7,
            "line_type": "REMOVED",
            "file_type": "FROM",
        }

    async def test_unknown_activity_is_passed_through(self, bb, fake_bitbucket):
        weird = activity(9, "AUTO_MERGE_REQUESTED", pluginData={"x": 1})
        fake_bitbucket.add("GET", f"{PR}/activities", page([weird]))

        result = await bb.call("bitbucket_get_pull_request_activity", **args())

        (entry,) = result["values"]
        assert entry["action"] == "AUTO_MERGE_REQUESTED"
        assert entry["raw"]["pluginData"] == {"x": 1}

    async def test_rescope_lists_added_and_removed_commits(self, bb, fake_bitbucket):
        fake_bitbucket.add(
            "GET",
            f"{PR}/activities",
            page(
                [
                    activity(
                        5,
                        "RESCOPED",
                        added={"commits": [{"id": "a" * 40}], "total": 1},
                        removed={"commits": [], "total": 0},
                    )
                ]
            ),
        )

        result = await bb.call("bitbucket_get_pull_request_activity", **args())

        (entry,) = result["values"]
        assert entry["added_commits"] == ["a" * 40]
        assert entry["removed_commits"] == []


async def test_respects_projects_filter(
    bitbucket_mcp_factory, bitbucket_config, fake_bitbucket
):
    config = dataclasses.replace(bitbucket_config, projects_filter="OPS")
    async with bitbucket_mcp_factory(config) as client:
        for tool in (
            "bitbucket_get_pull_request_diff",
            "bitbucket_get_pull_request_activity",
        ):
            message = await client.call_error(tool, **args())
            assert "BITBUCKET_PROJECTS_FILTER" in message, tool
    assert fake_bitbucket.requests == []
