#!/usr/bin/env python3
"""
Job Tracker — scans Gmail for job application emails, saves to jobs.xlsx.
Re-run anytime to pull new emails and update the sheet.
"""

import base64
import json
import re
from datetime import datetime
from pathlib import Path

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
import pandas as pd

# ── Config ──────────────────────────────────────────────────────────────────
SCOPES        = ['https://www.googleapis.com/auth/gmail.readonly']
BASE_DIR      = Path(__file__).parent
CREDS_FILE    = BASE_DIR / 'credentials.json'
TOKEN_FILE    = BASE_DIR / 'token.json'
OUTPUT_FILE   = BASE_DIR / 'jobs.xlsx'
MAX_RESULTS   = 500

# ── Gmail search query ───────────────────────────────────────────────────────
GMAIL_QUERY = (
    'subject:(application OR interview OR offer OR rejection OR '
    '"thank you for applying" OR "application received" OR '
    '"coding challenge" OR assessment OR recruiter OR "phone screen" OR '
    '"we regret" OR unfortunately OR "next steps" OR "moving forward" OR '
    '"not selected" OR "other candidates") '
    'OR from:(linkedin.com OR indeed.com OR greenhouse.io OR lever.co OR '
    'myworkday.com OR glassdoor.com OR recruiting OR talent OR careers OR '
    'noreply OR no-reply)'
)

# ── Academic email filter ────────────────────────────────────────────────────
# Emails from .edu senders OR with strong academic content are skipped entirely.

# Strong academic content signals — 2+ hits = skip
ACADEMIC_CONTENT_PATTERNS = [
    r'\bcourse\b', r'\bcoursework\b', r'\bsyllabus\b',
    r'\blecture\b', r'\boffice hours?\b', r'\bprofessor\b', r'\bprof\b',
    r'\bregistrar\b', r'\bfinancial aid\b', r'\btuition\b', r'\bbursar\b',
    r'\btranscript\b', r'\bgrade[sd]?\b', r'\bGPA\b',
    r'\bsemester\b', r'\bquarter\b', r'\bacademic year\b',
    r'\bcommencement\b', r'\bgraduation ceremony\b',
    r'\bcampus\b', r'\bdining hall\b', r'\bdormitory\b', r'\bresidence hall\b',
    r'\bstudent (?:id|account|portal|services|union|government)\b',
    r'\blibrary\b', r'\bfaculty\b', r'\bcurriculum\b',
    r'\bTA\b', r'\bteaching assistant\b',
    r'\bhomework\b', r'\bmidterm\b', r'\bfinal exam\b',
    r'\bdean\b', r'\bdepartment of \w+\b',
    r'\benrollment\b', r'\badmission[s]?\b',
    r'\bstudent loan\b', r'\bfafsa\b',
    r'\bclub meeting\b', r'\bstudent org\b',
]

# University domains to always block (regardless of content)
BLOCKED_UNIVERSITY_DOMAINS = [
    r'nyu\.edu',
    r'\.edu\b',   # catch-all for any .edu sender
]

# Job-specific signals that override academic filter (.edu career center emails)
JOB_OVERRIDE_PATTERNS = [
    r'career(?:s| center| fair|\.)', r'recruiting', r'internship',
    r'full.?time offer', r'job fair', r'on.?campus (?:recruit|interview|hiring)',
]


def is_academic_email(sender: str, subject: str, body: str) -> bool:
    """Return True if email should be excluded as university/academic noise."""
    sender_lower = sender.lower()
    is_edu_sender = bool(re.search(r'@[^>\s]*\.edu\b', sender_lower))

    combined = (subject + ' ' + body[:1000]).lower()

    if is_edu_sender:
        # Keep only if clearly job/recruiting related
        for pattern in JOB_OVERRIDE_PATTERNS:
            if re.search(pattern, combined):
                return False
        return True  # .edu with no job signal → skip

    # Non-.edu: skip if 2+ academic signals
    hits = sum(1 for p in ACADEMIC_CONTENT_PATTERNS if re.search(p, combined))
    return hits >= 2


