"""İçerik denetimi kuralları (ContentRule) CRUD'u ve işaretlenmiş mail
(FlaggedMail) inceleme uç noktaları -- accounts_routes.py'nin blueprint
deseniyle tutarlı, aynı `content_rules` ekranına bağlı.

Bu dosyadaki her endpoint @require_screen("content_rules") ile korunuyor --
React tarafında menüyü gizlemek yeterli değil, kontrol burada sunucu
tarafında yapılıyor (kullanıcının kendi belirttiği gereksinim)."""

from flask import Blueprint, g, jsonify, request

from accounts import record_audit_log, require_screen
from content_moderation import check_content, create_flagged_mail, validate_regex_pattern
from csm_api import CSMAPIClient
from logging_utils import record_mail_event
from mail_processor import EmailCategorizer, send_rejection_email
from models import CONTENT_RULE_CATEGORIES, CONTENT_RULE_TYPES, ContentRule, FlaggedMail, _utcnow, db

content_rules_bp = Blueprint("content_rules", __name__, url_prefix="/api")


def _validate_rule_fields(data: dict, partial: bool = False) -> str | None:
    """Returns an error message, or None if the fields present in `data`
    are all valid. `partial=True` (PATCH) skips "is this field present"
    checks -- only what's actually sent gets validated."""
    if "rule_type" in data and data["rule_type"] not in CONTENT_RULE_TYPES:
        return f"Geçersiz kural tipi. Seçenekler: {', '.join(CONTENT_RULE_TYPES)}"
    if "category" in data and data["category"] not in CONTENT_RULE_CATEGORIES:
        return f"Geçersiz kategori. Seçenekler: {', '.join(CONTENT_RULE_CATEGORIES)}"
    if not partial:
        if "pattern" not in data or not str(data["pattern"]).strip():
            return "pattern gerekli."
        if "rule_type" not in data:
            return "rule_type gerekli."
        if "category" not in data:
            return "category gerekli."
    return None


@content_rules_bp.route("/content-rules")
@require_screen("content_rules")
def list_content_rules():
    query = ContentRule.query
    category = request.args.get("category")
    rule_type = request.args.get("rule_type")
    if category:
        query = query.filter_by(category=category)
    if rule_type:
        query = query.filter_by(rule_type=rule_type)
    rules = query.order_by(ContentRule.created_at.desc()).all()
    return jsonify({"rules": [r.to_dict() for r in rules], "categories": CONTENT_RULE_CATEGORIES, "types": CONTENT_RULE_TYPES})


@content_rules_bp.route("/content-rules", methods=["POST"])
@require_screen("content_rules")
def create_content_rule():
    data = request.get_json(silent=True) or {}
    error = _validate_rule_fields(data)
    if error:
        return jsonify({"error": error}), 400

    pattern = str(data["pattern"]).strip()
    rule_type = data["rule_type"]
    if rule_type == "regex":
        regex_error = validate_regex_pattern(pattern)
        if regex_error:
            return jsonify({"error": regex_error}), 400

    rule = ContentRule(
        pattern=pattern,
        rule_type=rule_type,
        category=data["category"],
        is_active=bool(data.get("is_active", True)),
        created_by_id=g.current_user.id,
    )
    db.session.add(rule)
    db.session.commit()
    record_audit_log(
        g.current_user, "content_rule_created",
        detail=f"[{rule.rule_type}/{rule.category}] {rule.pattern}",
    )
    return jsonify(rule.to_dict()), 201


@content_rules_bp.route("/content-rules/<int:rule_id>", methods=["PATCH"])
@require_screen("content_rules")
def update_content_rule(rule_id: int):
    rule = db.session.get(ContentRule, rule_id)
    if rule is None:
        return jsonify({"error": "Kural bulunamadı."}), 404

    data = request.get_json(silent=True) or {}
    error = _validate_rule_fields(data, partial=True)
    if error:
        return jsonify({"error": error}), 400

    new_pattern = str(data["pattern"]).strip() if "pattern" in data else rule.pattern
    new_type = data.get("rule_type", rule.rule_type)
    if new_type == "regex" and (new_pattern != rule.pattern or new_type != rule.rule_type):
        regex_error = validate_regex_pattern(new_pattern)
        if regex_error:
            return jsonify({"error": regex_error}), 400

    before = f"[{rule.rule_type}/{rule.category}] {rule.pattern} (aktif={rule.is_active})"
    if "pattern" in data:
        rule.pattern = new_pattern
    if "rule_type" in data:
        rule.rule_type = new_type
    if "category" in data:
        rule.category = data["category"]
    if "is_active" in data:
        rule.is_active = bool(data["is_active"])
    db.session.commit()
    record_audit_log(
        g.current_user, "content_rule_updated",
        detail=f"#{rule.id}: {before} -> [{rule.rule_type}/{rule.category}] {rule.pattern} (aktif={rule.is_active})",
    )
    return jsonify(rule.to_dict())


