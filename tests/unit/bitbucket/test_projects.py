"""Bitbucket project tools, driven through MCP over the fake HTTP boundary."""

from __future__ import annotations

import pytest

from .fake_bitbucket import FakeBitbucket, page, project

pytestmark = pytest.mark.anyio

PROJECTS = "/rest/api/latest/projects"


async def test_list_projects_returns_projects_and_next_page(
    bb, fake_bitbucket: FakeBitbucket
):
    fake_bitbucket.add(
        "GET",
        PROJECTS,
        page(
            [project("PLAT", "Platform"), project("OPS", "Operations")],
            limit=2,
            next_page_start=2,
        ),
    )

    result = await bb.call("bitbucket_list_projects", limit=2)

    assert [p["key"] for p in result["values"]] == ["PLAT", "OPS"]
    assert result["values"][0]["name"] == "Platform"
    assert result["values"][0]["url"] == "https://bitbucket.example.com/projects/PLAT"
    assert result["next_page_start"] == 2
    assert result["is_last_page"] is False


async def test_list_projects_sends_bearer_token_and_paging(
    bb, fake_bitbucket: FakeBitbucket
):
    fake_bitbucket.add("GET", PROJECTS, page([project("PLAT")]))

    await bb.call("bitbucket_list_projects", start=50, limit=10)

    (request,) = fake_bitbucket.requests_to("GET", PROJECTS)
    assert request.headers["Authorization"] == "Bearer test-token"
    assert request.query == {"start": "50", "limit": "10"}


async def test_list_projects_last_page_has_no_next_start(
    bb, fake_bitbucket: FakeBitbucket
):
    fake_bitbucket.add("GET", PROJECTS, page([project("PLAT")]))

    result = await bb.call("bitbucket_list_projects")

    assert result["is_last_page"] is True
    assert result.get("next_page_start") is None


async def test_bitbucket_error_message_reaches_the_assistant(
    bb, fake_bitbucket: FakeBitbucket
):
    fake_bitbucket.error("GET", PROJECTS, 400, "Limit must be positive")

    message = await bb.call_error("bitbucket_list_projects")

    assert "400" in message
    assert "Limit must be positive" in message


async def test_unauthorized_mentions_both_auth_and_permission(
    bb, fake_bitbucket: FakeBitbucket
):
    fake_bitbucket.error("GET", PROJECTS, 401, "Authentication failed")

    message = await bb.call_error("bitbucket_list_projects")

    assert "401" in message
    assert "permission" in message.lower()


async def test_rate_limit_is_reported_with_backoff_hint(
    bb, fake_bitbucket: FakeBitbucket
):
    fake_bitbucket.add("GET", PROJECTS, "Too many requests", status=429)

    message = await bb.call_error("bitbucket_list_projects")

    assert "429" in message
    assert "rate limit" in message.lower()
