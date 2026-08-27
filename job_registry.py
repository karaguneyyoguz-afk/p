"""Static registry of the project's recurring background jobs, plus a tiny
heartbeat file so the panel's "Job'lar" screen can show "en son çalıştı"
for jobs that don't otherwise leave a per-cycle log line.

Two real jobs exist today (watch_mail.py's continuous poll loop and
run_scheduled_mail_check.py's Task Scheduler-driven run) -- both write a
heartbeat once per cycle via record_heartbeat(). This is a single small
JSON file overwritten in place (not an append log): watch_mail.py polls
every 10 seconds, so an append-only log would grow by ~8600 lines/day for
information nobody needs history of, just the latest value.

Job identity is intentionally a SEPARATE concept from service_log.py's
"actor" (sistem/panel/cli) -- actor already has an established meaning
across Monitoring/Loglar (what KIND of process), and both jobs here use
actor="sistem". Job is a finer-grained tag layered on top (see
service_log.set_job), used only by the Jobs screen.
"""

import json
import os
from datetime import datetime
from threading import Lock
from typing import Any, Dict, Optional

HEARTBEAT_FILE = os.path.join(os.path.dirname(__file__), "job_heartbeats.json")
_HEARTBEAT_LOCK = Lock()

JOBS: Dict[str, Dict[str, Any]] = {
    "watch_mail": {
        "label": "Sürekli Mail İzleme",
        "description": "Gelen kutusunu sürekli açık tutup izler, yeni mail geldiğinde birkaç saniye içinde işler.",
        "interval_label": "10 saniyede bir",
        "interval_seconds": 10,
        "entrypoint": "watch_mail.py",
    },
    "scheduled_mail_check": {
        "label": "Zamanlanmış Mail Kontrolü",
        "description": "Windows Görev Zamanlayıcı'daki \"TatilbudurMailCheck\" görevi tarafından tetiklenir; watch_mail.py çalışmıyorsa yedek olarak devreye girer.",
        "interval_label": "15 dakikada bir",
        "interval_seconds": 15 * 60,
        "entrypoint": "run_scheduled_mail_check.py",
    },
}

# Bir job'ın "gecikmiş/durmuş" sayılması için son heartbeat'in ne kadar eski
# olması gerektiği -- kendi periyodunun birkaç katı, ki tek bir yavaş
# döngünün "durmuş" gibi görünmesine yol açmasın.
STALE_MULTIPLIER = 4


def is_valid_job(job_name: str) -> bool:
    return job_name in JOBS


def record_heartbeat(job_name: str) -> None:
    """Called once per work cycle by a job's own entrypoint script."""
    with _HEARTBEAT_LOCK:
        heartbeats = _read_heartbeats_unlocked()
        heartbeats[job_name] = datetime.now().astimezone().isoformat()
        with open(HEARTBEAT_FILE, "w", encoding="utf-8") as f:
            json.dump(heartbeats, f, ensure_ascii=False)


def _read_heartbeats_unlocked() -> Dict[str, str]:
    if not os.path.exists(HEARTBEAT_FILE):
        return {}
    try:
        with open(HEARTBEAT_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return {}


def get_last_heartbeat(job_name: str) -> Optional[str]:
    with _HEARTBEAT_LOCK:
        return _read_heartbeats_unlocked().get(job_name)


def get_all_heartbeats() -> Dict[str, str]:
    with _HEARTBEAT_LOCK:
        return _read_heartbeats_unlocked()
