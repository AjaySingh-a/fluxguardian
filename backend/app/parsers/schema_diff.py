"""
schema_diff.py — Parse unified git diffs to detect breaking DB schema changes.

Only lines beginning with '+' (added lines) are inspected. Diff headers,
comments, and non-SQL files are silently skipped.
"""

import logging
import re
from typing import Literal

import sqlparse
from pydantic import BaseModel

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Model
# ---------------------------------------------------------------------------

ChangeType = Literal[
    "rename_column",
    "drop_column",
    "drop_table",
    "alter_column_type",
    "add_column",
    "rename_table",
]

Risk = Literal["critical", "high", "medium", "low"]

_RISK_MAP: dict[str, Risk] = {
    "drop_column": "critical",
    "drop_table": "critical",
    "rename_column": "high",
    "rename_table": "high",
    "alter_column_type": "medium",
    "add_column": "low",
}


class SchemaChange(BaseModel):
    change_type: ChangeType
    table: str
    database: str | None = None
    old_column: str | None = None
    new_column: str | None = None
    old_type: str | None = None
    new_type: str | None = None
    risk: Risk
    raw_sql: str
    line_number: int


# ---------------------------------------------------------------------------
# Identifier normalisation
# ---------------------------------------------------------------------------

def _unquote(token: str) -> str:
    """Strip surrounding quotes from a SQL identifier token."""
    token = token.strip()
    if len(token) >= 2 and token[0] in ('"', '`', "'") and token[-1] == token[0]:
        return token[1:-1]
    return token


# ---------------------------------------------------------------------------
# Regex patterns (case-insensitive, Postgres-first)
# Each pattern: (regex, handler_name)
# ---------------------------------------------------------------------------

# Capture any quoted or unquoted identifier
_ID = r'(?:"[^"]+"|`[^`]+`|\w+)'

_PATTERNS: list[tuple[re.Pattern, str]] = [
    # ALTER TABLE t RENAME COLUMN old TO new
    (
        re.compile(
            rf"ALTER\s+TABLE\s+({_ID}(?:\.{_ID})?)\s+RENAME\s+COLUMN\s+({_ID})\s+TO\s+({_ID})",
            re.IGNORECASE,
        ),
        "rename_column",
    ),
    # ALTER TABLE old RENAME TO new
    (
        re.compile(
            rf"ALTER\s+TABLE\s+({_ID}(?:\.{_ID})?)\s+RENAME\s+TO\s+({_ID})",
            re.IGNORECASE,
        ),
        "rename_table",
    ),
    # ALTER TABLE t DROP COLUMN col
    (
        re.compile(
            rf"ALTER\s+TABLE\s+({_ID}(?:\.{_ID})?)\s+DROP\s+COLUMN\s+(?:IF\s+EXISTS\s+)?({_ID})",
            re.IGNORECASE,
        ),
        "drop_column",
    ),
    # ALTER TABLE t ADD COLUMN col type
    (
        re.compile(
            rf"ALTER\s+TABLE\s+({_ID}(?:\.{_ID})?)\s+ADD\s+COLUMN\s+(?:IF\s+NOT\s+EXISTS\s+)?({_ID})\s+(\w[\w\s(,)]*?)(?:\s*;)?$",
            re.IGNORECASE,
        ),
        "add_column",
    ),
    # ALTER TABLE t ALTER COLUMN col TYPE newtype   (Postgres)
    # also: ALTER TABLE t ALTER COLUMN col SET DATA TYPE newtype
    (
        re.compile(
            rf"ALTER\s+TABLE\s+({_ID}(?:\.{_ID})?)\s+ALTER\s+COLUMN\s+({_ID})\s+(?:SET\s+DATA\s+)?TYPE\s+(\w[\w\s(,)]*?)(?:\s*;)?$",
            re.IGNORECASE,
        ),
        "alter_column_type",
    ),
    # DROP TABLE [IF EXISTS] t
    (
        re.compile(
            rf"DROP\s+TABLE\s+(?:IF\s+EXISTS\s+)?({_ID}(?:\.{_ID})?)",
            re.IGNORECASE,
        ),
        "drop_table",
    ),
]

# Detect SQL file extensions
_SQL_FILE_RE = re.compile(r"\+\+\+\s+b/.+\.sql(?:\s|$)", re.IGNORECASE)

# Diff header lines to skip
_DIFF_HEADER_RE = re.compile(r"^(diff --git|index |@@|--- |--- /dev/null|\+\+\+ )")


# ---------------------------------------------------------------------------
# Table / schema splitting
# ---------------------------------------------------------------------------

def _split_table(raw: str) -> tuple[str, str | None]:
    """Split 'schema.table' or '"schema"."table"' into (table, schema).
    Uses regex so quoted identifiers containing dots are handled correctly."""
    raw = raw.strip()
    m = re.match(rf"^({_ID})\s*\.\s*({_ID})$", raw)
    if m:
        return _unquote(m.group(2)), _unquote(m.group(1))
    return _unquote(raw), None


# ---------------------------------------------------------------------------
# Match handlers
# ---------------------------------------------------------------------------

