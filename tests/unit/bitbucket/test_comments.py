"""Commenting and tasks on pull requests, driven through MCP."""

from __future__ import annotations

import dataclasses

import pytest

from .fake_bitbucket import comment_payload, inline_anchor

pytestmark = pytest.mark.anyio

PR = "/rest/api/latest/projects/PLAT/repos/api/pull-requests/7"
COMMENTS = f"{PR}/comments"


def args(**extra):
    return {"project_key": "PLAT", "repo_slug": "api", "pull_request_id": 7, **extra}


class TestAddComment:
    async def test_general_comment(self, bb, fake_bitbucket):
        fake_bitbucket.add(
            "POST", COMMENTS, comment_payload(50, "Looks good"), status=201
        )

        result = await bb.call(
            "bitbucket_add_pull_request_comment", **args(text="Looks **good**")
        )

        (request,) = fake_bitbucket.requests_to("POST", COMMENTS)
        assert request.body == {"text": "Looks **good**"}
        assert result["id"] == 50

    @pytest.mark.parametrize(
        ("line_type", "expected_file_type"),
        [("ADDED", "TO"), ("CONTEXT", "TO"), ("REMOVED", "FROM")],
    )
    async def test_inline_comment_infers_file_type(
        self, bb, fake_bitbucket, line_type, expected_file_type
    ):
        fake_bitbucket.add(
            "POST",
            COMMENTS,
            comment_payload(51, "Nit", anchor=inline_anchor("src/app.py", 12)),
            status=201,
        )

        result = await bb.call(
            "bitbucket_add_pull_request_comment",
            **args(text="Nit", path="src/app.py", line=12, line_type=line_type),
        )

        (request,) = fake_bitbucket.requests_to("POST", COMMENTS)
        assert request.body == {
            "text": "Nit",
            "anchor": {
                "path": "src/app.py",
                "line": 12,
                "lineType": line_type,
                "fileType": expected_file_type,
                "diffType": "EFFECTIVE",
            },
        }
        assert result["anchor"]["path"] == "src/app.py"

    async def test_explicit_file_type_wins(self, bb, fake_bitbucket):
        fake_bitbucket.add("POST", COMMENTS, comment_payload(52, "x"), status=201)

        await bb.call(
            "bitbucket_add_pull_request_comment",
            **args(
                text="x", path="a.py", line=3, line_type="CONTEXT", file_type="FROM"
            ),
        )

        (request,) = fake_bitbucket.requests_to("POST", COMMENTS)
        assert request.body["anchor"]["fileType"] == "FROM"

    async def test_file_level_comment_without_line(self, bb, fake_bitbucket):
        fake_bitbucket.add("POST", COMMENTS, comment_payload(53, "x"), status=201)

        await bb.call(
            "bitbucket_add_pull_request_comment", **args(text="x", path="a.py")
        )

        (request,) = fake_bitbucket.requests_to("POST", COMMENTS)
        assert request.body["anchor"] == {"path": "a.py", "diffType": "EFFECTIVE"}

    async def test_reply(self, bb, fake_bitbucket):
        fake_bitbucket.add("POST", COMMENTS, comment_payload(54, "Done"), status=201)

        await bb.call(
            "bitbucket_add_pull_request_comment",
            **args(text="Done", parent_comment_id=41),
        )

        (request,) = fake_bitbucket.requests_to("POST", COMMENTS)
        assert request.body == {"text": "Done", "parent": {"id": 41}}

    async def test_task(self, bb, fake_bitbucket):
        fake_bitbucket.add(
            "POST",
            COMMENTS,
            comment_payload(55, "Add tests", severity="BLOCKER"),
            status=201,
        )

        result = await bb.call(
            "bitbucket_add_pull_request_comment", **args(text="Add tests", as_task=True)
        )

        (request,) = fake_bitbucket.requests_to("POST", COMMENTS)
        assert request.body == {"text": "Add tests", "severity": "BLOCKER"}
        assert result["is_task"] is True

    async def test_line_without_path_is_rejected(self, bb, fake_bitbucket):
        message = await bb.call_error(
            "bitbucket_add_pull_request_comment", **args(text="x", line=3)
        )

        assert "path" in message
        assert fake_bitbucket.requests == []


class TestUpdateComment:
    async def test_edits_text_with_current_version(self, bb, fake_bitbucket):
        fake_bitbucket.add("GET", f"{COMMENTS}/41", comment_payload(41, "old", version=4))
        fake_bitbucket.add(
            "PUT", f"{COMMENTS}/41", comment_payload(41, "new", version=5)
        )

        result = await bb.call(
            "bitbucket_update_pull_request_comment", **args(comment_id=41, text="new")
        )

        (request,) = fake_bitbucket.requests_to("PUT", f"{COMMENTS}/41")
        assert request.body == {"version": 4, "text": "new"}
        assert result["text"] == "new"

    @pytest.mark.parametrize(
        ("task_state", "sent"), [("resolved", "RESOLVED"), ("open", "OPEN")]
    )
    async def test_resolves_and_reopens_tasks(
        self, bb, fake_bitbucket, task_state, sent
    ):
        fake_bitbucket.add(
            "GET",
            f"{COMMENTS}/40",
            comment_payload(40, "Add tests", severity="BLOCKER", version=1),
        )
        fake_bitbucket.add(
            "PUT",
            f"{COMMENTS}/40",
            comment_payload(40, "Add tests", severity="BLOCKER", state=sent),
        )

        await bb.call(
            "bitbucket_update_pull_request_comment",
            **args(comment_id=40, task_state=task_state),
        )

        (request,) = fake_bitbucket.requests_to("PUT", f"{COMMENTS}/40")
        assert request.body == {"version": 1, "state": sent}

    async def test_needs_text_or_task_state(self, bb, fake_bitbucket):
        message = await bb.call_error(
            "bitbucket_update_pull_request_comment", **args(comment_id=41)
        )

        assert "text" in message and "task_state" in message
        assert fake_bitbucket.requests == []


class TestWriteSafety:
    async def test_read_only_mode_blocks_review_tools(
        self, bitbucket_mcp_factory, bitbucket_config, fake_bitbucket
    ):
        async with bitbucket_mcp_factory(bitbucket_config, read_only=True) as client:
            names = await client.tool_names()
            message = await client.call_error(
                "bitbucket_add_pull_request_comment", **args(text="x")
            )

        assert "bitbucket_add_pull_request_comment" not in names
        assert "bitbucket_update_pull_request_comment" not in names
        assert "bitbucket_get_pull_request" in names
        assert "Unknown tool" in message
        assert fake_bitbucket.requests == []

    async def test_respects_projects_filter(
        self, bitbucket_mcp_factory, bitbucket_config, fake_bitbucket
    ):
        config = dataclasses.replace(bitbucket_config, projects_filter="OPS")
        async with bitbucket_mcp_factory(config) as client:
            for tool, extra in [
                ("bitbucket_add_pull_request_comment", {"text": "x"}),
                ("bitbucket_update_pull_request_comment", {"comment_id": 1, "text": "x"}),
            ]:
                message = await client.call_error(tool, **args(**extra))
                assert "BITBUCKET_PROJECTS_FILTER" in message, tool
        assert fake_bitbucket.requests == []
