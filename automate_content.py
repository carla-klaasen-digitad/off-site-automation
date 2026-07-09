"""
Off-Site Content Automation — interactive CLI.
Run: python automate_content.py
"""
from __future__ import annotations
import sys
from datetime import datetime
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich import box
from rich.prompt import Prompt, Confirm

from core.config_loader import load_clients, get_client, get_brands_for_client
from core.auth import get_credentials
from core.sheet_reader import read_pending_rows, mark_row_done
from core.content_generator import generate_article
from core.doc_writer import create_article_doc
from core.logger import get_logger
from core.month_normalizer import normalize_month

console = Console()

MONTH_NAMES = {
    1: "January", 2: "February", 3: "March", 4: "April",
    5: "May", 6: "June", 7: "July", 8: "August",
    9: "September", 10: "October", 11: "November", 12: "December"
}


# ── Banner ────────────────────────────────────────────────────────────────────

def show_banner():
    console.clear()
    clients = load_clients()

    # Build dynamic client/brand table
    client_table = Table(box=box.SIMPLE, show_header=True, header_style="bold cyan")
    client_table.add_column("Client ID", style="cyan")
    client_table.add_column("Display Name")
    client_table.add_column("Brands")

    for cid, cfg in clients.items():
        brands = cfg.get("brands", [])
        brand_str = ", ".join(brands) if brands else "(same as client)"
        client_table.add_row(cid.upper(), cfg.get("name", cid), brand_str)

    usage = (
        "[bold]How to run:[/bold] Type client IDs and brand names in [bold]ALL CAPS[/bold]. "
        "Input is [bold]not case-sensitive[/bold] — ALL, all, All all work the same.\n"
        "Month names accepted in English or French, any abbreviation (e.g. Aug, août, aug., Août)."
    )

    console.print(Panel(usage, title="[bold white]Off-Site Content Automation[/bold white]",
                        border_style="cyan", padding=(1, 2)))
    console.print(client_table)


# ── Step-by-step prompts ──────────────────────────────────────────────────────

def prompt_client(clients: dict) -> list[str]:
    """Returns list of client_ids to run."""
    client_ids = list(clients.keys())
    display = " | ".join(f"[cyan]{c.upper()}[/cyan]" for c in client_ids)
    console.print(f"\nAvailable clients: {display} | [cyan]ALL[/cyan]")
    raw = Prompt.ask("[bold]Client[/bold]").strip().lower()
    if raw == "all":
        return client_ids
    matched = [c for c in client_ids if c.replace("_", "") == raw.replace("_", "").replace(" ", "")]
    if not matched:
        console.print(f"[red]Client '{raw}' not found. Check clients.yaml.[/red]")
        sys.exit(1)
    return matched


def prompt_brand(client_ids: list[str], clients: dict) -> dict[str, str | None]:
    """Returns {client_id: brand_filter | None}."""
    result = {}
    for cid in client_ids:
        brands = clients[cid].get("brands", [])
        if not brands:
            result[cid] = None
            continue
        display = " | ".join(f"[cyan]{b.upper()}[/cyan]" for b in brands)
        console.print(f"\n[bold]{clients[cid]['name']}[/bold] brands: {display} | [cyan]ALL[/cyan]")
        raw = Prompt.ask("[bold]Brand[/bold] (or ALL)").strip().lower()
        if raw == "all":
            result[cid] = None
        else:
            matched = next((b for b in brands if b.lower().replace(" ", "") == raw.replace(" ", "")), None)
            if not matched:
                console.print(f"[red]Brand '{raw}' not found for {clients[cid]['name']}.[/red]")
                sys.exit(1)
            result[cid] = matched
    return result


def prompt_month() -> int | None:
    """Returns month number (1-12) or None for all months."""
    raw = Prompt.ask("[bold]Month[/bold] (or ALL)", default="ALL").strip()
    if raw.upper() == "ALL":
        return None
    month_num = normalize_month(raw)
    if month_num is None:
        console.print(f"[red]'{raw}' is not a recognised month name. Try 'August', 'août', 'Aug', etc.[/red]")
        sys.exit(1)
    return month_num


