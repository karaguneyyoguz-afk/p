"""Persistent log of outbound service calls (CSM API, Gmail IMAP, panel API)
and the "actor" (sistem/panel/cli) that triggered them.

There is no login system in this app — "actor" is not a human user account,
it's simply which entry-point process is running: watch_mail.py's background
loop ("sistem"), app.py serving the Enigma panel ("panel"), or main.py run
directly from the CLI ("cli"). Each entry-point sets it once at startup via
set_actor(); library code (csm_api.py, mail_processor.py, auth.py) never sets
it, only reads it via get_actor() when recording an event.
"""

import json
import os
from datetime import datetime
from threading import Lock
from typing import Any, Dict, List, Optional

LOG_FILE = os.path.join(os.path.dirname(__file__), "service_requests_log.jsonl")
_LOG_LOCK = Lock()

_current_actor = "sistem"


def set_actor(actor: str) -> None:
    """Called once by each entry-point script (app.py/watch_mail.py/main.py)."""
    global _current_actor
    _current_actor = actor


def get_actor() -> str:
    return _current_actor


def record_service_event(
    service: str,
    action: str,
    status: str,
    detail: str = "",
    duration_ms: Optional[int] = None,
) -> Dict[str, Any]:
    """Append one outbound service-call record and return it.

    service: 'csm_api' | 'gmail_imap' | 'panel_api'
    status: 'success' | 'failed'
    """
    record = {
        "timestamp": datetime.now().astimezone().isoformat(),
        "service": service,
        "action": action,
        "actor": get_actor(),
        "status": status,
        "detail": detail,
        "duration_ms": duration_ms,
    }
    with _LOG_LOCK:
        with open(LOG_FILE, "a", encoding="utf-8") as log_file:
            log_file.write(json.dumps(record, ensure_ascii=False) + "\n")
    return record


def read_service_events(limit: int = 200) -> List[Dict[str, Any]]:
    """Read the newest service-call events without failing the dashboard."""
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


def clear_service_events() -> None:
    with _LOG_LOCK:
        if os.path.exists(LOG_FILE):
            os.remove(LOG_FILE)
