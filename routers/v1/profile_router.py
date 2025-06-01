# routers/v1/profile_router.py

from fastapi import APIRouter, Depends
from dependency_injector.wiring import inject, Provide

from core.schemas.response import SuccessResponse
from deps import get_current_user
from di.container import Container
from models import User
from services.user.user_service import UserService
from services.user.user_service_dto import (
    ProfileCompletionStep1,
    ProfileCompletionStep2,
    ProfileCompletionStep3,
    ProfileCompletionStep4,
    UserProfileUpdate,
    UserRead,
    OnboardingStatus
)

router = APIRouter(prefix="/profile", tags=["profile"])


@router.get("/me", response_model=SuccessResponse[UserRead])
async def get_my_profile(current_user: User = Depends(get_current_user)):
    """Get current user profile"""
    return SuccessResponse.create(
        data=current_user,
        message="Profile retrieved successfully"
    )


@router.get("/onboarding-status", response_model=SuccessResponse[OnboardingStatus])
async def get_onboarding_status(current_user: User = Depends(get_current_user)):
    """Get user's onboarding status"""

    # Determine completed steps
    completed_steps = []
    next_step = 1

    # Step 1: Basic info
    if current_user.display_name or current_user.bio or current_user.profile_image_url:
        completed_steps.append(1)
        next_step = 2

    # Step 2: Page settings
    if current_user.page_title or current_user.website:
        completed_steps.append(2)
        next_step = 3

    # Step 3: Social media
    if current_user.twitter_username or current_user.instagram_username or current_user.linkedin_username:
        completed_steps.append(3)
        next_step = 4

    # Step 4: Theme
    if current_user.theme_color != "#1383eb" or current_user.background_type != "color":
        completed_steps.append(4)
        next_step = 5  # Completed

    # Define step titles
    step_titles = {
        1: "Complete Your Profile",
        2: "Set Up Your Page",
        3: "Add Social Links",
        4: "Customize Appearance",
        5: "Add Your First Links"
    }

    status = OnboardingStatus(
        step=next_step,
        completed_steps=completed_steps,
        profile_completion_percentage=current_user.profile_completion_percentage,
        next_step_title=step_titles.get(next_step),
        can_skip=True
    )

    return SuccessResponse.create(
        data=status,
        message="Onboarding status retrieved"
    )


@router.post("/complete-step-1", response_model=SuccessResponse[UserRead])
@inject
async def complete_profile_step_1(
        profile_data: ProfileCompletionStep1,
        current_user: User = Depends(get_current_user),
        user_service: UserService = Depends(Provide[Container.user_service])
):
    """Complete profile step 1: Basic profile info"""

    # Update user with new data
    update_data = profile_data.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(current_user, key, value)

    updated_user = await user_service.update_user(current_user)

    return SuccessResponse.create(
        data=updated_user,
        message="Profile step 1 completed successfully"
    )


@router.post("/complete-step-2", response_model=SuccessResponse[UserRead])
@inject
async def complete_profile_step_2(
        profile_data: ProfileCompletionStep2,
        current_user: User = Depends(get_current_user),
        user_service: UserService = Depends(Provide[Container.user_service])
):
    """Complete profile step 2: Page settings"""

    update_data = profile_data.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(current_user, key, value)

    updated_user = await user_service.update_user(current_user)

    return SuccessResponse.create(
        data=updated_user,
        message="Profile step 2 completed successfully"
    )


@router.post("/complete-step-3", response_model=SuccessResponse[UserRead])
@inject
async def complete_profile_step_3(
        profile_data: ProfileCompletionStep3,
        current_user: User = Depends(get_current_user),
        user_service: UserService = Depends(Provide[Container.user_service])
):
    """Complete profile step 3: Social media links"""

    update_data = profile_data.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(current_user, key, value)

    updated_user = await user_service.update_user(current_user)

    return SuccessResponse.create(
        data=updated_user,
        message="Profile step 3 completed successfully"
    )


@router.post("/complete-step-4", response_model=SuccessResponse[UserRead])
@inject
async def complete_profile_step_4(
        profile_data: ProfileCompletionStep4,
        current_user: User = Depends(get_current_user),
        user_service: UserService = Depends(Provide[Container.user_service])
):
    """Complete profile step 4: Theme & appearance"""

    update_data = profile_data.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(current_user, key, value)

    updated_user = await user_service.update_user(current_user)

    return SuccessResponse.create(
        data=updated_user,
        message="Profile step 4 completed successfully"
    )


@router.post("/complete-onboarding", response_model=SuccessResponse[UserRead])
@inject
async def complete_onboarding(
        current_user: User = Depends(get_current_user),
        user_service: UserService = Depends(Provide[Container.user_service])
):
    """Mark onboarding as completed"""

    current_user.onboarding_completed = True
    current_user.profile_completed = True

    updated_user = await user_service.update_user(current_user)

    return SuccessResponse.create(
        data=updated_user,
        message="Onboarding completed successfully! Welcome to LinkYoSelf!"
    )


@router.put("/update", response_model=SuccessResponse[UserRead])
@inject
async def update_profile(
        profile_data: UserProfileUpdate,
        current_user: User = Depends(get_current_user),
        user_service: UserService = Depends(Provide[Container.user_service])
):
    """Update user profile (complete update)"""

    update_data = profile_data.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(current_user, key, value)

    updated_user = await user_service.update_user(current_user)

    return SuccessResponse.create(
        data=updated_user,
        message="Profile updated successfully"
    )


@router.post("/skip-onboarding", response_model=SuccessResponse[UserRead])
@inject
async def skip_onboarding(
        current_user: User = Depends(get_current_user),
        user_service: UserService = Depends(Provide[Container.user_service])
):
    """Skip onboarding process"""

    current_user.onboarding_completed = True
    # profile_completed stays False

    updated_user = await user_service.update_user(current_user)

    return SuccessResponse.create(
        data=updated_user,
        message="Onboarding skipped. You can complete your profile later!"
    )