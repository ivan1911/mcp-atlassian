"""BitbucketConfig.from_env and is_auth_configured."""

from __future__ import annotations

import pytest

from mcp_atlassian.bitbucket import BitbucketConfig

BITBUCKET_ENV = (
    "BITBUCKET_URL",
    "BITBUCKET_PERSONAL_TOKEN",
    "BITBUCKET_SSL_VERIFY",
    "BITBUCKET_PROJECTS_FILTER",
    "BITBUCKET_TIMEOUT",
    "BITBUCKET_CUSTOM_HEADERS",
    "BITBUCKET_HTTPS_PROXY",
    "BITBUCKET_CLIENT_CERT",
)


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch):
    for name in BITBUCKET_ENV:
        monkeypatch.delenv(name, raising=False)


def test_url_and_token_give_pat_config(monkeypatch):
    monkeypatch.setenv("BITBUCKET_URL", "https://bitbucket.example.com/")
    monkeypatch.setenv("BITBUCKET_PERSONAL_TOKEN", "secret")

    config = BitbucketConfig.from_env()

    assert config.url == "https://bitbucket.example.com"
    assert config.auth_type == "pat"
    assert config.personal_token == "secret"  # noqa: S105
    assert config.ssl_verify is True
    assert config.projects_filter is None
    assert config.is_auth_configured()


def test_missing_url_is_an_error(monkeypatch):
    monkeypatch.setenv("BITBUCKET_PERSONAL_TOKEN", "secret")

    with pytest.raises(ValueError, match="BITBUCKET_URL"):
        BitbucketConfig.from_env()


def test_missing_token_is_an_error(monkeypatch):
    monkeypatch.setenv("BITBUCKET_URL", "https://bitbucket.example.com")

    with pytest.raises(ValueError, match="BITBUCKET_PERSONAL_TOKEN"):
        BitbucketConfig.from_env()


def test_optional_settings_are_read(monkeypatch):
    monkeypatch.setenv("BITBUCKET_URL", "https://bitbucket.example.com")
    monkeypatch.setenv("BITBUCKET_PERSONAL_TOKEN", "secret")
    monkeypatch.setenv("BITBUCKET_SSL_VERIFY", "false")
    monkeypatch.setenv("BITBUCKET_PROJECTS_FILTER", "plat, OPS")
    monkeypatch.setenv("BITBUCKET_TIMEOUT", "30")
    monkeypatch.setenv("BITBUCKET_CUSTOM_HEADERS", "X-Team=core")
    monkeypatch.setenv("BITBUCKET_HTTPS_PROXY", "http://proxy:3128")
    monkeypatch.setenv("BITBUCKET_CLIENT_CERT", "/certs/client.pem")

    config = BitbucketConfig.from_env()

    assert config.ssl_verify is False
    assert config.projects_filter == "plat, OPS"
    assert config.timeout == 30
    assert config.custom_headers == {"X-Team": "core"}
    assert config.https_proxy == "http://proxy:3128"
    assert config.client_cert == "/certs/client.pem"


def test_empty_token_is_not_configured():
    config = BitbucketConfig(
        url="https://bitbucket.example.com", auth_type="pat", personal_token=""
    )

    assert not config.is_auth_configured()
