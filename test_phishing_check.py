# -*- coding: utf-8 -*-
"""
phishing_check.py'nin sahtecilik/tuzak tespitlerini dogrular: gorunen ad
sahteciligi, gonderen alan adi typosquat'i, Reply-To yonlendirmesi, supheli
linkler (IP-literal, punycode, URL kisaltici) ve anchor/href uyusmazligi.
Aglantisi gerektirmez.

Ayni derecede onemlisi: bu bir musteri hizmetleri kutusu, DIS gonderen
NORMAL durum -- bu testler ayrica "sirf harici oldugu icin" hicbir seyin
yanlislikla supheli isaretlenmedigini de dogruluyor (false-positive korumasi).
"""

import sys
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.message import Message

if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from phishing_check import (
    analyze_mail,
    check_display_name_spoofing,
    check_reply_to_mismatch,
    check_sender_domain_typosquat,
    check_suspicious_links,
    find_anchor_href_mismatches,
    is_typosquat_domain,
)

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


def plain_msg(reply_to=None):
    msg = Message()
    msg["From"] = "musteri@gmail.com"
    if reply_to:
        msg["Reply-To"] = reply_to
    return msg


def html_msg(html):
    msg = MIMEMultipart("alternative")
    msg.attach(MIMEText(html, "html", "utf-8"))
    return msg


# ==========================================================
# 1) Normal musteri maili -- HICBIR sinyal tetiklenmemeli (false-positive korumasi)
# ==========================================================
result = analyze_mail(plain_msg(), "musteri@gmail.com", "Ahmet Yilmaz", "Merhaba, rezervasyonumla ilgili bilgi almak istiyorum.")
check("Normal-1: sıradan gmail.com müşterisi -> şüpheli değil", result["suspicious"] is False, result["signals"])

result = analyze_mail(plain_msg(), "musteri@hotmail.com", "Ayşe Kaya", "İptal etmek istiyorum, google.com üzerinden yorum da bıraktım.")
check("Normal-2: harici alan adına sıradan bir referans (google.com) tek başına şüpheli değil", result["suspicious"] is False, result["signals"])

# ==========================================================
# 2) Görünen ad sahteciliği
# ==========================================================
signal = check_display_name_spoofing("TatilBudur Destek", "destek@gmail-destek-tatilbudur.com")
check("Spoof-1: 'TatilBudur Destek' adı ama tatilbudur.com dışı adres -> tespit edildi", signal is not None, signal)

signal = check_display_name_spoofing("TatilBudur Destek", "destek@tatilbudur.com")
check("Spoof-2: gerçek tatilbudur.com adresinden 'TatilBudur' adı -> şüpheli DEĞİL", signal is None, signal)

signal = check_display_name_spoofing("Ahmet Yilmaz", "ahmet@gmail.com")
check("Spoof-3: marka adı geçmiyor -> şüpheli değil", signal is None, signal)

# ==========================================================
# 3) Gönderen alan adı typosquat
# ==========================================================
check("Typo-1: tatiibudur.com (i/l harf degisimi) -> tatilbudur.com taklidi", is_typosquat_domain("tatiibudur.com") == "tatilbudur.com")
check("Typo-2: tatil-budur.com (eklenen tire) -> tatilbudur.com taklidi", is_typosquat_domain("tatil-budur.com") == "tatilbudur.com")
check("Typo-3: tatilbudur.com (gercek adres) -> taklit degil", is_typosquat_domain("tatilbudur.com") is None)
check("Typo-4: gmail.com (alakasiz) -> taklit degil", is_typosquat_domain("gmail.com") is None)

signal = check_sender_domain_typosquat("destek@tatiibudur.com")
check("Typo-5: check_sender_domain_typosquat gonderen adresi uzerinden calisiyor", signal is not None, signal)

# ==========================================================
# 4) Reply-To yönlendirmesi
# ==========================================================
signal = check_reply_to_mismatch(plain_msg(reply_to="baskasi@kotu-adres.com"), "musteri@gmail.com")
check("ReplyTo-1: Reply-To farklı alan adına gidiyor -> tespit edildi", signal is not None, signal)

signal = check_reply_to_mismatch(plain_msg(reply_to="musteri@gmail.com"), "musteri@gmail.com")
check("ReplyTo-2: Reply-To aynı adres -> şüpheli değil", signal is None, signal)

signal = check_reply_to_mismatch(plain_msg(), "musteri@gmail.com")
check("ReplyTo-3: Reply-To header hiç yok -> şüpheli değil", signal is None, signal)

# ==========================================================
# 5) Şüpheli linkler (IP-literal, punycode, URL kısaltıcı)
# ==========================================================
signals = check_suspicious_links("Ödemenizi buradan tamamlayın: http://192.168.1.55/odeme", "")
check("Link-1: IP-literal adrese giden link -> tespit edildi", len(signals) == 1, signals)

signals = check_suspicious_links("Detaylar: http://xn--tatlbudur-x1a.com/kampanya", "")
check("Link-2: punycode/IDN alan adı -> tespit edildi", len(signals) == 1, signals)

signals = check_suspicious_links("Kısa link: https://bit.ly/3xample", "")
check("Link-3: URL kısaltıcı -> tespit edildi", len(signals) == 1, signals)

signals = check_suspicious_links("Bkz: https://tatilbudur.com/kampanya ve https://google.com", "")
check("Link-4: allowlist'teki + sıradan harici link -> hiçbiri şüpheli değil", len(signals) == 0, signals)

# ==========================================================
# 6) Anchor/href uyuşmazlığı (gizlenmiş link)
# ==========================================================
html = '<p>Devam etmek için <a href="http://kotu-site.ru/phish">tatilbudur.com</a> adresine gidin.</p>'
signals = find_anchor_href_mismatches(html)
check("Anchor-1: metin 'tatilbudur.com' gösteriyor ama href kotu-site.ru -> tespit edildi", len(signals) == 1, signals)

html = '<p>Devam etmek için <a href="https://tatilbudur.com/kampanya">tatilbudur.com</a> adresine gidin.</p>'
signals = find_anchor_href_mismatches(html)
check("Anchor-2: metin ve href aynı alan adı -> şüpheli değil", len(signals) == 0, signals)

# ==========================================================
# 7) Uçtan uca analyze_mail -- birden fazla sinyal aynı anda
# ==========================================================
msg = html_msg('<p><a href="http://sahte-tatilbudur.ru/giris">tatilbudur.com</a></p>')
msg["From"] = "TatilBudur Destek <destek@gmail-guvenlik.com>"
msg["Reply-To"] = "baskasi@baska-yer.com"
result = analyze_mail(msg, "destek@gmail-guvenlik.com", "TatilBudur Destek", "Hesabınızı doğrulayın.")
check(
    "E2E-1: sahte görünen ad + Reply-To yönlendirmesi + gizli link aynı anda -> şüpheli, birden fazla sinyal",
    result["suspicious"] is True and len(result["signals"]) >= 2,
    result["signals"],
)

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
