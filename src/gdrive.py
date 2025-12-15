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


def upload_files(files: list[tuple[str, str]], timestamp: str) -> dict[str, str]:
    """Upload files to Google Drive using OAuth credentials.
    
    Args:
        files: List of tuples (local_path, desired_name) to upload.
        timestamp: Timestamp string to add to filenames (e.g., '2025-01-01').
        
    Returns:
        Dictionary mapping base_name (without extension) to file_id.
        Example: {'expenses': 'abc123', 'expenses_dashboard': 'xyz789'}
        
    Raises:
        ValueError: If Google Drive configuration is incomplete.
        Exception: If upload fails.
    """
    if not config.is_configured:
        raise ValueError(
            "Google Drive not configured - missing GDRIVE_CLIENT_ID, "
            "GDRIVE_CLIENT_SECRET, GDRIVE_REFRESH_TOKEN, or GDRIVE_FOLDER_ID"
        )
    
    file_ids = {}
    
    try:
        credentials = _create_credentials()
        service = build("drive", "v3", credentials=credentials)
        
        for file_path, base_name in files:
            file_id = _upload_single_file(service, file_path, base_name, timestamp)
            # Use base name without extension as key
            key = os.path.splitext(base_name)[0]
            file_ids[key] = file_id
                
    except Exception as e:
        print(f"Failed to upload to Google Drive: {e}")
        raise
    
    return file_ids


def share_with_emails(file_id: str, emails: list[str]) -> None:
    """Share a file with specific email addresses (viewer permission).
    
    Args:
        file_id: The Google Drive file ID to share.
        emails: List of email addresses to grant view access.
        
    Raises:
        ValueError: If Google Drive configuration is incomplete.
    """
    if not config.is_configured:
        raise ValueError("Google Drive not configured")
    
    credentials = _create_credentials()
    service = build("drive", "v3", credentials=credentials)
    
    for email in emails:
        permission = {
            "type": "user",
            "role": "reader",
            "emailAddress": email.strip(),
        }
        
        try:
            service.permissions().create(
                fileId=file_id,
                body=permission,
                sendNotificationEmail=False,  # Don't send Google's default notification
            ).execute()
            print(f"Shared file with {email}")
        except Exception as e:
            print(f"Warning: Could not share with {email}: {e}")


def get_view_link(file_id: str) -> str:
    """Get the shareable view link for a file.
    
    Args:
        file_id: The Google Drive file ID.
        
    Returns:
        URL to view the file in Google Drive.
    """
    return f"https://drive.google.com/file/d/{file_id}/view"


def get_service():
    """Get an authenticated Google Drive service instance.
    
    Returns:
        Google Drive API service object.
        
    Raises:
        ValueError: If Google Drive configuration is incomplete.
    """
    if not config.is_configured:
        raise ValueError("Google Drive not configured")
    
    credentials = _create_credentials()
    return build("drive", "v3", credentials=credentials)


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


def _upload_single_file(service, file_path: str, base_name: str, timestamp: str) -> str:
    """Upload a single file to Google Drive.
    
    Args:
        service: Google Drive API service object.
        file_path: Local path to the file.
        base_name: Desired filename (e.g., 'expenses.json').
        timestamp: Date string to prefix filename.
        
    Returns:
        The file ID of the uploaded file.
    """
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
    
    result = service.files().create(
        body=file_metadata,
        media_body=media,
        fields="id",
    ).execute()
    
    file_id = result.get("id")
    print(f"Uploaded {file_name} to Google Drive")
    
    return file_id
