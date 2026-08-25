"""Creates the first admin user from ADMIN_EMAIL / ADMIN_PASSWORD (.env) --
run once after `flask db upgrade`. Idempotent: does nothing if an admin
already exists, so it's safe to leave in a deploy script.

Usage:
    flask db upgrade
    python seed_admin.py
"""

import os
import sys

from dotenv import load_dotenv

load_dotenv()

from app import app  # noqa: E402  (import after load_dotenv/env is ready)
from accounts import hash_password
from models import User, db


def main() -> None:
    email = os.getenv("ADMIN_EMAIL", "").strip().lower()
    password = os.getenv("ADMIN_PASSWORD", "")

    if not email or not password:
        print("❌ ADMIN_EMAIL ve ADMIN_PASSWORD .env'de tanımlı olmalı.")
        sys.exit(1)
    if len(password) < 8:
        print("❌ ADMIN_PASSWORD en az 8 karakter olmalı.")
        sys.exit(1)

    with app.app_context():
        if User.query.filter_by(role="admin").first():
            print("ℹ️ Zaten bir admin kullanıcısı var, atlanıyor.")
            return

        existing = User.query.filter_by(email=email).first()
        if existing:
            existing.role = "admin"
            existing.is_active = True
            db.session.commit()
            print(f"✅ Mevcut kullanıcı '{email}' admin yapıldı.")
            return

        user = User(email=email, password_hash=hash_password(password), role="admin", is_active=True)
        db.session.add(user)
        db.session.commit()
        print(f"✅ İlk admin kullanıcısı oluşturuldu: {email}")


if __name__ == "__main__":
    main()
