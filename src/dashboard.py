"""Dashboard generation module - creates interactive HTML dashboard."""

import json
import os
from pathlib import Path
from typing import Optional

import pandas as pd
from jinja2 import Template

from src.config import app as app_config


# Path to template file
TEMPLATE_PATH = Path(__file__).parent.parent / "templates" / "dashboard.html"


def generate(df: pd.DataFrame, output_path: str, summary: Optional[dict] = None) -> None:
    """Generate an interactive HTML dashboard with charts and filterable table.
    
    Args:
        df: DataFrame with expense data.
        output_path: Path to write the HTML file.
        summary: Optional dictionary with monthly summary statistics.
                 If provided, displays a collapsible summary section.
    """
    # Prepare data for template
    context = _prepare_template_context(df, summary)
    
    # Load and render template
    with open(TEMPLATE_PATH, "r", encoding="utf-8") as f:
        template = Template(f.read())
    
    html_content = template.render(**context)
    
    # Write output
    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(html_content)
    
    print(f"Dashboard saved to {output_path}")


def _prepare_template_context(df: pd.DataFrame, summary: Optional[dict] = None) -> dict:
    """Prepare all data needed for the template.
    
    Args:
        df: DataFrame with expense data.
        summary: Optional monthly summary statistics.
        
    Returns:
        Dictionary with all template context variables.
    """
    # Get unique values for filters (months in descending order)
    months = sorted(df["month_str"].unique().tolist(), reverse=True)
    categories = sorted(df["category_name"].dropna().unique().tolist())
    
    # Get last 12 months for default filter
    last_12_months = months[:12] if len(months) >= 12 else months
    
    # Prepare table data
    table_df = df[["date", "description", "cost", "currency_code", "category_name", "month_str"]].copy()
    table_df["date"] = table_df["date"].dt.strftime("%Y-%m-%d")
    table_df = table_df.sort_values("date", ascending=False)
    table_data = table_df.to_dict("records")
    
    context = {
        "title": app_config.title,
        "table_data": json.dumps(table_data),
        "months": json.dumps(months),
        "categories": json.dumps(categories),
        "last_12_months": json.dumps(last_12_months),
        "summary": summary,  # Pass summary to template (can be None)
    }
    
    return context
