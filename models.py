"""SQLAlchemy models for panel user accounts and permission overrides.

The only database in this project — everything else (mail processing,
service calls) is JSONL log files, but user accounts need real relational
storage (unique emails, foreign keys, transactional lockout counters).

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
