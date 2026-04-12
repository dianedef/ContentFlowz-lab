# Newsletter Receiving - IMAP Integration

## Overview

The Newsletter Robot now supports two backends for receiving newsletter emails:

1. **IMAP (default)** - Direct Gmail access via IMAP protocol. Free, no external dependencies.
2. **Composio** - Managed Gmail integration via Composio API. Paid, requires account.

## Quick Start

### 1. Environment Configuration

```bash
# .env file
NEWSLETTER_EMAIL_BACKEND=imap  # or "composio"

# IMAP credentials (when using IMAP backend)
NEWSLETTER_IMAP_EMAIL=your-newsletters@gmail.com
NEWSLETTER_IMAP_PASSWORD=xxxx-xxxx-xxxx-xxxx  # Gmail App Password
NEWSLETTER_IMAP_HOST=imap.gmail.com
NEWSLETTER_IMAP_FOLDER=Newsletters
NEWSLETTER_IMAP_ARCHIVE=CONTENTFLOW_DONE
```

### 2. Gmail Setup (One-time)

1. **Create dedicated Gmail account**: `your-newsletters@gmail.com`

2. **Enable 2-Factor Authentication**:
   - Google Account → Security → 2-Step Verification → Enable

3. **Generate App Password**:
   - Google Account → Security → App Passwords
   - Select "Mail" and "Other (Custom name)"
   - Copy the 16-character password to `NEWSLETTER_IMAP_PASSWORD`

4. **Create Gmail Labels**:
   - `Newsletters` - Inbox for incoming newsletters
   - `CONTENTFLOW_DONE` - Archive for processed emails

5. **Create Gmail Filter**:
   - Settings → Filters → Create new filter
   - From: contains `newsletter OR digest OR weekly`
   - Apply label: `Newsletters`
   - Also apply to matching conversations

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    Newsletter Crew                          │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  ┌─────────────────┐    ┌─────────────────┐                │
│  │ Research Agent  │───▶│  Writer Agent   │                │
│  └────────┬────────┘    └─────────────────┘                │
│           │                                                 │
│           ▼                                                 │
│  ┌─────────────────────────────────────────┐               │
│  │         Email Backend Switch             │               │
│  │  EMAIL_BACKEND=imap | composio          │               │
│  └────────┬──────────────────┬─────────────┘               │
│           │                  │                              │
│           ▼                  ▼                              │
│  ┌─────────────────┐  ┌─────────────────┐                  │
│  │   IMAP Tools    │  │  Gmail Tools    │                  │
│  │   (imap-tools)  │  │  (Composio)     │                  │
│  └────────┬────────┘  └─────────────────┘                  │
│           │                                                 │
│           ▼                                                 │
│  ┌─────────────────┐                                       │
│  │ Archive Stage   │  ◀── IMAP only                        │
│  │ (post-process)  │                                       │
│  └─────────────────┘                                       │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

## Files Modified/Created

| File | Change |
|------|--------|
| `agents/newsletter/tools/imap_tools.py` | **Created** - IMAPNewsletterReader class + CrewAI tools |
| `agents/newsletter/config/newsletter_config.py` | Added IMAP_DEFAULTS, EMAIL_BACKEND config |
| `agents/newsletter/schemas/newsletter_schemas.py` | Added EmailMessage Pydantic model |
| `agents/newsletter/newsletter_agent.py` | Conditional import based on EMAIL_BACKEND |
| `agents/newsletter/newsletter_crew.py` | Added archiving workflow for IMAP backend |

## IMAP Tools Reference

### `read_recent_newsletters(days, max_emails)`

Read newsletters from the configured folder.

```python
from agents.newsletter.tools.imap_tools import read_recent_newsletters

result = read_recent_newsletters(days=7, max_emails=20)
# Returns: Found 5 newsletters:
#
# - UID: 12345
#   From: Daily Digest <digest@example.com>
#   Subject: Your Weekly Roundup
#   Date: 2024-01-15 09:30
#   Preview: This week in tech...
```

### `read_competitor_newsletters(sender_emails)`

Read emails from specific senders (competitor analysis).

```python
from agents.newsletter.tools.imap_tools import read_competitor_newsletters

result = read_competitor_newsletters("competitor1@example.com,competitor2@example.com")
```

### `archive_processed_newsletter(email_uid)`

Archive a single processed email.

```python
from agents.newsletter.tools.imap_tools import archive_processed_newsletter

result = archive_processed_newsletter("12345")
# Returns: Successfully archived email 12345
```

### `archive_multiple_newsletters(email_uids)`

Archive multiple emails at once.

```python
from agents.newsletter.tools.imap_tools import archive_multiple_newsletters

result = archive_multiple_newsletters("12345,12346,12347")
# Returns: Successfully archived 3 emails
```

## Direct API Usage

For programmatic access outside CrewAI:

```python
from agents.newsletter.tools.imap_tools import IMAPNewsletterReader

reader = IMAPNewsletterReader(
    email="your-newsletters@gmail.com",
    app_password="xxxx-xxxx-xxxx-xxxx"
)

# Fetch newsletters
emails = reader.fetch_newsletters(days_back=7, max_results=20)
for email in emails:
    print(f"{email.subject} from {email.from_email}")
    print(f"  UID: {email.uid}")
    print(f"  Is newsletter: {email.is_newsletter}")

# Fetch from specific senders
competitor_emails = reader.fetch_by_senders(
    ["competitor1@example.com", "competitor2@example.com"]
)

# Archive processed
reader.archive_multiple([e.uid for e in emails])
```

## Backend Comparison

| Feature | IMAP | Composio |
|---------|------|----------|
| Cost | Free | Per-API-call |
| Setup | App Password | OAuth + Account |
| Manual Gmail Access | ✅ Preserved | ✅ Preserved |
| Archive/Delete | ✅ | ✅ |
| External Dependency | None | Composio servers |
| Offline Capable | Yes (cached) | No |
| Rate Limits | Gmail IMAP limits | Composio limits |

## Workflow

1. **Research Stage**: Agent uses `read_recent_newsletters` and `read_competitor_newsletters`
2. **Writing Stage**: Agent writes newsletter content based on research
3. **Archive Stage** (IMAP only): Processed emails are moved to `CONTENTFLOW_DONE`

The archive stage prevents re-processing the same emails on subsequent runs.

## Troubleshooting

### "IMAP credentials required" Error

Set the environment variables:
```bash
export NEWSLETTER_IMAP_EMAIL="your@gmail.com"
export NEWSLETTER_IMAP_PASSWORD="your-app-password"
```

### "Authentication failed" Error

1. Verify App Password is correct (16 characters, no spaces)
2. Ensure 2FA is enabled on the Gmail account
3. Check that IMAP is enabled: Gmail Settings → Forwarding and POP/IMAP → Enable IMAP

### "Folder not found" Error

Create the Gmail labels:
- `Newsletters`
- `CONTENTFLOW_DONE`

The system falls back to INBOX if labels don't exist.

### Emails Not Detected as Newsletters

The detection looks for:
- "newsletter", "digest", "weekly" in subject
- "unsubscribe" in body
- `List-Unsubscribe` header

Create a Gmail filter to auto-label newsletters for reliable detection.

## Testing

```bash
# Test IMAP connection
python -c "
from agents.newsletter.tools.imap_tools import IMAPNewsletterReader
r = IMAPNewsletterReader()
emails = r.fetch_newsletters(days_back=1)
print(f'Found {len(emails)} emails')
for e in emails:
    print(f'  - {e.subject}')
"

# Test full newsletter generation
python -m agents.newsletter.newsletter_crew --test
```
