from fastapi import APIRouter, Depends

from app.api.deps import get_current_user, require_trusted_origin
from app.db.models import UserRecord
from app.db.session import DatabaseClient, get_database
from app.repositories.user_profile import UserLearningProfileRepository, json_list, json_object, parse_json_list, parse_json_object
from app.schemas.auth import UserLearningProfileResponse, UserLearningProfileUpdateRequest

router = APIRouter(prefix="/api/user/profile", tags=["user-profile"])


@router.get("", response_model=UserLearningProfileResponse)
async def get_learning_profile(
    user: UserRecord = Depends(get_current_user),
    db: DatabaseClient = Depends(get_database),
) -> UserLearningProfileResponse:
    profile = await UserLearningProfileRepository(db).get(user.id)
    if profile is None:
        return UserLearningProfileResponse()
    return profile_response(profile)


@router.patch("", response_model=UserLearningProfileResponse, dependencies=[Depends(require_trusted_origin)])
async def patch_learning_profile(
    request: UserLearningProfileUpdateRequest,
    user: UserRecord = Depends(get_current_user),
    db: DatabaseClient = Depends(get_database),
) -> UserLearningProfileResponse:
    payload = request.model_dump(exclude_unset=True)
    patch = dict(payload)
    if "learning_goals" in payload:
        patch["learning_goals_json"] = json_list(payload.pop("learning_goals") or [])
    if "subject_focus" in payload:
        patch["subject_focus_json"] = json_list(payload.pop("subject_focus") or [])
    if "accessibility_needs" in payload:
        patch["accessibility_needs_json"] = json_list(payload.pop("accessibility_needs") or [])
    if "profile" in payload:
        patch["profile_json"] = json_object(payload.pop("profile") or {})
    for legacy_key in ("learning_goals", "subject_focus", "accessibility_needs", "profile"):
        patch.pop(legacy_key, None)
    profile = await UserLearningProfileRepository(db).upsert(user.id, patch)
    return profile_response(profile)


def profile_response(profile) -> UserLearningProfileResponse:
    return UserLearningProfileResponse(
        preferred_name=profile.preferred_name,
        locale=profile.locale,
        timezone=profile.timezone,
        education_level=profile.education_level,
        grade_level=profile.grade_level,
        math_level=profile.math_level,
        learning_goals=parse_json_list(profile.learning_goals_json),
        subject_focus=parse_json_list(profile.subject_focus_json),
        preferred_explanation_style=profile.preferred_explanation_style,
        accessibility_needs=parse_json_list(profile.accessibility_needs_json),
        profile=parse_json_object(profile.profile_json),
        onboarding_completed_at=profile.onboarding_completed_at,
        created_at=profile.created_at,
        updated_at=profile.updated_at,
    )