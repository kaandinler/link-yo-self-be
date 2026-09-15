import hashlib
import secrets
import uuid
from datetime import timedelta
from typing import Any

import jwt
from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from core.auth.password import hash_password, verify_password
from core.email.sender import EmailSender
from core.exceptions import (
    AlreadyExistsException,
    InvalidCredentialsException,
    InvalidResetTokenException,
    InvalidVerificationTokenException,
    PermissionDeniedException,
    UnauthorizedException,
)
from models import EmailVerificationToken, PasswordResetToken, RefreshToken, User
from repositories.auth.email_verification_repository import (
    EmailVerificationRepository,
)
from repositories.auth.password_reset_repository import PasswordResetRepository
from repositories.auth.refresh_token_repository import RefreshTokenRepository
from repositories.user.user_repository import UserRepository
from services.user.user_service import UserService
from services.user.user_service_dto import UserCreate
from utils.time_utils import utcnow


class AuthService:

    def __init__(
            self,
            user_service: UserService,
            user_repository: UserRepository,
            refresh_token_repository: RefreshTokenRepository,
            password_reset_repository: PasswordResetRepository,
            email_verification_repository: EmailVerificationRepository,
            email_sender: EmailSender,
            secret_key: str,
            algorithm: str,
            expire_minutes: int,
            frontend_url: str,
            reset_expire_minutes: int = 60,
            verification_expire_minutes: int = 60 * 24,
            refresh_expire_days: int = 7,
            db_session: AsyncSession = None,
    ):
        self.user_service = user_service
        self.user_repository = user_repository
        self.refresh_token_repository = refresh_token_repository
        self.password_reset_repository = password_reset_repository
        self.email_verification_repository = email_verification_repository
        self.email_sender = email_sender
        self.frontend_url = frontend_url
        self.reset_expire_minutes = reset_expire_minutes
        self.verification_expire_minutes = verification_expire_minutes
        self.secret_key = secret_key
        self.algorithm = algorithm
        self.expire_minutes = expire_minutes
        self.refresh_expire_days = refresh_expire_days
        self.db_session = db_session

    def verify_password(self, plain_password: str, hashed_password: str) -> bool:
        return verify_password(plain_password, hashed_password)

    def hash_password(self, password: str) -> str:
        return hash_password(password)

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
        created = await self.user_service.create_user(new_user)

        # Adres sahipligi dogrulanana kadar email_verified False kaliyor.
        # Giris engellenmiyor: dogrulama, sifre sifirlamanin calisir kalmasi
        # icin; kullaniciyi kapida bekletmek ayri bir urun karari olurdu.
        await self.send_verification_email(created)
        return created

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

    @staticmethod
    def _hash_token(token: str) -> str:
        """E-postayla gonderilen token'in veritabaninda saklanacak ozeti.

        Ham token yalnizca e-postadaki baglantida bulunuyor; veritabaninda
        ozeti duruyor ki DB'yi okuyabilen biri (log, yedek, sizinti) sifre
        sifirlayamasin ya da baskasinin adresini dogrulayamasin.
        """
        return hashlib.sha256(token.encode()).hexdigest()

    async def request_password_reset(self, email: str) -> None:
        """Sifre sifirlama baglantisi gonderir.

        DIKKAT: Kullanici bulunamasa bile sessizce doner ve cagiran uc ayni
        yaniti verir. Aksi halde bu uc, bir e-postanin sistemde kayitli olup
        olmadigini ogrenmek icin kullanilabilirdi (kullanici numaralandirma).
        """
        user = await self.user_service.get_by_email(email)
        if not user:
            return

        # Onceki talepler gecersiz kilinliyor: ayni anda birden fazla gecerli
        # baglanti dolasmasin.
        await self.password_reset_repository.invalidate_user_tokens(user.id)

        raw_token = secrets.token_urlsafe(32)
        reset_token = PasswordResetToken(
            token_hash=self._hash_token(raw_token),
            user_id=user.id,
            expires_at=utcnow() + timedelta(minutes=self.reset_expire_minutes),
        )
        await self.password_reset_repository.create_token(reset_token)

        link = f"{self.frontend_url.rstrip('/')}/password-change?token={raw_token}"
        self.email_sender.send(
            to=str(user.email),
            subject="Reset your LinkYoSelf password",
            body=(
                f"Hi {user.username},\n\n"
                "We received a request to reset your LinkYoSelf password.\n"
                f"Use the link below within {self.reset_expire_minutes} minutes:\n\n"
                f"{link}\n\n"
                "If you did not request this, you can ignore this email; "
                "your password will stay the same.\n"
            ),
        )

    async def reset_password(self, token: str, new_password: str) -> None:
        """Token ile sifreyi degistirir ve acik oturumlari kapatir."""
        record = await self.password_reset_repository.get_valid_by_hash(
            self._hash_token(token)
        )
        if not record:
            raise InvalidResetTokenException

        user = await self.user_repository.get_by_id(record.user_id)
        if not user:
            raise InvalidResetTokenException

        user.hashed_password = self.hash_password(new_password)
        await self.user_repository.update(user)

        # Token tek kullanimlik; ayrica sifre degistigi icin mevcut refresh
        # token'lar da gecersiz kilinliyor (baska cihazlardaki oturumlar).
        await self.password_reset_repository.mark_used(record.token_hash)
        await self.refresh_token_repository.revoke_all_user_tokens(user.id)

    async def change_password(
        self, user: User, current_password: str, new_password: str
    ) -> tuple[str, str]:
        """Kullanicinin kendi sifresini degistirir.

        Mevcut sifre dogrulanmadan degisiklik yapilmaz: acik birakilmis bir
        oturum tek basina sifreyi degistirip hesabi ele gecirememeli.

        Sifre degistiginde tum refresh token'lar iptal ediliyor (diger
        cihazlardaki oturumlar kapansin), ardindan istegi yapan kullaniciya
        yeni bir cift uretiliyor; boylece bu oturum devam edebiliyor.
        """
        if not verify_password(current_password, user.hashed_password):
            raise PermissionDeniedException(detail="Current password is incorrect")

        user.hashed_password = hash_password(new_password)
        await self.user_repository.update(user)

        await self.refresh_token_repository.revoke_all_user_tokens(user.id)
        return await self.create_tokens(user)

    async def request_email_change(
        self, user: User, password: str, new_email: str
    ) -> str:
        """Adres degisikligi talebi: yeni adrese dogrulama baglantisi gonderir.

        DIKKAT: Adres BURADA degismiyor. Onceki hali dogrudan yaziyordu ve
        yanlis yazilan bir adres kullaniciyi sifre sifirlamadan -- yani tek
        kurtarma yolundan -- ediyordu. Degisiklik ancak kullanici yeni adrese
        gelen baglantiya tikladiginda uygulaniyor (bkz. verify_email).

        Talep edilen adresi doner; arayuz "su adrese baglanti gonderildi"
        diyebilsin.
        """
        if not verify_password(password, user.hashed_password):
            raise PermissionDeniedException(detail="Password is incorrect")

        new_email = new_email.lower()
        await self._ensure_email_available(new_email, user)

        await self.send_verification_email(user, new_email)
        return new_email

    async def _ensure_email_available(self, email: str, user: User) -> None:
        """Adres baskasinda mi? Kendi adresi catisma sayilmaz."""
        if email == user.email:
            return

        # include_deleted: silinen kayit tabloda kaliyor ve email UNIQUE;
        # gormezden gelirsek UPDATE unique ihlaliyle 500 olurdu.
        mevcut = await self.user_repository.get_by_email(email, include_deleted=True)
        if mevcut:
            raise AlreadyExistsException(detail=f"This email already exists: {email}")

    async def send_verification_email(
        self, user: User, email: str | None = None
    ) -> None:
        """Dogrulama baglantisi uretir ve gonderir.

        email verilmezse kullanicinin mevcut adresi dogrulanir (kayit ve
        "yeniden gonder"); verilirse henuz uygulanmamis yeni adres
        dogrulanir ve baglantiya tiklanmasi adresi degistirir.
        """
        hedef = (email or user.email).lower()

        # Onceki talepler gecersiz kilinliyor: ayni anda birden fazla gecerli
        # baglanti dolasmasin. Adres degistirmede kritik -- vazgecilen bir
        # adrese ait eski baglanti sonradan gecis yapabilirdi.
        await self.email_verification_repository.invalidate_user_tokens(user.id)

        raw_token = secrets.token_urlsafe(32)
        await self.email_verification_repository.create_token(
            EmailVerificationToken(
                token_hash=self._hash_token(raw_token),
                user_id=user.id,
                email=hedef,
                expires_at=utcnow()
                + timedelta(minutes=self.verification_expire_minutes),
            )
        )

        link = f"{self.frontend_url.rstrip('/')}/confirm-email?token={raw_token}"
        saat = max(1, self.verification_expire_minutes // 60)
        self.email_sender.send(
            to=hedef,
            subject="Confirm your LinkYoSelf email address",
            body=(
                f"Hi {user.username},\n\n"
                "Please confirm this email address for your LinkYoSelf account.\n"
                f"Use the link below within {saat} hours:\n\n"
                f"{link}\n\n"
                "If you did not request this, you can ignore this email.\n"
            ),
        )

    async def verify_email(self, token: str) -> User:
        """Dogrulama baglantisini isler.

        Token bir adres degisikligine aitse adres burada uygulaniyor;
        benzersizlik yeniden kontrol ediliyor, cunku talep ile onay arasinda
        adresi baskasi almis olabilir.
        """
        record = await self.email_verification_repository.get_valid_by_hash(
            self._hash_token(token)
        )
        if not record:
            raise InvalidVerificationTokenException

        user = await self.user_repository.get_by_id(record.user_id)
        if not user or user.is_deleted:
            raise InvalidVerificationTokenException

        if record.email != user.email:
            await self._ensure_email_available(record.email, user)
            user.email = record.email

        user.email_verified = True
        user = await self.user_repository.update(user)

        await self.email_verification_repository.mark_used(record.token_hash)
        return user

    async def resend_verification_email(self, user: User) -> str:
        """Bekleyen dogrulamayi yeniden gonderir.

        Onay bekleyen bir adres degisikligi varsa baglanti yine o adrese
        gider; yoksa kullanicinin mevcut adresine.
        """
        bekleyen = await self.email_verification_repository.get_pending_email(user.id)
        hedef = bekleyen or user.email

        await self.send_verification_email(user, hedef)
        return hedef

    async def revoke_all_user_tokens(self, user_id: int) -> None:
        """Kullanıcının tüm refresh token'larını geçersiz kılar (şifre değişikliği, vb.)"""
        await self.refresh_token_repository.revoke_all_user_tokens(user_id)

