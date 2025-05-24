from datetime import datetime, timedelta
from typing import Optional, Dict, Any

import jwt
from fastapi import HTTPException, status
from passlib.context import CryptContext

from core.exceptions import InvalidCredentialsException
from models import User
from repositories.user.user_repository import UserRepository
from services.user.user_service import UserService
from services.user.user_service_dto import UserCreate


class AuthService:
    pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

    def __init__(
            self,
            user_service: UserService,
            user_repository: UserRepository,
            secret_key: str,
            algorithm: str,
            expire_minutes: int,
    ):
        self.user_service = user_service
        self.user_repository = user_repository
        self.secret_key = secret_key
        self.algorithm = algorithm
        self.expire_minutes = expire_minutes

    def verify_password(self, plain_password: str, hashed_password: str) -> bool:
        return self.pwd_context.verify(plain_password, hashed_password)

    def hash_password(self, password: str) -> str:
        return self.pwd_context.hash(password)

    async def authenticate_user(self, email: str, password: str) -> Optional[User]:
        """Authenticate a user by username and password"""
        user = await self.user_service.get_by_email(email)
        if not user or not self.verify_password(password, user.hashed_password):
            raise InvalidCredentialsException
        return user

    def create_access_token(self, data: Dict[str, Any]) -> str:
        """Create a JWT access token with expiration time"""
        to_encode = data.copy()
        expire = datetime.utcnow() + timedelta(minutes=self.expire_minutes)
        to_encode.update({"exp": expire})

        # Ensure we have a subject claim
        if "sub" not in to_encode:
            raise ValueError("Token data must contain 'sub' field")

        return jwt.encode(to_encode, self.secret_key, algorithm=self.algorithm)

    async def verify_token(self, token: str) -> Dict[str, Any]:
        """Verify and decode a JWT token"""
        try:
            payload = jwt.decode(
                token,
                self.secret_key,
                algorithms=[self.algorithm]
            )
            return payload
        except jwt.PyJWTError:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid authentication credentials",
                headers={"WWW-Authenticate": "Bearer"},
            )

    async def register_user(self, user_in = UserCreate) -> User:
        """Register a new user with hashed password"""
        # Check if user exists
        existing_user = await self.user_service.get_by_email(str(user_in.email))
        if existing_user:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Username already registered"
            )

        # Create user with hashed password
        hashed_password = self.hash_password(user_in.password)

        # Create a User object instead of passing individual parameters
        new_user = User(
            username=user_in.username,
            email=str(user_in.email),
            hashed_password=hashed_password
        )

        # Pass the User object to create_user
        return await self.user_service.create_user(new_user)