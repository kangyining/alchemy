"""Deterministic financial calculation tool.

All math is done in Python — the LLM never computes numbers directly.
"""

from google.adk.tools import ToolContext


def calculate_financial_metrics(
    metric_type: str,
    current_value: float,
    previous_value: float,
    tool_context: ToolContext,
) -> dict:
    """Calculate financial metrics deterministically.

    Args:
        metric_type: One of 'yoy_growth', 'margin', 'ratio', 'change', 'percentage'.
        current_value: Current period value (or numerator).
        previous_value: Previous period value (or denominator/base).

    Returns:
        Dict with 'result', 'unit', 'formula' keys, or 'error' if invalid.
    """
    if metric_type == "yoy_growth":
        if previous_value == 0:
            return {"error": "Division by zero: previous value is 0"}
        growth = ((current_value - previous_value) / abs(previous_value)) * 100
        return {
            "result": round(growth, 2),
            "unit": "%",
            "formula": f"({current_value} - {previous_value}) / |{previous_value}| * 100 = {round(growth, 2)}%",
        }

    elif metric_type == "margin":
        if previous_value == 0:
            return {"error": "Division by zero: base value is 0"}
        margin = (current_value / previous_value) * 100
        return {
            "result": round(margin, 2),
            "unit": "%",
            "formula": f"{current_value} / {previous_value} * 100 = {round(margin, 2)}%",
        }

    elif metric_type == "ratio":
        if previous_value == 0:
            return {"error": "Division by zero: denominator is 0"}
        ratio = current_value / previous_value
        return {
            "result": round(ratio, 4),
            "unit": "x",
            "formula": f"{current_value} / {previous_value} = {round(ratio, 4)}x",
        }

    elif metric_type == "change":
        change = current_value - previous_value
        return {
            "result": round(change, 2),
            "unit": "",
            "formula": f"{current_value} - {previous_value} = {round(change, 2)}",
        }

    elif metric_type == "percentage":
        if previous_value == 0:
            return {"error": "Division by zero: total is 0"}
        pct = (current_value / previous_value) * 100
        return {
            "result": round(pct, 2),
            "unit": "%",
            "formula": f"{current_value} / {previous_value} * 100 = {round(pct, 2)}%",
        }

    else:
        return {
            "error": f"Unknown metric_type '{metric_type}'. "
            "Supported: yoy_growth, margin, ratio, change, percentage"
        }
