# -*- coding: utf-8 -*-
"""
/api/jobs ve /api/jobs/<name> uc noktalarini (yetkilendirme, heartbeat'ten
durum hesaplama, job'a gore filtrelenmis log listesi) dogrular. Gercek
watch_mail.py/run_scheduled_mail_check.py CALISTIRILMAZ -- job_registry'nin
heartbeat dosyasi ve service/mail loglari dogrudan yazilarak simule edilir.
"""

import json
import os
import sys
import tempfile
from datetime import datetime, timedelta, timezone

if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

_tmp_db = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
_tmp_db.close()
os.environ["DATABASE_URL"] = f"sqlite:///{_tmp_db.name}"

import job_registry
import logging_utils
import service_log
from app import app
from dev_test_helpers import login_test_client
from logging_utils import record_mail_event
from service_log import record_service_event, set_actor, set_job

# Bu test dosyasina ozel dosyalar -- gercek job_heartbeats.json /
# service_requests_log.jsonl / mail_processing_log.jsonl'a HIC dokunmaz
# (test_service_log.py'deki ile ayni desen: gercek proje loglarina test
# verisi sizmasin, ayrica bu dosyalarin PID'i paylasan canli watch_mail.py/
# app.py surecleriyle de karismaz).
_tmp_heartbeats = tempfile.NamedTemporaryFile(suffix=".json", delete=False)
_tmp_heartbeats.close()
job_registry.HEARTBEAT_FILE = _tmp_heartbeats.name

_tmp_service_log = os.path.join(os.path.dirname(__file__), "_test_jobs_service_log.jsonl")
if os.path.exists(_tmp_service_log):
    os.remove(_tmp_service_log)
service_log.LOG_FILE = _tmp_service_log

_tmp_mail_log = os.path.join(os.path.dirname(__file__), "_test_jobs_mail_log.jsonl")
if os.path.exists(_tmp_mail_log):
    os.remove(_tmp_mail_log)
logging_utils.LOG_FILE = _tmp_mail_log

passed = 0
failed = 0
results = []


def check(name, condition, detail=""):
    global passed, failed
    if condition:
        passed += 1
        results.append(("PASS", name, detail))
    else:
        failed += 1
        results.append(("FAIL", name, detail))


client = app.test_client()
admin_csrf = login_test_client(app, client, email="admin@local.test", role="admin")
admin_headers = {"X-CSRF-Token": admin_csrf}

operator_client = app.test_client()
login_test_client(app, operator_client, email="operator@local.test", role="operator")

# ==========================================================
# Yetkilendirme
# ==========================================================
resp = operator_client.get("/api/jobs")
check("Yetki: operator /api/jobs'a giremiyor (403)", resp.status_code == 403, resp.status_code)

resp = client.get("/api/jobs")
check("Yetki: admin /api/jobs'u görebiliyor (200)", resp.status_code == 200, resp.status_code)

# ==========================================================
# Hic calismamis job -> never_run
# ==========================================================
resp = client.get("/api/jobs")
jobs_by_name = {j["name"]: j for j in resp.get_json()["jobs"]}
check(
    "Liste: her iki bilinen job da dönüyor (watch_mail, scheduled_mail_check)",
    set(jobs_by_name.keys()) == {"watch_mail", "scheduled_mail_check"},
    jobs_by_name.keys(),
)
check(
    "Durum: heartbeat hiç yoksa 'never_run'",
    jobs_by_name["watch_mail"]["status"] == "never_run" and jobs_by_name["watch_mail"]["last_heartbeat"] is None,
    jobs_by_name["watch_mail"],
)

resp = client.get("/api/jobs/olmayan_job")
check("Detay: geçersiz job adı -> 404", resp.status_code == 404, resp.get_json())

