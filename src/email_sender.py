"""Email sender module - sends reports via Gmail SMTP."""

import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from src.config import app as app_config
from src.config import email as config
from src.logging_utils import log_error


def send_dashboard(dashboard_link: str, summary: dict) -> None:
    """Send an email with the monthly summary and Google Drive dashboard link.
    
    Args:
        dashboard_link: URL to the dashboard on Google Drive.
        summary: Dictionary with monthly summary statistics from stats module.
        
    Raises:
        ValueError: If email configuration is incomplete.
        Exception: If email sending fails.
    """
    if not config.is_configured:
        raise ValueError(
            "Email not configured - missing GMAIL_ADDRESS, GMAIL_APP_PASSWORD, or RECIPIENT_EMAIL"
        )
    
    # Parse recipients (comma-separated)
    recipient_list = [email.strip() for email in config.recipient_email.split(",")]
    
    # Create message
    msg = MIMEMultipart("alternative")
    msg["From"] = config.gmail_address
    msg["To"] = ", ".join(recipient_list)
    msg["Subject"] = f"{app_config.title} - As of {summary['report_date']}"
    
    # Create plain text version
    plain_body = _create_plain_text_body(dashboard_link, summary)
    
    # Create HTML version
    html_body = _create_html_body(dashboard_link, summary)
    
    # Attach both versions (email clients will choose the best one)
    msg.attach(MIMEText(plain_body, "plain"))
    msg.attach(MIMEText(html_body, "html"))
    
    # Send via Gmail SMTP
    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(config.gmail_address, config.gmail_app_password)
            server.sendmail(config.gmail_address, recipient_list, msg.as_string())
        pass  # Email sent successfully
    except Exception as e:
        log_error("ERROR: Failed to send email", str(e))
        raise


def _get_trend_symbol(direction: str) -> str:
    """Get the trend symbol for a direction."""
    symbols = {
        'up': '↑',
        'down': '↓',
        'stable': '→',
    }
    return symbols.get(direction, '→')


def _format_trend(pct: float, direction: str) -> str:
    """Format trend percentage with symbol."""
    symbol = _get_trend_symbol(direction)
    if direction == 'stable':
        return f"{symbol} stable"
    sign = '+' if pct > 0 else ''
    return f"{symbol} {sign}{pct:.1f}%"


def _create_plain_text_body(dashboard_link: str, summary: dict) -> str:
    """Create plain text email body."""
    lines = [
        f"📊 YOUR EXPENSE SUMMARY",
        f"{'═' * 40}",
        f"As of {summary['report_date']}",
        f"",
        f"Last Full Month: {summary['month_name']}",
        f"Total Expenses:     €{summary['total_expenses']:,.2f} ({summary['expense_count']} transactions)",
        f"Your Monthly Avg:   €{summary['monthly_avg']:,.2f} (based on {summary['total_months']} months)",
        f"Trend:              {_format_trend(summary['trend_pct'], summary['trend_direction'])} vs your average",
        f"",
        f"📈 TOP CATEGORIES",
        f"{'═' * 40}",
    ]
    
    for i, cat in enumerate(summary['top_categories'], 1):
        trend = _format_trend(cat['trend_pct'], cat['trend_direction'])
        lines.append(f"{i}. {cat['name']:<20} €{cat['amount']:>8,.2f}  {trend}")
    
    lines.extend([
        f"",
        f"🔗 VIEW FULL DASHBOARD",
        f"{dashboard_link}",
        f"",
        f"That's all for now — see you next month!",
    ])
    
    return "\n".join(lines)


