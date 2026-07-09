# Setup Guide — Off-Site Content Automation

Follow these steps the first time you use this tool. After setup, your daily workflow is just `python automate_content.py`.

---

## What You Need Before Starting

- Python 3.10 or higher ([download](https://www.python.org/downloads/))
- A Google account with access to the client's Google Sheet and Drive folder
- Your Anthropic API key ([console.anthropic.com](https://console.anthropic.com))
- Access to a Google Cloud project (see Step 3 below)

---

## Step 1 — Clone the Repo

```bash
git clone git@github.com:carla-klaasen-digitad/off-site-automation.git
cd off-site-automation
```

---

## Step 2 — Create and Activate a Virtual Environment

A virtual environment keeps the project's libraries separate from your computer's other Python packages.

```bash
python3 -m venv venv
source venv/bin/activate        # macOS / Linux
venv\Scripts\activate           # Windows
```

Your terminal prompt will show `(venv)` when it's active. **Always activate this before running any script.**

---

## Step 3 — Install Required Libraries

```bash
pip install -r requirements.txt
```

**Required libraries** (must be installed):

| Library | Purpose |
|---------|---------|
| `anthropic` | Claude API — generates article content |
| `google-api-python-client` | Google Sheets, Drive, Docs |
| `google-auth` | Google authentication |
| `google-auth-oauthlib` | Browser OAuth login flow |
| `google-auth-httplib2` | Transport layer for Google auth |
| `python-dotenv` | Reads your `.env` file |
| `pyyaml` | Reads `clients.yaml` config |
| `rich` | Terminal formatting and interactive prompts |

**Optional libraries** (only install if you need them):

| Library | Purpose |
|---------|---------|
| `python-docx` | Export articles to .docx files |
| `requests` | Fetch Unsplash images for articles |

---

## Step 4 — Set Up Google Cloud Credentials

This is the only technical step. You need a credentials file that lets the script access Google on your behalf.

**Option A — Get credentials from the existing project (recommended for DigitAd analysts):**

1. Ask Carla for access to the `content-automation` Google Cloud project
2. Go to [console.cloud.google.com](https://console.cloud.google.com) → select the project
3. Go to **APIs & Services → Credentials**
4. Download the OAuth 2.0 client credentials as JSON
5. Save the file as `credentials.json` in the project root (same folder as `automate_content.py`)

**Option B — Create your own Google Cloud project:**

1. Go to [console.cloud.google.com](https://console.cloud.google.com) → New project
2. Enable these APIs: **Google Sheets API**, **Google Drive API**, **Google Docs API**
3. Go to **APIs & Services → Credentials → Create Credentials → OAuth 2.0 Client ID**
4. Application type: **Desktop App**
5. Download the JSON and save as `credentials.json` in the project root

---

## Step 5 — Create Your `.env` File

Copy the template and fill in your keys:

```bash
cp .env.template .env
```

Open `.env` and add:

```
ANTHROPIC_API_KEY=your_key_here
UNSPLASH_ACCESS_KEY=your_key_here    # optional
```

**Never commit `.env` to Git.**

---

## Step 6 — Configure Your Client

If `clients.yaml` already has your client configured, skip to Step 7.

To add a new client, run the setup wizard:

```bash
python setup_client.py
```

The wizard will ask for:
- Client ID (e.g. `danone_usa`)
- Google Sheet URL (paste from browser — the script extracts the ID)
- Google Drive folder URL (paste from browser — the script extracts the ID)
- Tab name, header row, column letters, status values

It writes the entry to `clients.yaml` automatically.

**After adding a client, create the brand guidelines files:**

```
guidelines/{brand}_{client_prefix}_{en|fr}.md
```

Use `guidelines/template_brand.md` as a starting point. The `Language:` field at the top is required.

---

## Step 7 — First Run

```bash
python automate_content.py
```

On your first run, a browser window will open asking you to log in to your Google account. After that, a `token.json` file is created and no browser login is needed for future runs.

**If you ever get a Google authentication error:** delete `token.json` and re-run — you'll get a fresh browser login.

---

## Daily Workflow

```bash
source venv/bin/activate          # activate venv (every new terminal)
python automate_content.py        # run the script
```

The banner shows available clients and usage instructions. You choose client → brand → month → year, preview the rows, confirm, and the script runs.

---

## Troubleshooting

| Problem | Fix |
|---------|-----|
| `(venv)` not showing | Run `source venv/bin/activate` from the project folder |
| `ModuleNotFoundError` | Make sure venv is active, re-run `pip install -r requirements.txt` |
| `credentials.json not found` | Complete Step 4 above |
| Google auth error | Delete `token.json` and re-run |
| `clients.yaml not found` | Run `python setup_client.py` or copy `clients.yaml.template` to `clients.yaml` |
| Brand guidelines not found | Create `guidelines/{brand}_{prefix}_en.md` (see template) |
| Row skipped in log | Check log in `logs/{client_id}_batch.log` for the reason |
