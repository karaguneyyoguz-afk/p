"""Auth + user-management API routes, as a Blueprint (app.py is already
large; keeping the ~10 new account-related routes in their own file mirrors
how bulk_shift.py/csm_api.py already keep their logic out of app.py)."""

from flask import Blueprint, g, jsonify, request

from accounts import (
    attempt_login,
    get_csrf_token,
    hash_password,
    log_in_session,
    log_out_session,
    record_audit_log,
    require_login,
    require_screen,
)
from models import ROLES, User, UserScreenOverride, db
from screens import is_valid_screen, role_default_screens, screens_payload

accounts_bp = Blueprint("accounts", __name__, url_prefix="/api")


def _me_payload(user: User) -> dict:
    return {**user.to_dict(), **screens_payload(user), "csrf_token": get_csrf_token()}


@accounts_bp.route("/auth/login", methods=["POST"])
def login():
    data = request.get_json(silent=True) or {}
    email = (data.get("email") or "").strip()
    password = data.get("password") or ""
    if not email or not password:
        return jsonify({"error": "E-posta ve şifre gerekli."}), 400

    user, error = attempt_login(email, password)
    if error:
        record_audit_log(None, "login_failed", detail=email)
        return jsonify({"error": error}), 401

    log_in_session(user)
    record_audit_log(user, "login_success")
    return jsonify(_me_payload(user))


@accounts_bp.route("/auth/logout", methods=["POST"])
@require_login
def logout():
    record_audit_log(g.current_user, "logout")
    log_out_session()
    return jsonify({"success": True})


@accounts_bp.route("/auth/me")
@require_login
def me():
    return jsonify(_me_payload(g.current_user))


@accounts_bp.route("/users")
@require_screen("users")
def list_users():
    users = User.query.order_by(User.email).all()
    return jsonify({"users": [u.to_dict() for u in users]})


@accounts_bp.route("/users", methods=["POST"])
@require_screen("users")
def create_user():
    data = request.get_json(silent=True) or {}
    email = (data.get("email") or "").strip().lower()
    password = data.get("password") or ""
    role = data.get("role") or ""

    if not email or not password or role not in ROLES:
        return jsonify({"error": f"email, password ve role ({', '.join(ROLES)}) gerekli."}), 400
    if len(password) < 8:
        return jsonify({"error": "Şifre en az 8 karakter olmalı."}), 400
    if User.query.filter_by(email=email).first():
        return jsonify({"error": "Bu e-posta zaten kayıtlı."}), 409

    user = User(email=email, password_hash=hash_password(password), role=role, is_active=True)
    db.session.add(user)
    db.session.commit()
    record_audit_log(g.current_user, "user_created", detail=f"{email} ({role})")
    return jsonify(user.to_dict()), 201


@accounts_bp.route("/users/<int:user_id>", methods=["PATCH"])
@require_screen("users")
def update_user(user_id: int):
    user = db.session.get(User, user_id)
    if user is None:
        return jsonify({"error": "Kullanıcı bulunamadı."}), 404

    data = request.get_json(silent=True) or {}
    changes = []

    if "role" in data:
        if data["role"] not in ROLES:
            return jsonify({"error": f"Geçersiz rol. Seçenekler: {', '.join(ROLES)}"}), 400
        if user.id == g.current_user.id and data["role"] != "admin" and user.role == "admin":
            return jsonify({"error": "Kendi admin rolünüzü değiştiremezsiniz."}), 400
        user.role = data["role"]
        changes.append(f"role={data['role']}")

    if "is_active" in data:
        if user.id == g.current_user.id and not data["is_active"]:
            return jsonify({"error": "Kendi hesabınızı pasifleştiremezsiniz."}), 400
        if not data["is_active"] and user.role == "admin" and _is_last_active_admin(user):
            return jsonify({"error": "Son aktif admin pasifleştirilemez."}), 400
        user.is_active = bool(data["is_active"])
        changes.append(f"is_active={user.is_active}")

    if "password" in data and data["password"]:
        if len(data["password"]) < 8:
            return jsonify({"error": "Şifre en az 8 karakter olmalı."}), 400
        user.password_hash = hash_password(data["password"])
        changes.append("password_reset")

    db.session.commit()
    record_audit_log(g.current_user, "user_updated", detail=f"{user.email}: {', '.join(changes)}")
    return jsonify(user.to_dict())


@accounts_bp.route("/users/<int:user_id>", methods=["DELETE"])
@require_screen("users")
def deactivate_user(user_id: int):
    """Soft-delete only -- flips is_active off, never removes the row (keeps
    AuditLog/UserScreenOverride foreign keys intact)."""
    user = db.session.get(User, user_id)
    if user is None:
        return jsonify({"error": "Kullanıcı bulunamadı."}), 404
    if user.id == g.current_user.id:
        return jsonify({"error": "Kendi hesabınızı silemezsiniz."}), 400
    if user.role == "admin" and _is_last_active_admin(user):
        return jsonify({"error": "Son aktif admin silinemez."}), 400

    user.is_active = False
    db.session.commit()
    record_audit_log(g.current_user, "user_deactivated", detail=user.email)
    return jsonify({"success": True})


def _is_last_active_admin(user: User) -> bool:
    other_active_admins = User.query.filter(
        User.role == "admin", User.is_active.is_(True), User.id != user.id
    ).count()
    return other_active_admins == 0


@accounts_bp.route("/users/<int:user_id>/overrides")
@require_screen("users")
def get_overrides(user_id: int):
    user = db.session.get(User, user_id)
    if user is None:
        return jsonify({"error": "Kullanıcı bulunamadı."}), 404
    return jsonify(screens_payload(user))


@accounts_bp.route("/users/<int:user_id>/overrides", methods=["PUT"])
@require_screen("users")
def set_overrides(user_id: int):
    """Body: {"overrides": {"<screen_key>": true|false|null, ...}}
    true -> grant (screen not in role defaults), false -> deny (screen IS in
    role defaults, taken away), null -> remove any override (fall back to
    role default) for that screen."""
    user = db.session.get(User, user_id)
    if user is None:
        return jsonify({"error": "Kullanıcı bulunamadı."}), 404

    data = request.get_json(silent=True) or {}
    overrides = data.get("overrides")
    if not isinstance(overrides, dict):
        return jsonify({"error": "overrides bir obje olmalı."}), 400

    role_screens = role_default_screens(user.role)
    changed = []
    for screen_key, allow in overrides.items():
        if not is_valid_screen(screen_key):
            return jsonify({"error": f"Geçersiz ekran anahtarı: {screen_key}"}), 400

        existing = UserScreenOverride.query.filter_by(user_id=user.id, screen_key=screen_key).first()
        if allow is None:
            if existing:
                db.session.delete(existing)
                changed.append(f"{screen_key}:removed")
            continue

        if bool(allow) == (screen_key in role_screens):
            # Requested state already matches the role default -- an
            # override here would be a no-op, so don't store one.
            if existing:
                db.session.delete(existing)
            continue

        if existing:
            existing.allow = bool(allow)
        else:
            db.session.add(UserScreenOverride(user_id=user.id, screen_key=screen_key, allow=bool(allow)))
        changed.append(f"{screen_key}:{allow}")

    db.session.commit()
    record_audit_log(g.current_user, "user_overrides_changed", detail=f"{user.email}: {', '.join(changed)}")
    return jsonify(screens_payload(user))
