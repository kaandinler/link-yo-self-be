"""S3 uyumlu depo (AWS S3, Cloudflare R2, MinIO)."""

from starlette.concurrency import run_in_threadpool

from core.storage.base import Depo


class S3Depo(Depo):
    def __init__(
        self,
        kova: str,
        kok_adres: str,
        endpoint_url: str | None = None,
        bolge: str | None = None,
        erisim_anahtari: str | None = None,
        gizli_anahtar: str | None = None,
    ):
        # boto3 burada import ediliyor: yerel depoyla calisan bir
        # kurulum onu hic yuklemiyor (olculdu: import + istemci ~0.2 sn).
        import boto3

        self.kova = kova
        self.kok_adres = kok_adres.rstrip("/")
        self._istemci = boto3.client(
            "s3",
            endpoint_url=endpoint_url,
            region_name=bolge,
            aws_access_key_id=erisim_anahtari,
            aws_secret_access_key=gizli_anahtar,
        )

    async def kaydet(self, anahtar: str, veri: bytes, icerik_turu: str) -> str:
        # boto3 senkron; olay dongusunu durdurmasin.
        await run_in_threadpool(
            self._istemci.put_object,
            Bucket=self.kova,
            Key=anahtar,
            Body=veri,
            ContentType=icerik_turu,
            # Ad her yuklemede degisiyor (bkz. base.avatar_anahtari).
            CacheControl="public, max-age=31536000, immutable",
        )
        return self.adres(anahtar)

    async def sil(self, anahtar: str) -> None:
        # S3'te olmayan bir nesneyi silmek de basarili sayiliyor.
        await run_in_threadpool(
            self._istemci.delete_object, Bucket=self.kova, Key=anahtar
        )
