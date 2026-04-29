import logging
import re

from app.core.config import Settings
from app.schemas.scene import AiModelInfo
from app.services.router9_client import Router9Client

logger = logging.getLogger(__name__)
_CODEX_VERSION_RE = re.compile(r"codex[^0-9]*(\d+(?:\.\d+)*)", re.IGNORECASE)
_MIN_CODEX_VERSION = (5, 1)


async def bootstrap_router9_models(settings: Settings) -> None:
    if not settings.router9_api_key:
        return
    try:
        models = await Router9Client(settings).list_models()
    except RuntimeError as error:
        logger.warning("Không thể tự động quét model 9router lúc khởi động: %s", error)
        return

    codex_model_ids = select_codex_model_ids(models)
    if not codex_model_ids:
        return

    settings.router9_allowed_models = _merge_model_ids(settings.router9_allowed_models, codex_model_ids)
    if not settings.router9_text_model or settings.router9_text_model not in settings.router9_allowed_models:
        settings.router9_text_model = codex_model_ids[0]
    if not settings.router9_ocr_model or settings.router9_ocr_model not in codex_model_ids:
        settings.router9_ocr_model = codex_model_ids[0]


def select_codex_model_ids(models: list[AiModelInfo]) -> list[str]:
    candidates = [model.id for model in models if _codex_version(model.id) >= _MIN_CODEX_VERSION]
    return sorted(candidates, key=lambda model_id: (_codex_version(model_id), model_id.lower()), reverse=True)


def _codex_version(model_id: str) -> tuple[int, ...]:
    match = _CODEX_VERSION_RE.search(model_id)
    if not match:
        return ()
    return tuple(int(part) for part in match.group(1).split("."))


def _merge_model_ids(existing: list[str], additional: list[str]) -> list[str]:
    seen: set[str] = set()
    merged: list[str] = []
    for model_id in [*existing, *additional]:
        if model_id not in seen:
            seen.add(model_id)
            merged.append(model_id)
    return merged
