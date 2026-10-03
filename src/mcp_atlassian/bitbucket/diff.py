"""Render Bitbucket's JSON diffs as unified diff text.

Bitbucket's diff endpoints are not paged and enforce a server-side line cap;
the JSON form carries ``truncated`` flags that the plain-text form does not, so
diffs are fetched as JSON and rendered here.
"""

from typing import Any

from .client import BitbucketClient, file_path, segment

_SEGMENT_PREFIX = {"ADDED": "+", "REMOVED": "-", "CONTEXT": " "}

TRUNCATION_NOTICE = (
    "# NOTE: Bitbucket truncated this diff at its server-side size limit. "
    "Request one file at a time with `path` to see the rest."
)


def _path(side: Any) -> str | None:
    if isinstance(side, dict):
        value = side.get("toString")
        return str(value) if value else None
    return None


def _is_truncated(diff_json: dict[str, Any]) -> bool:
    if diff_json.get("truncated"):
        return True
    for file_diff in diff_json.get("diffs") or []:
        if file_diff.get("truncated"):
            return True
        for hunk in file_diff.get("hunks") or []:
            if hunk.get("truncated"):
                return True
    return False


def render_unified_diff(diff_json: dict[str, Any]) -> tuple[str, int, bool]:
    """Render a Bitbucket JSON diff as unified diff text.

    Args:
        diff_json: Response of a Bitbucket ``.../diff`` endpoint.

    Returns:
        ``(text, file_count, truncated)``.
    """
    out: list[str] = []
    files = diff_json.get("diffs") or []
    for file_diff in files:
        src = _path(file_diff.get("source"))
        dst = _path(file_diff.get("destination"))
        a_name = src or dst or ""
        b_name = dst or src or ""
        out.append(f"diff --git a/{a_name} b/{b_name}")
        if file_diff.get("binary"):
            out.append(f"Binary files a/{a_name} and b/{b_name} differ")
            continue
        out.append(f"--- a/{src}" if src else "--- /dev/null")
        out.append(f"+++ b/{dst}" if dst else "+++ /dev/null")
        for hunk in file_diff.get("hunks") or []:
            out.append(
                f"@@ -{hunk.get('sourceLine', 0)},{hunk.get('sourceSpan', 0)} "
                f"+{hunk.get('destinationLine', 0)},"
                f"{hunk.get('destinationSpan', 0)} @@"
            )
            for seg in hunk.get("segments") or []:
                prefix = _SEGMENT_PREFIX.get(str(seg.get("type")), " ")
                for line in seg.get("lines") or []:
                    out.append(f"{prefix}{line.get('line', '')}")
    text = "\n".join(out) + ("\n" if out else "")
    return text, len(files), _is_truncated(diff_json)


def diff_params(context_lines: int | None, ignore_whitespace: bool) -> dict[str, Any]:
    """Query parameters shared by Bitbucket diff endpoints."""
    return {
        "contextLines": context_lines,
        "whitespace": "ignore-all" if ignore_whitespace else None,
    }


class DiffMixin(BitbucketClient):
    """Commit diffs rendered as unified text."""

    def _render_diff(
        self,
        url_path: str,
        title: str,
        *,
        path: str | None,
        context_lines: int | None,
        ignore_whitespace: bool,
    ) -> str:
        suffix = f"/{file_path(path)}" if path and path.strip("/") else ""
        data = self._get_json(
            f"{url_path}{suffix}", diff_params(context_lines, ignore_whitespace)
        )
        text, count, truncated = render_unified_diff(data or {})
        noun = "file" if count == 1 else "files"
        header = [f"# {title} ({count} {noun})"]
        if truncated:
            header.append(TRUNCATION_NOTICE)
        return "\n".join(header) + "\n" + text

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
            f"{repo}/commits/{segment(commit_id)}/diff",
            f"Diff of commit {commit_id}",
            path=path,
            context_lines=context_lines,
            ignore_whitespace=ignore_whitespace,
        )
