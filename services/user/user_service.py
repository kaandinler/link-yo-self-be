from core.base_service import BaseService
from core.exceptions import NotFoundException
from models import User
from repositories.user.user_repository import UserRepository
from services.public.public_profile_dto import PublicLink, PublicProfile


class UserService(BaseService):
    def __init__(self, user_repo: UserRepository):
        super().__init__(user_repo)
        self.repository = user_repo

    async def list_users(self):
        return await self.list(User)

    async def get_user(self, user_id: int):
        return await self.repository.get_by_id(user_id)

    async def get_by_username(self, username: str):
        return await self.repository.get_by_username(username)

    async def get_by_email(self, email: str):
        return await self.repository.get_by_email(email)

    async def create_user(self, user: User):
        return await self.repository.create_user(user)

    async def update_user(self, user: User):
        """Update user information"""
        return await self.repository.update(user)

    async def get_public_profile(self, username: str) -> PublicProfile:
        """Kullanicinin herkese acik link sayfasini olusturur.

        Sadece aktif ve silinmemis linkler, order_index sirasiyla doner.
        """
        user = await self.repository.get_public_profile(username.lower())
        if not user:
            raise NotFoundException(f"Profile not found: {username}")

        visible_links = sorted(
            (link for link in user.links if link.is_active and not link.is_deleted),
            key=lambda link: link.order_index,
        )

        return PublicProfile(
            username=user.username,
            display_name=user.profile_display_name,
            bio=user.bio,
            profile_image_url=user.profile_image_url,
            page_title=user.page_title,
            page_description=user.page_description,
            website=user.website,
            twitter_username=user.twitter_username,
            instagram_username=user.instagram_username,
            linkedin_username=user.linkedin_username,
            theme_color=user.theme_color,
            background_type=user.background_type,
            background_value=user.background_value,
            links=[PublicLink.model_validate(link) for link in visible_links],
        )

    async def check_username_availability(self, username: str) -> bool:
        """Check if username is available"""
        user = await self.repository.get_by_username(username)
        return user is None

    async def check_email_availability(self, email: str) -> bool:
        """Check if email is available"""
        user = await self.repository.get_by_email(email)
        return user is None
