"""Reading code: files, branches, tags and commits, driven through MCP."""

from __future__ import annotations

import dataclasses

import pytest

from .fake_bitbucket import (
    branch_ref,
    browse_directory,
    change,
    commit,
    page,
    tag_ref,
)

pytestmark = pytest.mark.anyio

REPO = "/rest/api/latest/projects/PLAT/repos/api"
SHA = "0123456789abcdef0123456789abcdef01234567"
PARENT = "fedcba9876543210fedcba9876543210fedcba98"


def repo_args(**extra):
    return {"project_key": "PLAT", "repo_slug": "api", **extra}


class TestListFiles:
    async def test_lists_a_directory(self, bb, fake_bitbucket):
        fake_bitbucket.add(
            "GET",
            f"{REPO}/browse/src",
            browse_directory(
                "src", [("app.py", "FILE", 120), ("lib", "DIRECTORY", None)]
            ),
        )

        result = await bb.call("bitbucket_list_files", **repo_args(path="src"))

        assert result["values"] == [
            {"path": "src/app.py", "type": "file", "size": 120},
            {"path": "src/lib", "type": "directory"},
        ]

    async def test_lists_repository_root_at_a_ref(self, bb, fake_bitbucket):
        fake_bitbucket.add(
            "GET", f"{REPO}/browse", browse_directory("", [("README.md", "FILE", 9)])
        )

        result = await bb.call("bitbucket_list_files", **repo_args(at="develop"))

        assert result["values"] == [{"path": "README.md", "type": "file", "size": 9}]
        (request,) = fake_bitbucket.requests_to("GET", f"{REPO}/browse")
        assert request.query["at"] == "develop"

    async def test_lists_all_files_recursively(self, bb, fake_bitbucket):
        # /files returns paths relative to the requested directory.
        fake_bitbucket.add("GET", f"{REPO}/files/src", page(["app.py", "lib/util.py"]))

        result = await bb.call(
            "bitbucket_list_files", **repo_args(path="src", recursive=True)
        )

        assert result["values"] == [
            {"path": "src/app.py", "type": "file"},
            {"path": "src/lib/util.py", "type": "file"},
        ]


class TestGetFileContent:
    async def test_returns_lines_with_total_and_no_truncation(
        self, bb, fake_bitbucket
    ):
        fake_bitbucket.add("GET", f"{REPO}/raw/src/app.py", "import os\nprint(1)\n")

        result = await bb.call(
            "bitbucket_get_file_content", **repo_args(path="src/app.py")
        )

        assert result["content"] == "import os\nprint(1)\n"
        assert result["total_lines"] == 2
        assert result["start_line"] == 1
        assert result["end_line"] == 2
        assert result["truncated"] is False

    async def test_reads_a_line_range_and_reports_truncation(
        self, bb, fake_bitbucket
    ):
        body = "".join(f"line {n}\n" for n in range(1, 11))
        fake_bitbucket.add("GET", f"{REPO}/raw/big.txt", body)

        result = await bb.call(
            "bitbucket_get_file_content",
            **repo_args(path="big.txt", start_line=3, limit=4),
        )

        assert result["content"] == "line 3\nline 4\nline 5\nline 6\n"
        assert (result["start_line"], result["end_line"]) == (3, 6)
        assert result["total_lines"] == 10
        assert result["truncated"] is True

    async def test_default_limit_is_1000_lines(self, bb, fake_bitbucket):
        body = "".join(f"{n}\n" for n in range(1, 1501))
        fake_bitbucket.add("GET", f"{REPO}/raw/huge.txt", body)

        result = await bb.call("bitbucket_get_file_content", **repo_args(path="huge.txt"))

        assert result["end_line"] == 1000
        assert result["total_lines"] == 1500
        assert result["truncated"] is True

    async def test_binary_file_returns_metadata_only(self, bb, fake_bitbucket):
        fake_bitbucket.add("GET", f"{REPO}/raw/logo.png", b"\x89PNG\r\n\x1a\n\x00\x00")

        result = await bb.call("bitbucket_get_file_content", **repo_args(path="logo.png"))

        assert result["binary"] is True
        assert result["size_bytes"] == 10
        assert "content" not in result

    async def test_reads_at_a_ref(self, bb, fake_bitbucket):
        fake_bitbucket.add("GET", f"{REPO}/raw/a.txt", "x\n")

        await bb.call("bitbucket_get_file_content", **repo_args(path="a.txt", at=SHA))

        (request,) = fake_bitbucket.requests_to("GET", f"{REPO}/raw/a.txt")
        assert request.query["at"] == SHA


