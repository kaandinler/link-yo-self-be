from sqlalchemy import Column, Integer, String, UniqueConstraint, ForeignKey, DateTime, Boolean, func, JSON
from sqlalchemy.orm import relationship, declarative_base, DeclarativeMeta

Base: DeclarativeMeta = declarative_base()


# Tüm modeller için ortak alanları sağlayan abstract base sınıfı
class BaseModel(Base):
    __abstract__ = True

    id = Column(Integer, primary_key=True, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=True)
    is_deleted = Column(Boolean, default=False, nullable=False)


class User(BaseModel):
    __tablename__ = 'users'

    username = Column(String(50), unique=True, nullable=False, index=True)
    email = Column(String(255), unique=True, nullable=False, index=True)
    profile_image_url = Column(String, nullable=True)  # Kullanıcı profil fotoğrafı
    hashed_password = Column(String(128), nullable=False)

    social_accounts = relationship(
        'SocialAccount', back_populates='user', cascade='all, delete-orphan'
    )

    # Her kullanıcı için tekil sayfa ayarları
    page_settings = relationship(
        'PageSettings', uselist=False, back_populates='user', cascade='all, delete-orphan'
    )

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
