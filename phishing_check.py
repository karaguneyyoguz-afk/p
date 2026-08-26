"""Phishing/spoofing heuristics for inbound mail, run before anything else in
the ticket pipeline (see main.py's process_email).

Important framing: this is a customer-support inbox. Mail from an address
outside tatilbudur.com is the NORMAL, expected case (that's every customer),
so nothing here flags "external sender" by itself -- an allowlist is used
only for links/domains that a genuine tatilbudur.com message would point to,
never to judge the sender's own address. What IS flagged is impersonation/
deception: a display name claiming to be TatilBudur from a non-TatilBudur
address, a sender domain that's a one-or-two-character typo of a known
domain, a Reply-To that quietly redirects replies elsewhere, and links that
hide their real destination (IP-literal hosts, punycode/IDN homographs, URL
shorteners, or anchor text naming one domain while the href goes to another).

SAFE_DOMAINS is a manually maintained allowlist -- add any other domain the
company legitimately sends/links from (a second TLD, a payment provider,
etc.) here, otherwise it will be misflagged as a typosquat/external link.
"""

import re
from email.utils import parseaddr
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse

from utils import normalize_turkish_characters

SAFE_DOMAINS = {
    "tatilbudur.com",
    "cloudcsmetiya.com",  # CSM (Etiya) -- ticket system links may point here
}

# Normalized (accent-stripped, lowercased) brand keywords that, if present in
# a display name whose address isn't in SAFE_DOMAINS, indicate spoofing.
BRAND_KEYWORDS = ("tatilbudur", "tatil budur")

URL_SHORTENERS = {
    "bit.ly", "tinyurl.com", "t.co", "goo.gl", "ow.ly", "is.gd", "buff.ly", "cutt.ly",
}

_URL_PATTERN = re.compile(r"https?://[^\s<>\"']+", re.IGNORECASE)
_ANCHOR_PATTERN = re.compile(
    r'<a\b[^>]*href=["\']([^"\']+)["\'][^>]*>(.*?)</a>', re.IGNORECASE | re.DOTALL
)
_TAG_PATTERN = re.compile(r"<[^>]+>")
_DOMAIN_IN_TEXT_PATTERN = re.compile(r"\b([a-z0-9][a-z0-9-]*\.)+[a-z]{2,}\b", re.IGNORECASE)
_IPV4_PATTERN = re.compile(r"^\d{1,3}(\.\d{1,3}){3}$")


def _domain_of(url_or_address: str) -> str:
    """Best-effort hostname extraction from a URL or an email address."""
    if "@" in url_or_address and "://" not in url_or_address:
        return url_or_address.rsplit("@", 1)[-1].strip().lower()
    parsed = urlparse(url_or_address if "://" in url_or_address else f"//{url_or_address}")
    return (parsed.hostname or "").lower()


def _levenshtein(a: str, b: str) -> int:
    if a == b:
        return 0
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        curr = [i] + [0] * len(b)
        for j, cb in enumerate(b, 1):
            curr[j] = min(prev[j] + 1, curr[j - 1] + 1, prev[j - 1] + (ca != cb))
        prev = curr
    return prev[-1]


def is_typosquat_domain(domain: str) -> Optional[str]:
    """Returns the SAFE_DOMAINS entry `domain` looks like a typo of, or None.
    A 1-2 character edit distance from a known domain (extra/missing/swapped
    letter, an inserted hyphen) is the classic typosquat pattern; exact
    matches and domains that are simply unrelated are not flagged."""
    domain = (domain or "").lower()
    if not domain or domain in SAFE_DOMAINS:
        return None
    for safe in SAFE_DOMAINS:
        if 0 < _levenshtein(domain, safe) <= 2:
            return safe
    return None


def is_ip_literal_host(host: str) -> bool:
    return bool(_IPV4_PATTERN.match(host or "")) or (host or "").startswith("[")


def is_punycode_host(host: str) -> bool:
    host = (host or "").lower()
    return host.startswith("xn--") or ".xn--" in host


def extract_urls(text: str) -> List[str]:
    return _URL_PATTERN.findall(text or "")


def _extract_html_part(msg) -> str:
    """Best-effort raw text/html body, independent of mail_processor's own
    (already-converted-to-plain-text) extraction -- anchor/href mismatch
    detection needs the original markup, not the stripped-down text."""
    try:
        if msg.is_multipart():
            for part in msg.walk():
                if part.get_content_type() == "text/html":
                    charset = part.get_content_charset() or "utf-8"
                    payload = part.get_payload(decode=True)
                    if payload:
                        return payload.decode(charset, errors="ignore")
        elif msg.get_content_type() == "text/html":
            charset = msg.get_content_charset() or "utf-8"
            payload = msg.get_payload(decode=True)
            if payload:
                return payload.decode(charset, errors="ignore")
    except Exception:
        pass
    return ""


