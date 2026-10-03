"""Destructive toolset: delete pull request and branch, driven through MCP."""

from __future__ import annotations

import dataclasses

import pytest

from mcp_atlassian.utils.toolsets import get_enabled_toolsets

from .fake_bitbucket import pull_request

pytestmark = pytest.mark.anyio

PR = "/rest/api/latest/projects/PLAT/repos/api/pull-requests/7"
BRANCHES = "/rest/branch-utils/latest/projects/PLAT/repos/api/branches"
DESTRUCTIVE = {"bitbucket_delete_pull_request", "bitbucket_delete_branch"}


def repo_args(**extra):
    return {"project_key": "PLAT", "repo_slug": "api", **extra}


@pytest.fixture
async def opted_in(bitbucket_mcp_factory, bitbucket_config, monkeypatch):
    monkeypatch.setenv("TOOLSETS", "default,bitbucket_destructive")
    async with bitbucket_mcp_factory(
        bitbucket_config, enabled_toolsets=get_enabled_toolsets()
    ) as client:
        yield client


@pytest.mark.parametrize("toolsets", [None, "", "all", "default"])
async def test_destructive_tools_absent_unless_named(
    bitbucket_mcp_factory, bitbucket_config, fake_bitbucket, monkeypatch, toolsets
):
    monkeypatch.delenv("TOOLSETS", raising=False)
    if toolsets is not None:
        monkeypatch.setenv("TOOLSETS", toolsets)
    async with bitbucket_mcp_factory(
        bitbucket_config, enabled_toolsets=get_enabled_toolsets()
    ) as client:
        names = await client.tool_names()
        message = await client.call_error(
            "bitbucket_delete_branch", **repo_args(name="old")
        )

    assert names.isdisjoint(DESTRUCTIVE)
    assert "Unknown tool" in message
    assert fake_bitbucket.requests == []


async def test_destructive_tools_present_when_named(opted_in):
    assert DESTRUCTIVE <= await opted_in.tool_names()


async def test_delete_pull_request_reads_version(opted_in, fake_bitbucket):
    fake_bitbucket.add("GET", PR, pull_request(7, version=4))
    fake_bitbucket.add("DELETE", PR, None, status=204)

    result = await opted_in.call(
        "bitbucket_delete_pull_request", **repo_args(pull_request_id=7)
    )

    (request,) = fake_bitbucket.requests_to("DELETE", PR)
    assert request.body == {"version": 4}
    assert result == {"deleted": True, "pull_request_id": 7}


async def test_delete_pull_request_with_explicit_version(opted_in, fake_bitbucket):
    fake_bitbucket.add("DELETE", PR, None, status=204)

    await opted_in.call(
        "bitbucket_delete_pull_request", **repo_args(pull_request_id=7, version=2)
    )

    assert fake_bitbucket.requests_to("GET", PR) == []
    (request,) = fake_bitbucket.requests_to("DELETE", PR)
    assert request.body == {"version": 2}


async def test_delete_branch(opted_in, fake_bitbucket):
    fake_bitbucket.add("DELETE", BRANCHES, None, status=204)

    result = await opted_in.call(
        "bitbucket_delete_branch", **repo_args(name="feature/old")
    )

    (request,) = fake_bitbucket.requests_to("DELETE", BRANCHES)
    assert request.body == {"name": "refs/heads/feature/old", "dryRun": False}
    assert result == {"deleted": True, "branch": "refs/heads/feature/old"}


async def test_read_only_mode_blocks_destructive_tools(
    bitbucket_mcp_factory, bitbucket_config, fake_bitbucket, monkeypatch
):
    monkeypatch.setenv("TOOLSETS", "bitbucket_destructive")
    async with bitbucket_mcp_factory(
        bitbucket_config, read_only=True, enabled_toolsets=get_enabled_toolsets()
    ) as client:
        assert (await client.tool_names()).isdisjoint(DESTRUCTIVE)
        assert "Unknown tool" in await client.call_error(
            "bitbucket_delete_branch", **repo_args(name="x")
        )
    assert fake_bitbucket.requests == []


async def test_respects_projects_filter(
    bitbucket_mcp_factory, bitbucket_config, fake_bitbucket, monkeypatch
):
    monkeypatch.setenv("TOOLSETS", "bitbucket_destructive")
    config = dataclasses.replace(bitbucket_config, projects_filter="OPS")
    async with bitbucket_mcp_factory(
        config, enabled_toolsets=get_enabled_toolsets()
    ) as client:
        for tool, extra in [
            ("bitbucket_delete_pull_request", {"pull_request_id": 7}),
            ("bitbucket_delete_branch", {"name": "x"}),
        ]:
            assert "BITBUCKET_PROJECTS_FILTER" in await client.call_error(
                tool, **repo_args(**extra)
            )
    assert fake_bitbucket.requests == []
