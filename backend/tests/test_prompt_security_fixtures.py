"""Red-team fixture gates for prompt-injection allow/block corpora."""

from __future__ import annotations

import importlib
import json
from pathlib import Path

import pytest

from app.services.prompt_security import SYSTEM_PROMPT_SECURITY_PREFIX, classify_prompt_injection
from app.services.prompt_security_registry import SECURED_SYSTEM_PROMPTS, USER_ENVELOPE_BUILDERS

FIXTURE_DIR = Path(__file__).resolve().parent / "fixtures" / "prompt_injection"


def _load_jsonl(name: str) -> list[dict]:
    path = FIXTURE_DIR / name
    rows: list[dict] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        rows.append(json.loads(line))
    return rows


def test_block_fixture_threshold():
    rows = _load_jsonl("block.jsonl")
    assert rows, "block.jsonl empty"
    blocked = sum(1 for row in rows if classify_prompt_injection(row["text"]).blocked)
    rate = blocked / len(rows)
    assert rate >= 0.95, f"block rate {rate:.0%} < 95% ({blocked}/{len(rows)})"


def test_allow_fixture_threshold():
    rows = _load_jsonl("allow.jsonl")
    assert rows, "allow.jsonl empty"
    false_pos = [row["text"] for row in rows if classify_prompt_injection(row["text"]).blocked]
    rate = len(false_pos) / len(rows)
    assert rate <= 0.01, f"false positive rate {rate:.0%} > 1%: {false_pos}"


@pytest.mark.parametrize("module_path,symbol", SECURED_SYSTEM_PROMPTS)
def test_registry_system_prompts_are_secured(module_path: str, symbol: str):
    module = importlib.import_module(module_path)
    prompt = getattr(module, symbol)
    assert isinstance(prompt, str) and prompt.strip()
    assert "Ràng buộc hệ thống cố định" in prompt or prompt.startswith(SYSTEM_PROMPT_SECURITY_PREFIX)
    assert "không tin cậy" in prompt


@pytest.mark.parametrize("module_path,symbol", USER_ENVELOPE_BUILDERS)
def test_registry_user_builders_exist(module_path: str, symbol: str):
    module = importlib.import_module(module_path)
    assert callable(getattr(module, symbol))