def find_anchor_href_mismatches(html: str) -> List[str]:
    """Flags `<a href="real.com">tatilbudur.com</a>`-style links where the
    clickable text names a domain that differs from where the link actually
    goes -- the classic hidden-link phishing trick."""
    signals = []
    for href, anchor_html in _ANCHOR_PATTERN.findall(html or ""):
        anchor_text = _TAG_PATTERN.sub("", anchor_html).strip()
        named_domain_match = _DOMAIN_IN_TEXT_PATTERN.search(anchor_text)
        if not named_domain_match:
            continue
        named_domain = named_domain_match.group(0).lower()
        real_domain = _domain_of(href)
        if real_domain and named_domain != real_domain and not real_domain.endswith(f".{named_domain}"):
            signals.append(f"Gizlenmiş link: metin '{named_domain}' gösteriyor ama gerçek adres '{real_domain}'")
    return signals


def check_suspicious_links(body: str, html: str) -> List[str]:
    signals = []
    seen_domains = set()
    for url in extract_urls(body) + extract_urls(html):
        host = _domain_of(url)
        if not host or host in seen_domains:
            continue
        seen_domains.add(host)
        if host in SAFE_DOMAINS:
            continue
        if is_ip_literal_host(host):
            signals.append(f"IP adresine giden link: {url}")
        elif is_punycode_host(host):
            signals.append(f"Punycode/IDN alan adına giden link (homograph riski): {url}")
        elif host in URL_SHORTENERS:
            signals.append(f"URL kısaltıcı linki (gerçek hedef gizli): {url}")
        else:
            typosquat_of = is_typosquat_domain(host)
            if typosquat_of:
                signals.append(f"'{typosquat_of}' alan adının olası taklidi: {host}")
    return signals


def check_display_name_spoofing(sender_name: str, sender_email: str) -> Optional[str]:
    normalized_name = normalize_turkish_characters(sender_name or "").lower()
    if not any(keyword in normalized_name for keyword in BRAND_KEYWORDS):
        return None
    sender_domain = _domain_of(sender_email)
    if sender_domain in SAFE_DOMAINS:
        return None
    return f"Görünen ad TatilBudur'a ait gibi ('{sender_name}') ama gönderen adresi ({sender_email}) değil"


def check_reply_to_mismatch(msg, sender_email: str) -> Optional[str]:
    reply_to_header = msg.get("Reply-To")
    if not reply_to_header:
        return None
    reply_to_address = parseaddr(str(reply_to_header))[1]
    if not reply_to_address:
        return None
    from_domain = _domain_of(sender_email)
    reply_domain = _domain_of(reply_to_address)
    if from_domain and reply_domain and from_domain != reply_domain:
        return f"Reply-To ({reply_to_address}) gönderen adresten ({sender_email}) farklı bir alan adına yönlendiriyor"
    return None


def check_sender_domain_typosquat(sender_email: str) -> Optional[str]:
    sender_domain = _domain_of(sender_email)
    typosquat_of = is_typosquat_domain(sender_domain)
    if typosquat_of:
        return f"Gönderen alan adı ({sender_domain}) '{typosquat_of}' alan adının olası taklidi"
    return None


def analyze_mail(msg, sender_email: str, sender_name: str, body: str) -> Dict[str, Any]:
    """Runs every heuristic above and returns {"suspicious": bool, "signals":
    [str, ...]}. Any single signal is enough to mark the mail suspicious --
    these are all deception-specific checks (see module docstring), not
    generic "this looks unusual" scoring, so false positives should be rare
    by design; a real false positive means SAFE_DOMAINS/BRAND_KEYWORDS need
    another legitimate entry, not that the check itself is too strict."""
    html = _extract_html_part(msg)
    signals: List[str] = []

    spoof_signal = check_display_name_spoofing(sender_name, sender_email)
    if spoof_signal:
        signals.append(spoof_signal)

    typosquat_signal = check_sender_domain_typosquat(sender_email)
    if typosquat_signal:
        signals.append(typosquat_signal)

    reply_to_signal = check_reply_to_mismatch(msg, sender_email)
    if reply_to_signal:
        signals.append(reply_to_signal)

    signals.extend(check_suspicious_links(body, html))
    if html:
        signals.extend(find_anchor_href_mismatches(html))

    return {"suspicious": len(signals) > 0, "signals": signals}
