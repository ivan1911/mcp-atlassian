"""Bitbucket wiring into the main server: lifespan, listing, DI, toolsets."""

from __future__ import annotations

import os
from unittest.mock import MagicMock, patch

import pytest
from starlette.requests import Request

from mcp_atlassian.bitbucket import BitbucketConfig, BitbucketFetcher
from mcp_atlassian.servers.context import MainAppContext
from mcp_atlassian.servers.dependencies import get_bitbucket_fetcher
from mcp_atlassian.servers.main import main_lifespan, main_mcp
from mcp_atlassian.utils.toolsets import ALL_TOOLSETS, DEFAULT_TOOLSETS
from tests.utils.mocks import MockEnvironment

pytestmark = pytest.mark.anyio

BITBUCKET_ENV = {
    "BITBUCKET_URL": "https://bitbucket.company.com",
    "BITBUCKET_PERSONAL_TOKEN": "token",
}


def _config() -> BitbucketConfig:
    return BitbucketConfig(
        url="https://bitbucket.company.com",
        auth_type="pat",
        personal_token="token",  # noqa: S106
    )


class TestLifespan:
    async def test_loads_bitbucket_config_from_env(self):
        with MockEnvironment.clean_env(), patch.dict(os.environ, BITBUCKET_ENV):
            async with main_lifespan(MagicMock()) as context:
                app_context = context["app_lifespan_context"]

        config = app_context.full_bitbucket_config
        assert config is not None
        assert config.url == "https://bitbucket.company.com"
        assert config.personal_token == "token"  # noqa: S105
        assert app_context.full_jira_config is None

    async def test_no_bitbucket_config_without_env(self):
        with MockEnvironment.clean_env():
            async with main_lifespan(MagicMock()) as context:
                app_context = context["app_lifespan_context"]

        assert app_context.full_bitbucket_config is None


async def _listed_tools(app_context: MainAppContext) -> set[str]:
    request_context = MagicMock()
    request_context.request = None
    request_context.lifespan_context = {"app_lifespan_context": app_context}
    with patch.object(main_mcp, "_mcp_server") as mcp_server:
        mcp_server.request_context = request_context
        return {tool.name for tool in await main_mcp._list_tools_mcp()}


class TestListing:
    async def test_bitbucket_tools_listed_when_configured(self):
        names = await _listed_tools(MainAppContext(full_bitbucket_config=_config()))

        assert "bitbucket_list_projects" in names
        assert not any(n.startswith(("jira_", "confluence_")) for n in names)

    async def test_bitbucket_tools_hidden_when_not_configured(self):
        names = await _listed_tools(MainAppContext())

        assert not any(n.startswith("bitbucket_") for n in names)

    async def test_every_bitbucket_tool_has_a_known_bitbucket_toolset(self):
        tools = await main_mcp.list_tools()
        bitbucket_tools = [t for t in tools if "bitbucket" in t.tags]

        assert bitbucket_tools
        for tool in bitbucket_tools:
            toolset_tags = {t for t in tool.tags if t.startswith("toolset:")}
            assert len(toolset_tags) == 1, tool.name
            (tag,) = toolset_tags
            name = tag.removeprefix("toolset:")
            assert name.startswith("bitbucket_"), tool.name
            assert name in ALL_TOOLSETS, tool.name
            assert ("read" in tool.tags) != ("write" in tool.tags), tool.name

    def test_projects_toolset_is_default(self):
        assert "bitbucket_projects" in DEFAULT_TOOLSETS


def _ctx(app_context: MainAppContext | None) -> MagicMock:
    ctx = MagicMock()
    ctx.request_context.lifespan_context = (
        {"app_lifespan_context": app_context} if app_context else {}
    )
    return ctx


class TestGetBitbucketFetcher:
    @pytest.fixture(autouse=True)
    def _no_http_request(self):
        with patch(
            "mcp_atlassian.servers.dependencies.get_http_request",
            side_effect=RuntimeError("no request"),
        ):
            yield

    async def test_returns_fetcher_for_configured_instance(self):
        fetcher = await get_bitbucket_fetcher(
            _ctx(MainAppContext(full_bitbucket_config=_config()))
        )

        assert isinstance(fetcher, BitbucketFetcher)
        assert fetcher.config.url == "https://bitbucket.company.com"

    async def test_not_configured_is_an_error(self):
        with pytest.raises(ValueError, match="BITBUCKET_URL"):
            await get_bitbucket_fetcher(_ctx(MainAppContext()))


class TestGetBitbucketFetcherOverHttp:
    @pytest.fixture(autouse=True)
    def _http_request(self):
        with patch(
            "mcp_atlassian.servers.dependencies.get_http_request",
            return_value=MagicMock(spec=Request, state=MagicMock()),
        ):
            yield

    async def test_refuses_without_global_credential_fallback(self, monkeypatch):
        monkeypatch.delenv("ALLOW_GLOBAL_CRED_FALLBACK", raising=False)

        with pytest.raises(ValueError, match="ALLOW_GLOBAL_CRED_FALLBACK"):
            await get_bitbucket_fetcher(
                _ctx(MainAppContext(full_bitbucket_config=_config()))
            )

    async def test_allowed_with_global_credential_fallback(self, monkeypatch):
        monkeypatch.setenv("ALLOW_GLOBAL_CRED_FALLBACK", "true")

        fetcher = await get_bitbucket_fetcher(
            _ctx(MainAppContext(full_bitbucket_config=_config()))
        )

        assert isinstance(fetcher, BitbucketFetcher)
