# Bitbucket support targets Data Center only

Unlike Jira and Confluence, which this server supports on both Cloud and Server/Data Center, Bitbucket support covers only Bitbucket Data Center (tested against 10.x, using `/rest/api/latest` endpoints available since 8.x). Bitbucket Cloud (`api.bitbucket.org/2.0`) is a completely different API — workspaces instead of projects, different pagination, no PR versioning, different auth — so supporting it means a second client, not a variant of the first. We have no Cloud user, so we chose not to build Cloud support or a provider abstraction in anticipation of it: an abstraction without a second implementation would be guessed, not designed.

## Consequences

- There is no `is_cloud` branch in the Bitbucket config or client; "Bitbucket" in code and docs means Data Center.
- Adding Cloud later means a separate client and likely separate tools, not toggling a flag.
