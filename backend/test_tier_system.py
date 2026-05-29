"""
Test script cho hệ thống 3-tier model AI
Kiểm tra luồng render-only từ schema -> DB migration -> service -> API
"""
import asyncio
import json
from pathlib import Path

async def test_tier_system():
    print("=== TEST 1: Schema validation ===")
    from fastapi import HTTPException

    from app.schemas.auth import SystemAiProfiles, SystemAiTierProfiles, SystemSettingRequest
    from app.schemas.scene import RenderRequest

    profiles = SystemAiTierProfiles(
        version=3,
        tier1={"tier": "tier1", "default_model": "router9/fast-model", "models": ["router9/fast-model"]},
        tier2={"tier": "tier2", "default_model": "router9/balanced-model", "models": ["router9/balanced-model", "router9/support-model"]},
        tier3={"tier": "tier3", "default_model": "router9/best-model", "models": ["router9/best-model"]},
    )
    assert profiles.tier2.default_model == "router9/balanced-model"
    print(f"✓ SystemAiTierProfiles: tier2.default={profiles.tier2.default_model}, models={profiles.tier2.models}")

    legacy_profiles = SystemAiTierProfiles.model_validate({
        "version": 2,
        "render": {
            "tier1": {"tier": "tier1", "provider": "router9", "model": "fast-model", "fallbacks": []},
            "tier2": {"tier": "tier2", "provider": "router9", "model": "balanced-model", "fallbacks": ["fast-model"]},
            "tier3": {"tier": "tier3", "provider": "router9", "model": "best-model", "fallbacks": ["balanced-model"]},
        },
        "reasoning": {
            "tier1": {"tier": "tier1", "provider": "router9", "model": "should-not-sync", "fallbacks": []},
        },
        "solver_explanation": {
            "tier1": {"tier": "tier1", "provider": "router9", "model": "should-not-sync", "fallbacks": []},
        },
    })
    assert legacy_profiles.tier2.models == ["router9/balanced-model"]
    assert legacy_profiles.tier2.default_model == "router9/balanced-model"
    print("✓ Legacy schema migrates only render tier primary models")

    req = RenderRequest(problem_text="Cho tam giác ABC", grade=10, tier="tier1")
    print(f"✓ RenderRequest: tier={req.tier}, no preferred_ai_provider/model")
    setting_req = SystemSettingRequest(key="ai_tier_profiles", value=profiles.model_dump())
    assert setting_req.key == "ai_tier_profiles"
    print("✓ SystemSettingRequest accepts ai_tier_profiles")

    print("\n=== TEST 2: Database migration ===")
    from app.db.session import SQLiteClient

    test_db = Path('/tmp/test_tier_full.db')
    test_db.unlink(missing_ok=True)
    db = SQLiteClient(str(test_db))

    # Tạo schema gốc (giống production trước migration)
    await db.execute('''
        CREATE TABLE ai_task_profiles (
          task TEXT PRIMARY KEY,
          provider_id TEXT NOT NULL DEFAULT 'auto',
          model_id TEXT NOT NULL DEFAULT '',
          fallbacks_json TEXT NOT NULL DEFAULT '[]',
          updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    # Chạy migration
    migration_sql = (Path(__file__).resolve().parents[1] / 'migrations/0009_ai_tier_profiles.sql').read_text()
    # Split và chạy từng statement
    import re
    statements = [s.strip() for s in re.split(r';\s*(?=\n|$)', migration_sql) if s.strip()]
    for statement in statements:
        try:
            await db.execute(statement)
        except Exception as e:
            if 'duplicate column' not in str(e).lower():
                raise

    rows = await db.fetch_all('SELECT task, tier FROM ai_task_profiles ORDER BY task')
    assert [row["task"] for row in rows] == ["render_tier1", "render_tier2", "render_tier3"]
    print(f"✓ Migration: seeded {len(rows)} render tier profiles")

    await db.execute("INSERT INTO ai_task_profiles (task, provider_id, model_id, fallbacks_json, tier) VALUES ('reasoning_tier1', 'router9', 'bad', '[]', 'tier1')")
    await db.execute("INSERT INTO ai_task_profiles (task, provider_id, model_id, fallbacks_json, tier) VALUES ('solver_explanation_tier1', 'router9', 'bad', '[]', 'tier1')")
    cleanup_sql = (Path(__file__).resolve().parents[1] / 'migrations/0018_render_only_tier_profiles.sql').read_text()
    for statement in [s.strip() for s in re.split(r';\s*(?=\n|$)', cleanup_sql) if s.strip()]:
        await db.execute(statement)
    rows = await db.fetch_all("SELECT task FROM ai_task_profiles WHERE task LIKE '%tier%' ORDER BY task")
    assert [row["task"] for row in rows] == ["render_tier1", "render_tier2", "render_tier3"]
    print("✓ Migration cleanup: removed non-render tier rows")

    print("\n=== TEST 3: Service layer ===")
    from app.services.admin_settings import sync_ai_profiles_to_registry, sync_ai_tier_profiles_to_registry

    await sync_ai_tier_profiles_to_registry(db, legacy_profiles.model_dump(), None)
    rows = await db.fetch_all("SELECT task, provider_id, model_id, fallbacks_json FROM ai_task_profiles WHERE task LIKE '%tier%' ORDER BY task")
    assert len(rows) == 3
    assert all(row["task"].startswith("render_tier") for row in rows)
    tier2 = next(row for row in rows if row["task"] == "render_tier2")
    assert tier2["provider_id"] == "router9"
    assert tier2["model_id"] == "balanced-model"
    assert json.loads(tier2["fallbacks_json"]) == []
    print(f"✓ Sync: {len(rows)} render-only tier profiles synced")

    await sync_ai_tier_profiles_to_registry(db, profiles.model_dump(), None)
    tier2 = await db.fetch_one("SELECT provider_id, model_id, fallbacks_json FROM ai_task_profiles WHERE task = 'render_tier2'")
    assert tier2["provider_id"] == "router9"
    assert tier2["model_id"] == "balanced-model"
    assert json.loads(tier2["fallbacks_json"]) == ["support-model"]
    print("✓ Sync: default_model is stored as tier primary model")

    await sync_ai_profiles_to_registry(
        db,
        SystemAiProfiles(
            version=1,
            geometry_reasoning={"provider": "router9", "model": "reasoning-model", "fallbacks": ["should-not-render"]},
        ).model_dump(),
        None,
    )
    render_profile = await db.fetch_one("SELECT task FROM ai_task_profiles WHERE task = 'render'")
    reasoning_profile = await db.fetch_one("SELECT provider_id, model_id, fallbacks_json FROM ai_task_profiles WHERE task = 'reasoning'")
    assert render_profile is None
    assert reasoning_profile["provider_id"] == "router9"
    assert reasoning_profile["model_id"] == "reasoning-model"
    assert json.loads(reasoning_profile["fallbacks_json"]) == []
    print("✓ Sync: AI geometry profile does not create or override render profile")

    print("\n=== TEST 4: API validation ===")
    from app.api.routes_admin import validate_ai_tier_profiles_rules

    validate_ai_tier_profiles_rules(profiles)
    print("✓ Validation: render tier profiles valid")
    validate_ai_tier_profiles_rules(legacy_profiles)
    print("✓ Validation: legacy fallback duplicates are ignored")

    empty_profiles = SystemAiTierProfiles(version=3)
    validate_ai_tier_profiles_rules(empty_profiles)
    print("✓ Validation: accepts empty tier as render default fallback")

    duplicate_profiles = SystemAiTierProfiles(
        version=3,
        tier1={"tier": "tier1", "default_model": "router9/fast-model", "models": ["router9/fast-model"]},
        tier2={"tier": "tier2", "default_model": "router9/fast-model", "models": ["router9/fast-model"]},
        tier3={"tier": "tier3", "models": []},
    )
    try:
        validate_ai_tier_profiles_rules(duplicate_profiles)
        raise AssertionError("Duplicate tier model should be rejected")
    except HTTPException:
        print("✓ Validation: duplicate model across tiers rejected")

    ambiguous_profiles = SystemAiTierProfiles(
        version=3,
        tier1={"tier": "tier1", "models": ["fast-model"]},
    )
    try:
        validate_ai_tier_profiles_rules(ambiguous_profiles)
        raise AssertionError("Unprefixed tier model should be rejected")
    except HTTPException:
        print("✓ Validation: unprefixed tier model rejected")

    test_db.unlink()
    print("\n=== ALL TESTS PASSED ===")

if __name__ == "__main__":
    asyncio.run(test_tier_system())
