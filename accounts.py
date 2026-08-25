"""Panel user login, lockout, and screen-permission enforcement.

Named "accounts.py" (not "auth.py") to avoid colliding with the existing
auth.py, which handles CSM API bearer-token auth -- a completely different
thing from panel user login.

Session-based auth (not JWT): Flask-Session was already configured in this
app (app.py, SESSION_TYPE='filesystem') but never used. With few users and a
same-origin frontend (Vite dev proxy / Flask serving the built SPA in prod --
no CORS involved either way), a server-side session cookie is simpler than
JWT + refresh-token rotation: no client-side token storage/parsing, no
refresh-race handling, and revocation (logout, deactivate a user) is just
deleting server-side state instead of needing a token blocklist.
"""

import secrets
from datetime import datetime, timedelta, timezone
from functools import wraps

import bcrypt
from flask import g, jsonify, request, session

from models import AuditLog, User, db
from screens import effective_screens

LOCKOUT_THRESHOLD = 5
LOCKOUT_MINUTES = 15


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))
    except ValueError:
        return False


def _utcnow() -> datetime:
    # Naive-but-always-UTC, matching models._utcnow -- SQLite drops tzinfo on
    # round-trip so comparing an aware "now" against a naive locked_until
    # read back from the DB raises TypeError. See models.py's comment.
    return datetime.now(timezone.utc).replace(tzinfo=None)


def attempt_login(email: str, password: str) -> tuple[User | None, str | None]:
    """Returns (user, None) on success, or (None, error_message) on failure.
    Error messages are deliberately generic for "no such user"/"wrong
    password" (both -> "E-posta veya şifre hatalı") so a login form can't be
    used to enumerate valid emails."""
    user = User.query.filter_by(email=email.strip().lower()).first()

    if user is None:
        return None, "E-posta veya şifre hatalı."

    if not user.is_active:
        return None, "Bu hesap pasif durumda."

    if user.locked_until and user.locked_until > _utcnow():
        remaining = int((user.locked_until - _utcnow()).total_seconds() // 60) + 1
        return None, f"Hesap kilitli. {remaining} dakika sonra tekrar deneyin."

    if not verify_password(password, user.password_hash):
        user.failed_login_attempts += 1
        if user.failed_login_attempts >= LOCKOUT_THRESHOLD:
            user.locked_until = _utcnow() + timedelta(minutes=LOCKOUT_MINUTES)
        db.session.commit()
        return None, "E-posta veya şifre hatalı."

    user.failed_login_attempts = 0
    user.locked_until = None
    db.session.commit()
    return user, None


def current_user() -> User | None:
    user_id = session.get("user_id")
    if user_id is None:
        return None
    user = db.session.get(User, user_id)
    if user is None or not user.is_active:
        return None
    return user


def log_in_session(user: User) -> None:
    session.clear()
    session.permanent = True
    session["user_id"] = user.id
    session["csrf_token"] = secrets.token_urlsafe(32)


def log_out_session() -> None:
    session.clear()


def get_csrf_token() -> str | None:
    return session.get("csrf_token")


def record_audit_log(user: User | None, action: str, detail: str | None = None) -> None:
    entry = AuditLog(
        user_id=user.id if user else None,
        action=action,
        detail=detail,
        ip_address=request.remote_addr,
    )
    db.session.add(entry)
    db.session.commit()


def require_screen(screen_key: str):
    """Route decorator: 401 if not logged in, 403 if logged in but the
    screen isn't in the user's effective_screens (role default minus/plus
    per-user overrides -- see screens.effective_screens, the single formula
    both this and the frontend menu/route guard rely on). Sets g.current_user
    for the view to use."""

    def decorator(view_func):
        @wraps(view_func)
        def wrapped(*args, **kwargs):
            user = current_user()
            if user is None:
                return jsonify({"error": "Giriş gerekli."}), 401
            if screen_key not in effective_screens(user):
                return jsonify({"error": "Bu ekrana erişim yetkiniz yok."}), 403
            g.current_user = user
            return view_func(*args, **kwargs)

        return wrapped

    return decorator


def require_login(view_func):
    """Like require_screen but for endpoints any logged-in user may call
    regardless of screen permissions (e.g. /api/auth/me, /api/auth/logout)."""

    @wraps(view_func)
    def wrapped(*args, **kwargs):
        user = current_user()
        if user is None:
            return jsonify({"error": "Giriş gerekli."}), 401
        g.current_user = user
        return view_func(*args, **kwargs)

    return wrapped
