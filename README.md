# MCP Atlassian

![PyPI Version](https://img.shields.io/pypi/v/olddevs-mcp-atlassian)
![PyPI - Downloads](https://img.shields.io/pypi/dm/olddevs-mcp-atlassian)
[![Run Tests](https://github.com/ivan1911/olddevs-mcp-atlassian/actions/workflows/tests.yml/badge.svg)](https://github.com/ivan1911/olddevs-mcp-atlassian/actions/workflows/tests.yml)
![License](https://img.shields.io/github/license/ivan1911/olddevs-mcp-atlassian)
[![Docs](https://img.shields.io/badge/docs-mintlify-blue)](https://mcp-atlassian.soomiles.com)

> **This is a fork** of [sooperset/mcp-atlassian](https://github.com/sooperset/mcp-atlassian) that adds Bitbucket Data Center support. It is published on PyPI as [`olddevs-mcp-atlassian`](https://pypi.org/project/olddevs-mcp-atlassian/); the command is `olddevs-mcp-atlassian` (`mcp-atlassian` also works). The linked documentation site describes the upstream project; Bitbucket is covered in this README.

Model Context Protocol (MCP) server for Atlassian products: Jira, Confluence and Bitbucket. Jira and Confluence are supported on Cloud and Server/Data Center; Bitbucket is supported on Data Center (self-hosted) only.

https://github.com/user-attachments/assets/35303504-14c6-4ae4-913b-7c25ea511c3e

<details>
<summary>Confluence Demo</summary>

https://github.com/user-attachments/assets/7fe9c488-ad0c-4876-9b54-120b666bb785

</details>

## Quick Start

### 1. Get Your API Token

Go to https://id.atlassian.com/manage-profile/security/api-tokens and create a token.

> For Server/Data Center, use a Personal Access Token instead. See [Authentication](https://mcp-atlassian.soomiles.com/docs/authentication).

> For Bitbucket Data Center, create an HTTP access token in Bitbucket under **Profile → Manage account → HTTP access tokens** (read permission to browse and review, write permission to comment, create or merge pull requests).

### 2. Configure Your IDE

Add to your Claude Desktop or Cursor MCP configuration:

```json
{
  "mcpServers": {
    "mcp-atlassian": {
      "command": "uvx",
      "args": ["olddevs-mcp-atlassian"],
      "env": {
        "JIRA_URL": "https://your-company.atlassian.net",
        "JIRA_USERNAME": "your.email@company.com",
        "JIRA_API_TOKEN": "your_api_token",
        "CONFLUENCE_URL": "https://your-company.atlassian.net/wiki",
        "CONFLUENCE_USERNAME": "your.email@company.com",
        "CONFLUENCE_API_TOKEN": "your_api_token",
        "BITBUCKET_URL": "https://bitbucket.your-company.com",
        "BITBUCKET_PERSONAL_TOKEN": "your_bitbucket_http_access_token"
      }
    }
  }
}
```

> **Server/Data Center users**: Use `JIRA_PERSONAL_TOKEN` instead of `JIRA_USERNAME` + `JIRA_API_TOKEN`. See [Authentication](https://mcp-atlassian.soomiles.com/docs/authentication) for details.

> **Bitbucket Data Center** is optional: drop the `BITBUCKET_*` lines if you don't use it, or keep only them for a Bitbucket-only setup. See [Bitbucket Data Center](#bitbucket-data-center) below.

#### Autohand Code

Use the same `uvx` server with your Atlassian credentials:

```bash
autohand mcp add mcp-atlassian env \
  JIRA_URL=https://your-company.atlassian.net \
  JIRA_USERNAME=your.email@company.com \
  JIRA_API_TOKEN=your_api_token \
  CONFLUENCE_URL=https://your-company.atlassian.net/wiki \
  CONFLUENCE_USERNAME=your.email@company.com \
  CONFLUENCE_API_TOKEN=your_api_token \
  BITBUCKET_URL=https://bitbucket.your-company.com \
  BITBUCKET_PERSONAL_TOKEN=your_bitbucket_http_access_token \
  uvx olddevs-mcp-atlassian
```

Add `--scope project` after `add` to keep the configuration in the current
project. See [Autohand Code](https://github.com/autohandai/code-cli/) for current
installation and CLI details.

### 3. Start Using

Ask your AI assistant to:
- **"Find issues assigned to me in PROJ project"**
- **"Search Confluence for onboarding docs"**
- **"Create a bug ticket for the login issue"**
- **"Update the status of PROJ-123 to Done"**
- **"Review pull request #42 in PLAT/api and leave inline comments"**
- **"Which pull requests are waiting for my review?"**

## Bitbucket Data Center

Bitbucket support targets self-hosted **Bitbucket Data Center** (v8.0+, tested on 10.x). Bitbucket Cloud is not supported.

```json
{
  "mcpServers": {
    "mcp-atlassian": {
      "command": "uvx",
      "args": ["olddevs-mcp-atlassian"],
      "env": {
        "BITBUCKET_URL": "https://bitbucket.your-company.com",
        "BITBUCKET_PERSONAL_TOKEN": "your_http_access_token",
        "BITBUCKET_PROJECTS_FILTER": "PLAT,OPS"
      }
    }
  }
}
```

Bitbucket can be configured on its own or next to Jira and Confluence in the same `env` block.

What the assistant can do:

- **Read code**: browse projects and repositories, list files, read files at any branch, tag or commit, list branches, tags and commits, and read commit diffs.
- **Review pull requests**:
  - Find them, including your own review inbox.
  - Read the description, diff, changed files and full activity.
  - Leave general, inline and reply comments, raise and resolve tasks, set your reviewer status.
  - Collect pending comments and publish them as one review.
- **Manage pull requests**: create (default target branch and default reviewers), update, merge, decline and reopen pull requests, and create branches.

Safety and limits:

- **Authentication**: only an HTTP access token from the environment. No Basic auth, OAuth or per-request headers. Over HTTP transports the token is the operator's, so `ALLOW_GLOBAL_CRED_FALLBACK=true` is required (single-user deployments only).
- **`BITBUCKET_PROJECTS_FILTER`** limits every Bitbucket tool to the listed project keys: other projects are hidden from listings and refused on direct access.
- **`READ_ONLY_MODE=true`** disables all Bitbucket write tools.
- **Code search** (`bitbucket_search`) uses Bitbucket's unofficial search endpoint. It only covers default branches, and it is not part of `TOOLSETS=default`; enable it with, for example, `TOOLSETS=default,bitbucket_search`.
- **Deleting** pull requests and branches (`bitbucket_destructive`) is never enabled implicitly, not even by `TOOLSETS=all`. Name it explicitly: `TOOLSETS=all,bitbucket_destructive`.

All variables are listed in [.env.example](https://github.com/ivan1911/olddevs-mcp-atlassian/blob/main/.env.example).

## Documentation

Full documentation is available at **[mcp-atlassian.soomiles.com](https://mcp-atlassian.soomiles.com)**.

Documentation is also available in [llms.txt format](https://llmstxt.org/), which LLMs can consume easily:
- [`llms.txt`](https://mcp-atlassian.soomiles.com/llms.txt) — documentation sitemap
- [`llms-full.txt`](https://mcp-atlassian.soomiles.com/llms-full.txt) — complete documentation

| Topic | Description |
|-------|-------------|
| [Installation](https://mcp-atlassian.soomiles.com/docs/installation) | uvx, Docker, pip, from source |
| [Authentication](https://mcp-atlassian.soomiles.com/docs/authentication) | API tokens, PAT, OAuth 2.0 |
| [Configuration](https://mcp-atlassian.soomiles.com/docs/configuration) | IDE setup, environment variables |
| [HTTP Transport](https://mcp-atlassian.soomiles.com/docs/http-transport) | SSE, streamable-http, multi-user |
| [Tools Reference](https://mcp-atlassian.soomiles.com/docs/tools-reference) | All Jira, Confluence & Bitbucket tools |
| [Troubleshooting](https://mcp-atlassian.soomiles.com/docs/troubleshooting) | Common issues & debugging |

## Compatibility

| Product | Deployment | Support |
|---------|------------|---------|
| Confluence | Cloud | Fully supported |
| Confluence | Server/Data Center | Supported (v6.0+) |
| Jira | Cloud | Fully supported |
| Jira | Server/Data Center | Supported (v8.14+) |
| Bitbucket | Data Center | Supported (v8.0+, tested on 10.x) |
| Bitbucket | Cloud | Not supported |

## Key Tools

| Jira | Confluence | Bitbucket |
|------|------------|-----------|
| `jira_search` - Search with JQL | `confluence_search` - Search with CQL | `bitbucket_get_my_pull_requests` - My review inbox |
| `jira_get_issue` - Get issue details | `confluence_get_page` - Get page content | `bitbucket_get_pull_request_diff` - Pull request diff |
| `jira_create_issue` - Create issues | `confluence_create_page` - Create pages | `bitbucket_add_pull_request_comment` - Inline comments |
| `jira_update_issue` - Update issues | `confluence_update_page` - Update pages | `bitbucket_get_file_content` - Read code |
| `jira_transition_issue` - Change status | `confluence_add_comment` - Add comments | `bitbucket_create_pull_request` - Open pull requests |

**128 tools total** — See [Tools Reference](https://mcp-atlassian.soomiles.com/docs/tools-reference) for the complete list.

## Security

Never share API tokens. Keep `.env` files secure. See [SECURITY.md](https://github.com/ivan1911/olddevs-mcp-atlassian/blob/main/SECURITY.md).

## Contributing

See [CONTRIBUTING.md](https://github.com/ivan1911/olddevs-mcp-atlassian/blob/main/CONTRIBUTING.md) for development setup.

## License

MIT - See [LICENSE](https://github.com/ivan1911/olddevs-mcp-atlassian/blob/main/LICENSE). Not an official Atlassian product.
