# Changelog

All notable changes to this project will be documented here.

Format: [Keep a Changelog](https://keepachangelog.com/en/1.0.0/)

---

## [0.5.0] - 2026-04-30

### Added
- Streamlit dashboard (`dashboard.py`)
  - 6 metric cards: Total, Applied, Interview, Offer, Rejected, Unknown
  - Interview conversion rate caption
  - Status + Source bar charts
  - Sidebar filters: status, source, company search, date range
  - Editable table — Status column only, selectbox-constrained to valid values
  - Save button writes edits back to `jobs.xlsx`
- `streamlit` added to `requirements.txt`

---

## [0.4.0] - 2026-04-30

### Added
- Ollama integration for local LLM classification (`--ml` flag)
- `--model` flag to choose Ollama model (default: `llama3.2`)
- Ollama pre-flight check — gracefully falls back to regex if `ollama serve` not running
- `Regex_Status` column in sheet (only when `--ml` active) for side-by-side comparison
- Ollama only runs on emails regex marks `Unknown` — fast path for clear-cut cases

### Changed
- `requests` added explicitly to `requirements.txt`
- Ollama prompt uses `temperature=0` and `num_predict=8` for deterministic one-word output

---

## [0.3.0] - 2026-04-30

### Changed
- Block all `.edu` / NYU senders by default; keep only if career-center/recruiting content detected
- Rewrote all status detection patterns — each category now requires unambiguous, high-precision language:
  - **Offer**: requires explicit "we'd like to offer you", "welcome aboard", "compensation package", "your start date", etc.
  - **Rejected**: requires explicit decline phrases ("not moving forward with your", "we regret to inform", etc.)
  - **Interview**: requires scheduling signal (Calendly, Zoom meeting link, HackerRank, etc.) or confirmed interview invite — no longer fires on generic "interview" mention
  - **Applied**: requires submission confirmation language only
- Added noise filter: job alerts, recommended jobs, marketing emails → always `Unknown`
- Removed ambiguous single-word triggers (`\boffer\b`, `\binterview\b`, `congratulations` alone, `unfortunately` alone, `other candidates` alone)

### Fixed
- Offer false positives from any email containing "congratulations" or "\boffer\b"
- Interview false positives from recruiter intros mentioning interview as a future step
- Applied false positives from job board marketing

---

## [0.2.0] - 2026-04-30

### Changed
- Fetch full email body (`format='full'`) instead of metadata-only snippet
- Interview detection now requires multiple signals to reduce false positives:
  - High-confidence patterns (Calendly, Zoom, HackerRank, etc.) → single match sufficient
  - Regular patterns (interview, phone screen, etc.) → 2+ distinct matches required
- Added negative pattern filter: suppresses Interview if email looks like application confirmation, job alert, or "we'll be in touch" template
- Role extraction now uses first 500 chars of full body in addition to subject

### Fixed
- Interview over-counting caused by single-word `\binterview\b` match on generic recruiter emails

---

## [0.1.0] - 2026-04-30

### Added
- Initial Gmail scanning script (`job_tracker.py`)
- OAuth 2.0 auth flow with token caching
- Status detection: `Offer`, `Rejected`, `Interview`, `Applied`, `Unknown`
- Company extraction from sender display name and domain
- Role extraction from subject and email snippet
- Source detection: LinkedIn, Indeed, Greenhouse, Lever, Workday, Glassdoor, Direct
- Incremental deduplication via Message ID
- Export to `jobs.xlsx` via pandas + openpyxl
- Status summary printed after each run
