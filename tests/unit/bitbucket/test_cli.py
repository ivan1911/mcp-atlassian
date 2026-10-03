"""Bitbucket CLI flags map onto the BITBUCKET_* environment variables."""

from __future__ import annotations

import logging
import os
from unittest.mock import patch

from click.testing import CliRunner

from mcp_atlassian import main

BITBUCKET_ENV = (
    "BITBUCKET_URL",
    "BITBUCKET_PERSONAL_TOKEN",
    "BITBUCKET_SSL_VERIFY",
    "BITBUCKET_PROJECTS_FILTER",
)


def test_bitbucket_flags_set_environment(monkeypatch, tmp_path):
    for name in BITBUCKET_ENV:
        monkeypatch.delenv(name, raising=False)
    empty_env_file = tmp_path / ".env"
    empty_env_file.write_text("")

    with (
        patch("asyncio.run") as run,
        patch("mcp_atlassian.setup_signal_handlers"),
        # main() installs global logging handlers; keep them out of other tests.
        patch(
            "mcp_atlassian.setup_logging",
            return_value=logging.getLogger("test-cli"),
        ),
        patch.dict(os.environ, {}, clear=False),
    ):
        result = CliRunner().invoke(
            main,
            [
                "--env-file",
                str(empty_env_file),
                "--bitbucket-url",
                "https://bitbucket.company.com",
                "--bitbucket-personal-token",
                "token",
                "--no-bitbucket-ssl-verify",
                "--bitbucket-projects-filter",
                "PLAT,OPS",
            ],
        )
        env = {name: os.environ.get(name) for name in BITBUCKET_ENV}
        run.call_args[0][0].close()  # discard the never-awaited coroutine

    assert result.exit_code == 0, result.output
    assert env == {
        "BITBUCKET_URL": "https://bitbucket.company.com",
        "BITBUCKET_PERSONAL_TOKEN": "token",
        "BITBUCKET_SSL_VERIFY": "false",
        "BITBUCKET_PROJECTS_FILTER": "PLAT,OPS",
    }
