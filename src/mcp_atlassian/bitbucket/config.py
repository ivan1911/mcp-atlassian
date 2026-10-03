"""Configuration module for the Bitbucket Data Center client."""

import os
from dataclasses import dataclass
from typing import Literal

from ..utils.env import get_custom_headers, is_env_ssl_verify
from ..utils.proxy import get_proxy_settings_from_env

DEFAULT_TIMEOUT = 75


@dataclass
class BitbucketConfig:
    """Bitbucket Data Center API configuration.

    Bitbucket Cloud is not supported (see ADR-0001); the only authentication
    method is a personal (HTTP access) token sent as a Bearer token.
    """

    url: str  # Base URL of the Bitbucket Data Center instance
    auth_type: Literal["pat"]
    personal_token: str | None = None  # HTTP access token
    ssl_verify: bool = True
    projects_filter: str | None = None  # Comma-separated project keys
    http_proxy: str | None = None
    https_proxy: str | None = None
    no_proxy: str | None = None
    socks_proxy: str | None = None
    proxy_wpad_enable: bool = False
    proxy_wpad_url: str | None = None
    custom_headers: dict[str, str] | None = None
    client_cert: str | None = None  # Client certificate file path (.pem)
    client_key: str | None = None  # Client private key file path (.pem)
    client_key_password: str | None = None
    timeout: int = DEFAULT_TIMEOUT

    @property
    def allowed_project_keys(self) -> set[str] | None:
        """Upper-cased project keys from the projects filter, or None if unset."""
        if not self.projects_filter:
            return None
        keys = {k.strip().upper() for k in self.projects_filter.split(",")}
        keys.discard("")
        return keys or None

    @classmethod
    def from_env(cls) -> "BitbucketConfig":
        """Create configuration from environment variables.

        Returns:
            BitbucketConfig with values from environment variables.

        Raises:
            ValueError: If BITBUCKET_URL or BITBUCKET_PERSONAL_TOKEN is missing.
        """
        url = (os.getenv("BITBUCKET_URL") or "").strip()
        if not url:
            raise ValueError(
                "Missing required BITBUCKET_URL environment variable. "
                "Set BITBUCKET_URL to your Bitbucket Data Center base URL, "
                "for example https://bitbucket.your-company.com"
            )
        personal_token = os.getenv("BITBUCKET_PERSONAL_TOKEN")
        if not personal_token:
            raise ValueError(
                "Bitbucket authentication requires BITBUCKET_PERSONAL_TOKEN "
                "(an HTTP access token). Basic auth and OAuth are not supported."
            )

        timeout = DEFAULT_TIMEOUT
        timeout_env = os.getenv("BITBUCKET_TIMEOUT", "")
        if timeout_env.isdigit():
            timeout = int(timeout_env)

        proxy_settings = get_proxy_settings_from_env("BITBUCKET")

        return cls(
            url=url.rstrip("/"),
            auth_type="pat",
            personal_token=personal_token,
            ssl_verify=is_env_ssl_verify("BITBUCKET_SSL_VERIFY"),
            projects_filter=os.getenv("BITBUCKET_PROJECTS_FILTER") or None,
            http_proxy=proxy_settings["http_proxy"],
            https_proxy=proxy_settings["https_proxy"],
            no_proxy=proxy_settings["no_proxy"],
            socks_proxy=proxy_settings["socks_proxy"],
            proxy_wpad_enable=bool(proxy_settings["proxy_wpad_enable"]),
            proxy_wpad_url=proxy_settings["proxy_wpad_url"],
            custom_headers=get_custom_headers("BITBUCKET_CUSTOM_HEADERS"),
            client_cert=os.getenv("BITBUCKET_CLIENT_CERT"),
            client_key=os.getenv("BITBUCKET_CLIENT_KEY"),
            client_key_password=os.getenv("BITBUCKET_CLIENT_KEY_PASSWORD"),
            timeout=timeout,
        )

    def is_auth_configured(self) -> bool:
        """Return True when a personal token is available."""
        return bool(self.url and self.personal_token)
