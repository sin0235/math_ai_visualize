import asyncio
import json
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, status

from app.api.deps import require_admin_user, require_trusted_origin
from app.db.models import UserRecord
from app.core.config import Settings, get_settings
from app.db.session import DatabaseClient, create_database_client, get_database
from app.services.model_registry import resolve_effective_settings, save_provider_check, upsert_scanned_models
from app.schemas.scene import AiModelInfo, ModelScanJobCreateResponse, ModelScanJobStatusResponse, ModelScanRequest, ModelScanResponse, ProviderModelScanRequest
from app.services.model_scan import list_provider_models
from app.services.router9_client import Router9Client

router = APIRouter(prefix="/api/ai", tags=["ai-models"])


@router.post("/models/scan", response_model=ModelScanJobCreateResponse, status_code=status.HTTP_202_ACCEPTED, dependencies=[Depends(require_trusted_origin)])
async def scan_provider_models(request: ProviderModelScanRequest, user: UserRecord = Depends(require_admin_user), db: DatabaseClient = Depends(get_database), settings: Settings = Depends(get_settings)) -> ModelScanJobCreateResponse:
    scan_id = await create_scan_job(db, user.id, request.provider)
    asyncio.create_task(process_provider_scan_job(scan_id, request, settings))
    return ModelScanJobCreateResponse(scan_id=scan_id, status="queued")


@router.post("/router9/models/scan", response_model=ModelScanJobCreateResponse, status_code=status.HTTP_202_ACCEPTED, dependencies=[Depends(require_trusted_origin)])
async def scan_router9_models(request: ModelScanRequest, user: UserRecord = Depends(require_admin_user), db: DatabaseClient = Depends(get_database), settings: Settings = Depends(get_settings)) -> ModelScanJobCreateResponse:
    scan_id = await create_scan_job(db, user.id, "router9")
    asyncio.create_task(process_router9_scan_job(scan_id, request, settings))
    return ModelScanJobCreateResponse(scan_id=scan_id, status="queued")


@router.get("/models/scan/{scan_id}", response_model=ModelScanJobStatusResponse)
async def get_model_scan_job(scan_id: str, user: UserRecord = Depends(require_admin_user), db: DatabaseClient = Depends(get_database)) -> ModelScanJobStatusResponse:
    row = await db.fetch_one("SELECT * FROM model_scan_jobs WHERE id = ? AND user_id = ?", [scan_id, user.id])
    if row is None:
        raise HTTPException(status_code=404, detail="Không tìm thấy model scan job.")
    models = [AiModelInfo.model_validate(item) for item in json.loads(str(row.get("models_json") or "[]"))] if row.get("status") == "completed" else []
    return ModelScanJobStatusResponse(
        scan_id=str(row["id"]),
        provider=str(row["provider"]),
        status=str(row.get("status") or "queued"),  # type: ignore[arg-type]
        models=models,
        error=parse_json_object(str(row["error_json"])) if row.get("error_json") is not None else None,
    )


async def process_provider_scan_job(scan_id: str, request: ProviderModelScanRequest, settings: Settings) -> None:
    db = create_database_client(settings)
    await mark_scan_running(db, scan_id)
    effective_settings = await resolve_effective_settings(db, request.runtime_settings)
    try:
        models = await list_provider_models(effective_settings, request.provider)
        await upsert_scanned_models(db, request.provider, models)
        await save_provider_check(db, request.provider, "ok", f"Đã quét {len(models)} model.")
        await mark_scan_completed(db, scan_id, models)
    except RuntimeError as error:
        await save_provider_check(db, request.provider, "error", str(error))
        await mark_scan_failed(db, scan_id, error)


async def process_router9_scan_job(scan_id: str, request: ModelScanRequest, settings: Settings) -> None:
    db = create_database_client(settings)
    await mark_scan_running(db, scan_id)
    effective_settings = await resolve_effective_settings(db, request.runtime_settings)
    try:
        models = await Router9Client(effective_settings).list_models()
        await upsert_scanned_models(db, "router9", models)
        await save_provider_check(db, "router9", "ok", f"Đã quét {len(models)} model.")
        await mark_scan_completed(db, scan_id, models)
    except RuntimeError as error:
        await save_provider_check(db, "router9", "error", str(error))
        await mark_scan_failed(db, scan_id, error)


async def create_scan_job(db: DatabaseClient, user_id: str, provider: str) -> str:
    scan_id = str(uuid4())
    await db.execute("INSERT INTO model_scan_jobs (id, user_id, provider) VALUES (?, ?, ?)", [scan_id, user_id, provider])
    return scan_id


async def mark_scan_running(db: DatabaseClient, scan_id: str) -> None:
    await db.execute("UPDATE model_scan_jobs SET status = 'running', started_at = CURRENT_TIMESTAMP WHERE id = ?", [scan_id])


async def mark_scan_completed(db: DatabaseClient, scan_id: str, models: list[AiModelInfo]) -> None:
    await db.execute(
        "UPDATE model_scan_jobs SET status = 'completed', models_json = ?, finished_at = CURRENT_TIMESTAMP WHERE id = ?",
        [json.dumps([model.model_dump(mode="json") for model in models], ensure_ascii=False), scan_id],
    )


async def mark_scan_failed(db: DatabaseClient, scan_id: str, error: Exception) -> None:
    await db.execute(
        "UPDATE model_scan_jobs SET status = 'failed', error_json = ?, finished_at = CURRENT_TIMESTAMP WHERE id = ?",
        [json.dumps({"message": str(error) or error.__class__.__name__}, ensure_ascii=False), scan_id],
    )


def parse_json_object(value: str | None) -> dict | None:
    if not value:
        return None
    parsed = json.loads(value)
    return parsed if isinstance(parsed, dict) else None
