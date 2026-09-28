from sqlalchemy import (
    JSON,
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import DeclarativeMeta, declarative_base, relationship

Base: DeclarativeMeta = declarative_base()


# Tüm modeller için ortak alanları sağlayan abstract base sınıfı
class BaseModel(Base):
    __abstract__ = True

    id = Column(Integer, primary_key=True, index=True)
    created_at = Column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=True,
    )
    is_deleted = Column(Boolean, default=False, nullable=False)


class User(BaseModel):
    __tablename__ = "users"

    # Temel kayıt bilgileri (zorunlu)
    username = Column(String(50), unique=True, nullable=False, index=True)
    email = Column(String(255), unique=True, nullable=False, index=True)
    hashed_password = Column(String(128), nullable=False)

    # Profil bilgileri (opsiyonel - sonradan eklenebilir)
    first_name = Column(String(50), nullable=True)
    last_name = Column(String(50), nullable=True)
    display_name = Column(
        String(100), nullable=True
    )  # Profil sayfasında görünecek isim
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
    background_type = Column(
        String(20), default="color", nullable=True
    )  # color, gradient, image
    background_value = Column(String(500), default="#ffffff", nullable=True)

    # Profil completion tracking
    profile_completed = Column(Boolean, default=False, nullable=False)
    onboarding_completed = Column(Boolean, default=False, nullable=False)

    # Yetkilendirme
    is_admin = Column(Boolean, default=False, nullable=False)

    # Analytics: public profil sayfasi her goruntulendiginde artar.
    profile_view_count = Column(Integer, default=0, nullable=False)

    # E-posta adresinin sahipligi dogrulandi mi? Sifre sifirlama baglantisi
    # bu adrese gittigi icin, dogrulanmamis adres kurtarma yolunu calismaz
    # hale getirir.
    email_verified = Column(Boolean, default=False, nullable=False)

    # İlişkiler
    social_accounts = relationship(
        "SocialAccount", back_populates="user", cascade="all, delete-orphan"
    )

    page_settings = relationship(
        "PageSettings",
        uselist=False,
        back_populates="user",
        cascade="all, delete-orphan",
    )

    links = relationship(
        "Link",
        back_populates="user",
        cascade="all, delete-orphan",
        order_by="Link.order_index",
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
        # Sayilan alanlar; toplam total_fields ile ayni olmali.
        doldurulmus = [
            self.display_name,
            self.bio,
            self.profile_image_url,
            self.website,
            self.twitter_username or self.instagram_username or self.linkedin_username,
            self.page_title,
            self.page_description,
            len(self.links) > 0,
        ]
        completed_fields = sum(1 for alan in doldurulmus if alan)

        return int((completed_fields / total_fields) * 100)


class Platform(BaseModel):
    __tablename__ = "platforms"

    name = Column(String, unique=True, nullable=False, index=True)
    display_name = Column(String, nullable=True)

    social_accounts = relationship("SocialAccount", back_populates="platform")


class SocialAccount(BaseModel):
    __tablename__ = "social_accounts"

    user_id = Column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    platform_id = Column(
        Integer, ForeignKey("platforms.id", ondelete="CASCADE"), nullable=False
    )
    username = Column(String, nullable=False)
    profile_url = Column(String, nullable=False)

    __table_args__ = (
        UniqueConstraint(
            "user_id", "platform_id", "username", name="uq_user_platform_username"
        ),
    )

    user = relationship("User", back_populates="social_accounts")
    platform = relationship("Platform", back_populates="social_accounts")


class PageSettings(BaseModel):
    """Kullanicinin sayfa ayarlarindan users'ta karsiligi OLMAYANLAR.

    NEDEN BU KADAR DAR: tablo basta background_color, background_image_url
    ve profile_image_url kolonlarini da tasiyordu; ucu de users'takilerle
    ayni seyi anlatiyordu (background_type + background_value ikilisi
    ustelik 'gradient'i de ifade edebiliyor, bu iki kolon edemiyordu).
    Ikisini birden acik birakmak ayni gorunumu iki yerden okunabilir
    yapardi. Kolonlar b8c9d0e1f2a3 migration'inda dusuruldu; tablo hic
    yazilmamisti, veri kaybi olmadi.

    Gorunumle ilgili her sey users'ta: theme_color, background_type,
    background_value, profile_image_url. Burasi yalnizca onlarin
    kapsamadigi iki ayar icin.
    """

    __tablename__ = "user_page_settings"

    user_id = Column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )
    # Herkese acik sayfada +18 ara ekrani gosterilsin mi?
    adult_warning_enabled = Column(Boolean, default=False, nullable=False)
    # Semasi olmayan, sahibine ozel ek ayarlar. Herkese acik profile
    # DAHIL EDILMIYOR: icerigini istemci belirliyor, yani sema disi bir
    # alani kazara yayinlamak mumkun olurdu.
    extra_settings = Column(JSON, nullable=True)

    user = relationship("User", back_populates="page_settings")


