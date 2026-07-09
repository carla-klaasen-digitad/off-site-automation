"""
Setup wizard — add a new client to clients.yaml.
Run: python setup_client.py
"""
import re
import sys
from pathlib import Path
import yaml
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt, Confirm

from core.auth import get_credentials

console = Console()
CONFIG_PATH = Path("clients.yaml")


def extract_id_from_url(url: str, pattern: str) -> str | None:
    match = re.search(pattern, url)
    return match.group(1) if match else None


def extract_sheet_id(url: str) -> str | None:
    return extract_id_from_url(url, r"/spreadsheets/d/([a-zA-Z0-9_-]+)")


def extract_drive_folder_id(url: str) -> str | None:
    return extract_id_from_url(url, r"/folders/([a-zA-Z0-9_-]+)")


def load_existing_config() -> dict:
    if CONFIG_PATH.exists():
        with open(CONFIG_PATH) as f:
            data = yaml.safe_load(f) or {}
        return data.get("clients", {})
    return {}


def save_config(clients: dict):
    CONFIG_PATH.write_text(
        yaml.dump({"clients": clients}, allow_unicode=True, default_flow_style=False, sort_keys=False),
        encoding="utf-8"
    )


def main():
    console.clear()
    console.print(Panel(
        "[bold]Add a new client to off-site content automation.[/bold]\n"
        "You will need:\n"
        "  • The Google Sheet URL\n"
        "  • The Google Drive folder URL (where Docs will be saved)\n"
        "  • Your credentials.json file in this folder",
        title="[bold white]Client Setup Wizard[/bold white]",
        border_style="cyan", padding=(1, 2)
    ))

    # ── Client ID ──
    client_id = Prompt.ask("\n[bold]Client ID[/bold] (lowercase, no spaces, e.g. danone_usa)").strip().lower().replace(" ", "_")
    existing = load_existing_config()
    if client_id in existing:
        if not Confirm.ask(f"[yellow]'{client_id}' already exists. Overwrite?[/yellow]"):
            console.print("[dim]Cancelled.[/dim]")
            sys.exit(0)

    display_name = Prompt.ask("[bold]Client display name[/bold] (e.g. Danone USA)").strip()

    # ── Sheet ──
    console.print("\n[dim]Paste the full Google Sheet URL (the one from your browser).[/dim]")
    sheet_url = Prompt.ask("[bold]Google Sheet URL[/bold]").strip()
    sheet_id = extract_sheet_id(sheet_url)
    if not sheet_id:
        console.print("[red]Could not extract Sheet ID from that URL. Make sure it's a full Google Sheets URL.[/red]")
        sys.exit(1)
    console.print(f"  [green]Sheet ID:[/green] {sheet_id}")

    tab_name = Prompt.ask("[bold]Sheet tab name[/bold] (exact name of the tab)").strip()
    header_row = int(Prompt.ask("[bold]Header row number[/bold] (row containing column headers)", default="4"))
    data_start_row = int(Prompt.ask("[bold]Data start row number[/bold] (first row of data)", default=str(header_row + 1)))

    # ── Drive folder ──
    console.print("\n[dim]Paste the full Google Drive folder URL where generated Docs should be saved.[/dim]")
    drive_url = Prompt.ask("[bold]Google Drive folder URL[/bold]").strip()
    drive_folder_id = extract_drive_folder_id(drive_url)
    if not drive_folder_id:
        console.print("[red]Could not extract folder ID from that URL. Make sure it's a folder URL (contains /folders/).[/red]")
        sys.exit(1)
    console.print(f"  [green]Folder ID:[/green] {drive_folder_id}")

    # ── Status values ──
    status_trigger = Prompt.ask("[bold]Status value that triggers a run[/bold]", default="To create").strip()
    status_done = Prompt.ask("[bold]Status value to write when done[/bold]", default="Automation Done").strip()

    # ── Guideline prefix ──
    console.print("\n[dim]The guideline prefix is used in guidelines filenames.[/dim]")
    console.print(f"[dim]Example: prefix 'danonenorthamerica' → oikos_danonenorthamerica_en.md[/dim]")
    default_prefix = client_id.replace("_", "")
    guideline_prefix = Prompt.ask("[bold]Guideline prefix[/bold]", default=default_prefix).strip().lower()

    # ── Brands ──
    console.print("\n[dim]List the brand IDs for this client (comma-separated). Leave blank if client name = brand.[/dim]")
    brands_raw = Prompt.ask("[bold]Brands[/bold]", default="").strip()
    brands = [b.strip().lower() for b in brands_raw.split(",") if b.strip()] if brands_raw else []

    # ── Column mapping ──
    console.print("\n[bold]Column mapping[/bold] — enter the column letter for each field in the sheet.")
    console.print("[dim](Press Enter to accept the default shown in brackets)[/dim]\n")
    columns = {
        "website":    Prompt.ask("  Website / Brand column", default="B").strip().upper(),
        "status":     Prompt.ask("  Status column", default="C").strip().upper(),
        "month":      Prompt.ask("  Month column", default="D").strip().upper(),
        "year":       Prompt.ask("  Year column (leave blank if not in sheet)", default="").strip().upper() or None,
        "bl_type":    Prompt.ask("  BL Type column", default="F").strip().upper(),
        "language":   Prompt.ask("  Language column", default="G").strip().upper(),
        "title":      Prompt.ask("  Title / Heading column", default="N").strip().upper(),
        "anchor":     Prompt.ask("  Anchor text column", default="O").strip().upper(),
        "target_url": Prompt.ask("  Target URL column", default="P").strip().upper(),
        "content":    Prompt.ask("  Content (Doc URL output) column", default="Q").strip().upper(),
    }
    # Remove blank optional columns
    columns = {k: v for k, v in columns.items() if v}

    # ── Google auth ──
    console.print("\n[dim]Testing Google authentication...[/dim]")
    try:
        get_credentials()
        console.print("  [green]Google authentication successful.[/green]")
    except FileNotFoundError as e:
        console.print(f"  [yellow]Warning:[/yellow] {e}")
        console.print("  [dim]You can complete setup now and add credentials.json later.[/dim]")

    # ── Save ──
    new_entry = {
        "name": display_name,
        "sheet_id": sheet_id,
        "tab_name": tab_name,
        "drive_folder_id": drive_folder_id,
        "header_row": header_row,
        "data_start_row": data_start_row,
        "status_trigger": status_trigger,
        "status_done": status_done,
        "guideline_prefix": guideline_prefix,
        "brands": brands,
        "columns": columns,
    }

    console.print(f"\n[bold]Summary:[/bold] {display_name} → Sheet {sheet_id[:20]}... | {len(brands)} brand(s)")
    if Confirm.ask("Save this client to clients.yaml?"):
        existing[client_id] = new_entry
        save_config(existing)
        console.print(f"\n[green]Saved.[/green] Run [bold]python automate_content.py[/bold] to start generating.")
        if brands:
            console.print(f"\n[dim]Remember to create guidelines files for each brand:[/dim]")
            for b in brands:
                console.print(f"  guidelines/{b}_{guideline_prefix}_en.md")
    else:
        console.print("[dim]Cancelled — nothing saved.[/dim]")


if __name__ == "__main__":
    main()
