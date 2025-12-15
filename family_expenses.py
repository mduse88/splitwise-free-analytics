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

from src import splitwise_client, dashboard, gdrive, email_sender, stats, firebase
from src.config import app as app_config
from src.config import gdrive as gdrive_config, email as email_config
from src import logging_utils
from src.logging_utils import log_info, log_verbose


def parse_args() -> argparse.Namespace:
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="Fetch Splitwise expenses, upload to Google Drive, and optionally send email.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Fetch fresh data from Splitwise, upload to Google Drive
  python family_expenses.py

  # Fetch fresh data, upload to Drive, send email
  python family_expenses.py --email

  # Use cached data, save to output/, upload to Drive
  python family_expenses.py --local

  # Use cached data, save to output/, upload to Drive, send email
  python family_expenses.py --local --email

  # Any command with verbose logging
  python family_expenses.py --local --email --full-log
        """,
    )
    
    parser.add_argument(
        "--email",
        action="store_true",
        help="Send email with monthly summary and Google Drive link",
    )
    
    parser.add_argument(
        "--local",
        action="store_true",
        help="Use cached data (Drive → output/ → API) and save files to output/ folder",
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
            file_id, _ = result
            try:
                json_content = gdrive.download_json(file_id)
                data = json.loads(json_content)
                return pd.DataFrame(data)
            except Exception:
                pass  # Fall through to local cache
    
    # Fall back to local output/ folder
    local_path = find_latest_local_json()
    if local_path:
        try:
            return pd.read_json(local_path)
        except Exception:
            pass  # Return None below
    
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
    
    # Configure centralized verbose logging for all modules
    logging_utils.set_verbose(args.full_log)
    
    log_verbose(f"=== Starting {app_config.title} ===")
    
    timestamp = datetime.now().strftime("%Y-%m-%d")
    
    # Step 1: Get data (--local affects data source only)
    if args.local:
        log_verbose("Data source: cached (Drive → output/ → API fallback)")
        raw_df = load_cached_data()
        
        if raw_df is None:
            log_verbose("No cached data found - fetching from Splitwise API...")
            client = splitwise_client.get_client()
            raw_df = splitwise_client.get_raw_expenses(client)
        else:
            log_verbose("Loaded cached data")
    else:
        log_verbose("Data source: fresh from Splitwise API")
        client = splitwise_client.get_client()
        raw_df = splitwise_client.get_raw_expenses(client)
    
    if raw_df.empty:
        log_info("ERROR: No data found")
        return
    
    log_verbose(f"Raw data: {len(raw_df)} total records (including payments)")
    
    # Step 2: Process data for dashboard
    processed_df = splitwise_client.process_for_dashboard(raw_df)
    
    log_verbose(f"Dashboard data: {len(processed_df)} expenses")
    if not processed_df.empty and logging_utils.is_verbose():
        log_verbose(f"Date range: {processed_df['date'].min()} to {processed_df['date'].max()}")
        log_verbose(f"Months found: {processed_df['month_str'].nunique()}")
    
    # Step 3: Calculate monthly summary statistics
    summary = stats.calculate_monthly_summary(processed_df)
    log_verbose(f"Monthly summary: {summary['month_name']} - €{summary['total_expenses']:,.2f}")
    
    # Step 4: Create files (--local affects storage location)
    temp_files = []
    if args.local:
        json_path, csv_path, html_path = create_local_files(raw_df, timestamp)
        log_verbose("Files saved to output/ folder")
    else:
        temp_files, json_path, csv_path, html_path = create_temp_files(raw_df)
        log_verbose("Files saved to temp folder")
    
    try:
        # Step 5: Generate dashboard
        dashboard.generate(processed_df, html_path, summary=summary)
        log_verbose(f"Dashboard generated with {len(processed_df)} expenses")
        
        # Step 6: Upload to Google Drive for backup (always, when configured)
        if gdrive_config.is_configured:
            files_to_upload = [
                (json_path, "expenses.json"),
                (csv_path, "expenses.csv"),
                (html_path, "expenses_dashboard.html"),
            ]
            gdrive.upload_files(files_to_upload, timestamp)
            log_verbose("Files uploaded to Google Drive (backup)")
        else:
            log_verbose("Google Drive not configured - skipping backup")
        
        # Step 7: Deploy to Firebase Hosting (the dashboard URL for email)
        firebase_url = None
        firebase_url = firebase.deploy_dashboard(html_path)
        if firebase_url:
            log_verbose(f"Dashboard deployed to Firebase: {firebase_url}")
        else:
            log_verbose("Firebase deployment skipped or failed")
        
        # Step 8: Send email (when --email flag is passed)
        if args.email:
            if not email_config.is_configured:
                log_verbose("Email not configured - skipping")
            elif firebase_url:
                # Use Firebase URL (auth-protected live dashboard)
                email_sender.send_dashboard(firebase_url, summary)
                log_verbose("Email sent with Firebase dashboard link")
            else:
                log_info("WARNING: No Firebase URL available - skipping email")
        
        # Show local file path if in local mode
        if args.local:
            log_verbose(f"Open the dashboard: open {html_path}")
    
    finally:
        # Only cleanup temp files (not local files)
        if temp_files:
            cleanup_temp_files(temp_files)


if __name__ == "__main__":
    main()
