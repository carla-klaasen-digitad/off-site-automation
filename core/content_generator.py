"""Generate article content via Claude API — handles guidelines loading, BL type, language."""
import re
from pathlib import Path
import anthropic
from dotenv import load_dotenv
import os

load_dotenv()

GUIDELINES_DIR = Path(__file__).parent.parent / "guidelines"
MODEL = "claude-opus-4-5"

LANGUAGE_VARIANT_PATTERN = re.compile(r"^Language:\s*(.+)$", re.MULTILINE | re.IGNORECASE)

LANG_CODE_MAP = {
    "english": "en",
    "french": "fr",
    "français": "fr",
    "anglais": "en",
}

# Maps sheet brand values (after slug normalization) to the guidelines filename prefix.
# Add entries here when the sheet uses a different name than the guidelines file.
BRAND_SLUG_ALIASES = {
    "danoneyogurt": "dannon",   # "Danone Yogurt" in sheet → dannon_*.md
    "danone":       "dannon",   # "Danone" → dannon_*.md
    "danino":       "dannon",   # "Danino" → dannon_*.md
}


def _load_guidelines(brand: str, client_guideline_prefix: str, language_col: str) -> tuple[str, str]:
    """
    Load general_CLIENT.md (optional) + brand_client_lang.md.
    Returns (combined_guidelines_text, language_variant).
    """
    lang_code = LANG_CODE_MAP.get(language_col.strip().lower(), "en")

    brand_slug = brand.strip().lower().replace(" ", "").replace("'", "").replace("-", "")
    brand_slug = BRAND_SLUG_ALIASES.get(brand_slug, brand_slug)
    brand_file = GUIDELINES_DIR / f"{brand_slug}_{client_guideline_prefix}_{lang_code}.md"
    general_file = GUIDELINES_DIR / f"general_{client_guideline_prefix}.md"

    brand_text = brand_file.read_text(encoding="utf-8") if brand_file.exists() else ""

    # Read language variant declared in the file header
    match = LANGUAGE_VARIANT_PATTERN.search(brand_text)
    language_variant = match.group(1).strip() if match else ("English" if lang_code == "en" else "French")

    general_text = general_file.read_text(encoding="utf-8") if general_file.exists() else ""

    combined = ""
    if general_text:
        combined += f"## Client-Wide Guidelines\n\n{general_text}\n\n---\n\n"
    if brand_text:
        combined += f"## Brand-Specific Guidelines\n\n{brand_text}"

    return combined, language_variant


def _build_prompt(row: dict, guidelines: str, language_variant: str, bl_type: str) -> str:
    title = row["title"]
    anchor = row["anchor"]
    target_url = row["target_url"]
    brand = row["website"]

    bl_type_clean = bl_type.strip().lower().replace("-", "").replace(" ", "")
    is_with_mention = "withmention" in bl_type_clean

    lang_lower = language_variant.strip().lower()
    is_french = lang_lower in ("french", "français", "fr")
    meta_title_label = "Méta-titre :" if is_french else "Meta-title:"
    meta_desc_label = "Méta-description :" if is_french else "Meta-description:"

    anchor_instruction = (
        f'Embed the anchor text as a markdown hyperlink exactly once: [{anchor}]({target_url})'
        if target_url and target_url.lower() != "category page to add"
        else f'Insert the exact text "{anchor}" in bold (no hyperlink — URL to be added later)'
    )

    if is_with_mention:
        brand_instruction = (
            f"The article is NOT about {brand} — the brand must not be the main subject. "
            f"Include exactly ONE natural mention of {brand}, in ONE paragraph. "
            f"That mention must be in the SAME paragraph as the anchor link for \"{anchor}\". "
            f"The mention is a brief aside — a single sentence where the brand appears as a practical example. "
            f"Example pattern: \"A [product type] can be a simple option for this purpose.\" "
            f"The article must not read like a press release or sponsored content."
        )
    else:
        brand_instruction = (
            f"Do NOT mention {brand} or any brand name anywhere in the article. "
            f"This is a pure guest post — write only general editorial content."
        )

    return f"""You are an expert content writer for off-site guest posts and link-building articles. Follow all guidelines below exactly.

---

WRITING GUIDELINES:
{guidelines}

---

ARTICLE SPECIFICATIONS:
- Title: {title}
- Language: Write entirely in {language_variant}
- Length: 500–700 words
- Anchor text: {anchor_instruction}
- Brand mention rule: {brand_instruction}

---

STRUCTURE:
1. Start with these two lines (use exactly this format):
   {meta_title_label} [SEO title, 55–65 characters]
   {meta_desc_label} [SEO description, 140–160 characters]
   Then a blank line.
2. Introduction (no heading) — 2–4 sentences setting up the topic
3. 5–7 body sections, each with an H2 heading (## Heading)
4. No separate conclusion heading — end with a short closing paragraph

FORMAT RULES:
- Use ## for section headings only (no H1 — the title is set separately)
- Paragraphs: 2–4 sentences. No dense blocks.
- No bullet lists unless the title explicitly calls for a numbered list format
- No em dashes (—) more than twice in the entire article
- No filler phrases ("In today's world", "In conclusion", "It goes without saying")
- No superlatives, no enthusiastic or promotional language
- Output the meta block + article body only — no commentary, no "Here is your article:"

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
