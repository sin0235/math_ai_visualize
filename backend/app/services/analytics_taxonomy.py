"""Canonical product analytics event types."""

from __future__ import annotations

# Auth
AUTH_REGISTER = "auth.register"
AUTH_LOGIN = "auth.login"
AUTH_VERIFY = "auth.verify"
AUTH_LOGOUT = "auth.logout"

# Navigation / feature
PAGE_VIEW = "page.view"
FEATURE_OPEN = "feature.open"

# Domain outcomes (existing)
RENDER_QUEUED = "render.queued"
RENDER_COMPLETED = "render.completed"
RENDER_FAILED = "render.failed"
OCR_COMPLETED = "ocr.completed"
OCR_FAILED = "ocr.failed"
ALGEBRA_COMPLETED = "algebra.completed"
ALGEBRA_FAILED = "algebra.failed"
SOLVE_COMPLETED = "solve.completed"
SOLVE_FAILED = "solve.failed"
EXPORT_COMPLETED = "export.completed"
ANALYZE_COMPLETED = "analyze.completed"
ANALYZE_FAILED = "analyze.failed"

# Client
CLIENT_ERROR = "client.error"
CLIENT_API_ERROR = "client.api_error"

FEATURE_KEYS = frozenset({
    "home",
    "render",
    "analyzer",
    "algebra-solver",
    "simulation",
    "geogebra-lab",
    "history",
    "settings",
    "account",
    "admin",
    "chat",
    "feedback",
    "guide",
    "about",
    "login",
})

ALLOWED_CLIENT_EVENT_TYPES = frozenset({
    PAGE_VIEW,
    FEATURE_OPEN,
    CLIENT_ERROR,
    CLIENT_API_ERROR,
})
