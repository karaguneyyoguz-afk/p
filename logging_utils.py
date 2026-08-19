"""Persistent processing logs shared by the CLI and Flask dashboard."""

import json
import os
from datetime import datetime
from threading import Lock
from typing import Any, Dict, List, Optional

LOG_FILE = os.path.join(os.path.dirname(__file__), "mail_processing_log.jsonl")
_LOG_LOCK = Lock()


def record_mail_event(
    event: str,
    status: str,
    sender_email: str = "",
    subject: str = "",
    reason: str = "",
    details: str = "",
    classification: str = "",
    ticket_id: Optional[str] = None,
    ticket_details: Optional[Dict[str, Any]] = None,
    mail_body: str = "",
) -> Dict[str, Any]:
    """Append one processing event and return the stored record."""
    record = {
        "timestamp": datetime.now().astimezone().isoformat(),
        "event": event,
        "status": status,
        "sender_email": sender_email,
        "subject": subject,
        "reason": reason,
        "details": details,
        "classification": classification,
        "ticket_id": ticket_id,
        "ticket_details": ticket_details or {},
        "mail_body": mail_body,
    }
    with _LOG_LOCK:
        with open(LOG_FILE, "a", encoding="utf-8") as log_file:
            log_file.write(json.dumps(record, ensure_ascii=False) + "\n")
    return record


def read_mail_events(limit: int = 100) -> List[Dict[str, Any]]:
    """Read the newest processing events without failing the dashboard."""
    if not os.path.exists(LOG_FILE):
        return []

    with _LOG_LOCK:
        with open(LOG_FILE, "r", encoding="utf-8") as log_file:
            lines = log_file.readlines()

    events = []
    for line in lines[-limit:]:
        try:
            events.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return list(reversed(events))


def clear_mail_events() -> None:
    """Remove all persisted processing events."""
    with _LOG_LOCK:
        if os.path.exists(LOG_FILE):
            os.remove(LOG_FILE)


def clear_mail_error_events() -> None:
    """Remove failed, blocked, and rejected events while keeping successes."""
    events = read_mail_events(limit=100000)
    remaining = [
        event for event in events
        if event.get("status") not in {"failed", "blocked", "rejected"}
    ]
    with _LOG_LOCK:
        if not remaining:
            if os.path.exists(LOG_FILE):
                os.remove(LOG_FILE)
            return
        with open(LOG_FILE, "w", encoding="utf-8") as log_file:
            for event in reversed(remaining):
                log_file.write(json.dumps(event, ensure_ascii=False) + "\n")
