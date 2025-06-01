from core.base_service import BaseService
from models import User
from repositories.user.user_repository import UserRepository


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

    async def check_username_availability(self, username: str) -> bool:
        """Check if username is available"""
        user = await self.repository.get_by_username(username)
        return user is None

    async def check_email_availability(self, email: str) -> bool:
        """Check if email is available"""
        user = await self.repository.get_by_email(email)
        return user is None
