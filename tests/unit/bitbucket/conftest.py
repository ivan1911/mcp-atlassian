"""Fixtures for Bitbucket tests driven through MCP tool calls.

The primary seam: an in-memory FastMCP client calls Bitbucket tools on the main
server; underneath runs a real BitbucketFetcher whose HTTP session talks to
``FakeBitbucket`` instead of the network.
"""

from __future__ import annotations

import json
from collections.abc import AsyncGenerator, AsyncIterator, Callable
from contextlib import asynccontextmanager
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest
from fastmcp import Client, FastMCP
from fastmcp.client import FastMCPTransport

from mcp_atlassian.bitbucket import BitbucketConfig, BitbucketFetcher
from mcp_atlassian.servers.bitbucket import bitbucket_mcp
from mcp_atlassian.servers.context import MainAppContext
from mcp_atlassian.servers.main import AtlassianMCP

from .fake_bitbucket import FakeBitbucket

BASE_URL = "https://bitbucket.example.com"


@pytest.fixture
def bitbucket_config() -> BitbucketConfig:
    return BitbucketConfig(
        url=BASE_URL,
        auth_type="pat",
        personal_token="test-token",  # noqa: S106
    )


@pytest.fixture
def fake_bitbucket() -> FakeBitbucket:
    return FakeBitbucket()


def make_fetcher(config: BitbucketConfig, fake: FakeBitbucket) -> BitbucketFetcher:
    fetcher = BitbucketFetcher(config=config)
    fetcher.bitbucket._session.mount(config.url, fake)  # noqa: SLF001
    return fetcher


class BitbucketMCP:
    """Thin wrapper over the MCP client returning parsed tool output."""

    def __init__(self, client: Client) -> None:
        self.client = client

    async def call(self, tool: str, **arguments: Any) -> Any:
        result = await self.client.call_tool(tool, arguments)
        text = result.content[0].text  # type: ignore[union-attr]
        try:
            return json.loads(text)
        except ValueError:
            return text

    async def call_error(self, tool: str, **arguments: Any) -> str:
        result = await self.client.call_tool(tool, arguments, raise_on_error=False)
        assert result.is_error, f"expected {tool} to fail, got {result.content}"
        return result.content[0].text  # type: ignore[union-attr]

    async def tool_names(self) -> set[str]:
        return {t.name for t in await self.client.list_tools()}


@pytest.fixture
def bitbucket_mcp_factory(
    fake_bitbucket: FakeBitbucket,
) -> Callable[..., Any]:
    """Build an MCP client over a main server with Bitbucket mounted."""

    @asynccontextmanager
    async def factory(
        config: BitbucketConfig,
        *,
        read_only: bool = False,
        enabled_toolsets: set[str] | None = None,
    ) -> AsyncIterator[BitbucketMCP]:
        fetcher = make_fetcher(config, fake_bitbucket)

        @asynccontextmanager
        async def lifespan(app: FastMCP) -> AsyncGenerator[dict[str, Any], None]:
            yield {
                "app_lifespan_context": MainAppContext(
                    full_bitbucket_config=config,
                    read_only=read_only,
                    enabled_toolsets=enabled_toolsets,
                )
            }

        server = AtlassianMCP("TestBitbucket", lifespan=lifespan)
        server.mount(bitbucket_mcp, namespace="bitbucket")
        with patch(
            "mcp_atlassian.servers.bitbucket.get_bitbucket_fetcher",
            AsyncMock(return_value=fetcher),
        ):
            async with Client(transport=FastMCPTransport(server)) as client:
                yield BitbucketMCP(client)

    return factory


@pytest.fixture
async def bb(
    bitbucket_mcp_factory: Callable[..., Any], bitbucket_config: BitbucketConfig
) -> AsyncIterator[BitbucketMCP]:
    """MCP client for the default Bitbucket config."""
    async with bitbucket_mcp_factory(bitbucket_config) as client:
        yield client
