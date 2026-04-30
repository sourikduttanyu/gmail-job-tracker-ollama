# Changelog

All notable changes to this project will be documented here.

Format: [Keep a Changelog](https://keepachangelog.com/en/1.0.0/)

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
