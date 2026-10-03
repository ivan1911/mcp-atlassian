"""Package version lookup independent of the distribution name."""

from types import SimpleNamespace
from unittest.mock import patch

from mcp_atlassian.utils.package import get_package_version


def _versions(known: dict[str, str]):
    from importlib.metadata import PackageNotFoundError

    def version(name: str) -> str:
        if name in known:
            return known[name]
        raise PackageNotFoundError(name)

    return version


def test_uses_the_distribution_that_provides_the_module():
    with (
        patch(
            "mcp_atlassian.utils.package.packages_distributions",
            return_value={"mcp_atlassian": ["olddevs-mcp-atlassian"]},
        ),
        patch(
            "mcp_atlassian.utils.package.version",
            side_effect=_versions({"olddevs-mcp-atlassian": "0.1.0"}),
        ),
    ):
        assert get_package_version() == "0.1.0"


def test_finds_editable_install_through_its_console_script():
    entry_point = SimpleNamespace(
        value="mcp_atlassian:main", dist=SimpleNamespace(name="olddevs-mcp-atlassian")
    )
    with (
        patch("mcp_atlassian.utils.package.packages_distributions", return_value={}),
        patch("mcp_atlassian.utils.package.entry_points", return_value=[entry_point]),
        patch(
            "mcp_atlassian.utils.package.version",
            side_effect=_versions({"olddevs-mcp-atlassian": "0.1.0"}),
        ),
    ):
        assert get_package_version() == "0.1.0"


def test_falls_back_to_the_upstream_distribution_name():
    with (
        patch("mcp_atlassian.utils.package.packages_distributions", return_value={}),
        patch("mcp_atlassian.utils.package.entry_points", return_value=[]),
        patch(
            "mcp_atlassian.utils.package.version",
            side_effect=_versions({"mcp-atlassian": "0.23.1"}),
        ),
    ):
        assert get_package_version() == "0.23.1"


def test_not_installed_gives_zero_version():
    with (
        patch("mcp_atlassian.utils.package.packages_distributions", return_value={}),
        patch("mcp_atlassian.utils.package.entry_points", return_value=[]),
        patch("mcp_atlassian.utils.package.version", side_effect=_versions({})),
    ):
        assert get_package_version() == "0.0.0"
