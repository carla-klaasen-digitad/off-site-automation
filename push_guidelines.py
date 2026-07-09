"""
Push brand writing guidelines into the Danone USA Content Rules Google Doc.

Usage:
  python push_guidelines.py --client danone_usa --brand oikos
  python push_guidelines.py --client danone_usa --brand ALL
  python push_guidelines.py --list

⚠️  This script INSERTS content — it does not replace.
    Clear the existing brand section in the Google Doc before re-running,
    or you will get duplicates.
"""
import argparse
import sys
from pathlib import Path
from rich.console import Console
from rich.prompt import Confirm

from core.auth import get_credentials
from core.config_loader import load_clients

console = Console()

GUIDELINES_DIR = Path("guidelines")

# ── Google Doc ID for each client's Content Rules doc ─────────────────────────
# Add entries here as new clients are added.
CONTENT_RULES_DOC = {
    "danone_usa": "1bkyrpZWU2I2arZa6YER9iTG9dFsehkxZQ2jrRF9RsFw",
    # "danone_canada": "FILL_IN",
}

FONT = "Poppins"
FONT_SIZE = 11


def list_available(clients: dict):
    console.print("\n[bold]Available clients and brands:[/bold]")
    for cid, cfg in clients.items():
        brands = cfg.get("brands", [])
        doc_id = CONTENT_RULES_DOC.get(cid, "NOT CONFIGURED")
        console.print(f"  [cyan]{cid}[/cyan] ({cfg['name']}) — Doc ID: {doc_id[:20]}...")
        for b in brands:
            files = list(GUIDELINES_DIR.glob(f"{b}_{cfg.get('guideline_prefix', cid)}*.md"))
            status = "[green]✓[/green]" if files else "[yellow]missing[/yellow]"
            console.print(f"    {status} {b}")


def parse_guidelines_file(filepath: Path) -> list[tuple[str, str]]:
    """
    Parse a brand .md file into a CONTENT list of (text, type) tuples.
    ## headings → "header", everything else → "bullet".
    Skips the Language: line and blank lines.
    """
    content = []
    for line in filepath.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        if line.lower().startswith("language:"):
            continue
        if line.startswith("## "):
            content.append((line[3:].strip(), "header"))
        elif line.startswith("# "):
            content.append((line[2:].strip(), "header"))
        elif line.startswith("- "):
            content.append((line[2:].strip(), "bullet"))
        else:
            content.append((line, "bullet"))
    return content


def find_insert_index(doc: dict, brand_name: str) -> int | None:
    """Find insertion point after the brand's header table in the doc."""
    body = doc["body"]["content"]
    for i, elem in enumerate(body):
        if "table" not in elem:
            continue
        for row in elem["table"].get("tableRows", []):
            for cell in row.get("tableCells", []):
                for para in cell.get("content", []):
                    if "paragraph" not in para:
                        continue
                    text = "".join(
                        r.get("textRun", {}).get("content", "")
                        for r in para["paragraph"].get("elements", [])
                    )
                    if brand_name.lower() in text.lower():
                        table_end = elem.get("endIndex", 0)
                        if i + 1 < len(body):
                            return body[i + 1].get("startIndex", table_end)
                        return table_end
    return None


