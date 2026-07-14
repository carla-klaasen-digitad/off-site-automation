"""Create formatted Google Docs from generated article content."""
import os
import re

import anthropic
import requests
from dotenv import load_dotenv
from googleapiclient.discovery import build

load_dotenv()

COMBINED_RE = re.compile(r'\[([^\]]+)\]\(([^)]+)\)|\*\*([^\*]+)\*\*')
META_LINE_RE = re.compile(r'^(Meta-title|Meta-description|Méta-titre|Méta-description)', re.IGNORECASE)


def get_docs_service(creds):
    return build("docs", "v1", credentials=creds)


def get_drive_service(creds):
    return build("drive", "v3", credentials=creds)


# ── Unsplash ──────────────────────────────────────────────────────────────────

def _image_search_query(title: str, content: str) -> str:
    client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
    preview = content[:2000] if content else title
    msg = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=25,
        messages=[{"role": "user", "content": (
            "Generate a 2-4 word Unsplash image search query for the article below. "
            "Pick a concrete, photogenic subject (e.g. 'morning yogurt bowl', "
            "'family breakfast table', 'woman stretching morning') that visually "
            "represents the article's main theme — not an abstract concept. "
            f"Return only the search query, nothing else.\n\nHeading: {title}\n\nArticle excerpt:\n{preview}"
        )}]
    )
    return msg.content[0].text.strip().strip('"')


def _fetch_unsplash_image(title: str, content: str):
    """Returns (image_url, page_url) or (None, None)."""
    api_key = os.getenv("UNSPLASH_ACCESS_KEY")
    if not api_key:
        return None, None
    try:
        query = _image_search_query(title, content)
    except Exception:
        query = " ".join(title.split()[:4])
    try:
        resp = requests.get(
            "https://api.unsplash.com/search/photos",
            params={"query": query, "per_page": 1, "orientation": "landscape", "content_filter": "high"},
            headers={"Authorization": f"Client-ID {api_key}"},
            timeout=10
        )
        if resp.status_code != 200:
            return None, None
        results = resp.json().get("results", [])
        if not results:
            return None, None
        photo = results[0]
        return photo["urls"]["regular"], photo["links"]["html"]
    except Exception:
        return None, None


# ── Content parser ────────────────────────────────────────────────────────────

def _split_content(content: str) -> tuple:
    """
    Separate meta lines (Meta-title, Meta-description) from the article body.
    Returns (meta_lines: list[str], body_lines: list[str]).
    """
    lines = content.split("\n")
    meta_lines = []
    body_start = 0
    for i, line in enumerate(lines):
        if META_LINE_RE.match(line.strip()):
            meta_lines.append(line.strip())
            body_start = i + 1
        elif not line.strip() and i <= len(meta_lines) + 1:
            body_start = i + 1  # skip blank line after meta block
        elif meta_lines:
            break  # first non-blank, non-meta line after meta block
    return meta_lines, lines[body_start:]


def _parse_inline(line: str, segments: list):
    """Append inline-parsed segments (links, bold, normal) for one line."""
    last_end = 0
    for m in COMBINED_RE.finditer(line):
        if m.start() > last_end:
            segments.append({"type": "normal", "text": line[last_end:m.start()], "url": None})
        if m.group(0).startswith("["):
            segments.append({"type": "link", "text": m.group(1), "url": m.group(2)})
        else:
            segments.append({"type": "bold", "text": m.group(3), "url": None})
        last_end = m.end()
    if last_end < len(line):
        segments.append({"type": "normal", "text": line[last_end:], "url": None})
    segments.append({"type": "normal", "text": "\n", "url": None})


def _build_segments(title: str, meta_lines: list, body_lines: list) -> tuple:
    """
    Build segment list in display order:
      1. Meta-title (bold label)
      2. Meta-description (bold label)
      3. Blank line
      4. [image placeholder — caller inserts image here]
      5. H1 title
      6. Article body

    Returns (segments, meta_block_char_len) so the caller knows where to insert the image.
    """
    segments = []
    meta_char_len = 0

    # 1–2. Meta block (bold)
    for line in meta_lines:
        segments.append({"type": "bold",   "text": line, "url": None})
        segments.append({"type": "normal", "text": "\n",  "url": None})
        meta_char_len += len(line) + 1  # +1 for \n

    # 3. Blank line after meta block
    if meta_lines:
        segments.append({"type": "normal", "text": "\n", "url": None})
        meta_char_len += 1

    # Image goes here — caller uses meta_char_len+1 as the insertion index

    # 4. H1 title
    segments.append({"type": "h1",     "text": title, "url": None})
    segments.append({"type": "normal", "text": "\n",  "url": None})

    # 5. Article body
    for line in body_lines:
        if line.startswith("## "):
            segments.append({"type": "h2",     "text": line[3:].strip(), "url": None})
            segments.append({"type": "normal", "text": "\n",             "url": None})
        elif line.startswith("# "):
            segments.append({"type": "h1",     "text": line[2:].strip(), "url": None})
            segments.append({"type": "normal", "text": "\n",             "url": None})
        else:
            _parse_inline(line, segments)

    return segments, meta_char_len


