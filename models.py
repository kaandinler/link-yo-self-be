import datetime

from sqlalchemy import Column, Integer, String, UniqueConstraint, ForeignKey, DateTime, Boolean, func, JSON, Text
from sqlalchemy.orm import relationship, declarative_base, DeclarativeMeta

Base: DeclarativeMeta = declarative_base()


# Tüm modeller için ortak alanları sağlayan abstract base sınıfı
class BaseModel(Base):
    __abstract__ = True

    id = Column(Integer, primary_key=True, index=True)
    created_at = Column(DateTime(timezone=True), server_default=str(datetime.datetime.now(datetime.UTC)), nullable=False)
    updated_at = Column(DateTime(timezone=True), onupdate=str(datetime.datetime.now(datetime.UTC)), nullable=True)
    is_deleted = Column(Boolean, default=False, nullable=False)


class User(BaseModel):
    __tablename__ = 'users'

    # Temel kayıt bilgileri (zorunlu)
    username = Column(String(50), unique=True, nullable=False, index=True)
    email = Column(String(255), unique=True, nullable=False, index=True)
    hashed_password = Column(String(128), nullable=False)

    # Profil bilgileri (opsiyonel - sonradan eklenebilir)
    first_name = Column(String(50), nullable=True)
    last_name = Column(String(50), nullable=True)
    display_name = Column(String(100), nullable=True)  # Profil sayfasında görünecek isim
    bio = Column(Text, nullable=True)  # Kısa açıklama
    profile_image_url = Column(String(500), nullable=True)

    # Page/Link tree ayarları (opsiyonel)
    page_title = Column(String(100), nullable=True)  # Custom page title
    page_description = Column(String(500), nullable=True)  # SEO description
    website = Column(String(500), nullable=True)  # Ana web sitesi

    # Sosyal medya bağlantıları (opsiyonel)
    twitter_username = Column(String(100), nullable=True)
    instagram_username = Column(String(100), nullable=True)
    linkedin_username = Column(String(100), nullable=True)

    # Tema ayarları (default değerlerle)
    theme_color = Column(String(20), default="#1383eb", nullable=True)
    background_type = Column(String(20), default="color", nullable=True)  # color, gradient, image
    background_value = Column(String(500), default="#ffffff", nullable=True)

    # Profil completion tracking
    profile_completed = Column(Boolean, default=False, nullable=False)
    onboarding_completed = Column(Boolean, default=False, nullable=False)

    # İlişkiler
    social_accounts = relationship(
        'SocialAccount', back_populates='user', cascade='all, delete-orphan'
    )

    page_settings = relationship(
        'PageSettings', uselist=False, back_populates='user', cascade='all, delete-orphan'
    )

    links = relationship(
        'Link', back_populates='user', cascade='all, delete-orphan',
        order_by="Link.order_index"
    )

    @property
    def full_name(self) -> str:
        """Full name property"""
        if self.first_name and self.last_name:
            return f"{self.first_name} {self.last_name}"
        return self.first_name or self.last_name or self.username

    @property
    def profile_display_name(self) -> str:
        """Display name for profile page"""
        return self.display_name or self.full_name or self.username

    @property
    def profile_completion_percentage(self) -> int:
        """Calculate profile completion percentage"""
        total_fields = 8
        completed_fields = 0

        # Check required completion fields
        if self.display_name: completed_fields += 1
        if self.bio: completed_fields += 1
        if self.profile_image_url: completed_fields += 1
        if self.website: completed_fields += 1
        if self.twitter_username or self.instagram_username or self.linkedin_username: completed_fields += 1
        if self.page_title: completed_fields += 1
        if self.page_description: completed_fields += 1
        if len(self.links) > 0: completed_fields += 1  # En az bir link var mı

        return int((completed_fields / total_fields) * 100)


class Platform(BaseModel):
    __tablename__ = 'platforms'

    name = Column(String, unique=True, nullable=False, index=True)
    display_name = Column(String, nullable=True)

    social_accounts = relationship(
        'SocialAccount', back_populates='platform'
    )


class SocialAccount(BaseModel):
    __tablename__ = 'social_accounts'

    user_id = Column(
        Integer,
        ForeignKey('users.id', ondelete='CASCADE'),
        nullable=False
    )
    platform_id = Column(
        Integer,
        ForeignKey('platforms.id', ondelete='CASCADE'),
        nullable=False
    )
    username = Column(String, nullable=False)
    profile_url = Column(String, nullable=False)

    __table_args__ = (
        UniqueConstraint('user_id', 'platform_id', 'username', name='uq_user_platform_username'),
    )

    user = relationship('User', back_populates='social_accounts')
    platform = relationship('Platform', back_populates='social_accounts')


class PageSettings(BaseModel):
    __tablename__ = 'user_page_settings'

    user_id = Column(
        Integer,
        ForeignKey('users.id', ondelete='CASCADE'),
        nullable=False,
        unique=True,
    )
    background_color = Column(String(20), nullable=True)          # CSS hex veya isim
    background_image_url = Column(String, nullable=True)          # URL ile resim
    profile_image_url = Column(String, nullable=True)             # Kullanıcı profil fotoğrafı
    adult_warning_enabled = Column(Boolean, default=False, nullable=False)  # +18 uyarısı
    extra_settings = Column(JSON, nullable=True)                  # İleride ek ihtiyaçlar için JSON

    user = relationship('User', back_populates='page_settings')


class RefreshToken(BaseModel):
    __tablename__ = 'refresh_tokens'

    token = Column(Text, nullable=False, unique=True, index=True)
    user_id = Column(Integer, ForeignKey('users.id', ondelete='CASCADE'), nullable=False)
    expires_at = Column(DateTime(timezone=True), nullable=False)
    is_revoked = Column(Boolean, default=False, nullable=False)

    user = relationship('User')


# Link modeli - EKLENDI
class Link(BaseModel):
    __tablename__ = 'links'

    user_id = Column(
        Integer,
        ForeignKey('users.id', ondelete='CASCADE'),
        nullable=False
    )
    title = Column(String(255), nullable=False)
    url = Column(String(2048), nullable=False)  # URL'ler uzun olabilir
    description = Column(Text, nullable=True)
    icon_url = Column(String(500), nullable=True)  # Link ikonu URL'si
    background_color = Column(String(20), nullable=True)  # Hex renk kodu
    text_color = Column(String(20), nullable=True)  # Metin rengi
    border_radius = Column(Integer, default=8, nullable=False)  # Border radius px
    is_active = Column(Boolean, default=True, nullable=False)
    click_count = Column(Integer, default=0, nullable=False)  # Analytics için
    order_index = Column(Integer, default=0, nullable=False)  # Sıralama için

    # İlişkiler
    user = relationship('User', back_populates='links')