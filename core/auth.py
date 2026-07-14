"""Google OAuth authentication — handles first-time browser login and token refresh."""
import json
import os
from pathlib import Path

from dotenv import load_dotenv
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow

load_dotenv()

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
    "https://www.googleapis.com/auth/documents",
]

TOKEN_PATH       = Path(__file__).parent.parent / "token.json"
CREDENTIALS_PATH = Path(__file__).parent.parent / "credentials.json"


def get_credentials():
    """
    Return valid Google credentials.

    Priority order:
    1. GOOGLE_REFRESH_TOKEN env var — builds credentials directly from .env
       (used when the content-automation OAuth app credentials are in .env)
    2. token.json — cached credentials from a previous browser login
    3. credentials.json + browser OAuth flow — first-time setup fallback
    """
    # ── 1. Env-var credentials (content-automation OAuth app) ────────────────
    refresh_token = os.getenv("GOOGLE_REFRESH_TOKEN")
    client_id     = os.getenv("GOOGLE_CLIENT_ID")
    client_secret = os.getenv("GOOGLE_CLIENT_SECRET")
    token_uri     = os.getenv("GOOGLE_TOKEN_URI", "https://oauth2.googleapis.com/token")

    if refresh_token and client_id and client_secret:
        creds = Credentials(
            token=None,
            refresh_token=refresh_token.strip("'"),
            token_uri=token_uri,
            client_id=client_id,
            client_secret=client_secret,
            scopes=SCOPES,
        )
        creds.refresh(Request())
        return creds

    # ── 2. Cached token.json ──────────────────────────────────────────────────
    creds = None
    if TOKEN_PATH.exists():
        with open(TOKEN_PATH) as f:
            token_data = json.load(f)
        creds = Credentials(
            token=token_data.get("token"),
            refresh_token=token_data.get("refresh_token"),
            token_uri=token_data.get("token_uri"),
            client_id=token_data.get("client_id"),
            client_secret=token_data.get("client_secret"),
            scopes=token_data.get("scopes"),
        )

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            # ── 3. Browser OAuth flow ─────────────────────────────────────────
            if not CREDENTIALS_PATH.exists():
                raise FileNotFoundError(
                    "No GOOGLE_REFRESH_TOKEN in .env and no credentials.json found.\n"
                    "Either add GOOGLE_REFRESH_TOKEN / GOOGLE_CLIENT_ID / GOOGLE_CLIENT_SECRET "
                    "to .env, or place credentials.json in the project root."
                )
            flow = InstalledAppFlow.from_client_secrets_file(str(CREDENTIALS_PATH), SCOPES)
            creds = flow.run_local_server(port=0)
        with open(TOKEN_PATH, "w") as f:
            json.dump({
                "token":         creds.token,
                "refresh_token": creds.refresh_token,
                "token_uri":     creds.token_uri,
                "client_id":     creds.client_id,
                "client_secret": creds.client_secret,
                "scopes":        creds.scopes,
            }, f)

    return creds
