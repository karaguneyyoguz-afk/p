"""
Mail Processor Module

Handles email retrieval, parsing, and categorization for ticket routing.
"""

import imaplib
import email
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Dict, List, Tuple, Optional
from config import (
    EMAIL_USER, EMAIL_PASS, IMAP_SERVER,
    SMTP_SERVER, SMTP_PORT, CHANNEL_ID,
    TICKET_TYPE_THANK_YOU, TICKET_TYPE_COMPLAINT,
    TICKET_TYPE_INFO_REQUEST, CATEGORY_THANK_YOU,
    CATEGORY_COMPLAINT, CATEGORY_FACILITY,
    SUB_CATEGORY_THANK_YOU_GENERAL, SUB_CATEGORY_THANK_YOU_GUIDE,
    SUB_CATEGORY_THANK_YOU_CONSULTANT, SUB_CATEGORY_COMPLAINT_INVOICE,
    SUB_CATEGORY_FACILITY_CONTACT, MAIL_CHARSET_DEFAULT,
    MAIL_CHARSET_FALLBACK
)
from utils import (
    decode_email_header, extract_sender_info, 
    clean_subject_line, normalize_turkish_characters
)
from validators import contains_profanity, extract_invoice_attributes


class EmailProcessor:
    """Handles email retrieval and processing."""
    
    def __init__(self, username: Optional[str] = None, password: Optional[str] = None):
        """
        Initialize email processor.
        
        Args:
            username: Email account username (uses env var if None)
            password: Email account password (uses env var if None)
        """
        self.username = username or EMAIL_USER
        self.password = password or EMAIL_PASS
        self.mail_connection = None
    
    def connect(self) -> None:
        """Establish IMAP connection to email server."""
        try:
            self.mail_connection = imaplib.IMAP4_SSL(IMAP_SERVER)
            self.mail_connection.login(self.username, self.password)
            self.mail_connection.select("inbox")
            print("✅ Connected to email server")
        except Exception as e:
            print(f"❌ Email connection error: {e}")
            raise
    
    def disconnect(self) -> None:
        """Close IMAP connection."""
        if self.mail_connection:
            try:
                self.mail_connection.logout()
                print("✅ Disconnected from email server")
            except Exception as e:
                print(f"⚠️ Error disconnecting: {e}")
    
    def get_unread_emails(self) -> List[bytes]:
        """
        Retrieve unread emails.
        
        Returns:
            List of email message IDs
        """
        status, messages = self.mail_connection.search(None, 'UNSEEN')
        email_ids = messages[0].split()
        return email_ids
    
    def get_recent_emails(self, count: int = 1) -> List[bytes]:
        """
        Retrieve recent emails when no unread emails exist.
        
        Args:
            count: Number of recent emails to retrieve
            
        Returns:
            List of email message IDs
        """
        status, all_messages = self.mail_connection.search(None, 'ALL')
        all_ids = all_messages[0].split()
        
        if all_ids:
            return all_ids[-count:]
        return []
    
    def fetch_email(self, email_id: bytes) -> Optional[email.message.Message]:
        """
        Fetch and parse a single email.
        
        Args:
            email_id: Email message ID
            
        Returns:
            Parsed email message object or None
        """
        try:
            status, msg_data = self.mail_connection.fetch(email_id, "(RFC822)")
            
            for response_part in msg_data:
                if isinstance(response_part, tuple):
                    return email.message_from_bytes(response_part[1])
        except Exception as e:
            print(f"❌ Error fetching email: {e}")
        
        return None
    
    @staticmethod
    def extract_email_content(msg: email.message.Message) -> Tuple[str, str, str, str]:
        """
        Extract subject, sender info, and body from email message.
        
        Args:
            msg: Email message object
            
        Returns:
            Tuple of (subject, sender_email, sender_name, body)
        """
        subject = decode_email_header(msg["Subject"]) if msg["Subject"] else ""
        raw_from = msg.get("From", "")
        sender_email, sender_name = extract_sender_info(raw_from)
        
        body = ""
        if msg.is_multipart():
            # Extract first text/plain part (ignore attachments)
            for part in msg.walk():
                if part.get_content_type() == "text/plain":
                    if "attachment" not in str(part.get("Content-Disposition", "")):
                        charset = part.get_content_charset() or MAIL_CHARSET_DEFAULT
                        try:
                            body = part.get_payload(decode=True).decode(charset, errors="ignore")
                        except Exception:
                            body = part.get_payload(decode=True).decode(MAIL_CHARSET_FALLBACK, errors="ignore")
                        break
        else:
            # Single part message
            charset = msg.get_content_charset() or MAIL_CHARSET_DEFAULT
            try:
                body = msg.get_payload(decode=True).decode(charset, errors="ignore")
            except Exception:
                body = msg.get_payload(decode=True).decode(MAIL_CHARSET_FALLBACK, errors="ignore")
        
        return subject, sender_email, sender_name, body


