import json

from app.db.models import DbRow, UserLearningProfileRecord
from app.db.session import DatabaseClient


class UserLearningProfileRepository:
    def __init__(self, db: DatabaseClient) -> None:
        self.db = db

    async def get(self, user_id: str) -> UserLearningProfileRecord | None:
        row = await self.db.fetch_one("SELECT * FROM user_learning_profiles WHERE user_id = ?", [user_id])
        return user_learning_profile_from_row(row) if row else None

    async def upsert(self, user_id: str, patch: dict) -> UserLearningProfileRecord:
        current = await self.get(user_id)
        data = {
            "preferred_name": current.preferred_name if current else None,
            "locale": current.locale if current else "vi-VN",
            "timezone": current.timezone if current else None,
            "education_level": current.education_level if current else None,
            "grade_level": current.grade_level if current else None,
            "math_level": current.math_level if current else None,
            "learning_goals_json": current.learning_goals_json if current else "[]",
            "subject_focus_json": current.subject_focus_json if current else "[]",
            "preferred_explanation_style": current.preferred_explanation_style if current else None,
            "accessibility_needs_json": current.accessibility_needs_json if current else "[]",
            "profile_json": current.profile_json if current else "{}",
            "onboarding_completed_at": current.onboarding_completed_at if current else None,
        }
        data.update(patch)
        await self.db.execute(
            """
            INSERT INTO user_learning_profiles (
              user_id, preferred_name, locale, timezone, education_level, grade_level, math_level,
              learning_goals_json, subject_focus_json, preferred_explanation_style, accessibility_needs_json,
              profile_json, onboarding_completed_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(user_id) DO UPDATE SET
              preferred_name = excluded.preferred_name,
              locale = excluded.locale,
              timezone = excluded.timezone,
              education_level = excluded.education_level,
              grade_level = excluded.grade_level,
              math_level = excluded.math_level,
              learning_goals_json = excluded.learning_goals_json,
              subject_focus_json = excluded.subject_focus_json,
              preferred_explanation_style = excluded.preferred_explanation_style,
              accessibility_needs_json = excluded.accessibility_needs_json,
              profile_json = excluded.profile_json,
              onboarding_completed_at = excluded.onboarding_completed_at,
              updated_at = CURRENT_TIMESTAMP
            """,
            [
                user_id,
                data["preferred_name"],
                data["locale"],
                data["timezone"],
                data["education_level"],
                data["grade_level"],
                data["math_level"],
                data["learning_goals_json"],
                data["subject_focus_json"],
                data["preferred_explanation_style"],
                data["accessibility_needs_json"],
                data["profile_json"],
                data["onboarding_completed_at"],
            ],
        )
        profile = await self.get(user_id)
        if profile is None:
            raise RuntimeError("Không thể lưu hồ sơ học tập.")
        return profile


def json_list(value: list[str]) -> str:
    return json.dumps([item.strip() for item in value if item.strip()], ensure_ascii=False)


def json_object(value: dict) -> str:
    return json.dumps(value, ensure_ascii=False)


def parse_json_list(value: str) -> list[str]:
    parsed = json.loads(value or "[]")
    return [str(item) for item in parsed] if isinstance(parsed, list) else []


def parse_json_object(value: str) -> dict:
    parsed = json.loads(value or "{}")
    return parsed if isinstance(parsed, dict) else {}


def user_learning_profile_from_row(row: DbRow) -> UserLearningProfileRecord:
    return UserLearningProfileRecord(
        user_id=str(row["user_id"]),
        preferred_name=str(row["preferred_name"]) if row.get("preferred_name") is not None else None,
        locale=str(row.get("locale") or "vi-VN"),
        timezone=str(row["timezone"]) if row.get("timezone") is not None else None,
        education_level=str(row["education_level"]) if row.get("education_level") is not None else None,
        grade_level=str(row["grade_level"]) if row.get("grade_level") is not None else None,
        math_level=str(row["math_level"]) if row.get("math_level") is not None else None,
        learning_goals_json=str(row.get("learning_goals_json") or "[]"),
        subject_focus_json=str(row.get("subject_focus_json") or "[]"),
        preferred_explanation_style=str(row["preferred_explanation_style"]) if row.get("preferred_explanation_style") is not None else None,
        accessibility_needs_json=str(row.get("accessibility_needs_json") or "[]"),
        profile_json=str(row.get("profile_json") or "{}"),
        onboarding_completed_at=str(row["onboarding_completed_at"]) if row.get("onboarding_completed_at") is not None else None,
        created_at=str(row["created_at"]),
        updated_at=str(row["updated_at"]),
    )