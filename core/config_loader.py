"""Load and validate client configuration from clients.yaml."""
import yaml
from pathlib import Path

CONFIG_PATH = Path(__file__).parent.parent / "clients.yaml"

REQUIRED_FIELDS = [
    "name", "sheet_id", "tab_name", "drive_folder_id",
    "header_row", "data_start_row", "status_trigger", "status_done",
    "brands", "columns"
]

REQUIRED_COLUMNS = [
    "website", "status", "bl_type", "language", "title", "anchor", "content"
]


def load_clients():
    if not CONFIG_PATH.exists():
        raise FileNotFoundError(
            "clients.yaml not found. Run python setup_client.py to configure your first client."
        )
    with open(CONFIG_PATH, "r") as f:
        data = yaml.safe_load(f)
    clients = data.get("clients", {})
    if not clients:
        raise ValueError("clients.yaml has no clients configured. Run python setup_client.py.")
    return clients


def get_client(client_id):
    clients = load_clients()
    if client_id not in clients:
        raise KeyError(f"Client '{client_id}' not found in clients.yaml.")
    client = clients[client_id]
    _validate_client(client_id, client)
    return client


def _validate_client(client_id, client):
    for field in REQUIRED_FIELDS:
        if field not in client:
            raise ValueError(f"clients.yaml: client '{client_id}' is missing required field '{field}'.")
    for col in REQUIRED_COLUMNS:
        if col not in client.get("columns", {}):
            raise ValueError(
                f"clients.yaml: client '{client_id}' columns section is missing required field '{col}'."
            )


def list_client_names():
    """Return dict of {client_id: display_name} for all configured clients."""
    clients = load_clients()
    return {cid: c.get("name", cid) for cid, c in clients.items()}


def get_brands_for_client(client_id):
    client = get_client(client_id)
    return client.get("brands", [])
