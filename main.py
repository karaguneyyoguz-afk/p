"""
Email Automation System - Main Application

Orchestrates email retrieval, validation, and CSM ticket creation.
"""

import sys

# Not: Windows'ta konsol varsayilan olarak cp1254 (Turkce ANSI) kullanabiliyor,
# bu da print() icindeki emoji karakterlerinde UnicodeEncodeError'a yol aciyor
# (canli ortamda watch_mail.py'de gozlemlendi). stdout/stderr'i PYTHONIOENCODING
# ortam degiskenine bagli kalmadan burada UTF-8'e zorluyoruz.
if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if sys.stderr.encoding and sys.stderr.encoding.lower() != "utf-8":
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

from mail_processor import (
    EmailProcessor, EmailCategorizer, send_notification_email,
    send_ticket_confirmation_email, send_rejection_email,
    send_missing_fields_email, send_vendor_redirect_email
)
from validators import (
    contains_profanity, extract_reservation_number, detect_priority_level,
    is_vendor_finance_correspondence
)
from csm_api import CSMAPIClient, TicketPayloadBuilder
from utils import clean_subject_line, clean_mailto_artifacts
from logging_utils import record_mail_event


def process_email(
    email_message,
    processor: EmailProcessor,
    categorizer: EmailCategorizer,
    csm_client: CSMAPIClient
) -> None:
    """
    Process a single email message.
    
    Args:
        email_message: Parsed email message object
        processor: EmailProcessor instance
        categorizer: EmailCategorizer instance
        csm_client: CSM API client instance
    """
    # Extract email content
    subject, sender_email, sender_name, body = processor.extract_email_content(email_message)
    body = clean_mailto_artifacts(body)

    # OCR any image attachments (Vergi Levhası scan, kaşe photo) up front --
    # only fed into categorization if the mail body itself is missing
    # invoice fields (see EmailCategorizer.categorize's resolve_invoice_attributes).
    attachment_text = ""
    image_attachments = processor.extract_image_attachments(email_message)
    if image_attachments:
        from ocr_utils import extract_text_from_images
        attachment_text = extract_text_from_images(image_attachments)

    print("-" * 50)
    print(f"Gönderen: {sender_email} ({sender_name})")
    print(f"Konu: {subject}")
    
    # Clean subject line
    clean_subject = clean_subject_line(subject)
    
    # Check for profanity/hate speech
    if contains_profanity(f"{clean_subject} {body}"):
        print("❌ SONUÇ: E-posta küfür/hakaret içeriyor!")
        print("❌ Ticket oluşturulamadı.")
        
        send_rejection_email(sender_email, subject, sender_name)
        record_mail_event(
            event="email_processed",
            status="rejected",
            sender_email=sender_email,
            subject=subject,
            reason="Uygunsuz ifade veya hakaret tespit edildi",
            classification="rejected_content",
            mail_body=body,
        )
        print("-" * 50 + "\n")
        return
    
    print("✅ SONUÇ: İçerik temiz.")

    # Otel/tedarikci muhasebe birimlerinin gonderdigi ekstre/mutabakat/cari
    # hesap yazismalari -- bu kutunun ilgilenmedigi bir konu, ticket
    # OLUSTURULMAZ, sadece dogru adreslere yonlendirme maili gonderilir
    # (kullanici tarafindan bildirildi).
    if is_vendor_finance_correspondence(f"{clean_subject} {body}"):
        print("↪️ SONUÇ: B2B muhasebe yazışması (ekstre/mutabakat/cari hesap) tespit edildi.")
        print("↪️ Ticket oluşturulmadı, yönlendirme maili gönderiliyor.")

        send_vendor_redirect_email(sender_email, subject, sender_name)
        record_mail_event(
            event="email_processed",
            status="redirected",
            sender_email=sender_email,
            subject=subject,
            reason="B2B muhasebe yazışması (ekstre/mutabakat/cari hesap) -- ticket oluşturulmadı",
            classification="vendor_finance_redirect",
            mail_body=body,
        )
        print("-" * 50 + "\n")
        return

    # Categorize email
    categorization = categorizer.categorize(clean_subject, body, sender_email, attachment_text)
    print(f"📌 Sınıflandırma: {categorization['classification']}")

    # Not: kirilim ne olursa olsun, mailde "acil"/"opsiyon" gibi aciliyet
    # sinyalleri geciyorsa ticket'in Oncelik alani buna gore ayarlanmali
    # (kullanici tarafindan bildirilen genel kural). Belirli bir kirilimin
    # kendi mantigi zaten bir priority_level belirlemisse (ör. Kaydırma >
    # Otel/Operasyon Kaynaklı), bu genel kural onunla AYNI sonucu uretir; farkli
    # bir kirilimde de aynı sinyaller gecerse artik burada yakalanir.
    urgency_priority = detect_priority_level(body)
    if urgency_priority:
        categorization["priority_level"] = urgency_priority
        print(f"⚡ Aciliyet sinyali tespit edildi, Öncelik: {urgency_priority}")

    # Check for missing required fields
    if categorization.get("missing_fields"):
        missing_fields = categorization["missing_fields"]
        missing_fields_str = "\n".join([f"- {field}" for field in missing_fields])
        print(f"⚠️ EKSİK VEYA HATALI BİLGİ TESPİT EDİLDİ! Ticket oluşturulamayacak.")
        print(f"Eksik Alanlar:\n{missing_fields_str}")
        
        send_missing_fields_email(sender_email, subject, missing_fields, sender_name)
        record_mail_event(
            event="ticket_not_created",
            status="blocked",
            sender_email=sender_email,
            subject=subject,
            reason="Zorunlu alanlar eksik veya geçersiz",
            details=", ".join(missing_fields),
            classification=categorization.get("classification", ""),
            mail_body=body,
        )
        print("-" * 50 + "\n")
        return
    
    # Create CSM ticket
    print("🔄 CSM sistemi'nde ticket oluşturuluyor...")
    
    # Search for customer in database
    print("🔍 Müşteri veritabanında aranıyor...")
    customer_info = csm_client.search_customer_by_email(sender_email)
    customer_id = None
    if customer_info:
        customer_id = customer_info.get('id')
        print(f"✅ Kayıtlı müşteri bulundu. ID: {customer_id}")
    else:
        print(f"🆕 Müşteri bulunamadı - Potansiyel müşteri olarak kaydedilecek")
    
    # Not: kirilim ne olursa olsun, mailde bir rezervasyon numarasi geciyorsa
    # CSM/Etiya'dan ilgili urun kaydi cekilip ticket'a gomuluyor -- aksi
    # halde backoffice ekibi ticket icinde ilgili rezervasyona/urune
    # erisemiyor (canli ortamda musteri temsilcisinin "rezervasyon numarasi
    # paylasabilir misiniz" diye geri donmesiyle tespit edildi).
    related_product = None
    reservation_number = extract_reservation_number(body)
    if reservation_number:
        print(f"🔍 Rezervasyon numarası tespit edildi, ürün aranıyor: {reservation_number}")
        products = csm_client.search_product_by_reservation_number(reservation_number)
        if products:
            related_product = next(
                (p for p in products if p.get("serviceNumber") == reservation_number),
                products[0]
            )
            print(f"✅ Ürün bulundu ve ticket'a eklenecek: {related_product.get('name')}")

    payload = TicketPayloadBuilder.build_payload(
        sender_email,
        sender_name,
        subject,
        body,
        categorization,
        customer_id=customer_id,
        related_product=related_product
    )
    
    ticket_id = csm_client.create_ticket(payload)
    
    if ticket_id:
        print(f"📧 Müşteriye onay maili gönderiliyor...")
        send_ticket_confirmation_email(sender_email, subject, ticket_id, sender_name)
        record_mail_event(
            event="ticket_created",
            status="success",
            sender_email=sender_email,
            subject=subject,
            reason="Ticket başarıyla oluşturuldu",
            classification=categorization.get("classification", ""),
            ticket_id=ticket_id,
            ticket_details={
                "ticket_type": categorization.get("ticket_type_id"),
                "category": categorization.get("category_id"),
                "sub_category": categorization.get("sub_category_id"),
                "sub_category_code": categorization.get("sub_category_code", ""),
                "body_preview": body[:300],
            },
            mail_body=body,
        )
    else:
        print("⚠️ CSM'de ticket oluşturulamadı")
        send_notification_email(
            sender_email,
            subject,
            "Talebiniz teknik bir nedenle şu anda işleme alınamadı. Lütfen daha sonra tekrar deneyiniz."
        )
        record_mail_event(
            event="ticket_not_created",
            status="failed",
            sender_email=sender_email,
            subject=subject,
            reason="CSM API ticket oluşturamadı",
            details=csm_client.last_error,
            classification=categorization.get("classification", ""),
            mail_body=body,
        )
    
    print("-" * 50 + "\n")


