# The fork is published as olddevs-mcp-atlassian; the import package stays mcp_atlassian

This fork (Bitbucket Data Center support) is published on PyPI as `olddevs-mcp-atlassian`, because `mcp-atlassian` belongs to the upstream project. Only the distribution name changes: the import package stays `mcp_atlassian`, and both `olddevs-mcp-atlassian` and `mcp-atlassian` console scripts are installed. Renaming the import package would touch nearly every file and turn each merge from upstream into a conflict (see ADR-0002); keeping it means the fork cannot be installed side by side with upstream in one environment, which `uvx` isolation makes a non-issue in practice.

## Consequences

- Code must not hardcode the distribution name: the version is looked up from the distribution that provides `mcp_atlassian` (`utils/package.py`).
- Versions are the fork's own, from git tags starting at `v0.1.0`; untagged builds are `X.Y.Z.devN` (no local `+hash`, which PyPI rejects).
- Publishing uses PyPI Trusted Publishing from `.github/workflows/publish.yml`; no API tokens are stored.
