"""Commit diff as unified text, driven through MCP."""

from __future__ import annotations

import pytest

from .fake_bitbucket import diff, file_diff, hunk

pytestmark = pytest.mark.anyio

REPO = "/rest/api/latest/projects/PLAT/repos/api"
SHA = "0123456789abcdef0123456789abcdef01234567"
DIFF = f"{REPO}/commits/{SHA}/diff"


def args(**extra):
    return {"project_key": "PLAT", "repo_slug": "api", "commit_id": SHA, **extra}


async def test_renders_modified_added_and_deleted_files(bb, fake_bitbucket):
    fake_bitbucket.add(
        "GET",
        DIFF,
        diff(
            [
                file_diff(
                    "src/app.py",
                    "src/app.py",
                    [
                        hunk(
                            3,
                            3,
                            [
                                ("CONTEXT", ["import os"]),
                                ("REMOVED", ["print('a')"]),
                                ("ADDED", ["print('b')", "print('c')"]),
                            ],
                        )
                    ],
                ),
                file_diff(None, "NEW.md", [hunk(0, 1, [("ADDED", ["hello"])])]),
                file_diff("old.txt", None, [hunk(1, 0, [("REMOVED", ["bye"])])]),
            ]
        ),
    )

    text = await bb.call("bitbucket_get_commit_diff", **args())

    assert text == (
        f"# Diff of commit {SHA} (3 files)\n"
        "diff --git a/src/app.py b/src/app.py\n"
        "--- a/src/app.py\n"
        "+++ b/src/app.py\n"
        "@@ -3,2 +3,3 @@\n"
        " import os\n"
        "-print('a')\n"
        "+print('b')\n"
        "+print('c')\n"
        "diff --git a/NEW.md b/NEW.md\n"
        "--- /dev/null\n"
        "+++ b/NEW.md\n"
        "@@ -0,0 +1,1 @@\n"
        "+hello\n"
        "diff --git a/old.txt b/old.txt\n"
        "--- a/old.txt\n"
        "+++ /dev/null\n"
        "@@ -1,1 +0,0 @@\n"
        "-bye\n"
    )


async def test_single_file_context_and_whitespace(bb, fake_bitbucket):
    fake_bitbucket.add(
        "GET",
        f"{DIFF}/src/app.py",
        diff([file_diff("src/app.py", "src/app.py", [hunk(1, 1, [("ADDED", ["x"])])])]),
    )

    await bb.call(
        "bitbucket_get_commit_diff",
        **args(path="src/app.py", context_lines=3, ignore_whitespace=True),
    )

    (request,) = fake_bitbucket.requests_to("GET", f"{DIFF}/src/app.py")
    assert request.query == {"contextLines": "3", "whitespace": "ignore-all"}


async def test_truncated_diff_says_so(bb, fake_bitbucket):
    fake_bitbucket.add(
        "GET",
        DIFF,
        diff(
            [
                file_diff(
                    "big.sql",
                    "big.sql",
                    [hunk(1, 1, [("ADDED", ["a"])], truncated=True)],
                    truncated=True,
                )
            ],
            truncated=True,
        ),
    )

    text = await bb.call("bitbucket_get_commit_diff", **args())

    header = text.splitlines()[:2]
    assert "truncated" in header[1].lower()
    assert "path" in header[1]


async def test_binary_file_is_marked(bb, fake_bitbucket):
    fake_bitbucket.add(
        "GET", DIFF, diff([file_diff("logo.png", "logo.png", binary=True)])
    )

    text = await bb.call("bitbucket_get_commit_diff", **args())

    assert "Binary files a/logo.png and b/logo.png differ" in text


async def test_respects_projects_filter(
    bitbucket_mcp_factory, bitbucket_config, fake_bitbucket
):
    import dataclasses

    config = dataclasses.replace(bitbucket_config, projects_filter="OPS")
    async with bitbucket_mcp_factory(config) as client:
        message = await client.call_error("bitbucket_get_commit_diff", **args())

    assert "BITBUCKET_PROJECTS_FILTER" in message
    assert fake_bitbucket.requests == []
