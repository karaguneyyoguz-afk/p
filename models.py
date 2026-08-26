"""SQLAlchemy models for panel user accounts, permission overrides, and the
content-moderation rule engine.

Most mail-processing state (tickets, service calls) is still JSONL log
files -- ContentRule and FlaggedMail are the exception, and need real
relational storage on purpose: ContentRule needs CRUD + a uniqueness-free
but queryable "is_active" filter, and FlaggedMail needs a mutable "status"
field an operator changes later (pending -> approved/rejected), which a
write-once JSONL log line can't represent. mail-processing scripts that
aren't Flask requests (watch_mail.py, main.py's CLI entrypoint) read/write
these two tables through content_moderation.py's own standalone SQLAlchemy
session (no app context needed) -- see that module's docstring.

Uses plain SQLAlchemy (via Flask-SQLAlchemy) rather than hand-written SQL so
the code stays database-agnostic: this runs on SQLite today, and the plan is
to move to Postgres later — at that point only the SQLALCHEMY_DATABASE_URI
env var needs to change, no query rewrites.

Roles and screens are NOT modeled here as tables — they're small, fixed,
code-defined sets (see screens.py) since they change rarely and a whole
"role"/"screen" DB table would be more machinery than three-people-editing-a-
dropdown needs.
"""

from datetime import datetime, timezone

from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()

ROLES = ("admin", "yonetici", "operator", "izleyici")


def _utcnow() -> datetime:
    # Naive UTC on purpose: SQLite silently drops tzinfo on round-trip (a
    # DateTime() column reads back as offset-naive), which
    # breaks any `aware > naive` comparison (e.g. lockout expiry checks).
    # Storing everything as naive-but-always-UTC works identically on SQLite
    # today and Postgres later, as long as nothing ever mixes in local time.
    return datetime.now(timezone.utc).replace(tzinfo=None)


class User(db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(255), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(20), nullable=False)
    is_active = db.Column(db.Boolean, nullable=False, default=True)

    failed_login_attempts = db.Column(db.Integer, nullable=False, default=0)
    locked_until = db.Column(db.DateTime(), nullable=True)

    created_at = db.Column(db.DateTime(), nullable=False, default=_utcnow)
    updated_at = db.Column(db.DateTime(), nullable=False, default=_utcnow, onupdate=_utcnow)

    overrides = db.relationship(
        "UserScreenOverride", back_populates="user", cascade="all, delete-orphan"
    )

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "email": self.email,
            "role": self.role,
            "is_active": self.is_active,
            # created_at is stored naive-but-always-UTC (see _utcnow) -- "Z"
            # suffix makes that explicit for JSON consumers instead of
            # leaving an ambiguous timezone-less timestamp string.
            "created_at": self.created_at.isoformat() + "Z" if self.created_at else None,
        }


class UserScreenOverride(db.Model):
    """Per-user exception to the role's default screen access.

    allow=False -- take a screen AWAY that the role would otherwise grant.
    allow=True  -- give a screen the role does NOT grant by default.
    See screens.effective_screens() for how this combines with ROLE_SCREENS.
    """

    __tablename__ = "user_screen_overrides"
    __table_args__ = (db.UniqueConstraint("user_id", "screen_key", name="uq_user_screen"),)

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    screen_key = db.Column(db.String(50), nullable=False)
    allow = db.Column(db.Boolean, nullable=False)
    created_at = db.Column(db.DateTime(), nullable=False, default=_utcnow)

    user = db.relationship("User", back_populates="overrides")


CONTENT_RULE_TYPES = ("keyword", "regex")
CONTENT_RULE_CATEGORIES = ("kufur", "spam", "tehdit", "yetiskin", "diger")


