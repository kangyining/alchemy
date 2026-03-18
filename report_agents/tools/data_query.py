"""Natural language query tool for financial data.

This tool allows slide agents to query the SQLite database using
natural language. Only the query translation uses an LLM (gemini-3-flash-preview),
not the data storage or retrieval.
"""

import json
import logging
from typing import Any

from google import genai
from google.adk.tools import ToolContext

from report_agents.services.database_service import FinancialDataStore
from report_agents.utils.gemini_models import GEMINI_PRO_MODEL

logger = logging.getLogger(__name__)

# System prompt for SQL generation
SQL_GENERATION_PROMPT = """You are a SQL query generator for financial data stored in SQLite.

Given the database schema and a natural language question, generate a valid SQLite SELECT query.

RULES:
1. Only use tables and columns that exist in the schema
2. Use LIKE with % for partial text matching (case-insensitive with LOWER())
3. For financial metrics, the first column often contains row labels (e.g., "Revenue", "Net Income")
4. Return at most 100 rows (add LIMIT 100 if no limit specified)
5. Use appropriate aggregations (SUM, AVG) when asked for totals or averages
6. For period comparisons, look for columns like "Q1", "Q2", "2023", "2024", "Current", "Prior"
7. Output ONLY the SQL query, no explanation or markdown
8. IMPORTANT: Check for UNIT NOTE in the schema. If a table's values are expressed in thousands/millions/billions, apply the multiplier to dollar-amount columns in your SELECT (e.g., column_name * 1000) so results reflect actual dollar amounts. Do NOT multiply non-dollar columns like years, counts, or percentages.

SCHEMA:
{schema}

QUESTION: {question}

SQL:"""


async def _generate_sql(schema: str, question: str) -> str:
    """Use Gemini to convert natural language to SQL.

    Args:
        schema: Database schema description
        question: Natural language question

    Returns:
        Generated SQL query string
    """
    client = genai.Client()

    prompt = SQL_GENERATION_PROMPT.format(schema=schema, question=question)

    response = await client.aio.models.generate_content(
        model=GEMINI_PRO_MODEL,
        contents=prompt,
    )

    sql = response.text.strip()
    # Remove markdown code blocks if present
    if sql.startswith("```"):
        lines = sql.split("\n")
        sql = "\n".join(lines[1:-1] if lines[-1] == "```" else lines[1:])
    sql = sql.strip()

    logger.info("NL-to-SQL: '%s' -> '%s'", question[:50], sql[:100])
    return sql


def query_financial_data(
    query: str,
    tool_context: ToolContext,
) -> dict[str, Any]:
    """Query financial data using natural language.

    This tool translates natural language questions into SQL queries
    and returns relevant data from the parsed Excel/CSV documents.

    The data is stored in SQLite (via pandas df.to_sql, 0 tokens).
    Only this query step uses an LLM for NL-to-SQL translation.

    Args:
        query: Natural language question about the financial data.
            Examples:
            - "Get all revenue figures"
            - "Show the income statement data"
            - "Find gross profit and operating income"
            - "Get balance sheet items with current and prior period values"
            - "Show all data from the Cash Flow sheet"

    Returns:
        Dict with:
        - 'success': bool
        - 'data': List of matching rows as dicts
        - 'columns': Column names in result
        - 'row_count': Number of rows returned
        - 'sql_query': The generated SQL (for transparency)
        - 'error': Error message if failed
    """
    import asyncio

    # Get session ID from context
    session_id = tool_context.session.id if tool_context.session else "default"

    # Get or create the data store
    try:
        store = FinancialDataStore(session_id)
    except Exception as e:
        logger.error("Failed to access data store: %s", e)
        return {
            "success": False,
            "error": f"Database not available: {e}",
            "data": [],
            "columns": [],
            "row_count": 0,
        }

    # Get schema for SQL generation
    schema = store.get_schema_context()
    if "No financial data" in schema:
        return {
            "success": False,
            "error": "No financial data has been loaded. Please upload documents first.",
            "data": [],
            "columns": [],
            "row_count": 0,
        }

    # Generate SQL from natural language
    try:
        # Run async SQL generation
        loop = asyncio.get_event_loop()
        if loop.is_running():
            # If already in async context, create a new task
            import concurrent.futures

            with concurrent.futures.ThreadPoolExecutor() as executor:
                future = executor.submit(
                    asyncio.run, _generate_sql(schema, query)
                )
                sql = future.result(timeout=30)
        else:
            sql = asyncio.run(_generate_sql(schema, query))
    except Exception as e:
        logger.error("NL-to-SQL generation failed: %s", e)
        return {
            "success": False,
            "error": f"Failed to generate SQL query: {e}",
            "data": [],
            "columns": [],
            "row_count": 0,
            "natural_query": query,
        }

    # Execute the query
    try:
        rows, columns = store.execute_query(sql)
        agent_name = tool_context.agent_name
        logger.info(
            "QUERY_FINANCIAL_DATA | agent=%s | question='%s' | sql='%s' | rows=%d",
            agent_name, query, sql, len(rows),
        )
        return {
            "success": True,
            "data": rows,
            "columns": columns,
            "row_count": len(rows),
            "sql_query": sql,
            "natural_query": query,
        }
    except Exception as e:
        logger.error("SQL execution failed: %s | Query: %s", e, sql)
        return {
            "success": False,
            "error": f"Query execution failed: {e}",
            "sql_query": sql,
            "natural_query": query,
            "data": [],
            "columns": [],
            "row_count": 0,
        }


def list_available_tables(tool_context: ToolContext) -> dict[str, Any]:
    """List all available financial data tables.

    Use this tool to see what data is available before querying.

    Returns:
        Dict with:
        - 'success': bool
        - 'tables': List of table info (source, sheet, columns, row_count)
        - 'schema_context': Full schema description for reference
    """
    session_id = tool_context.session.id if tool_context.session else "default"

    try:
        store = FinancialDataStore(session_id)
        tables = store.get_table_list()
        schema = store.get_schema_context()

        # Parse column names for each table
        for t in tables:
            t["column_names"] = json.loads(t["column_names"])

        return {
            "success": True,
            "tables": tables,
            "table_count": len(tables),
            "schema_context": schema,
        }
    except Exception as e:
        logger.error("Failed to list tables: %s", e)
        return {
            "success": False,
            "error": str(e),
            "tables": [],
            "table_count": 0,
        }