# ==========================================================
# Taze heartbeat -> active
# ==========================================================
job_registry.record_heartbeat("watch_mail")
resp = client.get("/api/jobs")
jobs_by_name = {j["name"]: j for j in resp.get_json()["jobs"]}
check(
    "Durum: az önceki heartbeat -> 'active'",
    jobs_by_name["watch_mail"]["status"] == "active" and jobs_by_name["watch_mail"]["last_heartbeat"] is not None,
    jobs_by_name["watch_mail"],
)
check(
    "Durum: hiç heartbeat atmayan diğer job hâlâ 'never_run'",
    jobs_by_name["scheduled_mail_check"]["status"] == "never_run",
    jobs_by_name["scheduled_mail_check"],
)

# ==========================================================
# Eski (bayat) heartbeat -> stale
# ==========================================================
old_timestamp = (datetime.now(timezone.utc).astimezone() - timedelta(hours=2)).isoformat()
with open(job_registry.HEARTBEAT_FILE, "w", encoding="utf-8") as f:
    json.dump({"watch_mail": old_timestamp}, f)

resp = client.get("/api/jobs")
jobs_by_name = {j["name"]: j for j in resp.get_json()["jobs"]}
check(
    "Durum: 2 saat önceki heartbeat (10sn'lik job için) -> 'stale'",
    jobs_by_name["watch_mail"]["status"] == "stale",
    jobs_by_name["watch_mail"],
)

# ==========================================================
# Job'a göre filtrelenmiş loglar (service + mail)
# ==========================================================
set_actor("sistem")
set_job("scheduled_mail_check")
record_service_event("gmail_imap", "connect", "success", detail="test@ornek.com")
record_mail_event(
    event="ticket_created", status="success", sender_email="test@ornek.com",
    subject="test", reason="test", classification="TEST",
)

set_job("watch_mail")
record_service_event("gmail_imap", "connect", "success", detail="baska@ornek.com")

set_job(None)  # panel/cli gibi diğer süreçler job etiketi taşımaz
record_service_event("panel_api", "GET /api/status", "success")

resp = client.get("/api/jobs/scheduled_mail_check")
detail = resp.get_json()
check("Detay: 200 dönüyor", resp.status_code == 200, resp.status_code)
check(
    "Detay: sadece bu job'a ait service log'lar dönüyor (job=None olanlar hariç)",
    len(detail["service_logs"]) == 1 and detail["service_logs"][0]["detail"] == "test@ornek.com",
    detail["service_logs"],
)
check(
    "Detay: sadece bu job'a ait mail log'ları dönüyor",
    len(detail["mail_logs"]) == 1 and detail["mail_logs"][0]["sender_email"] == "test@ornek.com",
    detail["mail_logs"],
)

resp = client.get("/api/jobs/watch_mail")
detail = resp.get_json()
check(
    "Detay: watch_mail'in kendi log'u diğer job'unkiyle karışmıyor",
    len(detail["service_logs"]) == 1 and detail["service_logs"][0]["detail"] == "baska@ornek.com",
    detail["service_logs"],
)

# ==========================================================
# izleyici rolü de görebiliyor (salt izleme ekranı)
# ==========================================================
izleyici_client = app.test_client()
login_test_client(app, izleyici_client, email="izleyici@local.test", role="izleyici")
resp = izleyici_client.get("/api/jobs")
check("Yetki: izleyici rolü de /api/jobs'u görebiliyor (200)", resp.status_code == 200, resp.status_code)

for _f in (_tmp_service_log, _tmp_mail_log, job_registry.HEARTBEAT_FILE):
    if os.path.exists(_f):
        os.remove(_f)

# ==========================================================
# OZET
# ==========================================================
print("=" * 60)
for status, name, detail in results:
    mark = "[OK]" if status == "PASS" else "[FAIL]"
    line = f"{mark} {name}"
    if status == "FAIL":
        line += f"  -> {detail}"
    print(line)

print("=" * 60)
print(f"TOPLAM: {passed + failed} senaryo | BASARILI: {passed} | BASARISIZ: {failed}")
if failed:
    raise SystemExit(1)
