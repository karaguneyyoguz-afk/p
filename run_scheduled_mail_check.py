"""Scheduled unattended mail check -- run every 15 minutes by Windows Task
Scheduler (task name: TatilbudurMailCheck).

Unlike main.py's CLI entrypoint (which re-processes the most recently
received email as a manual-testing convenience when the inbox has no unread
mail), this ONLY processes mail that is actually unread. An unattended job
that reran main.py's fallback every 15 minutes would silently re-create a
ticket for the same old email forever -- there being nothing new is the
normal, expected case here, not something to work around.

Checks every mailbox in MAILBOXES and exits; no internal loop/sleep --
Task Scheduler owns the interval. Each run's activity lands in the same
mail_processing_log.jsonl the web panel's Monitoring/Logs pages already
read, so watching those pages in a browser tab is enough to see this job
work without the panel (app.py) needing to be the one running it.
"""

import sys

if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if sys.stderr.encoding and sys.stderr.encoding.lower() != "utf-8":
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

from mail_processor import EmailProcessor, EmailCategorizer
from csm_api import CSMAPIClient
from main import process_email
from service_log import set_actor
from logging_utils import record_mail_event

# Each entry: (label, username_or_None, password_or_None). None/None uses
# the default EMAIL_USER/EMAIL_PASS from .env. Add the two company mailboxes
# here (with their own IMAP username/app-password) once available -- each
# runs independently, one mailbox's failure doesn't block the others.
MAILBOXES = [
    ("varsayılan", None, None),
]


def check_mailbox(label: str, username, password) -> None:
    processor = EmailProcessor(username=username, password=password)
    categorizer = EmailCategorizer()
    csm_client = CSMAPIClient()
    try:
        processor.connect()
        email_ids = processor.get_unread_emails()
        if not email_ids:
            print(f"[{label}] Yeni mail yok.")
            return

        print(f"[{label}] {len(email_ids)} yeni mail bulundu, işleniyor...")
        for email_id in email_ids:
            email_message = processor.fetch_email(email_id)
            if email_message:
                process_email(email_message, processor, categorizer, csm_client)
            else:
                record_mail_event(
                    event="email_fetch",
                    status="failed",
                    reason="E-posta IMAP sunucusundan alınamadı",
                    details=f"[{label}] IMAP ID: {email_id!r}",
                )
    except Exception as e:
        print(f"[{label}] Hata: {e}")
        record_mail_event(
            event="processor_error",
            status="failed",
            reason="Zamanlanmış mail kontrolü sırasında hata",
            details=f"[{label}] {e}",
        )
    finally:
        try:
            processor.disconnect()
        except Exception:
            pass


def main() -> None:
    set_actor("sistem")
    for label, username, password in MAILBOXES:
        check_mailbox(label, username, password)


if __name__ == "__main__":
    main()
