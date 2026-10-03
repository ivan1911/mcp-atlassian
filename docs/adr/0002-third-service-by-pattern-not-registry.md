# Bitbucket is wired in by copying the Jira/Confluence pattern, not via a service registry

The set of services `{jira, confluence}` is hardcoded across `servers/main.py`, `servers/context.py`, `servers/dependencies.py`, `utils/environment.py`, the CLI, toolsets and the docs generator. Adding Bitbucket as a third parallel branch in each of those places duplicates code that a service registry would remove. We chose duplication anyway because this is a fork that regularly merges from upstream `sooperset/mcp-atlassian`: a registry refactor would rewrite shared code that upstream keeps changing and turn every sync into a conflict, while additive per-service branches merge cleanly.

## Considered Options

- **Service registry refactor first**: cleaner, but touches most of the shared server plumbing and maximizes merge conflicts with upstream.
- **Additive third branch (chosen)**: more repetition, minimal diff in shared lines.

Revisit if upstream itself adopts a registry or if the fork stops tracking upstream.
