from __future__ import annotations

from collections.abc import Iterable

from app.services.prompt_security import secure_system_prompt


def compile_json_task_prompt(
    *,
    role: str,
    task: str,
    contract: Iterable[str],
    invariants: Iterable[str],
    self_check: Iterable[str],
) -> str:
    sections = (
        role.strip(),
        "NHIỆM VỤ\n" + task.strip(),
        "OUTPUT CONTRACT\n- " + "\n- ".join(item.strip() for item in contract),
        "BẤT BIẾN\n- " + "\n- ".join(item.strip() for item in invariants),
        "SELF-CHECK NỘI BỘ\n- " + "\n- ".join(item.strip() for item in self_check),
    )
    return secure_system_prompt("\n\n".join(section for section in sections if section), output_mode="json")