import logging
import re

from app.core.config import Settings
from app.schemas.scene import AiModelInfo
from app.services.router9_client import Router9Client

logger = logging.getLogger(__name__)
_CODEX_VERSION_RE = re.compile(r"codex[^0-9]*(\d+(?:\.\d+)*)", re.IGNORECASE)
_GPT_VERSION_RE = re.compile(r"gpt[^0-9]*(\d+(?:\.\d+)*)", re.IGNORECASE)
_LEGACY_MIN_CODEX_VERSION = (5, 1)
_RENDER_CODEX_VERSIONS = ((5, 5), (5, 4), (5, 3))
_OCR_CODEX_VERSIONS = ((5, 5), (5, 4))


async def bootstrap_router9_models(settings: Settings) -> None:
    if not settings.router9_api_key:
        return
    try:
        models = await Router9Client(settings).list_models()
    except RuntimeError as error:
        logger.warning("Không thể tự động quét model 9router lúc khởi động: %s", error)
        return

    render_model_ids = select_router9_render_model_ids(models)
    ocr_model_ids = select_router9_ocr_model_ids(models)
    preferred_model_ids = _merge_model_ids(ocr_model_ids, render_model_ids)
    if not preferred_model_ids:
        return

    settings.router9_allowed_models = _merge_model_ids(settings.router9_allowed_models, preferred_model_ids)
    if render_model_ids and (not settings.router9_text_model or settings.router9_text_model not in settings.router9_allowed_models):
        settings.router9_text_model = render_model_ids[0]
    if ocr_model_ids and (not settings.router9_ocr_model or settings.router9_ocr_model not in settings.router9_allowed_models):
        settings.router9_ocr_model = ocr_model_ids[0]


def select_codex_model_ids(models: list[AiModelInfo]) -> list[str]:
    candidates = [model.id for model in models if _codex_version(model.id) >= _LEGACY_MIN_CODEX_VERSION]
    return sorted(candidates, key=lambda model_id: (_codex_version(model_id), model_id.lower()), reverse=True)


def select_router9_render_model_ids(models: list[AiModelInfo]) -> list[str]:
    model_ids = [model.id for model in models]
    return select_router9_render_model_ids_from_ids(model_ids)


def select_router9_ocr_model_ids(models: list[AiModelInfo]) -> list[str]:
    model_ids = [model.id for model in models]
    return select_router9_ocr_model_ids_from_ids(model_ids)


def select_router9_render_model_ids_from_ids(model_ids: list[str]) -> list[str]:
    return _select_by_score(model_ids, _render_model_score)


def select_router9_ocr_model_ids_from_ids(model_ids: list[str]) -> list[str]:
    selected = _select_by_score(model_ids, _ocr_model_score)
    primary = [model_id for model_id in selected if (_ocr_model_score(model_id) or (9, 9))[0] < 3]
    return primary or selected


def _render_model_score(model_id: str) -> tuple[int, int] | None:
    codex_version = _codex_version(model_id)
    if codex_version in _RENDER_CODEX_VERSIONS:
        image_penalty = 1 if _looks_image_model(model_id) else 0
        return (0, _RENDER_CODEX_VERSIONS.index(codex_version) * 2 + image_penalty)
    if _is_github_gpt_52(model_id):
        return (1, 0)
    if _gpt_version(model_id) == (5, 2):
        return (2, 0)
    return None


def _ocr_model_score(model_id: str) -> tuple[int, int] | None:
    codex_version = _codex_version(model_id)
    if codex_version in _OCR_CODEX_VERSIONS and _looks_image_model(model_id):
        return (0, _OCR_CODEX_VERSIONS.index(codex_version))
    if _is_github_gpt_52(model_id):
        return (1, 0)
    if _gpt_version(model_id) == (5, 2):
        return (2, 0)
    if codex_version in _OCR_CODEX_VERSIONS:
        return (3, _OCR_CODEX_VERSIONS.index(codex_version))
    return None


def _codex_version(model_id: str) -> tuple[int, ...]:
    match = _CODEX_VERSION_RE.search(model_id)
    if not match:
        return ()
    return tuple(int(part) for part in match.group(1).split("."))


def _gpt_version(model_id: str) -> tuple[int, ...]:
    match = _GPT_VERSION_RE.search(model_id)
    if not match:
        return ()
    return tuple(int(part) for part in match.group(1).split("."))


def _looks_image_model(model_id: str) -> bool:
    lowered = model_id.lower()
    return any(marker in lowered for marker in ("image", "vision", "vl"))


def _is_github_gpt_52(model_id: str) -> bool:
    lowered = model_id.lower()
    if _gpt_version(model_id) != (5, 2):
        return False
    return "github" in lowered or "copilot" in lowered or re.search(r"(^|[/:_-])gh([/:_-]|$)", lowered) is not None


def _select_by_score(model_ids: list[str], score_fn) -> list[str]:
    scored: list[tuple[tuple[int, int, str], str]] = []
    for model_id in model_ids:
        score = score_fn(model_id)
        if score is None:
            continue
        scored.append(((score[0], score[1], model_id.lower()), model_id))
    return [model_id for _, model_id in sorted(scored)]


def _merge_model_ids(existing: list[str], additional: list[str]) -> list[str]:
    seen: set[str] = set()
    merged: list[str] = []
    for model_id in [*existing, *additional]:
        if model_id not in seen:
            seen.add(model_id)
            merged.append(model_id)
    return merged
