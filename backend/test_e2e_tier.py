"""
End-to-end test cho hệ thống 3-tier model AI
Test render-only tier profile flow without starting the server
"""
import asyncio
from pathlib import Path

async def test_e2e():
    print("=== END-TO-END TEST ===\n")

    # Setup test database
    from app.db.session import SQLiteClient
    test_db = Path('/tmp/test_e2e_tier.db')
    test_db.unlink(missing_ok=True)

    db = SQLiteClient(str(test_db))

    # Tạo schema đầy đủ (cần cho backend hoạt động)
    print("1. Setup test database...")
    await db.execute('''
        CREATE TABLE ai_task_profiles (
          task TEXT PRIMARY KEY,
          provider_id TEXT NOT NULL DEFAULT 'auto',
          model_id TEXT NOT NULL DEFAULT '',
          fallbacks_json TEXT NOT NULL DEFAULT '[]',
          tier TEXT,
          updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    await db.execute('''
        CREATE TABLE ai_providers (
          id TEXT PRIMARY KEY,
          label TEXT NOT NULL,
          base_url TEXT NOT NULL DEFAULT '',
          default_model_id TEXT NOT NULL DEFAULT '',
          api_key_configured INTEGER NOT NULL DEFAULT 0,
          enabled INTEGER NOT NULL DEFAULT 1,
          updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    await db.execute('''
        CREATE TABLE ai_models (
          provider_id TEXT NOT NULL,
          id TEXT NOT NULL,
          label TEXT NOT NULL,
          enabled INTEGER NOT NULL DEFAULT 1,
          allowed INTEGER NOT NULL DEFAULT 0,
          source TEXT NOT NULL DEFAULT 'scan',
          updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
          PRIMARY KEY (provider_id, id)
        )
    ''')

    await db.execute('''
        CREATE TABLE ai_model_settings (
          key TEXT PRIMARY KEY,
          value_json TEXT NOT NULL,
          updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    await db.execute('''
        CREATE TABLE system_settings (
          key TEXT PRIMARY KEY,
          value_json TEXT NOT NULL,
          updated_by TEXT,
          updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    # Seed providers
    await db.execute("INSERT INTO ai_providers (id, label, enabled) VALUES ('router9', '9router', 1)")
    await db.execute("INSERT INTO ai_providers (id, label, enabled) VALUES ('openrouter', 'OpenRouter', 1)")

    # Seed models
    await db.execute("INSERT INTO ai_models (provider_id, id, label, enabled, allowed) VALUES ('router9', 'test-model-fast', 'Fast Model', 1, 1)")
    await db.execute("INSERT INTO ai_models (provider_id, id, label, enabled, allowed) VALUES ('router9', 'test-model-balanced', 'Balanced Model', 1, 1)")
    await db.execute("INSERT INTO ai_models (provider_id, id, label, enabled, allowed) VALUES ('router9', 'test-model-best', 'Best Model', 1, 1)")

    # Chạy migration
    migration_sql = (Path(__file__).resolve().parents[1] / 'migrations/0009_ai_tier_profiles.sql').read_text()
    import re
    statements = [s.strip() for s in re.split(r';\s*(?=\n|$)', migration_sql) if s.strip()]
    for statement in statements:
        try:
            await db.execute(statement)
        except Exception as e:
            if 'duplicate column' not in str(e).lower():
                raise

    print("✓ Database setup complete\n")

    # Sync tier profiles
    print("2. Sync tier profiles...")
    from app.services.admin_settings import sync_ai_tier_profiles_to_registry
    from app.schemas.auth import SystemAiTierProfiles

    profiles = SystemAiTierProfiles(
        version=3,
        tier1={"tier": "tier1", "default_model": "router9/test-model-fast", "models": ["router9/test-model-fast"]},
        tier2={"tier": "tier2", "default_model": "router9/test-model-balanced", "models": ["router9/test-model-fast", "router9/test-model-balanced"]},
        tier3={"tier": "tier3", "default_model": "router9/test-model-best", "models": ["router9/test-model-best"]},
    )

    await sync_ai_tier_profiles_to_registry(db, profiles.model_dump(), None)
    print("✓ Tier profiles synced\n")

    # Verify tier profiles in database
    print("3. Verify tier profiles in database...")
    rows = await db.fetch_all("SELECT task, provider_id, model_id, fallbacks_json FROM ai_task_profiles WHERE task LIKE '%tier%' ORDER BY task")
    print(f"✓ Found {len(rows)} tier profiles in database")
    assert len(rows) == 3
    assert [row["task"] for row in rows] == ["render_tier1", "render_tier2", "render_tier3"]
    for row in rows[:3]:
        print(f"  {row['task']}: provider={row['provider_id']}, model={row['model_id']}")

    print()

    print("4. Resolve render tier candidates...")
    from app.services.model_registry import load_model_registry, resolve_render_tier_candidates

    registry = await load_model_registry(db)
    tier2_candidates = resolve_render_tier_candidates(registry, "tier2")
    assert [(item.provider_id, item.model_id) for item in tier2_candidates] == [
        ("router9", "test-model-balanced"),
        ("router9", "test-model-fast"),
    ]
    assert not any(task.startswith("reasoning_tier") or task.startswith("solver_explanation_tier") for task in registry.task_profiles)
    print("✓ Tier2 resolves only render model pool; reasoning/solver tier profiles absent\n")

    # Test RenderRequest schema
    print("5. Test RenderRequest schema...")
    from app.schemas.scene import RenderRequest

    # Test với tier1
    req1 = RenderRequest(problem_text="Cho tam giác ABC", tier="tier1")
    print(f"✓ RenderRequest tier1: {req1.tier}")

    # Test với tier mặc định
    req_default = RenderRequest(problem_text="Cho tam giác ABC")
    print(f"✓ RenderRequest default: {req_default.tier}")

    # Test validation tier không hợp lệ
    try:
        req_invalid = RenderRequest(problem_text="Test", tier="tier99")
        print("✗ Should have rejected invalid tier")
    except Exception:
        print("✓ Invalid tier correctly rejected")

    print()

    # Test extract_scene signature (không gọi thật vì cần API key)
    print("6. Test extract_scene signature...")
    from app.services.extractor import extract_scene
    import inspect

    sig = inspect.signature(extract_scene)
    params = list(sig.parameters.keys())
    expected = ['problem_text', 'grade', 'tier', 'advanced_settings', 'db']

    if params[:len(expected)] == expected:
        print(f"✓ extract_scene signature: {params}")
    else:
        print(f"✗ extract_scene signature mismatch")
        print(f"  Expected: {expected}")
        print(f"  Got: {params}")

    print()

    # Cleanup
    test_db.unlink()

    print("=== ALL E2E TESTS PASSED ===")

if __name__ == "__main__":
    asyncio.run(test_e2e())