# ── Doc creation ──────────────────────────────────────────────────────────────

def create_article_doc(creds, title: str, content: str, drive_folder_id: str) -> str:
    """
    Create a Google Doc with this structure:
      Meta-title (bold) / Meta-description (bold) / blank line / image / H1 title / body.
    Hyperlinks, Poppins font, and Unsplash attribution are applied.
    Returns the Doc URL.
    """
    docs  = get_docs_service(creds)
    drive = get_drive_service(creds)

    # supportsAllDrives=True is required for Google Workspace Shared Drives;
    # harmless on regular My Drive folders.
    doc = drive.files().create(
        body={
            "name": title,
            "mimeType": "application/vnd.google-apps.document",
            "parents": [drive_folder_id]
        },
        supportsAllDrives=True
    ).execute()
    doc_id = doc["id"]

    # Split content into meta block + article body
    meta_lines, body_lines = _split_content(content)

    # Build segments and get meta block length for image placement
    segments, meta_block_len = _build_segments(title, meta_lines, body_lines)

    # Build full text string + character ranges
    full_text = ""
    ranges    = []
    for seg in segments:
        start = len(full_text)
        full_text += seg["text"]
        ranges.append((start, len(full_text), seg["type"], seg.get("url")))

    # Insert all text at once
    docs.documents().batchUpdate(
        documentId=doc_id,
        body={"requests": [{"insertText": {"location": {"index": 1}, "text": full_text}}]}
    ).execute()

    # Apply paragraph and text styles
    style_requests = []
    for (start, end, seg_type, url) in ranges:
        if not full_text[start:end].strip():
            continue
        doc_start = start + 1
        doc_end   = end   + 1

        if seg_type in ("h1", "h2"):
            style_requests.append({"updateParagraphStyle": {
                "range": {"startIndex": doc_start, "endIndex": doc_end},
                "paragraphStyle": {"namedStyleType": f"HEADING_{1 if seg_type == 'h1' else 2}"},
                "fields": "namedStyleType"
            }})
        elif seg_type == "bold":
            style_requests.append({"updateTextStyle": {
                "range": {"startIndex": doc_start, "endIndex": doc_end},
                "textStyle": {"bold": True},
                "fields": "bold"
            }})
        elif seg_type == "link" and url:
            style_requests.append({"updateTextStyle": {
                "range": {"startIndex": doc_start, "endIndex": doc_end},
                "textStyle": {
                    "link": {"url": url},
                    "foregroundColor": {"color": {"rgbColor": {"red": 0.07, "green": 0.36, "blue": 0.72}}},
                    "underline": True
                },
                "fields": "link,foregroundColor,underline"
            }})

    if style_requests:
        docs.documents().batchUpdate(documentId=doc_id, body={"requests": style_requests}).execute()

    # Apply Poppins font to entire document
    docs.documents().batchUpdate(
        documentId=doc_id,
        body={"requests": [{"updateTextStyle": {
            "range": {"startIndex": 1, "endIndex": len(full_text) + 1},
            "textStyle": {"weightedFontFamily": {"fontFamily": "Poppins", "weight": 400}},
            "fields": "weightedFontFamily"
        }}]}
    ).execute()

    # Fetch and insert Unsplash image after meta block + blank line (before H1)
    image_url, page_url = _fetch_unsplash_image(title, content)
    if image_url:
        try:
            image_index = meta_block_len + 1  # 1-based; right after meta block + blank line
            docs.documents().batchUpdate(
                documentId=doc_id,
                body={"requests": [{"insertInlineImage": {
                    "location": {"index": image_index},
                    "uri": image_url,
                    "objectSize": {
                        "height": {"magnitude": 300, "unit": "PT"},
                        "width":  {"magnitude": 450, "unit": "PT"}
                    }
                }}]}
            ).execute()

            if page_url:
                attr_label = "View photo on Unsplash"
                attr_text  = "\n" + attr_label + "\n"
                attr_index = image_index + 1
                docs.documents().batchUpdate(
                    documentId=doc_id,
                    body={"requests": [{"insertText": {
                        "location": {"index": attr_index}, "text": attr_text
                    }}]}
                ).execute()
                link_start = attr_index + 1
                link_end   = link_start + len(attr_label)
                docs.documents().batchUpdate(
                    documentId=doc_id,
                    body={"requests": [{"updateTextStyle": {
                        "range": {"startIndex": link_start, "endIndex": link_end},
                        "textStyle": {
                            "link": {"url": page_url},
                            "foregroundColor": {"color": {"rgbColor": {"red": 0.07, "green": 0.36, "blue": 0.72}}},
                            "underline": True,
                            "fontSize": {"magnitude": 9, "unit": "PT"}
                        },
                        "fields": "link,foregroundColor,underline,fontSize"
                    }}]}
                ).execute()
        except Exception:
            pass  # Doc is still complete without image

    return f"https://docs.google.com/document/d/{doc_id}/edit"