# ── Status detection ─────────────────────────────────────────────────────────

# Noise: skip classification entirely if these match
NOISE_PATTERNS = [
    r'job alert',
    r'new jobs? (?:for|matching)',
    r'recommended jobs?',
    r'\d+ new jobs?',
    r'jobs? you might like',
    r'based on your (?:profile|resume|search)',
    r'(?:open|new) (?:roles?|positions?) (?:at|near)',
]

# Offer: requires unambiguous "you got the job" language
OFFER_PATTERNS = [
    r'pleased to (?:offer|extend an offer)',
    r"we(?:'re| are) (?:excited|pleased|happy|delighted) to offer you",
    r"we(?:'d| would) like to offer you",
    r'offer letter',
    r'congratulations.*(?:joining|new role|new position|accepted)',
    r'(?:joining|accepted).*congratulations',
    r'you have been selected.*(?:join|offer)',
    r'welcome (?:aboard|to the team)',
    r'compensation package',
    r'sign(?:ing)? bonus',
    r'your start date',
]

# Rejected: unambiguous decline language
REJECTED_PATTERNS = [
    r'unfortunately.*(?:not|unable|decided|move)',
    r'not (?:moving|proceed)ing forward with your',
    r'moved forward with (?:other|another) candidate',
    r'not selected for (?:this|the)',
    r'decided to pursue other candidates',
    r'will not be moving forward',
    r'position has been filled',
    r'not (?:a match|the right fit) for',
    r'no longer (?:being considered|moving forward with you)',
    r"we(?:'re| have) decided not to",
    r"we've decided to move forward with (?:other|another)",
    r'after (?:careful )?consideration.*(?:not|decided)',
    r'wish you (?:all the best|success) in your (?:job )?search',
    r'we (?:will not|won\'t) be moving',
    r'we regret to inform',
]

# Applied: submission confirmation only
APPLIED_PATTERNS = [
    r'(?:your )?application (?:has been |was )?(?:received|submitted|confirmed)',
    r'thank you for (?:applying|your application)',
    r'we(?:\'ve| have) received your application',
    r'application (?:successfully )?submitted',
    r'successfully applied',
    r'application confirmation',
]

# Interview: high-confidence scheduling/test signals only
INTERVIEW_PATTERNS = [
    r'calendly\.com',
    r'zoom\.us/[a-z]',
    r'meet\.google\.com',
    r'teams\.microsoft\.com/l/meetup',
    r'hackerrank\.com',
    r'codility\.com',
    r'codesignal\.com',
    r'hirevue\.com',
    r'take.?home (?:assignment|test|project|challenge)',
    r'technical (?:screen|round)\b',
    r'hiring manager (?:interview|call|round)',
    r'on.?site (?:interview|visit)',
    r'final (?:round|interview)',
    r'please (?:select|schedule|choose|pick|book) (?:a )?(?:time|slot|date)',
    r'schedule (?:a )?(?:30|45|60).?min',
    r'(?:phone|video) (?:screen|interview) (?:scheduled|confirmed)',
    r'interview (?:scheduled|confirmed|invitation)',
    r'we(?:\'d| would) like to (?:invite|schedule) you for (?:an )?interview',
]

# ── Job board domains ────────────────────────────────────────────────────────
JOB_BOARDS = {
    'LinkedIn':   ['linkedin.com'],
    'Indeed':     ['indeed.com'],
    'Greenhouse': ['greenhouse.io'],
    'Lever':      ['lever.co'],
    'Workday':    ['myworkday.com', 'workday.com'],
    'Glassdoor':  ['glassdoor.com'],
}

