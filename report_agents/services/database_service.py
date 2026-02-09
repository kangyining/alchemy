"""SQLite database service for session-scoped financial data storage.

This module provides a simple interface for storing pandas DataFrames
in SQLite and querying them. Data import uses df.to_sql() (0 tokens,
pure pandas). Only the query translation uses an LLM.
"""

import json
import logging
import re
import sqlite3
from pathlib import Path

import pandas as pd

logger = logging.getLogger(__name__)

# Default base path for session databases
DEFAULT_DB_PATH = "/tmp/report_agents"


class FinancialDataStore:
    """Manages SQLite database for a single session's financial data."""

    def __init__(self, session_id: str, base_path: str = DEFAULT_DB_PATH):
        """Initialize the data store for a session.

        Args:
            session_id: Unique session identifier
            base_path: Directory to store database files
        """
        self.session_id = session_id
        self.db_path = Path(base_path) / f"{session_id}.db"
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_schema()
        logger.info("FinancialDataStore initialized: %s", self.db_path)

    def _init_schema(self) -> None:
        """Create metadata table if not exists."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS table_metadata (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    source_file TEXT NOT NULL,
                    sheet_name TEXT NOT NULL,
                    table_name TEXT NOT NULL UNIQUE,
                    column_names TEXT NOT NULL,
                    column_types TEXT NOT NULL,
                    row_count INTEGER NOT NULL,
                    sample_values TEXT,
                    unit_note TEXT DEFAULT '',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            conn.commit()

    def store_dataframe(
        self,
        df: pd.DataFrame,
        source_file: str,
        sheet_name: str,
        unit_note: str = "",
    ) -> str:
        """Store a pandas DataFrame as a SQLite table.

        Uses df.to_sql() for deterministic data transfer (0 tokens).

        Args:
            df: The DataFrame to store
            source_file: Original filename (e.g., "financials.xlsx")
            sheet_name: Sheet name within the file
            unit_note: Unit qualifier detected from the sheet (e.g.,
                "Values expressed in thousands (multiply by 1,000 for actual amounts)")

        Returns:
            The sanitized table name used in SQLite
        """
        table_name = self._sanitize_table_name(source_file, sheet_name)

        with sqlite3.connect(self.db_path) as conn:
            # Store the data using pandas (deterministic, 0 tokens)
            df.to_sql(table_name, conn, if_exists="replace", index=False)

            # Collect sample values for each column (helps LLM write better queries)
            sample_values = {}
            for col in df.columns:
                non_null = df[col].dropna()
                if len(non_null) > 0:
                    samples = non_null.head(3).astype(str).tolist()
                    sample_values[str(col)] = samples

            # Store metadata
            conn.execute(
                """
                INSERT OR REPLACE INTO table_metadata
                (source_file, sheet_name, table_name, column_names, column_types, row_count, sample_values, unit_note)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
                (
                    source_file,
                    sheet_name,
                    table_name,
                    json.dumps([str(c) for c in df.columns]),
                    json.dumps([str(dt) for dt in df.dtypes]),
                    len(df),
                    json.dumps(sample_values),
                    unit_note,
                ),
            )
            conn.commit()

        logger.info(
            "Stored DataFrame: %s.%s -> %s (%d rows, %d cols)",
            source_file,
            sheet_name,
            table_name,
            len(df),
            len(df.columns),
        )
        return table_name

    def execute_query(self, sql: str, limit: int = 100) -> tuple[list[dict], list[str]]:
        """Execute SQL and return results.

        Args:
            sql: SQL query to execute
            limit: Maximum rows to return (safety limit)

        Returns:
            Tuple of (rows_as_dicts, column_names)
        """
        # Add LIMIT if not present (safety)
        sql_lower = sql.lower().strip()
        if "limit" not in sql_lower and sql_lower.startswith("select"):
            sql = f"{sql.rstrip(';')} LIMIT {limit}"

        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            try:
                cursor = conn.execute(sql)
                columns = [desc[0] for desc in cursor.description]
                rows = [dict(row) for row in cursor.fetchall()]
                logger.info("Query executed: %d rows returned", len(rows))
                return rows, columns
            except sqlite3.Error as e:
                logger.error("SQL execution error: %s | Query: %s", e, sql)
                raise

    def get_all_table_names(self) -> list[str]:
        """Return all table names in the SQLite database (from sqlite_master)."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table' ORDER BY name"
            )
            return [row[0] for row in cursor.fetchall()]

    def print_tables(self) -> None:
        """Log all table names to the screen (logger.info)."""
        names = self.get_all_table_names()
        if not names:
            logger.info("Database has no tables.")
            return
        logger.info("Tables in SQLite: %s", ", ".join(names))

    def get_all_table_contents(self, limit_per_table: int = 100) -> dict[str, list[dict]]:
        """Return contents of every table as dict[table_name -> list of row dicts].

        Args:
            limit_per_table: Max rows to fetch per table (default 100).
        """
        names = self.get_all_table_names()
        out = {}
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            for name in names:
                cursor = conn.execute(
                    f'SELECT * FROM "{name}" LIMIT {limit_per_table}'
                )
                out[name] = [dict(row) for row in cursor.fetchall()]
        return out

    def print_all_table_contents(self, limit_per_table: int = 50) -> None:
        """Log table names and their contents (first N rows) to the screen."""
        contents = self.get_all_table_contents(limit_per_table=limit_per_table)
        if not contents:
            logger.info("Database has no tables.")
            return
        for name, rows in contents.items():
            logger.info("--- Table: %s (%d rows) ---", name, len(rows))
            if not rows:
                continue
            keys = list(rows[0].keys())
            logger.info("Columns: %s", keys)
            for i, row in enumerate(rows):
                logger.info("  Row %d: %s", i + 1, row)
        logger.info("--- End table contents ---")

    def get_table_list(self) -> list[dict]:
        """Get list of all stored tables with metadata.

        Returns:
            List of dicts with table info (source_file, sheet_name, table_name, etc.)
        """
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(
                "SELECT source_file, sheet_name, table_name, column_names, row_count FROM table_metadata"
            )
            return [dict(row) for row in cursor.fetchall()]

    def get_schema_context(self) -> str:
        """Return schema description for LLM context.

        Includes column names, sample values for ALL columns, and the first
        few rows of each table so the LLM can understand what generic column
        names (col_8, col_9, ...) actually represent.

        Returns:
            Formatted string describing available tables and columns
        """
        tables = self.get_table_list()
        if not tables:
            return "No financial data tables available."

        # Get sample values, unit notes, and first rows for each table
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute("SELECT table_name, sample_values, unit_note FROM table_metadata")
            meta_by_table = {}
            for row in cursor:
                meta_by_table[row["table_name"]] = {
                    "sample_values": row["sample_values"],
                    "unit_note": row["unit_note"] or "",
                }

        lines = ["## Available Financial Data Tables\n"]
        for t in tables:
            cols = json.loads(t["column_names"])
            meta = meta_by_table.get(t["table_name"], {})
            samples = json.loads(meta.get("sample_values", "{}"))
            unit_note = meta.get("unit_note", "")

            lines.append(f"### Table: `{t['table_name']}`")
            lines.append(f"- Source: {t['source_file']} / {t['sheet_name']}")
            lines.append(f"- Rows: {t['row_count']}")
            lines.append(f"- Columns: {', '.join(cols)}")

            # Surface unit note prominently so LLM applies multiplier in queries
            if unit_note:
                lines.append(f"- **UNIT NOTE: {unit_note}**")

            # Show sample values for ALL columns so the LLM knows what
            # generic names like col_8 actually contain (e.g. year values)
            if samples:
                lines.append("- Sample values per column:")
                for col, vals in samples.items():
                    lines.append(f"  - {col}: {vals[:3]}")

            # Show first 3 rows so the LLM can map column positions to meaning
            try:
                with sqlite3.connect(self.db_path) as conn:
                    conn.row_factory = sqlite3.Row
                    cursor = conn.execute(
                        f'SELECT * FROM "{t["table_name"]}" LIMIT 3'
                    )
                    preview_rows = [dict(row) for row in cursor.fetchall()]
                    if preview_rows:
                        lines.append("- First rows:")
                        for i, row in enumerate(preview_rows):
                            lines.append(f"  Row {i}: {row}")
            except Exception:
                pass

            lines.append("")

        return "\n".join(lines)

    def cleanup(self) -> None:
        """Delete the database file."""
        if self.db_path.exists():
            self.db_path.unlink()
            logger.info("Database cleaned up: %s", self.db_path)

    @staticmethod
    def _sanitize_table_name(source_file: str, sheet_name: str) -> str:
        """Convert source file + sheet name to valid SQLite table name.

        Examples:
            ('financials.xlsx', 'Income Statement') -> 'financials_xlsx_income_statement'
            ('Q3 2024.csv', 'Sheet1') -> 'q3_2024_csv_sheet1'
        """
        combined = f"{source_file}_{sheet_name}"
        # Remove extension dots, replace spaces/special chars with underscores
        sanitized = re.sub(r"[^a-zA-Z0-9]", "_", combined).lower()
        # Collapse multiple underscores
        sanitized = re.sub(r"_+", "_", sanitized).strip("_")
        # SQLite identifiers can't start with a digit without quoting
        if sanitized and sanitized[0].isdigit():
            sanitized = f"t_{sanitized}"
        # SQLite table name limit
        return sanitized[:64]


def get_or_create_store(session_id: str) -> FinancialDataStore:
    """Get or create a FinancialDataStore for the given session.

    This is a convenience function for use in tools/agents.
    """
    return FinancialDataStore(session_id)
