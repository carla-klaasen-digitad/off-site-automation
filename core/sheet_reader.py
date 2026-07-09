"""Read and update rows in a Google Sheet."""
from googleapiclient.discovery import build
from core.month_normalizer import month_matches


def get_sheets_service(creds):
    return build("sheets", "v4", credentials=creds)


def col_letter_to_index(letter: str) -> int:
    """Convert column letter (A, B, ... Z, AA, ...) to zero-based index."""
    letter = letter.upper().strip()
    result = 0
    for char in letter:
        result = result * 26 + (ord(char) - ord("A") + 1)
    return result - 1


def read_pending_rows(creds, client: dict, filter_brand: str = None,
                      filter_month: int = None, filter_year: int = None) -> list[dict]:
    """
    Return all rows that match the run conditions:
    - status column == status_trigger
    - content column is empty (no existing Doc URL)
    - optionally filtered by brand, month, year
    """
    service = get_sheets_service(creds)
    cols = client["columns"]

    range_name = f"'{client['tab_name']}'!A{client['header_row']}:ZZ"
    result = service.spreadsheets().values().get(
        spreadsheetId=client["sheet_id"],
        range=range_name
    ).execute()
    all_rows = result.get("values", [])
    if not all_rows:
        return []

    data_rows = all_rows[client["data_start_row"] - client["header_row"]:]

    def cell(row, col_letter):
        idx = col_letter_to_index(col_letter)
        if idx < len(row):
            return str(row[idx]).strip()
        return ""

    pending = []
    for row_num, row in enumerate(data_rows, start=client["data_start_row"]):
        status = cell(row, cols["status"])
        content_val = cell(row, cols["content"])
        title = cell(row, cols["title"])
        anchor = cell(row, cols["anchor"])

        # Skip rows not triggered or already done
        if status.lower() != client["status_trigger"].lower():
            continue
        if content_val:
            continue
        # Title and anchor are required to run
        if not title or not anchor:
            continue

        website = cell(row, cols["website"])
        language = cell(row, cols.get("language", ""))
        bl_type = cell(row, cols.get("bl_type", ""))
        target_url = cell(row, cols.get("target_url", ""))
        month_val = cell(row, cols.get("month", "")) if cols.get("month") else ""
        year_val = cell(row, cols.get("year", "")) if cols.get("year") else ""

        # Brand filter
        if filter_brand and website.lower().replace(" ", "") != filter_brand.lower().replace(" ", ""):
            continue

        # Month filter
        if filter_month and month_val:
            if not month_matches(month_val, filter_month):
                continue

        # Year filter
        if filter_year and year_val:
            try:
                if int(year_val) != filter_year:
                    continue
            except ValueError:
                pass

        pending.append({
            "row_num": row_num,
            "website": website,
            "title": title,
            "anchor": anchor,
            "target_url": target_url,
            "bl_type": bl_type,
            "language": language,
            "month": month_val,
            "year": year_val,
        })

    return pending


def mark_row_done(creds, client: dict, row_num: int, doc_url: str):
    """Write Doc URL to content column and update status to done."""
    service = get_sheets_service(creds)
    cols = client["columns"]
    sheet_id = client["sheet_id"]
    tab = client["tab_name"]

    content_range = f"'{tab}'!{cols['content']}{row_num}"
    status_range = f"'{tab}'!{cols['status']}{row_num}"

    service.spreadsheets().values().update(
        spreadsheetId=sheet_id, range=content_range,
        valueInputOption="RAW", body={"values": [[doc_url]]}
    ).execute()
    service.spreadsheets().values().update(
        spreadsheetId=sheet_id, range=status_range,
        valueInputOption="RAW", body={"values": [[client["status_done"]]]}
    ).execute()
