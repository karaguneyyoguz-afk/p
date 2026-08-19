"""
Email Automation System - Main Application

Orchestrates email retrieval, validation, and CSM ticket creation.
"""

import sys
from mail_processor import (
    EmailProcessor, EmailCategorizer, send_notification_email, 
    send_ticket_confirmation_email, send_rejection_email, 
    send_missing_fields_email
)
from validators import contains_profanity
from csm_api import CSMAPIClient, TicketPayloadBuilder
from utils import clean_subject_line
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
    
    # Categorize email
    categorization = categorizer.categorize(clean_subject, body, sender_email)
    print(f"📌 Sınıflandırma: {categorization['classification']}")
    
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
    
    payload = TicketPayloadBuilder.build_payload(
        sender_email,
        sender_name,
        subject,
        body,
        categorization,
        customer_id=customer_id
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
        record_mail_event(
            event="ticket_not_created",
            status="failed",
            sender_email=sender_email,
            subject=subject,
            reason="CSM API ticket oluşturamadı",
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
    main()