def _build(
    change_type: ChangeType,
    raw_sql: str,
    line_number: int,
    **kwargs,
) -> SchemaChange:
    return SchemaChange(
        change_type=change_type,
        risk=_RISK_MAP[change_type],
        raw_sql=raw_sql.strip(),
        line_number=line_number,
        **kwargs,
    )


def _handle_rename_column(m: re.Match, raw: str, lineno: int) -> SchemaChange:
    table, database = _split_table(m.group(1))
    return _build(
        "rename_column", raw, lineno,
        table=table, database=database,
        old_column=_unquote(m.group(2)),
        new_column=_unquote(m.group(3)),
    )


def _handle_rename_table(m: re.Match, raw: str, lineno: int) -> SchemaChange:
    table, database = _split_table(m.group(1))
    return _build(
        "rename_table", raw, lineno,
        table=table, database=database,
        old_column=None,
        new_column=_unquote(m.group(2)),
    )


def _handle_drop_column(m: re.Match, raw: str, lineno: int) -> SchemaChange:
    table, database = _split_table(m.group(1))
    return _build(
        "drop_column", raw, lineno,
        table=table, database=database,
        old_column=_unquote(m.group(2)),
    )


def _handle_add_column(m: re.Match, raw: str, lineno: int) -> SchemaChange:
    table, database = _split_table(m.group(1))
    col_type = m.group(3).strip().rstrip(";").strip()
    return _build(
        "add_column", raw, lineno,
        table=table, database=database,
        new_column=_unquote(m.group(2)),
        new_type=col_type,
    )


def _handle_alter_column_type(m: re.Match, raw: str, lineno: int) -> SchemaChange:
    table, database = _split_table(m.group(1))
    new_type = m.group(3).strip().rstrip(";").strip()
    return _build(
        "alter_column_type", raw, lineno,
        table=table, database=database,
        old_column=_unquote(m.group(2)),
        new_type=new_type,
    )


def _handle_drop_table(m: re.Match, raw: str, lineno: int) -> SchemaChange:
    table, database = _split_table(m.group(1))
    return _build(
        "drop_table", raw, lineno,
        table=table, database=database,
    )


_HANDLERS = {
    "rename_column": _handle_rename_column,
    "rename_table": _handle_rename_table,
    "drop_column": _handle_drop_column,
    "add_column": _handle_add_column,
    "alter_column_type": _handle_alter_column_type,
    "drop_table": _handle_drop_table,
}


# ---------------------------------------------------------------------------
# Core parser
# ---------------------------------------------------------------------------

def _strip_sql_comment(line: str) -> str:
    """Remove inline -- comments."""
    idx = line.find("--")
    if idx != -1:
        return line[:idx]
    return line


def _is_sql_context(diff_lines: list[str], current_index: int) -> bool:
    """
    Walk backwards through diff lines to find the most recent +++ header.
    Return True only if it references a .sql file.
    Returns True when no file header has been seen yet (assume SQL for safety),
    but only if the added line looks like SQL.
    """
    for i in range(current_index - 1, -1, -1):
        line = diff_lines[i]
        if line.startswith("+++ "):
            return bool(_SQL_FILE_RE.match(line))
    return False  # No file header found — skip to be safe


def _try_match(sql_line: str, raw: str, lineno: int) -> SchemaChange | None:
    """Try all patterns against a cleaned SQL line. Return first match."""
    for pattern, handler_name in _PATTERNS:
        m = pattern.search(sql_line)
        if m:
            try:
                return _HANDLERS[handler_name](m, raw, lineno)
            except Exception as exc:
                logger.warning("Handler %s failed on line %d: %s", handler_name, lineno, exc)
    return None


def parse_schema_diff(diff_text: str) -> list[SchemaChange]:
    """
    Parse a unified git diff and return detected SchemaChange objects.

    Only added lines (starting with '+') are examined. Non-SQL files and
    diff header lines are skipped. Unrecognised lines are silently skipped.
    """
    results: list[SchemaChange] = []
    lines = diff_text.splitlines()

    for lineno, raw_line in enumerate(lines, start=1):
        # Skip diff metadata / headers
        if _DIFF_HEADER_RE.match(raw_line):
            continue

        # Only look at added lines
        if not raw_line.startswith("+"):
            continue

        # Check we are inside a .sql file context
        if not _is_sql_context(lines, lineno - 1):
            continue

        # Strip the leading '+' and any trailing whitespace
        sql_fragment = raw_line[1:].strip()

        # Skip blank lines and pure SQL comments
        if not sql_fragment or sql_fragment.startswith("--"):
            continue

        sql_fragment = _strip_sql_comment(sql_fragment)

        # Split multi-statement fragments (e.g. two statements on one diff line)
        try:
            statements = sqlparse.split(sql_fragment)
        except Exception:
            statements = [sql_fragment]

        for stmt in statements:
            stmt = stmt.strip().rstrip(";")
            if not stmt:
                continue
            change = _try_match(stmt, raw_line, lineno)
            if change:
                results.append(change)
            else:
                logger.debug("No schema change detected at diff line %d: %r", lineno, stmt)

    return results
