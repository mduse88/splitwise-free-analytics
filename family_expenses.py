#!/usr/bin/env python3
"""
Splitwise Expense Dashboard - Main Entry Point

Fetches expenses from Splitwise, generates an interactive dashboard,
uploads to Google Drive, and optionally sends email notifications.
"""

import argparse
import glob
import json
import os
import tempfile
from datetime import datetime

import pandas as pd

from src import splitwise_client, dashboard, gdrive, email_sender, stats
from src.config import app as app_config
from src.config import gdrive as gdrive_config, email as email_config


def parse_args() -> argparse.Namespace:
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="Fetch Splitwise expenses, upload to Google Drive, and optionally send email.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Default: generate dashboard and upload to Google Drive
  python family_expenses.py

  # With email: upload to Google Drive and send email with Drive link
  python family_expenses.py --email

  # Skip upload (useful for testing)
  python family_expenses.py --no-upload

  # Save files locally to output/ folder
  python family_expenses.py --local
        """,
    )
    
    parser.add_argument(
        "--email",
        action="store_true",
        help="Send email with monthly summary and Google Drive link",
    )
    
    parser.add_argument(
        "--no-upload",
        action="store_true",
        help="Skip uploading files to Google Drive",
    )
    
    parser.add_argument(
        "--local",
        action="store_true",
        help="Save files locally to output/ folder instead of temp files",
    )
    
    parser.add_argument(
        "--full-log",
        action="store_true",
        help="Enable verbose logging (default: minimal logging for public runs)",
    )
    
    return parser.parse_args()


def create_temp_files(raw_df) -> tuple[list[str], str, str, str]:
    """Create temporary files for JSON, CSV, and HTML.
    
    Args:
        raw_df: Raw DataFrame with ALL Splitwise data (for backup).
    
    Returns:
        Tuple of (list of temp paths, json_path, csv_path, html_path)
    """
    temp_files = []
    
    # JSON - full raw data backup
    json_file = tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False)
    raw_df.to_json(json_file, orient="records", index=False, indent=2, date_format="iso", default_handler=str)
    json_file.close()
    temp_files.append(json_file.name)
    
    # CSV - full raw data backup
    csv_file = tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False, newline="")
    raw_df.to_csv(csv_file, index=False)
    csv_file.close()
    temp_files.append(csv_file.name)
    
    # HTML - will be generated separately with processed data
    html_file = tempfile.NamedTemporaryFile(mode="w", suffix=".html", delete=False)
    html_file.close()
    temp_files.append(html_file.name)
    
    return temp_files, json_file.name, csv_file.name, html_file.name


def cleanup_temp_files(temp_files: list[str]) -> None:
    """Remove temporary files."""
    for path in temp_files:
        try:
            os.unlink(path)
        except OSError:
            pass


def find_latest_local_json() -> str | None:
    """Find the most recent expenses.json file in output/ folder.
    
    Returns:
        Path to the most recent *_expenses.json file, or None if not found.
    """
    output_dir = "output"
    if not os.path.exists(output_dir):
        return None
    
    # Find all *_expenses.json files (date prefix means sorted = newest last)
    pattern = os.path.join(output_dir, "*_expenses.json")
    files = sorted(glob.glob(pattern))
    
    if files:
        return files[-1]  # Return the most recent (last when sorted)
    
    return None


def load_cached_data() -> pd.DataFrame | None:
    """Try to load cached data from Google Drive or local output/ folder.
    
    Fallback order:
    1. Google Drive (most recent *_expenses.json)
    2. Local output/ folder (most recent *_expenses.json)
    
    Returns:
        DataFrame with cached data, or None if no cache available.
    """
    # Try Google Drive first
    if gdrive_config.is_configured:
        result = gdrive.find_latest_json()
        if result:
            file_id, filename = result
            print(f"Loading cached data from Google Drive: {filename}")
            try:
                json_content = gdrive.download_json(file_id)
                data = json.loads(json_content)
                return pd.DataFrame(data)
            except Exception as e:
                print(f"Warning: Failed to download from Google Drive: {e}")
    
    # Fall back to local output/ folder
    local_path = find_latest_local_json()
    if local_path:
        print(f"Loading cached data from local file: {local_path}")
        try:
            return pd.read_json(local_path)
        except Exception as e:
            print(f"Warning: Failed to read local cache: {e}")
    
    return None


def create_local_files(raw_df, timestamp: str) -> tuple[str, str, str]:
    """Create files in output/ directory for local viewing.
    
    Args:
        raw_df: Raw DataFrame with ALL Splitwise data (for backup).
        timestamp: Date string for filename.
    
    Returns:
        Tuple of (json_path, csv_path, html_path)
    """
    output_dir = "output"
    os.makedirs(output_dir, exist_ok=True)
    
    json_path = os.path.join(output_dir, f"{timestamp}_expenses.json")
    csv_path = os.path.join(output_dir, f"{timestamp}_expenses.csv")
    html_path = os.path.join(output_dir, f"{timestamp}_expenses_dashboard.html")
    
    # Remove existing files with same name before creating new ones
    for path in [json_path, csv_path, html_path]:
        if os.path.exists(path):
            os.remove(path)
    
    # Save full raw data for backup
    raw_df.to_json(json_path, orient="records", index=False, indent=2, date_format="iso", default_handler=str)
    raw_df.to_csv(csv_path, index=False)
    
    return json_path, csv_path, html_path


def main() -> None:
    """Main entry point."""
    args = parse_args()
    full_log = args.full_log
    
    def log_info(message: str) -> None:
        """Minimal logging always shown."""
        print(message)
    
    def log_verbose(message: str) -> None:
        """Verbose logging shown only when full_log is enabled."""
        if full_log:
            print(message)
    
    log_info(f"=== Starting {app_config.title} ===")
    
    timestamp = datetime.now().strftime("%Y-%m-%d")
    
    # Local mode: use cached data to avoid API calls
    if args.local:
        log_info("Mode: local (use cached data if available)")
        raw_df = load_cached_data()
        
        if raw_df is None:
            log_info("No cached data found - fetching from Splitwise API...")
            client = splitwise_client.get_client()
            raw_df = splitwise_client.get_raw_expenses(client)
        else:
            log_info("Loaded cached data")
        
        if raw_df.empty:
            log_info("ERROR: No data found!")
            return
        
        log_verbose(f"Raw data: {len(raw_df)} total records (including payments)")
        
        # Process for dashboard
        processed_df = splitwise_client.process_for_dashboard(raw_df)
        
        log_verbose(f"Dashboard data: {len(processed_df)} expenses")
        if not processed_df.empty and full_log:
            log_verbose(f"Date range: {processed_df['date'].min()} to {processed_df['date'].max()}")
            log_verbose(f"Months found: {processed_df['month_str'].nunique()}")
        
        summary = stats.calculate_monthly_summary(processed_df)
        log_verbose(f"Monthly summary: {summary['month_name']} - €{summary['total_expenses']:,.2f}")
        
        json_path, csv_path, html_path = create_local_files(raw_df, timestamp)
        dashboard.generate(processed_df, html_path, summary=summary)
        log_info("Saved files to output/ (local mode)")
        log_verbose(f"  - {html_path} (dashboard with {len(processed_df)} expenses)")
        log_verbose(f"  - {json_path} (full backup: {len(raw_df)} records)")
        log_verbose(f"  - {csv_path} (full backup: {len(raw_df)} records)")
        log_verbose(f"Open the dashboard: open {html_path}")
        return
    
    # Cloud mode: always fetch fresh data from Splitwise
    log_info("Mode: cloud (fresh fetch from Splitwise API)")
    log_verbose("Fetching fresh data from Splitwise API...")
    client = splitwise_client.get_client()
    raw_df = splitwise_client.get_raw_expenses(client)
    
    log_verbose(f"Raw data: {len(raw_df)} total records (including payments)")
    
    if raw_df.empty:
        log_info("ERROR: No data found! Check API key and group_id.")
        return
    
    # Process for dashboard (filter payments, select columns)
    processed_df = splitwise_client.process_for_dashboard(raw_df)
    
    log_verbose(f"Dashboard data: {len(processed_df)} expenses")
    if not processed_df.empty and full_log:
        log_verbose(f"Date range: {processed_df['date'].min()} to {processed_df['date'].max()}")
        log_verbose(f"Months found: {processed_df['month_str'].nunique()}")
    
    # Calculate monthly summary statistics
    summary = stats.calculate_monthly_summary(processed_df)
    log_verbose(f"Monthly summary: {summary['month_name']} - €{summary['total_expenses']:,.2f}")
    
    # Cloud mode: use temp files
    temp_files, json_path, csv_path, html_path = create_temp_files(raw_df)
    
    try:
        # Generate dashboard with processed data and summary
        dashboard.generate(processed_df, html_path, summary=summary)
        log_info("Dashboard generated")
        log_verbose(f"Generated dashboard with {len(processed_df)} expenses")
        
        file_ids = {}
        dashboard_link = None
        
        # Upload to Google Drive
        if not args.no_upload:
            if gdrive_config.is_configured:
                files_to_upload = [
                    (json_path, "expenses.json"),
                    (csv_path, "expenses.csv"),
                    (html_path, "expenses_dashboard.html"),
                ]
                file_ids = gdrive.upload_files(files_to_upload, timestamp)
                
                # Get the dashboard file ID for sharing and linking
                dashboard_file_id = file_ids.get("expenses_dashboard")
                if dashboard_file_id:
                    dashboard_link = gdrive.get_view_link(dashboard_file_id)
                    
                    # Share with email recipients if email is enabled
                    if args.email and email_config.is_configured:
                        recipient_list = [
                            e.strip() for e in email_config.recipient_email.split(",")
                        ]
                        log_verbose(f"Sharing dashboard with {len(recipient_list)} recipient(s)")
                        gdrive.share_with_emails(dashboard_file_id, recipient_list)
            else:
                log_info("Google Drive not configured - skipping upload")
        else:
            log_info("Google Drive upload skipped (--no-upload flag)")
        
        # Send email with summary and Drive link
        if args.email:
            if email_config.is_configured:
                if dashboard_link:
                    email_sender.send_dashboard(dashboard_link, summary)
                else:
                    log_info("Warning: No dashboard link available - email requires Google Drive upload")
                    log_verbose("Run without --no-upload to enable email with Drive link")
            else:
                log_info("Email not configured - skipping")
    
    finally:
        cleanup_temp_files(temp_files)


if __name__ == "__main__":
    main()
