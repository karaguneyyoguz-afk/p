"""Content moderation: keyword/regex rule engine for flagging inappropriate
inbound mail before it reaches the ticket pipeline.

Two rule sources are checked and merged, on purpose ("hem koddan hem
panelden güncelleyebileyim" -- kullanıcı isteği): config.PROFANITY_WORDS (a
fixed, code-level list a developer edits directly, no panel access needed)
and ContentRule rows in the database (edited live from the panel, no
restart/deploy needed).

This module is imported from two very different kinds of process: Flask
request handlers (app.py, content_rules_routes.py -- these already have an
app-bound db.session) AND standalone scripts that are NOT Flask apps at all
(watch_mail.py, main.py's CLI entrypoint, run_scheduled_mail_check.py --
these have no Flask app context to push, and models.py's own docstring
notes the project deliberately keeps them off Flask-SQLAlchemy's request-
scoped session). Rather than wrapping every one of those long-running,
already-in-production scripts in `with app.app_context():`, this module
opens its OWN plain SQLAlchemy session against the same DATABASE_URL,
independent of Flask. Both sides read/write the same SQLite file underneath;
at this project's scale that's fine.
"""

import json
import os
import re
import subprocess
import sys
from dataclasses import dataclass
from typing import List, Optional

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from config import PROFANITY_WORDS
from models import ContentRule, FlaggedMail
from utils import normalize_turkish_characters

REGEX_TIMEOUT_SECONDS = 2.0
MAX_PATTERN_LENGTH = 300
# Kaydedilmeden önce her regex bu string'lere karşı denenir -- klasik
# catastrophic-backtracking tetikleyicileri (uzun tekrar + son karakterin
# eşleşmemesi).
_ADVERSARIAL_TEST_STRINGS = [
    "a" * 50 + "!",
    ("ab" * 25) + "!",
    " ".join(["kelime"] * 60),
]
# Klasik iç-içe tekrar kalıpları -- (x+)+, (x*)*, (x+)*, (x*)+ gibi --
# catastrophic backtracking'in en yaygın imzası. Gerçek koruma aşağıdaki
# subprocess testi; bu sadece hızlı, net bir ön-eleme/hata mesajı.
_NESTED_QUANTIFIER_PATTERN = re.compile(r"\([^()]*[+*][^()]*\)[+*]")

_REGEX_WORKER_SOURCE = (
    "import json,re,sys\n"
    "d=json.loads(sys.stdin.read())\n"
    "try:\n"
    "    re.compile(d['pattern'], re.IGNORECASE).search(d['test_string'])\n"
    "    print('OK')\n"
    "except re.error as e:\n"
    "    print('ERROR:'+str(e))\n"
)


def _run_regex_in_subprocess(pattern: str, test_string: str) -> str:
    """Returns "OK", "ERROR:<msg>", or "TIMEOUT". Runs the compile+search in
    a genuinely separate OS process (subprocess), not a thread -- CPython's
    `re` matcher never releases the GIL while backtracking, so a thread
    stuck in a catastrophic pattern can't be preempted or even detected as
    timed out (confirmed live: an earlier thread-based version of this
    check hung the entire test process on `(a+)+` and had to be killed by
    hand). A separate process can always be killed by the OS regardless of
    what it's doing internally."""
    try:
        proc = subprocess.run(
            [sys.executable, "-c", _REGEX_WORKER_SOURCE],
            input=json.dumps({"pattern": pattern, "test_string": test_string}),
            capture_output=True,
            text=True,
            timeout=REGEX_TIMEOUT_SECONDS,
        )
        return proc.stdout.strip() or f"ERROR:{proc.stderr.strip() or 'bilinmeyen hata'}"
    except subprocess.TimeoutExpired:
        return "TIMEOUT"

_engine = None
_SessionFactory = None


def _get_session():
    global _engine, _SessionFactory
    if _SessionFactory is None:
        database_url = os.getenv("DATABASE_URL", "sqlite:///enigma.db")
        _engine = create_engine(database_url)
        _SessionFactory = sessionmaker(bind=_engine)
    return _SessionFactory()


# Tek tek harfin arasina serpistirilmis nokta/tire/alt cizgi/bosluk --
# "k.ü.f.ü.r" veya "k u f u r" gibi -- EN AZ 3 tek harf gerektirir (2
# ayirici), boylece sıradan iki kelime arasindaki normal bosluga ASLA
# dokunmaz ("bu kötü" gibi cumleler etkilenmez).
_SPACED_OUT_PATTERN = re.compile(r"\b\w(?:[\s.\-_]\w){2,}\b", re.UNICODE)
_LEET_MAP = str.maketrans({"0": "o", "1": "i", "3": "e", "4": "a", "@": "a", "$": "s"})


def _collapse_spaced_out_letters(text: str) -> str:
    return _SPACED_OUT_PATTERN.sub(lambda m: re.sub(r"[\s.\-_]", "", m.group(0)), text)


def normalize_for_moderation(text: str) -> str:
    """Türkçe karakterleri sadeleştirir, küçük harfe çevirir, harf arasına
    serpiştirilmiş ayırıcıları birleştirir ve yaygın leetspeak eşlemelerini
    (0->o, 1->i, 3->e, 4->a, @->a, $->s) uygular."""
    normalized = normalize_turkish_characters(text or "").lower()
    normalized = _collapse_spaced_out_letters(normalized)
    return normalized.translate(_LEET_MAP)


