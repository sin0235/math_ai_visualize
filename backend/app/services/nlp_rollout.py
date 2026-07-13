from __future__ import annotations

import asyncio
import logging

from app.db.session import DatabaseClient
from app.repositories.activity import try_log_user_activity
from app.schemas.nlp import InputEnvelope
from app.services.analytics_taxonomy import NLP_TARGETS, NLP_TAXONOMY_CODES
from app.services.nlp.rollout import NlpRolloutDecision, evaluate_nlp_rollout
from app.services.system_settings import load_feature_flags

logger = logging.getLogger(__name__)


async def log_nlp_taxonomy(
    db: DatabaseClient,
    *,
    user_id: str | None,
    taxonomy_code: str,
    target: str,
    status: str | None = None,
    request_id: str | None = None,
) -> None:
    if user_id is None or taxonomy_code not in NLP_TAXONOMY_CODES or target not in NLP_TARGETS:
        return
    metadata = {"taxonomy_code": taxonomy_code, "target": target}
    if status:
        metadata["status"] = status[:32]
    if request_id:
        metadata["request_id"] = request_id[:80]
    await try_log_user_activity(
        db,
        user_id,
        "nlp.outcome",
        target_type="nlp",
        target_id=taxonomy_code,
        metadata=metadata,
        source="server",
    )


async def evaluate_configured_nlp_rollout(
    db: DatabaseClient,
    envelope: InputEnvelope,
    *,
    user_id: str | None,
    request_id: str | None = None,
    legacy_intent: str | None = None,
    legacy_status: str | None = None,
    legacy_canonical: str | None = None,
) -> NlpRolloutDecision | None:
    try:
        flags = await asyncio.wait_for(load_feature_flags(db), timeout=1.0)
    except Exception:
        logger.warning("Không thể tải cờ NLP rollout; giữ pipeline legacy", exc_info=True)
        return None
    decision = evaluate_nlp_rollout(
        envelope,
        shadow_rules=flags.nlp_shadow_rules,
        authoritative_rules=flags.nlp_authoritative_rules,
        legacy_intent=legacy_intent,
        legacy_status=legacy_status,
        legacy_canonical=legacy_canonical,
    )
    if decision is None or not decision.mismatch or user_id is None:
        return decision
    metadata = decision.safe_metadata
    if request_id:
        metadata["request_id"] = request_id[:80]
    await try_log_user_activity(
        db,
        user_id,
        "nlp.rollout",
        target_type="nlp",
        target_id="shadow_mismatch",
        metadata=metadata,
        source="server",
    )
    return decision