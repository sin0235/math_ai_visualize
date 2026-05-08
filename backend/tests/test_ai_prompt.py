"""Regression test: đảm bảo các phần quan trọng của AI prompt còn nguyên.

Khi prompt bị refactor, các block ràng buộc reference/expression/self-check
phải còn nguyên — vì validator + verifier dựa vào hành vi LLM tuân theo
prompt này. Nếu mất, chất lượng output sẽ tụt rõ rệt.
"""

import pytest

from app.services.ai_prompt import (
    REASONING_SYSTEM_PROMPT,
    SCENE_EXTRACTION_SYSTEM_PROMPT,
)


# ---------------------------------------------------------------------------
# Scene extraction prompt
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("snippet", [
    "Reference Integrity",
    "Expression Integrity",
    "Self-check",
    "Quy tắc relation type",
    "midpoint",
    "on_plane",
    "on_line",
    "on_sphere",
    "on_circle",
    "collinear",
    "coplanar",
    "tangent",
    "distance",
    "angle",
])
def test_scene_extraction_prompt_contains(snippet: str):
    assert snippet in SCENE_EXTRACTION_SYSTEM_PROMPT, (
        f"SCENE_EXTRACTION_SYSTEM_PROMPT thiếu phần '{snippet}' — "
        "đây là ràng buộc bắt buộc cho validator/verifier"
    )


@pytest.mark.parametrize("relation", [
    '"type":"midpoint"',
    '"type":"on_plane"',
    '"type":"on_line"',
    '"type":"on_sphere"',
    '"type":"on_circle"',
    '"type":"collinear"',
    '"type":"coplanar"',
    '"type":"tangent"',
    '"type":"distance"',
    '"type":"angle"',
])
def test_scene_prompt_has_relation_example(relation: str):
    """Mỗi loại relation phải có ví dụ JSON cụ thể trong schema."""
    assert relation in SCENE_EXTRACTION_SYSTEM_PROMPT


def test_scene_prompt_warns_about_dropping_invalid_refs():
    """Phải nói rõ tham chiếu sai sẽ bị drop để LLM tự sửa."""
    text = SCENE_EXTRACTION_SYSTEM_PROMPT.lower()
    assert "drop" in text or "bỏ" in text or "loại bỏ" in text


def test_scene_prompt_mentions_naming_uniqueness():
    """Phải có ràng buộc: tên object phải duy nhất."""
    text = SCENE_EXTRACTION_SYSTEM_PROMPT
    assert "duy nhất" in text or "unique" in text.lower() or "trùng" in text


# ---------------------------------------------------------------------------
# Reasoning prompt
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("snippet", [
    "Self-check",
    "midpoint",
    "on_plane",
    "on_line",
])
def test_reasoning_prompt_contains(snippet: str):
    assert snippet in REASONING_SYSTEM_PROMPT, (
        f"REASONING_SYSTEM_PROMPT thiếu phần '{snippet}'"
    )
