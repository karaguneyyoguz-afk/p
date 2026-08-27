"""Job'lar ekranı: hangi arka plan işi hangi aralıkta çalışıyor, en son ne
zaman çalıştı, ve ona ait son loglar -- accounts_routes.py'nin blueprint
deseniyle tutarlı, "jobs" ekranına bağlı."""

from datetime import datetime, timezone

from flask import Blueprint, jsonify

from accounts import require_screen
from job_registry import JOBS, STALE_MULTIPLIER, get_all_heartbeats, get_last_heartbeat, is_valid_job
from logging_utils import read_mail_events
from service_log import read_service_events

jobs_bp = Blueprint("jobs", __name__, url_prefix="/api")


def _status_for(job_name: str, heartbeat_iso: str | None) -> str:
    if heartbeat_iso is None:
        return "never_run"
    try:
        heartbeat_at = datetime.fromisoformat(heartbeat_iso)
    except ValueError:
        return "never_run"
    now = datetime.now(heartbeat_at.tzinfo) if heartbeat_at.tzinfo else datetime.now()
    age_seconds = (now - heartbeat_at).total_seconds()
    stale_after = JOBS[job_name]["interval_seconds"] * STALE_MULTIPLIER
    return "active" if age_seconds <= stale_after else "stale"


def _job_summary(job_name: str, heartbeats: dict) -> dict:
    info = JOBS[job_name]
    last_heartbeat = heartbeats.get(job_name)
    return {
        "name": job_name,
        "label": info["label"],
        "description": info["description"],
        "interval_label": info["interval_label"],
        "entrypoint": info["entrypoint"],
        "last_heartbeat": last_heartbeat,
        "status": _status_for(job_name, last_heartbeat),
    }


@jobs_bp.route("/jobs")
@require_screen("jobs")
def list_jobs():
    heartbeats = get_all_heartbeats()
    return jsonify({"jobs": [_job_summary(name, heartbeats) for name in JOBS]})


@jobs_bp.route("/jobs/<job_name>")
@require_screen("jobs")
def get_job_detail(job_name: str):
    if not is_valid_job(job_name):
        return jsonify({"error": "Job bulunamadı."}), 404

    heartbeats = get_all_heartbeats()
    summary = _job_summary(job_name, heartbeats)

    service_logs = [log for log in read_service_events(limit=100000) if log.get("job") == job_name][:50]
    mail_logs = [log for log in read_mail_events(limit=100000) if log.get("job") == job_name][:50]

    return jsonify({
        "job": summary,
        "service_logs": service_logs,
        "mail_logs": mail_logs,
    })
