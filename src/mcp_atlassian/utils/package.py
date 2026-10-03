"""Installed package metadata, independent of the distribution name.

The import package is always ``mcp_atlassian``, but it may be installed from a
differently named distribution (e.g. a fork published under another name), so
the version is looked up through the distribution that provides the module.
"""

from importlib.metadata import (
    PackageNotFoundError,
    entry_points,
    packages_distributions,
    version,
)

_IMPORT_NAME = "mcp_atlassian"
_UPSTREAM_DISTRIBUTION = "mcp-atlassian"


def _candidate_distributions() -> list[str]:
    """Distributions that may provide ``mcp_atlassian``, most specific first.

    ``packages_distributions`` covers regular installs; editable installs are
    found through the console script that points into the package.
    """
    candidates = list(packages_distributions().get(_IMPORT_NAME, []))
    for entry_point in entry_points(group="console_scripts"):
        if entry_point.value.startswith(f"{_IMPORT_NAME}:") and entry_point.dist:
            candidates.append(entry_point.dist.name)
    candidates.append(_UPSTREAM_DISTRIBUTION)
    return list(dict.fromkeys(candidates))


def get_package_version() -> str:
    """Return the installed version of the distribution providing this package.

    Returns:
        The version string, or ``"0.0.0"`` when the package is not installed.
    """
    for distribution in _candidate_distributions():
        try:
            return version(distribution)
        except PackageNotFoundError:
            continue
    return "0.0.0"
