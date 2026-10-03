"""Render Bitbucket's JSON diffs as unified diff text.

Bitbucket's diff endpoints are not paged and enforce a server-side line cap;
the JSON form carries ``truncated`` flags that the plain-text form does not, so
diffs are fetched as JSON and rendered here.
"""

from typing import Any

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