def main() -> None:
    """Main application entry point."""
    print("=" * 50)
    print("📧 E-POSTA OTOMASYON SİSTEMİ")
    print("=" * 50 + "\n")
    
    # Initialize components
    processor = EmailProcessor(username=None, password=None)  # Will use env vars
    categorizer = EmailCategorizer()
    csm_client = CSMAPIClient()
    
    try:
        # Connect to email server
        processor.connect()
        
        # Get unread emails
        email_ids = processor.get_unread_emails()
        
        if not email_ids:
            print("📌 Okunmamış e-posta bulunamadı. Son gelen e-postalar kontrol ediliyor...\n")
            email_ids = processor.get_recent_emails(count=1)
            
            if not email_ids:
                print("İşlenecek e-posta bulunamadı.")
                return
        
        print(f"📬 {len(email_ids)} adet e-posta işleme alınıyor...\n")
        
        # Process each email
        for email_id in email_ids:
            email_message = processor.fetch_email(email_id)
            
            if email_message:
                process_email(email_message, processor, categorizer, csm_client)
            else:
                record_mail_event(
                    event="email_fetch",
                    status="failed",
                    reason="E-posta IMAP sunucusundan alınamadı",
                    details=f"IMAP ID: {email_id!r}",
                )
        
        print("=" * 50)
        print("✅ E-POSTA İŞLEME TAMAMLANDI")
        print("=" * 50)
    
    except Exception as e:
        print(f"❌ Uygulama hatası: {e}")
        record_mail_event(
            event="processor_error",
            status="failed",
            reason="Mail işleme sırasında beklenmeyen hata",
            details=str(e),
        )
        sys.exit(1)
    
    finally:
        # Disconnect from email server
        processor.disconnect()


if __name__ == "__main__":
    from service_log import set_actor
    set_actor("cli")
    main()
