"""
Tests for the schema_diff parser.

Run with:
    pytest backend/tests/test_schema_diff.py -v
"""

import pytest

from app.parsers.schema_diff import SchemaChange, parse_schema_diff


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

FIXTURE_1_RENAME_COLUMN = """\
--- a/migrations/005_rename_email.sql
+++ b/migrations/005_rename_email.sql
@@ -0,0 +1,1 @@
+ALTER TABLE users RENAME COLUMN email TO contact_email;
"""

FIXTURE_2_DROP_COLUMN = """\
--- a/migrations/006.sql
+++ b/migrations/006.sql
@@ -0,0 +1,1 @@
+ALTER TABLE orders DROP COLUMN amount_cents;
"""

FIXTURE_3_ADD_COLUMN = """\
--- a/migrations/007.sql
+++ b/migrations/007.sql
@@ -0,0 +1,1 @@
+ALTER TABLE users ADD COLUMN loyalty_tier VARCHAR(20);
"""

FIXTURE_4_NON_SQL = """\
--- a/README.md
+++ b/README.md
@@ -1,1 +1,1 @@
-old text
+new text
"""

FIXTURE_5_MULTI_STATEMENT = """\
--- a/migrations/008_multi.sql
+++ b/migrations/008_multi.sql
@@ -0,0 +1,2 @@
+ALTER TABLE users RENAME COLUMN phone TO mobile_number;
+ALTER TABLE deliveries DROP COLUMN driver_phone;
"""

FIXTURE_6_DROP_TABLE = """\
--- a/migrations/009.sql
+++ b/migrations/009.sql
@@ -0,0 +1,1 @@
+DROP TABLE legacy_sessions;
"""

FIXTURE_7_RENAME_TABLE = """\
--- a/migrations/010.sql
+++ b/migrations/010.sql
@@ -0,0 +1,1 @@
+ALTER TABLE order_items RENAME TO line_items;
"""

FIXTURE_8_ALTER_COLUMN_TYPE = """\
--- a/migrations/011.sql
+++ b/migrations/011.sql
@@ -0,0 +1,1 @@
+ALTER TABLE payments ALTER COLUMN amount TYPE NUMERIC(12,2);
"""

FIXTURE_9_QUOTED_IDENTIFIERS = """\
--- a/migrations/012.sql
+++ b/migrations/012.sql
@@ -0,0 +1,1 @@
+ALTER TABLE "public"."users" RENAME COLUMN "email" TO "contact_email";
"""

FIXTURE_10_SCHEMA_QUALIFIED = """\
--- a/migrations/013.sql
+++ b/migrations/013.sql
@@ -0,0 +1,1 @@
+ALTER TABLE public.orders DROP COLUMN amount_cents;
"""

FIXTURE_11_WITH_SQL_COMMENT = """\
--- a/migrations/014.sql
+++ b/migrations/014.sql
@@ -0,0 +1,2 @@
+-- This renames the column for PII compliance
+ALTER TABLE users DROP COLUMN ssn; -- social security number
"""

FIXTURE_12_DROP_IF_EXISTS = """\
--- a/migrations/015.sql
+++ b/migrations/015.sql
@@ -0,0 +1,1 @@
+DROP TABLE IF EXISTS temp_import_data;
"""


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def _only(changes: list[SchemaChange], n: int = 1) -> SchemaChange:
    assert len(changes) == n, f"Expected {n} change(s), got {len(changes)}: {changes}"
    return changes[0]


class TestFixture1RenameColumn:
    def setup_method(self):
        self.changes = parse_schema_diff(FIXTURE_1_RENAME_COLUMN)

    def test_returns_one_change(self):
        _only(self.changes)

    def test_change_type(self):
        assert self.changes[0].change_type == "rename_column"

    def test_table(self):
        assert self.changes[0].table == "users"

    def test_old_column(self):
        assert self.changes[0].old_column == "email"

    def test_new_column(self):
        assert self.changes[0].new_column == "contact_email"

    def test_risk(self):
        assert self.changes[0].risk == "high"


class TestFixture2DropColumn:
    def setup_method(self):
        self.changes = parse_schema_diff(FIXTURE_2_DROP_COLUMN)

    def test_returns_one_change(self):
        _only(self.changes)

    def test_change_type(self):
        assert self.changes[0].change_type == "drop_column"

    def test_table(self):
        assert self.changes[0].table == "orders"

    def test_old_column(self):
        assert self.changes[0].old_column == "amount_cents"

    def test_risk_is_critical(self):
        assert self.changes[0].risk == "critical"


class TestFixture3AddColumn:
    def setup_method(self):
        self.changes = parse_schema_diff(FIXTURE_3_ADD_COLUMN)

    def test_returns_one_change(self):
        _only(self.changes)

    def test_change_type(self):
        assert self.changes[0].change_type == "add_column"

    def test_table(self):
        assert self.changes[0].table == "users"

    def test_new_column(self):
        assert self.changes[0].new_column == "loyalty_tier"

    def test_risk_is_low(self):
        assert self.changes[0].risk == "low"


class TestFixture4NonSqlFile:
    def test_returns_empty_list(self):
        changes = parse_schema_diff(FIXTURE_4_NON_SQL)
        assert changes == []


