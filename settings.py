# settings.py

from typing import Literal

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

    # Hiz siniri deposu. Bos ise surec ici bellek: sinirlar SUREC BASINA
    # ve uygulama N isciyle kosarsa gercek sinir ~N katina cikiyor
    # (olculdu: 1/2/4 isci -> 10/20/31-33, kural 10). Birden fazla isci ya da
    # sunucu varsa verilmeli, ornegin "redis://localhost:6379/0".
    redis_url: str | None = None

    # Ayni ziyaretcinin ayni linke tiklamasi kac saniye icinde TEK
    # sayilsin? 0 = tekillestirme kapali.
    #
    # OLCULDU: tekillestirme yokken tek bir ziyaretcinin ~2 saniyede
    # yaptigi 10 istek 10 tiklama olarak sayiliyordu.
    #
    # NEDEN 30 SANIYE -- pencerenin KAPSAMASI gerekenler:
    #   - Cift tiklama (tarayici esigi ~500 ms).
    #   - Sabirsiz tekrar dokunuslar ("acilmadi galiba"), 2-5 saniye.
    #   - Geri gelip yeniden tiklama.
    #
    # ...ve YUTMAMASI gerekenler, asil kisit bu: ANAHTAR IP, yani
    # ziyaretci kimligi yok. Ayni adresin arkasinda (okul, ofis,
    # mobil operatorun CGNAT'i) bircok gercek kisi olabilir. Pencere
    # uzadikca ayni linke tiklayan FARKLI kisiler tek kisi sayilmaya
    # baslar; 30 dakikalik bir "oturum" penceresi (Google Analytics
    # varsayilani) onlarca gercek tiklamayi tek tiklamaya indirirdi.
    #
    # Bu metrigin isi "kac FARKLI KISI tikladi" degil, "linke ne kadar
    # trafik gitti" -- yani hedef tekil ziyaretci saymak degil,
    # KAZALARI temizlemek. Kisa pencere tam olarak bunu yapiyor.
    #
    # BU BIR KOTUYE KULLANIM ONLEMI DEGIL: 30 saniye, sayiyi bilerek
    # sisirmek isteyen birini dakikada 2 tiklamada tutuyor (gunde
    # ~2.880). Sayiyi kazalardan koruyor, kasittan degil.
    click_dedup_seconds: int = 30

    # --- Dosya deposu (avatarlar) -----------------------------------------
    #
    # "local": dosyalar MEDIA_ROOT'a yaziliyor ve uygulama onlari /media
    # altindan kendisi sunuyor. Tek sunucu ve gelistirme icin; birden
    # fazla sunucuda her biri kendi diskini gorur.
    #
    # "s3": S3 uyumlu bir servis (AWS S3, Cloudflare R2, MinIO). Dosyalari
    # uygulama SUNMUYOR; S3_PUBLIC_URL'deki adres (kovanin herkese acik
    # alan adi ya da onundeki CDN) sunuyor.
    storage_backend: Literal["local", "s3"] = "local"

    # local: dosyalarin yazildigi dizin ve tarayicinin onlara ulastigi
    # adres. MEDIA_URL, uygulamanin /media yolunun DISARIDAN gorunen hali
    # olmali (uretimde orn. https://api.linkyoself.com/media).
    media_root: str = "media"
    media_url: str = "http://localhost:8000/media"

    # s3: kimlik bilgileri bossa boto3'un kendi zinciri (AWS_* ortam
    # degiskenleri, IAM rolu) kullaniliyor. R2/MinIO icin endpoint
    # verilmeli; AWS S3'te bos birakilir.
    s3_bucket: str | None = None
    s3_endpoint_url: str | None = None
    s3_region: str | None = None
    s3_access_key_id: str | None = None
    s3_secret_access_key: str | None = None
    s3_public_url: str | None = None

    # Yuklenen ham dosyanin ust siniri. Telefon fotograflari 3-6 MB
    # arasinda geliyor; 8 MB onlari reddetmiyor. Saklanan dosya bu degil:
    # sunucu 400x400 JPEG/PNG olarak yeniden yaziyor (12 MP fotograftan ~25 KB).
    avatar_max_bytes: int = 8 * 1024 * 1024


settings = Settings()
