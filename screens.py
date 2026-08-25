"""Single source of truth for panel screens and role → screen access.

Both the backend (require_screen decorator, accounts_routes) and the
frontend (via /api/auth/me returning effective_screens) key off this module
— add a new screen here once, wire ROLE_SCREENS, and every enforcement point
picks it up automatically. Screens/roles are fixed in code (not DB-managed)
since they change rarely; only per-user overrides live in the database
(see models.UserScreenOverride).
"""

from typing import Iterable

from models import User, UserScreenOverride

# Screen key -> human-readable label (used by the Users admin page and by
# /api/auth/me so the frontend doesn't need its own hardcoded label map).
SCREENS = {
    "dashboard": "Dashboard",
    "reports": "Raporlar",
    "monitoring": "Monitoring",
    "logs": "Loglar",
    "emails": "E-postalar",
    "tickets": "Talepler",
    "bulk_shift": "Toplu Kaydırma",
    "settings": "Ayarlar",
    "users": "Kullanıcılar",
}

# Ticket/log DETAIL routes (/tickets/:id, /logs/:timestamp) use their list
# screen's permission -- they are not separate screen keys.
ROLE_SCREENS: dict[str, set[str]] = {
    "admin": set(SCREENS.keys()),
    "yonetici": set(SCREENS.keys()) - {"users"},
    "operator": {"dashboard", "emails", "tickets", "bulk_shift"},
    "izleyici": {"dashboard", "reports", "monitoring", "logs"},
}


def effective_screens(user: User) -> set[str]:
    """(role's default screens) - (denied overrides) + (granted overrides).

    The one formula every enforcement point (backend decorator, /api/auth/me
    for the frontend menu/route guard) calls -- keeps role defaults and
    per-user exceptions from ever drifting out of sync between frontend and
    backend.
    """
    base = set(ROLE_SCREENS.get(user.role, ()))
    denied = {o.screen_key for o in user.overrides if o.allow is False}
    granted = {o.screen_key for o in user.overrides if o.allow is True}
    return (base - denied) | granted


def role_default_screens(role: str) -> set[str]:
    return set(ROLE_SCREENS.get(role, ()))


def is_valid_screen(screen_key: str) -> bool:
    return screen_key in SCREENS


def screens_payload(user: User) -> dict:
    """Shape returned by /api/auth/me -- role defaults kept separate from the
    final effective set so the Users admin page can render "rolden gelen"
    (checked, role default) vs "ek olarak verildi" (checked, granted
    override) vs unchecked without recomputing anything client-side."""
    return {
        "role": user.role,
        "role_screens": sorted(role_default_screens(user.role)),
        "effective_screens": sorted(effective_screens(user)),
        "overrides": [
            {"screen_key": o.screen_key, "allow": o.allow} for o in user.overrides
        ],
    }
