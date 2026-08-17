"""
Email Automation System - Main Application

Orchestrates email retrieval, validation, and CSM ticket creation.
"""

import sys
from mail_processor import EmailProcessor, EmailCategorizer, send_notification_email
from validators import contains_profanity
from csm_api import CSMAPIClient, TicketPayloadBuilder
from utils import clean_subject_line


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
    print(f"From: {sender_email} ({sender_name})")
    print(f"Subject: {subject}")
    
    # Clean subject line
    clean_subject = clean_subject_line(subject)
    
    # Check for profanity/hate speech
    if contains_profanity(f"{clean_subject} {body}"):
        print("❌ RESULT: Email contains profanity/hate speech!")
        print("❌ Ticket not created.")
        
        notification_body = (
            "Your email has been rejected because it contains inappropriate language or offensive content. "
            "Your request has not been created and processed."
        )
        send_notification_email(sender_email, subject, notification_body)
        print("-" * 50 + "\n")
        return
    
    print("✅ RESULT: Content is clean.")
    
    # Categorize email
    categorization = categorizer.categorize(clean_subject, body, sender_email)
    print(f"📌 Classification: {categorization['classification']}")
    
    # Check for missing required fields
    if categorization.get("missing_fields"):
        missing_fields_str = "\n".join([f"- {field}" for field in categorization["missing_fields"]])
        print(f"⚠️ MISSING/INVALID INFORMATION DETECTED! Ticket will not be created.")
        print(f"Missing Fields:\n{missing_fields_str}")
        
        notification_body = (
            "We detected missing or invalid information in your invoice request:\n\n"
            f"{missing_fields_str}\n\n"
            "Please reply with the correct information (valid ID number and complete address)."
        )
        send_notification_email(sender_email, subject, notification_body)
        print("-" * 50 + "\n")
        return
    
    # Create CSM ticket
    print("🔄 Creating ticket in CSM system...")
    payload = TicketPayloadBuilder.build_payload(
        sender_email,
        sender_name,
        subject,
        body,
        categorization
    )
    
    success = csm_client.create_ticket(payload)
    
    if not success:
        print("⚠️ Failed to create ticket in CSM")
    
    print("-" * 50 + "\n")


def main() -> None:
    """Main application entry point."""
    print("=" * 50)
    print("📧 EMAIL AUTOMATION SYSTEM")
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
            print("📌 No unread emails found. Checking recent emails...\n")
            email_ids = processor.get_recent_emails(count=1)
            
            if not email_ids:
                print("No emails to process.")
                return
        
        print(f"📬 Processing {len(email_ids)} email(s)...\n")
        
        # Process each email
        for email_id in email_ids:
            email_message = processor.fetch_email(email_id)
            
            if email_message:
                process_email(email_message, processor, categorizer, csm_client)
        
        print("=" * 50)
        print("✅ EMAIL PROCESSING COMPLETE")
        print("=" * 50)
    
    except Exception as e:
        print(f"❌ Application error: {e}")
        sys.exit(1)
    
    finally:
        # Disconnect from email server
        processor.disconnect()


if __name__ == "__main__":
    main()
