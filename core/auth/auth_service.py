import uuid
from datetime import timedelta
from typing import Any

import jwt
from fastapi import HTTPException, status
from passlib.context import CryptContext
from sqlalchemy.ext.asyncio import AsyncSession

from core.exceptions import InvalidCredentialsException, UnauthorizedException
from models import RefreshToken, User
from repositories.auth.refresh_token_repository import RefreshTokenRepository
from repositories.user.user_repository import UserRepository
from services.user.user_service import UserService
from services.user.user_service_dto import UserCreate
from utils.time_utils import utcnow


class AuthService:
    pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

    def __init__(
            self,
            user_service: UserService,
            user_repository: UserRepository,
            refresh_token_repository: RefreshTokenRepository,
            secret_key: str,
            algorithm: str,
            expire_minutes: int,
            refresh_expire_days: int = 7,
            db_session: AsyncSession = None,
    ):
        self.user_service = user_service
        self.user_repository = user_repository
        self.refresh_token_repository = refresh_token_repository
        self.secret_key = secret_key
        self.algorithm = algorithm
        self.expire_minutes = expire_minutes
        self.refresh_expire_days = refresh_expire_days
        self.db_session = db_session

    def verify_password(self, plain_password: str, hashed_password: str) -> bool:
        return self.pwd_context.verify(plain_password, hashed_password)

    def hash_password(self, password: str) -> str:
        return self.pwd_context.hash(password)

    async def authenticate_user(self, identifier: str, password: str) -> User | None:
        """Kullaniciyi e-posta VEYA kullanici adi ile dogrular.

        OAuth2PasswordRequestForm alani `username` olarak geldigi icin kullanici
        her ikisini de girebilmeli; once e-posta, bulunamazsa kullanici adi
        uzerinden aranir.
        """
        user = await self.user_service.get_by_email(identifier)
        if not user:
            user = await self.user_service.get_by_username(identifier.lower())
        if not user or not self.verify_password(password, user.hashed_password):
            raise InvalidCredentialsException
        return user

    def create_access_token(self, data: dict[str, Any]) -> str:
        """Create a JWT access token with expiration time"""
        to_encode = data.copy()
        expire = utcnow() + timedelta(minutes=self.expire_minutes)
        to_encode.update({"exp": expire})

        # Ensure we have a subject claim
        if "sub" not in to_encode:
            raise ValueError("Token data must contain 'sub' field")

        return jwt.encode(to_encode, self.secret_key, algorithm=self.algorithm)

    async def verify_token(self, token: str) -> dict[str, Any]:
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

    async def create_tokens(self, user: User) -> tuple[str, str]:
        """Kullanıcı için access token ve refresh token oluşturur"""
        # Access token oluştur
        access_token = self.create_access_token({"sub": user.username})

        # Refresh token oluştur
        refresh_token_value = str(uuid.uuid4())
        expires_at = utcnow() + timedelta(days=self.refresh_expire_days)

        # Refresh token veritabanına kaydet
        refresh_token = RefreshToken(
            token=refresh_token_value,
            user_id=user.id,
            expires_at=expires_at,
            is_revoked=False
        )

        await self.refresh_token_repository.create_token(refresh_token)

        return access_token, refresh_token_value

    async def refresh_access_token(self, refresh_token_value: str) -> str:
        """Refresh token kullanarak yeni bir access token oluşturur"""
        # Refresh token'ı veritabanında bul
        refresh_token = await self.refresh_token_repository.get_valid_token(refresh_token_value)

        if not refresh_token:
            raise UnauthorizedException(detail="Invalid or expired refresh token")

        # Kullanıcıyı bul
        user = await self.user_repository.get_by_id(refresh_token.user_id)
        if not user:
            raise UnauthorizedException(detail="User not found")

        # Yeni access token oluştur
        access_token = self.create_access_token({"sub": user.username})

        return access_token

    async def revoke_refresh_token(self, refresh_token_value: str) -> None:
        """Refresh token'ı geçersiz kılar (logout işlemi için)"""
        await self.refresh_token_repository.revoke_token(refresh_token_value)

    async def revoke_all_user_tokens(self, user_id: int) -> None:
        """Kullanıcının tüm refresh token'larını geçersiz kılar (şifre değişikliği, vb.)"""
        await self.refresh_token_repository.revoke_all_user_tokens(user_id)

