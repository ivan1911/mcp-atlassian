"""Finding and reading pull requests, driven through MCP."""

from __future__ import annotations

import dataclasses

import pytest

from .fake_bitbucket import change, commit, page, participant, pull_request

pytestmark = pytest.mark.anyio

API = "/rest/api/latest"
REPO = f"{API}/projects/PLAT/repos/api"
PRS = f"{REPO}/pull-requests"
SHA = "0123456789abcdef0123456789abcdef01234567"


def repo_args(**extra):
    return {"project_key": "PLAT", "repo_slug": "api", **extra}


class TestListPullRequests:
    async def test_lists_open_pull_requests_by_default(self, bb, fake_bitbucket):
        fake_bitbucket.add("GET", PRS, page([pull_request(7), pull_request(8, "Fix")]))

        result = await bb.call("bitbucket_list_pull_requests", **repo_args())

        assert [(p["id"], p["title"]) for p in result["values"]] == [
            (7, "Add login"),
            (8, "Fix"),
        ]
        (request,) = fake_bitbucket.requests_to("GET", PRS)
        assert request.query["state"] == "OPEN"

    async def test_filters_by_state_author_reviewer_target_and_text(
        self, bb, fake_bitbucket
    ):
        fake_bitbucket.add("GET", PRS, page([]))

        await bb.call(
            "bitbucket_list_pull_requests",
            **repo_args(
                state="MERGED",
                author="alice",
                reviewer="bob",
                target_branch="main",
                text="login",
                direction="OUTGOING",
            ),
        )

        (request,) = fake_bitbucket.requests_to("GET", PRS)
        assert request.query == {
            "state": "MERGED",
            "direction": "OUTGOING",
            "at": "refs/heads/main",
            "filterText": "login",
            "username.1": "alice",
            "role.1": "AUTHOR",
            "username.2": "bob",
            "role.2": "REVIEWER",
            "start": "0",
            "limit": "25",
        }


class TestMyPullRequests:
    async def test_lists_dashboard_by_role_within_the_filter(
        self, bitbucket_mcp_factory, bitbucket_config, fake_bitbucket
    ):
        fake_bitbucket.add(
            "GET",
            f"{API}/dashboard/pull-requests",
            page(
                [
                    pull_request(7, project_key="PLAT"),
                    pull_request(9, project_key="OPS", slug="infra"),
                ]
            ),
        )
        config = dataclasses.replace(bitbucket_config, projects_filter="PLAT")
        async with bitbucket_mcp_factory(config) as client:
            result = await client.call(
                "bitbucket_get_my_pull_requests", role="REVIEWER"
            )

        assert [(p["id"], p["target"]["project_key"]) for p in result["values"]] == [
            (7, "PLAT")
        ]
        (request,) = fake_bitbucket.requests_to("GET", f"{API}/dashboard/pull-requests")
        assert request.query["role"] == "REVIEWER"
        assert request.query["state"] == "OPEN"


class TestGetPullRequest:
    async def test_returns_details_reviewers_and_version(self, bb, fake_bitbucket):
        fake_bitbucket.add(
            "GET",
            f"{PRS}/7",
            pull_request(
                7,
                version=5,
                reviewers=[
                    participant("bob", "APPROVED"),
                    participant("carol", "NEEDS_WORK"),
                ],
            ),
        )

        result = await bb.call(
            "bitbucket_get_pull_request", **repo_args(pull_request_id=7)
        )

        assert result["id"] == 7
        assert result["version"] == 5
        assert result["state"] == "OPEN"
        assert result["description"] == "Implements add login"
        assert result["author"]["slug"] == "alice"
        assert result["source"] == {
            "branch": "feature/login",
            "latest_commit": "d" * 40,
            "project_key": "PLAT",
            "repo_slug": "api",
        }
        assert result["target"]["branch"] == "main"
        assert [(r["slug"], r["status"]) for r in result["reviewers"]] == [
            ("bob", "approved"),
            ("carol", "needs_work"),
        ]
        assert result["open_task_count"] == 1
        assert "merge_status" not in result

    async def test_optionally_includes_merge_status(self, bb, fake_bitbucket):
        fake_bitbucket.add("GET", f"{PRS}/7", pull_request(7))
        fake_bitbucket.add(
            "GET",
            f"{PRS}/7/merge",
            {
                "canMerge": False,
                "conflicted": True,
                "outcome": "CONFLICTED",
                "vetoes": [
                    {
                        "summaryMessage": "Requires approvals",
                        "detailedMessage": "You need 2 approvals",
                    }
                ],
            },
        )

        result = await bb.call(
            "bitbucket_get_pull_request",
            **repo_args(pull_request_id=7, include_merge_status=True),
        )

        assert result["merge_status"] == {
            "can_merge": False,
            "conflicted": True,
            "outcome": "CONFLICTED",
            "vetoes": ["Requires approvals: You need 2 approvals"],
        }


class TestChangesAndCommits:
    async def test_lists_changed_files(self, bb, fake_bitbucket):
        fake_bitbucket.add(
            "GET",
            f"{PRS}/7/changes",
            page([change("src/app.py"), change("src/old.py", "DELETE")]),
        )

        result = await bb.call(
            "bitbucket_get_pull_request_changes", **repo_args(pull_request_id=7)
        )

        assert result["values"] == [
            {"path": "src/app.py", "type": "MODIFY"},
            {"path": "src/old.py", "type": "DELETE"},
        ]

    async def test_lists_commits(self, bb, fake_bitbucket):
        fake_bitbucket.add("GET", f"{PRS}/7/commits", page([commit(SHA, "Wire it")]))

        result = await bb.call(
            "bitbucket_get_pull_request_commits", **repo_args(pull_request_id=7)
        )

        assert [(c["id"], c["message"]) for c in result["values"]] == [(SHA, "Wire it")]


async def test_pull_request_tools_respect_projects_filter(
    bitbucket_mcp_factory, bitbucket_config, fake_bitbucket
):
    config = dataclasses.replace(bitbucket_config, projects_filter="OPS")
    async with bitbucket_mcp_factory(config) as client:
        for tool, extra in [
            ("bitbucket_list_pull_requests", {}),
            ("bitbucket_get_pull_request", {"pull_request_id": 7}),
            ("bitbucket_get_pull_request_changes", {"pull_request_id": 7}),
            ("bitbucket_get_pull_request_commits", {"pull_request_id": 7}),
        ]:
            message = await client.call_error(tool, **repo_args(**extra))
            assert "BITBUCKET_PROJECTS_FILTER" in message, tool
    assert fake_bitbucket.requests == []
