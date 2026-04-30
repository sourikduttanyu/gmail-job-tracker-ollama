# Job Tracker

> Scans your Gmail inbox, classifies job application emails with regex + optional local LLM, and exports a colour-coded `jobs.xlsx` — with an interactive Streamlit dashboard for filtering, charting, and manual status edits.

![CI](https://github.com/YOUR_USERNAME/job-tracker/actions/workflows/ci.yml/badge.svg)
![Python](https://img.shields.io/badge/python-3.9%2B-blue)
![License](https://img.shields.io/badge/license-MIT-green)

---

## Problem → Solution

Tracking 100+ job applications by hand is error-prone and time-consuming. This tool auto-scans your Gmail, classifies each email into `Applied / Interview / Offer / Rejected / Unknown`, deduplicates on Message ID, and keeps a live spreadsheet — zero manual entry.

---

## Demo

<!-- Add screenshot here: docs/screenshot.png -->
> Screenshot coming soon. Run locally to see the dashboard: `streamlit run dashboard.py`

---

## Architecture

```
Gmail API (OAuth 2.0)
        │
        ▼
  fetch_message_ids()          ← broad Gmail search query, paginated
        │
        ▼
  parse_message()
   ├── is_blocked()            ← blocklist: UAW, Yankees, Kaggle, etc.
   ├── is_academic_email()     ← .edu sender + content signal filter
   ├── detect_status_regex()   ← Offer > Rejected > Interview > Applied > Unknown
   │       │
   │       └── [Unknown + --ml flag]
   │               ▼
   │       classify_with_ollama()   ← local LLM via Ollama (llama3.2)
   ├── extract_company()
   ├── extract_role()
   └── detect_source()        ← LinkedIn / Indeed / Greenhouse / Lever / Workday / Direct
        │
        ▼
  jobs.xlsx  (dedup by Message ID, sorted by date)
        │
        ▼
  dashboard.py  (Streamlit: metrics, charts, editable table)
```

---

## How It Works

1. **Broad search** — Gmail query matches subject keywords and known recruiter domains
2. **Dedup** — skips emails already in `jobs.xlsx` (Message ID key) — safe to re-run anytime
3. **Filter** — drops blocked senders and academic emails before any processing
4. **Classify** — regex patterns ordered by confidence: Offer → Rejected → Interview → Applied → Unknown
5. **LLM fallback** (optional) — only `Unknown` emails go to Ollama; clear-cut cases skip it entirely
6. **Export** — colour-coded Excel with frozen header, auto-fit columns, and status summary

---

## Tech Stack

| Layer | Tech |
|---|---|
| Language | Python 3.9+ |
| Email source | Gmail API (google-auth, google-api-python-client) |
| Classification | Regex (primary) + Ollama local LLM (optional fallback) |
| Output | pandas + openpyxl |
| Dashboard | Streamlit |
| CI | GitHub Actions |
| Tests | pytest |
| Lint | ruff |

---

## Setup

### 1. Python environment

```bash
python3 -m venv .venv
source .venv/bin/activate       # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

### 2. Gmail OAuth credentials

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create project → Enable **Gmail API**
3. Create OAuth 2.0 credentials (Desktop app type)
4. Download → save as `credentials.json` in this directory

### 3. Run

```bash
python3 job_tracker.py
```

First run opens browser for Gmail OAuth consent. `token.json` saved locally for future runs.

---

## Usage

```bash
# Regex-only (fast, default)
python3 job_tracker.py

# Regex + Ollama LLM for Unknown emails
python3 job_tracker.py --ml

# Specify a different Ollama model
python3 job_tracker.py --ml --model phi3:mini

# Launch Streamlit dashboard
streamlit run dashboard.py
```

**Ollama setup** (for `--ml`):
```bash
# Install: https://ollama.com
ollama serve          # in one terminal
ollama pull llama3.2  # one-time download
```

---

## Output

| Column | Description |
|---|---|
| Date | Email received date |
| Company | Extracted from sender display name / domain |
| Role | Extracted from subject and body |
| Status | `Applied` / `Interview` / `Offer` / `Rejected` / `Unknown` |
| Source | `LinkedIn`, `Indeed`, `Greenhouse`, `Lever`, `Workday`, `Glassdoor`, `Direct` |
| Subject | Original email subject |
| Sender | Full sender field |
| Snippet | First 250 chars of body |
| Message ID | Gmail message ID (dedup key) |
| Thread ID | Gmail thread ID |

### Status colour coding

| Status | Colour |
|---|---|
| Offer | Green |
| Interview | Yellow |
| Applied | Blue |
| Rejected | Red |
| Unknown | Grey |

---

## Dashboard

```bash
streamlit run dashboard.py
```

- 6 metric cards + interview conversion rate
- Status and source bar charts
- Sidebar filters: status, source, company search, date range
- Editable table — change Status inline, save writes back to `jobs.xlsx`

---

## Design Decisions

**For engineering managers reviewing this project:**

| Decision | Reason |
|---|---|
| Regex-first, LLM-fallback | ~95% of emails have clear signals. Regex is instant; LLM only runs on ambiguous cases. Keeps runtime low even without GPU. |
| Dedup by Message ID | Gmail Message IDs are stable and unique. Makes re-runs safe and incremental without a database. |
| No database | `jobs.xlsx` is portable, shareable, and diff-friendly. Right tool for single-user personal data at this scale. |
| Academic filter | NYU .edu emails flood the inbox. Domain + content signal combination avoids blocking legitimate campus recruiting. |
| Blocklist pattern | Known noise sources (union emails, sports, Kaggle) were polluting results. Explicit blocklist is transparent and easy to extend. |
| Status priority order | Offer > Rejected > Interview > Applied. Later statuses in a thread supersede earlier ones. Most important signal wins. |
| `temperature=0, num_predict=8` for LLM | Forces deterministic one-word output from Ollama. Prevents hallucinations in structured classification. |

---

## Cloud Deployment (example)

This project is designed for local use, but can be adapted for cloud automation:

**Option 1 — GitHub Actions scheduled run**
```yaml
# .github/workflows/daily.yml
on:
  schedule:
    - cron: '0 9 * * *'   # 9 AM UTC daily
```
Requires: storing `credentials.json` + `token.json` as GitHub Secrets, and pushing `jobs.xlsx` back as an artifact or to Google Sheets via the Sheets API.

**Option 2 — Streamlit Cloud dashboard**
Deploy `dashboard.py` to [Streamlit Cloud](https://streamlit.io/cloud) with `jobs.xlsx` synced from Google Drive or S3. The tracker script remains local; the dashboard becomes publicly viewable.

**Option 3 — Google Cloud Run + Cloud Scheduler**
Containerise `job_tracker.py`, deploy to Cloud Run, trigger via Cloud Scheduler daily. Store output in Google Sheets instead of Excel.

---

## File Structure

```
job-tracker/
├── job_tracker.py          # Main script
├── dashboard.py            # Streamlit dashboard
├── requirements.txt        # Runtime dependencies
├── requirements-dev.txt    # Dev dependencies (pytest, ruff)
├── tests/
│   └── test_job_tracker.py # Unit tests for all pure functions
├── .github/
│   └── workflows/
│       └── ci.yml          # GitHub Actions: lint + test
├── CHANGELOG.md
├── credentials.json        # OAuth client secret (not committed)
├── token.json              # OAuth token (not committed, auto-generated)
└── jobs.xlsx               # Output spreadsheet (not committed)
```

---

## Running Tests

```bash
pip install -r requirements-dev.txt
pytest tests/ -v
```

---

## Roadmap

- [ ] Google Sheets export option (shareable, no Excel needed)
- [ ] Email reply tracking (thread-aware status updates)
- [ ] Weekly summary email digest
- [ ] Duplicate company detection (same company, multiple roles)
- [ ] Export to Notion / Airtable

---

## License

MIT
