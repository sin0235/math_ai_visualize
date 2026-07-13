"""Registry of LLM entrypoints that must use prompt_security helpers.

Used by tests to prevent regressions when new LLM paths are added.
Update this list when adding a new system prompt / chat completion path.
"""

from __future__ import annotations

# (module_path, symbol_name, expected_secure: bool)
# expected_secure means the constant should already include security boundary text.
SECURED_SYSTEM_PROMPTS: list[tuple[str, str]] = [
    ("app.services.openrouter_client", "OCR_SYSTEM_PROMPT"),
    ("app.services.ocr", "DIAGRAM_OCR_SYSTEM_PROMPT"),
    ("app.services.algebra.ai_extraction", "ALGEBRA_EXTRACTION_SYSTEM_PROMPT"),
    ("app.services.algebra.ai_explainer", "ALGEBRA_EXPLAINER_SYSTEM_PROMPT"),
    ("app.services.solver_explainer", "SOLVER_EXPLAINER_SYSTEM_PROMPT_OXYZ"),
    ("app.services.solver_explainer", "SOLVER_EXPLAINER_SYSTEM_PROMPT_CLASSICAL"),
    ("app.services.problem_variants", "VARIANTS_SYSTEM_PROMPT"),
    ("app.api.routes_function_analysis", "FUNCTION_EXTRACT_SYSTEM_PROMPT"),
    ("app.services.ai_prompt", "SCENE_EXTRACTION_V3_SYSTEM_PROMPT"),
    ("app.services.ai_prompt", "SCENE_REPAIR_V3_SYSTEM_PROMPT"),
    ("app.services.ai_prompt", "REASONING_SYSTEM_PROMPT"),
]

# Paths that assemble user messages via envelope_untrusted / build_* helpers.
USER_ENVELOPE_BUILDERS: list[tuple[str, str]] = [
    ("app.services.ai_prompt", "build_reasoning_prompt"),
    ("app.services.ai_prompt", "build_scene_extraction_prompt"),
    ("app.services.ai_prompt", "build_scene_repair_v3_prompt"),
    ("app.services.problem_variants", "_build_user_prompt"),
    ("app.api.routes_function_analysis", "_build_function_extract_prompt"),
]

# Chat product is human support (no LLM). Documented so audits do not flag it.
NON_LLM_CHAT_NOTE = "routes_chat.py is human-admin support chat; no model system prompt."
