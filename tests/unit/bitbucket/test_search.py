"""Code search through the unofficial search endpoint, driven through MCP."""

from __future__ import annotations

import dataclasses

import pytest

from .fake_bitbucket import repository

pytestmark = pytest.mark.anyio

SEARCH = "/rest/search/latest/search"


def hit(project_key, slug, path, lines, hit_count=1, path_matches=None):
    return {
        "repository": repository(project_key, slug),
        "file": path,
        "hitContexts": [[{"line": n, "text": text} for n, text in lines]]
        if lines
        else [],
        "pathMatches": path_matches or [],
        "hitCount": hit_count,
    }


def results(values, *, is_last_page=True, next_start=None, start=0, count=None):
    code = {
        "category": "primary",
        "isLastPage": is_last_page,
        "count": len(values) if count is None else count,
        "start": start,
        "values": values,
    }
    if next_start is not None:
        code["nextStart"] = next_start
    return {"scope": {"type": "GLOBAL"}, "code": code, "query": {"substituted": False}}


async def test_returns_file_repository_and_matching_lines(bb, fake_bitbucket):
    fake_bitbucket.add(
        "POST",
        SEARCH,
        results(
            [
                hit(
                    "PLAT",
                    "api",
                    "src/auth.py",
                    [(11, "def <em>login</em>(user):"), (12, "    a &lt; b")],
                    hit_count=2,
                )
            ],
            is_last_page=False,
            next_start=25,
            count=40,
        ),
    )

    result = await bb.call("bitbucket_search_code", query="login")

    assert result["values"] == [
        {
            "project_key": "PLAT",
            "repo_slug": "api",
            "path": "src/auth.py",
            "hit_count": 2,
            "matches": [
                {"line": 11, "text": "def login(user):", "match": True},
                {"line": 12, "text": "    a < b"},
            ],
        }
    ]
    assert result["total"] == 40
    assert result["next_page_start"] == 25
    (request,) = fake_bitbucket.requests_to("POST", SEARCH)
    assert request.body == {
        "query": "login",
        "entities": {"code": {"start": 0, "limit": 25}},
        "limits": {"primary": 25, "secondary": 10},
    }


async def test_file_name_match_is_flagged(bb, fake_bitbucket):
    fake_bitbucket.add(
        "POST",
        SEARCH,
        results(
            [
                hit(
                    "PLAT",
                    "api",
                    "123.txt",
                    [],
                    hit_count=0,
                    path_matches=[{"text": "123", "match": True}, {"text": ".txt"}],
                )
            ]
        ),
    )

    result = await bb.call("bitbucket_search_code", query="123")

    assert result["values"] == [
        {
            "project_key": "PLAT",
            "repo_slug": "api",
            "path": "123.txt",
            "hit_count": 0,
            "path_match": True,
            "matches": [],
        }
    ]


async def test_narrows_to_project_and_repository(bb, fake_bitbucket):
    fake_bitbucket.add("POST", SEARCH, results([]))

    await bb.call(
        "bitbucket_search_code",
        query="TODO lang:python",
        project_key="plat",
        repo_slug="api",
        start=25,
        limit=10,
    )

    (request,) = fake_bitbucket.requests_to("POST", SEARCH)
    assert request.body["query"] == "TODO lang:python project:PLAT repo:api"
    assert request.body["entities"] == {"code": {"start": 25, "limit": 10}}


async def test_repo_slug_needs_project_key(bb, fake_bitbucket):
    message = await bb.call_error("bitbucket_search_code", query="x", repo_slug="api")

    assert "project_key" in message
    assert fake_bitbucket.requests == []


@pytest.mark.parametrize(
    ("status", "body"),
    [
        (404, {"errors": [{"message": "Not found"}]}),
        (503, {"errors": [{"message": "Search is currently unavailable"}]}),
    ],
)
async def test_unavailable_search_is_reported_clearly(bb, fake_bitbucket, status, body):
    fake_bitbucket.add("POST", SEARCH, body, status=status)

    message = await bb.call_error("bitbucket_search_code", query="x")

    assert "code search is unavailable" in message.lower()
    assert "bitbucket_list_files" in message


async def test_unexpected_response_shape_is_reported_as_unavailable(bb, fake_bitbucket):
    fake_bitbucket.add("POST", SEARCH, {"something": "else"})

    message = await bb.call_error("bitbucket_search_code", query="x")

    assert "code search is unavailable" in message.lower()


class TestProjectsFilter:
    async def test_single_allowed_project_is_injected_and_hits_filtered(
        self, bitbucket_mcp_factory, bitbucket_config, fake_bitbucket
    ):
        fake_bitbucket.add(
            "POST",
            SEARCH,
            results(
                [
                    hit("PLAT", "api", "a.py", [(1, "x")]),
                    hit("OPS", "infra", "b.py", [(1, "x")]),
                ]
            ),
        )
        config = dataclasses.replace(bitbucket_config, projects_filter="PLAT")
        async with bitbucket_mcp_factory(config) as client:
            result = await client.call("bitbucket_search_code", query="x")

        (request,) = fake_bitbucket.requests_to("POST", SEARCH)
        assert request.body["query"] == "x project:PLAT"
        assert [v["project_key"] for v in result["values"]] == ["PLAT"]

    async def test_several_allowed_projects_are_ored_into_the_query(
        self, bitbucket_mcp_factory, bitbucket_config, fake_bitbucket
    ):
        fake_bitbucket.add(
            "POST",
            SEARCH,
            results(
                [
                    hit("PLAT", "api", "a.py", [(1, "x")]),
                    hit("SEC", "vault", "s.py", [(1, "x")]),
                    hit("OPS", "infra", "b.py", [(1, "x")]),
                ]
            ),
        )
        config = dataclasses.replace(bitbucket_config, projects_filter="PLAT,OPS")
        async with bitbucket_mcp_factory(config) as client:
            result = await client.call("bitbucket_search_code", query="x")

        (request,) = fake_bitbucket.requests_to("POST", SEARCH)
        # Bitbucket ANDs bare project: terms; OR inside parentheses spans both.
        assert request.body["query"] == "x (project:OPS OR project:PLAT)"
        assert [v["project_key"] for v in result["values"]] == ["PLAT", "OPS"]

    async def test_refuses_project_outside_filter(
        self, bitbucket_mcp_factory, bitbucket_config, fake_bitbucket
    ):
        config = dataclasses.replace(bitbucket_config, projects_filter="PLAT")
        async with bitbucket_mcp_factory(config) as client:
            message = await client.call_error(
                "bitbucket_search_code", query="x", project_key="OPS"
            )

        assert "BITBUCKET_PROJECTS_FILTER" in message
        assert fake_bitbucket.requests == []


def test_search_toolset_is_not_default():
    from mcp_atlassian.utils.toolsets import ALL_TOOLSETS, DEFAULT_TOOLSETS

    assert "bitbucket_search" in ALL_TOOLSETS
    assert "bitbucket_search" not in DEFAULT_TOOLSETS