def _create_html_body(dashboard_link: str, summary: dict) -> str:
    """Create HTML email body."""
    # Generate category rows
    category_rows = ""
    for i, cat in enumerate(summary['top_categories'], 1):
        trend_color = _get_trend_color(cat['trend_direction'])
        trend_text = _format_trend(cat['trend_pct'], cat['trend_direction'])
        category_rows += f"""
            <tr>
                <td style="padding: 8px; border-bottom: 1px solid #eee;">{i}. {cat['name']}</td>
                <td style="padding: 8px; border-bottom: 1px solid #eee; text-align: right;">€{cat['amount']:,.2f}</td>
                <td style="padding: 8px; border-bottom: 1px solid #eee; text-align: right; color: {trend_color};">{trend_text}</td>
            </tr>
        """
    
    trend_color = _get_trend_color(summary['trend_direction'])
    trend_text = _format_trend(summary['trend_pct'], summary['trend_direction'])
    
    return f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="utf-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
    </head>
    <body style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; max-width: 600px; margin: 0 auto; padding: 20px; background-color: #f5f5f5;">
        <div style="background-color: white; border-radius: 12px; padding: 30px; box-shadow: 0 2px 10px rgba(0,0,0,0.1);">
            
            <!-- Header -->
            <h1 style="color: #333; margin: 0 0 5px 0; font-size: 24px;">📊 Your Expense Summary</h1>
            <p style="color: #888; margin: 0 0 25px 0; font-size: 12px;">As of {summary['report_date']}</p>
            
            <!-- Main Stats -->
            <div style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); border-radius: 10px; padding: 25px; color: white; margin-bottom: 25px;">
                <h2 style="margin: 0 0 15px 0; font-size: 18px; opacity: 0.9;">Last Full Month: {summary['month_name']}</h2>
                <div style="font-size: 36px; font-weight: bold; margin-bottom: 5px;">€{summary['total_expenses']:,.2f}</div>
                <div style="font-size: 14px; opacity: 0.9; margin-bottom: 15px;">{summary['expense_count']} transactions</div>
                <div style="display: flex; justify-content: space-between; border-top: 1px solid rgba(255,255,255,0.3); padding-top: 15px; margin-top: 10px;">
                    <div>
                        <div style="font-size: 11px; opacity: 0.8;">Your Monthly Average</div>
                        <div style="font-size: 16px; font-weight: 600;">€{summary['monthly_avg']:,.2f}</div>
                    </div>
                    <div style="text-align: right;">
                        <div style="font-size: 11px; opacity: 0.8;">vs Your Average</div>
                        <div style="font-size: 16px; font-weight: 600;">{trend_text}</div>
                    </div>
                </div>
            </div>
            
            <!-- Top Categories -->
            <h3 style="color: #333; margin: 0 0 15px 0; font-size: 16px;">📈 Top Categories</h3>
            <table style="width: 100%; border-collapse: collapse; margin-bottom: 25px;">
                <thead>
                    <tr style="background-color: #f8f9fa;">
                        <th style="padding: 10px 8px; text-align: left; font-size: 12px; color: #666;">Category</th>
                        <th style="padding: 10px 8px; text-align: right; font-size: 12px; color: #666;">Amount</th>
                        <th style="padding: 10px 8px; text-align: right; font-size: 12px; color: #666;">Trend</th>
                    </tr>
                </thead>
                <tbody>
                    {category_rows}
                </tbody>
            </table>
            
            <!-- CTA Button -->
            <div style="text-align: center; margin-top: 30px;">
                <a href="{dashboard_link}" style="display: inline-block; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; text-decoration: none; padding: 15px 30px; border-radius: 8px; font-weight: 600; font-size: 14px;">
                    View Full Dashboard →
                </a>
            </div>
            
            <!-- Footer -->
            <p style="color: #888; font-size: 12px; text-align: center; margin-top: 30px;">
                That's all for now — see you next month! 👋
            </p>
        </div>
    </body>
    </html>
    """


def _get_trend_color(direction: str) -> str:
    """Get the color for a trend direction."""
    colors = {
        'up': '#e74c3c',     # Red for spending increase
        'down': '#27ae60',   # Green for spending decrease
        'stable': '#888888', # Gray for stable
    }
    return colors.get(direction, '#888888')
