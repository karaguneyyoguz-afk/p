"""
Utilities Module

Common utility functions for text processing, email handling, and data transformation.
"""

import html as html_module
import re
from email.header import decode_header
from typing import Tuple

_HTML_SKIP_BLOCK_PATTERN = re.compile(r'<(script|style)\b[^>]*>.*?</\1>', re.IGNORECASE | re.DOTALL)
_HTML_TAG_PATTERN = re.compile(r'<[^>]+>')
_HTML_WHITESPACE_PATTERN = re.compile(r'[ \t]*\n[ \t]*\n[ \t\n]*')


def html_to_text(html: str) -> str:
    """
    Strip an HTML email body down to its readable text.

    Only used as a fallback for mail that has NO text/plain part (some
    marketing/newsletter senders only send text/html, or send a single-part
    HTML message) -- passing raw markup through as the ticket description or
    into keyword-based classification is worse than a plain-text approximation:
    tracking-pixel URLs and boilerplate ("Üyelikten Ayrıl" unsubscribe footers
    etc.) can spuriously match classification keywords, and CSM's ticket API
    rejects overly long/malformed descriptions (observed live: a 13KB raw-HTML
    newsletter body got "ticket.description" HTTP 500 from CSM).
    """
    if not html:
        return ""
    text = _HTML_SKIP_BLOCK_PATTERN.sub(' ', html)
    text = re.sub(r'<br\s*/?>', '\n', text, flags=re.IGNORECASE)
    text = re.sub(r'</(p|div|tr|table|li|h[1-6])>', '\n', text, flags=re.IGNORECASE)
    text = _HTML_TAG_PATTERN.sub(' ', text)
    text = html_module.unescape(text)
    text = re.sub(r'[ \t]+', ' ', text)
    text = _HTML_WHITESPACE_PATTERN.sub('\n\n', text)
    return text.strip()


def normalize_turkish_characters(text: str) -> str:
    """
    Normalize Turkish characters to ASCII equivalents.
    
    Args:
        text: Text containing Turkish characters
        
    Returns:
        str: Normalized text with Turkish chars converted to ASCII
    """
    text = text.lower()
    
    character_map = {
        'ş': 's', 'ç': 'c', 'ğ': 'g', 'ü': 'u', 
        'ö': 'o', 'ı': 'i', 'i̇': 'i'
    }
    
    for turkish_char, ascii_char in character_map.items():
        text = text.replace(turkish_char, ascii_char)
    
    return text


def decode_email_header(header_value: str) -> str:
    """
    Decode email header with proper encoding handling.
    
    Handles various character encodings (UTF-8, ISO-8859-9, etc.)
    
    Args:
        header_value: Raw header value to decode
        
    Returns:
        str: Decoded header string
    """
    if not header_value:
        return ""
    
    result = ""
    
    for content, encoding in decode_header(header_value):
        if isinstance(content, bytes):
            # Try to decode with specified encoding
            enc = encoding if encoding else "utf-8"
            try:
                result += content.decode(enc, errors="ignore")
            except Exception:
                # Fallback to ISO-8859-9 (Turkish encoding)
                result += content.decode("iso-8859-9", errors="ignore")
        else:
            result += str(content)
    
    return result.strip()


def extract_sender_info(raw_from: str) -> Tuple[str, str]:
    """
    Extract sender email and name from raw From header.
    
    Args:
        raw_from: Raw From header value (e.g., "John Doe <john@example.com>")
        
    Returns:
        Tuple of (email, name)
    """
    import email.utils
    
    parsed = email.utils.parseaddr(raw_from)
    sender_email = parsed[1] if parsed[1] else ""
    sender_name = decode_email_header(parsed[0]) if parsed[0] else ""
    
    return sender_email, sender_name


def parse_name_parts(full_name: str) -> Tuple[str, str]:
    """
    Parse full name into first and last name parts.
    
    Args:
        full_name: Complete name string
        
    Returns:
        Tuple of (first_name, last_name)
    """
    name_parts = full_name.split()
    
    if len(name_parts) > 1:
        first_name = " ".join(name_parts[:-1])
        last_name = name_parts[-1]
    else:
        first_name = full_name if full_name else "User"
        last_name = "Guest"
    
    return first_name, last_name


def clean_subject_line(subject: str) -> str:
    """
    Remove email reply prefixes (Re:, Fwd:, etc.) from subject line.
    
    Args:
        subject: Original subject line
        
    Returns:
        str: Cleaned subject line
    """
    import re
    
    # Remove common reply/forward prefixes
    cleaned = re.sub(
        r'^(re|fwd|fw)[:\s]*',
        '',
        subject.strip(),
        flags=re.IGNORECASE
    )

    return cleaned


def clean_mailto_artifacts(text: str) -> str:
    """
    Outlook gibi mail istemcilerinin duz metne cevirdigi e-posta baglantilarinda
    biraktigi "<mailto:...>" (bazen ic ice / URL-encoded) artiklarini temizler.

    Args:
        text: Ham e-posta govde metni

    Returns:
        str: mailto: artiklarindan arindirilmis metin
    """
    import re

    if not text:
        return text

    cleaned = text
    cleaned = cleaned.replace("%3c", "<").replace("%3C", "<")
    cleaned = cleaned.replace("%3e", ">").replace("%3E", ">")
    cleaned = cleaned.replace("&lt;", "<").replace("&gt;", ">")

    # Sadece DENGELI "<mailto:...>" ciftlerini kaldiriyoruz (ic ice olsa bile,
    # dongu ile en ictekinden disariya dogru temizlenir). Kapanan ">" bulunamayan
    # (dengesiz) durumlar KASITLI OLARAK dokunulmadan birakiliyor; aksi halde
    # mailin geri kalan gercek icerigi (ör. "Gereğini rica ederim...") de
    # yanlislikla silinebilir.
    previous = None
    while previous != cleaned:
        previous = cleaned
        cleaned = re.sub(r'<\s*mailto:[^<>]*>', '', cleaned, flags=re.IGNORECASE)

    return cleaned.strip()