# ── Role extraction patterns ─────────────────────────────────────────────────
ROLE_PATTERNS = [
    r'(?:position|role|job|opportunity) (?:of |for |as )?(?:a |an )?([A-Za-z][A-Za-z\s/,-]+?)(?:\s+(?:at|with|in)|[,.]|$)',
    r'(?:applying|applied) (?:for |to )?(?:the )?([A-Za-z][A-Za-z\s/,-]+?)(?:\s+(?:position|role|job)|[,.]|$)',
    r'([A-Za-z][A-Za-z\s/,-]+?) (?:position|role|opening|opportunity)\b',
    r'(?:re:|fw:)\s*(?:your application for |application - )?([A-Za-z][A-Za-z\s/,-]+?)(?:\s+at|\s*[-|]|\s*$)',
]


# ── Auth ─────────────────────────────────────────────────────────────────────
def get_gmail_service():
    creds = None
    if TOKEN_FILE.exists():
        with open(TOKEN_FILE) as f:
            creds = Credentials.from_authorized_user_info(json.load(f), SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(str(CREDS_FILE), SCOPES)
            creds = flow.run_local_server(port=0)
        with open(TOKEN_FILE, 'w') as f:
            f.write(creds.to_json())

    return build('gmail', 'v1', credentials=creds)


# ── Body extraction ───────────────────────────────────────────────────────────
def extract_body(payload: dict) -> str:
    """Recursively extract plain-text body from MIME payload."""
    mime = payload.get('mimeType', '')
    if mime == 'text/plain':
        data = payload.get('body', {}).get('data', '')
        if data:
            return base64.urlsafe_b64decode(data + '==').decode('utf-8', errors='ignore')

    for part in payload.get('parts', []):
        result = extract_body(part)
        if result:
            return result

    return ''


# ── Status detection ──────────────────────────────────────────────────────────
def detect_status(text: str) -> str:
    t = text.lower()

    # Discard job-alert / marketing noise immediately
    for pattern in NOISE_PATTERNS:
        if re.search(pattern, t):
            return 'Unknown'

    # Priority order: Offer > Rejected > Interview > Applied
    for pattern in OFFER_PATTERNS:
        if re.search(pattern, t):
            return 'Offer'

    for pattern in REJECTED_PATTERNS:
        if re.search(pattern, t):
            return 'Rejected'

    for pattern in INTERVIEW_PATTERNS:
        if re.search(pattern, t):
            return 'Interview'

    for pattern in APPLIED_PATTERNS:
        if re.search(pattern, t):
            return 'Applied'

    return 'Unknown'


def extract_company(sender: str) -> str:
    m = re.match(r'"?([^"<@\n]+?)"?\s*<', sender)
    if m:
        name = m.group(1).strip()
        skip = {'noreply', 'no-reply', 'recruiting', 'talent', 'careers',
                 'hr', 'jobs', 'hiring', 'notifications', 'info', 'hello',
                 'team', 'support', 'do not reply'}
        if name.lower() not in skip and len(name) > 1:
            return name

    m = re.search(r'@([^.@>]+)\.', sender)
    if m:
        domain = m.group(1)
        skip_domains = {'gmail', 'yahoo', 'hotmail', 'outlook', 'noreply',
                        'no-reply', 'mail', 'email', 'bounce', 'send'}
        if domain.lower() not in skip_domains:
            return domain.capitalize()

    return 'Unknown'


def extract_role(subject: str, body: str) -> str:
    clean_subject = re.sub(r'^(re|fw|fwd):\s*', '', subject, flags=re.IGNORECASE).strip()
    # Use subject + first 500 chars of body for role extraction
    text = clean_subject + ' ' + body[:500]

    for pattern in ROLE_PATTERNS:
        m = re.search(pattern, text, re.IGNORECASE)
        if m:
            role = m.group(1).strip().rstrip('.,')
            if 3 < len(role) < 70:
                return role

    return 'Unknown'


def detect_source(sender: str) -> str:
    sender_lower = sender.lower()
    for board, domains in JOB_BOARDS.items():
        if any(d in sender_lower for d in domains):
            return board
    return 'Direct'


def parse_message(msg: dict) -> dict | None:
    headers = {h['name']: h['value'] for h in msg['payload']['headers']}
    subject = headers.get('Subject', '')
    sender  = headers.get('From', '')
    snippet = msg.get('snippet', '')
    body    = extract_body(msg['payload'])

    # Skip academic/university emails
    if is_academic_email(sender, subject, body or snippet):
        return None

    try:
        ts   = int(msg.get('internalDate', 0))
        date = datetime.fromtimestamp(ts / 1000).strftime('%Y-%m-%d')
    except Exception:
        date = ''

    # Use full body for detection; fall back to snippet if body empty
    detection_text = f"{subject} {body if body else snippet}"
    return {
        'Date':       date,
        'Company':    extract_company(sender),
        'Role':       extract_role(subject, body or snippet),
        'Status':     detect_status(detection_text),
        'Source':     detect_source(sender),
        'Subject':    subject,
        'Sender':     sender,
        'Snippet':    snippet[:250],
        'Message ID': msg['id'],
        'Thread ID':  msg['threadId'],
    }


# ── Fetch ────────────────────────────────────────────────────────────────────
def fetch_message_ids(service, max_results: int) -> list[dict]:
    print(f"Searching Gmail (up to {max_results} results)...")
    refs, page_token = [], None

    while len(refs) < max_results:
        batch = min(100, max_results - len(refs))
        kwargs = {'userId': 'me', 'q': GMAIL_QUERY, 'maxResults': batch}
        if page_token:
            kwargs['pageToken'] = page_token

        resp       = service.users().messages().list(**kwargs).execute()
        refs      += resp.get('messages', [])
        page_token = resp.get('nextPageToken')
        if not page_token:
            break

    print(f"Found {len(refs)} matching emails.")
    return refs


# ── Main ─────────────────────────────────────────────────────────────────────
def main():
    service = get_gmail_service()

    # Load existing
    if OUTPUT_FILE.exists():
        existing_df = pd.read_excel(OUTPUT_FILE, engine='openpyxl')
        seen_ids    = set(existing_df['Message ID'].astype(str))
        print(f"Existing records: {len(existing_df)}")
    else:
        existing_df = pd.DataFrame()
        seen_ids    = set()

    # Fetch and filter
    refs     = fetch_message_ids(service, MAX_RESULTS)
    new_refs = [r for r in refs if r['id'] not in seen_ids]
    print(f"New emails to process: {len(new_refs)}")

    # Process — fetch full message body now
    records = []
    skipped = 0
    for i, ref in enumerate(new_refs, 1):
        try:
            msg = service.users().messages().get(
                userId='me',
                id=ref['id'],
                format='full',
            ).execute()
            record = parse_message(msg)
            if record is None:
                skipped += 1
            else:
                records.append(record)
        except Exception as e:
            print(f"  [!] Error on {ref['id']}: {e}")

        if i % 50 == 0:
            print(f"  Processed {i}/{len(new_refs)}...")

    print(f"Skipped (academic/university): {skipped}")

    # Save
    if records:
        new_df   = pd.DataFrame(records)
        final_df = pd.concat([existing_df, new_df], ignore_index=True)
        final_df.sort_values('Date', ascending=False, inplace=True)
        final_df.to_excel(OUTPUT_FILE, index=False, engine='openpyxl')
        print(f"\nSaved {len(final_df)} total records → {OUTPUT_FILE}")
    else:
        print("\nNo new records — sheet unchanged.")
        final_df = existing_df

    # Summary
    if not final_df.empty:
        print("\n─── Status Summary ───────────────────")
        print(final_df['Status'].value_counts().to_string())
        print("──────────────────────────────────────")


if __name__ == '__main__':
    main()
