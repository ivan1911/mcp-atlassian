"""Commit diffs rendered as unified text."""

from .client import BitbucketClient, quote_segment


class DiffMixin(BitbucketClient):
    """Commit diffs rendered as unified text."""

    def get_commit_diff(
        self,
        project_key: str,
        repo_slug: str,
        commit_id: str,
        *,
        path: str | None = None,
        context_lines: int | None = None,
        ignore_whitespace: bool = False,
    ) -> str:
        """Unified diff of a commit against its first parent.

        Args:
            project_key: Project key.
            repo_slug: Repository slug.
            commit_id: Commit hash.
            path: Only this file.
            context_lines: Lines of context around changes.
            ignore_whitespace: Ignore whitespace-only changes.

        Returns:
            A header line (with a truncation notice when Bitbucket cut the
            diff) followed by unified diff text.
        """
        repo = self._repo_path(project_key, repo_slug)
        commit_id = commit_id.strip()
        return self._render_diff(
            f"{repo}/commits/{quote_segment(commit_id)}/diff",
            f"Diff of commit {commit_id}",
            path=path,
            context_lines=context_lines,
            ignore_whitespace=ignore_whitespace,
        )
