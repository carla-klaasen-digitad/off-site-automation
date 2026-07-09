# Off-Site Content Automation

Generates off-site guest post articles from a Google Sheet and saves them as formatted Google Docs. Supports multiple clients, multiple brands, English and French, and month/year filtering.

---

## What It Does

1. You fill in a Google Sheet with article specs (title, anchor text, target URL, brand, month, BL type, language)
2. Run `python automate_content.py`
3. Choose client → brand → month → year in the interactive prompt
4. Preview matching rows, confirm, and the script generates 800–1,200 word articles via Claude
5. Each article is saved as a Google Doc in the client's Drive folder and the Doc URL is written back to the sheet

---

## Scripts

| Script | Purpose |
|--------|---------|
| `automate_content.py` | Main script — interactive banner, prompts, generates articles |
| `setup_client.py` | Add a new client to `clients.yaml` via guided prompts |
| `push_guidelines.py` | Push brand writing guidelines into the client's Content Rules Google Doc |

---

## Folder Structure

```
off-site-automation/
├── automate_content.py       ← run this daily
├── setup_client.py           ← run once per new client
├── push_guidelines.py        ← run when brand guidelines change
├── clients.yaml              ← client config (never commit — contains IDs)
├── clients.yaml.template     ← reference template for clients.yaml
├── .env                      ← API keys (never commit)
├── .env.template             ← reference template for .env
├── requirements.txt          ← Python dependencies
├── SETUP.md                  ← first-time setup instructions
├── core/                     ← internal modules (do not edit)
│   ├── auth.py
│   ├── config_loader.py
│   ├── content_generator.py
│   ├── doc_writer.py
│   ├── logger.py
│   ├── month_normalizer.py
│   └── sheet_reader.py
├── guidelines/               ← brand writing guidelines
│   ├── template_brand.md     ← use this to create new brand files
│   ├── general_{client}.md   ← client-wide rules (optional)
│   └── {brand}_{client}_{en|fr}.md
└── logs/                     ← auto-generated per-client run logs
```

---

## Adding a New Client

```bash
python setup_client.py
```

Then create brand guidelines files in `guidelines/` using `template_brand.md`.

---

## Quick Start

See **[SETUP.md](SETUP.md)** for first-time setup (Google credentials, virtual environment, `.env`).

---

## Required Libraries

Install everything with:
```bash
pip install -r requirements.txt
```

`rich`, `anthropic`, `pyyaml`, and the Google API libraries are required. `python-docx` and `requests` are optional.

---

## Google Sheet Setup

The sheet needs these columns (letters are configurable per client in `clients.yaml`):

| Default Column | Field | Notes |
|----------------|-------|-------|
| B | Website / Brand | Must match brand ID in `clients.yaml` |
| C | Status | Set to `status_trigger` value to queue a row |
| D | Month | EN or FR month name, any format |
| E | Year | Optional — leave blank to skip year filter |
| F | BL Type | `Guest-blog` or `Guest-blog with mention` |
| G | Language | `English` or `French` |
| N | Title | Article heading |
| O | Anchor | Anchor text |
| P | Target URL | Destination URL (can be blank) |
| Q | Content | Doc URL written here when complete |

---

## Brand Guidelines Files

Each brand needs a file at `guidelines/{brand}_{client_prefix}_{lang}.md`.

The file **must start** with a `Language:` line declaring the writing variant:

```
Language: American English
```

Supported variants: `American English` · `Canadian English` · `Quebec French` · `France French`

For bilingual brands (e.g. Oikos Canada), create two files:
- `oikos_danonenorthamerica_en.md` — Canadian English
- `oikos_danonenorthamerica_fr.md` — Quebec French

The `Language` column in the sheet drives which file is loaded per row.
