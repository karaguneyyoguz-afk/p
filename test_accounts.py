# -*- coding: utf-8 -*-
"""
Login, kilitlenme (lockout), effective_screens formulu ve require_screen
decorator'inin 401/403/gecis davranisini kontrol eder. Gercek CSM/IMAP
cagrisi YAPILMAZ. Kendi gecici SQLite dosyasinda calisir, mevcut
instance/enigma.db'ye DOKUNMAZ.
"""

import os
import sys
import tempfile

if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

# Her test calistirmasinda temiz bir SQLite dosyasi -- gercek admin
# hesabinin/verisinin bulundugu instance/enigma.db'yi ASLA kullanma.
_TMP_DB = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
_TMP_DB.close()
os.environ["DATABASE_URL"] = f"sqlite:///{_TMP_DB.name}"

from app import app
from accounts import attempt_login, hash_password, verify_password, LOCKOUT_THRESHOLD
from models import User, UserScreenOverride, db
from screens import effective_screens, ROLE_SCREENS

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


with app.app_context():
    db.create_all()

    # ==========================================================
    # password hashing
    # ==========================================================
    h = hash_password("dogru-sifre-123")
    check("hash_password: verify_password dogru sifreyle True doner", verify_password("dogru-sifre-123", h))
    check("hash_password: verify_password yanlis sifreyle False doner", not verify_password("yanlis-sifre", h))

    # ==========================================================
    # effective_screens formulu
    # ==========================================================
    operator = User(email="op@test.com", password_hash=h, role="operator", is_active=True)
    db.session.add(operator)
    db.session.commit()

    check(
        "effective_screens: override yokken rol varsayilanina esit",
        effective_screens(operator) == ROLE_SCREENS["operator"],
        effective_screens(operator),
    )

    db.session.add(UserScreenOverride(user_id=operator.id, screen_key="tickets", allow=False))
    db.session.commit()
    check(
        "effective_screens: deny override rolden geleni cikarir",
        "tickets" not in effective_screens(operator) and "dashboard" in effective_screens(operator),
        effective_screens(operator),
    )

    db.session.add(UserScreenOverride(user_id=operator.id, screen_key="reports", allow=True))
    db.session.commit()
    check(
        "effective_screens: grant override rolde olmayani ekler",
        "reports" in effective_screens(operator),
        effective_screens(operator),
    )
    check(
        "effective_screens: deny+grant ayni anda dogru birlesiyor",
        effective_screens(operator) == (ROLE_SCREENS["operator"] - {"tickets"}) | {"reports"},
        effective_screens(operator),
    )

    admin = User(email="admin2@test.com", password_hash=h, role="admin", is_active=True)
    db.session.add(admin)
    db.session.commit()
    check(
        "effective_screens: admin rolu 'users' dahil tum ekranlari kapsar",
        "users" in effective_screens(admin) and effective_screens(admin) == ROLE_SCREENS["admin"],
        effective_screens(admin),
    )

    yonetici = User(email="yonetici@test.com", password_hash=h, role="yonetici", is_active=True)
    db.session.add(yonetici)
    db.session.commit()
    check(
        "effective_screens: yonetici 'users' HARIC hepsini kapsar",
        "users" not in effective_screens(yonetici) and "dashboard" in effective_screens(yonetici),
        effective_screens(yonetici),
    )

    # ==========================================================
    # attempt_login + lockout
    # ==========================================================
    login_user = User(email="login@test.com", password_hash=hash_password("gercek-sifre"), role="izleyici", is_active=True)
    db.session.add(login_user)
    db.session.commit()

    ok_user, err = attempt_login("login@test.com", "gercek-sifre")
    check("attempt_login: dogru bilgiyle basarili, hata yok", ok_user is not None and err is None)

    _, err = attempt_login("login@test.com", "yanlis-sifre")
    check("attempt_login: yanlis sifrede kullanici None, jenerik hata doner", "hatalı" in (err or "").lower())

    _, err = attempt_login("olmayan@test.com", "herhangi")
    check(
        "attempt_login: olmayan kullanici ile AYNI jenerik hata doner (enumeration onlenir)",
        err == "E-posta veya şifre hatalı.",
    )

    inactive_user = User(email="pasif@test.com", password_hash=hash_password("sifre123"), role="izleyici", is_active=False)
    db.session.add(inactive_user)
    db.session.commit()
    _, err = attempt_login("pasif@test.com", "sifre123")
    check("attempt_login: pasif hesap ozel mesajla reddedilir", "pasif" in (err or "").lower())

    lockout_user = User(email="lockout@test.com", password_hash=hash_password("dogru123"), role="izleyici", is_active=True)
    db.session.add(lockout_user)
    db.session.commit()
    for _ in range(LOCKOUT_THRESHOLD):
        attempt_login("lockout@test.com", "yanlis")
    _, err = attempt_login("lockout@test.com", "dogru123")
    check(
        f"attempt_login: {LOCKOUT_THRESHOLD} basarisiz denemeden sonra DOGRU sifre bile kilitli hesabi acmaz",
        "kilitli" in (err or "").lower(),
        err,
    )

    # ==========================================================
    # require_screen decorator (Flask test client uzerinden 401/403/gecis)
    # ==========================================================
    client = app.test_client()

    resp = client.get("/api/tickets")
    check("require_screen: giris yapilmamis istek 401 doner", resp.status_code == 401, resp.get_json())

    resp = client.post(
        "/api/auth/login", json={"email": "op@test.com", "password": "dogru-sifre-123"}
    )
    check("login endpoint: dogru bilgiyle 200 + csrf_token doner", resp.status_code == 200 and resp.get_json().get("csrf_token"))

    resp = client.get("/api/tickets")
    check(
        "require_screen: 'tickets' izni deny override'la kaldirilmisti -> giris yapmis olsa da 403",
        resp.status_code == 403,
        resp.get_json(),
    )

    resp = client.get("/api/status")
    check("require_screen: 'dashboard' izni var -> 200 gecer", resp.status_code == 200, resp.get_json())

    resp = client.get("/api/users")
    check("require_screen: operator 'users' ekranina giremez -> 403", resp.status_code == 403, resp.get_json())

    resp = client.post("/api/auth/logout")
    check("logout: CSRF token'siz istek 403 doner (mutating request korumasi)", resp.status_code == 403, resp.get_json())

    resp = client.get("/api/status")
    check("require_screen: logout denemesi CSRF'de reddedildigi icin oturum HALA acik", resp.status_code == 200)


print("=" * 60)
for status, name, detail in results:
    mark = "[OK]" if status == "PASS" else "[FAIL]"
    line = f"{mark} {name}"
    if status == "FAIL":
        line += f"  -> {detail}"
    print(line)

print("=" * 60)
print(f"TOPLAM: {passed + failed} senaryo | BASARILI: {passed} | BASARISIZ: {failed}")

with app.app_context():
    db.engine.dispose()  # release the SQLite file handle before deleting (required on Windows)
try:
    os.unlink(_TMP_DB.name)
except OSError:
    pass  # best-effort cleanup -- a leftover temp file isn't worth failing the suite over

if failed:
    raise SystemExit(1)
