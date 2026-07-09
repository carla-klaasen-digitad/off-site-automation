"""Create formatted Google Docs from generated article content."""
from googleapiclient.discovery import build


def get_docs_service(creds):
    return build("docs", "v1", credentials=creds)


def get_drive_service(creds):
    return build("drive", "v3", credentials=creds)


def create_article_doc(creds, title: str, content: str, drive_folder_id: str) -> str:
    """
    Create a Google Doc with the article title and content,
    move it to the specified Drive folder, and return the Doc URL.
    """
    docs = get_docs_service(creds)
    drive = get_drive_service(creds)

    # Create the document
    doc = docs.documents().create(body={"title": title}).execute()
    doc_id = doc["documentId"]

    # Move to the correct Drive folder
    file = drive.files().get(fileId=doc_id, fields="parents").execute()
    previous_parents = ",".join(file.get("parents", []))
    drive.files().update(
        fileId=doc_id,
        addParents=drive_folder_id,
        removeParents=previous_parents,
        fields="id,parents"
    ).execute()

    # Insert content
    _insert_content(docs, doc_id, title, content)

    return f"https://docs.google.com/document/d/{doc_id}/edit"


def _insert_content(docs, doc_id: str, title: str, content: str):
    """Insert title as H1 and body content with H2 headings formatted."""
    requests = []

    # Insert full text first (title + newline + body)
    full_text = f"{title}\n{content}"
    requests.append({
        "insertText": {"location": {"index": 1}, "text": full_text}
    })

    # Style the title line as Heading 1
    title_end = len(title) + 1
    requests.append({
        "updateParagraphStyle": {
            "range": {"startIndex": 1, "endIndex": title_end},
            "paragraphStyle": {"namedStyleType": "HEADING_1"},
            "fields": "namedStyleType"
        }
    })

    # Style ## lines as Heading 2 and strip the ## markers
    lines = full_text.split("\n")
    index = 1
    cleanup_requests = []
    for line in lines:
        line_end = index + len(line) + 1  # +1 for newline
        if line.startswith("## "):
            cleanup_requests.append({
                "updateParagraphStyle": {
                    "range": {"startIndex": index, "endIndex": line_end},
                    "paragraphStyle": {"namedStyleType": "HEADING_2"},
                    "fields": "namedStyleType"
                }
            })
            # Delete the "## " prefix (3 chars)
            cleanup_requests.append({
                "deleteContentRange": {
                    "range": {"startIndex": index, "endIndex": index + 3}
                }
            })
        index = line_end

    docs.documents().batchUpdate(
        documentId=doc_id,
        body={"requests": requests}
    ).execute()

    if cleanup_requests:
        # Process heading deletions in reverse order to preserve indices
        cleanup_requests_rev = [
            r for r in reversed(cleanup_requests)
            if "deleteContentRange" in r
        ]
        style_requests = [r for r in cleanup_requests if "updateParagraphStyle" in r]
        if style_requests:
            docs.documents().batchUpdate(
                documentId=doc_id, body={"requests": style_requests}
            ).execute()
        if cleanup_requests_rev:
            docs.documents().batchUpdate(
                documentId=doc_id, body={"requests": cleanup_requests_rev}
            ).execute()
