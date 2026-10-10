"""Ayarlara gore depo."""

from core.storage.base import Depo


def depo_olustur() -> Depo:
    """settings.storage_backend'e gore depoyu kurar.

    s3 seciliyken eksik ayar varsa uygulama AYAGA KALKMIYOR (bkz.
    main.cors_kaynaklari ile ayni ilke): ilk avatar yuklemesinde 500
    almaktansa baslarken neyin eksik oldugunu soylemek daha iyi.
    """
    from settings import settings

    if settings.storage_backend == "s3":
        from core.storage.s3 import S3Depo

        eksik = [
            ad
            for ad, deger in (
                ("S3_BUCKET", settings.s3_bucket),
                ("S3_PUBLIC_URL", settings.s3_public_url),
            )
            if not deger
        ]
        if eksik:
            raise RuntimeError(
                f"STORAGE_BACKEND=s3 icin eksik ayar: {', '.join(eksik)}"
            )
        return S3Depo(
            kova=settings.s3_bucket,
            kok_adres=settings.s3_public_url,
            endpoint_url=settings.s3_endpoint_url,
            bolge=settings.s3_region,
            erisim_anahtari=settings.s3_access_key_id,
            gizli_anahtar=settings.s3_secret_access_key,
        )

    from core.storage.yerel import YerelDepo

    return YerelDepo(settings.media_root, settings.media_url)
