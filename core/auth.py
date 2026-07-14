"""Google OAuth authentication — handles first-time browser login and token refresh."""
from pathlib import Path
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
    "https://www.googleapis.com/auth/documents",
]

TOKEN_PATH       = Path(__file__).parent.parent / "token.json"
CREDENTIALS_PATH = Path(__file__).parent.parent / "credentials.json"


def get_credentials():
    """Return valid Google credentials, triggering browser login if needed."""
    if not CREDENTIALS_PATH.exists():
        raise FileNotFoundError(
            "credentials.json not found in project root.\n"
            "Copy content_automation/content-automation-key.json here as credentials.json."
        )

    creds = None
    if TOKEN_PATH.exists():
        creds = Credentials.from_authorized_user_file(str(TOKEN_PATH), SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(str(CREDENTIALS_PATH), SCOPES)
            creds = flow.run_local_server(port=0)
        with open(TOKEN_PATH, "w") as f:
            f.write(creds.to_json())

    return creds
