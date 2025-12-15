#!/usr/bin/env python3
"""
Splitwise Expense Dashboard - Main Entry Point

Fetches expenses from Splitwise, generates an interactive dashboard,
uploads to Google Drive, and optionally sends email notifications.
"""

import argparse
import os
import tempfile
from datetime import datetime

from src import splitwise_client, dashboard, gdrive, email_sender
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

  # With email: upload to Google Drive and send email notification
  python family_expenses.py --email

  # Skip upload (useful for testing)
  python family_expenses.py --no-upload
        """,
    )
    
    parser.add_argument(
        "--email",
        action="store_true",
        help="Send email notification with the dashboard attached",
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
    
    # Save full raw data for backup
    raw_df.to_json(json_path, orient="records", index=False, indent=2, date_format="iso", default_handler=str)
    raw_df.to_csv(csv_path, index=False)
    
    return json_path, csv_path, html_path


def main() -> None:
    """Main entry point."""
    args = parse_args()
    
    print(f"=== Starting {app_config.title} ===")
    
    # Fetch raw data from Splitwise (all fields, all records)
    client = splitwise_client.get_client()
    raw_df = splitwise_client.get_raw_expenses(client)
    
    print(f"Raw data: {len(raw_df)} total records (including payments)")
    
    if raw_df.empty:
        print("ERROR: No data found! Check API key and group_id.")
        return
    
    # Process for dashboard (filter payments, select columns)
    processed_df = splitwise_client.process_for_dashboard(raw_df)
    
    print(f"Dashboard data: {len(processed_df)} expenses")
    if not processed_df.empty:
        print(f"Date range: {processed_df['date'].min()} to {processed_df['date'].max()}")
        print(f"Months found: {processed_df['month_str'].nunique()}")
    
    timestamp = datetime.now().strftime("%Y-%m-%d")
    
    # Local mode: save to output/ folder
    if args.local:
        json_path, csv_path, html_path = create_local_files(raw_df, timestamp)
        dashboard.generate(processed_df, html_path)
        print(f"\nFiles saved to output/:")
        print(f"  - {html_path} (dashboard with {len(processed_df)} expenses)")
        print(f"  - {json_path} (full backup: {len(raw_df)} records)")
        print(f"  - {csv_path} (full backup: {len(raw_df)} records)")
        print(f"\nOpen the dashboard: open {html_path}")
        return
    
    # Cloud mode: use temp files
    temp_files, json_path, csv_path, html_path = create_temp_files(raw_df)
    
    try:
        # Generate dashboard with processed data
        dashboard.generate(processed_df, html_path)
        print(f"Generated dashboard with {len(processed_df)} expenses")
        
        # Upload to Google Drive
        if not args.no_upload:
            if gdrive_config.is_configured:
                files_to_upload = [
                    (json_path, "expenses.json"),
                    (csv_path, "expenses.csv"),
                    (html_path, "expenses_dashboard.html"),
                ]
                gdrive.upload_files(files_to_upload, timestamp)
            else:
                print("Google Drive not configured - skipping upload")
        else:
            print("Google Drive upload skipped (--no-upload flag)")
        
        # Send email
        if args.email:
            if email_config.is_configured:
                email_sender.send_dashboard(html_path)
            else:
                print("Email not configured - skipping")
    
    finally:
        cleanup_temp_files(temp_files)


if __name__ == "__main__":
    main()

