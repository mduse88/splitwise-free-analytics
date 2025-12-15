"""Email sender module - sends reports via Gmail SMTP."""

import smtplib
from datetime import datetime
from email import encoders
from email.mime.base import MIMEBase
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from src.config import app as app_config
from src.config import email as config


def send_dashboard(html_path: str) -> None:
    """Send the HTML dashboard as an email attachment via Gmail SMTP.
    
    Args:
        html_path: Path to the HTML file to attach.
        
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
    msg = MIMEMultipart()
    msg["From"] = config.gmail_address
    msg["To"] = ", ".join(recipient_list)
    msg["Subject"] = f"{app_config.title} - {datetime.now().strftime('%d %B %Y')}"
    
    # Email body
    body = """Ciao!

Ecco il report settimanale delle spese familiari.

Apri il file HTML allegato nel browser per vedere il dashboard interattivo.

A presto!
"""
    msg.attach(MIMEText(body, "plain"))
    
    # Attach HTML file
    with open(html_path, "rb") as attachment:
        part = MIMEBase("application", "octet-stream")
        part.set_payload(attachment.read())
    
    encoders.encode_base64(part)
    # Generate filename from title (date prefix, lowercase, underscores)
    safe_title = app_config.title.lower().replace(" ", "_")
    filename = f"{datetime.now().strftime('%Y-%m-%d')}_{safe_title}.html"
    part.add_header("Content-Disposition", f"attachment; filename={filename}")
    msg.attach(part)
    
    # Send via Gmail SMTP
    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(config.gmail_address, config.gmail_app_password)
            server.sendmail(config.gmail_address, recipient_list, msg.as_string())
        print(f"Email sent successfully to: {', '.join(recipient_list)}")
    except Exception as e:
        print(f"Failed to send email: {e}")
        raise