def push_brand(docs_service, doc_id: str, brand_display: str, content: list[tuple[str, str]]):
    """Insert brand guidelines into the Content Rules doc."""
    doc = docs_service.documents().get(documentId=doc_id).execute()
    insert_index = find_insert_index(doc, brand_display)

    if insert_index is None:
        console.print(f"  [red]ERROR[/red] Could not find '{brand_display}' header table in the doc.")
        return False

    full_text = ""
    segments = []
    for text, seg_type in content:
        start_off = len(full_text)
        full_text += text + "\n"
        segments.append((start_off, len(full_text), seg_type))

    requests = [
        {"insertText": {"location": {"index": insert_index}, "text": full_text}},
        {
            "updateTextStyle": {
                "range": {"startIndex": insert_index, "endIndex": insert_index + len(full_text)},
                "textStyle": {
                    "fontSize": {"magnitude": FONT_SIZE, "unit": "PT"},
                    "weightedFontFamily": {"fontFamily": FONT},
                    "bold": False,
                },
                "fields": "fontSize,weightedFontFamily,bold",
            }
        },
    ]

    for start_off, end_off, seg_type in segments:
        abs_s = insert_index + start_off
        abs_e = insert_index + end_off
        if seg_type == "header":
            requests.append({"deleteParagraphBullets": {"range": {"startIndex": abs_s, "endIndex": abs_e}}})
            requests.append({"updateTextStyle": {
                "range": {"startIndex": abs_s, "endIndex": abs_e - 1},
                "textStyle": {"bold": True}, "fields": "bold"
            }})
        else:
            requests.append({"createParagraphBullets": {
                "range": {"startIndex": abs_s, "endIndex": abs_e},
                "bulletPreset": "BULLET_DISC_CIRCLE_SQUARE"
            }})

    docs_service.documents().batchUpdate(documentId=doc_id, body={"requests": requests}).execute()
    return True


def main():
    parser = argparse.ArgumentParser(description="Push brand guidelines to Content Rules Google Doc.")
    parser.add_argument("--client", help="Client ID (e.g. danone_usa)")
    parser.add_argument("--brand", help="Brand ID or ALL")
    parser.add_argument("--list", action="store_true", help="List available clients and brands")
    args = parser.parse_args()

    clients = load_clients()

    if args.list:
        list_available(clients)
        return

    if not args.client or not args.brand:
        console.print("[red]Usage: python push_guidelines.py --client danone_usa --brand oikos[/red]")
        console.print("       python push_guidelines.py --list")
        sys.exit(1)

    client_id = args.client.lower()
    if client_id not in clients:
        console.print(f"[red]Client '{client_id}' not in clients.yaml.[/red]")
        sys.exit(1)

    if client_id not in CONTENT_RULES_DOC:
        console.print(f"[red]No Content Rules Doc ID configured for '{client_id}'. Add it to CONTENT_RULES_DOC in this script.[/red]")
        sys.exit(1)

    client_cfg = clients[client_id]
    doc_id = CONTENT_RULES_DOC[client_id]
    prefix = client_cfg.get("guideline_prefix", client_id)
    all_brands = client_cfg.get("brands", [])

    target_brands = all_brands if args.brand.lower() == "all" else [args.brand.lower()]

    console.print(f"\n[bold]Client:[/bold] {client_cfg['name']}")
    console.print(f"[bold]Brands to push:[/bold] {', '.join(target_brands)}")
    console.print(f"[yellow]⚠️  Remember: this INSERTS content. Clear existing sections in the doc first if refreshing.[/yellow]")

    if not Confirm.ask("Proceed?"):
        console.print("[dim]Cancelled.[/dim]")
        return

    creds = get_credentials()
    from googleapiclient.discovery import build
    docs_service = build("docs", "v1", credentials=creds)

    for brand in target_brands:
        # Try EN file first, then FR, then any match
        candidates = list(GUIDELINES_DIR.glob(f"{brand}_{prefix}_*.md"))
        if not candidates:
            console.print(f"  [yellow]Skipped[/yellow] {brand} — no guidelines file found (expected guidelines/{brand}_{prefix}_en.md)")
            continue

        for filepath in candidates:
            brand_display = brand.replace("_", " ").title()
            console.print(f"  Pushing [cyan]{brand_display}[/cyan] from {filepath.name}...")
            content = parse_guidelines_file(filepath)
            ok = push_brand(docs_service, doc_id, brand_display, content)
            if ok:
                console.print(f"  [green]Done[/green] — {len(content)} segments inserted.")

    console.print("\n[bold]Push complete.[/bold]")


if __name__ == "__main__":
    main()
