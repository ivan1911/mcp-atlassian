"""Reviewer status and pending review, driven through MCP."""

from __future__ import annotations

import dataclasses

import pytest

from .fake_bitbucket import comment_payload, page, participant, pull_request, user

pytestmark = pytest.mark.anyio

API = "/rest/api/latest"
PR = f"{API}/projects/PLAT/repos/api/pull-requests/7"
WHOAMI = f"{API}/application-properties"
USERS = f"{API}/users"


def args(**extra):
    return {"project_key": "PLAT", "repo_slug": "api", "pull_request_id": 7, **extra}


def known_user(fake, username="Alice.Smith", slug="alice.smith"):
    fake.add("GET", WHOAMI, {"version": "10.0.1"}, headers={"X-AUSERNAME": username})
    other = user("alice.smithers")
    me = {**user(slug), "name": username, "slug": slug}
    fake.add("GET", USERS, page([other, me]))


class TestSetReviewerStatus:
    @pytest.mark.parametrize(
        ("status", "sent"),
        [
            ("approved", "APPROVED"),
            ("needs_work", "NEEDS_WORK"),
            ("unapproved", "UNAPPROVED"),
        ],
    )
    async def test_sets_status_as_the_token_user(
        self, bb, fake_bitbucket, status, sent
    ):
        known_user(fake_bitbucket)
        path = f"{PR}/participants/alice.smith"
        fake_bitbucket.add("PUT", path, participant("alice.smith", sent))

        result = await bb.call(
            "bitbucket_set_reviewer_status", **args(status=status, version=3)
        )

        (request,) = fake_bitbucket.requests_to("PUT", path)
        assert request.query == {"version": "3"}
        assert request.body == {"status": sent}
        (lookup,) = fake_bitbucket.requests_to("GET", USERS)
        assert lookup.query["filter"] == "Alice.Smith"
        assert result["status"] == status
        assert fake_bitbucket.requests_to("GET", PR) == []

    async def test_reads_version_when_omitted(self, bb, fake_bitbucket):
        known_user(fake_bitbucket)
        fake_bitbucket.add("GET", PR, pull_request(7, version=6))
        path = f"{PR}/participants/alice.smith"
        fake_bitbucket.add("PUT", path, participant("alice.smith", "APPROVED"))

        await bb.call("bitbucket_set_reviewer_status", **args(status="approved"))

        (request,) = fake_bitbucket.requests_to("PUT", path)
        assert request.query == {"version": "6"}


class TestPendingReview:
    async def test_pending_comment(self, bb, fake_bitbucket):
        fake_bitbucket.add(
            "POST",
            f"{PR}/comments",
            comment_payload(60, "Nit", state="PENDING"),
            status=201,
        )

        result = await bb.call(
            "bitbucket_add_pull_request_comment", **args(text="Nit", pending=True)
        )

        (request,) = fake_bitbucket.requests_to("POST", f"{PR}/comments")
        assert request.body == {"text": "Nit", "state": "PENDING"}
        assert result["state"] == "pending"

    async def test_publish_review_with_status_and_summary(self, bb, fake_bitbucket):
        fake_bitbucket.add("PUT", f"{PR}/review", participant("alice", "NEEDS_WORK"))

        result = await bb.call(
            "bitbucket_publish_review",
            **args(status="needs_work", comment="Two blocking issues, see inline."),
        )

        (request,) = fake_bitbucket.requests_to("PUT", f"{PR}/review")
        assert request.body == {
            "participantStatus": "NEEDS_WORK",
            "commentText": "Two blocking issues, see inline.",
        }
        assert result["published"] is True
        assert result["status"] == "needs_work"

    async def test_publish_review_without_options(self, bb, fake_bitbucket):
        fake_bitbucket.add("PUT", f"{PR}/review", participant("alice"))

        await bb.call("bitbucket_publish_review", **args())

        (request,) = fake_bitbucket.requests_to("PUT", f"{PR}/review")
        assert request.body == {}


async def test_read_only_and_filter(
    bitbucket_mcp_factory, bitbucket_config, fake_bitbucket
):
    tools = [
        ("bitbucket_set_reviewer_status", args(status="approved")),
        ("bitbucket_publish_review", args()),
    ]
    async with bitbucket_mcp_factory(bitbucket_config, read_only=True) as client:
        names = await client.tool_names()
        for tool, arguments in tools:
            assert tool not in names
            assert "Unknown tool" in await client.call_error(tool, **arguments)
    config = dataclasses.replace(bitbucket_config, projects_filter="OPS")
    async with bitbucket_mcp_factory(config) as client:
        for tool, arguments in tools:
            assert "BITBUCKET_PROJECTS_FILTER" in await client.call_error(
                tool, **arguments
            )
    assert fake_bitbucket.requests == []
