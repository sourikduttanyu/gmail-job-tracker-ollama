#!/usr/bin/env python3
"""
Job Tracker — scans Gmail for job application emails, saves to jobs.xlsx.
Re-run anytime to pull new emails and update the sheet.
"""

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

# ── Status detection (order = priority) ─────────────────────────────────────
STATUS_PATTERNS = {
    'Offer': [
        r'offer letter', r'\boffer\b', r'congratulations',
        r'pleased to inform', r"we'd like to offer", r'happy to extend',
    ],
    'Rejected': [
        r'unfortunately', r'not moving forward', r'moved forward with other',
        r'not selected', r'decided to pursue other', r'will not be moving',
        r'position has been filled', r'not a match',
        r'no longer being considered', r'other candidates',
        r'we regret', r"we've decided",
    ],
    'Interview': [
        r'\binterview\b', r'phone screen', r'phone call', r'video call',
        r'coding challenge', r'technical assessment', r'take.home',
        r'hackerrank', r'codility', r'schedule.*call', r'next step',
        r'hiring manager', r'technical round',
    ],
    'Applied': [
        r'application received', r'thank you for applying',
        r'thank you for your application', r'we received your application',
        r'application has been submitted', r'successfully applied',
        r'application confirmation',
    ],
}

# ── Job board domains ────────────────────────────────────────────────────────
JOB_BOARDS = {
    'LinkedIn':  ['linkedin.com'],
    'Indeed':    ['indeed.com'],
    'Greenhouse':['greenhouse.io'],
    'Lever':     ['lever.co'],
    'Workday':   ['myworkday.com', 'workday.com'],
    'Glassdoor': ['glassdoor.com'],
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


# ── Parsers ──────────────────────────────────────────────────────────────────
def detect_status(text: str) -> str:
    text_lower = text.lower()
    for status, patterns in STATUS_PATTERNS.items():
        for pattern in patterns:
            if re.search(pattern, text_lower):
                return status
    return 'Unknown'


def extract_company(sender: str) -> str:
    # Try display name before angle bracket
    m = re.match(r'"?([^"<@\n]+?)"?\s*<', sender)
    if m:
        name = m.group(1).strip()
        skip = {'noreply', 'no-reply', 'recruiting', 'talent', 'careers',
                 'hr', 'jobs', 'hiring', 'notifications', 'info', 'hello',
                 'team', 'support', 'do not reply'}
        if name.lower() not in skip and len(name) > 1:
            return name

    # Fall back to domain without TLD
    m = re.search(r'@([^.@>]+)\.', sender)
    if m:
        domain = m.group(1)
        skip_domains = {'gmail', 'yahoo', 'hotmail', 'outlook', 'noreply',
                        'no-reply', 'mail', 'email', 'bounce', 'send'}
        if domain.lower() not in skip_domains:
            return domain.capitalize()

    return 'Unknown'


def extract_role(subject: str, snippet: str) -> str:
    # Clean subject prefixes
    clean_subject = re.sub(r'^(re|fw|fwd):\s*', '', subject, flags=re.IGNORECASE).strip()
    text = clean_subject + ' ' + snippet

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


def parse_message(msg: dict) -> dict:
    headers = {h['name']: h['value'] for h in msg['payload']['headers']}
    subject = headers.get('Subject', '')
    sender  = headers.get('From', '')
    snippet = msg.get('snippet', '')

    try:
        ts   = int(msg.get('internalDate', 0))
        date = datetime.fromtimestamp(ts / 1000).strftime('%Y-%m-%d')
    except Exception:
        date = ''

    combined = f"{subject} {snippet}"
    return {
        'Date':       date,
        'Company':    extract_company(sender),
        'Role':       extract_role(subject, snippet),
        'Status':     detect_status(combined),
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

    # Process
    records = []
    for i, ref in enumerate(new_refs, 1):
        try:
            msg = service.users().messages().get(
                userId='me',
                id=ref['id'],
                format='metadata',
                metadataHeaders=['Subject', 'From', 'Date'],
            ).execute()
            records.append(parse_message(msg))
        except Exception as e:
            print(f"  [!] Error on {ref['id']}: {e}")

        if i % 50 == 0:
            print(f"  Processed {i}/{len(new_refs)}...")

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
