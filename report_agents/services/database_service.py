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
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            conn.commit()

    def store_dataframe(
        self,
        df: pd.DataFrame,
        source_file: str,
        sheet_name: str,
    ) -> str:
        """Store a pandas DataFrame as a SQLite table.

        Uses df.to_sql() for deterministic data transfer (0 tokens).

        Args:
            df: The DataFrame to store
            source_file: Original filename (e.g., "financials.xlsx")
            sheet_name: Sheet name within the file

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
                (source_file, sheet_name, table_name, column_names, column_types, row_count, sample_values)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
                (
                    source_file,
                    sheet_name,
                    table_name,
                    json.dumps([str(c) for c in df.columns]),
                    json.dumps([str(dt) for dt in df.dtypes]),
                    len(df),
                    json.dumps(sample_values),
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

        This is the minimal context needed for the LLM to write SQL queries.
        Much smaller than the full data (~500 tokens vs 260k).

        Returns:
            Formatted string describing available tables and columns
        """
        tables = self.get_table_list()
        if not tables:
            return "No financial data tables available."

        # Also get sample values for better query generation
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute("SELECT table_name, sample_values FROM table_metadata")
            samples_by_table = {row["table_name"]: row["sample_values"] for row in cursor}

        lines = ["## Available Financial Data Tables\n"]
        for t in tables:
            cols = json.loads(t["column_names"])
            samples = json.loads(samples_by_table.get(t["table_name"], "{}"))

            lines.append(f"### Table: `{t['table_name']}`")
            lines.append(f"- Source: {t['source_file']} / {t['sheet_name']}")
            lines.append(f"- Rows: {t['row_count']}")
            lines.append(f"- Columns: {', '.join(cols)}")

            # Show sample values for key columns (helps LLM understand data format)
            if samples:
                sample_strs = []
                for col, vals in list(samples.items())[:5]:  # Limit to 5 columns
                    sample_strs.append(f"  - {col}: {vals[:2]}")  # 2 samples per col
                if sample_strs:
                    lines.append("- Sample values:")
                    lines.extend(sample_strs)
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