@content_rules_bp.route("/content-rules/<int:rule_id>", methods=["DELETE"])
@require_screen("content_rules")
def delete_content_rule(rule_id: int):
    rule = db.session.get(ContentRule, rule_id)
    if rule is None:
        return jsonify({"error": "Kural bulunamadı."}), 404
    detail = f"[{rule.rule_type}/{rule.category}] {rule.pattern}"
    db.session.delete(rule)
    db.session.commit()
    record_audit_log(g.current_user, "content_rule_deleted", detail=f"#{rule_id}: {detail}")
    return jsonify({"success": True})


@content_rules_bp.route("/content-rules/test", methods=["POST"])
@require_screen("content_rules")
def test_content_rule():
    """Kaydetmeden önce bir metni mevcut (kaydedilmiş + henüz kaydedilmemiş
    varsayımsal) kurallara karşı denemek için -- panelde "Test Et" butonu."""
    data = request.get_json(silent=True) or {}
    text = data.get("text", "")
    match = check_content(text)
    return jsonify({
        "matched": match is not None,
        "category": match.category if match else None,
        "rule_source": match.rule_source if match else None,
        "snippet": match.snippet if match else None,
    })


@content_rules_bp.route("/flagged-mails")
@require_screen("content_rules")
def list_flagged_mails():
    status = request.args.get("status")
    try:
        limit = min(max(int(request.args.get("limit", 25)), 1), 100)
    except (TypeError, ValueError):
        limit = 25
    try:
        offset = max(int(request.args.get("offset", 0)), 0)
    except (TypeError, ValueError):
        offset = 0

    query = FlaggedMail.query
    if status:
        query = query.filter_by(status=status)
    total = query.count()
    rows = query.order_by(FlaggedMail.created_at.desc()).offset(offset).limit(limit).all()
    return jsonify({
        "flagged_mails": [r.to_dict(reveal=False) for r in rows],
        "total": total, "limit": limit, "offset": offset,
    })


@content_rules_bp.route("/flagged-mails/<int:flagged_id>")
@require_screen("content_rules")
def get_flagged_mail(flagged_id: int):
    row = db.session.get(FlaggedMail, flagged_id)
    if row is None:
        return jsonify({"error": "Kayıt bulunamadı."}), 404
    reveal = request.args.get("reveal") == "true"
    return jsonify({"flagged_mail": row.to_dict(reveal=reveal)})


@content_rules_bp.route("/flagged-mails/<int:flagged_id>/approve", methods=["POST"])
@require_screen("content_rules")
def approve_flagged_mail(flagged_id: int):
    row = db.session.get(FlaggedMail, flagged_id)
    if row is None:
        return jsonify({"error": "Kayıt bulunamadı."}), 404
    if row.status != "pending":
        return jsonify({"error": f"Bu kayıt zaten '{row.status}' durumunda."}), 409

    # main.py'nin process_email'iyle AYNI devam mantığı -- attachment_fields
    # her zaman None: orijinal mailin OCR'lanmış ek dosyaları FlaggedMail'de
    # saklanmıyor, sadece metin (bkz. models.FlaggedMail).
    from main import _continue_after_content_check
    from utils import clean_subject_line

    categorizer = EmailCategorizer()
    csm_client = CSMAPIClient()
    clean_subject = clean_subject_line(row.subject)
    _continue_after_content_check(
        row.sender_email, row.sender_name, row.subject, clean_subject, row.mail_body,
        None, categorizer, csm_client,
    )

    row.status = "approved"
    row.reviewed_by_id = g.current_user.id
    row.reviewed_at = _utcnow()
    db.session.commit()
    record_audit_log(g.current_user, "flagged_mail_approved", detail=f"#{row.id}: {row.sender_email} / {row.subject}")
    return jsonify(row.to_dict(reveal=True))


@content_rules_bp.route("/flagged-mails/<int:flagged_id>/reject", methods=["POST"])
@require_screen("content_rules")
def reject_flagged_mail(flagged_id: int):
    row = db.session.get(FlaggedMail, flagged_id)
    if row is None:
        return jsonify({"error": "Kayıt bulunamadı."}), 404
    if row.status != "pending":
        return jsonify({"error": f"Bu kayıt zaten '{row.status}' durumunda."}), 409

    send_rejection_email(row.sender_email, row.subject, row.sender_name)
    record_mail_event(
        event="email_processed",
        status="rejected",
        sender_email=row.sender_email,
        subject=row.subject,
        reason="Uygunsuz içerik -- operatör tarafından reddedildi",
        classification="rejected_content",
        mail_body=row.mail_body,
    )
    row.status = "rejected"
    row.reviewed_by_id = g.current_user.id
    row.reviewed_at = _utcnow()
    db.session.commit()
    record_audit_log(g.current_user, "flagged_mail_rejected", detail=f"#{row.id}: {row.sender_email} / {row.subject}")
    return jsonify(row.to_dict(reveal=True))
