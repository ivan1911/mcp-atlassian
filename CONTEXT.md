# MCP Atlassian

An MCP server that lets LLM assistants read and act on Atlassian products: Jira, Confluence and Bitbucket.

## Language

### Bitbucket

**Bitbucket**:
Bitbucket Data Center (formerly Bitbucket Server), self-hosted. Bitbucket Cloud is out of scope.
_Avoid_: Stash, Bitbucket Server, Bitbucket Cloud

**Project**:
A named container of repositories, addressed by its short uppercase key (e.g. `PLAT`).
_Avoid_: Workspace, space

**Repository**:
A git repository inside a project, addressed by project key plus its slug.
_Avoid_: Repo name (the display name is not an identifier)

**Pull request**:
A request to merge a source branch into a target branch within Bitbucket, carrying a version that must match on every state change.
_Avoid_: Merge request, PR (in user-facing text)

**Reviewer status**:
A reviewer's verdict on a pull request: approved, needs work, or unapproved.
_Avoid_: Vote, approval (when meaning the status in general)

**Inline comment**:
A pull request comment anchored to a specific file and line of the diff.
_Avoid_: Line comment, file comment

**Pending comment**:
A pull request comment visible only to its author until the author publishes their review.
_Avoid_: Draft comment, unpublished comment

**Task**:
A pull request comment marked as blocking, which must be resolved before merge.
_Avoid_: Blocker comment, todo