class TestBranchesAndTags:
    async def test_lists_branches_with_default_marked(self, bb, fake_bitbucket):
        fake_bitbucket.add(
            "GET",
            f"{REPO}/branches",
            page([branch_ref("main", default=True), branch_ref("feature/x")]),
        )

        result = await bb.call("bitbucket_list_branches", **repo_args(filter="feat"))

        assert [(b["name"], b["is_default"]) for b in result["values"]] == [
            ("main", True),
            ("feature/x", False),
        ]
        assert result["values"][1]["id"] == "refs/heads/feature/x"
        (request,) = fake_bitbucket.requests_to("GET", f"{REPO}/branches")
        assert request.query["filterText"] == "feat"

    async def test_lists_tags(self, bb, fake_bitbucket):
        fake_bitbucket.add("GET", f"{REPO}/tags", page([tag_ref("v1.2.0")]))

        result = await bb.call("bitbucket_list_tags", **repo_args())

        (tag,) = result["values"]
        assert tag["name"] == "v1.2.0"
        assert tag["latest_commit"] == "b" * 40


class TestCommits:
    async def test_lists_commits_on_a_ref_for_a_path(self, bb, fake_bitbucket):
        fake_bitbucket.add(
            "GET",
            f"{REPO}/commits",
            page([commit(SHA, "Add login\n\nLonger body", parents=(PARENT,))]),
        )

        result = await bb.call(
            "bitbucket_list_commits",
            **repo_args(at="develop", path="src/app.py", since="v1.0"),
        )

        (c,) = result["values"]
        assert c["id"] == SHA
        assert c["message"] == "Add login\n\nLonger body"
        assert c["author"] == {"name": "Alice", "email": "alice@example.com"}
        assert c["parents"] == [PARENT]
        assert c["author_timestamp"].startswith("2023-11-14T")
        (request,) = fake_bitbucket.requests_to("GET", f"{REPO}/commits")
        assert request.query["until"] == "develop"
        assert request.query["path"] == "src/app.py"
        assert request.query["since"] == "v1.0"

    async def test_get_commit_includes_changed_files(self, bb, fake_bitbucket):
        fake_bitbucket.add("GET", f"{REPO}/commits/{SHA}", commit(SHA))
        fake_bitbucket.add(
            "GET",
            f"{REPO}/commits/{SHA}/changes",
            page(
                [
                    change("src/app.py"),
                    change("src/new.py", "ADD"),
                    change("docs/b.md", "MOVE", src_path="docs/a.md"),
                ]
            ),
        )

        result = await bb.call("bitbucket_get_commit", **repo_args(commit_id=SHA))

        assert result["id"] == SHA
        assert result["changes"] == [
            {"path": "src/app.py", "type": "MODIFY"},
            {"path": "src/new.py", "type": "ADD"},
            {"path": "docs/b.md", "type": "MOVE", "src_path": "docs/a.md"},
        ]


async def test_code_tools_respect_projects_filter(
    bitbucket_mcp_factory, bitbucket_config, fake_bitbucket
):
    config = dataclasses.replace(bitbucket_config, projects_filter="OPS")
    async with bitbucket_mcp_factory(config) as client:
        for tool, extra in [
            ("bitbucket_list_files", {}),
            ("bitbucket_get_file_content", {"path": "a"}),
            ("bitbucket_list_branches", {}),
            ("bitbucket_list_tags", {}),
            ("bitbucket_list_commits", {}),
            ("bitbucket_get_commit", {"commit_id": SHA}),
        ]:
            message = await client.call_error(tool, **repo_args(**extra))
            assert "BITBUCKET_PROJECTS_FILTER" in message, tool
    assert fake_bitbucket.requests == []
