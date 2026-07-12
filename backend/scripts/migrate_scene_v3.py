from __future__ import annotations

import argparse
import json
import shutil
import sqlite3
from pathlib import Path

from app.services.scene_v3_adapter import migrate_render_response_v2_dict, migrate_scene_v2_dict


def migrate_database(path: Path, *, write: bool) -> dict[str, int]:
    counts = {"render_jobs": 0, "scene_revisions": 0, "requires_confirmation": 0, "failed": 0}
    connection = sqlite3.connect(path)
    connection.row_factory = sqlite3.Row
    try:
        connection.execute("BEGIN")
        for row in connection.execute("SELECT id, scene_json, response_json FROM render_jobs WHERE COALESCE(schema_version, '2.0') != '3.0'"):
            try:
                scene, scene_report = migrate_scene_v2_dict(json.loads(row["scene_json"]))
                response_json = row["response_json"]
                migrated_response = None
                report = scene_report
                if response_json:
                    migrated_response, report = migrate_render_response_v2_dict(json.loads(response_json))
                connection.execute(
                    "UPDATE render_jobs SET scene_json = ?, response_json = ?, schema_version = '3.0', migration_report_json = ? WHERE id = ?",
                    [
                        scene.model_dump_json(),
                        json.dumps(migrated_response, ensure_ascii=False) if migrated_response is not None else None,
                        json.dumps(report.model_dump(), ensure_ascii=False),
                        row["id"],
                    ],
                )
                counts["render_jobs"] += 1
                counts["requires_confirmation"] += int(report.requires_confirmation)
            except Exception:
                counts["failed"] += 1

        for row in connection.execute("SELECT id, scene_json, response_json FROM scene_revisions WHERE COALESCE(schema_version, '2.0') != '3.0'"):
            try:
                scene, scene_report = migrate_scene_v2_dict(json.loads(row["scene_json"]))
                response_json = row["response_json"]
                migrated_response = None
                report = scene_report
                if response_json:
                    migrated_response, report = migrate_render_response_v2_dict(json.loads(response_json))
                connection.execute(
                    "UPDATE scene_revisions SET scene_json = ?, response_json = ?, schema_version = '3.0', migration_report_json = ? WHERE id = ?",
                    [
                        scene.model_dump_json(),
                        json.dumps(migrated_response, ensure_ascii=False) if migrated_response is not None else None,
                        json.dumps(report.model_dump(), ensure_ascii=False),
                        row["id"],
                    ],
                )
                counts["scene_revisions"] += 1
                counts["requires_confirmation"] += int(report.requires_confirmation)
            except Exception:
                counts["failed"] += 1

        if write:
            connection.commit()
        else:
            connection.rollback()
        return counts
    finally:
        connection.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="Chuyển scene/history SQLite từ MathScene v2 sang v3.")
    parser.add_argument("database", type=Path)
    parser.add_argument("--write", action="store_true", help="Ghi thay đổi; mặc định chỉ dry-run.")
    args = parser.parse_args()
    database = args.database.resolve()
    if not database.is_file():
        raise SystemExit(f"Không tìm thấy database: {database}")
    if args.write:
        backup = database.with_suffix(f"{database.suffix}.pre-scene-v3.bak")
        if backup.exists():
            raise SystemExit(f"Backup đã tồn tại, không ghi đè: {backup}")
        shutil.copy2(database, backup)
        print(f"Backup: {backup}")
    result = migrate_database(database, write=args.write)
    mode = "write" if args.write else "dry-run"
    print(json.dumps({"mode": mode, **result}, ensure_ascii=False, indent=2))
    if result["failed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()