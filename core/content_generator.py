"""Generate article content via Claude API — handles guidelines loading, BL type, language."""
import re
from pathlib import Path
import anthropic
from dotenv import load_dotenv
import os

load_dotenv()

GUIDELINES_DIR = Path(__file__).parent.parent / "guidelines"
MODEL = "claude-sonnet-4-6"

LANGUAGE_VARIANT_PATTERN = re.compile(r"^Language:\s*(.+)$", re.MULTILINE | re.IGNORECASE)

LANG_CODE_MAP = {
    "english": "en",
    "french": "fr",
    "français": "fr",
    "anglais": "en",
}


def _load_guidelines(brand: str, client_guideline_prefix: str, language_col: str) -> tuple[str, str]:
    """
    Load general_CLIENT.md (optional) + brand_client_lang.md.
    Returns (combined_guidelines_text, language_variant).
    """
    lang_code = LANG_CODE_MAP.get(language_col.strip().lower(), "en")

    brand_slug = brand.strip().lower().replace(" ", "").replace("'", "").replace("-", "")
    brand_file = GUIDELINES_DIR / f"{brand_slug}_{client_guideline_prefix}_{lang_code}.md"
    general_file = GUIDELINES_DIR / f"general_{client_guideline_prefix}.md"

    if not brand_file.exists():
        raise FileNotFoundError(
            f"Guidelines file not found: {brand_file.name}\n"
            f"Expected at: guidelines/{brand_file.name}\n"
            f"Create this file using guidelines/template_brand.md as a starting point."
        )

    brand_text = brand_file.read_text(encoding="utf-8")

    # Read language variant declared in the file header
    match = LANGUAGE_VARIANT_PATTERN.search(brand_text)
    language_variant = match.group(1).strip() if match else ("English" if lang_code == "en" else "French")

    general_text = general_file.read_text(encoding="utf-8") if general_file.exists() else ""

    combined = ""
    if general_text:
        combined += f"## Client-Wide Guidelines\n\n{general_text}\n\n---\n\n"
    combined += f"## Brand-Specific Guidelines\n\n{brand_text}"

    return combined, language_variant


def _build_prompt(row: dict, guidelines: str, language_variant: str, bl_type: str) -> str:
    title = row["title"]
    anchor = row["anchor"]
    target_url = row["target_url"]
    brand = row["website"]

    bl_type_clean = bl_type.strip().lower().replace("-", "").replace(" ", "")
    is_with_mention = "withmention" in bl_type_clean

    anchor_instruction = (
        f'Hyperlink the exact text "{anchor}" to this URL: {target_url}'
        if target_url and target_url.lower() != "category page to add"
        else f'Insert the exact text "{anchor}" in bold (no hyperlink — URL to be added later)'
    )

    if is_with_mention:
        brand_instruction = (
            f"The article is NOT about {brand}. However, naturally incorporate one brief mention "
            f"of {brand} somewhere in the article where it relates organically to the anchor text "
            f'"{anchor}". This can be a single sentence or a short paragraph. '
            f"The rest of the article must remain focused on the topic."
        )
    else:
        brand_instruction = (
            f"Do NOT mention {brand} or any brand name anywhere in the article. "
            f"This is a pure guest post — the anchor text is the only brand-adjacent element."
        )

    return f"""You are writing an off-site guest post article. Follow all guidelines below exactly.

---

WRITING GUIDELINES:
{guidelines}

---

ARTICLE SPECIFICATIONS:
- Title: {title}
- Language: Write entirely in {language_variant}
- Length: 800–1,200 words
- Anchor text: {anchor_instruction}
- Brand mention rule: {brand_instruction}

---

STRUCTURE:
1. Introduction (no heading) — 2–3 sentences leading naturally into the topic
2. 3–4 body sections with H2 headings
3. Conclusion — 1 short paragraph, no heading

FORMAT RULES:
- Use H2 for section headings only (##)
- No H1 — the title is set separately
- No bullet lists unless the content genuinely calls for it
- No em dashes (—) more than twice in the entire article
- No filler phrases ("In today's world", "In conclusion", "It goes without saying")
- Output the article body only — no meta commentary, no "Here is your article:"

---

Write the article now."""


def generate_article(row: dict, client: dict) -> str:
    """
    Generate an article for a single row. Returns the article text.
    Raises on guidelines missing or API failure.
    """
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        raise EnvironmentError("ANTHROPIC_API_KEY not set. Check your .env file.")

    guideline_prefix = client.get("guideline_prefix", client.get("name", "").lower().replace(" ", ""))
    guidelines, language_variant = _load_guidelines(row["website"], guideline_prefix, row.get("language", "English"))
    bl_type = row.get("bl_type", "guest-blog")
    prompt = _build_prompt(row, guidelines, language_variant, bl_type)

    client_api = anthropic.Anthropic(api_key=api_key)
    message = client_api.messages.create(
        model=MODEL,
        max_tokens=2048,
        messages=[{"role": "user", "content": prompt}]
    )
    return message.content[0].text
