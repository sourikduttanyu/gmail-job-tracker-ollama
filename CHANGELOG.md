# Changelog

All notable changes to this project will be documented here.

Format: [Keep a Changelog](https://keepachangelog.com/en/1.0.0/)

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
