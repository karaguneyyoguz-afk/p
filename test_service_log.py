# -*- coding: utf-8 -*-
"""
service_log.py (kayit/okuma/actor) ve bunu kullanan /api/service-logs* uc
noktalarinin sozlesmesini dogrular. Ag baglantisi gerektirmez.
"""

import os
import sys
import tempfile

if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import service_log

# Test'ler kendi gecici log dosyasini kullansin, gercek servis logunu etkilemesin.
_TEST_LOG_FILE = os.path.join(os.path.dirname(__file__), "_test_service_requests_log.jsonl")
service_log.LOG_FILE = _TEST_LOG_FILE
if os.path.exists(_TEST_LOG_FILE):
    os.remove(_TEST_LOG_FILE)

# Temp SQLite DB for the login below -- must be set before `from app import
# app` (app.py reads DATABASE_URL at import time). Never touches the real
# instance/enigma.db.
_tmp_db = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
_tmp_db.close()
os.environ["DATABASE_URL"] = f"sqlite:///{_tmp_db.name}"

from app import app  # noqa: E402  (once test dosya yolu override edilmeli)
from dev_test_helpers import login_test_client  # noqa: E402

# Girisin kendi audit-trail POST'u da service_log'a yazilir -- asagidaki
# testler sifirdan saydigi icin onu hemen temizliyoruz.
client = app.test_client()
csrf_token = login_test_client(app, client)
service_log.clear_service_events()
# app.py itself calls set_actor('panel') at import time (see app.py) -- reset
# back to the module's real default so the "varsayilan" check below still
# tests what it says it tests, unaffected by having imported app up here.
service_log.set_actor("sistem")

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


# ==========================================================
# set_actor / get_actor
# ==========================================================
check("get_actor: varsayilan 'sistem'", service_log.get_actor() == "sistem")
service_log.set_actor("panel")
check("set_actor/get_actor: 'panel' olarak degisir", service_log.get_actor() == "panel")

# ==========================================================
# record_service_event / read_service_events
# ==========================================================
record = service_log.record_service_event("csm_api", "create_ticket", "success", detail="#123")
check(
    "record_service_event: kaydedilen actor, o anki set_actor degeriyle esler",
    record["actor"] == "panel",
    record,
)
check("record_service_event: service/action/status dogru", record["service"] == "csm_api" and record["status"] == "success")

service_log.set_actor("sistem")
service_log.record_service_event("gmail_imap", "connect", "failed", detail="timeout")

events = service_log.read_service_events(limit=10)
check("read_service_events: 2 kayit da geri geliyor", len(events) == 2, events)
check("read_service_events: en yeni kayit basta (ters kronolojik)", events[0]["service"] == "gmail_imap", events)

service_log.clear_service_events()
check("clear_service_events: temizledikten sonra bos liste doner", service_log.read_service_events() == [])

# ==========================================================
# Endpoint sozlesmesi (Flask test client) -- birkac farkli kayit uretip
# filtrelerin gercekten daralttigini dogrular.
# ==========================================================
service_log.set_actor("panel")
service_log.record_service_event("csm_api", "create_ticket", "success", detail="#1")
service_log.record_service_event("csm_api", "create_ticket", "failed", detail="HTTP 500")
service_log.set_actor("sistem")
service_log.record_service_event("gmail_imap", "connect", "success", detail="ok")

resp = client.get("/api/service-logs?limit=2")
check("GET /api/service-logs?limit=2 -> 200", resp.status_code == 200, resp.status_code)
body = resp.get_json() or {}
check(
    "service-logs: limit/offset/total alanlarini iceriyor",
    {"logs", "total", "limit", "offset"} <= set(body),
    body,
)
check("service-logs: total=3, ama sayfa limit'e uyup 2 kayit doner", body.get("total") == 3 and len(body.get("logs", [])) == 2, body)

resp = client.get("/api/service-logs?service=csm_api&status=failed")
matched = (resp.get_json() or {}).get("logs", [])
check(
    "service-logs: service+status filtresiyle sadece eslesen 1 kayit doner",
    resp.status_code == 200 and len(matched) == 1 and matched[0]["detail"] == "HTTP 500",
    matched,
)

resp = client.get("/api/service-logs?actor=sistem")
matched = (resp.get_json() or {}).get("logs", [])
check(
    "service-logs: actor filtresiyle sadece 'sistem' kaynakli kayit doner",
    resp.status_code == 200 and len(matched) == 1 and matched[0]["service"] == "gmail_imap",
    matched,
)

resp = client.get("/api/service-logs/summary")
check("GET /api/service-logs/summary -> 200", resp.status_code == 200, resp.status_code)
summary = resp.get_json() or {}
check(
    "service-logs/summary: her bilinen servis icin ozet var",
    {"csm_api", "gmail_imap", "panel_api"} <= set(summary.get("services", {})),
    summary,
)
check(
    "service-logs/summary: csm_api icin 1 basarili + 1 basarisiz sayiyor",
    summary["services"]["csm_api"]["success_count"] == 1
    and summary["services"]["csm_api"]["failed_count"] == 1,
    summary["services"]["csm_api"],
)

resp = client.post("/api/service-logs/clear", headers={"X-CSRF-Token": csrf_token})
check("POST /api/service-logs/clear -> success", resp.status_code == 200 and resp.get_json().get("success") is True)
# Not: app.py'nin after_request audit-trail'i POST /api/service-logs/clear'in
# KENDİSİNİ de bir panel_api kaydi olarak loglar (clear_service_events()
# calisip dosyayi bosalttiktan SONRA calisir) -- yani clear sonrasi log
# tamamen bos degil, sadece bu tek audit kaydini icerir.
remaining = service_log.read_service_events()
check(
    "clear sonrasi tek kayit kalir: clear istegin kendi audit-trail'i",
    len(remaining) == 1 and remaining[0]["action"] == "POST /api/service-logs/clear",
    remaining,
)

# Test bitince kendi gecici dosyasini temizle.
if os.path.exists(_TEST_LOG_FILE):
    os.remove(_TEST_LOG_FILE)

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