def prompt_year() -> int | None:
    """Returns year or None to default to current year."""
    current = datetime.now().year
    raw = Prompt.ask(f"[bold]Year[/bold] (or ALL, default {current})", default=str(current)).strip()
    if raw.upper() == "ALL":
        return None
    try:
        return int(raw)
    except ValueError:
        console.print(f"[red]'{raw}' is not a valid year.[/red]")
        sys.exit(1)


# ── Preview ───────────────────────────────────────────────────────────────────

def show_preview(run_plan: list[dict]) -> bool:
    """Display a summary of rows that would be generated and ask for confirmation."""
    if not run_plan:
        console.print("\n[yellow]No rows match the selected filters. Nothing to generate.[/yellow]")
        return False

    total = sum(len(r["rows"]) for r in run_plan)
    console.print(f"\n[bold]Preview — {total} row(s) to generate:[/bold]")

    preview_table = Table(box=box.SIMPLE, show_header=True, header_style="bold")
    preview_table.add_column("Client")
    preview_table.add_column("Brand")
    preview_table.add_column("Month")
    preview_table.add_column("Title", no_wrap=False, max_width=50)

    for entry in run_plan:
        for row in entry["rows"]:
            preview_table.add_row(
                entry["client_name"],
                row["website"],
                row.get("month", "—"),
                row["title"]
            )

    console.print(preview_table)
    return Confirm.ask(f"\nGenerate [bold]{total}[/bold] article(s)?")


# ── Runner ────────────────────────────────────────────────────────────────────

def run_client(creds, client_id: str, client_cfg: dict, rows: list[dict]):
    logger = get_logger(client_id)
    drive_folder_id = client_cfg["drive_folder_id"]
    success = 0
    skipped = 0

    for row in rows:
        row_label = f"Row {row['row_num']} | {row['website']} | {row['title'][:60]}"
        console.print(f"  Generating: [dim]{row_label}[/dim]")
        try:
            article = generate_article(row, client_cfg)
            doc_url = create_article_doc(creds, row["title"], article, drive_folder_id)
            mark_row_done(creds, client_cfg, row["row_num"], doc_url)
            logger.info(f"OK   row={row['row_num']} brand={row['website']} title={row['title']} url={doc_url}")
            console.print(f"  [green]Done[/green] → {doc_url}")
            success += 1
        except FileNotFoundError as e:
            msg = f"SKIP row={row['row_num']} — guidelines not found: {e}"
            logger.warning(msg)
            console.print(f"  [yellow]Skipped[/yellow] — {e}")
            skipped += 1
        except Exception as e:
            msg = f"FAIL row={row['row_num']} brand={row['website']} — {e}"
            logger.error(msg)
            console.print(f"  [red]Failed[/red] — {e}")
            skipped += 1

    return success, skipped


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    try:
        clients = load_clients()
    except FileNotFoundError as e:
        console.print(f"[red]{e}[/red]")
        sys.exit(1)

    show_banner()

    selected_clients = prompt_client(clients)
    brand_filters = prompt_brand(selected_clients, clients)
    month_filter = prompt_month()
    year_filter = prompt_year()

    # Authenticate once for all clients
    console.print("\n[dim]Authenticating with Google...[/dim]")
    try:
        creds = get_credentials()
    except FileNotFoundError as e:
        console.print(f"[red]{e}[/red]")
        sys.exit(1)

    # Collect all matching rows for preview
    run_plan = []
    for client_id in selected_clients:
        client_cfg = get_client(client_id)
        brand_filter = brand_filters.get(client_id)
        rows = read_pending_rows(creds, client_cfg, brand_filter, month_filter, year_filter)
        if rows:
            run_plan.append({
                "client_id": client_id,
                "client_name": client_cfg["name"],
                "client_cfg": client_cfg,
                "rows": rows,
            })

    confirmed = show_preview(run_plan)
    if not confirmed:
        console.print("[dim]Cancelled.[/dim]")
        return

    # Run
    console.print()
    total_success = 0
    total_skipped = 0
    for entry in run_plan:
        console.print(f"[bold cyan]{entry['client_name']}[/bold cyan]")
        s, sk = run_client(creds, entry["client_id"], entry["client_cfg"], entry["rows"])
        total_success += s
        total_skipped += sk

    console.print(
        f"\n[bold]Done.[/bold] {total_success} generated, {total_skipped} skipped. "
        f"See logs/ for details."
    )


if __name__ == "__main__":
    main()
