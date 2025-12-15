"""Google Drive upload module - uploads files using OAuth."""

import os

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

from src.config import gdrive as config


# MIME type mapping
MIME_TYPES = {
    ".json": "application/json",
    ".csv": "text/csv",
    ".html": "text/html",
}


def upload_files(files: list[tuple[str, str]], timestamp: str) -> None:
    """Upload files to Google Drive using OAuth credentials.
    
    Args:
        files: List of tuples (local_path, desired_name) to upload.
        timestamp: Timestamp string to add to filenames (e.g., '2025-01-01').
        
    Raises:
        ValueError: If Google Drive configuration is incomplete.
        Exception: If upload fails.
    """
    if not config.is_configured:
        raise ValueError(
            "Google Drive not configured - missing GDRIVE_CLIENT_ID, "
            "GDRIVE_CLIENT_SECRET, GDRIVE_REFRESH_TOKEN, or GDRIVE_FOLDER_ID"
        )
    
    try:
        credentials = _create_credentials()
        service = build("drive", "v3", credentials=credentials)
        
        for file_path, base_name in files:
            _upload_single_file(service, file_path, base_name, timestamp)
                
    except Exception as e:
        print(f"Failed to upload to Google Drive: {e}")
        raise


def _create_credentials() -> Credentials:
    """Create and refresh OAuth credentials."""
    credentials = Credentials(
        token=None,
        refresh_token=config.refresh_token,
        token_uri="https://oauth2.googleapis.com/token",
        client_id=config.client_id,
        client_secret=config.client_secret,
        scopes=["https://www.googleapis.com/auth/drive.file"],
    )
    credentials.refresh(Request())
    return credentials


def _upload_single_file(service, file_path: str, base_name: str, timestamp: str) -> None:
    """Upload a single file to Google Drive."""
    # Build timestamped filename (date prefix)
    name_parts = os.path.splitext(base_name)
    file_name = f"{timestamp}_{name_parts[0]}{name_parts[1]}"
    
    # Determine MIME type
    extension = name_parts[1].lower()
    mime_type = MIME_TYPES.get(extension, "application/octet-stream")
    
    # Upload
    media = MediaFileUpload(file_path, mimetype=mime_type, resumable=True)
    file_metadata = {
        "name": file_name,
        "parents": [config.folder_id],
    }
    
    service.files().create(
        body=file_metadata,
        media_body=media,
        fields="id",
    ).execute()
    
    print(f"Uploaded {file_name} to Google Drive")