class RefreshToken(BaseModel):
    __tablename__ = "refresh_tokens"

    token = Column(Text, nullable=False, unique=True, index=True)
    user_id = Column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    expires_at = Column(DateTime(timezone=True), nullable=False)
    is_revoked = Column(Boolean, default=False, nullable=False)

    user = relationship("User")


class PasswordResetToken(BaseModel):
    """Sifre sifirlama baglantisindaki tek kullanimlik token.

    Token'in kendisi degil, SHA-256 ozeti saklaniyor: veritabanini okuyabilen
    biri (log, yedek, sizinti) ele gecirdigi kayitla sifre sifirlayamamali.
    """

    __tablename__ = "password_reset_tokens"

    token_hash = Column(String(64), nullable=False, unique=True, index=True)
    user_id = Column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    expires_at = Column(DateTime(timezone=True), nullable=False)
    used_at = Column(DateTime(timezone=True), nullable=True)

    user = relationship("User")


class EmailVerificationToken(BaseModel):
    """E-posta adresi dogrulama baglantisindaki tek kullanimlik token.

    PasswordResetToken gibi ham token degil SHA-256 ozeti saklaniyor:
    veritabanini okuyabilen biri (log, yedek, sizinti) baskasinin adresini
    dogrulayamamali.

    `email` kolonu dogrulanmakta olan adresi tutuyor. Kayit sirasinda bu
    kullanicinin mevcut adresi; adres degistirmede ise HENUZ uygulanmamis
    yeni adres -- degisiklik ancak kullanici yeni adrese gelen baglantiya
    tikladiginda gerceklesiyor.
    """

    __tablename__ = "email_verification_tokens"

    token_hash = Column(String(64), nullable=False, unique=True, index=True)
    user_id = Column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    email = Column(String(255), nullable=False)
    expires_at = Column(DateTime(timezone=True), nullable=False)
    used_at = Column(DateTime(timezone=True), nullable=True)

    user = relationship("User")


# Link modeli - EKLENDI
class Link(BaseModel):
    __tablename__ = "links"

    user_id = Column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
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
    user = relationship("User", back_populates="links")


# Olay turleri. Sayaclar (Link.click_count, User.profile_view_count) toplami
# tutmaya devam ediyor; buradaki satirlar "ne zaman" sorusunu cevapliyor.
EVENT_LINK_CLICK = "link_click"
EVENT_PROFILE_VIEW = "profile_view"


class AnalyticsEvent(BaseModel):
    """Tek bir tiklama ya da profil goruntulemesi.

    NEDEN AYRI TABLO: link ve kullanici uzerindeki sayaclar yalnizca toplami
    biliyor. "Son 7 gun" gibi bir grafik, olayin ne zaman gerceklestigini
    gerektiriyor ve sayactan geriye dogru uretilemez.

    Sayaclar kaldirilmadi: ozet uclari onlari tek satirdan okuyor ve bu
    migration'dan onceki gecmisi yalnizca onlar biliyor.
    """

    __tablename__ = "analytics_events"

    user_id = Column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    event_type = Column(String(30), nullable=False)

    # Link silinince olay kalmali: gecmis bir gunun toplami, bugun yapilan bir
    # silme yuzunden degismemeli. Bu yuzden CASCADE degil SET NULL.
    link_id = Column(
        Integer,
        ForeignKey("links.id", ondelete="SET NULL"),
        nullable=True,
    )

    # Ziyaretcinin bu sayfaya hangi siteden geldigi; yalnizca host, orn.
    # "instagram.com". NULL = dis bir kaynak yok (adres cubuguna yazilmis,
    # referrer gondermeyen bir uygulamadan gelinmis ya da site ici gezinme).
    #
    # NEDEN TAM URL DEGIL: referrer'in yol ve sorgu kismi cogu zaman kampanya
    # ve oturum belirteci tasiyor; bunlari saklamanin bize bir faydasi yok ama
    # sizdirma yuzeyi yaratiyor. Host, "trafigim nereden geliyor" sorusunun
    # tamamini cevapliyor. Bedeli: "Instagram'da hangi gonderi" gibi bir
    # kirilim sonradan gecmise donuk uretilemez.
    referrer = Column(String(255), nullable=True)

    # Zaman serisi sorgusu her zaman "bir kullanicinin su tarihten sonraki
    # olaylari" seklinde; bilesik indeks tam bu erisim icin.
    __table_args__ = (
        Index("ix_analytics_events_user_created", "user_id", "created_at"),
    )
