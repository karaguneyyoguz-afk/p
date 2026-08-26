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
    send_missing_fields_email, send_vendor_redirect_email,
    send_bulk_kaydirma_summary_email, send_unclear_request_email,
)
from validators import (
    contains_profanity, extract_reservation_number, detect_priority_level,
    is_vendor_finance_correspondence
)
from csm_api import CSMAPIClient, TicketPayloadBuilder
from phishing_check import analyze_mail
from utils import clean_subject_line, clean_mailto_artifacts, normalize_turkish_characters
from logging_utils import record_mail_event


def _process_bulk_kaydirma_email(
    processor: EmailProcessor,
    email_message,
    sender_email: str,
    subject: str,
    body: str,
) -> None:
    """Handles the "toplu kaydırma" mail-trigger branch of process_email --
    split out since it's a fundamentally different shape of work (many
    linked tickets from one Excel, not one ticket from the mail body)."""
    import io
    from bulk_shift import parse_excel_rows, process_rows

    excel_bytes = processor.extract_excel_attachment(email_message)
    if excel_bytes is None:
        print("⚠️ Toplu kaydırma maili ama Excel eki bulunamadı, atlanıyor.")
        record_mail_event(
            event="email_processed",
            status="failed",
            sender_email=sender_email,
            subject=subject,
            reason="Toplu kaydırma maili tespit edildi ama Excel eki bulunamadı",
            classification="bulk_kaydirma_no_attachment",
            mail_body=body,
        )
        return

    try:
        rows = parse_excel_rows(io.BytesIO(excel_bytes))
    except ValueError as e:
        print(f"⚠️ Toplu kaydırma Excel'i okunamadı: {e}")
        record_mail_event(
            event="email_processed",
            status="failed",
            sender_email=sender_email,
            subject=subject,
            reason=f"Toplu kaydırma Excel'i okunamadı: {e}",
            classification="bulk_kaydirma_excel_error",
            mail_body=body,
        )
        return

    if not rows:
        print("⚠️ Toplu kaydırma Excel'inde işlenecek satır bulunamadı.")
        record_mail_event(
            event="email_processed",
            status="failed",
            sender_email=sender_email,
            subject=subject,
            reason="Toplu kaydırma Excel'inde işlenecek satır bulunamadı",
            classification="bulk_kaydirma_empty",
            mail_body=body,
        )
        return

    missing_parent_rows = [r["reservation_no"] for r in rows if not r["parent_ticket_uuid"]]
    if missing_parent_rows:
        print(f"⚠️ parentTicketUUID eksik: {', '.join(missing_parent_rows[:10])}")
        record_mail_event(
            event="email_processed",
            status="failed",
            sender_email=sender_email,
            subject=subject,
            reason=f"parentTicketUUID eksik satırlar: {', '.join(missing_parent_rows[:10])}",
            classification="bulk_kaydirma_missing_parent",
            mail_body=body,
        )
        return

    try:
        summary = process_rows(rows)
    except RuntimeError as e:
        print(f"❌ Toplu kaydırma: bearer token alınamadı: {e}")
        record_mail_event(
            event="email_processed",
            status="failed",
            sender_email=sender_email,
            subject=subject,
            reason=f"CSM token alınamadı: {e}",
            classification="bulk_kaydirma_token_error",
            mail_body=body,
        )
        return

    print(f"📊 Toplu kaydırma: {summary['success_count']}/{summary['total']} başarılı")
    record_mail_event(
        event="ticket_created" if summary["success_count"] > 0 else "ticket_not_created",
        status="success" if summary["failed_count"] == 0 else "failed",
        sender_email=sender_email,
        subject=subject,
        reason=f"Toplu kaydırma: {summary['success_count']}/{summary['total']} ilişkili ticket oluşturuldu",
        classification="bulk_kaydirma",
        ticket_details=summary,
        mail_body=body,
    )
    send_bulk_kaydirma_summary_email(sender_email, subject, summary)


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

    print("-" * 50)
    print(f"Gönderen: {sender_email} ({sender_name})")
    print(f"Konu: {subject}")

    # Automated bounce/delivery-failure notification (mailer-daemon, not a
    # person) -- never a ticket, never a reply (replying to mailer-daemon is
    # a no-op at best, a bounce loop at worst). Checked first: the most
    # unambiguous "this isn't a customer" signal there is.
    if processor.is_bounce_notification(email_message, subject):
        print("📪 SONUÇ: Teslim edilemedi bildirimi (bounce) tespit edildi, atlanıyor.")
        record_mail_event(
            event="email_processed",
            status="skipped",
            sender_email=sender_email,
            subject=subject,
            reason="Otomatik teslim edilemedi bildirimi (mailer-daemon) -- ticket oluşturulmadı",
            classification="bounce_notification",
            mail_body=body,
        )
        print("-" * 50 + "\n")
        return

    # Phishing/spoofing şüphesi (bkz. phishing_check.py) -- görünen ad
    # sahteciliği, gönderen alan adının typosquat'ı, Reply-To yönlendirmesi
    # veya gizli/şüpheli linkler tespit edilirse ticket AÇILMAZ; mail
    # kategorize edilmeden en baştan karantinaya (blocked + phishing_suspect
    # sınıflandırması) düşer, manuel incelemeye bırakılır. bulk_kaydirma
    # tetikleyicisi de dahil her şeyden önce kontrol edilir -- o akış tek
    # başına subject eşleşmesiyle tetiklendiği için sahte bir "toplu
    # kaydırma" maili buradan geçmeden onu tetikleyemesin diye.
    phishing_result = analyze_mail(email_message, sender_email, sender_name, body)
    if phishing_result["suspicious"]:
        print(f"🎣 SONUÇ: Phishing/sahtecilik şüphesi tespit edildi: {'; '.join(phishing_result['signals'])}")
        record_mail_event(
            event="email_processed",
            status="blocked",
            sender_email=sender_email,
            subject=subject,
            reason="Phishing/sahtecilik şüphesi -- ticket otomatik oluşturulmadı, manuel inceleme gerekiyor",
            details="; ".join(phishing_result["signals"]),
            classification="phishing_suspect",
            mail_body=body,
        )
        print("-" * 50 + "\n")
        return

    # Bulk/newsletter mail (List-Unsubscribe header or unsubscribe-link
    # boilerplate) never becomes a ticket and gets no automated reply --
    # checked before anything else since it's the most unambiguous signal
    # that this isn't a genuine customer message.
    if processor.is_bulk_marketing_email(email_message, body):
        print("📰 SONUÇ: Toplu pazarlama/haber bülteni maili tespit edildi, atlanıyor.")
        record_mail_event(
            event="email_processed",
            status="skipped",
            sender_email=sender_email,
            subject=subject,
            reason="Toplu pazarlama/haber bülteni maili (List-Unsubscribe/abonelik iptali tespit edildi)",
            classification="bulk_marketing",
            mail_body=body,
        )
        print("-" * 50 + "\n")
        return

    # Mail body is (almost) just a bare link with no real question/request of
    # its own (see EmailProcessor.is_link_only_content) -- not phishing, not
    # marketing, but not a support request either; without this it fell
    # through every classification branch into the TESIS_ILETISIM catch-all
    # and became a ticket for a mail that isn't asking anything (observed
    # live: a mail whose entire body was one YouTube link).
    if processor.is_link_only_content(body):
        print("🔗 SONUÇ: Mail yalnızca bir link içeriyor, gerçek bir talep tespit edilemedi, atlanıyor.")
        record_mail_event(
            event="email_processed",
            status="skipped",
            sender_email=sender_email,
            subject=subject,
            reason="Mail gövdesi yalnızca bir link içeriyor -- gerçek bir destek talebi tespit edilemedi",
            classification="link_only_content",
            mail_body=body,
        )
        print("-" * 50 + "\n")
        return

    # Mail-triggered Toplu Kaydırma (bulk reservation shift): "toplu
    # kaydırma" in the subject + an .xlsx attachment creates one CSM
    # "ilişkili ticket" (LINKED_TICKET) per row via bulk_shift.py -- the same
    # PROD flow the panel's Toplu Kaydırma page uses. Checked before the
    # normal profanity/vendor/categorize path since this isn't a single-
    # ticket request at all.
    if processor.is_bulk_kaydirma_email(subject):
        print("📊 SONUÇ: Toplu kaydırma maili tespit edildi.")
        _process_bulk_kaydirma_email(processor, email_message, sender_email, subject, body)
        print("-" * 50 + "\n")
        return

    # Read any image or PDF attachments (Vergi Levhası scan/export, kaşe
    # photo) up front -- only fed into categorization if the mail body itself
    # is missing invoice fields (see categorize's resolve_invoice_attributes).
    # Gated on invoice-context keywords so OCR doesn't run on unrelated PDF
    # attachments (uçak/otobüs bileti vb.) -- those are routed to the right
    # kırılım by subject/body keywords alone, no attribute extraction needed.
    attachment_fields = None
    normalized_for_ocr_gate = normalize_turkish_characters(f"{subject} {body}")
    looks_invoice_related = any(
        keyword in normalized_for_ocr_gate for keyword in EmailCategorizer.INVOICE_CONTEXT_KEYWORDS
    )
    if looks_invoice_related:
        ocr_attachments = processor.extract_ocr_attachments(email_message)
        if ocr_attachments:
            from ocr_utils import extract_invoice_fields_from_attachments
            attachment_fields = extract_invoice_fields_from_attachments(ocr_attachments)

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
    categorization = categorizer.categorize(clean_subject, body, sender_email, attachment_fields)
    print(f"📌 Sınıflandırma: {categorization['classification']}")

    # Hiçbir alt kırılımın içeriğine uymayan mailler (bkz.
    # EmailCategorizer.DOMAIN_RELEVANCE_KEYWORDS) artık varsayılan
    # TESIS_ILETISIM'e düşüp ticket açmıyor -- konuyla hiç ilgisi olmayan bir
    # mail (ör. "bugün havalar nasıl") gerçek bir talep değildir; ticket
    # açılmadan netleştirme cevabı gönderilir.
    if categorization.get("sub_category_code") == "UNCLEAR_REQUEST":
        print("❓ SONUÇ: Mail hiçbir kategoriye uymuyor, net bir talep tespit edilemedi.")
        send_unclear_request_email(sender_email, subject, sender_name)
        record_mail_event(
            event="ticket_not_created",
            status="skipped",
            sender_email=sender_email,
            subject=subject,
            reason="Mail içeriği hiçbir alt kırılıma uymuyor -- net bir talep tespit edilemedi",
            classification="unclear_request",
            mail_body=body,
        )
        print("-" * 50 + "\n")
        return

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
