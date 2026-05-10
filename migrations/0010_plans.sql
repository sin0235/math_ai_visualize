CREATE TABLE IF NOT EXISTS plans (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    daily_render_limit INTEGER CHECK(daily_render_limit IS NULL OR daily_render_limit >= 0),
    daily_ocr_limit INTEGER CHECK(daily_ocr_limit IS NULL OR daily_ocr_limit >= 0),
    sort_order INTEGER NOT NULL DEFAULT 0,
    is_active INTEGER NOT NULL DEFAULT 1 CHECK(is_active IN (0, 1)),
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

INSERT INTO plans (id, name, daily_render_limit, daily_ocr_limit, sort_order, is_active)
VALUES
    ('free', 'Free', 20, 20, 10, 1),
    ('pro', 'Pro', 200, 200, 20, 1),
    ('pro_plus', 'Pro+', NULL, NULL, 30, 1)
ON CONFLICT(id) DO UPDATE SET
    name = excluded.name,
    sort_order = excluded.sort_order,
    is_active = excluded.is_active;

CREATE INDEX IF NOT EXISTS idx_plans_active_sort ON plans(is_active, sort_order);
