"""
Utilities Module

Common utility functions for text processing, email handling, and data transformation.
"""

from email.header import decode_header
from typing import Tuple


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
