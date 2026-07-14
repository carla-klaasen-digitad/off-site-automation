"""Create formatted Google Docs from generated article content."""
import os
import re

import anthropic
import requests
from dotenv import load_dotenv
from googleapiclient.discovery import build

load_dotenv()

COMBINED_RE = re.compile(r'\[([^\]]+)\]\(([^)]+)\)|\*\*([^\*]+)\*\*')


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

def _parse_segments(title: str, content: str) -> list:
    """
    Build a flat list of typed segments from title + article markdown.
    Types: h1, h2, bold, link, normal.
    """
    segments = []

    # Title as H1
    segments.append({"type": "h1",     "text": title, "url": None})
    segments.append({"type": "normal", "text": "\n",  "url": None})

    for line in content.split("\n"):
        if line.startswith("## "):
            segments.append({"type": "h2",     "text": line[3:].strip(), "url": None})
            segments.append({"type": "normal", "text": "\n",             "url": None})
        elif line.startswith("# "):
            # Claude shouldn't emit H1, but handle gracefully
            segments.append({"type": "h1",     "text": line[2:].strip(), "url": None})
            segments.append({"type": "normal", "text": "\n",             "url": None})
        elif (line.startswith("Meta-title:") or line.startswith("Meta-description:")
              or line.startswith("Méta-titre") or line.startswith("Méta-description")):
            segments.append({"type": "bold",   "text": line, "url": None})
            segments.append({"type": "normal", "text": "\n", "url": None})
        else:
            last_end = 0
            for m in COMBINED_RE.finditer(line):
                if m.start() > last_end:
                    segments.append({"type": "normal", "text": line[last_end:m.start()], "url": None})
                if m.group(0).startswith("["):
                    # Markdown link: [text](url)
                    segments.append({"type": "link", "text": m.group(1), "url": m.group(2)})
                else:
                    # Bold: **text**
                    segments.append({"type": "bold", "text": m.group(3), "url": None})
                last_end = m.end()
            if last_end < len(line):
                segments.append({"type": "normal", "text": line[last_end:], "url": None})
            segments.append({"type": "normal", "text": "\n", "url": None})

    return segments


# ── Doc creation ──────────────────────────────────────────────────────────────

def create_article_doc(creds, title: str, content: str, drive_folder_id: str) -> str:
    """
    Create a Google Doc: H1 title, hyperlinked anchors, H2 headings, bold meta
    lines, Poppins font, and an Unsplash image after the H1.
    Returns the Doc URL.
    """
    docs  = get_docs_service(creds)
    drive = get_drive_service(creds)

    # Create document and move to target folder
    doc = docs.documents().create(body={"title": title}).execute()
    doc_id = doc["documentId"]
    file = drive.files().get(fileId=doc_id, fields="parents").execute()
    drive.files().update(
        fileId=doc_id,
        addParents=drive_folder_id,
        removeParents=",".join(file.get("parents", [])),
        fields="id,parents"
    ).execute()

    # Build full text + character ranges from segments
    segments  = _parse_segments(title, content)
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
        doc_start = start + 1  # Google Docs indices are 1-based
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

    # Fetch and insert Unsplash image after H1 (title + \n = len(title)+1, image goes after that)
    image_url, page_url = _fetch_unsplash_image(title, content)
    if image_url:
        try:
            image_index = len(title) + 2  # after H1 text + its \n (1-based)
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
                attr_index = image_index + 1  # image occupies 1 char
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
            pass  # Doc is still created without image

    return f"https://docs.google.com/document/d/{doc_id}/edit"
