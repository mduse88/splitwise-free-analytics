"""Statistics module - calculates monthly summaries and trends."""

from datetime import datetime
from typing import Optional

import pandas as pd


def calculate_monthly_summary(df: pd.DataFrame, num_top_categories: int = 5) -> dict:
    """Calculate summary for the most recent complete month.
    
    Args:
        df: Processed DataFrame with expenses (must have 'date', 'cost', 'category_name' columns).
        num_top_categories: Number of top categories to include.
    
    Returns:
        Dictionary with summary statistics:
        {
            'report_date': '2025-12-15 14:30:00',
            'month_name': 'November 2025',
            'total_expenses': 1234.56,
            'expense_count': 45,
            'monthly_avg': 1100.00,
            'trend_pct': 12.2,
            'trend_direction': 'up',
            'total_months': 12,
            'top_categories': [
                {
                    'name': 'Food',
                    'amount': 456.78,
                    'avg_12mo': 400.00,
                    'trend_pct': 14.2,
                    'trend_direction': 'up'
                },
                ...
            ]
        }
    """
    if df.empty:
        return _empty_summary()
    
    report_date = datetime.now().strftime("%Y-%m-%d %H:%M")
    
    # Get the most recent complete month (not current month)
    # Use UTC timezone to match the DataFrame's date column
    today = pd.Timestamp.now(tz='UTC')
    current_month_start = today.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    
    # Filter to get data before current month for "last month" stats
    df_before_current = df[df['date'] < current_month_start]
    
    if df_before_current.empty:
        # If no data before current month, use all data
        df_before_current = df
    
    # Find the most recent complete month
    last_complete_month = df_before_current['date'].max().to_period('M')
    month_name = last_complete_month.strftime('%B %Y')
    
    # Filter for last month's expenses
    df_last_month = df[df['date'].dt.to_period('M') == last_complete_month]
    
    # Calculate last month totals
    total_expenses = float(df_last_month['cost'].sum())
    expense_count = len(df_last_month)
    
    # Calculate true monthly average (counting ALL months, even empty ones)
    monthly_avg = calculate_true_monthly_average(df)
    total_months = _count_total_months(df)
    
    # Calculate trend (last month vs average)
    trend_pct, trend_direction = _calculate_trend(total_expenses, monthly_avg)
    
    # Calculate top categories with trends
    top_categories = _calculate_top_categories(df, df_last_month, num_top_categories)
    
    return {
        'report_date': report_date,
        'month_name': month_name,
        'total_expenses': round(total_expenses, 2),
        'expense_count': expense_count,
        'monthly_avg': round(monthly_avg, 2),
        'trend_pct': trend_pct,
        'trend_direction': trend_direction,
        'total_months': total_months,
        'top_categories': top_categories,
    }


def calculate_true_monthly_average(df: pd.DataFrame) -> float:
    """Calculate average counting ALL months between first and last expense.
    
    This counts every month in the range, even if some months have zero expenses.
    
    Example: Jan €150, Feb €0, Mar €150 → €100/month (not €150)
    
    Args:
        df: DataFrame with 'date' and 'cost' columns.
    
    Returns:
        Average monthly expense amount.
    """
    if df.empty:
        return 0.0
    
    total_months = _count_total_months(df)
    if total_months == 0:
        return 0.0
    
    return df['cost'].sum() / total_months


def _count_total_months(df: pd.DataFrame) -> int:
    """Count total months between first and last expense (inclusive).
    
    Args:
        df: DataFrame with 'date' column.
    
    Returns:
        Number of months in the range.
    """
    if df.empty:
        return 0
    
    first_month = df['date'].min().to_period('M')
    last_month = df['date'].max().to_period('M')
    
    # Calculate difference in months and add 1 to include both endpoints
    return (last_month - first_month).n + 1


def _calculate_trend(value: float, average: float) -> tuple[float, str]:
    """Calculate trend percentage and direction.
    
    Args:
        value: Current value to compare.
        average: Average value to compare against.
    
    Returns:
        Tuple of (percentage, direction) where direction is 'up', 'down', or 'stable'.
    """
    if average == 0:
        return 0.0, 'stable'
    
    trend_pct = ((value - average) / average) * 100
    
    # Consider "stable" if within ±5%
    if abs(trend_pct) < 5:
        direction = 'stable'
    elif trend_pct > 0:
        direction = 'up'
    else:
        direction = 'down'
    
    return round(trend_pct, 1), direction


def _calculate_top_categories(
    df_all: pd.DataFrame, 
    df_last_month: pd.DataFrame, 
    num_categories: int
) -> list[dict]:
    """Calculate top categories with their trends.
    
    Args:
        df_all: All expenses DataFrame.
        df_last_month: Last month's expenses DataFrame.
        num_categories: Number of top categories to return.
    
    Returns:
        List of category dictionaries with amounts and trends.
    """
    if df_last_month.empty:
        return []
    
    # Get top categories by last month's spending
    last_month_by_cat = df_last_month.groupby('category_name')['cost'].sum()
    top_cats = last_month_by_cat.nlargest(num_categories)
    
    # Calculate average for each category (using true monthly average)
    total_months = _count_total_months(df_all)
    if total_months == 0:
        total_months = 1
    
    all_by_cat = df_all.groupby('category_name')['cost'].sum()
    
    result = []
    for cat_name, amount in top_cats.items():
        # Get category's total across all time
        cat_total = all_by_cat.get(cat_name, 0)
        cat_avg = cat_total / total_months
        
        trend_pct, trend_direction = _calculate_trend(amount, cat_avg)
        
        result.append({
            'name': cat_name,
            'amount': round(float(amount), 2),
            'avg_12mo': round(float(cat_avg), 2),
            'trend_pct': trend_pct,
            'trend_direction': trend_direction,
        })
    
    return result


def _empty_summary() -> dict:
    """Return an empty summary structure."""
    return {
        'report_date': datetime.now().strftime("%Y-%m-%d %H:%M"),
        'month_name': 'No data',
        'total_expenses': 0.0,
        'expense_count': 0,
        'monthly_avg': 0.0,
        'trend_pct': 0.0,
        'trend_direction': 'stable',
        'total_months': 0,
        'top_categories': [],
    }

