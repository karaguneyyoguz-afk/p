"""
Email Automation System - Watch Mode

Sürekli çalışır, belirli aralıklarla gelen kutusunu kontrol eder ve okunmamış
her yeni e-postayı main.py ile aynı mantıkla (process_email) otomatik işler.
Durdurmak için Ctrl+C.
"""

import time
import imaplib

from mail_processor import EmailProcessor, EmailCategorizer
from csm_api import CSMAPIClient
from main import process_email

POLL_SECONDS = 10
RECONNECT_RETRY_SECONDS = 15


def safe_connect(processor: EmailProcessor) -> None:
    """
    processor.connect() basarili olana kadar (DNS/aginin gecici kesintisi dahil)
    sonsuz dener; hicbir istisnayi disariya sizdirmaz. Bu fonksiyon dismadan
    donerse baglanti kurulmus demektir.
    """
    while True:
        try:
            processor.connect()
            return
        except Exception as e:
            print(f"⚠️ Bağlantı kurulamadı ({e}), {RECONNECT_RETRY_SECONDS} sn sonra tekrar denenecek...")
            time.sleep(RECONNECT_RETRY_SECONDS)


def watch() -> None:
    processor = EmailProcessor(username=None, password=None)
    categorizer = EmailCategorizer()
    csm_client = CSMAPIClient()

    safe_connect(processor)
    print(f"👀 İzleme modu başladı. Her {POLL_SECONDS} saniyede bir yeni mail kontrol edilecek. Durdurmak için Ctrl+C.\n")

    try:
        while True:
            # Not: dongu govdesinin TAMAMI try/except icinde -- sadece
            # get_unread_emails() degil, fetch/process sirasinda da baglanti
            # kopabiliyor (Gmail IMAP bosta kalinca baglantiyi kapatiyor,
            # yerel ag/DNS de gecici kesilebiliyor). Yakalanmayan HICBIR hata
            # bu dongudan disariya sizmamali; aksi halde izleme sessizce
            # tamamen durur (canli ortamda gozlemlendi).
            try:
                email_ids = processor.get_unread_emails()
                if email_ids:
                    print(f"📬 {len(email_ids)} yeni mail bulundu, işleniyor...\n")
                    for email_id in email_ids:
                        email_message = processor.fetch_email(email_id)
                        if email_message:
                            process_email(email_message, processor, categorizer, csm_client)
            except (imaplib.IMAP4.abort, imaplib.IMAP4.error, OSError) as e:
                print(f"⚠️ IMAP bağlantısı koptu ({e}), yeniden bağlanılıyor...")
                try:
                    processor.disconnect()
                except Exception:
                    pass
                safe_connect(processor)
            except Exception as e:
                print(f"⚠️ Beklenmeyen hata, izleme devam ediyor: {e}")

            time.sleep(POLL_SECONDS)
    except KeyboardInterrupt:
        print("\n🛑 İzleme durduruldu.")
    finally:
        try:
            processor.disconnect()
        except Exception:
            pass


if __name__ == "__main__":
    watch()
