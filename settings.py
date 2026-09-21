# settings.py

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
    )

    database_url: str
    secret_key: str
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 30

    # SQLAlchemy engine SQL loglarini stdout'a yazsin mi?
    # (Onceden kodda sabit True idi; production'da ve testlerde istenmiyor.)
    db_echo: bool = False

    # E-posta (SMTP). smtp_host bos birakilirsa e-posta gonderilmez,
    # icerik log'a yazilir - gelistirme ve test icin.
    smtp_host: str | None = None
    smtp_port: int = 587
    smtp_username: str | None = None
    smtp_password: str | None = None
    smtp_from: str = "no-reply@linkyoself.local"
    smtp_use_tls: bool = True

    # Sifre sifirlama baglantisinin isaret ettigi frontend adresi.
    frontend_url: str = "http://localhost:3000"
    password_reset_token_expire_minutes: int = 60

    # Dogrulama baglantisi sifirlamadan uzun yasiyor: kullanicinin e-postasini
    # hemen kontrol etmesi gerekmiyor, acil bir islem degil.
    email_verification_token_expire_minutes: int = 60 * 24

    # Ortam değişkeni
    environment: str = "development"

    # Güvenlik ayarları
    allowed_hosts: list[str] | None = None
    allowed_origins: list[str] | None = None

    # Hiz siniri.
    #
    # Kapatmak icin bir anahtar var cunku sinir SUREC ICI bellekte
    # (bkz. core/rate_limit/limiter.py): yuk testi gibi durumlarda
    # kapatilabilmesi gerekiyor. Varsayilan ACIK -- guvenligi varsayilan
    # olarak kapali birakmak, unutuldugunda hic olmamasiyla ayni sey.
    rate_limit_enabled: bool = True

    # Onumuzde kac GUVENILIR ters vekil var?
    #
    # 0 (varsayilan): X-Forwarded-For hic okunmuyor, baglantinin kendi
    # adresi kullaniliyor. Vekil arkasinda DEGILKEN dogrusu bu ve
    # guvenli tarafta olan varsayilan: basligi koru korune okuyan bir
    # sinirlayici, her istekte rastgele bir deger yazan saldirgan
    # tarafindan tamamen atlatilir.
    #
    # Uygulama bir ters vekilin (nginx, Cloudflare, yuk dengeleyici)
    # arkasindaysa BU DEGER AYARLANMALI, yoksa butun istekler vekilin
    # tek adresinden geliyormus gibi gorunur ve tum kullanicilar ayni
    # sayaci paylasir.
    trusted_proxy_count: int = 0


settings = Settings()
