"""Managing pull requests and creating branches, driven through MCP."""

from __future__ import annotations

import dataclasses

import pytest

from .fake_bitbucket import (
    branch_ref,
    participant,
    pull_request,
    repository,
    user,
)

pytestmark = pytest.mark.anyio

API = "/rest/api/latest"
REPO = f"{API}/projects/PLAT/repos/api"
PRS = f"{REPO}/pull-requests"
PR = f"{PRS}/7"
DEFAULT_REVIEWERS = "/rest/default-reviewers/latest/projects/PLAT/repos/api/reviewers"


def repo_args(**extra):
    return {"project_key": "PLAT", "repo_slug": "api", **extra}


def pr_args(**extra):
    return repo_args(pull_request_id=7, **extra)


def out_of_date(fake, method, path):
    fake.add(
        method,
        path,
        {
            "errors": [
                {
                    "context": None,
                    "message": "You are attempting to modify a pull request based "
                    "on out-of-date information.",
                    "exceptionName": "com.atlassian.bitbucket.pull."
                    "PullRequestOutOfDateException",
                    "currentVersion": 6,
                    "expectedVersion": 3,
                }
            ]
        },
        status=409,
    )


class TestCreatePullRequest:
    async def test_defaults_target_branch_and_reviewers(self, bb, fake_bitbucket):
        repo = repository("PLAT", "api", id=11)
        fake_bitbucket.add("GET", REPO, repo)
        fake_bitbucket.add("GET", f"{REPO}/default-branch", branch_ref("main"))
        fake_bitbucket.add("GET", DEFAULT_REVIEWERS, [user("bob"), user("carol")])
        fake_bitbucket.add("POST", PRS, pull_request(12, "Add login"), status=201)

        result = await bb.call(
            "bitbucket_create_pull_request",
            **repo_args(title="Add login", source_branch="feature/login"),
        )

        (reviewers_request,) = fake_bitbucket.requests_to("GET", DEFAULT_REVIEWERS)
        assert reviewers_request.query == {
            "sourceRepoId": "11",
            "targetRepoId": "11",
            "sourceRefId": "refs/heads/feature/login",
            "targetRefId": "refs/heads/main",
        }
        (create,) = fake_bitbucket.requests_to("POST", PRS)
        repo_ref = {"slug": "api", "project": {"key": "PLAT"}}
        assert create.body == {
            "title": "Add login",
            "fromRef": {"id": "refs/heads/feature/login", "repository": repo_ref},
            "toRef": {"id": "refs/heads/main", "repository": repo_ref},
            "reviewers": [{"user": {"name": "bob"}}, {"user": {"name": "carol"}}],
            "draft": False,
        }
        assert result["id"] == 12

    async def test_explicit_target_reviewers_description_and_draft(
        self, bb, fake_bitbucket
    ):
        fake_bitbucket.add("POST", PRS, pull_request(13), status=201)

        await bb.call(
            "bitbucket_create_pull_request",
            **repo_args(
                title="WIP",
                source_branch="refs/heads/spike",
                target_branch="develop",
                description="Draft",
                reviewers=["dave"],
                draft=True,
            ),
        )

        (create,) = fake_bitbucket.requests_to("POST", PRS)
        assert create.body["toRef"]["id"] == "refs/heads/develop"
        assert create.body["fromRef"]["id"] == "refs/heads/spike"
        assert create.body["description"] == "Draft"
        assert create.body["reviewers"] == [{"user": {"name": "dave"}}]
        assert create.body["draft"] is True
        assert fake_bitbucket.requests_to("GET", DEFAULT_REVIEWERS) == []


class TestVersionHandling:
    async def test_explicit_version_is_sent_without_reading_first(
        self, bb, fake_bitbucket
    ):
        fake_bitbucket.add("POST", f"{PR}/decline", pull_request(7, state="DECLINED"))

        await bb.call("bitbucket_decline_pull_request", **pr_args(version=3))

        assert fake_bitbucket.requests_to("GET", PR) == []
        (request,) = fake_bitbucket.requests_to("POST", f"{PR}/decline")
        assert request.query == {"version": "3"}

    async def test_omitted_version_is_read_first(self, bb, fake_bitbucket):
        fake_bitbucket.add("GET", PR, pull_request(7, version=8))
        fake_bitbucket.add("POST", f"{PR}/reopen", pull_request(7, version=9))

        await bb.call("bitbucket_reopen_pull_request", **pr_args())

        (request,) = fake_bitbucket.requests_to("POST", f"{PR}/reopen")
        assert request.query == {"version": "8"}

    async def test_version_conflict_says_re_read(self, bb, fake_bitbucket):
        out_of_date(fake_bitbucket, "POST", f"{PR}/merge")

        message = await bb.call_error(
            "bitbucket_merge_pull_request", **pr_args(version=3)
        )

        assert "changed since it was read" in message
        assert "bitbucket_get_pull_request" in message