class EmailCategorizer:
    """Categorizes emails and determines ticket routing."""
    
    THANK_YOU_KEYWORDS = [
        "tesekkur", "sagol", "tesekkurler", 
        "tesekkur ederim", "teşekkur"
    ]
    
    INVOICE_KEYWORDS = ["fatura", "efatura", "e-fatura"]
    
    GUIDE_KEYWORDS = ["rehber", "tur lideri", "oguz", "rehbere"]
    
    CONSULTANT_KEYWORDS = [
        "danisman", "temsilci", "cagri merkezi", "telefondaki"
    ]
    
    @staticmethod
    def categorize(subject: str, body: str, sender_email: str) -> Dict:
        """
        Categorize email and determine ticket type/category.
        
        Args:
            subject: Email subject line
            body: Email body content
            sender_email: Sender's email address
            
        Returns:
            Dictionary containing ticket categorization info
        """
        combined_text = f"{subject} {body}"
        normalized_text = normalize_turkish_characters(combined_text)
        
        # Check for invoice requests
        if any(keyword in normalized_text for keyword in EmailCategorizer.INVOICE_KEYWORDS):
            attributes, missing_fields = extract_invoice_attributes(combined_text, sender_email)
            return {
                "channel_id": CHANNEL_ID,
                "ticket_type_id": TICKET_TYPE_COMPLAINT,
                "category_id": CATEGORY_COMPLAINT,
                "sub_category_id": SUB_CATEGORY_COMPLAINT_INVOICE,
                "sub_category_code": "INVOICE_REQUEST",
                "attributes": attributes,
                "missing_fields": missing_fields,
                "classification": "COMPLAINT > INVOICE > INVOICE_REQUEST"
            }
        
        # Check for thank you messages
        if any(keyword in normalized_text for keyword in EmailCategorizer.THANK_YOU_KEYWORDS):
            # Determine sub-category based on keywords
            if any(kw in normalized_text for kw in EmailCategorizer.GUIDE_KEYWORDS):
                sub_category_id = SUB_CATEGORY_THANK_YOU_GUIDE
                sub_category_code = "GUIDE_THANK_YOU"
            elif any(kw in normalized_text for kw in EmailCategorizer.CONSULTANT_KEYWORDS):
                sub_category_id = SUB_CATEGORY_THANK_YOU_CONSULTANT
                sub_category_code = "CONSULTANT_THANK_YOU"
            else:
                sub_category_id = SUB_CATEGORY_THANK_YOU_GENERAL
                sub_category_code = "GENERAL_THANK_YOU"
            
            return {
                "channel_id": CHANNEL_ID,
                "ticket_type_id": TICKET_TYPE_THANK_YOU,
                "category_id": CATEGORY_THANK_YOU,
                "sub_category_id": sub_category_id,
                "sub_category_code": sub_category_code,
                "attributes": [],
                "missing_fields": [],
                "classification": f"THANK_YOU > THANK_YOU > {sub_category_code}"
            }
        
        # Default: General information request
        return {
            "channel_id": CHANNEL_ID,
            "ticket_type_id": TICKET_TYPE_INFO_REQUEST,
            "category_id": CATEGORY_FACILITY,
            "sub_category_id": SUB_CATEGORY_FACILITY_CONTACT,
            "sub_category_code": "FACILITY_CONTACT",
            "attributes": [],
            "missing_fields": [],
            "classification": "GENERAL > FACILITY > FACILITY_CONTACT"
        }


def send_notification_email(recipient_email: str, subject: str, body: str) -> None:
    """
    Send automatic notification email to recipient.
    
    Args:
        recipient_email: Recipient email address
        subject: Email subject
        body: Email body (notification message)
    """
    try:
        message = MIMEMultipart()
        message['From'] = EMAIL_USER
        message['To'] = recipient_email
        message['Subject'] = f"Re: {subject} - NOTIFICATION: Request Could Not Be Processed"
        
        formatted_body = f"Dear Customer,\n\n{body}\n\nBest regards."
        message.attach(MIMEText(formatted_body, 'plain', 'utf-8'))
        
        server = smtplib.SMTP_SSL(SMTP_SERVER, SMTP_PORT)
        server.login(EMAIL_USER, EMAIL_PASS)
        server.sendmail(EMAIL_USER, recipient_email, message.as_string())
        server.quit()
        
        print(f"✉️ [NOTIFICATION SENT] -> {recipient_email}")
    
    except Exception as e:
        print(f"❌ Error sending notification email: {e}")
