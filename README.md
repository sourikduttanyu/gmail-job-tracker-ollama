# Job Tracker

Scans Gmail for job application emails and exports a structured spreadsheet (`jobs.xlsx`). Re-run anytime to pull new emails and update the sheet incrementally.

## What it does

- Searches Gmail using a broad query covering applications, interviews, offers, rejections
- Extracts: company, role, status, source (LinkedIn/Indeed/etc.), date
- Deduplicates on Message ID — safe to re-run
- Outputs `jobs.xlsx` sorted by date descending

## Setup

### 1. Python environment

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 2. Google OAuth credentials

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a project → Enable **Gmail API**
3. Create OAuth 2.0 credentials (Desktop app type)
4. Download → save as `credentials.json` in this directory

### 3. Run

```bash
python3 job_tracker.py
```

First run opens a browser for Gmail OAuth consent. `token.json` is saved locally for subsequent runs.

## Output columns

| Column | Description |
|--------|-------------|
| Date | Email received date |
| Company | Extracted from sender |
| Role | Extracted from subject/snippet |
| Status | `Applied` / `Interview` / `Offer` / `Rejected` / `Unknown` |
| Source | `LinkedIn`, `Indeed`, `Greenhouse`, `Lever`, `Workday`, `Glassdoor`, `Direct` |
| Subject | Original email subject |
| Sender | Full sender field |
| Snippet | First 250 chars of email body |
| Message ID | Gmail message ID (dedup key) |
| Thread ID | Gmail thread ID |

## Files

```
Job Tracker/
├── job_tracker.py       # Main script
├── requirements.txt     # Dependencies
├── credentials.json     # OAuth client secret (not committed)
├── token.json           # OAuth token (not committed, auto-generated)
└── jobs.xlsx            # Output spreadsheet (not committed)
```

## Status detection priority

`Offer` > `Rejected` > `Interview` > `Applied` > `Unknown`