class ContentRule(db.Model):
    """Panelden yönetilen uygunsuz-içerik kuralı (kelime ya da regex).

    Bu tablo hem panel CRUD'u (Flask request/db.session üzerinden) hem de
    watch_mail.py/main.py gibi Flask uygulaması OLMAYAN mail-işleme
    scriptleri tarafından okunuyor -- ikincisi content_moderation.py'deki
    bağımsız (app context gerektirmeyen) SQLAlchemy session'ı kullanıyor,
    bu modelin kendisi ise her iki tarafta da aynı."""

    __tablename__ = "content_rules"

    id = db.Column(db.Integer, primary_key=True)
    pattern = db.Column(db.String(300), nullable=False)
    rule_type = db.Column(db.String(10), nullable=False)
    category = db.Column(db.String(30), nullable=False)
    is_active = db.Column(db.Boolean, nullable=False, default=True)
    created_by_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    created_at = db.Column(db.DateTime(), nullable=False, default=_utcnow)
    updated_at = db.Column(db.DateTime(), nullable=False, default=_utcnow, onupdate=_utcnow)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "pattern": self.pattern,
            "rule_type": self.rule_type,
            "category": self.category,
            "is_active": self.is_active,
            "created_by_id": self.created_by_id,
            "created_at": self.created_at.isoformat() + "Z" if self.created_at else None,
            "updated_at": self.updated_at.isoformat() + "Z" if self.updated_at else None,
        }


FLAGGED_MAIL_STATUSES = ("pending", "approved", "rejected")


class FlaggedMail(db.Model):
    """Uygunsuz içerik kuralına takılıp otomatik ticket akışından çıkarılan,
    operatör onayını bekleyen mail. mail_body burada TAM olarak saklanıyor
    (onaylanırsa ticket akışının kaldığı yerden devam edebilmesi için) --
    panelde gösterilirken varsayılan olarak maskeli önizleme kullanılır,
    ham içerik sadece "tam metni göster" ile açılır."""

    __tablename__ = "flagged_mails"

    id = db.Column(db.Integer, primary_key=True)
    sender_email = db.Column(db.String(255), nullable=False)
    sender_name = db.Column(db.String(255), nullable=True)
    subject = db.Column(db.Text, nullable=False)
    mail_body = db.Column(db.Text, nullable=False)
    matched_category = db.Column(db.String(30), nullable=False)
    matched_rule_source = db.Column(db.String(10), nullable=False)  # "config" | "db"
    matched_rule_id = db.Column(db.Integer, nullable=True)  # ContentRule.id, source == "db" ise
    matched_pattern = db.Column(db.String(300), nullable=True)
    matched_snippet = db.Column(db.String(300), nullable=True)
    status = db.Column(db.String(20), nullable=False, default="pending")
    reviewed_by_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    reviewed_at = db.Column(db.DateTime(), nullable=True)
    created_at = db.Column(db.DateTime(), nullable=False, default=_utcnow)

    @staticmethod
    def _mask(text: str) -> str:
        """İlk ve son karakteri bırakıp arasını yıldızlarla değiştirir --
        uzunluk hakkında hâlâ bir fikir verir ama kelimenin kendisini gizler."""
        if not text:
            return text
        return "".join(
            ch if ch in " \n\r\t" or i in (0, len(text) - 1) else "*"
            for i, ch in enumerate(text)
        )

    def to_dict(self, reveal: bool = False) -> dict:
        return {
            "id": self.id,
            "sender_email": self.sender_email,
            "sender_name": self.sender_name,
            "subject": self.subject,
            "mail_body": self.mail_body if reveal else self._mask(self.mail_body),
            "matched_category": self.matched_category,
            "matched_rule_source": self.matched_rule_source,
            "matched_rule_id": self.matched_rule_id,
            "matched_pattern": self.matched_pattern if reveal else self._mask(self.matched_pattern or ""),
            "matched_snippet": self.matched_snippet if reveal else self._mask(self.matched_snippet or ""),
            "status": self.status,
            "reviewed_by_id": self.reviewed_by_id,
            "reviewed_at": self.reviewed_at.isoformat() + "Z" if self.reviewed_at else None,
            "created_at": self.created_at.isoformat() + "Z" if self.created_at else None,
        }


class AuditLog(db.Model):
    """Record of security-sensitive actions (login, user/permission changes)
    -- a curated subset, not a log of every request (that's already covered
    by service_requests_log.jsonl's panel_api entries)."""

    __tablename__ = "audit_log"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    action = db.Column(db.String(100), nullable=False)
    detail = db.Column(db.Text, nullable=True)
    ip_address = db.Column(db.String(64), nullable=True)
    created_at = db.Column(db.DateTime(), nullable=False, default=_utcnow)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "user_id": self.user_id,
            "action": self.action,
            "detail": self.detail,
            "ip_address": self.ip_address,
            "created_at": self.created_at.isoformat() + "Z" if self.created_at else None,
        }