class TestUpdatePullRequest:
    async def test_keeps_reviewers_when_not_given(self, bb, fake_bitbucket):
        fake_bitbucket.add(
            "GET",
            PR,
            pull_request(7, version=4, reviewers=[participant("bob", "APPROVED")]),
        )
        fake_bitbucket.add("PUT", PR, pull_request(7, "New title", version=5))

        result = await bb.call(
            "bitbucket_update_pull_request", **pr_args(title="New title")
        )

        (request,) = fake_bitbucket.requests_to("PUT", PR)
        assert request.body == {
            "version": 4,
            "title": "New title",
            "description": "Implements add login",
            "reviewers": [{"user": {"name": "bob"}}],
        }
        assert result["title"] == "New title"

    async def test_replaces_reviewers_target_and_draft(self, bb, fake_bitbucket):
        fake_bitbucket.add("GET", PR, pull_request(7, version=4))
        fake_bitbucket.add("PUT", PR, pull_request(7, version=5))

        await bb.call(
            "bitbucket_update_pull_request",
            **pr_args(
                reviewers=["carol"], target_branch="release/1.0", draft=True, version=4
            ),
        )

        (request,) = fake_bitbucket.requests_to("PUT", PR)
        assert request.body["version"] == 4
        assert request.body["reviewers"] == [{"user": {"name": "carol"}}]
        assert request.body["toRef"] == {
            "id": "refs/heads/release/1.0",
            "repository": {"slug": "api", "project": {"key": "PLAT"}},
        }
        assert request.body["draft"] is True


class TestMerge:
    async def test_merges_with_strategy_and_message(self, bb, fake_bitbucket):
        fake_bitbucket.add("GET", PR, pull_request(7, version=2))
        fake_bitbucket.add("POST", f"{PR}/merge", pull_request(7, state="MERGED"))

        result = await bb.call(
            "bitbucket_merge_pull_request",
            **pr_args(strategy="squash", message="Add login (#7)"),
        )

        (request,) = fake_bitbucket.requests_to("POST", f"{PR}/merge")
        assert request.query == {"version": "2"}
        assert request.body == {"strategyId": "squash", "message": "Add login (#7)"}
        assert result["state"] == "MERGED"

    async def test_refused_merge_explains_vetoes(self, bb, fake_bitbucket):
        fake_bitbucket.add(
            "POST",
            f"{PR}/merge",
            {
                "errors": [
                    {
                        "message": "Merging the pull request has been vetoed.",
                        "exceptionName": "com.atlassian.bitbucket.pull."
                        "PullRequestMergeVetoedException",
                        "conflicted": False,
                        "vetoes": [
                            {
                                "summaryMessage": "Not all required builds are "
                                "successful yet",
                                "detailedMessage": "You need 1 successful build",
                            },
                            {"summaryMessage": "Open tasks", "detailedMessage": ""},
                        ],
                    }
                ]
            },
            status=409,
        )

        message = await bb.call_error(
            "bitbucket_merge_pull_request", **pr_args(version=2)
        )

        assert "vetoed" in message
        assert "You need 1 successful build" in message
        assert "Open tasks" in message


class TestDeclineAndReopen:
    async def test_decline_with_comment(self, bb, fake_bitbucket):
        fake_bitbucket.add("POST", f"{PR}/decline", pull_request(7, state="DECLINED"))

        result = await bb.call(
            "bitbucket_decline_pull_request",
            **pr_args(version=3, comment="Superseded by #9"),
        )

        (request,) = fake_bitbucket.requests_to("POST", f"{PR}/decline")
        assert request.body == {"comment": "Superseded by #9"}
        assert result["state"] == "DECLINED"


class TestCreateBranch:
    async def test_creates_branch_from_start_point(self, bb, fake_bitbucket):
        fake_bitbucket.add(
            "POST", f"{REPO}/branches", branch_ref("fix/bug"), status=200
        )

        result = await bb.call(
            "bitbucket_create_branch", **repo_args(name="fix/bug", start_point="main")
        )

        (request,) = fake_bitbucket.requests_to("POST", f"{REPO}/branches")
        assert request.body == {"name": "fix/bug", "startPoint": "main"}
        assert result["name"] == "fix/bug"


MANAGE_TOOLS = [
    ("bitbucket_create_pull_request", repo_args(title="t", source_branch="b")),
    ("bitbucket_update_pull_request", pr_args(title="t")),
    ("bitbucket_merge_pull_request", pr_args()),
    ("bitbucket_decline_pull_request", pr_args()),
    ("bitbucket_reopen_pull_request", pr_args()),
    ("bitbucket_create_branch", repo_args(name="b", start_point="main")),
]


async def test_read_only_mode_blocks_manage_tools(
    bitbucket_mcp_factory, bitbucket_config, fake_bitbucket
):
    async with bitbucket_mcp_factory(bitbucket_config, read_only=True) as client:
        names = await client.tool_names()
        for tool, arguments in MANAGE_TOOLS:
            assert tool not in names
            assert "Unknown tool" in await client.call_error(tool, **arguments)
    assert fake_bitbucket.requests == []


async def test_respects_projects_filter(
    bitbucket_mcp_factory, bitbucket_config, fake_bitbucket
):
    config = dataclasses.replace(bitbucket_config, projects_filter="OPS")
    async with bitbucket_mcp_factory(config) as client:
        for tool, arguments in MANAGE_TOOLS:
            message = await client.call_error(tool, **arguments)
            assert "BITBUCKET_PROJECTS_FILTER" in message, tool
    assert fake_bitbucket.requests == []