def validate_regex_pattern(pattern: str) -> Optional[str]:
    """Returns None if `pattern` is safe to store as a ContentRule, or a
    user-facing error string otherwise. Only called when a panel admin
    creates/updates a rule (rare), so the subprocess-per-test-string cost
    (~50-150ms each) is a non-issue here."""
    if not pattern or not pattern.strip():
        return "Regex boş olamaz."
    if len(pattern) > MAX_PATTERN_LENGTH:
        return f"Regex en fazla {MAX_PATTERN_LENGTH} karakter olabilir."
    try:
        re.compile(pattern, re.IGNORECASE)
    except re.error as e:
        return f"Geçersiz regex: {e}"
    if _NESTED_QUANTIFIER_PATTERN.search(pattern):
        return "Regex iç içe tekrar (ör. (x+)+) içeriyor — ReDoS riski taşıyor, daha basit bir desen deneyin."

    for test_string in _ADVERSARIAL_TEST_STRINGS:
        outcome = _run_regex_in_subprocess(pattern, test_string)
        if outcome == "TIMEOUT":
            return "Regex çok yavaş çalışıyor (olası ReDoS) — daha basit bir desen deneyin."
        if outcome.startswith("ERROR:"):
            return f"Geçersiz regex: {outcome[len('ERROR:'):]}"
    return None


@dataclass
class ModerationMatch:
    category: str
    rule_source: str  # "config" | "db"
    rule_id: Optional[int]
    pattern: str
    snippet: str


def _extract_snippet(original_text: str, needle: str, context: int = 15) -> str:
    """Orijinal (normalize edilmemiş) metinden eşleşmenin etrafından kısa bir
    alıntı çıkarır -- operatöre "neden işaretlendi" göstermek için. Bulunamazsa
    (leetspeak/boşluklu varyant orijinalde birebir görünmüyorsa) needle'ın
    kendisi döner."""
    hay = normalize_turkish_characters(original_text or "").lower()
    idx = hay.find(normalize_turkish_characters(needle or "").lower())
    if idx == -1:
        return needle
    start = max(0, idx - context)
    end = min(len(original_text), idx + len(needle) + context)
    return original_text[start:end].strip()


def get_active_rules() -> List[ContentRule]:
    session = _get_session()
    try:
        return session.query(ContentRule).filter_by(is_active=True).all()
    finally:
        session.close()


def check_content(text: str) -> Optional[ModerationMatch]:
    """Runs config.PROFANITY_WORDS then every active DB ContentRule against
    `text`, in that order, returning the FIRST match (or None if clean).
    Regex rules are matched directly (no per-call subprocess sandbox --
    every regex rule already passed validate_regex_pattern's adversarial
    subprocess testing before it could ever be saved, and re-sandboxing on
    every single incoming mail would add ~100ms+ per rule to the hot path
    for a risk that's already been screened out at write time)."""
    normalized = normalize_for_moderation(text)

    # Sol tarafta \b, sağda YOK: Türkçe sondan eklemeli bir dil -- kelime
    # köküne "dolandırıcısınız" gibi keyfi uzunlukta ek gelebilir, sabit bir
    # "en fazla N ek karakteri" sınırı (ör. eski \w{0,3}) bunu kaçırırdı
    # (canlı testte "dolandirici" kuralı "dolandiricisiniz" ile eslesmedi,
    # duzeltildi). Sadece SOL sınır araniyor ki "sik" "asik" icinde
    # yakalanmasin (a ile s arasinda kelime siniri yok).
    for word in PROFANITY_WORDS:
        pattern = r"\b" + re.escape(normalize_for_moderation(word))
        if re.search(pattern, normalized):
            return ModerationMatch("kufur", "config", None, word, _extract_snippet(text, word))

    for rule in get_active_rules():
        if rule.rule_type == "keyword":
            pattern = r"\b" + re.escape(normalize_for_moderation(rule.pattern))
            if re.search(pattern, normalized):
                return ModerationMatch(
                    rule.category, "db", rule.id, rule.pattern, _extract_snippet(text, rule.pattern)
                )
        else:
            try:
                match = re.search(rule.pattern, text or "", re.IGNORECASE)
            except re.error:
                continue  # panelde kaydedilmiş ama artık geçersiz -- crash etme, atla
            if match:
                return ModerationMatch(rule.category, "db", rule.id, rule.pattern, match.group(0))

    return None


def create_flagged_mail(
    sender_email: str, sender_name: str, subject: str, body: str, match: ModerationMatch
) -> int:
    session = _get_session()
    try:
        row = FlaggedMail(
            sender_email=sender_email,
            sender_name=sender_name,
            subject=subject,
            mail_body=body,
            matched_category=match.category,
            matched_rule_source=match.rule_source,
            matched_rule_id=match.rule_id,
            matched_pattern=match.pattern,
            matched_snippet=match.snippet,
            status="pending",
        )
        session.add(row)
        session.commit()
        return row.id
    finally:
        session.close()
