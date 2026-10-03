"""Repositories, the projects filter and paging, driven through MCP."""

from __future__ import annotations

import dataclasses

import pytest

from .fake_bitbucket import FakeBitbucket, branch_ref, page, project, repository

pytestmark = pytest.mark.anyio

API = "/rest/api/latest"


@pytest.fixture
async def filtered(bitbucket_mcp_factory, bitbucket_config):
    """MCP client with BITBUCKET_PROJECTS_FILTER=plat (lower case on purpose)."""
    config = dataclasses.replace(bitbucket_config, projects_filter="plat")
    async with bitbucket_mcp_factory(config) as client:
        yield client


class TestListRepositories:
    async def test_lists_repositories_of_a_project(self, bb, fake_bitbucket):
        fake_bitbucket.add(
            "GET",
            f"{API}/projects/PLAT/repos",
            page([repository("PLAT", "api"), repository("PLAT", "web")]),
        )

        result = await bb.call("bitbucket_list_repositories", project_key="PLAT")

        assert [(r["project_key"], r["slug"]) for r in result["values"]] == [
            ("PLAT", "api"),
            ("PLAT", "web"),
        ]

    async def test_searches_repositories_by_name_across_projects(
        self, bb, fake_bitbucket
    ):
        fake_bitbucket.add(
            "GET",
            f"{API}/repos",
            page([repository("PLAT", "billing-api"), repository("OPS", "billing")]),
        )

        result = await bb.call("bitbucket_list_repositories", name="billing")

        (request,) = fake_bitbucket.requests_to("GET", f"{API}/repos")
        assert request.query["name"] == "billing"
        assert {r["project_key"] for r in result["values"]} == {"PLAT", "OPS"}

    async def test_paging_follows_next_page_start(self, bb, fake_bitbucket):
        fake_bitbucket.add(
            "GET",
            f"{API}/projects/PLAT/repos",
            page([repository("PLAT", "api")], start=7, limit=1, next_page_start=12),
        )

        result = await bb.call(
            "bitbucket_list_repositories", project_key="PLAT", start=7, limit=1
        )

        assert result["next_page_start"] == 12
        (request,) = fake_bitbucket.requests_to("GET", f"{API}/projects/PLAT/repos")
        assert request.query == {"start": "7", "limit": "1"}


class TestGetRepository:
    async def test_returns_details_default_branch_and_clone_urls(
        self, bb, fake_bitbucket
    ):
        repo_path = f"{API}/projects/PLAT/repos/api"
        fake_bitbucket.add("GET", repo_path, repository("PLAT", "api"))
        fake_bitbucket.add(
            "GET", f"{repo_path}/default-branch", branch_ref("main", default=True)
        )

        result = await bb.call(
            "bitbucket_get_repository", project_key="PLAT", repo_slug="api"
        )

        assert result["project_key"] == "PLAT"
        assert result["slug"] == "api"
        assert result["default_branch"] == "main"
        assert result["clone_urls"] == {
            "http": "https://bitbucket.example.com/scm/plat/api.git",
            "ssh": "ssh://git@bitbucket.example.com:7999/plat/api.git",
        }

    async def test_empty_repository_has_no_default_branch(self, bb, fake_bitbucket):
        repo_path = f"{API}/projects/PLAT/repos/empty"
        fake_bitbucket.add("GET", repo_path, repository("PLAT", "empty"))
        fake_bitbucket.error(
            "GET", f"{repo_path}/default-branch", 404, "Repository is empty"
        )

        result = await bb.call(
            "bitbucket_get_repository", project_key="PLAT", repo_slug="empty"
        )

        assert result["slug"] == "empty"
        assert result.get("default_branch") is None


class TestProjectsFilter:
    async def test_hides_filtered_out_projects(self, filtered, fake_bitbucket):
        fake_bitbucket.add(
            "GET", f"{API}/projects", page([project("PLAT"), project("OPS")])
        )

        result = await filtered.call("bitbucket_list_projects")

        assert [p["key"] for p in result["values"]] == ["PLAT"]

    async def test_hides_repositories_of_filtered_out_projects(
        self, filtered, fake_bitbucket
    ):
        fake_bitbucket.add(
            "GET",
            f"{API}/repos",
            page([repository("PLAT", "billing-api"), repository("OPS", "billing")]),
        )

        result = await filtered.call("bitbucket_list_repositories", name="billing")

        assert [r["project_key"] for r in result["values"]] == ["PLAT"]

    @pytest.mark.parametrize(
        ("tool", "arguments"),
        [
            ("bitbucket_list_repositories", {"project_key": "OPS"}),
            ("bitbucket_get_repository", {"project_key": "ops", "repo_slug": "x"}),
        ],
    )
    async def test_refuses_direct_access_without_a_request(
        self, filtered, fake_bitbucket, tool, arguments
    ):
        message = await filtered.call_error(tool, **arguments)

        assert "BITBUCKET_PROJECTS_FILTER" in message
        assert fake_bitbucket.requests == []

    async def test_allows_permitted_project_case_insensitively(
        self, filtered, fake_bitbucket: FakeBitbucket
    ):
        fake_bitbucket.add(
            "GET", f"{API}/projects/PLAT/repos", page([repository("PLAT", "api")])
        )

        result = await filtered.call("bitbucket_list_repositories", project_key="Plat")

        assert [r["slug"] for r in result["values"]] == ["api"]
