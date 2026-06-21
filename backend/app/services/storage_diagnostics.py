from __future__ import annotations

import hashlib
import time
from dataclasses import dataclass, field
from typing import Literal

from app.core.config import Settings
from app.services import appwrite_storage, r2_storage

StorageCheckProvider = Literal["auto", "appwrite", "r2"]
SMOKE_BODY = b"storage-smoke-check"
SMOKE_FILENAME = "storage-smoke-check.txt"
SMOKE_CONTENT_TYPE = "text/plain"


@dataclass
class StorageCheckState:
    provider: str
    configured: bool
    status: str = "skipped"
    steps: list[dict[str, str]] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    storage_key: str | None = None
    external_file_id: str | None = None
    latency_ms: int = 0

    def step(self, name: str, status: str, message: str) -> None:
        self.steps.append({"name": name, "status": status, "message": message})

    def as_dict(self) -> dict:
        return {
            "provider": self.provider,
            "configured": self.configured,
            "status": self.status,
            "steps": self.steps,
            "warnings": self.warnings,
            "storage_key": self.storage_key,
            "external_file_id": self.external_file_id,
            "latency_ms": self.latency_ms,
        }


async def check_upload_storage(
    settings: Settings,
    provider: StorageCheckProvider = "auto",
    write: bool = False,
    read_back: bool = True,
    delete_after: bool = True,
) -> dict:
    providers = selected_providers(provider, settings)
    results = []
    for item in providers:
        if item == "appwrite":
            results.append(await check_appwrite(settings, write, read_back, delete_after))
        elif item == "r2":
            results.append(check_r2(settings, write, read_back, delete_after))
    overall = "ok" if any(result["status"] == "ok" for result in results) else "error"
    if results and all(result["status"] == "skipped" for result in results):
        overall = "skipped"
    return {"provider": provider, "status": overall, "results": results}


def selected_providers(provider: StorageCheckProvider, settings: Settings) -> list[str]:
    if provider in {"appwrite", "r2"}:
        return [provider]
    providers: list[str] = []
    if appwrite_storage.appwrite_configured(settings):
        providers.append("appwrite")
    if r2_storage.r2_configured(settings):
        providers.append("r2")
    return providers or ["appwrite", "r2"]


async def check_appwrite(settings: Settings, write: bool, read_back: bool, delete_after: bool) -> dict:
    started = time.monotonic()
    state = StorageCheckState("appwrite", appwrite_storage.appwrite_configured(settings))
    if not state.configured:
        state.step("config", "error", "Appwrite storage chưa được cấu hình đầy đủ.")
        state.status = "skipped"
        state.latency_ms = elapsed_ms(started)
        return state.as_dict()
    state.step("config", "ok", "Appwrite storage đã có cấu hình bắt buộc.")
    if not write:
        state.status = "ok"
        state.latency_ms = elapsed_ms(started)
        return state.as_dict()
    try:
        stored = await appwrite_storage.store_file(SMOKE_BODY, SMOKE_FILENAME, SMOKE_CONTENT_TYPE, settings)
        state.storage_key = stored.storage_key
        state.external_file_id = stored.file_id
        state.step("write", "ok", "Đã upload smoke object lên Appwrite.")
        if read_back:
            loaded = await appwrite_storage.load_file(stored.file_id, settings, stored.bucket_id)
            verify_smoke_body(loaded)
            state.step("read", "ok", "Đã đọc lại smoke object và checksum khớp.")
        if delete_after:
            try:
                await appwrite_storage.delete_file(stored.file_id, settings, stored.bucket_id)
                state.step("delete", "ok", "Đã xoá smoke object khỏi Appwrite.")
            except Exception as error:
                state.step("delete", "warning", "Không xoá được smoke object khỏi Appwrite.")
                state.warnings.append(f"Appwrite delete smoke failed: {short_error(error)}")
        state.status = "ok"
    except Exception as error:
        state.step("smoke", "error", short_error(error))
        state.status = "error"
    state.latency_ms = elapsed_ms(started)
    return state.as_dict()


def check_r2(settings: Settings, write: bool, read_back: bool, delete_after: bool) -> dict:
    started = time.monotonic()
    state = StorageCheckState("r2", r2_storage.r2_configured(settings))
    if not state.configured:
        state.step("config", "error", "R2 storage chưa được cấu hình đầy đủ.")
        state.status = "skipped"
        state.latency_ms = elapsed_ms(started)
        return state.as_dict()
    state.step("config", "ok", "R2 storage đã có cấu hình bắt buộc.")
    if not write:
        state.status = "ok"
        state.latency_ms = elapsed_ms(started)
        return state.as_dict()
    try:
        object_key = r2_storage.store_file(SMOKE_BODY, SMOKE_FILENAME, SMOKE_CONTENT_TYPE, settings)
        state.storage_key = object_key
        state.step("write", "ok", "Đã upload smoke object lên R2.")
        if read_back:
            loaded = r2_storage.load_file(object_key, settings)
            verify_smoke_body(loaded)
            state.step("read", "ok", "Đã đọc lại smoke object và checksum khớp.")
        if delete_after:
            try:
                r2_storage.delete_file(object_key, settings)
                state.step("delete", "ok", "Đã xoá smoke object khỏi R2.")
            except Exception as error:
                state.step("delete", "warning", "Không xoá được smoke object khỏi R2.")
                state.warnings.append(f"R2 delete smoke failed: {short_error(error)}")
        state.status = "ok"
    except Exception as error:
        state.step("smoke", "error", short_error(error))
        state.status = "error"
    state.latency_ms = elapsed_ms(started)
    return state.as_dict()


def verify_smoke_body(body: bytes) -> None:
    if hashlib.sha256(body).hexdigest() != hashlib.sha256(SMOKE_BODY).hexdigest():
        raise RuntimeError("Smoke object đọc lại không khớp checksum.")


def elapsed_ms(started: float) -> int:
    return int((time.monotonic() - started) * 1000)


def short_error(error: Exception) -> str:
    message = " ".join(str(error).split()) or error.__class__.__name__
    return message[:240] + ("..." if len(message) > 240 else "")
