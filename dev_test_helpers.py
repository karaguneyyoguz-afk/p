"""Shared helper for the test_*.py scripts that hit /api/* through a Flask
test client -- every route now requires a logged-in session + screen
permission (see accounts.require_screen), so tests exercising those routes
need to log in first.

IMPORTANT: the test file importing this must set os.environ['DATABASE_URL']
to a temp SQLite file BEFORE importing app (this helper can't do that for
you -- app.py reads DATABASE_URL at import time to configure SQLAlchemy) so
tests never touch the real instance/enigma.db.
"""

from accounts import hash_password
from models import User, db


def login_test_client(app, client, email="tester@local.test", password="Test-Sifre-123", role="admin"):
    """Ensures tables exist, creates (if needed) a test user with the given
    role, logs them in via the given test client, and returns the CSRF token
    to attach as the X-CSRF-Token header on subsequent mutating requests."""
    with app.app_context():
        db.create_all()
        user = User.query.filter_by(email=email).first()
        if user is None:
            user = User(email=email, password_hash=hash_password(password), role=role, is_active=True)
            db.session.add(user)
            db.session.commit()

    resp = client.post("/api/auth/login", json={"email": email, "password": password})
    assert resp.status_code == 200, resp.get_json()
    return resp.get_json()["csrf_token"]
