# Standard python libs
import errno
import os
import tempfile
from enum import Enum
from typing import IO, Mapping, Optional, Sequence

# Common PyPI libs
import requests

# Main Google client library
from googleapiclient.discovery import build as google_service_build
from googleapiclient.http import MediaIoBaseDownload

# For OAuth2
SCOPES: Optional[Sequence[str]] = None
try:
    # No stubs for these in google-api-python-client-stubs
    from google.auth.transport.requests import Request  # type: ignore
    from google.oauth2.credentials import Credentials  # type: ignore
    from google_auth_oauthlib.flow import InstalledAppFlow  # type: ignore

    SCOPES = [
        "https://www.googleapis.com/auth/drive.readonly",
        "https://www.googleapis.com/auth/drive.metadata.readonly",
    ]
except ImportError:
    pass

# Local libs
from .state import read_json, state_path


class MediaType(Enum):
    def __new__(cls, *args):
        value = len(cls.__members__) + 1
        obj = object.__new__(cls)
        obj._value_ = value
        return obj

    def __init__(self, mimeType: str, extension: str):
        self.mimeType = mimeType
        self.extension = extension

    PDF = ("application/pdf", ".pdf")
    SVG = ("image/svg+xml", ".svg")
    PNG = ("image/png", ".png")
    JPEG = ("image/jpeg", ".jpg")


class GoogleDrive:
    """Get map drawing metadata and content from Google Drive"""

    # The google drive API object
    _drive = None

    def __init__(self, fileId: str):
        self.fileId = fileId

    @classmethod
    def _get_drive(cls):  # by inference, -> DriveResource:
        SERVICE = "drive"
        VERSION = "v3"

        if cls._drive is None:
            creds = None
            if SCOPES is not None:
                token_path = state_path("google_token.json")
                if os.path.exists(token_path):
                    creds = Credentials.from_authorized_user_file(token_path, SCOPES)
                if not creds or not creds.valid:
                    if creds and creds.expired and creds.refresh_token:
                        creds.refresh(Request())
            if not creds or not creds.valid:
                api_cfg = read_json("google_api")
                if "api_key" in api_cfg:
                    cls._drive = google_service_build(
                        SERVICE, VERSION, developerKey=api_cfg["api_key"]
                    )
                elif SCOPES is not None:
                    ip = requests.get("https://checkip.amazonaws.com").text.strip()
                    flow = InstalledAppFlow.from_client_config(api_cfg, SCOPES)
                    try:
                        creds = flow.run_local_server(ip, 0)
                    except OSError as e:
                        if e.errno == errno.EADDRNOTAVAIL:
                            # fall back to localhost, user might have to fiddle last browser redirect
                            creds = flow.run_local_server(port=0)
                        else:
                            raise
            if creds:
                with open(token_path, "w") as f:
                    f.write(creds.to_json())
                if creds.valid:
                    cls._drive = google_service_build(
                        SERVICE, VERSION, credentials=creds
                    )

        assert cls._drive is not None
        return cls._drive

    def stat(self) -> Mapping[str, str]:
        drive = self._get_drive()
        return (
            drive.files()
            .get(fileId=self.fileId, fields="id, name, mimeType, modifiedTime")
            .execute()
        )

    def export(
        self, mediaType: MediaType, file: Optional[IO[bytes]] = None
    ) -> IO[bytes]:
        drive = self._get_drive()
        request = drive.files().export_media(
            fileId=self.fileId, mimeType=mediaType.mimeType
        )
        if file is None:
            file = tempfile.NamedTemporaryFile(suffix=mediaType.extension)
        assert file is not None

        done = False
        download = MediaIoBaseDownload(file, request)
        while done is False:
            _, done = download.next_chunk()
        return file
