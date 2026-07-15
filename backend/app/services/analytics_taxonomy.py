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
NLP_PREFLIGHT = "nlp.preflight"

NLP_UNKNOWN_INTENT = "unknown_intent"
NLP_LOW_CONFIDENCE = "low_confidence"
NLP_CLARIFICATION_SHOWN = "clarification_shown"
NLP_CLARIFICATION_ACCEPTED = "clarification_accepted"
NLP_CLARIFICATION_EDITED = "clarification_edited"
NLP_CANONICAL_VALIDATION_FAILURE = "canonical_validation_failure"
NLP_SOLVER_UNSUPPORTED = "solver_unsupported"
NLP_EXPLAINER_FALLBACK = "explainer_fallback"
NLP_SHADOW_MISMATCH = "shadow_mismatch"

NLP_TAXONOMY_CODES = frozenset({
    NLP_UNKNOWN_INTENT,
    NLP_LOW_CONFIDENCE,
    NLP_CLARIFICATION_SHOWN,
    NLP_CLARIFICATION_ACCEPTED,
    NLP_CLARIFICATION_EDITED,
    NLP_CANONICAL_VALIDATION_FAILURE,
    NLP_SOLVER_UNSUPPORTED,
    NLP_EXPLAINER_FALLBACK,
    NLP_SHADOW_MISMATCH,
})
NLP_VALIDATION_CODES = frozenset({
    "unsupported",
    "unknown_intent",
    "missing_fields",
    "missing_goal",
    "ambiguities",
    "missing_canonical_text",
    "critic_review",
    "candidate_disagreement",
    "single_candidate",
    "invalid_evidence",
    "invalid_canonical",
})

NLP_STATUSES = frozenset({"accepted", "needs_confirmation", "abstained", "unsupported"})
NLP_CONFIDENCE_BUCKETS = frozenset({"very_low", "low", "medium", "high", "very_high"})
NLP_TARGETS = frozenset({"render", "geometry_solve", "algebra", "analyzer", "ocr"})

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
    NLP_PREFLIGHT,
})