class TestFixture5MultiStatement:
    def setup_method(self):
        self.changes = parse_schema_diff(FIXTURE_5_MULTI_STATEMENT)

    def test_returns_two_changes(self):
        assert len(self.changes) == 2, f"Expected 2, got {len(self.changes)}: {self.changes}"

    def test_first_is_rename(self):
        rename = next(c for c in self.changes if c.change_type == "rename_column")
        assert rename.table == "users"
        assert rename.old_column == "phone"
        assert rename.new_column == "mobile_number"

    def test_second_is_drop(self):
        drop = next(c for c in self.changes if c.change_type == "drop_column")
        assert drop.table == "deliveries"
        assert drop.old_column == "driver_phone"
        assert drop.risk == "critical"


class TestFixture6DropTable:
    def setup_method(self):
        self.changes = parse_schema_diff(FIXTURE_6_DROP_TABLE)

    def test_returns_one_change(self):
        _only(self.changes)

    def test_change_type(self):
        assert self.changes[0].change_type == "drop_table"

    def test_table(self):
        assert self.changes[0].table == "legacy_sessions"

    def test_risk_is_critical(self):
        assert self.changes[0].risk == "critical"


class TestFixture7RenameTable:
    def setup_method(self):
        self.changes = parse_schema_diff(FIXTURE_7_RENAME_TABLE)

    def test_returns_one_change(self):
        _only(self.changes)

    def test_change_type(self):
        assert self.changes[0].change_type == "rename_table"

    def test_table(self):
        assert self.changes[0].table == "order_items"

    def test_new_name(self):
        assert self.changes[0].new_column == "line_items"

    def test_risk_is_high(self):
        assert self.changes[0].risk == "high"


class TestFixture8AlterColumnType:
    def setup_method(self):
        self.changes = parse_schema_diff(FIXTURE_8_ALTER_COLUMN_TYPE)

    def test_returns_one_change(self):
        _only(self.changes)

    def test_change_type(self):
        assert self.changes[0].change_type == "alter_column_type"

    def test_table(self):
        assert self.changes[0].table == "payments"

    def test_column(self):
        assert self.changes[0].old_column == "amount"

    def test_new_type(self):
        assert "NUMERIC" in (self.changes[0].new_type or "").upper()

    def test_risk_is_medium(self):
        assert self.changes[0].risk == "medium"


class TestFixture9QuotedIdentifiers:
    def setup_method(self):
        self.changes = parse_schema_diff(FIXTURE_9_QUOTED_IDENTIFIERS)

    def test_returns_one_change(self):
        _only(self.changes)

    def test_change_type(self):
        assert self.changes[0].change_type == "rename_column"

    def test_table_unquoted(self):
        assert self.changes[0].table == "users"

    def test_database_extracted(self):
        assert self.changes[0].database == "public"

    def test_old_column_unquoted(self):
        assert self.changes[0].old_column == "email"

    def test_new_column_unquoted(self):
        assert self.changes[0].new_column == "contact_email"


class TestFixture10SchemaQualified:
    def setup_method(self):
        self.changes = parse_schema_diff(FIXTURE_10_SCHEMA_QUALIFIED)

    def test_returns_one_change(self):
        _only(self.changes)

    def test_change_type(self):
        assert self.changes[0].change_type == "drop_column"

    def test_table(self):
        assert self.changes[0].table == "orders"

    def test_database(self):
        assert self.changes[0].database == "public"


class TestFixture11SqlComments:
    def setup_method(self):
        self.changes = parse_schema_diff(FIXTURE_11_WITH_SQL_COMMENT)

    def test_ignores_comment_only_line(self):
        # Only the DROP COLUMN line should produce a change
        assert len(self.changes) == 1

    def test_drop_column_detected(self):
        assert self.changes[0].change_type == "drop_column"
        assert self.changes[0].table == "users"
        assert self.changes[0].old_column == "ssn"


class TestFixture12DropIfExists:
    def setup_method(self):
        self.changes = parse_schema_diff(FIXTURE_12_DROP_IF_EXISTS)

    def test_returns_one_change(self):
        _only(self.changes)

    def test_change_type(self):
        assert self.changes[0].change_type == "drop_table"

    def test_table(self):
        assert self.changes[0].table == "temp_import_data"


class TestLineNumbers:
    def test_line_number_is_accurate(self):
        changes = parse_schema_diff(FIXTURE_1_RENAME_COLUMN)
        assert changes[0].line_number > 0

    def test_raw_sql_contains_plus(self):
        changes = parse_schema_diff(FIXTURE_1_RENAME_COLUMN)
        # raw_sql stores the original diff line (starting with +)
        assert changes[0].raw_sql.startswith("+")


class TestEdgeCases:
    def test_empty_diff_returns_empty(self):
        assert parse_schema_diff("") == []

    def test_no_added_lines_returns_empty(self):
        diff = "--- a/m.sql\n+++ b/m.sql\n-ALTER TABLE x DROP COLUMN y;\n"
        assert parse_schema_diff(diff) == []

    def test_unknown_sql_returns_empty(self):
        diff = "--- a/m.sql\n+++ b/m.sql\n+CREATE INDEX idx_users_email ON users(email);\n"
        assert parse_schema_diff(diff) == []
